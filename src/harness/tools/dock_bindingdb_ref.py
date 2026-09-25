"""BindingDB 참조 친화도 집합 조회 도구 (NAT 래퍼).

등록 이름은 ``bindingdb_ref`` 다. **bindingdb.org 를 직접 부르지 않는다.** FDDD 가 BindingDB
REST 를 한 번 호출해 캡처해 둔 요약을 읽는다. 그래서 조회 시각은 우리 실행 시각이 아니라 FDDD 의
캡처 시각이고, 원본 질의 URL 을 함께 돌려준다.

출처
- 조회 URL: ``https://drug.flybrain.kr/data/evidence/summary.json`` 의 ``bindingdb`` 블록
- FDDD 가 캡처한 원본 질의: BindingDB REST ``getLigandsByUniprots``
- 원문 정리: ``docs/notes/fddd-and-jev.md``
- HTTP 계층: ``pharmasignal_common`` 의 재시도와 원자적 파일 캐시를 그대로 쓴다.

설계 의도
참조 집합이 **없을 때 없다고 돌려주는 것**이 이 도구의 핵심이다. 케이스 시연에서 경로 A(사람
PARP1)에는 참조 친화도 집합이 있고 경로 B(응고인자 Xa)에는 없다. 두 경로를 가르는 지점이 이
불리언이므로 빈 값을 그럴듯하게 채우지 않는다.

종점 분리
Ki, IC50, Kd, EC50 은 측정 방식이 다른 별개의 종점이라 건수를 합치지 않는다. 반환값에 합계
필드를 두지 않고 종점별로 나눠 싣는다. FDDD 원문 경고도 그대로 함께 보낸다.

중복 고지
``case_runner.py`` 의 ``step_bindingdb`` 가 같은 블록을 읽는다. 그 파일은 다른 담당 범위라
손대지 않았고, 공통 함수로 빼지 못해 파싱이 두 곳에 있다.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from pydantic import BaseModel, Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

try:
    from .bionemo_client import canonical_json, sha256_text
    from .pharmasignal_common import ResponseCache, http_get, is_error, now_iso
except ImportError:  # 스크립트에서 sys.path 로 직접 임포트할 때
    from bionemo_client import canonical_json, sha256_text  # type: ignore[no-redef]
    from pharmasignal_common import ResponseCache, http_get, is_error, now_iso  # type: ignore[no-redef]

TOOL_NAME = "bindingdb_ref"
FDDD_EVIDENCE_URL = "https://drug.flybrain.kr/data/evidence/summary.json"
CACHE_SOURCE = "fddd"
CACHE_KEY = "evidence-summary"

# 합치지 않고 나눠 싣는 네 종점. 순서도 FDDD 원문 순서를 따른다.
ENDPOINTS = ("Ki", "IC50", "Kd", "EC50")

# FDDD 원문 경고. 요약하지 않고 그대로 옮긴다.
ENDPOINT_WARNING = (
    "Ki, Kd, IC50 and EC50 are distinct endpoints and are NOT pooled into one affinity score.")

SOURCE_NOTE = (
    "bindingdb.org 를 직접 부르지 않는다. FDDD 가 BindingDB REST 를 한 번 호출해 캡처해 둔 "
    "요약(evidence/summary.json)을 읽는다. 조회 시각은 captured_at 이고 우리 실행 시각이 아니다.")

# 참조 집합이 붙은 타깃의 별명. FDDD 문서의 타깃 ID 와 PDB ID 를 포함한다.
# 이 목록에 없는 타깃은 참조 집합이 없는 것으로 돌려준다.
UNIPROT_ALIASES: dict[str, tuple[str, ...]] = {
    "P09874": ("p09874", "parp1", "parp", "humanparp1", "parp1catalyticdomain",
               "parp14r6echaina", "4r6e"),
}


# --------------------------------------------------------------------------------------
# 반환 스키마
# --------------------------------------------------------------------------------------
class EndpointCounts(BaseModel):
    """종점별 레코드 수. 합계 필드를 두지 않는다. 네 값을 더해 쓰지 않는다."""

    Ki: int | None = Field(default=None, description="Ki 레코드 수")
    IC50: int | None = Field(default=None, description="IC50 레코드 수")
    Kd: int | None = Field(default=None, description="Kd 레코드 수")
    EC50: int | None = Field(default=None, description="EC50 레코드 수")


class BindingDbRefResult(BaseModel):
    """BindingDB 참조 집합 조회 결과. 없으면 없다고 적는다."""

    tool: str = Field(default=TOOL_NAME)
    url: str = Field(default=FDDD_EVIDENCE_URL, description="조회한 FDDD 요약 문서 URL")
    source: str = Field(
        default="FDDD evidence summary (captured BindingDB REST response)",
        description="어디서 읽었는지. BindingDB 직접 호출이 아니다.")
    direct_bindingdb_call: bool = Field(
        default=False, description="bindingdb.org 를 직접 불렀는지. 항상 False 다.")
    reference_set_present: bool = Field(
        default=False,
        description="이 타깃에 붙은 참조 친화도 집합이 있는지. 없으면 False 이고 건수는 None 이다.")
    queried_target: str = Field(default="", description="호출자가 넘긴 타깃 식별자 원문")
    target: str | None = Field(default=None, description="참조 집합의 타깃 표기 원문")
    uniprot: str | None = Field(default=None, description="참조 집합의 UniProt 식별자")
    record_count: int | None = Field(
        default=None, description="참조 집합의 레코드 수. FDDD 가 적은 값이고 종점 합이 아니다.")
    compound_count: int | None = Field(default=None, description="참조 집합의 화합물 수")
    endpoint_counts: EndpointCounts = Field(
        default_factory=EndpointCounts,
        description="Ki, IC50, Kd, EC50 별 건수. 합치지 않는다.")
    captured_at: str | None = Field(default=None, description="FDDD 가 BindingDB 를 캡처한 시각")
    source_query_url: str | None = Field(
        default=None, description="FDDD 가 호출한 BindingDB REST 질의 URL 원문")
    raw_path: str | None = Field(default=None, description="FDDD 가 보관한 원응답 경로")
    filter_note: str | None = Field(
        default=None, description="참조 집합의 필터 조건 원문. 완전한 DB 도 음성 대조군도 아니다.")
    endpoint_warning: str = Field(
        default=ENDPOINT_WARNING, description="종점 혼합 금지 경고. FDDD 원문 그대로다.")
    absent_note: str | None = Field(
        default=None, description="참조 집합이 없을 때 그 사실을 적은 문장")
    evidence_id: str | None = Field(default=None, description="근거 ID. 형식 bindingdb:<UniProt>")
    evidence_ids: list[str] = Field(default_factory=list, description="근거 ID 목록")
    available_reference_sets: list[str] = Field(
        default_factory=list, description="이 문서에 실제로 실린 참조 집합 목록")
    source_note: str = Field(default=SOURCE_NOTE)
    from_cache: bool = Field(default=False, description="응답을 캐시에서 읽었는지")
    retrieved_at: str = Field(default_factory=now_iso)
    errors: list[str] = Field(default_factory=list, description="실패 사유. 빈 값을 채우지 않는다.")


# --------------------------------------------------------------------------------------
# 조회와 파싱. 파싱은 순수 함수라 오프라인에서 그대로 검증한다.
# --------------------------------------------------------------------------------------
def evidence_id(uniprot: str) -> str:
    """근거 ID. 형식 ``bindingdb:<UniProt>``."""
    key = str(uniprot or "").strip().upper()
    if not key:
        raise ValueError("UniProt 식별자가 비었습니다.")
    return f"bindingdb:{key}"


def _norm(text: Any) -> str:
    """영숫자만 남긴 소문자. 타깃 이름 비교에만 쓴다."""
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def parse_uniprot(source_url: str) -> str:
    """FDDD 가 적어 둔 BindingDB 질의 URL 에서 UniProt 식별자를 읽는다."""
    match = re.search(r"uniprot=([A-Za-z0-9]+)", str(source_url or ""))
    return match.group(1).upper() if match else ""


def target_matches(block: dict[str, Any], target: str, uniprot: str = "") -> bool:
    """요청한 타깃이 이 참조 집합의 타깃인지 본다. 애매하면 False 로 둔다."""
    key = _norm(target)
    if not key:
        return False
    if uniprot and key == _norm(uniprot):
        return True
    if uniprot and key in UNIPROT_ALIASES.get(uniprot.upper(), ()):
        return True
    block_target = _norm(block.get("target"))
    return bool(block_target) and (key in block_target)


def fetch_evidence_summary(*, use_cache: bool = True,
                           getter: Callable[..., Any] | None = None) -> dict[str, Any]:
    """FDDD evidence/summary.json 을 한 번 받는다."""
    cache = ResponseCache(CACHE_SOURCE, CACHE_KEY, enabled=use_cache)
    get = getter or http_get
    payload = get(FDDD_EVIDENCE_URL, cache=cache, is_json=True)
    if is_error(payload) or not isinstance(payload, dict):
        code = payload.get("__error__") if isinstance(payload, dict) else "non_json"
        return {"ok": False, "doc": None, "url": FDDD_EVIDENCE_URL, "from_cache": False,
                "errors": [f"fddd_evidence_fetch_failed:{code}"]}
    return {"ok": True, "doc": payload, "url": FDDD_EVIDENCE_URL,
            "doc_sha256": sha256_text(canonical_json(payload)),
            "captured_at": payload.get("capturedAt"),
            "from_cache": cache.hits > 0, "errors": []}


def parse_bindingdb_block(doc: dict[str, Any], target: str, *, from_cache: bool = False,
                          url: str = FDDD_EVIDENCE_URL) -> BindingDbRefResult:
    """요약 문서의 ``bindingdb`` 블록을 읽는다. 요청한 타깃이 아니면 없다고 돌려준다.

    종점 건수는 요청한 타깃에 참조 집합이 있을 때만 채운다. 없을 때 0 으로 채우지 않는다.
    0 건과 "집합이 없다"는 다른 사실이다.
    """
    block = (doc or {}).get("bindingdb") or {}
    result = BindingDbRefResult(
        url=url, queried_target=str(target), captured_at=(doc or {}).get("capturedAt"),
        from_cache=from_cache)

    if not isinstance(block, dict) or not block:
        result.errors.append("bindingdb_block_missing")
        return result

    uniprot = parse_uniprot(block.get("sourceUrl"))
    block_target = block.get("target")
    result.available_reference_sets = [str(block_target)] if block_target else []
    result.source_query_url = block.get("sourceUrl")
    result.raw_path = block.get("rawPath")
    result.filter_note = block.get("filter")
    result.endpoint_warning = block.get("warning") or ENDPOINT_WARNING
    result.target = block_target
    result.uniprot = uniprot or None
    if not uniprot:
        result.errors.append("uniprot_not_found_in_source_url")

    if not target_matches(block, target, uniprot):
        result.reference_set_present = False
        result.absent_note = (
            f"이 문서에 실린 참조 친화도 집합은 {block_target} 하나뿐이고, 요청한 "
            f"{target} 에 대응하는 집합은 없다. 건수를 0 으로 읽지 말고 집합이 없다고 읽는다.")
        if uniprot:
            # 근거 ID 는 "어느 집합이 실려 있는지"를 가리키는 캡처 요약을 지목한다.
            result.evidence_id = evidence_id(uniprot)
            result.evidence_ids = [result.evidence_id]
        return result

    counts = block.get("counts") or {}
    result.reference_set_present = True
    result.record_count = block.get("recordCount")
    result.compound_count = block.get("compoundCount")
    result.endpoint_counts = EndpointCounts(**{
        name: counts.get(name) for name in ENDPOINTS})
    if uniprot:
        result.evidence_id = evidence_id(uniprot)
        result.evidence_ids = [result.evidence_id]
    return result


def lookup(target: str, *, use_cache: bool = True,
           getter: Callable[..., Any] | None = None) -> BindingDbRefResult:
    """FDDD 요약을 받아 참조 집합 존재 여부와 종점별 건수를 돌려준다."""
    fetched = fetch_evidence_summary(use_cache=use_cache, getter=getter)
    if not fetched["ok"]:
        return BindingDbRefResult(
            queried_target=str(target), url=fetched["url"], errors=list(fetched["errors"]))
    return parse_bindingdb_block(
        fetched["doc"], target, from_cache=bool(fetched.get("from_cache")), url=fetched["url"])


# --------------------------------------------------------------------------------------
# NAT 등록
# --------------------------------------------------------------------------------------
class BindingDbRefConfig(FunctionBaseConfig, name=TOOL_NAME):
    """BindingDB 참조 집합 조회 도구 설정."""

    url: str = Field(default=FDDD_EVIDENCE_URL, description="FDDD 근거 요약 문서 URL")
    use_cache: bool = Field(
        default=True, description="원응답을 eval/results 에 캐시해 같은 문서를 다시 받지 않는다.")


@register_function(config_type=BindingDbRefConfig)
async def bindingdb_ref(config: BindingDbRefConfig, _builder: Builder):

    async def _lookup(target: str) -> BindingDbRefResult:
        """Check whether a reference affinity set exists for a target, and how large it is.

        This tool does NOT call bindingdb.org. It reads the BindingDB summary that FDDD captured
        once and serves at drug.flybrain.kr/data/evidence/summary.json, so the timestamp is
        FDDD's capture time (captured_at), not the time of this call. The original BindingDB REST
        query URL is returned as source_query_url.

        target: a target identifier, e.g. "PARP1", "P09874", "4R6E" or "factor Xa".

        Returns reference_set_present (a boolean: false when this target has no reference set,
        which is a real answer and not a failure), the target and its UniProt id, the record and
        compound counts, per-endpoint counts for Ki, IC50, Kd and EC50, the capture time, the
        original query URL, and an evidence_id of the form bindingdb:<uniprot>.

        INTERPRETATION LIMITS:
        - "Ki, Kd, IC50 and EC50 are distinct endpoints and are NOT pooled into one affinity
          score." Never add the four counts together and never merge the endpoints into a single
          affinity value without calibration and an explicit uncertainty statement. Report them
          separately.
        - The set is filtered (API affinity cutoff), so it is neither the complete database nor
          an unbiased negative set. Absence of a record is not evidence of no binding.
        - When reference_set_present is false, say that no reference affinity set is attached to
          that target. Do not read it as a count of zero, and do not borrow another target's
          numbers.
        """
        return lookup(target, use_cache=config.use_cache)

    def _result_to_str(result: BindingDbRefResult) -> str:
        """pydantic 반환은 콘솔 프런트엔드에서 깨지므로 문자열 변환기를 함께 등록한다."""
        return result.model_dump_json()

    yield FunctionInfo.from_fn(_lookup, description=_lookup.__doc__, converters=[_result_to_str])
