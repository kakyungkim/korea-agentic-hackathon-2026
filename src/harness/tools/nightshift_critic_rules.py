"""Night Shift 규칙 기반 크리틱 (LLM 없이 동작).

패치(unified diff)와 전후 실행 결과를 받아 규칙으로 accept/reject를 판정한다.
LLM 크리틱(configs/critic.yml)이 판단하기 전에 먼저 도는 고정 규칙이며, 하나라도
걸리면 reject다.

규칙
(a) 테스트 파일에서 테스트 함수 삭제, 또는 skip/xfail 마커·호출 추가 -> reject
(b) assert 문 수 감소 -> reject
(c) 커버리지 하락 -> reject
(d) 벤치마크 개선 주장인데 중앙값 개선 5% 미만, 또는 재측정 3회 중 1회라도 악화 -> reject
(e) 허용 glob 밖 파일 수정 -> reject
(f) 비밀·자격증명 패턴 추가 -> reject
(g) 보조: after 테스트 실패, 테스트 총수 감소 -> reject

반환 형식은 src/harness/schemas.py의 CriticReport와 맞춘 dict
{"verdict", "checks":[{"name","passed","reason"}], "required_followups":[...]}.
(schemas.py는 다른 에이전트가 만들므로 import하지 않는다.)
"""
from __future__ import annotations

import ast
import fnmatch
import re
import subprocess
from typing import Any, Iterable, Sequence

SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("nvidia_api_key", re.compile(r"nvapi-[A-Za-z0-9_\-]{8,}")),
    ("pem_private_key", re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----|-----BEGIN")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("openai_style_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("generic_assignment", re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|password|passwd|auth[_-]?token)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
]
SKIP_DECORATOR_NAMES = {"skip", "skipif", "xfail"}          # pytest.mark.<x>, unittest.skip*
SKIP_CALL_NAMES = {"skip", "xfail"}                        # pytest.skip(), pytest.xfail()
BENCH_MIN_IMPROVEMENT = 0.05
COVERAGE_TOLERANCE = 0.0


# ---------------------------------------------------------------------------
# diff 파싱
# ---------------------------------------------------------------------------
_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_PLUS_FILE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
_MINUS_FILE = re.compile(r"^--- (?:a/)?(.+)$")


def parse_diff(patch_text: str) -> dict[str, dict[str, Any]]:
    """파일별 {added:[...], removed:[...], is_new, is_deleted}를 만든다."""
    files: dict[str, dict[str, Any]] = {}
    cur: dict[str, Any] | None = None
    cur_path = None
    for ln in patch_text.splitlines():
        m = _DIFF_HEADER.match(ln)
        if m:
            cur_path = m.group(2)
            cur = files.setdefault(cur_path, {"added": [], "removed": [], "is_new": False, "is_deleted": False})
            continue
        if ln.startswith("+++ "):
            pm = _PLUS_FILE.match(ln)
            if pm and pm.group(1) != "/dev/null":
                path = pm.group(1)
                if cur is None or cur_path != path:
                    cur_path = path
                    cur = files.setdefault(path, {"added": [], "removed": [], "is_new": False, "is_deleted": False})
            elif pm and cur is not None:
                cur["is_deleted"] = True
            continue
        if ln.startswith("--- "):
            mm = _MINUS_FILE.match(ln)
            if mm and mm.group(1) == "/dev/null" and cur is not None:
                cur["is_new"] = True
            continue
        if cur is None:
            continue
        if ln.startswith("+") and not ln.startswith("+++"):
            cur["added"].append(ln[1:])
        elif ln.startswith("-") and not ln.startswith("---"):
            cur["removed"].append(ln[1:])
    return files


def is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    parts = path.split("/")
    return (name.startswith("test_") and name.endswith(".py")) or name.endswith("_test.py") \
        or ("tests" in parts[:-1] or "test" in parts[:-1]) and name.endswith(".py")


# ---------------------------------------------------------------------------
# AST 분석
# ---------------------------------------------------------------------------
def _safe_parse(src: str | None) -> ast.Module | None:
    if src is None:
        return None
    try:
        return ast.parse(src)
    except SyntaxError:
        return None


def _decorator_name(dec: ast.expr) -> str:
    """@pytest.mark.skip(...) -> 'pytest.mark.skip', @unittest.skip -> 'unittest.skip'."""
    if isinstance(dec, ast.Call):
        dec = dec.func
    parts = []
    while isinstance(dec, ast.Attribute):
        parts.append(dec.attr)
        dec = dec.value
    if isinstance(dec, ast.Name):
        parts.append(dec.id)
    return ".".join(reversed(parts))


def test_functions(tree: ast.Module | None) -> set[str]:
    """모듈·클래스 안의 test* 함수 이름(클래스는 Class.method)."""
    names: set[str] = set()
    if tree is None:
        return names
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name.startswith("test"):
                    names.add(f"{node.name}.{sub.name}")
    return names


def count_skip_markers(tree: ast.Module | None) -> int:
    """skip/skipif/xfail 데코레이터와 pytest.skip()/xfail() 호출, pytestmark 지정 수."""
    if tree is None:
        return 0
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                dn = _decorator_name(dec)
                last = dn.rsplit(".", 1)[-1]
                if last in SKIP_DECORATOR_NAMES or dn.startswith("unittest.skip") or last.startswith("skip"):
                    n += 1
        elif isinstance(node, ast.Call):
            fn = _decorator_name(node.func)
            if fn in {"pytest.skip", "pytest.xfail", "skip", "xfail"} or fn.endswith(".skipTest"):
                n += 1
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "pytestmark":
                    n += 1
    return n


def count_asserts(tree: ast.Module | None) -> int:
    """assert 문 + unittest 스타일 self.assert*() 호출 + pytest.raises()/warns() 컨텍스트 수."""
    if tree is None:
        return 0
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            n += 1
        elif isinstance(node, ast.Call):
            fn = _decorator_name(node.func)
            last = fn.rsplit(".", 1)[-1]
            # unittest self.assert*(), pytest.raises()/warns() 컨텍스트도 검증문으로 센다
            if last.startswith("assert") or fn in {"raises", "pytest.raises", "warns", "pytest.warns"}:
                n += 1
    return n


def _diff_line_count(lines: Iterable[str], pattern: re.Pattern) -> int:
    return sum(1 for ln in lines if pattern.search(ln))


_RE_DEF_TEST = re.compile(r"^\s*(async\s+)?def\s+test\w*\s*\(")
_RE_SKIP = re.compile(r"pytest\.mark\.(skip|skipif|xfail)|pytest\.(skip|xfail)\(|unittest\.skip|\.skipTest\(|^\s*pytestmark\s*=")
_RE_ASSERT = re.compile(r"^\s*assert\b|\.assert\w*\(|\braises\(|\bwarns\(")


# ---------------------------------------------------------------------------
# 개별 규칙
# ---------------------------------------------------------------------------
def _check(name: str, passed: bool, reason: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "reason": reason}


def rule_tests_not_deleted_or_skipped(diff: dict, files_before: dict[str, str | None], files_after: dict[str, str | None]) -> list[dict]:
    deleted: list[str] = []
    skips_added: list[str] = []
    for path, info in diff.items():
        if not is_test_file(path):
            continue
        b_src, a_src = files_before.get(path), files_after.get(path)
        if b_src is not None or a_src is not None:
            tb, ta = _safe_parse(b_src), _safe_parse(a_src)
            if info["is_deleted"] or (b_src is not None and a_src is None):
                gone = sorted(test_functions(tb))
                deleted.extend(f"{path}::{n}" for n in gone)
                if not gone:
                    deleted.append(f"{path} (file removed)")
            else:
                missing = test_functions(tb) - test_functions(ta)
                deleted.extend(f"{path}::{n}" for n in sorted(missing))
                if count_skip_markers(ta) > count_skip_markers(tb):
                    skips_added.append(f"{path} (+{count_skip_markers(ta) - count_skip_markers(tb)} skip/xfail)")
        else:  # 파일 내용이 없으면 diff 줄 수준 휴리스틱
            removed_defs = _diff_line_count(info["removed"], _RE_DEF_TEST)
            added_defs = _diff_line_count(info["added"], _RE_DEF_TEST)
            if removed_defs > added_defs:
                deleted.append(f"{path} (-{removed_defs - added_defs} test def, diff heuristic)")
            sk = _diff_line_count(info["added"], _RE_SKIP) - _diff_line_count(info["removed"], _RE_SKIP)
            if sk > 0:
                skips_added.append(f"{path} (+{sk} skip/xfail, diff heuristic)")
    checks = [
        _check("no_test_deleted", not deleted,
               "no test function removed" if not deleted else "test functions removed: " + ", ".join(deleted)),
        _check("no_skip_added", not skips_added,
               "no skip/xfail marker added" if not skips_added else "skip/xfail added: " + ", ".join(skips_added)),
    ]
    return checks


def rule_assert_count(diff: dict, files_before: dict[str, str | None], files_after: dict[str, str | None]) -> dict:
    before = after = 0
    heuristic = False
    for path, info in diff.items():
        if not path.endswith(".py"):
            continue
        b_src, a_src = files_before.get(path), files_after.get(path)
        if b_src is not None or a_src is not None:
            before += count_asserts(_safe_parse(b_src))
            after += count_asserts(_safe_parse(a_src))
        else:
            heuristic = True
            before += _diff_line_count(info["removed"], _RE_ASSERT)
            after += _diff_line_count(info["added"], _RE_ASSERT)
    passed = after >= before
    tag = " (diff heuristic)" if heuristic else ""
    return _check("assert_count_not_reduced", passed,
                  f"asserts in changed files: {before} -> {after}{tag}")


def rule_coverage(before: dict | None, after: dict | None, tolerance: float = COVERAGE_TOLERANCE) -> dict:
    b = (before or {}).get("coverage_pct")
    a = (after or {}).get("coverage_pct")
    if b is None or a is None:
        return _check("coverage_not_dropped", True, "coverage not measured on both sides; rule skipped")
    passed = a >= b - tolerance
    return _check("coverage_not_dropped", passed, f"coverage {b:.2f}% -> {a:.2f}%")


def rule_benchmark(before: dict | None, after: dict | None, claims_improvement: bool,
                   min_improvement: float = BENCH_MIN_IMPROVEMENT) -> dict:
    if not claims_improvement:
        return _check("benchmark_claim", True, "no performance claim; rule skipped")
    bb = (before or {}).get("bench") or {}
    ab = (after or {}).get("bench") or {}
    bm, am = bb.get("median_s"), ab.get("median_s")
    runs = [r for r in (ab.get("runs") or []) if r is not None]
    if bm is None or am is None or not runs:
        return _check("benchmark_claim", False, "performance claimed but benchmark not measured on both sides")
    if bm <= 0:
        return _check("benchmark_claim", False, f"invalid baseline median {bm}")
    improvement = (bm - am) / bm
    worse_runs = [r for r in runs if r >= bm]
    if improvement < min_improvement:
        return _check("benchmark_claim", False,
                      f"median {bm:.6g}s -> {am:.6g}s ({improvement*100:+.1f}%), below {min_improvement*100:.0f}% threshold")
    if worse_runs:
        return _check("benchmark_claim", False,
                      f"median improved {improvement*100:+.1f}% but {len(worse_runs)}/{len(runs)} re-runs not faster than baseline median {bm:.6g}s")
    return _check("benchmark_claim", True, f"median {bm:.6g}s -> {am:.6g}s ({improvement*100:+.1f}%), all {len(runs)} runs faster")


def rule_scope(diff: dict, allowed_globs: Sequence[str] | None) -> dict:
    if not allowed_globs:
        return _check("files_in_scope", True, "no scope restriction configured")
    outside = [p for p in diff if not any(fnmatch.fnmatch(p, g) for g in allowed_globs)]
    return _check("files_in_scope", not outside,
                  "all changed files within allowed globs" if not outside else "outside scope: " + ", ".join(outside))


def rule_no_secrets(diff: dict) -> dict:
    hits: list[str] = []
    for path, info in diff.items():
        for ln in info["added"]:
            for label, pat in SECRET_PATTERNS:
                if pat.search(ln):
                    hits.append(f"{path}: {label}")
                    break
    return _check("no_secrets_added", not hits,
                  "no credential pattern in added lines" if not hits else "credential-like additions: " + ", ".join(sorted(set(hits))))


def rule_tests_pass(after: dict | None) -> dict:
    t = (after or {}).get("tests") or {}
    if not t:
        return _check("tests_pass_after", False, "no test result after patch")
    if t.get("timed_out"):
        return _check("tests_pass_after", False, "test run timed out")
    ok = t.get("returncode") == 0 and not t.get("failed") and not t.get("errors")
    return _check("tests_pass_after", ok,
                  f"rc={t.get('returncode')} passed={t.get('passed')} failed={t.get('failed')} errors={t.get('errors')} skipped={t.get('skipped')}")


def rule_test_count(before: dict | None, after: dict | None) -> dict:
    tb = ((before or {}).get("tests") or {})
    ta = ((after or {}).get("tests") or {})
    if not tb.get("parsed") or not ta.get("parsed"):
        return _check("test_count_not_reduced", True, "test counts not parsed on both sides; rule skipped")
    b_run, a_run = tb.get("passed", 0) + tb.get("failed", 0), ta.get("passed", 0) + ta.get("failed", 0)
    b_skip, a_skip = tb.get("skipped", 0) + tb.get("xfailed", 0), ta.get("skipped", 0) + ta.get("xfailed", 0)
    passed = a_run >= b_run and a_skip <= b_skip
    return _check("test_count_not_reduced", passed,
                  f"executed tests {b_run} -> {a_run}, skipped/xfailed {b_skip} -> {a_skip}")


# ---------------------------------------------------------------------------
# 종합
# ---------------------------------------------------------------------------
def evaluate_patch(patch_text: str, before: dict | None, after: dict | None, *,
                   files_before: dict[str, str | None] | None = None,
                   files_after: dict[str, str | None] | None = None,
                   allowed_globs: Sequence[str] | None = None,
                   claims_bench_improvement: bool = False) -> dict[str, Any]:
    """순수 함수형 진입점. 파일 내용(files_before/after)이 있으면 AST, 없으면 diff 휴리스틱."""
    diff = parse_diff(patch_text)
    fb, fa = files_before or {}, files_after or {}
    checks: list[dict] = []
    checks += rule_tests_not_deleted_or_skipped(diff, fb, fa)
    checks.append(rule_assert_count(diff, fb, fa))
    checks.append(rule_coverage(before, after))
    checks.append(rule_benchmark(before, after, claims_bench_improvement))
    checks.append(rule_scope(diff, allowed_globs))
    checks.append(rule_no_secrets(diff))
    checks.append(rule_tests_pass(after))
    checks.append(rule_test_count(before, after))
    failed = [c for c in checks if not c["passed"]]
    followups = [_followup(c) for c in failed]
    return {
        "verdict": "reject" if failed else "accept",
        "checks": checks,
        "required_followups": followups,
        "summary": ("all rules passed" if not failed else "; ".join(f"{c['name']}: {c['reason']}" for c in failed)),
        "files_changed": sorted(diff),
    }


def _followup(check: dict) -> str:
    return {
        "no_test_deleted": "restore the removed test functions; if they are obsolete, explain per test in the PR body",
        "no_skip_added": "remove skip/xfail markers and make the test pass, or justify each skip with a linked issue",
        "assert_count_not_reduced": "keep or add assertions; do not weaken existing checks",
        "coverage_not_dropped": "add tests so coverage returns to at least the baseline",
        "benchmark_claim": "re-measure with a stable benchmark; claim improvement only above 5% with all re-runs faster",
        "files_in_scope": "limit the diff to the allowed paths for this goal",
        "no_secrets_added": "remove credential-like strings; load secrets from the environment",
        "tests_pass_after": "fix the failing tests before resubmitting",
        "test_count_not_reduced": "explain why fewer tests executed; restore or replace them",
    }.get(check["name"], f"resolve {check['name']}: {check['reason']}")


def snapshot_files(repo_dir: str, sha: str, paths: Iterable[str]) -> dict[str, str | None]:
    """`git show <sha>:<path>`로 파일 내용을 가져온다(없으면 None). 읽기 전용 git 명령만 쓴다."""
    out: dict[str, str | None] = {}
    for p in paths:
        proc = subprocess.run(["git", "show", f"{sha}:{p}"], cwd=repo_dir, capture_output=True, text=True)
        out[p] = proc.stdout if proc.returncode == 0 else None
    return out


def evaluate_experiment(run_result: dict[str, Any], *, allowed_globs: Sequence[str] | None = None,
                        claims_bench_improvement: bool | None = None) -> dict[str, Any]:
    """nightshift_runner.run_experiment 결과를 받아 판정한다. 파일 내용은 base/commit sha에서 읽는다."""
    patch_text = run_result.get("diff_text") or ""
    repo_dir, base, commit = run_result.get("repo_dir"), run_result.get("base_sha"), run_result.get("commit_sha")
    if claims_bench_improvement is None:
        goal = (run_result.get("goal") or "").lower()
        claims_bench_improvement = any(k in goal for k in ("perf", "성능", "faster", "speed", "benchmark", "최적화"))
    if run_result.get("status") in ("apply_failed", "error"):
        return {
            "verdict": "reject",
            "checks": [_check("patch_applies", False, run_result.get("error") or run_result["patch"].get("check_error") or run_result["status"])],
            "required_followups": ["produce a patch that applies cleanly to the base commit"],
            "summary": f"runner status {run_result.get('status')}",
            "files_changed": run_result.get("files_changed", []),
        }
    paths = list(parse_diff(patch_text))
    fb = fa = None
    if repo_dir and base and commit:
        fb = snapshot_files(repo_dir, base, paths)
        fa = snapshot_files(repo_dir, commit, paths)
    rep = evaluate_patch(patch_text, run_result.get("before"), run_result.get("after"), files_before=fb, files_after=fa,
                         allowed_globs=allowed_globs, claims_bench_improvement=claims_bench_improvement)
    rep["experiment_id"] = run_result.get("id")
    return rep
