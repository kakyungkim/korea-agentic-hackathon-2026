"""DailyMed 도구 테스트. XML 파싱은 오프라인 픽스처, 라이브는 @pytest.mark.network."""
import pytest

# 도구 모듈은 반드시 패키지 경로로 import 한다. sys.path 로 최상위 모듈로도 불러오면
# @register_function 이 두 번 돌아 같은 짧은 이름(openfda_faers 등)이 둘이 되고,
# NAT 가 YAML 의 _type 을 해석하지 못한다 (nat/cli/type_registry.py _do_compute_annotation).
from harness.tools import pharmasignal_dailymed as dm

SPL_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<document xmlns="urn:hl7-org:v3">
  <title>TESTDRUG tablets</title>
  <component><structuredBody>
    <component><section>
      <code code="34066-1" codeSystem="2.16.840.1.113883.6.1" displayName="BOXED WARNING SECTION"/>
      <title>WARNING: LACTIC ACIDOSIS</title>
      <text><paragraph>Postmarketing cases of lactic acidosis have resulted in death.</paragraph></text>
    </section></component>
    <component><section>
      <code code="43685-7" codeSystem="2.16.840.1.113883.6.1" displayName="WARNINGS AND PRECAUTIONS SECTION"/>
      <title>5 WARNINGS AND PRECAUTIONS</title>
      <component><section>
        <code code="42229-5" codeSystem="2.16.840.1.113883.6.1"/>
        <title>5.1 Lactic Acidosis</title>
        <text><paragraph>There have been cases of lactic acidosis.</paragraph></text>
      </section></component>
    </section></component>
    <component><section>
      <code code="34084-4" codeSystem="2.16.840.1.113883.6.1" displayName="ADVERSE REACTIONS SECTION"/>
      <title>6 ADVERSE REACTIONS</title>
      <text><paragraph>Nausea, diarrhea.</paragraph></text>
    </section></component>
  </structuredBody></component>
</document>"""


def test_fetch_label_sections_parses_fixture(monkeypatch):
    monkeypatch.setattr(dm, "http_get", lambda url, cache=None, is_json=True, **kw: SPL_FIXTURE)
    out = dm.fetch_label_sections("fake-setid", use_cache=False)
    assert out["errors"] == []
    assert out["title"] == "TESTDRUG tablets"
    assert set(out["sections"]) == {"boxed_warning", "warnings_and_precautions", "adverse_reactions"}
    assert "5.1 Lactic Acidosis" in out["sections"]["warnings_and_precautions"]  # 하위 섹션 포함
    assert "34066-1" in out["section_codes_seen"]


def test_find_label_mentions_with_fixture(monkeypatch):
    monkeypatch.setattr(dm, "http_get", lambda url, cache=None, is_json=True, **kw: SPL_FIXTURE)
    out = dm.find_label_mentions("testdrug", "lactic acidosis", setids=["fake-setid"], use_cache=False)
    assert out["labeled"] is True
    assert out["mentioned_sections"] == ["boxed_warning", "warnings_and_precautions"]
    assert all(m["setid"] == "fake-setid" for m in out["label_mentions"])
    assert out["evidence_ids"] == ["fake-setid"]
    none = dm.find_label_mentions("testdrug", "Retinal detachment", setids=["fake-setid"], use_cache=False)
    assert none["labeled"] is False and none["label_mentions"] == []


def test_label_download_error_gives_none(monkeypatch):
    monkeypatch.setattr(dm, "http_get", lambda url, cache=None, is_json=True, **kw: {"__error__": 404, "body": ""})
    out = dm.find_label_mentions("testdrug", "x", setids=["bad"], use_cache=False)
    assert out["labeled"] is None and out["errors"]


def test_snippets_dedupe():
    text = "lactic acidosis " * 10
    assert len(dm._snippets(text, "lactic acidosis", width=20)) <= 3
    assert dm._snippets("nothing here", "lactic acidosis") == []


@pytest.mark.network
def test_live_metformin_label(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    found = dm.search_setids("metformin", pagesize=2)
    assert found["errors"] == [] and found["total"] > 0 and len(found["labels"]) == 2
    out = dm.find_label_mentions("metformin", "Lactic acidosis", max_labels=1)
    assert out["errors"] == []
    assert out["labeled"] is True
    assert "boxed_warning" in out["mentioned_sections"]


# --------------------------------------------------------------------------------------
# NAT 등록 래퍼 (dailymed_label). 네트워크 없이 배선, 설정값, 출력 스키마만 본다.
# --------------------------------------------------------------------------------------
def test_dailymed_config_type_and_defaults():
    assert dm.DailyMedLabelConfig.static_type() == "dailymed_label"   # YAML 의 _type 값
    cfg = dm.DailyMedLabelConfig()
    assert cfg.name_type == "both" and cfg.max_labels == 1 and cfg.use_cache is True
    with pytest.raises(ValueError):
        dm.DailyMedLabelConfig(max_labels=0)      # ge=1


def test_label_mention_report_model_from_fixture_result(monkeypatch):
    monkeypatch.setattr(dm, "http_get", lambda url, cache=None, is_json=True, **kw: SPL_FIXTURE)
    raw = dm.find_label_mentions("testdrug", "lactic acidosis", setids=["fake-setid"], use_cache=False)
    report = dm.LabelMentionReport.model_validate(raw)
    assert report.labeled is True
    assert report.mentioned_sections == ["boxed_warning", "warnings_and_precautions"]
    assert report.evidence_ids == ["fake-setid"]
    assert all({"section", "snippet", "setid"} <= set(m) for m in report.label_mentions)


def test_dailymed_tool_returns_report_and_str_converter(monkeypatch):
    """등록 래퍼가 find_label_mentions 를 그대로 부르고 LabelMentionReport 로 돌려주는지."""
    import asyncio

    searched = []

    def fake_get(url, cache=None, is_json=True, **kw):
        if url.endswith(".json") or "spls.json" in url:
            searched.append(url)
            return {"metadata": {"total_elements": 1},
                    "data": [{"setid": "fake-setid", "title": "TESTDRUG tablets",
                              "spl_version": 3, "published_date": "Jan 1, 2026"}]}
        return SPL_FIXTURE

    monkeypatch.setattr(dm, "http_get", fake_get)

    async def run():
        cfg = dm.DailyMedLabelConfig(name_type="generic", max_labels=2, use_cache=False)
        async with dm.dailymed_label(cfg, None) as info:
            assert list(info.input_schema.model_fields) == ["drug_name", "reaction"]
            assert info.single_output_schema is dm.LabelMentionReport
            assert info.description.startswith("Check the US DailyMed SPL label")
            out = await info.single_fn(info.input_schema(drug_name="testdrug", reaction="lactic acidosis"))
            return out, info.converters[0](out)

    report, as_str = asyncio.run(run())
    assert isinstance(report, dm.LabelMentionReport)
    assert report.drug_name == "testdrug" and report.labeled is True
    assert report.evidence_ids == ["fake-setid"] and report.errors == []
    assert "boxed_warning" in report.mentioned_sections
    # 설정의 name_type 과 max_labels 가 검색 URL 로 이어진다
    assert searched and "name_type=generic" in searched[0] and "pagesize=2" in searched[0]
    assert as_str.startswith("{")


def test_dailymed_tool_rejects_bad_name_type_at_build():
    import asyncio

    async def run():
        async with dm.dailymed_label(dm.DailyMedLabelConfig(name_type="nope"), None):
            pass

    with pytest.raises(ValueError):
        asyncio.run(run())
