"""PubMed E-utilities 문헌 검색 도구 (LLM 없이 동작).

엔드포인트: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{esearch,efetch}.fcgi
- esearch: ``db=pubmed&retmode=json&retmax=N&sort=relevance&term=<약물> AND "<반응>"``
  → ``esearchresult.idlist``, ``esearchresult.count``.
- efetch: ``db=pubmed&retmode=xml&rettype=abstract&id=<PMID,...>`` → PubmedArticle XML에서
  ArticleTitle, Journal/Title, PubDate/Year(또는 MedlineDate), AbstractText를 읽는다.
- 제한: 키 없이 초당 3회(NCBI 사용 지침). 이 모듈은 호출 사이 최소 0.34초를 보장한다.
  ``NCBI_API_KEY``가 있으면 ``api_key``를 붙이고(초당 10회), ``NCBI_EMAIL``·``tool`` 파라미터를 붙인다.
  (지침 원문은 이번 세션에서 NCBI 페이지가 reCAPTCHA로 막혀 재확인하지 못했다. [unverified])

참고 구현: autobiox/BioProject02/agents/critic/scripts/verify_citations.py 의
fetch_abstract_pubmed(esearch → efetch XML → <AbstractText> 정규식) 로직을 따랐다.
"""

from __future__ import annotations

import html
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any

try:
    from .pharmasignal_common import ResponseCache, http_get, is_error, now_iso, quote
except ImportError:
    from pharmasignal_common import ResponseCache, http_get, is_error, now_iso, quote

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MIN_INTERVAL = 0.34  # 초당 3회 제한 준수
_LAST_CALL: list[float] = []


def _auth_params() -> str:
    parts = ["tool=pharmasignal"]
    email = os.environ.get("NCBI_EMAIL")
    key = os.environ.get("NCBI_API_KEY")
    if email:
        parts.append(f"email={quote(email)}")
    if key:
        parts.append(f"api_key={quote(key)}")
    return "&".join(parts)


def build_term(drug: str, reaction: str) -> str:
    return f'{drug.strip()} AND "{reaction.strip()}"'


def _clean(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _parse_articles(xml_text: str) -> dict[str, dict[str, Any]]:
    """efetch XML → {pmid: {title, journal, year, abstract_300}}."""
    out: dict[str, dict[str, Any]] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for art in root.iter("PubmedArticle"):
        pmid_el = art.find("./MedlineCitation/PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        pmid = pmid_el.text.strip()
        article = art.find("./MedlineCitation/Article")
        if article is None:
            continue
        title_el = article.find("ArticleTitle")
        title = _clean("".join(title_el.itertext())) if title_el is not None else ""
        journal_el = article.find("Journal/Title")
        journal = _clean(journal_el.text if journal_el is not None else "")
        year = None
        pd = article.find("Journal/JournalIssue/PubDate")
        if pd is not None:
            y = pd.find("Year")
            if y is not None and y.text and y.text.strip().isdigit():
                year = int(y.text.strip())
            else:
                md = pd.find("MedlineDate")
                m = re.search(r"(19|20)\d{2}", md.text or "") if md is not None else None
                year = int(m.group(0)) if m else None
        abstract = " ".join(_clean("".join(a.itertext())) for a in article.findall("Abstract/AbstractText"))
        pubtypes = [_clean(p.text) for p in article.findall("PublicationTypeList/PublicationType")]
        out[pmid] = {"pmid": pmid, "title": title, "journal": journal, "year": year,
                     "abstract_300": abstract[:300], "has_abstract": bool(abstract),
                     "publication_types": pubtypes,
                     "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"}
    return out


def search_pubmed(drug: str, reaction: str, retmax: int = 10, use_cache: bool = True) -> dict[str, Any]:
    """"<약물> AND "<반응>"" 검색 상위 retmax건의 PMID, 제목, 저널, 연도, 초록 앞 300자.

    반환: {term, total_count, pmids[], articles[], query_urls{esearch, efetch}, evidence_ids(=PMID),
           errors[], retrieved_at}
    """
    retmax = max(1, min(int(retmax), 100))
    term = build_term(drug, reaction)
    cache = ResponseCache("pubmed", f"{term}|{retmax}", enabled=use_cache)
    esearch_url = (f"{EUTILS}/esearch.fcgi?db=pubmed&retmode=json&retmax={retmax}&sort=relevance"
                   f"&term={quote(term)}&{_auth_params()}")
    out: dict[str, Any] = {"tool": "pubmed_search", "drug": drug, "reaction": reaction, "term": term,
                           "total_count": None, "pmids": [], "articles": [],
                           "query_urls": {"esearch": esearch_url, "efetch": None},
                           "evidence_ids": [], "errors": [], "retrieved_at": now_iso()}
    payload = http_get(esearch_url, cache=cache, is_json=True, min_interval=MIN_INTERVAL, _last_call=_LAST_CALL)
    if is_error(payload):
        out["errors"].append(f"esearch_error:{payload.get('__error__') if isinstance(payload, dict) else payload}")
        return out
    res = payload.get("esearchresult") or {}
    try:
        out["total_count"] = int(res.get("count", 0))
    except (TypeError, ValueError):
        out["total_count"] = None
    if res.get("errorlist"):
        out["errors"].append(f"esearch_errorlist:{res['errorlist']}")
    ids = [str(i) for i in res.get("idlist") or []]
    out["pmids"] = ids
    out["evidence_ids"] = list(ids)
    if not ids:
        return out
    efetch_url = f"{EUTILS}/efetch.fcgi?db=pubmed&retmode=xml&rettype=abstract&id={','.join(ids)}&{_auth_params()}"
    out["query_urls"]["efetch"] = efetch_url
    xml_text = http_get(efetch_url, cache=cache, is_json=False, min_interval=MIN_INTERVAL, _last_call=_LAST_CALL)
    if is_error(xml_text) or not isinstance(xml_text, str):
        out["errors"].append(f"efetch_error:{xml_text.get('__error__') if isinstance(xml_text, dict) else 'non_text'}")
        return out
    parsed = _parse_articles(xml_text)
    out["articles"] = [parsed[p] for p in ids if p in parsed]
    missing = [p for p in ids if p not in parsed]
    if missing:
        out["errors"].append(f"efetch_missing_pmids:{missing}")
    return out


if __name__ == "__main__":  # 수동 점검용
    import json
    import sys

    d = sys.argv[1] if len(sys.argv) > 1 else "metformin"
    r = sys.argv[2] if len(sys.argv) > 2 else "Lactic acidosis"
    print(json.dumps(search_pubmed(d, r, retmax=5), indent=1, ensure_ascii=False))
