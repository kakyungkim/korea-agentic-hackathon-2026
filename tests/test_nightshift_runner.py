"""Night Shift 실행기 테스트: 임시 git 저장소에서 실제 pytest를 돌린다. 네트워크·LLM 없음.

실행: .venv/bin/python -m pytest tests/test_nightshift_runner.py -q
"""
import difflib
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "harness" / "tools"))

import nightshift_runner as nr  # noqa: E402

PY = sys.executable
LIB = "def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n"
TESTS = "from mylib import add, mul\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
CMD_TEST = f"{PY} -m pytest -q -p no:cacheprovider"


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    (d / "mylib.py").write_text(LIB)
    (d / "tests").mkdir()
    (d / "tests" / "test_mylib.py").write_text(TESTS)
    (d / "tests" / "__init__.py").write_text("")
    _git(d, "init", "-q")
    _git(d, "-c", "user.name=t", "-c", "user.email=t@x", "add", "-A")
    _git(d, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "-m", "base")
    return str(d)


def _patch(path, before, after):
    body = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"a/{path}", f"b/{path}"))
    return f"diff --git a/{path} b/{path}\n{body}"


HONEST = _patch("tests/test_mylib.py", TESTS, TESTS + "\n\ndef test_mul():\n    assert mul(2, 3) == 6\n")


# --- 파서 ---------------------------------------------------------------------
def test_parse_pytest_summary():
    out = "....s\n===== 4 passed, 1 skipped, 2 xfailed in 0.12s =====\n"
    r = nr.parse_test_output(out, 0)
    assert r["parsed"] and r["passed"] == 4 and r["skipped"] == 1 and r["xfailed"] == 2 and r["total"] == 7


def test_parse_pytest_failed_summary():
    r = nr.parse_test_output("== 1 failed, 3 passed, 1 error in 1.0s ==", 1)
    assert r["failed"] == 1 and r["passed"] == 3 and r["errors"] == 1


def test_parse_unittest_summary():
    out = "...\n----\nRan 5 tests in 0.01s\n\nFAILED (failures=1, skipped=1)\n"
    r = nr.parse_test_output(out, 1)
    assert r["parsed"] and r["passed"] == 3 and r["failed"] == 1 and r["skipped"] == 1


def test_parse_bench_last_number():
    assert nr.parse_bench_output("warming up\nbench: 0.0421 s\n") == pytest.approx(0.0421)
    assert nr.parse_bench_output("elapsed=1.5e-3\n\n") == pytest.approx(0.0015)
    assert nr.parse_bench_output("no numbers here") is None


# --- push 금지 -----------------------------------------------------------------
@pytest.mark.parametrize("sub", ["push", "pull", "fetch", "remote"])
def test_git_wrapper_refuses_remote_subcommands(repo, sub):
    with pytest.raises(nr.NightShiftPolicyError):
        nr._git(repo, [sub, "origin", "main"])
    with pytest.raises(nr.NightShiftPolicyError):
        nr._git(repo, ["-c", "x=y", sub])


def test_run_experiment_never_invokes_git_push(repo, monkeypatch):
    seen = []
    real_run = subprocess.run

    def spy(argv, *a, **kw):
        if isinstance(argv, (list, tuple)) and argv and os.path.basename(str(argv[0])) == "git":
            seen.append([str(x) for x in argv])
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(nr.subprocess, "run", spy)
    res = nr.run_experiment(repo, HONEST, CMD_TEST, timeout=120, exp_id="pushcheck", with_coverage=False)
    assert res["status"] == "ok", res
    assert seen, "git was expected to be called"
    for argv in seen:
        assert not set(argv) & nr.FORBIDDEN_GIT_SUBCOMMANDS, argv


def test_runner_source_has_no_push_call_site():
    src = Path(nr.__file__).read_text(encoding="utf-8")
    # 'push'라는 낱말은 금지 목록 정의에만 등장해야 한다.
    lines = [ln for ln in src.splitlines() if "push" in ln]
    assert all("FORBIDDEN_GIT_SUBCOMMANDS" in ln or ln.strip().startswith(("#", "-", '"""', "  push")) or "forbidden" in ln.lower() or "원본" in ln or "push 대상" in ln for ln in lines), lines


# --- 실험 실행 -----------------------------------------------------------------
def test_honest_patch_runs_and_returns_to_base(repo):
    res = nr.run_experiment(repo, HONEST, CMD_TEST, timeout=180, exp_id="honest", goal="test coverage: mul")
    assert res["status"] == "ok", res
    assert res["before"]["tests"]["passed"] == 1
    assert res["after"]["tests"]["passed"] == 2
    assert res["files_changed"] == ["tests/test_mylib.py"]
    assert "1 file changed" in res["diff_stat"]
    assert res["patch"]["insertions"] == 4 and res["patch"]["deletions"] == 0
    assert res["branch"] == "exp/honest"
    # 브랜치는 남고, 작업 트리는 base로 돌아왔고 깨끗하다.
    assert "exp/honest" in _git(repo, "branch", "--list", "exp/*")
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == res["base_ref"]
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    assert (Path(repo) / "tests" / "test_mylib.py").read_text() == TESTS
    assert res["commit_sha"] and res["commit_sha"] != res["base_sha"]
    assert "def test_mul" in res["diff_text"]
    import json
    json.dumps(res)


def test_coverage_measured_when_available(repo):
    pytest.importorskip("coverage")
    res = nr.run_experiment(repo, HONEST, CMD_TEST, timeout=180, exp_id="cov")
    assert res["status"] == "ok", res
    assert res["before"]["coverage_pct"] == pytest.approx(75.0)   # mylib.py 4 statements, mul body uncovered
    assert res["after"]["coverage_pct"] == pytest.approx(100.0)


def test_patch_file_and_git_am_command(repo, tmp_path):
    out = tmp_path / "out"
    res = nr.run_experiment(repo, HONEST, CMD_TEST, timeout=180, exp_id="am", out_dir=str(out), with_coverage=False)
    assert res["patch_path"] and os.path.exists(res["patch_path"])
    assert res["apply_cmd"].startswith("git am ")
    text = Path(res["patch_path"]).read_text()
    assert text.startswith("From ") and "def test_mul" in text
    # 만든 패치를 base에 git am 해 보면 같은 내용이 붙는다.
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", repo, str(other)], check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x", "am", res["patch_path"]], cwd=other, check=True, capture_output=True)
    assert "def test_mul" in (other / "tests" / "test_mylib.py").read_text()


def test_bench_runs_three_times_and_reports_median(repo):
    bench = f'{PY} -c "import random; print(\'t=\', 0.5)"'
    res = nr.run_experiment(repo, HONEST, CMD_TEST, cmd_bench=bench, timeout=180, exp_id="bench", with_coverage=False)
    b = res["after"]["bench"]
    assert b["repeats"] == 3 and len(b["runs"]) == 3 and b["median_s"] == pytest.approx(0.5)


def test_failing_patch_reports_tests_failed(repo):
    bad = _patch("mylib.py", LIB, LIB.replace("return a + b", "return a - b"))
    res = nr.run_experiment(repo, bad, CMD_TEST, timeout=180, exp_id="bad", with_coverage=False)
    assert res["status"] == "tests_failed"
    assert res["after"]["tests"]["failed"] == 1
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""


def test_garbage_patch_is_apply_failed(repo):
    res = nr.run_experiment(repo, "diff --git a/nope.py b/nope.py\n--- a/nope.py\n+++ b/nope.py\n@@ -1 +1 @@\n-x\n+y\n", CMD_TEST, exp_id="garbage")
    assert res["status"] == "apply_failed"
    assert res["patch"]["check_error"]
    assert res["after"] is None
    assert "exp/garbage" not in _git(repo, "branch", "--list")


def test_dirty_tree_is_refused(repo):
    (Path(repo) / "mylib.py").write_text(LIB + "# dirty\n")
    res = nr.run_experiment(repo, HONEST, CMD_TEST, exp_id="dirty")
    assert res["status"] == "error" and "uncommitted" in res["error"]


def test_timeout_is_reported(repo):
    slow = f'{PY} -c "import time; time.sleep(5)"'
    res = nr.run_experiment(repo, HONEST, slow, timeout=1, exp_id="slow")
    assert res["status"] == "timeout"
    assert res["after"]["tests"]["timed_out"] is True
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == res["base_ref"]


def test_baseline_reuse_skips_before_measurement(repo):
    base = nr.measure(repo, CMD_TEST, timeout=120, with_coverage=False)
    res = nr.run_experiment(repo, HONEST, CMD_TEST, timeout=120, exp_id="reuse", baseline=base, with_coverage=False)
    assert res["before"] is base and res["durations_s"]["before"] < 0.05


def test_prepare_repo_copy_drops_remote(repo, tmp_path):
    copy = nr.prepare_repo_copy(repo, str(tmp_path / "copy"))
    remotes = subprocess.run(["git", "remote", "-v"], cwd=copy, capture_output=True, text=True).stdout
    assert remotes.strip() == ""
