"""PubMed 도구 테스트. XML 파싱은 오프라인 픽스처, 라이브는 @pytest.mark.network."""
import time

import pytest

# 도구 모듈은 반드시 패키지 경로로 import 한다. sys.path 로 최상위 모듈로도 불러오면
# @register_function 이 두 번 돌아 같은 짧은 이름(openfda_faers 등)이 둘이 되고,
# NAT 가 YAML 의 _type 을 해석하지 못한다 (nat/cli/type_registry.py _do_compute_annotation).
from harness.tools import pharmasignal_pubmed as pm

EFETCH_FIXTURE = """<?xml version="1.0"?>
<PubmedArticleSet>
 <PubmedArticle><MedlineCitation Status="MEDLINE" Owner="NLM"><PMID Version="1">111</PMID>
  <Article PubModel="Print"><Journal><Title>Drug safety</Title>
   <JournalIssue><PubDate><Year>2019</Year></PubDate></JournalIssue></Journal>
   <ArticleTitle>The Association between <i>Metformin</i> and Lactic Acidosis.</ArticleTitle>
   <Abstract><AbstractText Label="BACKGROUND">Part one.</AbstractText><AbstractText>Part two.</AbstractText></Abstract>
   <PublicationTypeList><PublicationType>Review</PublicationType></PublicationTypeList>
  </Article></MedlineCitation></PubmedArticle>
 <PubmedArticle><MedlineCitation><PMID Version="1">222</PMID>
  <Article><Journal><Title>Some journal</Title>
   <JournalIssue><PubDate><MedlineDate>1998 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal>
   <ArticleTitle>No abstract paper</ArticleTitle>
  </Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


def test_parse_articles_fixture():
    parsed = pm._parse_articles(EFETCH_FIXTURE)
    assert set(parsed) == {"111", "222"}
    a = parsed["111"]
    assert a["title"] == "The Association between Metformin and Lactic Acidosis."
    assert a["journal"] == "Drug safety" and a["year"] == 2019
    assert a["abstract_300"] == "Part one. Part two." and a["has_abstract"]
    assert a["publication_types"] == ["Review"]
    b = parsed["222"]
    assert b["year"] == 1998 and b["has_abstract"] is False


def test_build_term():
    assert pm.build_term(" metformin ", "Lactic acidosis") == 'metformin AND "Lactic acidosis"'


def test_search_pubmed_offline(monkeypatch):
    calls = []

    def fake_get(url, cache=None, is_json=True, **kw):
        calls.append(url)
        if "esearch" in url:
            return {"esearchresult": {"count": "2", "idlist": ["111", "222"]}}
        return EFETCH_FIXTURE

    monkeypatch.setattr(pm, "http_get", fake_get)
    out = pm.search_pubmed("metformin", "Lactic acidosis", retmax=5, use_cache=False)
    assert out["total_count"] == 2 and out["pmids"] == ["111", "222"]
    assert out["evidence_ids"] == ["111", "222"]
    assert [a["pmid"] for a in out["articles"]] == ["111", "222"]
    assert len(calls) == 2 and "id=111,222" in calls[1]
    assert out["errors"] == []


def test_search_pubmed_no_hits(monkeypatch):
    monkeypatch.setattr(pm, "http_get", lambda url, cache=None, is_json=True, **kw: {"esearchresult": {"count": "0", "idlist": []}})
    out = pm.search_pubmed("zzzz", "yyyy", use_cache=False)
    assert out["total_count"] == 0 and out["articles"] == [] and out["query_urls"]["efetch"] is None


@pytest.mark.network
def test_live_metformin_lactic_acidosis(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    t0 = time.monotonic()
    out = pm.search_pubmed("metformin", "Lactic acidosis", retmax=5)
    assert out["errors"] == []
    assert out["total_count"] > 100 and len(out["pmids"]) == 5
    assert all(a["title"] for a in out["articles"])
    # 두 호출 사이 최소 간격(초당 3회 제한)
    assert time.monotonic() - t0 >= pm.MIN_INTERVAL


# --------------------------------------------------------------------------------------
# NAT 등록 래퍼 (pubmed_search). 네트워크 없이 배선, 설정값, 출력 스키마만 본다.
# --------------------------------------------------------------------------------------
def test_pubmed_config_type_and_defaults():
    assert pm.PubmedSearchConfig.static_type() == "pubmed_search"   # YAML 의 _type 값
    cfg = pm.PubmedSearchConfig()
    assert cfg.retmax == 5 and cfg.use_cache is True
    assert cfg.min_interval_seconds == pytest.approx(pm.MIN_INTERVAL)
    with pytest.raises(ValueError):
        pm.PubmedSearchConfig(min_interval_seconds=0.0)   # 초당 10회 상한 아래로는 못 내린다
    with pytest.raises(ValueError):
        pm.PubmedSearchConfig(retmax=0)


def test_pubmed_search_report_model_from_offline_result(monkeypatch):
    def fake_get(url, cache=None, is_json=True, **kw):
        return {"esearchresult": {"count": "2", "idlist": ["111", "222"]}} if "esearch" in url else EFETCH_FIXTURE

    monkeypatch.setattr(pm, "http_get", fake_get)
    raw = pm.search_pubmed("metformin", "Lactic acidosis", retmax=5, use_cache=False)
    report = pm.PubmedSearchReport.model_validate(raw)
    assert report.total_count == 2 and report.evidence_ids == ["111", "222"]
    assert report.term == 'metformin AND "Lactic acidosis"'
    assert report.articles[0]["journal"] == "Drug safety"
    assert report.query_urls["efetch"] is not None


def test_pubmed_tool_returns_report_and_str_converter(monkeypatch):
    """등록 래퍼가 search_pubmed 를 그대로 부르고 PubmedSearchReport 로 돌려주는지."""
    import asyncio

    calls = []

    def fake_get(url, cache=None, is_json=True, **kw):
        calls.append(url)
        return {"esearchresult": {"count": "2", "idlist": ["111", "222"]}} if "esearch" in url else EFETCH_FIXTURE

    monkeypatch.setattr(pm, "http_get", fake_get)
    monkeypatch.setattr(pm, "MIN_INTERVAL", pm.MIN_INTERVAL)   # 원복은 monkeypatch 가 맡는다

    async def run():
        cfg = pm.PubmedSearchConfig(retmax=2, use_cache=False)
        async with pm.pubmed_search(cfg, None) as info:
            assert list(info.input_schema.model_fields) == ["drug", "reaction"]
            assert info.single_output_schema is pm.PubmedSearchReport
            assert info.description.startswith("Search PubMed")
            out = await info.single_fn(info.input_schema(drug="metformin", reaction="Lactic acidosis"))
            return out, info.converters[0](out)

    report, as_str = asyncio.run(run())
    assert isinstance(report, pm.PubmedSearchReport)
    assert report.pmids == ["111", "222"] and report.errors == []
    assert "retmax=2" in calls[0]
    assert as_str.startswith("{") and '"tool":"pubmed_search"' in as_str


def test_pubmed_tool_config_slows_down_calls_but_not_below_floor(monkeypatch):
    import asyncio

    monkeypatch.setattr(pm, "MIN_INTERVAL", pm.MIN_INTERVAL)

    async def run(seconds):
        async with pm.pubmed_search(pm.PubmedSearchConfig(min_interval_seconds=seconds), None):
            return pm.MIN_INTERVAL

    assert asyncio.run(run(1.5)) == pytest.approx(1.5)
    assert asyncio.run(run(pm.MIN_INTERVAL_FLOOR)) == pytest.approx(pm.MIN_INTERVAL_FLOOR)
