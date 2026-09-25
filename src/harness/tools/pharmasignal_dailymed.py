"""DailyMed SPL 라벨 섹션 도구 (LLM 없이 동작).

엔드포인트(공식 문서 https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm 및
/dailymed/webservices-help/v2/spls_api.cfm, 2026-09-24 확인):
- 검색: ``GET /dailymed/services/v2/spls.json?drug_name=<이름>&name_type=<generic|brand|both>&pagesize=<=100>&page=N``
  응답 ``data[]`` 항목: setid, title, spl_version, published_date. ``metadata.total_elements``.
- 라벨 본문: ``GET /dailymed/services/v2/spls/<SETID>.xml`` → HL7 SPL XML(네임스페이스 urn:hl7-org:v3).

섹션은 ``<section><code code="LOINC">`` 로 구분한다. 실제 metformin 라벨(setid
1200ea71-8a9e-4e49-bb77-7d9fe0d84ae7)에서 확인한 코드:
  34066-1 BOXED WARNING, 34070-3 CONTRAINDICATIONS, 43685-7 WARNINGS AND PRECAUTIONS,
  34084-4 ADVERSE REACTIONS. 구형(비 PLR) 라벨은 34071-1 WARNINGS, 42232-9 PRECAUTIONS를 쓴다.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

try:
    from .pharmasignal_common import ResponseCache, http_get, is_error, now_iso, quote
except ImportError:
    from pharmasignal_common import ResponseCache, http_get, is_error, now_iso, quote

BASE = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
NS = "{urn:hl7-org:v3}"

SECTION_CODES = {
    "34066-1": "boxed_warning",
    "34070-3": "contraindications",
    "43685-7": "warnings_and_precautions",
    "34071-1": "warnings",          # 구형 라벨
    "42232-9": "precautions",       # 구형 라벨
    "34084-4": "adverse_reactions",
}


def search_setids(drug_name: str, name_type: str = "both", pagesize: int = 10,
                  use_cache: bool = True) -> dict[str, Any]:
    """약물명으로 SPL setid 목록을 조회한다. 반환: {drug_name, total, labels[], query_url, ...}."""
    if name_type not in ("generic", "brand", "both"):
        raise ValueError("name_type must be generic|brand|both")
    pagesize = max(1, min(int(pagesize), 100))
    cache = ResponseCache("dailymed", f"search|{drug_name.strip().lower()}|{name_type}", enabled=use_cache)
    url = f"{BASE}/spls.json?drug_name={quote(drug_name.strip())}&name_type={name_type}&pagesize={pagesize}"
    payload = http_get(url, cache=cache, is_json=True)
    out: dict[str, Any] = {"tool": "dailymed_search", "drug_name": drug_name, "name_type": name_type,
                           "total": None, "labels": [], "query_url": url, "evidence_ids": [],
                           "errors": [], "retrieved_at": now_iso()}
    if is_error(payload):
        out["errors"].append(f"http_error:{payload.get('__error__') if isinstance(payload, dict) else payload}")
        return out
    out["total"] = (payload.get("metadata") or {}).get("total_elements")
    for item in payload.get("data") or []:
        out["labels"].append({k: item.get(k) for k in ("setid", "title", "spl_version", "published_date")})
    out["evidence_ids"] = [lab["setid"] for lab in out["labels"] if lab.get("setid")]
    return out


def _text(el: ET.Element) -> str:
    txt = " ".join(t.strip() for t in el.itertext() if t and t.strip())
    return re.sub(r"\s+", " ", txt).strip()


def fetch_label_sections(setid: str, use_cache: bool = True) -> dict[str, Any]:
    """setid의 SPL XML을 내려받아 LOINC 코드 기준으로 주요 섹션 텍스트를 나눈다.

    반환: {setid, title, sections{boxed_warning, contraindications, warnings_and_precautions,
           warnings, precautions, adverse_reactions -> text}, section_codes_seen[], xml_url, ...}
    같은 코드 섹션이 여럿이면 텍스트를 이어 붙인다.
    """
    cache = ResponseCache("dailymed", f"label|{setid}", enabled=use_cache)
    url = f"{BASE}/spls/{quote(setid)}.xml"
    payload = http_get(url, cache=cache, is_json=False)
    out: dict[str, Any] = {"tool": "dailymed_label", "setid": setid, "title": None, "sections": {},
                           "section_codes_seen": [], "xml_url": url, "evidence_ids": [setid],
                           "errors": [], "retrieved_at": now_iso()}
    if is_error(payload) or not isinstance(payload, str):
        out["errors"].append(f"http_error:{payload.get('__error__') if isinstance(payload, dict) else 'non_text'}")
        return out
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        out["errors"].append(f"xml_parse_error:{exc}")
        return out
    title_el = root.find(f"{NS}title")
    out["title"] = _text(title_el) if title_el is not None else None
    seen: list[str] = []
    sections: dict[str, list[str]] = {}
    for sec in root.iter(f"{NS}section"):
        code_el = sec.find(f"{NS}code")
        if code_el is None:
            continue
        code = code_el.get("code")
        if code:
            seen.append(code)
        name = SECTION_CODES.get(code or "")
        if name:
            sections.setdefault(name, []).append(_text(sec))
    out["section_codes_seen"] = sorted(set(seen))
    out["sections"] = {k: "\n".join(v) for k, v in sections.items()}
    return out


def _snippets(text: str, term: str, width: int = 150, max_hits: int = 3) -> list[str]:
    hits: list[str] = []
    last_end = -1
    for m in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
        if m.start() <= last_end:  # 직전 스니펫 창 안의 중복 등장은 건너뛴다
            continue
        s, e = max(0, m.start() - width), min(len(text), m.end() + width)
        hits.append(("..." if s > 0 else "") + text[s:e] + ("..." if e < len(text) else ""))
        last_end = e
        if len(hits) >= max_hits:
            break
    return hits


def find_label_mentions(drug_name: str, reaction: str, name_type: str = "both",
                        max_labels: int = 1, setids: list[str] | None = None,
                        use_cache: bool = True) -> dict[str, Any]:
    """약물 라벨에서 반응명이 어느 섹션에 등장하는지 찾는다.

    setids를 주면 그 라벨만 본다. 없으면 검색 결과 상위 max_labels개를 본다.
    반환: {drug_name, reaction, labels_checked[{setid,title}], label_mentions[{section,snippet,setid}],
           mentioned_sections[], labeled(bool|None), evidence_ids[], errors[]}
    labeled=None 은 라벨을 하나도 못 받은 경우다(근거 없음과 구분).
    """
    out: dict[str, Any] = {"tool": "dailymed_label_mentions", "drug_name": drug_name, "reaction": reaction,
                           "labels_checked": [], "label_mentions": [], "mentioned_sections": [],
                           "labeled": None, "evidence_ids": [], "errors": [], "retrieved_at": now_iso()}
    if not setids:
        found = search_setids(drug_name, name_type=name_type, pagesize=max(1, max_labels), use_cache=use_cache)
        out["search_query_url"] = found["query_url"]
        out["search_total"] = found["total"]
        out["errors"].extend(found["errors"])
        setids = [lab["setid"] for lab in found["labels"][:max_labels]]
    term = reaction.strip()
    checked_any = False
    for setid in setids:
        label = fetch_label_sections(setid, use_cache=use_cache)
        out["errors"].extend(label["errors"])
        if label["errors"]:
            continue
        checked_any = True
        out["labels_checked"].append({"setid": setid, "title": label["title"], "xml_url": label["xml_url"],
                                      "sections_present": sorted(label["sections"])})
        out["evidence_ids"].append(setid)
        for section, text in label["sections"].items():
            for snip in _snippets(text, term):
                out["label_mentions"].append({"section": section, "snippet": snip, "setid": setid})
    if checked_any:
        out["mentioned_sections"] = sorted({m["section"] for m in out["label_mentions"]})
        out["labeled"] = bool(out["label_mentions"])
    return out


# ======================================================================================
# NAT 등록 래퍼 (dailymed_label). 위 파싱 로직과 기존 함수는 그대로 두고 감싸기만 한다.
#
# 패턴은 src/harness/register.py 의 prr_calculator 를 그대로 따른다.
#   FunctionBaseConfig(name=...)  -> YAML 의 _type 값
#   @register_function            -> NAT 레지스트리 등록 (import 시점에 발동)
#   FunctionInfo.from_fn(fn, description=..., converters=[모델 -> str])
# register.py 하단의 "도메인 도구 import" 블록이 이 모듈을 import 해야 등록이 실린다.
# ======================================================================================
import asyncio  # noqa: E402
import os  # noqa: E402

from pydantic import BaseModel  # noqa: E402
from pydantic import ConfigDict  # noqa: E402
from pydantic import Field  # noqa: E402

from nat.builder.builder import Builder  # noqa: E402
from nat.builder.function_info import FunctionInfo  # noqa: E402
from nat.cli.register_workflow import register_function  # noqa: E402
from nat.data_models.function import FunctionBaseConfig  # noqa: E402


class LabelMentionReport(BaseModel):
    """dailymed_label 의 출력 스키마. `find_label_mentions` 반환 dict 를 그대로 담는다."""

    model_config = ConfigDict(extra="allow")

    tool: str = "dailymed_label_mentions"
    drug_name: str
    reaction: str
    labels_checked: list[dict[str, Any]] = Field(
        default_factory=list, description="setid, title, xml_url and the sections present in each label read")
    label_mentions: list[dict[str, Any]] = Field(
        default_factory=list, description="section, snippet and setid for every hit of the reaction term")
    mentioned_sections: list[str] = Field(
        default_factory=list,
        description="LOINC section names holding the term: boxed_warning, contraindications, "
                    "warnings_and_precautions, warnings, precautions, adverse_reactions")
    labeled: bool | None = Field(
        default=None, description="True if the reaction is in the label, False if absent, null if no label was read")
    evidence_ids: list[str] = Field(default_factory=list, description="DailyMed SPL setids. Cite these.")
    errors: list[str] = Field(default_factory=list)
    retrieved_at: str | None = None
    search_query_url: str | None = None
    search_total: int | None = None


class DailyMedLabelConfig(FunctionBaseConfig, name="dailymed_label"):
    """DailyMed SPL 라벨 조회 도구. 설정값은 이름 매칭 방식, 볼 라벨 수, 캐시다."""

    name_type: str = Field(default="both", description="DailyMed 검색의 이름 종류. generic, brand, both 중 하나.")
    max_labels: int = Field(default=1, ge=1, le=5,
                            description="검색 결과 상위 몇 개 라벨을 내려받아 볼지. 라벨 하나가 수 MB 라 기본 1개.")
    use_cache: bool = Field(default=True, description="원응답 파일 캐시 사용 여부.")
    cache_dir: str | None = Field(default=None, description="캐시 디렉터리. 비우면 eval/results 를 쓴다.")


@register_function(config_type=DailyMedLabelConfig)
async def dailymed_label(config: DailyMedLabelConfig, _builder: Builder):
    if config.name_type not in ("generic", "brand", "both"):
        raise ValueError(f"name_type 은 generic|brand|both 중 하나여야 합니다: {config.name_type!r}")
    if config.cache_dir:
        os.environ["PHARMASIGNAL_CACHE_DIR"] = config.cache_dir

    async def _label(drug_name: str, reaction: str) -> LabelMentionReport:
        """Check the US DailyMed SPL label of a drug for an adverse event and say where it appears.

        drug_name: ingredient or brand name, for example "metformin".
        reaction: the event term to look for, for example "lactic acidosis".
        Returns labeled (true when the term is in the label, false when it is absent, null when no
        label could be read), mentioned_sections naming the label sections that hold it, verbatim
        snippets around each hit, and evidence_ids holding the DailyMed setids. Cite a setid in
        every claim about label status. A labeled event is an already known risk, not a new signal.
        """
        raw = await asyncio.to_thread(find_label_mentions, drug_name, reaction, config.name_type,
                                      config.max_labels, None, config.use_cache)
        return LabelMentionReport.model_validate(raw)

    def _report_to_str(report: LabelMentionReport) -> str:
        """도구 출력이 문자열을 요구하는 경로(콘솔, 일부 도구 래퍼)용 변환기."""
        return report.model_dump_json()

    yield FunctionInfo.from_fn(_label, description=_label.__doc__, converters=[_report_to_str])


if __name__ == "__main__":  # 수동 점검용
    import json
    import sys

    d = sys.argv[1] if len(sys.argv) > 1 else "metformin"
    r = sys.argv[2] if len(sys.argv) > 2 else "Lactic acidosis"
    print(json.dumps(find_label_mentions(d, r), indent=1, ensure_ascii=False)[:4000])
