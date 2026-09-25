"""dock_diffdock 오프라인 테스트. 네트워크도 API 키도 쓰지 않는다.

실행: .venv/bin/python -m pytest tests/test_dock_diffdock.py -q -m "not network"

픽스처 값은 eval/results/diffdock_smoke.txt 의 2026-09-25 실측 기록에서 가져왔다.
SDF 본문만 길어서 줄였고 신뢰도 세 개는 원값 그대로다.
"""

from __future__ import annotations

import inspect
import json

import pytest

from harness.tools import bionemo_client as bc
from harness.tools import dock_diffdock as dd

# 2026-09-25 스모크의 실측값
SMOKE_CONFIDENCE = [0.7979534864425659, 0.7512781023979187, 0.7245222330093384]
NIRAPARIB_SMILES = "C1CC(CNC1)C2=CC=C(C=C2)N3C=C4C=CC=C(C4=N3)C(=O)N"

PDB_SAMPLE = "\n".join([
    "HEADER    TRANSFERASE                             01-JAN-00   4R6E",
    "ATOM      1  N   SER A 662      10.000  20.000  30.000  1.00 20.00           N",
    "ATOM      2  CA  SER A 662      11.000  21.000  31.000  1.00 20.00           C",
    "HETATM    3  O   HOH A 900      13.000  23.000  33.000  1.00 30.00           O",
    "ATOM      4  N   GLY B   1      12.000  22.000  32.000  1.00 20.00           N",
    "END",
])

RESPONSE_FIXTURE = {
    "status": "success",
    "details": "success without retry",
    "protein": "ATOM      1  N   SER A 662 ...",
    "ligand": NIRAPARIB_SMILES,
    "ligand_positions": [
        "pose1\n     RDKit          3D\n$$$$",
        "pose2\n     RDKit          3D\n$$$$",
        "pose3\n     RDKit          3D\n$$$$",
    ],
    "position_confidence": SMOKE_CONFIDENCE,
    "trajectory": None,
}


def _response(body=None, request_sha256="", from_cache=False):
    body = RESPONSE_FIXTURE if body is None else body
    return bc.NimResponse(
        status=200, body=body, headers={"nvcf-status": "fulfilled"},
        url=dd.DIFFDOCK_URL, request_sha256=request_sha256,
        response_sha256=bc.sha256_text(bc.canonical_json(body)),
        elapsed_s=4.1, from_cache=from_cache)


# --------------------------------------------------------------------------------------
# 페이로드
# --------------------------------------------------------------------------------------
def test_payload_uses_steps_not_num_steps():
    p = dd.build_payload("ATOM x", NIRAPARIB_SMILES, num_poses=3, time_divisions=20, steps=18)
    assert "steps" in p and "num_steps" not in p
    assert p["steps"] == 18 and isinstance(p["steps"], int)
    assert p["num_poses"] == 3 and p["time_divisions"] == 20
    assert p["ligand_file_type"] == "txt"   # SMILES 는 smiles 가 아니라 txt
    assert p["save_trajectory"] is False
    assert "is_staged" not in p             # 사용법이 없어 건드리지 않는다


def test_payload_fallback_field_name():
    p = dd.build_payload("ATOM x", "C", steps_field="num_steps")
    assert p["num_steps"] == 18 and "steps" not in p
    with pytest.raises(ValueError):
        dd.build_payload("ATOM x", "C", steps_field="n_steps")


def test_payload_rejects_smiles_file_type():
    with pytest.raises(ValueError) as exc:
        dd.build_payload("ATOM x", "C", ligand_file_type="smiles")
    assert "txt" in str(exc.value)


def test_payload_numbers_are_not_strings():
    p = dd.build_payload("ATOM x", "C", num_poses="3", time_divisions="20", steps="18")
    assert all(isinstance(p[k], int) for k in ("num_poses", "time_divisions", "steps"))


# --------------------------------------------------------------------------------------
# 응답 파싱과 근거 ID
# --------------------------------------------------------------------------------------
def test_parse_response_ranks_and_confidence():
    sha = bc.payload_sha256({"protein": "ATOM x"})
    r = dd.parse_diffdock_response(RESPONSE_FIXTURE, sha, protein_atom_count=2752)
    assert r.tool == "diffdock_nim"
    assert r.status == "success" and r.details == "success without retry"
    assert r.num_poses_returned == 3
    assert r.position_confidence == SMOKE_CONFIDENCE
    assert [p.rank for p in r.poses] == [1, 2, 3]
    assert r.poses[0].position_confidence == pytest.approx(0.7979534864425659)
    assert r.poses[0].sdf.startswith("pose1")   # [0] 이 1순위다
    assert r.poses[0].position_confidence >= r.poses[2].position_confidence
    assert r.trajectory_present is False
    assert r.protein_atom_count == 2752
    assert r.field_name_used == "steps"


def test_evidence_id_format():
    sha = "abcdef1234567890" + "0" * 48
    assert dd.evidence_id(sha, 1) == "dock:diffdock:abcdef12:pose1"
    r = dd.parse_diffdock_response(RESPONSE_FIXTURE, sha)
    assert r.evidence_ids == [
        "dock:diffdock:abcdef12:pose1",
        "dock:diffdock:abcdef12:pose2",
        "dock:diffdock:abcdef12:pose3",
    ]
    assert [p.evidence_id for p in r.poses] == r.evidence_ids


def test_parse_handles_short_confidence_array():
    body = dict(RESPONSE_FIXTURE, position_confidence=[0.79])
    r = dd.parse_diffdock_response(body, "a" * 64)
    assert r.poses[0].position_confidence == pytest.approx(0.79)
    assert r.poses[1].position_confidence is None
    assert r.num_poses_returned == 3


def test_parse_rejects_non_list_positions():
    with pytest.raises(ValueError):
        dd.parse_diffdock_response({"ligand_positions": "sdf"}, "a" * 64)


def test_parse_trajectory_present():
    body = dict(RESPONSE_FIXTURE, trajectory=["frame1"])
    assert dd.parse_diffdock_response(body, "a" * 64).trajectory_present is True


# --------------------------------------------------------------------------------------
# dock(): ATOM 추출, 해시, 422 폴백
# --------------------------------------------------------------------------------------
def test_dock_extracts_atom_records_and_hashes_request():
    sent = []

    def fake_post(url, payload, timeout, **kwargs):
        sent.append((url, payload, timeout, kwargs))
        return _response(request_sha256=bc.payload_sha256(payload))

    r = dd.dock(PDB_SAMPLE, NIRAPARIB_SMILES, chains="A", num_poses=3, post=fake_post)
    url, payload, timeout, kwargs = sent[0]
    assert url == dd.DIFFDOCK_URL
    assert payload["protein"].splitlines() == [
        line for line in PDB_SAMPLE.splitlines()
        if line.startswith("ATOM") and line[21] == "A"]
    assert "HETATM" not in payload["protein"]
    assert kwargs["cache_source"] == "bionemo_diffdock"
    assert timeout == bc.DEFAULT_TIMEOUT == 900
    assert r.protein_atom_count == 2
    assert r.request_sha256 == bc.payload_sha256(payload)
    assert r.evidence_ids[0] == f"dock:diffdock:{r.request_sha256[:8]}:pose1"
    assert r.response_sha256 and len(r.response_sha256) == 64


def test_dock_falls_back_to_num_steps_on_422():
    payloads = []

    def fake_post(url, payload, timeout, **kwargs):
        payloads.append(payload)
        if "steps" in payload:
            raise bc.NimHTTPError(422, '{"error": "unknown field steps"}', url)
        return _response(request_sha256=bc.payload_sha256(payload))

    r = dd.dock(PDB_SAMPLE, NIRAPARIB_SMILES, post=fake_post)
    assert len(payloads) == 2                      # 폴백은 1회뿐이다
    assert "steps" in payloads[0] and "num_steps" not in payloads[0]
    assert "num_steps" in payloads[1] and "steps" not in payloads[1]
    assert r.field_name_used == "num_steps"
    assert r.num_poses_returned == 3


def test_dock_no_fallback_when_steps_accepted():
    payloads = []

    def fake_post(url, payload, timeout, **kwargs):
        payloads.append(payload)
        return _response(request_sha256=bc.payload_sha256(payload))

    r = dd.dock(PDB_SAMPLE, NIRAPARIB_SMILES, post=fake_post)
    assert len(payloads) == 1
    assert r.field_name_used == "steps"


def test_dock_propagates_non_422_errors():
    def fake_post(url, payload, timeout, **kwargs):
        raise bc.NimHTTPError(500, "server error", url)

    with pytest.raises(bc.NimHTTPError) as exc:
        dd.dock(PDB_SAMPLE, NIRAPARIB_SMILES, post=fake_post)
    assert exc.value.status == 500


def test_dock_empty_chain_selection_raises():
    def fake_post(url, payload, timeout, **kwargs):  # pragma: no cover  불려서는 안 된다
        raise AssertionError("ATOM 이 없으면 호출 전에 멈춰야 한다")

    with pytest.raises(ValueError):
        dd.dock(PDB_SAMPLE, NIRAPARIB_SMILES, chains="Z", post=fake_post)


# --------------------------------------------------------------------------------------
# 과잉해석 경고와 NAT 등록 형태
# --------------------------------------------------------------------------------------
def test_confidence_warning_is_carried_in_the_result():
    warning = "Do not convert confidence directly into binding affinity."
    r = dd.parse_diffdock_response(RESPONSE_FIXTURE, "a" * 64)
    assert "결합 친화도가 아니다" in r.confidence_warning
    assert warning in dd.CONFIDENCE_WARNING
    source = inspect.getsource(dd)
    assert warning in source                       # 도구 docstring 이 LLM 에게 보여 줄 문장
    assert "kcal/mol" in source                    # Vina 와 같은 척도로 비교하지 말 것


def test_config_name_and_fields():
    cfg = dd.DiffDockConfig()
    assert dd.DiffDockConfig.static_type() == "diffdock_nim"
    assert cfg.base_url == "https://health.api.nvidia.com/v1/biology/mit/diffdock"
    assert (cfg.num_poses, cfg.time_divisions, cfg.steps, cfg.timeout) == (3, 20, 18, 900)


def test_result_serializes_to_str_for_console():
    r = dd.parse_diffdock_response(RESPONSE_FIXTURE, "a" * 64)
    payload = json.loads(r.model_dump_json())
    assert payload["tool"] == "diffdock_nim"
    assert payload["evidence_ids"][0].startswith("dock:diffdock:")
    assert payload["poses"][0]["position_confidence"] == pytest.approx(SMOKE_CONFIDENCE[0])
