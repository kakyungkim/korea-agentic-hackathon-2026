"""그림 생성기의 데이터 계약 테스트.

그림을 실제로 렌더하지 않고, 케이스 JSON 에서 값을 꺼내는 계층만 본다.
키가 빠지면 그리지 않고 무엇이 없는지 알리며 멈추는지가 핵심이다.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASE_JSON = ROOT / "eval" / "results" / "case_niraparib.json"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "make_figures", ROOT / "scripts" / "make_figures.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mf = pytest.importorskip("matplotlib") and _load_module()


def test_project_name_is_single_constant():
    """이름은 상수 한 줄이고 파일 이름에는 들어가지 않는다."""
    source = (ROOT / "scripts" / "make_figures.py").read_text(encoding="utf-8")
    assert source.count("PROJECT_NAME = ") == 1
    assert "architecture_pipeline.png" in source
    assert "results_case.png" in source
    assert mf.PROJECT_NAME.lower() not in "architecture_pipeline.png"
    assert mf.PROJECT_NAME.lower() not in "results_case.png"


def test_missing_file_stops():
    with pytest.raises(mf.CaseKeyError) as exc:
        mf.load_case(ROOT / "eval" / "results" / "case_없는파일.json")
    assert "없습니다" in str(exc.value)


@pytest.mark.skipif(not CASE_JSON.exists(), reason="케이스 결과 파일이 없다")
def test_load_case_reads_both_paths():
    case = mf.load_case(CASE_JSON)
    assert len(case["paths"]) == 2
    a, b = case["paths"]
    assert a["path"] == "A" and b["path"] == "B"
    assert a["vina_score"] < 0 and b["vina_score"] < 0
    assert len(a["diffdock"]) == 3 and len(b["diffdock"]) == 3
    assert a["bdb_present"] is True
    assert b["bdb_present"] is False
    # 사람 근거 세 줄은 화합물 단위라 두 경로에 같은 값이 들어간다.
    assert a["prr"] == b["prr"]
    assert a["labeled"] == b["labeled"]
    assert a["pubmed_total"] == b["pubmed_total"]
    assert set(case["critic"]) == {"supported", "overclaim"}


@pytest.mark.skipif(not CASE_JSON.exists(), reason="케이스 결과 파일이 없다")
def test_missing_key_names_what_is_missing(tmp_path):
    payload = json.loads(CASE_JSON.read_text(encoding="utf-8"))
    del payload["paths"][1]["steps"]["diffdock"]["position_confidence"]
    del payload["critic_verdicts"]["overclaim"]["stage3"]["checks"]
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(mf.CaseKeyError) as exc:
        mf.load_case(broken)
    message = str(exc.value)
    assert "paths.1.steps.diffdock.position_confidence" in message
    assert "critic_verdicts.overclaim.stage3.checks" in message
