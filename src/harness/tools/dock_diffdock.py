"""DiffDock NIM 단백질-리간드 도킹 도구 (NAT 래퍼).

호출 계층은 ``bionemo_client`` 가 전부 맡고 이 모듈은 페이로드를 만들고 응답을 파싱해
근거 ID 를 붙이는 일만 한다. 등록 이름은 ``diffdock_nim`` 이다.

규격 근거
- 사양: ``docs/notes/bionemo-nim.md``
- 실측: ``eval/results/diffdock_smoke.txt`` (2026-09-25). 4R6E chain A 의 ATOM 2,752줄(222KB)과
  niraparib SMILES 로 HTTP 200, 4.1초, ``Nvcf-Status: fulfilled``,
  ``position_confidence`` [0.798, 0.751, 0.725], 포즈 3개(SDF).

실측으로 굳은 규칙
- 필드 이름은 ``steps`` 다. ``num_steps`` 가 아니다. 다만 블루프린트 노트북이 ``num_steps`` 를
  쓰므로 422 가 오면 한 번만 ``num_steps`` 로 다시 보낸다.
- SMILES 를 줄 때 ``ligand_file_type`` 은 ``"txt"`` 다. ``"smiles"`` 가 아니다.
- ``protein`` 은 PDB 텍스트 인라인이고 ATOM 레코드만 남긴다. base64 도 업로드도 아니다.
- ``is_staged`` 는 쓰지 않는다. 사용법이 어느 문서에도 없고 222KB 인라인이 통과했다.

점수 해석 경고 (NVIDIA 문서 원문)
    "Do not convert confidence directly into binding affinity."
``position_confidence`` 는 포즈 신뢰도이지 결합 친화도가 아니다. AutoDock Vina 의 kcal/mol 과
같은 척도로 비교하지 않는다. 이 문장을 도구 설명에 그대로 넣어 모델이 보게 한다.
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

try:
    from .bionemo_client import (
        DIFFDOCK_URL, DEFAULT_TIMEOUT, NimHTTPError, NimResponse,
        count_atom_records, extract_atom_records, integrity_record, payload_sha256, post_json,
    )
    from .pharmasignal_common import now_iso
except ImportError:  # 스크립트/테스트에서 sys.path 로 직접 임포트할 때
    from bionemo_client import (  # type: ignore[no-redef]
        DIFFDOCK_URL, DEFAULT_TIMEOUT, NimHTTPError, NimResponse,
        count_atom_records, extract_atom_records, integrity_record, payload_sha256, post_json,
    )
    from pharmasignal_common import now_iso  # type: ignore[no-redef]

TOOL_NAME = "diffdock_nim"
CACHE_SOURCE = "bionemo_diffdock"

CONFIDENCE_WARNING = (
    "position_confidence 는 포즈 신뢰도이고 결합 친화도가 아니다. "
    "NVIDIA 문서 원문: Do not convert confidence directly into binding affinity. "
    "AutoDock Vina 의 kcal/mol 과 같은 척도로 비교하지 않는다."
)


# --------------------------------------------------------------------------------------
# 반환 스키마
# --------------------------------------------------------------------------------------
class DockPose(BaseModel):
    """포즈 하나. 랭크는 1부터 세고 1순위가 ``ligand_positions[0]`` 이다."""

    rank: int = Field(description="포즈 순위. 1 이 1순위다.")
    position_confidence: float | None = Field(
        default=None,
        description="DiffDock 의 포즈 신뢰도. 결합 친화도가 아니고 kcal/mol 도 아니다.")
    sdf: str = Field(description="포즈의 SDF 문자열 (RDKit 3D).")
    evidence_id: str = Field(
        description="근거 ID. 형식 dock:diffdock:<요청 SHA256 앞 8자>:pose<순위>")


class DiffDockResult(BaseModel):
    """DiffDock 한 번의 결과. 수치는 응답에서만 오고 해석은 붙이지 않는다."""

    tool: str = Field(default=TOOL_NAME)
    endpoint: str = Field(description="호출한 엔드포인트 URL")
    status: str | None = Field(default=None, description="응답의 status 필드")
    details: str | None = Field(default=None, description="응답의 details 필드")
    field_name_used: str = Field(
        default="steps",
        description="스텝 수를 보낸 필드 이름. steps 가 기본이고 422 폴백에서만 num_steps 다.")
    num_poses_returned: int = Field(description="응답으로 온 포즈 개수")
    position_confidence: list[float] = Field(
        default_factory=list, description="포즈별 신뢰도. ligand_positions 와 평행한 배열이다.")
    poses: list[DockPose] = Field(default_factory=list, description="랭크순 포즈 목록")
    evidence_ids: list[str] = Field(default_factory=list, description="포즈별 근거 ID 목록")
    request_sha256: str = Field(description="요청 페이로드의 SHA256")
    response_sha256: str = Field(description="응답 본문의 SHA256")
    protein_atom_count: int = Field(default=0, description="보낸 단백질의 ATOM 줄 수")
    ligand_file_type: str = Field(default="txt", description="SMILES 는 txt 다")
    trajectory_present: bool = Field(default=False, description="save_trajectory 결과가 있는지")
    from_cache: bool = Field(default=False, description="응답을 캐시에서 읽었는지")
    elapsed_s: float = Field(default=0.0, description="호출에 걸린 초. 캐시 적중이면 0 이다.")
    retrieved_at: str = Field(default_factory=now_iso)
    confidence_warning: str = Field(default=CONFIDENCE_WARNING)


# --------------------------------------------------------------------------------------
# 페이로드와 파싱. 순수 함수라 오프라인에서 그대로 검증한다.
# --------------------------------------------------------------------------------------
def build_payload(protein: str, ligand: str, *, ligand_file_type: str = "txt",
                  num_poses: int = 3, time_divisions: int = 20, steps: int = 18,
                  save_trajectory: bool = False, steps_field: str = "steps") -> dict[str, Any]:
    """DiffDock 요청 본문을 만든다. 숫자 필드는 숫자로 보낸다(NVIDIA 문서: 문자열 숫자 금지).

    ``steps_field`` 는 ``steps`` 가 기본이고 422 폴백에서만 ``num_steps`` 가 된다.
    ``is_staged`` 는 넣지 않는다.
    """
    if steps_field not in ("steps", "num_steps"):
        raise ValueError(f"steps_field 는 steps 또는 num_steps 여야 합니다: {steps_field!r}")
    if ligand_file_type not in ("txt", "sdf", "mol2"):
        raise ValueError(
            f"ligand_file_type 은 txt, sdf, mol2 중 하나입니다: {ligand_file_type!r}. "
            "SMILES 는 smiles 가 아니라 txt 다.")
    return {
        "protein": protein,
        "ligand": ligand,
        "ligand_file_type": ligand_file_type,
        "num_poses": int(num_poses),
        "time_divisions": int(time_divisions),
        steps_field: int(steps),
        "save_trajectory": bool(save_trajectory),
    }


def evidence_id(request_sha256: str, rank: int) -> str:
    """근거 ID. 형식 ``dock:diffdock:<요청 SHA256 앞 8자>:pose<순위>``."""
    return f"dock:diffdock:{request_sha256[:8]}:pose{rank}"


def parse_diffdock_response(body: dict[str, Any], request_sha256: str, *,
                            endpoint: str = DIFFDOCK_URL, field_name_used: str = "steps",
                            protein_atom_count: int = 0, ligand_file_type: str = "txt",
                            response_sha256: str = "", from_cache: bool = False,
                            elapsed_s: float = 0.0) -> DiffDockResult:
    """응답 본문을 DiffDockResult 로 옮긴다.

    ``ligand_positions`` 는 랭크순 SDF 문자열 배열이고 ``position_confidence`` 는 그와 평행한
    float 배열이다. 두 배열의 길이가 어긋나면 짧은 쪽에 맞추지 않고 신뢰도를 None 으로 둔다.
    """
    positions = body.get("ligand_positions") or []
    if not isinstance(positions, list):
        raise ValueError(f"ligand_positions 가 배열이 아닙니다: {type(positions).__name__}")
    raw_conf = body.get("position_confidence") or []
    confidences = [float(c) for c in raw_conf] if isinstance(raw_conf, list) else []

    poses: list[DockPose] = []
    for idx, sdf in enumerate(positions):
        rank = idx + 1
        conf = confidences[idx] if idx < len(confidences) else None
        poses.append(DockPose(
            rank=rank, position_confidence=conf, sdf=str(sdf),
            evidence_id=evidence_id(request_sha256, rank)))

    trajectory = body.get("trajectory")
    return DiffDockResult(
        endpoint=endpoint,
        status=body.get("status"),
        details=body.get("details"),
        field_name_used=field_name_used,
        num_poses_returned=len(poses),
        position_confidence=confidences,
        poses=poses,
        evidence_ids=[p.evidence_id for p in poses],
        request_sha256=request_sha256,
        response_sha256=response_sha256,
        protein_atom_count=protein_atom_count,
        ligand_file_type=ligand_file_type,
        trajectory_present=bool(trajectory),
        from_cache=from_cache,
        elapsed_s=elapsed_s,
    )


def dock(protein_pdb: str, ligand: str, *, chains: str | list[str] | None = None,
         ligand_file_type: str = "txt", num_poses: int = 3, time_divisions: int = 20,
         steps: int = 18, save_trajectory: bool = False,
         base_url: str = DIFFDOCK_URL, timeout: float = DEFAULT_TIMEOUT,
         use_cache: bool = True,
         post: Callable[..., NimResponse] | None = None) -> DiffDockResult:
    """DiffDock 을 한 번 부른다. ``steps`` 로 보내고 422 가 오면 ``num_steps`` 로 1회 폴백한다.

    ``protein_pdb`` 는 PDB 원문이어도 되고 ATOM 만 남긴 텍스트여도 된다. 어느 쪽이든 여기서
    ATOM 레코드만 다시 추려서 보낸다. ``post`` 는 테스트에서 주입한다.
    """
    protein = extract_atom_records(protein_pdb, chains)
    atom_count = count_atom_records(protein)
    do_post = post or post_json

    payload = build_payload(
        protein, ligand, ligand_file_type=ligand_file_type, num_poses=num_poses,
        time_divisions=time_divisions, steps=steps, save_trajectory=save_trajectory,
        steps_field="steps")
    field_used = "steps"
    try:
        resp = do_post(base_url, payload, timeout, cache_source=CACHE_SOURCE, use_cache=use_cache)
    except NimHTTPError as exc:
        if exc.status != 422:
            raise
        # 호스팅은 steps 로 확인됐지만 블루프린트 노트북이 num_steps 를 쓴다. 한 번만 폴백한다.
        payload = build_payload(
            protein, ligand, ligand_file_type=ligand_file_type, num_poses=num_poses,
            time_divisions=time_divisions, steps=steps, save_trajectory=save_trajectory,
            steps_field="num_steps")
        field_used = "num_steps"
        resp = do_post(base_url, payload, timeout, cache_source=CACHE_SOURCE, use_cache=use_cache)

    return parse_diffdock_response(
        resp.body, resp.request_sha256 or payload_sha256(payload),
        endpoint=base_url, field_name_used=field_used, protein_atom_count=atom_count,
        ligand_file_type=ligand_file_type, response_sha256=resp.response_sha256,
        from_cache=resp.from_cache, elapsed_s=resp.elapsed_s)


# --------------------------------------------------------------------------------------
# NAT 등록. 배선(register.py import, author.yml functions)은 오케스트레이터가 따로 한다.
# --------------------------------------------------------------------------------------
class DiffDockConfig(FunctionBaseConfig, name=TOOL_NAME):
    """DiffDock NIM 도구 설정. 기본값은 스모크에서 통과한 조합이다."""

    base_url: str = Field(default=DIFFDOCK_URL, description="DiffDock NIM 엔드포인트 URL")
    num_poses: int = Field(default=3, description="생성할 포즈 수. 호스팅 상한은 100 이다.")
    time_divisions: int = Field(default=20, description="역확산 시간 분할 수. 상한 20.")
    steps: int = Field(default=18, description="역확산 스텝 수. 상한 18.")
    timeout: float = Field(default=DEFAULT_TIMEOUT, description="HTTP 타임아웃 초")


@register_function(config_type=DiffDockConfig)
async def diffdock_nim(config: DiffDockConfig, _builder: Builder):

    async def _dock(protein_pdb: str, ligand_smiles: str, chain: str = "") -> DiffDockResult:
        """Dock a ligand into a protein structure with the NVIDIA DiffDock NIM.

        protein_pdb: PDB text of the receptor (ATOM records are extracted here).
        ligand_smiles: ligand SMILES, sent inline with ligand_file_type "txt".
        chain: optional chain id to keep, e.g. "A". Empty keeps every chain.

        Returns ranked poses as SDF strings with their position_confidence and an
        evidence_id per pose (dock:diffdock:<sha8>:pose<rank>). Cite the evidence_id
        for every claim built from these numbers.

        WARNING from the NVIDIA documentation: Do not convert confidence directly into
        binding affinity. position_confidence is a pose confidence score, not a binding
        energy. Do not compare it on the same scale as AutoDock Vina kcal/mol values,
        and do not call a pose "strong binding" on the basis of this number alone.
        """
        return dock(
            protein_pdb, ligand_smiles, chains=chain or None,
            ligand_file_type="txt", num_poses=config.num_poses,
            time_divisions=config.time_divisions, steps=config.steps,
            base_url=config.base_url, timeout=config.timeout)

    def _result_to_str(result: DiffDockResult) -> str:
        """pydantic 반환은 콘솔 프런트엔드에서 깨지므로 문자열 변환기를 함께 등록한다."""
        return result.model_dump_json()

    yield FunctionInfo.from_fn(_dock, description=_dock.__doc__, converters=[_result_to_str])
