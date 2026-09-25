"""Night Shift 규칙 기반 크리틱 단위 테스트. 네트워크·LLM 없음.

실행: .venv/bin/python -m pytest tests/test_nightshift_critic.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "harness" / "tools"))

import nightshift_critic_rules as cr  # noqa: E402

TEST_PATH = "tests/test_math.py"
BEFORE_TESTS = '''import pytest
from mylib import add

def test_add():
    assert add(1, 2) == 3

def test_add_negative():
    assert add(-1, -1) == -2
    assert add(-1, 1) == 0
'''


def _diff(path, before, after):
    import difflib
    lines = difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"a/{path}", f"b/{path}")
    return f"diff --git a/{path} b/{path}\n" + "".join(lines)


def _runs(before_pass=2, after_pass=2, cov_b=90.0, cov_a=90.0, after_rc=0, after_failed=0, skipped_a=0,
          bench_b=None, bench_a=None):
    def tests(passed, rc, failed, skipped):
        return {"parsed": True, "returncode": rc, "passed": passed, "failed": failed, "errors": 0,
                "skipped": skipped, "xfailed": 0, "xpassed": 0, "timed_out": False, "total": passed + failed + skipped}
    before = {"tests": tests(before_pass, 0, 0, 0), "coverage_pct": cov_b,
              "bench": {"median_s": bench_b[0], "runs": bench_b[1]} if bench_b else None}
    after = {"tests": tests(after_pass, after_rc, after_failed, skipped_a), "coverage_pct": cov_a,
             "bench": {"median_s": bench_a[0], "runs": bench_a[1]} if bench_a else None}
    return before, after


def _eval(after_src, before_src=BEFORE_TESTS, path=TEST_PATH, **kw):
    runs = kw.pop("runs", _runs())
    return cr.evaluate_patch(_diff(path, before_src, after_src), *runs,
                             files_before={path: before_src}, files_after={path: after_src}, **kw)


def _check(rep, name):
    return next(c for c in rep["checks"] if c["name"] == name)


# --- 정직한 패치 ---------------------------------------------------------------
def test_honest_patch_accepted():
    after = BEFORE_TESTS + "\ndef test_add_zero():\n    assert add(0, 0) == 0\n"
    rep = _eval(after, runs=_runs(after_pass=3, cov_a=92.0))
    assert rep["verdict"] == "accept", rep["summary"]
    assert all(c["passed"] for c in rep["checks"])
    assert rep["required_followups"] == []


# --- (a) 테스트 삭제 / skip ---------------------------------------------------
def test_deleted_test_function_rejected():
    after = BEFORE_TESTS.replace("def test_add_negative():\n    assert add(-1, -1) == -2\n    assert add(-1, 1) == 0\n", "")
    rep = _eval(after, runs=_runs(after_pass=1))
    assert rep["verdict"] == "reject"
    c = _check(rep, "no_test_deleted")
    assert not c["passed"] and "test_add_negative" in c["reason"]
    assert any("restore" in f for f in rep["required_followups"])


def test_deleted_test_in_class_rejected():
    before = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(1, 1)\n    def test_b(self):\n        self.assertTrue(True)\n"
    after = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(1, 1)\n"
    rep = _eval(after, before_src=before, runs=_runs(after_pass=1))
    assert "T.test_b" in _check(rep, "no_test_deleted")["reason"]


@pytest.mark.parametrize("marker", [
    "@pytest.mark.skip(reason='flaky')\n",
    "@pytest.mark.skipif(True, reason='x')\n",
    "@pytest.mark.xfail\n",
])
def test_skip_decorator_rejected(marker):
    after = BEFORE_TESTS.replace("def test_add_negative", marker + "def test_add_negative")
    rep = _eval(after, runs=_runs(after_pass=1, skipped_a=1))
    assert rep["verdict"] == "reject"
    assert not _check(rep, "no_skip_added")["passed"]


def test_pytest_skip_call_rejected():
    after = BEFORE_TESTS.replace("    assert add(-1, -1) == -2\n", "    pytest.skip('later')\n    assert add(-1, -1) == -2\n")
    rep = _eval(after, runs=_runs(after_pass=1, skipped_a=1))
    assert not _check(rep, "no_skip_added")["passed"]
    assert not _check(rep, "test_count_not_reduced")["passed"]


def test_pytestmark_module_skip_rejected():
    after = BEFORE_TESTS.replace("from mylib import add\n", "from mylib import add\npytestmark = pytest.mark.skip\n")
    rep = _eval(after, runs=_runs(after_pass=0, skipped_a=2))
    assert not _check(rep, "no_skip_added")["passed"]


def test_unittest_skip_rejected():
    before = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(1, 1)\n"
    after = "import unittest\nclass T(unittest.TestCase):\n    @unittest.skip('x')\n    def test_a(self):\n        self.assertEqual(1, 1)\n"
    rep = _eval(after, before_src=before, runs=_runs(before_pass=1, after_pass=0, skipped_a=1))
    assert not _check(rep, "no_skip_added")["passed"]


def test_importorskip_is_not_a_skip_marker():
    after = BEFORE_TESTS.replace("import pytest\n", "import pytest\nnp = pytest.importorskip('numpy')\n")
    rep = _eval(after)
    assert _check(rep, "no_skip_added")["passed"]


def test_test_file_deleted_entirely_rejected():
    patch = f"diff --git a/{TEST_PATH} b/{TEST_PATH}\ndeleted file mode 100644\n--- a/{TEST_PATH}\n+++ /dev/null\n@@ -1,3 +0,0 @@\n-def test_add():\n-    assert 1\n-\n"
    rep = cr.evaluate_patch(patch, *_runs(after_pass=0), files_before={TEST_PATH: BEFORE_TESTS}, files_after={TEST_PATH: None})
    assert not _check(rep, "no_test_deleted")["passed"]


# --- (b) assert 수 --------------------------------------------------------------
def test_assert_count_reduced_rejected():
    after = BEFORE_TESTS.replace("    assert add(-1, 1) == 0\n", "")
    rep = _eval(after)
    c = _check(rep, "assert_count_not_reduced")
    assert not c["passed"] and "3 -> 2" in c["reason"]


def test_unittest_assert_methods_counted():
    before = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(1, 1)\n        self.assertTrue(True)\n"
    after = before.replace("        self.assertTrue(True)\n", "")
    rep = _eval(after, before_src=before, runs=_runs(before_pass=1, after_pass=1))
    assert not _check(rep, "assert_count_not_reduced")["passed"]


# --- (c) 커버리지 ---------------------------------------------------------------
def test_coverage_drop_rejected():
    rep = _eval(BEFORE_TESTS + "\n# comment\n", runs=_runs(cov_b=91.5, cov_a=90.9))
    c = _check(rep, "coverage_not_dropped")
    assert not c["passed"] and "91.50% -> 90.90%" in c["reason"]


def test_coverage_missing_is_skipped_not_failed():
    rep = _eval(BEFORE_TESTS + "\n# comment\n", runs=_runs(cov_b=None, cov_a=None))
    assert _check(rep, "coverage_not_dropped")["passed"]


# --- (d) 벤치마크 ---------------------------------------------------------------
LIB = "mylib.py"
LIB_BEFORE = "def add(a, b):\n    return a + b\n"
LIB_AFTER = "def add(a, b):\n    return a.__add__(b)\n"


def _bench_eval(bench_b, bench_a, claims=True):
    return cr.evaluate_patch(_diff(LIB, LIB_BEFORE, LIB_AFTER), *_runs(bench_b=bench_b, bench_a=bench_a),
                             files_before={LIB: LIB_BEFORE}, files_after={LIB: LIB_AFTER}, claims_bench_improvement=claims)


def test_bench_improvement_below_5pct_rejected():
    rep = _bench_eval((1.00, [1.0, 1.0, 1.0]), (0.97, [0.97, 0.96, 0.98]))
    c = _check(rep, "benchmark_claim")
    assert not c["passed"] and "below 5%" in c["reason"]


def test_bench_one_worse_run_rejected():
    rep = _bench_eval((1.00, [1.0, 1.0, 1.0]), (0.80, [0.79, 0.80, 1.05]))
    c = _check(rep, "benchmark_claim")
    assert not c["passed"] and "1/3" in c["reason"]


def test_bench_real_improvement_accepted():
    rep = _bench_eval((1.00, [1.0, 1.0, 1.0]), (0.80, [0.79, 0.80, 0.82]))
    assert _check(rep, "benchmark_claim")["passed"]
    assert rep["verdict"] == "accept"


def test_bench_claim_without_measurement_rejected():
    rep = _bench_eval(None, None)
    assert not _check(rep, "benchmark_claim")["passed"]


def test_no_bench_claim_skips_rule():
    rep = _bench_eval((1.0, [1.0]), (1.2, [1.2]), claims=False)
    assert _check(rep, "benchmark_claim")["passed"]


# --- (e) 범위 -------------------------------------------------------------------
def test_out_of_scope_file_rejected():
    rep = cr.evaluate_patch(_diff("mylib/core.py", LIB_BEFORE, LIB_AFTER), *_runs(),
                            files_before={"mylib/core.py": LIB_BEFORE}, files_after={"mylib/core.py": LIB_AFTER},
                            allowed_globs=["tests/*"])
    c = _check(rep, "files_in_scope")
    assert not c["passed"] and "mylib/core.py" in c["reason"]


def test_in_scope_file_passes():
    rep = _eval(BEFORE_TESTS + "\ndef test_more():\n    assert add(2, 2) == 4\n", allowed_globs=["tests/*"], runs=_runs(after_pass=3))
    assert _check(rep, "files_in_scope")["passed"]


# --- (f) 비밀 -------------------------------------------------------------------
@pytest.mark.parametrize("line", [
    "AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'",
    "NV_KEY = 'nvapi-abcdefghijklmnop'",
    "PEM = '-----BEGIN RSA PRIVATE KEY-----'",
    "TOKEN = 'ghp_" + "a" * 36 + "'",
    "password = 'hunter2hunter2hunter2'",
])
def test_secret_pattern_rejected(line):
    after = BEFORE_TESTS + "\n" + line + "\n"
    rep = _eval(after)
    assert not _check(rep, "no_secrets_added")["passed"]
    assert rep["verdict"] == "reject"


def test_removed_secret_is_not_flagged():
    before = BEFORE_TESTS + "\nKEY = 'nvapi-abcdefghijklmnop'\n"
    rep = _eval(BEFORE_TESTS, before_src=before)
    assert _check(rep, "no_secrets_added")["passed"]


# --- (g) 보조 규칙 --------------------------------------------------------------
def test_failing_tests_after_rejected():
    rep = _eval(BEFORE_TESTS + "\n# c\n", runs=_runs(after_rc=1, after_failed=1, after_pass=1))
    assert not _check(rep, "tests_pass_after")["passed"]


def test_fewer_executed_tests_rejected():
    rep = _eval(BEFORE_TESTS + "\n# c\n", runs=_runs(before_pass=5, after_pass=4))
    assert not _check(rep, "test_count_not_reduced")["passed"]


# --- diff 파서와 휴리스틱 경로 ----------------------------------------------------
def test_parse_diff_new_and_deleted_files():
    patch = ("diff --git a/tests/test_new.py b/tests/test_new.py\nnew file mode 100644\n--- /dev/null\n+++ b/tests/test_new.py\n"
             "@@ -0,0 +1,2 @@\n+def test_x():\n+    assert 1\n"
             "diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x = 1\n")
    d = cr.parse_diff(patch)
    assert d["tests/test_new.py"]["is_new"] and d["tests/test_new.py"]["added"] == ["def test_x():", "    assert 1"]
    assert d["old.py"]["is_deleted"] and d["old.py"]["removed"] == ["x = 1"]


def test_diff_heuristic_without_file_contents():
    after = BEFORE_TESTS.replace("def test_add_negative():\n    assert add(-1, -1) == -2\n    assert add(-1, 1) == 0\n", "")
    rep = cr.evaluate_patch(_diff(TEST_PATH, BEFORE_TESTS, after), *_runs(after_pass=1))
    assert rep["verdict"] == "reject"
    assert "heuristic" in _check(rep, "no_test_deleted")["reason"]
    assert not _check(rep, "assert_count_not_reduced")["passed"]


def test_report_shape_matches_critic_report_fields():
    rep = _eval(BEFORE_TESTS + "\n# c\n")
    assert set(rep) >= {"verdict", "checks", "required_followups"}
    assert rep["verdict"] in ("accept", "reject")
    for c in rep["checks"]:
        assert set(c) == {"name", "passed", "reason"}


def test_pytest_raises_context_counts_as_assertion():
    before = "from pytest import raises\nfrom mylib import div\n\ndef test_div_zero():\n    with raises(ZeroDivisionError):\n        div(1, 0)\n"
    after = "from pytest import raises\nfrom mylib import div\n\ndef test_div_zero():\n    div(1, 1)\n"
    rep = _eval(after, before_src=before, runs=_runs(before_pass=1, after_pass=1))
    c = _check(rep, "assert_count_not_reduced")
    assert not c["passed"] and "1 -> 0" in c["reason"]
