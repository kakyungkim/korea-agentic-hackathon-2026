"""PubMed 도구 테스트. XML 파싱은 오프라인 픽스처, 라이브는 @pytest.mark.network."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "harness" / "tools"))

import pharmasignal_pubmed as pm  # noqa: E402

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
