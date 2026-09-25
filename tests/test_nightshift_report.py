"""Night Shift 아침 보고서 렌더 테스트. 네트워크·LLM 없음."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "harness" / "tools"))

import nightshift_report as rp  # noqa: E402


def _runner(exp_id, status="ok", cov=(80.0, 82.5), passed=(10, 11)):
    return {"id": exp_id, "goal": "g", "branch": f"exp/{exp_id}", "status": status, "base_sha": "a" * 40, "commit_sha": "b" * 40,
            "files_changed": ["tests/test_x.py"], "diff_stat": " tests/test_x.py | 4 ++++\n 1 file changed, 4 insertions(+)",
            "before": {"tests": {"passed": passed[0], "failed": 0, "errors": 0, "skipped": 0, "duration_s": 1.2}, "coverage_pct": cov[0], "bench": None},
            "after": {"tests": {"passed": passed[1], "failed": 0, "errors": 0, "skipped": 0, "duration_s": 1.3}, "coverage_pct": cov[1], "bench": None},
            "apply_cmd": f"git am /out/{exp_id}.patch", "durations_s": {"total": 5.5}, "diff_text": "SHOULD_NOT_APPEAR"}


def _critic(verdict):
    return {"verdict": verdict, "checks": [{"name": "no_test_deleted", "passed": verdict == "accept", "reason": "<b>x</b> & y"}],
            "required_followups": [] if verdict == "accept" else ["restore tests"]}


def _records():
    return [rp.make_record("테스트 추가: mul", _runner("e1"), _critic("accept")),
            rp.make_record("테스트 삭제로 통과", _runner("e2", passed=(10, 9), cov=(80.0, 70.0)), _critic("reject"))]


def test_make_record_drops_full_diff():
    rec = rp.make_record("g", _runner("e1"), _critic("accept"))
    assert "diff_text" not in rec["runner"]
    json.dumps(rec)


def test_markdown_contains_cards_and_apply_cmd_only_for_accepted():
    md = rp.render_markdown(_records(), {"blocked_network": 3, "blocked_write": 1})
    assert "실험 2건 중 통과 1건, 반려 1건" in md
    assert "### 1. [통과] 테스트 추가: mul" in md and "### 2. [반려] 테스트 삭제로 통과" in md
    assert md.count("git am /out/e1.patch") == 1 and "git am /out/e2.patch" not in md
    assert "| 커버리지 | 80.00% | 82.50% |" in md
    assert "| 차단된 네트워크 시도 | 3 |" in md
    assert "restore tests" in md


def test_html_is_single_file_responsive_and_escaped():
    html = rp.render_html(_records(), {"blocked_network": 3, "blocked_write": 1, "allowed_hosts": ["pypi.org"]})
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "max-width:1080px" in html and "@media (max-width:640px)" in html and "grid-template-columns:1fr" in html
    assert not re.search(r'<(script|link)\b', html), "no external resources or scripts"
    assert "&lt;b&gt;x&lt;/b&gt; &amp; y" in html and "<b>x</b>" not in html
    assert "SHOULD_NOT_APPEAR" not in html
    assert html.count("git am /out/e1.patch") == 1 and "git am /out/e2.patch" not in html
    assert 'data-verdict="accept"' in html and 'data-verdict="reject"' in html
    assert ">4<" in html  # 정책 차단 시도 합계 3+1
    assert "pypi.org" in html


def test_write_report_creates_both_files(tmp_path):
    paths = rp.write_report(_records(), str(tmp_path), {"blocked_network": 0})
    assert Path(paths["md"]).exists() and Path(paths["html"]).exists()
    assert Path(paths["html"]).read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_empty_audit_is_marked_unverified():
    html = rp.render_html(_records(), None)
    assert "[unverified]" in html
