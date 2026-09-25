"""FDDD 가 미리 계산해 정적으로 서빙하는 AutoDock Vina 실측 조회 도구 (NAT 래퍼).

등록 이름은 ``vina_reference`` 다. 이 도구는 도킹을 실행하지 않는다. FDDD 가 이미 돌려 놓고
파일로 공개한 결과를 읽어 점수와 프로토콜과 무결성 해시와 근거 ID 를 함께 돌려준다.

출처
- 조회 URL: ``https://drug.flybrain.kr/data/docking/multi-target.json``
- 원문 정리: ``docs/notes/fddd-and-jev.md`` (도킹 조합 8건과 금지 해석 8항목)
- HTTP 계층: ``pharmasignal_common`` 의 재시도와 원자적 파일 캐시를 그대로 쓴다.

설계 의도
``notes`` 배열 8항목은 FDDD 가 스스로 금지한 해석이다. 도구가 점수만 내보내면 모델이 그 8항목을
모른 채 해석하게 되므로, 점수와 해석 한계를 한 반환값에 같이 담는다. ``role`` 도 요약하거나
번역하지 않고 원문 그대로 싣는다. 크리틱이 이 문장을 판단 근거로 쓴다.

해석 한계 (원문은 ``notes`` 와 ``role`` 에 그대로 있다)
- 서로 다른 타깃의 Raw Vina 점수는 교차 타깃으로 보정된 값이 아니다. 타깃 순위나 선택성을
  말하지 않는다.
- 점수를 Kd, Ki, IC50, EC50 으로 환산하지 않는다.
- seed 하나로 돌린 결과이고 불확실성과 수렴 분석이 없다. 재현성을 주장하지 않는다.
- 포즈 RMSD 는 같은 실행 안의 포즈끼리 잰 값이고 결정 구조와의 편차가 아니다.
- 실행된 입력은 SMILES 가 아니라 준비된 PDBQT 파일이다.

중복 고지
``case_runner.py`` 의 ``step_vina`` 가 같은 문서에서 같은 필드를 읽는다. 그 파일은 다른 담당
범위라 손대지 않았고, 공통 함수로 빼지 못해 파싱이 두 곳에 있다.
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

TOOL_NAME = "vina_reference"
FDDD_DOCKING_URL = "https://drug.flybrain.kr/data/docking/multi-target.json"
CACHE_SOURCE = "fddd"
CACHE_KEY = "multi-target"

# 도구가 실행 주체가 아님을 반환값에 남긴다. 모델이 "우리가 도킹했다"로 읽지 않게 한다.
EXECUTION_NOTE = (
    "이 도구는 도킹을 실행하지 않는다. FDDD 가 AutoDock Vina 1.2.3 으로 미리 계산해 정적 "
    "파일로 서빙하는 결과를 조회한 것이다.")

INTERPRETATION_WARNING = (
    "서로 다른 타깃의 Vina 점수는 교차 타깃 보정값이 아니므로 타깃 순위나 선택성으로 읽지 "
    "않는다. 점수를 Kd, Ki, IC50, EC50 으로 환산하지 않는다. seed 하나로 돌린 단일 실행이고 "
    "수렴 분석이 없으므로 재현성을 주장하지 않는다. 자세한 원문은 fddd_notes 8항목에 있다.")


# --------------------------------------------------------------------------------------
# 반환 스키마
# --------------------------------------------------------------------------------------
class VinaProtocol(BaseModel):
    """실행 프로토콜. FDDD 가 공개한 값만 담고 비어 있으면 None 이다."""

    id: str | None = None
    tool: str | None = Field(default=None, description="도킹 도구 이름. AutoDock Vina 다.")
    version: str | None = Field(default=None, description="도구 버전. 1.2.3 이다.")
    runtime: str | None = Field(default=None, description="실행 런타임(WASM 여부 포함)")
    scoring_function: str | None = Field(default=None, description="채점함수 이름")
    units: str | None = Field(default=None, description="점수 단위. kcal/mol 이다.")
    seed: int | None = Field(default=None, description="난수 seed. 단일 seed 실행이다.")
    exhaustiveness: int | None = Field(default=None, description="탐색 강도")
    cpu: int | None = Field(default=None, description="사용 CPU 수")
    num_modes: int | None = Field(default=None, description="생성한 포즈 수 상한")
    box_center: list[float] | None = Field(default=None, description="도킹 박스 중심 좌표")
    box_size: list[float] | None = Field(default=None, description="도킹 박스 크기")
    box_source_url: str | None = Field(default=None, description="박스 좌표의 출처 URL")
    parameter_note: str | None = Field(default=None, description="파라미터에 붙은 FDDD 원문 메모")


class VinaPose(BaseModel):
    """포즈 하나. RMSD 는 같은 실행의 1순위 포즈 기준이고 결정 구조 기준이 아니다."""

    rank: int = Field(description="포즈 순위. 1 이 1순위다.")
    score: float | None = Field(default=None, description="포즈 점수 (kcal/mol)")
    rmsd_lower_bound_from_best: float | None = Field(
        default=None, description="같은 실행의 1순위 포즈 대비 RMSD 하한. 결정 구조 기준이 아니다.")
    rmsd_upper_bound_from_best: float | None = Field(
        default=None, description="같은 실행의 1순위 포즈 대비 RMSD 상한. 결정 구조 기준이 아니다.")


class VinaIntegrity(BaseModel):
    """무결성 해시. 점수가 적힌 로그 해시가 근거 ID 의 재료다."""

    receptor_pdbqt: str | None = Field(default=None, description="준비된 수용체 PDBQT 의 SHA256")
    ligand_input_pdbqt: str | None = Field(
        default=None, description="실행된 리간드 입력 PDBQT 의 SHA256. SMILES 가 아니다.")
    poses: str | None = Field(default=None, description="포즈 파일의 SHA256")
    log: str | None = Field(default=None, description="Vina 로그의 SHA256. 근거 ID 의 재료다.")
    manifest_document: str | None = Field(default=None, description="조회한 문서 전체의 SHA256")
    wasm_runtime: str | None = Field(default=None, description="WASM 런타임 바이너리의 SHA256")


class VinaReferenceResult(BaseModel):
    """FDDD Vina 실측 한 건. 수치를 새로 만들지 않고 문서에 있는 값만 옮긴다."""

    tool: str = Field(default=TOOL_NAME)
    url: str = Field(default=FDDD_DOCKING_URL, description="조회한 FDDD 문서 URL")
    found: bool = Field(default=False, description="요청한 타깃과 화합물 조합이 문서에 있는지")
    computed: bool = Field(default=False, description="그 조합이 실제로 계산된 것으로 표시돼 있는지")
    queried_target: str = Field(default="", description="호출자가 넘긴 타깃 식별자 원문")
    queried_compound: str = Field(default="", description="호출자가 넘긴 화합물 이름 원문")
    combination_id: str | None = Field(default=None, description="FDDD 조합 ID")
    target_id: str | None = Field(default=None, description="FDDD 타깃 ID")
    target_name: str | None = Field(default=None, description="타깃 이름")
    pdb_id: str | None = Field(default=None, description="수용체 PDB ID")
    organism: str | None = Field(
        default=None, description="수용체의 종. 사람이 아닌 구조가 섞여 있어 반드시 함께 읽는다.")
    compound_id: str | None = Field(default=None, description="FDDD 화합물 ID")
    compound_name: str | None = Field(default=None, description="화합물 이름")
    score_kcal_mol: float | None = Field(default=None, description="Vina 점수")
    units: str | None = Field(default=None, description="점수 단위. kcal/mol 이다.")
    role: str | None = Field(
        default=None,
        description="FDDD 가 이 조합에 적어 둔 역할. 원문 그대로이고 요약도 번역도 하지 않는다.")
    protocol: VinaProtocol = Field(default_factory=VinaProtocol, description="실행 프로토콜")
    poses: list[VinaPose] = Field(default_factory=list, description="랭크순 포즈 목록")
    integrity: VinaIntegrity = Field(default_factory=VinaIntegrity, description="SHA256 묶음")
    smiles: str | None = Field(default=None, description="화합물 식별용 SMILES. 실행 입력이 아니다.")
    smiles_kind: str | None = Field(default=None, description="SMILES 표기 종류")
    executed_input: str | None = Field(
        default=None, description="실제로 실행된 입력 파일 경로. 준비된 PDBQT 다.")
    receptor_pdbqt: str | None = Field(default=None, description="실행에 쓴 수용체 PDBQT 경로")
    computed_at: str | None = Field(default=None, description="그 조합이 계산된 시각")
    generated_at: str | None = Field(default=None, description="문서가 생성된 시각")
    evidence_id: str | None = Field(
        default=None, description="근거 ID. 형식 dock:vina:<로그 SHA256 앞 8자>")
    evidence_ids: list[str] = Field(default_factory=list, description="근거 ID 목록")
    fddd_notes: list[str] = Field(
        default_factory=list,
        description="FDDD 가 금지한 해석 8항목. 원문 그대로다. 점수와 함께 읽는다.")
    available_combinations: list[str] = Field(
        default_factory=list, description="조합을 못 찾았을 때 문서에 있는 조합 ID 목록")
    execution_note: str = Field(default=EXECUTION_NOTE)
    interpretation_warning: str = Field(default=INTERPRETATION_WARNING)
    from_cache: bool = Field(default=False, description="응답을 캐시에서 읽었는지")
    retrieved_at: str = Field(default_factory=now_iso)
    errors: list[str] = Field(default_factory=list, description="실패 사유. 자리표시자를 채우지 않는다.")


# --------------------------------------------------------------------------------------
# 조회와 파싱. 파싱은 순수 함수라 오프라인에서 그대로 검증한다.
# --------------------------------------------------------------------------------------
def evidence_id(log_sha256: str) -> str:
    """근거 ID. 형식 ``dock:vina:<로그 SHA256 앞 8자>``.

    점수가 적힌 파일을 가리켜야 대조가 되므로 수용체나 포즈 해시가 아니라 로그 해시를 쓴다.
    """
    if not isinstance(log_sha256, str) or len(log_sha256) < 8:
        raise ValueError(f"SHA256 16진 문자열이 아닙니다: {log_sha256!r}")
    return f"dock:vina:{log_sha256[:8]}"


def _norm(text: Any) -> str:
    """영숫자만 남긴 소문자. 타깃과 화합물 이름 비교에만 쓴다."""
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def fetch_docking_manifest(*, use_cache: bool = True,
                           getter: Callable[..., Any] | None = None) -> dict[str, Any]:
    """FDDD multi-target.json 을 한 번 받는다. 문서 자체의 SHA256 을 함께 남긴다."""
    cache = ResponseCache(CACHE_SOURCE, CACHE_KEY, enabled=use_cache)
    get = getter or http_get
    payload = get(FDDD_DOCKING_URL, cache=cache, is_json=True)
    if is_error(payload) or not isinstance(payload, dict):
        code = payload.get("__error__") if isinstance(payload, dict) else "non_json"
        return {"ok": False, "doc": None, "url": FDDD_DOCKING_URL, "from_cache": False,
                "errors": [f"fddd_docking_fetch_failed:{code}"]}
    return {"ok": True, "doc": payload, "url": FDDD_DOCKING_URL,
            "doc_sha256": sha256_text(canonical_json(payload)),
            "generated_at": payload.get("generatedAt"),
            "notes": list(payload.get("notes") or []),
            "from_cache": cache.hits > 0, "errors": []}


def find_target(doc: dict[str, Any], target: str) -> dict[str, Any] | None:
    """타깃을 FDDD ID, PDB ID, 이름 중 무엇으로 줘도 찾는다. 못 찾으면 None 이다."""
    key = _norm(target)
    if not key:
        return None
    entries = [t for t in (doc.get("targets") or []) if isinstance(t, dict)]
    for entry in entries:                                   # 정확히 맞는 것 먼저
        if key in (_norm(entry.get("id")), _norm(entry.get("pdbId")), _norm(entry.get("name"))):
            return entry
    for entry in entries:                                   # 그다음 부분 일치
        if key and (key in _norm(entry.get("id")) or key in _norm(entry.get("name"))):
            return entry
    return None


def find_combination(doc: dict[str, Any], target_id: str, compound: str) -> dict[str, Any] | None:
    """타깃 ID 와 화합물(ID 또는 이름)로 조합 하나를 찾는다."""
    key = _norm(compound)
    for combo in (doc.get("combinations") or []):
        if not isinstance(combo, dict) or combo.get("targetId") != target_id:
            continue
        if key in (_norm(combo.get("compoundId")), _norm(combo.get("name"))):
            return combo
    return None


def parse_combination(doc: dict[str, Any], target: str, compound: str, *,
                      doc_sha256: str | None = None, from_cache: bool = False,
                      url: str = FDDD_DOCKING_URL) -> VinaReferenceResult:
    """문서에서 조합 하나를 골라 VinaReferenceResult 로 옮긴다. 값을 새로 만들지 않는다.

    ``notes`` 는 조합을 찾았든 못 찾았든 항상 실어 보낸다. 해석 한계를 함께 내보내는 것이
    이 도구의 설계 의도다.
    """
    notes = [str(n) for n in (doc.get("notes") or [])]
    result = VinaReferenceResult(
        url=url, queried_target=str(target), queried_compound=str(compound),
        generated_at=doc.get("generatedAt"), fddd_notes=notes, from_cache=from_cache)

    target_entry = find_target(doc, target)
    if target_entry is None:
        result.errors.append(f"target_not_found:{target}")
        result.available_combinations = [str(c.get("id")) for c in (doc.get("combinations") or [])
                                        if isinstance(c, dict)]
        return result

    target_id = str(target_entry.get("id") or "")
    result.target_id = target_id
    result.target_name = target_entry.get("name")
    result.pdb_id = target_entry.get("pdbId")
    result.organism = target_entry.get("organism")
    result.receptor_pdbqt = target_entry.get("receptorPdbqt")

    combo = find_combination(doc, target_id, compound)
    if combo is None:
        result.errors.append(f"combination_not_found:{target_id}/{compound}")
        result.available_combinations = [str(c.get("id")) for c in (doc.get("combinations") or [])
                                        if isinstance(c, dict) and c.get("targetId") == target_id]
        return result

    protocols = {p.get("id"): p for p in (doc.get("protocols") or []) if isinstance(p, dict)}
    proto = protocols.get(combo.get("protocolId")) or {}
    box = proto.get("box") or {}
    provenance = doc.get("provenance") or {}
    log_sha = str(combo.get("logSha256") or "")

    result.combination_id = combo.get("id")
    result.compound_id = combo.get("compoundId")
    result.compound_name = combo.get("name")
    result.score_kcal_mol = combo.get("scoreKcalMol", combo.get("score"))
    result.units = proto.get("units")
    result.role = combo.get("role")                      # 원문 그대로. 요약하지 않는다.
    result.computed = bool(combo.get("computed"))
    result.computed_at = combo.get("computedAt")
    result.smiles = combo.get("smiles")
    result.smiles_kind = combo.get("smilesKind")
    result.executed_input = combo.get("inputUrl")
    result.protocol = VinaProtocol(
        id=proto.get("id"), tool=proto.get("tool"), version=proto.get("version"),
        runtime=proto.get("runtime"), scoring_function=proto.get("scoringFunction"),
        units=proto.get("units"), seed=proto.get("seed"),
        exhaustiveness=proto.get("exhaustiveness"), cpu=proto.get("cpu"),
        num_modes=proto.get("numModes"), box_center=box.get("center"), box_size=box.get("size"),
        box_source_url=proto.get("boxSourceUrl"), parameter_note=proto.get("parameterNote"))
    result.poses = [
        VinaPose(rank=int(p.get("rank")), score=p.get("score"),
                 rmsd_lower_bound_from_best=p.get("rmsdLowerBoundFromBest"),
                 rmsd_upper_bound_from_best=p.get("rmsdUpperBoundFromBest"))
        for p in (combo.get("poses") or []) if isinstance(p, dict) and p.get("rank") is not None]
    result.integrity = VinaIntegrity(
        receptor_pdbqt=target_entry.get("receptorSha256"),
        ligand_input_pdbqt=combo.get("inputSha256"),
        poses=combo.get("posesSha256"), log=log_sha or None,
        manifest_document=doc_sha256, wasm_runtime=provenance.get("runtimeWasmSha256"))

    if log_sha:
        result.evidence_id = evidence_id(log_sha)
        result.evidence_ids = [result.evidence_id]
    else:
        result.errors.append("log_sha256_missing")
    result.found = result.score_kcal_mol is not None and bool(log_sha)
    if not result.found and "log_sha256_missing" not in result.errors:
        result.errors.append("score_missing")
    return result


def lookup(target: str, compound: str, *, use_cache: bool = True,
           getter: Callable[..., Any] | None = None) -> VinaReferenceResult:
    """FDDD 문서를 받아 조합 하나를 돌려준다. ``getter`` 는 테스트에서 주입한다."""
    fetched = fetch_docking_manifest(use_cache=use_cache, getter=getter)
    if not fetched["ok"]:
        return VinaReferenceResult(
            queried_target=str(target), queried_compound=str(compound),
            url=fetched["url"], errors=list(fetched["errors"]))
    return parse_combination(
        fetched["doc"], target, compound, doc_sha256=fetched.get("doc_sha256"),
        from_cache=bool(fetched.get("from_cache")), url=fetched["url"])


# --------------------------------------------------------------------------------------
# NAT 등록
# --------------------------------------------------------------------------------------
class VinaReferenceConfig(FunctionBaseConfig, name=TOOL_NAME):
    """FDDD Vina 실측 조회 도구 설정."""

    url: str = Field(default=FDDD_DOCKING_URL, description="FDDD 도킹 문서 URL")
    use_cache: bool = Field(
        default=True, description="원응답을 eval/results 에 캐시해 같은 문서를 다시 받지 않는다.")


@register_function(config_type=VinaReferenceConfig)
async def vina_reference(config: VinaReferenceConfig, _builder: Builder):

    async def _lookup(target: str, compound: str) -> VinaReferenceResult:
        """Look up a precomputed AutoDock Vina docking result served statically by FDDD.

        This tool runs no docking. It reads the manifest FDDD published at
        drug.flybrain.kr/data/docking/multi-target.json, where every combination was already
        executed with AutoDock Vina 1.2.3.

        target: a target identifier, e.g. "parp1-4r6e-chain-a", "4R6E" or "factor Xa".
        compound: a compound name, e.g. "niraparib" or "apixaban".

        Returns the Vina score with its unit (kcal/mol), the verbatim FDDD `role` string for
        that combination, the full protocol (tool and version, seed, exhaustiveness, cpu,
        num_modes, box center and size), SHA256 integrity values for receptor, executed input,
        poses and log, an evidence_id of the form dock:vina:<first 8 of the log sha256>, and the
        eight FDDD `notes` entries verbatim. Cite the evidence_id for every claim built from
        these numbers, and read the `role` and `fddd_notes` before writing any interpretation.

        INTERPRETATION LIMITS, from the FDDD notes:
        - Raw Vina scores from different targets are NOT calibrated cross-target affinities.
          Do not compare scores across targets, do not rank targets, and do not infer
          selectivity, efficacy or any fly response from them.
        - Do not convert a Vina score into an affinity: no Kd, Ki, IC50 or EC50.
        - Single seed, exhaustiveness 4, no uncertainty or convergence analysis. Do not claim
          convergence or reproducibility from this one run.
        - Pose RMSD columns compare poses within the same run, NOT to a crystallographic pose.
        - SMILES are identity metadata; the executed input is the prepared PDBQT file.
        - Check `organism`: one receptor in this set is mouse, not human.
        If the combination is absent, the result says so and lists the available combinations;
        never invent a score.
        """
        return lookup(target, compound, use_cache=config.use_cache)

    def _result_to_str(result: VinaReferenceResult) -> str:
        """pydantic 반환은 콘솔 프런트엔드에서 깨지므로 문자열 변환기를 함께 등록한다."""
        return result.model_dump_json()

    yield FunctionInfo.from_fn(_lookup, description=_lookup.__doc__, converters=[_result_to_str])
