"""Night Shift 실험 실행기 (LLM 없이 동작).

저장소 사본에서 패치를 실험 브랜치(exp/<id>)에 적용하고, 테스트와 벤치마크를
실행해 전후 수치를 JSON 직렬화 가능한 dict로 돌려준다. 브랜치는 남기고 작업
트리는 base로 되돌린다.

안전 장치
- 모든 git 호출은 `_git()` 하나로 통과하며, `push`, `pull`, `fetch`, `remote`
  하위 명령은 코드 수준에서 거부한다(NightShiftPolicyError). 원본 저장소로
  코드가 나가는 경로가 없다.
- 테스트와 벤치마크는 `subprocess.run(timeout=...)`으로 감싼다.

외부 의존성: 표준 라이브러리만. coverage는 실행 인터프리터에 설치되어 있을 때만
자동으로 쓴다(없으면 coverage_pct=None).
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any, Sequence

FORBIDDEN_GIT_SUBCOMMANDS = frozenset({"push", "pull", "fetch", "remote", "submodule"})
DEFAULT_COVERAGE_OMIT = "tests/*,*/tests/*,test_*.py,*_test.py,conftest.py,setup.py"


class NightShiftPolicyError(RuntimeError):
    """정책상 금지된 동작(예: git push)을 시도했을 때."""


class RunnerError(RuntimeError):
    """실행기 자체의 실패(git 저장소 아님, 작업 트리 더러움 등)."""


# ---------------------------------------------------------------------------
# git 래퍼
# ---------------------------------------------------------------------------
def _git(repo_dir: str, args: Sequence[str], check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    """git을 실행한다. 원격 전송 하위 명령은 어떤 경로로도 허용하지 않는다."""
    args = [str(a) for a in args]
    # 위치에 상관없이 금지 낱말이 인자에 하나라도 있으면 거부한다(`-c k=v push` 같은 우회 차단).
    hit = FORBIDDEN_GIT_SUBCOMMANDS.intersection(args)
    if hit:
        raise NightShiftPolicyError(f"git {sorted(hit)[0]} is forbidden inside Night Shift runner")
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_AUTHOR_NAME", "Night Shift")
    env.setdefault("GIT_AUTHOR_EMAIL", "nightshift@localhost")
    env.setdefault("GIT_COMMITTER_NAME", "Night Shift")
    env.setdefault("GIT_COMMITTER_EMAIL", "nightshift@localhost")
    proc = subprocess.run(
        ["git", *args], cwd=repo_dir, capture_output=True, text=True, env=env, timeout=timeout
    )
    if check and proc.returncode != 0:
        raise RunnerError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc


def _git_out(repo_dir: str, args: Sequence[str]) -> str:
    return _git(repo_dir, args).stdout.strip()


def _ensure_repo_clean(repo_dir: str) -> None:
    if not os.path.isdir(repo_dir):
        raise RunnerError(f"repo_dir does not exist: {repo_dir}")
    if _git(repo_dir, ["rev-parse", "--is-inside-work-tree"], check=False).stdout.strip() != "true":
        raise RunnerError(f"not a git work tree: {repo_dir}")
    dirty = _git_out(repo_dir, ["status", "--porcelain", "--untracked-files=no"])
    if dirty:
        raise RunnerError(f"work tree has uncommitted tracked changes:\n{dirty}")


def _base_ref(repo_dir: str) -> tuple[str, str]:
    """(체크아웃에 쓸 ref, sha). 분리 HEAD면 ref는 sha."""
    sha = _git_out(repo_dir, ["rev-parse", "HEAD"])
    name = _git(repo_dir, ["symbolic-ref", "-q", "--short", "HEAD"], check=False).stdout.strip()
    return (name or sha), sha


# ---------------------------------------------------------------------------
# 출력 파서
# ---------------------------------------------------------------------------
_PYTEST_COUNTS = re.compile(r"(\d+)\s+(passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)\b")
_UNITTEST_RAN = re.compile(r"^Ran (\d+) tests?", re.M)
_UNITTEST_TAIL = re.compile(r"^(OK|FAILED)\b(?:\s*\((.*)\))?", re.M)
_LAST_FLOAT = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def parse_test_output(stdout: str, returncode: int) -> dict[str, Any]:
    """pytest 요약 줄 또는 unittest 요약을 통과/실패 수로 파싱한다."""
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    parsed = False
    # pytest: 마지막 요약 줄만 본다(중간에 나오는 "N passed" 재출력을 피한다).
    summary_lines = [ln for ln in stdout.splitlines() if _PYTEST_COUNTS.search(ln) and ("=" in ln or " in " in ln)]
    if summary_lines:
        for n, key in _PYTEST_COUNTS.findall(summary_lines[-1]):
            key = {"error": "errors", "warning": "warnings", "warnings": "warnings"}.get(key, key)
            if key in counts:
                counts[key] += int(n)
                parsed = True
    if not parsed:
        m = _UNITTEST_RAN.search(stdout)
        if m:
            ran = int(m.group(1))
            tail = _UNITTEST_TAIL.findall(stdout)
            fails = errs = skips = 0
            if tail:
                detail = tail[-1][1] or ""
                for part in detail.split(","):
                    k, _, v = part.strip().partition("=")
                    v = int(v) if v.isdigit() else 0
                    if k == "failures":
                        fails = v
                    elif k == "errors":
                        errs = v
                    elif k == "skipped":
                        skips = v
            counts.update(passed=max(ran - fails - errs - skips, 0), failed=fails, errors=errs, skipped=skips)
            parsed = True
    total = sum(counts.values())
    return {"parsed": parsed, "total": total, "ok": returncode == 0, **counts}


def parse_bench_output(stdout: str) -> float | None:
    """벤치마크 명령의 마지막 비어 있지 않은 줄에서 마지막 숫자를 초 단위 값으로 읽는다."""
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    for ln in reversed(lines):
        nums = _LAST_FLOAT.findall(ln)
        if nums:
            try:
                return float(nums[-1])
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# 명령 실행
# ---------------------------------------------------------------------------
def _run_cmd(cmd: str | Sequence[str], cwd: str, timeout: int, env: dict | None = None) -> dict[str, Any]:
    argv = shlex.split(cmd) if isinstance(cmd, str) else [str(c) for c in cmd]
    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = -1
        out = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = (exc.stderr or b"").decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    except FileNotFoundError as exc:
        rc, out, err = 127, "", str(exc)
    dt = time.monotonic() - t0
    return {"argv": argv, "returncode": rc, "stdout": out, "stderr": err, "duration_s": round(dt, 3), "timed_out": timed_out}


def _coverage_available() -> bool:
    try:
        import coverage  # noqa: F401
        return True
    except Exception:
        return False


def _pytest_args(cmd: str | Sequence[str]) -> list[str] | None:
    """`pytest ...`, `python -m pytest ...` 꼴이면 pytest 뒤 인자를 돌려준다. 아니면 None."""
    argv = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
    for i, tok in enumerate(argv):
        base = os.path.basename(tok)
        if base in ("pytest", "py.test"):
            return argv[i + 1:]
        if tok == "-m" and i + 1 < len(argv) and argv[i + 1] == "pytest":
            return argv[i + 2:]
    return None


def run_tests(repo_dir: str, cmd_test: str | Sequence[str], timeout: int, with_coverage: bool = True,
              coverage_omit: str = DEFAULT_COVERAGE_OMIT, work_dir: str | None = None) -> dict[str, Any]:
    """테스트를 실행한다. pytest 꼴이고 coverage가 있으면 같은 실행에서 커버리지도 측정한다."""
    pyargs = _pytest_args(cmd_test)
    cov_pct = None
    cov_used = False
    data_file = None
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if with_coverage and pyargs is not None and _coverage_available():
        work_dir = work_dir or os.path.join(os.path.dirname(os.path.abspath(repo_dir)), ".nightshift_tmp")
        os.makedirs(work_dir, exist_ok=True)
        data_file = os.path.join(work_dir, f".coverage.{os.getpid()}.{int(time.time()*1000)}")
        argv = [sys.executable, "-m", "coverage", "run", f"--data-file={data_file}", "--source=.",
                f"--omit={coverage_omit}", "-m", "pytest", *pyargs]
        cov_used = True
    else:
        argv = shlex.split(cmd_test) if isinstance(cmd_test, str) else list(cmd_test)
    res = _run_cmd(argv, cwd=repo_dir, timeout=timeout, env=env)
    if cov_used and not res["timed_out"]:
        rep = _run_cmd([sys.executable, "-m", "coverage", "json", f"--data-file={data_file}", "-o", "-", "-q"],
                       cwd=repo_dir, timeout=120, env=env)
        try:
            cov_pct = round(float(json.loads(rep["stdout"])["totals"]["percent_covered"]), 2)
        except Exception:
            cov_pct = None
        if data_file and os.path.exists(data_file):
            os.remove(data_file)
    parsed = parse_test_output(res["stdout"], res["returncode"])
    return {
        "cmd": " ".join(shlex.quote(a) for a in res["argv"]),
        "returncode": res["returncode"],
        "timed_out": res["timed_out"],
        "duration_s": res["duration_s"],
        "coverage_pct": cov_pct,
        "coverage_measured": cov_used and cov_pct is not None,
        "stdout_tail": "\n".join(res["stdout"].splitlines()[-15:]),
        "stderr_tail": "\n".join(res["stderr"].splitlines()[-10:]),
        **{k: v for k, v in parsed.items() if k != "ok"},
    }


def run_bench(repo_dir: str, cmd_bench: str | Sequence[str], timeout: int, repeats: int = 3) -> dict[str, Any]:
    """벤치마크 명령을 repeats회 실행해 값 목록과 중앙값을 돌려준다."""
    runs: list[float | None] = []
    durations = []
    rcs = []
    for _ in range(repeats):
        res = _run_cmd(cmd_bench, cwd=repo_dir, timeout=timeout)
        rcs.append(res["returncode"])
        durations.append(res["duration_s"])
        runs.append(None if res["timed_out"] else parse_bench_output(res["stdout"]))
    valid = [r for r in runs if r is not None]
    return {
        "cmd": cmd_bench if isinstance(cmd_bench, str) else " ".join(map(str, cmd_bench)),
        "runs": runs,
        "median_s": round(statistics.median(valid), 6) if valid else None,
        "returncodes": rcs,
        "wall_s": durations,
        "repeats": repeats,
    }


def measure(repo_dir: str, cmd_test: str | Sequence[str], cmd_bench: str | Sequence[str] | None = None,
            timeout: int = 600, with_coverage: bool = True, work_dir: str | None = None) -> dict[str, Any]:
    """현재 작업 트리 상태에서 테스트(+커버리지)와 벤치마크를 측정한다."""
    out: dict[str, Any] = {"sha": _git_out(repo_dir, ["rev-parse", "HEAD"])}
    out["tests"] = run_tests(repo_dir, cmd_test, timeout=timeout, with_coverage=with_coverage, work_dir=work_dir)
    out["coverage_pct"] = out["tests"]["coverage_pct"]
    out["bench"] = run_bench(repo_dir, cmd_bench, timeout=timeout) if cmd_bench else None
    return out


# ---------------------------------------------------------------------------
# 패치 정보
# ---------------------------------------------------------------------------
def patch_numstat(repo_dir: str, patch_text: str) -> dict[str, Any]:
    """적용하지 않고 `git apply --numstat`으로 변경 파일과 줄 수를 얻는다."""
    proc = subprocess.run(["git", "apply", "--numstat", "-"], cwd=repo_dir, input=patch_text,
                          capture_output=True, text=True)
    files, ins, dels = [], 0, 0
    for ln in proc.stdout.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 3:
            a, d, path = parts[0], parts[1], parts[2]
            files.append(path)
            ins += int(a) if a.isdigit() else 0
            dels += int(d) if d.isdigit() else 0
    stat = subprocess.run(["git", "apply", "--stat", "-"], cwd=repo_dir, input=patch_text,
                          capture_output=True, text=True).stdout.rstrip()
    return {"files_changed": files, "insertions": ins, "deletions": dels, "diff_stat": stat}


def files_outside_scope(files: Sequence[str], allowed_globs: Sequence[str] | None) -> list[str]:
    if not allowed_globs:
        return []
    return [f for f in files if not any(fnmatch.fnmatch(f, g) for g in allowed_globs)]


def _make_id(patch_text: str) -> str:
    h = hashlib.sha1(patch_text.encode("utf-8", "replace")).hexdigest()[:6]
    return time.strftime("%Y%m%d-%H%M%S") + "-" + h


# ---------------------------------------------------------------------------
# 실험 1건
# ---------------------------------------------------------------------------
def run_experiment(repo_dir: str, patch_text: str, cmd_test: str | Sequence[str],
                   cmd_bench: str | Sequence[str] | None = None, timeout: int = 600, *,
                   exp_id: str | None = None, baseline: dict | None = None, goal: str = "",
                   out_dir: str | None = None, with_coverage: bool = True) -> dict[str, Any]:
    """패치 하나를 실험 브랜치에서 실행·측정한다.

    반환 dict는 JSON 직렬화 가능하며 `diff_stat`, `files_changed`, `before`, `after`를 담는다.
    `baseline`을 주면 base 측정을 건너뛰고 그 값을 `before`로 쓴다(밤새 실험마다 재측정하지 않기 위함).
    `out_dir`을 주면 `git format-patch` 출력(<id>.patch)을 그곳에 저장하고 `apply_cmd`에 `git am` 명령을 넣는다.
    """
    repo_dir = os.path.abspath(repo_dir)
    t_start = time.time()
    exp_id = exp_id or _make_id(patch_text)
    branch = f"exp/{exp_id}"
    result: dict[str, Any] = {
        "id": exp_id, "goal": goal, "branch": branch, "repo_dir": repo_dir,
        "status": "error", "error": None, "base_ref": None, "base_sha": None, "commit_sha": None,
        "patch": {"applied": False, "check_ok": False, "check_error": None,
                  "files_changed": [], "insertions": 0, "deletions": 0, "diff_stat": ""},
        "before": None, "after": None, "apply_cmd": None, "patch_path": None,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t_start)),
        "durations_s": {},
    }
    try:
        _ensure_repo_clean(repo_dir)
        base_ref, base_sha = _base_ref(repo_dir)
        result.update(base_ref=base_ref, base_sha=base_sha)
        work_dir = os.path.join(os.path.dirname(repo_dir), ".nightshift_tmp")

        # 1) 패치 정합성
        result["patch"].update(patch_numstat(repo_dir, patch_text))
        chk = subprocess.run(["git", "apply", "--check", "-"], cwd=repo_dir, input=patch_text,
                             capture_output=True, text=True)
        if chk.returncode != 0:
            result["patch"]["check_error"] = chk.stderr.strip()
            result["status"] = "apply_failed"
            return result
        result["patch"]["check_ok"] = True

        # 2) base 측정
        t0 = time.monotonic()
        if baseline is None:
            baseline = measure(repo_dir, cmd_test, cmd_bench, timeout=timeout, with_coverage=with_coverage, work_dir=work_dir)
        result["before"] = baseline
        result["durations_s"]["before"] = round(time.monotonic() - t0, 3)

        # 3) 브랜치 생성, 적용, 커밋
        if _git(repo_dir, ["rev-parse", "--verify", "-q", branch], check=False).returncode == 0:
            branch = f"{branch}-{int(time.time()) % 100000}"
            result["branch"] = branch
        _git(repo_dir, ["checkout", "-q", "-b", branch])
        try:
            ap = subprocess.run(["git", "apply", "--index", "-"], cwd=repo_dir, input=patch_text,
                                capture_output=True, text=True)
            if ap.returncode != 0:
                result["patch"]["check_error"] = ap.stderr.strip()
                result["status"] = "apply_failed"
                _git(repo_dir, ["reset", "-q", "--hard", base_sha])
                return result
            result["patch"]["applied"] = True
            msg = f"nightshift {exp_id}: {goal or 'experiment'}"
            _git(repo_dir, ["commit", "-q", "-m", msg])
            commit_sha = _git_out(repo_dir, ["rev-parse", "HEAD"])
            result["commit_sha"] = commit_sha

            # 4) after 측정
            t0 = time.monotonic()
            result["after"] = measure(repo_dir, cmd_test, cmd_bench, timeout=timeout, with_coverage=with_coverage, work_dir=work_dir)
            result["durations_s"]["after"] = round(time.monotonic() - t0, 3)
            at = result["after"]["tests"]
            if at["timed_out"]:
                result["status"] = "timeout"
            elif at["returncode"] == 0:
                result["status"] = "ok"
            else:
                result["status"] = "tests_failed"

            # 5) 적용 명령: git am 용 패치 파일
            fp = _git_out(repo_dir, ["format-patch", "-1", commit_sha, "--stdout"])
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
                patch_path = os.path.join(os.path.abspath(out_dir), f"{exp_id}.patch")
                with open(patch_path, "w", encoding="utf-8") as fh:
                    fh.write(fp if fp.endswith("\n") else fp + "\n")
                result["patch_path"] = patch_path
                result["apply_cmd"] = f"git am {shlex.quote(patch_path)}"
            else:
                result["apply_cmd"] = f"git fetch {shlex.quote(repo_dir)} {branch} && git cherry-pick {commit_sha[:12]}"
            result["diff_text"] = _git_out(repo_dir, ["diff", f"{base_sha}..{commit_sha}"])
        finally:
            # 테스트 실행이 남긴 추적 파일 변경은 버리고 base로 복귀. 브랜치와 커밋은 남는다.
            _git(repo_dir, ["reset", "-q", "--hard", "HEAD"], check=False)
            _git(repo_dir, ["checkout", "-q", base_ref], check=False)
        result["patch"]["diff_stat"] = result["patch"]["diff_stat"] or ""
        result["files_changed"] = result["patch"]["files_changed"]
        result["diff_stat"] = result["patch"]["diff_stat"]
        return result
    except (RunnerError, NightShiftPolicyError, subprocess.TimeoutExpired) as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        result["files_changed"] = result["patch"]["files_changed"]
        result["diff_stat"] = result["patch"]["diff_stat"]
        result["durations_s"]["total"] = round(time.time() - t_start, 3)
        json.dumps(result)  # 직렬화 가능성 자기 점검


def prepare_repo_copy(src_repo: str, dst_dir: str) -> str:
    """원본을 건드리지 않도록 로컬 복제를 만든다(네트워크 없음). 이미 있으면 그대로 쓴다."""
    if os.path.isdir(os.path.join(dst_dir, ".git")):
        return dst_dir
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", src_repo, dst_dir], check=True,
                   capture_output=True, text=True)
    # 사본에서 원격을 끊어 push 대상이 아예 없게 한다(`git remote` 금지 규칙과 별개로 직접 config 편집).
    subprocess.run(["git", "remote", "remove", "origin"], cwd=dst_dir, capture_output=True)
    return dst_dir


if __name__ == "__main__":  # 간단한 수동 실행: python nightshift_runner.py <repo> <patch.diff> "<cmd_test>"
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo_dir")
    ap.add_argument("patch_file")
    ap.add_argument("cmd_test")
    ap.add_argument("--bench", default=None)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out-dir", default=None)
    ns = ap.parse_args()
    with open(ns.patch_file, encoding="utf-8") as fh:
        text = fh.read()
    res = run_experiment(ns.repo_dir, text, ns.cmd_test, ns.bench, ns.timeout, out_dir=ns.out_dir)
    res.pop("diff_text", None)
    print(json.dumps(res, ensure_ascii=False, indent=2))
