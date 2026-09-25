"""openFDA 도구 테스트. 단위 테스트는 오프라인, 라이브 테스트는 @pytest.mark.network.

실행: .venv/bin/pytest tests/test_pharmasignal_openfda.py -m "not network"   # 오프라인만
"""
import pytest

# 도구 모듈은 반드시 패키지 경로로 import 한다. sys.path 로 최상위 모듈로도 불러오면
# @register_function 이 두 번 돌아 같은 짧은 이름(openfda_faers 등)이 둘이 되고,
# NAT 가 YAML 의 _type 을 해석하지 못한다 (nat/cli/type_registry.py _do_compute_annotation).
from harness.tools import pharmasignal_openfda as ofda


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


# --------------------------------------------------------------------------------------
# NAT 등록 래퍼 (openfda_faers). 네트워크 없이 배선, 설정값, 출력 스키마만 본다.
# --------------------------------------------------------------------------------------
FAERS_META = {"meta": {"results": {"total": 7}, "last_updated": "20260901"}}


def test_openfda_config_type_and_defaults():
    assert ofda.OpenFdaFaersConfig.static_type() == "openfda_faers"   # YAML 의 _type 값
    cfg = ofda.OpenFdaFaersConfig()
    assert cfg.name_field == "generic" and cfg.use_cache is True and cfg.cache_dir is None


def test_faers_report_model_keeps_fields_and_serializes():
    raw = {
        "tool": "openfda_faers", "drug": "metformin", "reaction": "Lactic acidosis",
        "name_field": "generic",
        "counts": {"a": 40, "b": 960, "c": 200, "d": 98800},
        "evidence_ids": ["https://api.fda.gov/drug/event.json?limit=1"],
        "errors": [],
    }
    raw.update(ofda.disproportionality(40, 960, 200, 98800))
    report = ofda.FaersReport.model_validate(raw)
    assert report.prr == pytest.approx(19.8, rel=1e-6)
    assert report.evans_signal is True and report.counts["a"] == 40
    assert report.evidence_ids and report.errors == []
    import json
    assert json.loads(report.model_dump_json())["prr"] == pytest.approx(19.8, rel=1e-6)


def test_openfda_tool_returns_report_and_str_converter(monkeypatch):
    """등록 래퍼가 faers_disproportionality 를 그대로 부르고 FaersReport 로 돌려주는지."""
    import asyncio

    monkeypatch.setattr(ofda, "http_get", lambda url, **kw: FAERS_META)

    async def run():
        cfg = ofda.OpenFdaFaersConfig(use_cache=False)
        async with ofda.openfda_faers(cfg, None) as info:
            assert list(info.input_schema.model_fields) == ["drug", "reaction"]
            assert info.single_output_schema is ofda.FaersReport
            assert info.description.startswith("Query openFDA FAERS")
            out = await info.single_fn(info.input_schema(drug="metformin", reaction="Lactic acidosis"))
            return out, info.converters[0](out)

    report, as_str = asyncio.run(run())
    assert isinstance(report, ofda.FaersReport)
    assert report.counts["n_total"] == 7 and report.drug == "metformin"
    assert as_str.startswith("{") and '"tool":"openfda_faers"' in as_str


def test_openfda_tool_rejects_bad_name_field_at_build():
    import asyncio

    async def run():
        async with ofda.openfda_faers(ofda.OpenFdaFaersConfig(name_field="nope"), None):
            pass

    with pytest.raises(ValueError):
        asyncio.run(run())
