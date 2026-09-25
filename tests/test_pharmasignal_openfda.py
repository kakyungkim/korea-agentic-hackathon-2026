"""openFDA 도구 테스트. 단위 테스트는 오프라인, 라이브 테스트는 @pytest.mark.network.

실행: .venv/bin/pytest tests/test_pharmasignal_openfda.py -m "not network"   # 오프라인만
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "harness" / "tools"))

import pharmasignal_openfda as ofda  # noqa: E402


def test_prr_reference_case():
    # a=40, b=960, c=200, d=98800 -> PRR = (40/1000)/(200/99000) = 19.8
    m = ofda.disproportionality(40, 960, 200, 98800)
    assert m["prr"] == pytest.approx(19.8, rel=1e-6)
    assert m["ror"] == pytest.approx((40 * 98800) / (960 * 200), rel=1e-9)
    assert m["chi2"] > 4
    assert m["evans_signal"] is True
    lo, hi = m["prr_ci95"]
    assert lo < 19.8 < hi


def test_prr_zero_guard():
    m = ofda.disproportionality(0, 10, 0, 100)
    assert m["prr"] is None and m["ror"] is None
    assert m["evans_signal"] is False


def test_total_parsing_not_found_is_zero():
    assert ofda._total({"__error__": 404, "body": '{"error":{"code":"NOT_FOUND"}}'}) == (0, None)
    assert ofda._total({"error": {"code": "NOT_FOUND", "message": "No matches found!"}}) == (0, None)
    total, err = ofda._total({"__error__": 500, "body": ""})
    assert total is None and err.startswith("http_error")
    assert ofda._total({"meta": {"results": {"total": 12}}}) == (12, None)


def test_query_url_shape():
    url = ofda._url(f"{ofda._drug_clause('Metformin', 'generic')}+AND+{ofda._reaction_clause('Lactic acidosis')}")
    assert url.startswith("https://api.fda.gov/drug/event.json?search=")
    assert 'patient.drug.openfda.generic_name:"metformin"' in url
    assert 'patient.reaction.reactionmeddrapt.exact:"LACTIC%20ACIDOSIS"' in url
    assert url.endswith("&limit=1")


def test_bad_name_field():
    with pytest.raises(ValueError):
        ofda.faers_disproportionality("metformin", "Lactic acidosis", name_field="nope")


@pytest.mark.network
def test_live_metformin_lactic_acidosis(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    res = ofda.faers_disproportionality("metformin", "Lactic acidosis")
    assert res["errors"] == []
    c = res["counts"]
    assert c["a"] > 0 and c["d"] > c["a"]
    assert res["prr"] > 2 and res["evans_signal"] is True
    assert len(res["evidence_ids"]) == 4
    # 재실행은 캐시에서 온다
    res2 = ofda.faers_disproportionality("metformin", "Lactic acidosis")
    assert res2["cache"]["hits"] == 4 and res2["cache"]["misses"] == 0
    assert res2["counts"] == c
