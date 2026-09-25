"""DailyMed 도구 테스트. XML 파싱은 오프라인 픽스처, 라이브는 @pytest.mark.network."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "harness" / "tools"))

import pharmasignal_dailymed as dm  # noqa: E402

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
