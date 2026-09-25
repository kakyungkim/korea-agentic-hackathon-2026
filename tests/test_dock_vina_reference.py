"""dock_vina_reference 오프라인 테스트. 네트워크도 API 키도 쓰지 않는다.

실행: .venv/bin/python -m pytest tests/test_dock_vina_reference.py -q -m "not network"

픽스처는 2026-09-25 에 받아 둔 FDDD ``multi-target.json`` 실측값이다(캐시 파일
``eval/results/pharmasignal_cache_fddd_e4af1c0aa9f2.json``). 점수와 role 과 SHA256 과 notes 8항목은
원값 그대로이고, 타깃 3종 중 필요한 부분만 남겼다.

도구 모듈은 반드시 패키지 경로로 import 한다. 최상위 모듈로 두 번 들어오면 짧은 이름이 겹쳐
``nat validate`` 가 union_tag_invalid 로 실패한다(docs/TROUBLESHOOTING.md 8번).
"""

from __future__ import annotations

import inspect
import json

import pytest

from harness.tools import dock_vina_reference as vr

# FDDD 원문 notes 8항목. 요약하거나 번역하지 않는다.
FDDD_NOTES = [
    "These are three DIFFERENT proteins, not three PARP1 structures. COX-2 structure 3LN1 is mouse, not human.",
    "Raw Vina scores from different targets are NOT calibrated cross-target affinities. Do not globally rank targets or infer selectivity, Kd, Ki, IC50, efficacy, or fly response.",
    "Niraparib on factor Xa and COX-2 is exploratory computational cross-docking, not evidence of experimentally confirmed binding.",
    "Rigid published prepared receptors and ligands reused without local protonation changes. Single seed, exhaustiveness 4, no uncertainty/convergence analysis.",
    "SMILES are molecular identity metadata, not the executed input. Connectivity SMILES can omit stereochemistry; preserved prepared PDBQT files define the exact executed structures.",
    "Pose RMSD columns compare poses within each run, NOT to crystallographic ligand poses.",
    "Use receptorPdbqt for the exact docking receptor; receptorPdb is the full original experimental entry and may contain additional chains, waters and co-crystal ligands.",
    "All receptor/pose coordinates remain in their original Angstrom coordinate frame. A scene must apply the same translation/rotation to each target receptor and its associated poses.",
]

PARP1_LOG_SHA = "3fe4e8bb90aaf7c05e148760e714186b27c2815a1c43e18fdcf9ed4b541ff7be"
XA_LOG_SHA = "e3970b3cf97bc8ac6d7859465d9c0ec769051a7e1773a4ccba88de6b127b4294"
COX2_LOG_SHA = "7582cf9bc8e18cedc22d1a39cb8813469cceaceb6af10da4530841e8dbfad5c5"
NIRAPARIB_SMILES = "C1CC(CNC1)C2=CC=C(C=C2)N3C=C4C=CC=C(C4=N3)C(=O)N"

DOCKING_FIXTURE = {
    "schemaVersion": "fddd-multi-target-docking-v1",
    "computed": True,
    "generatedAt": "2026-09-14T19:57:35.667Z",
    "targets": [
        {"id": "parp1-4r6e-chain-a", "name": "Human PARP1 catalytic domain", "pdbId": "4R6E",
         "organism": "Homo sapiens",
         "receptorPdbqt": "/data/docking/inputs/4R6E-A_receptor_parp-1.pdbqt",
         "receptorSha256": "573b53e7cff5fcd49bfcff94b0af2e0a640820abe4c6125af07eecb8190f9aff",
         "protocolId": "vina-parp1-4r6e-chain-a"},
        {"id": "factor-xa-2p16", "name": "Human coagulation factor Xa", "pdbId": "2P16",
         "organism": "Homo sapiens",
         "receptorPdbqt": "/data/docking/inputs/2P16_receptor_factor-Xa.pdbqt",
         "receptorSha256": "468d654f0b0c0cda3f0cdbbb707579bdc21a527a6bd1c4bb7e26fc72f8782287",
         "protocolId": "vina-factor-xa-2p16"},
        {"id": "cox2-3ln1", "name": "Mouse cyclooxygenase-2 (COX-2)", "pdbId": "3LN1",
         "organism": "Mus musculus",
         "receptorPdbqt": "/data/docking/inputs/3LN1_receptor_COX-2.pdbqt",
         "receptorSha256": "8212fe20f7c9276d260df8ee2b13a01ca232b8c475d8ef2b234db60f7ad5b08f",
         "protocolId": "vina-cox2-3ln1"},
    ],
    "combinations": [
        {"id": "parp1-4r6e-chain-a--niraparib", "targetId": "parp1-4r6e-chain-a",
         "compoundId": "niraparib", "name": "Niraparib", "smiles": NIRAPARIB_SMILES,
         "smilesKind": "PubChem connectivity SMILES", "protocolId": "vina-parp1-4r6e-chain-a",
         "inputUrl": "/data/docking/inputs/4R6E_ligand_niraparib.pdbqt",
         "inputSha256": "a561742a0c8a99705ce18c2922e7912f578c3c2318b3294ee8e38b6b0390468a",
         "role": "co-crystal redocking control", "score": -10.178, "scoreKcalMol": -10.178,
         "posesSha256": "b90fc9d4872c3fc28683bc9f8408850e89197a571c4153d5636992ee3d1ac794",
         "logSha256": PARP1_LOG_SHA,
         "poses": [
             {"rank": 1, "score": -10.178, "rmsdLowerBoundFromBest": 0, "rmsdUpperBoundFromBest": 0},
             {"rank": 2, "score": -9.916, "rmsdLowerBoundFromBest": 4.295,
              "rmsdUpperBoundFromBest": 5.666},
         ],
         "computed": True, "computedAt": "2026-09-14T18:57:21.792Z"},
        {"id": "factor-xa-2p16--niraparib", "targetId": "factor-xa-2p16",
         "compoundId": "niraparib", "name": "Niraparib", "smiles": NIRAPARIB_SMILES,
         "smilesKind": "PubChem connectivity SMILES", "protocolId": "vina-factor-xa-2p16",
         "inputUrl": "/data/docking/inputs/4R6E_ligand_niraparib.pdbqt",
         "inputSha256": "a561742a0c8a99705ce18c2922e7912f578c3c2318b3294ee8e38b6b0390468a",
         "role": "Exploratory cross-docking; no claim of validated binding",
         "score": -7.967, "scoreKcalMol": -7.967,
         "posesSha256": "ccbd2e6d20b48b44c25bee1a090241a422dc0baa796b3cbc78542d41f65b6953",
         "logSha256": XA_LOG_SHA,
         "poses": [{"rank": 1, "score": -7.967, "rmsdLowerBoundFromBest": 0,
                    "rmsdUpperBoundFromBest": 0}],
         "computed": True, "computedAt": "2026-09-14T19:56:11.024Z"},
        {"id": "cox2-3ln1--niraparib", "targetId": "cox2-3ln1", "compoundId": "niraparib",
         "name": "Niraparib", "smiles": NIRAPARIB_SMILES,
         "smilesKind": "PubChem connectivity SMILES", "protocolId": "vina-cox2-3ln1",
         "inputUrl": "/data/docking/inputs/4R6E_ligand_niraparib.pdbqt",
         "role": "Exploratory cross-docking; no claim of validated binding",
         "score": -6.605, "scoreKcalMol": -6.605, "logSha256": COX2_LOG_SHA,
         "poses": [], "computed": True, "computedAt": "2026-09-14T19:56:10.827Z"},
    ],
    "protocols": [
        {"id": "vina-parp1-4r6e-chain-a", "targetId": "parp1-4r6e-chain-a",
         "tool": "AutoDock Vina", "version": "1.2.3",
         "runtime": "Webina/MolModa WASM in Node worker_threads", "scoringFunction": "vina",
         "units": "kcal/mol", "seed": 20260914, "exhaustiveness": 4, "cpu": 1, "numModes": 5,
         "box": {"center": [-39, 5, -8], "size": [15, 20, 14]},
         "boxSourceUrl": "https://github.com/durrantlab/webina/blob/4230729e/4R6E-A_docking_params.txt",
         "parameterNote": ("Published box reused; seed=20260914 and exhaustiveness=4 "
                           "deliberately override example settings.")},
        {"id": "vina-factor-xa-2p16", "targetId": "factor-xa-2p16", "tool": "AutoDock Vina",
         "version": "1.2.3", "runtime": "Webina/MolModa WASM in Node worker_threads",
         "scoringFunction": "vina", "units": "kcal/mol", "seed": 20260914, "exhaustiveness": 4,
         "cpu": 1, "numModes": 5,
         "box": {"center": [7.48497143, 43.97488571, 62.17711429], "size": [20, 20, 20]}},
        {"id": "vina-cox2-3ln1", "targetId": "cox2-3ln1", "tool": "AutoDock Vina",
         "version": "1.2.3", "scoringFunction": "vina", "units": "kcal/mol", "seed": 20260914,
         "exhaustiveness": 4, "cpu": 1, "numModes": 5,
         "box": {"center": [26, 24, 15], "size": [20, 20, 20]}},
    ],
    "provenance": {
        "runtimeWasmSha256": "702192bed93a6a254b8a06dc10c886d68bfc4079a2613853cbe1de39a6ac7d87",
        "manifestBuilder": "scripts/docking/build-multi-target.mjs",
    },
    "notes": list(FDDD_NOTES),
}


def _getter(doc=None, error=None):
    """``pharmasignal_common.http_get`` 자리에 끼우는 가짜 GET. 네트워크를 타지 않는다."""
    def get(url, cache=None, is_json=True, **_kwargs):
        return error if error is not None else (DOCKING_FIXTURE if doc is None else doc)
    return get


# --------------------------------------------------------------------------------------
# 근거 ID
# --------------------------------------------------------------------------------------
def test_evidence_id_uses_log_sha_prefix():
    assert vr.evidence_id(PARP1_LOG_SHA) == "dock:vina:3fe4e8bb"
    assert vr.evidence_id(XA_LOG_SHA) == "dock:vina:e3970b3c"
    assert vr.evidence_id(COX2_LOG_SHA) == "dock:vina:7582cf9b"
    with pytest.raises(ValueError):
        vr.evidence_id("abc")


def test_evidence_ids_match_eval_cases():
    """eval/cases.jsonl 의 과잉해석 케이스가 쓰는 ID 와 같아야 대조가 된다."""
    parp1 = vr.parse_combination(DOCKING_FIXTURE, "parp1-4r6e-chain-a", "niraparib")
    xa = vr.parse_combination(DOCKING_FIXTURE, "factor-xa-2p16", "niraparib")
    assert parp1.evidence_ids == ["dock:vina:3fe4e8bb"]
    assert xa.evidence_ids == ["dock:vina:e3970b3c"]


# --------------------------------------------------------------------------------------
# 파싱: 점수와 단위와 role 원문
# --------------------------------------------------------------------------------------
def test_parse_parp1_score_units_and_role_verbatim():
    r = vr.parse_combination(DOCKING_FIXTURE, "parp1-4r6e-chain-a", "niraparib",
                             doc_sha256="d" * 64)
    assert r.found is True and r.computed is True
    assert r.tool == "vina_reference"
    assert r.score_kcal_mol == -10.178
    assert r.units == "kcal/mol"
    assert r.role == "co-crystal redocking control"          # 원문 그대로
    assert r.target_name == "Human PARP1 catalytic domain"
    assert r.pdb_id == "4R6E" and r.organism == "Homo sapiens"
    assert r.compound_id == "niraparib" and r.compound_name == "Niraparib"
    assert r.combination_id == "parp1-4r6e-chain-a--niraparib"
    assert r.generated_at == "2026-09-14T19:57:35.667Z"
    assert r.computed_at == "2026-09-14T18:57:21.792Z"


def test_cross_docking_role_is_not_summarised_or_translated():
    r = vr.parse_combination(DOCKING_FIXTURE, "2P16", "niraparib")
    assert r.role == "Exploratory cross-docking; no claim of validated binding"
    assert r.score_kcal_mol == -7.967


def test_mouse_receptor_keeps_its_organism():
    """3LN1 은 생쥐 구조다. 종을 지워 버리면 종 차이 규칙을 지킬 수 없다."""
    r = vr.parse_combination(DOCKING_FIXTURE, "3LN1", "niraparib")
    assert r.organism == "Mus musculus"
    assert r.score_kcal_mol == -6.605


def test_protocol_carries_seed_exhaustiveness_and_box():
    p = vr.parse_combination(DOCKING_FIXTURE, "4R6E", "niraparib").protocol
    assert (p.tool, p.version) == ("AutoDock Vina", "1.2.3")
    assert (p.seed, p.exhaustiveness, p.cpu, p.num_modes) == (20260914, 4, 1, 5)
    assert p.box_center == [-39, 5, -8] and p.box_size == [15, 20, 14]
    assert p.units == "kcal/mol"
    assert "seed=20260914" in (p.parameter_note or "")


def test_poses_keep_within_run_rmsd_fields():
    r = vr.parse_combination(DOCKING_FIXTURE, "4R6E", "niraparib")
    assert [p.rank for p in r.poses] == [1, 2]
    assert r.poses[1].score == -9.916
    assert r.poses[1].rmsd_lower_bound_from_best == 4.295
    assert r.poses[1].rmsd_upper_bound_from_best == 5.666
    # 필드 이름이 "같은 실행의 1순위 포즈 기준"임을 드러내야 한다.
    assert "결정 구조" in (vr.VinaPose.model_fields["rmsd_lower_bound_from_best"].description or "")


def test_integrity_hashes_are_carried():
    r = vr.parse_combination(DOCKING_FIXTURE, "4R6E", "niraparib", doc_sha256="d" * 64)
    integ = r.integrity
    assert integ.log == PARP1_LOG_SHA
    assert integ.receptor_pdbqt.startswith("573b53e7")
    assert integ.ligand_input_pdbqt.startswith("a561742a")
    assert integ.poses.startswith("b90fc9d4")
    assert integ.manifest_document == "d" * 64
    assert integ.wasm_runtime.startswith("702192be")


def test_executed_input_is_pdbqt_not_smiles():
    r = vr.parse_combination(DOCKING_FIXTURE, "4R6E", "niraparib")
    assert r.executed_input == "/data/docking/inputs/4R6E_ligand_niraparib.pdbqt"
    assert r.smiles == NIRAPARIB_SMILES
    assert r.smiles_kind == "PubChem connectivity SMILES"


# --------------------------------------------------------------------------------------
# FDDD notes 8항목을 함께 내보낸다
# --------------------------------------------------------------------------------------
def test_all_eight_fddd_notes_are_returned_verbatim():
    r = vr.parse_combination(DOCKING_FIXTURE, "4R6E", "niraparib")
    assert len(r.fddd_notes) == 8
    assert r.fddd_notes == FDDD_NOTES
    joined = " ".join(r.fddd_notes)
    assert "NOT calibrated cross-target affinities" in joined
    assert "no uncertainty/convergence analysis" in joined


def test_notes_are_returned_even_when_the_combination_is_missing():
    r = vr.parse_combination(DOCKING_FIXTURE, "4R6E", "aspirin")
    assert r.found is False and len(r.fddd_notes) == 8


# --------------------------------------------------------------------------------------
# 없는 것을 만들지 않는다
# --------------------------------------------------------------------------------------
def test_unknown_compound_reports_absence_and_lists_alternatives():
    r = vr.parse_combination(DOCKING_FIXTURE, "parp1-4r6e-chain-a", "aspirin")
    assert r.found is False
    assert r.score_kcal_mol is None and r.role is None and r.evidence_ids == []
    assert r.errors == ["combination_not_found:parp1-4r6e-chain-a/aspirin"]
    assert r.available_combinations == ["parp1-4r6e-chain-a--niraparib"]


def test_unknown_target_reports_absence():
    r = vr.parse_combination(DOCKING_FIXTURE, "EGFR", "niraparib")
    assert r.found is False and r.target_id is None
    assert r.errors == ["target_not_found:EGFR"]
    assert len(r.available_combinations) == 3


def test_missing_log_sha_blocks_the_evidence_id():
    doc = json.loads(json.dumps(DOCKING_FIXTURE))
    doc["combinations"][0].pop("logSha256")
    r = vr.parse_combination(doc, "4R6E", "niraparib")
    assert r.found is False and r.evidence_id is None
    assert "log_sha256_missing" in r.errors
    assert r.score_kcal_mol == -10.178       # 점수는 있었다는 사실은 그대로 남긴다


def test_fetch_failure_is_reported_not_filled_in():
    r = vr.lookup("4R6E", "niraparib", use_cache=False,
                  getter=_getter(error={"__error__": 503, "body": "down"}))
    assert r.found is False and r.score_kcal_mol is None
    assert r.errors == ["fddd_docking_fetch_failed:503"]


# --------------------------------------------------------------------------------------
# 타깃 식별자 해석과 lookup 배선
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("target", ["parp1-4r6e-chain-a", "4R6E", "4r6e",
                                    "Human PARP1 catalytic domain", "PARP1"])
def test_target_lookup_accepts_id_pdb_and_name(target):
    r = vr.parse_combination(DOCKING_FIXTURE, target, "niraparib")
    assert r.target_id == "parp1-4r6e-chain-a"


def test_lookup_passes_through_the_injected_getter():
    r = vr.lookup("2P16", "Niraparib", use_cache=False, getter=_getter())
    assert r.found is True and r.evidence_ids == ["dock:vina:e3970b3c"]
    assert r.integrity.manifest_document and len(r.integrity.manifest_document) == 64


# --------------------------------------------------------------------------------------
# 해석 한계 문장과 NAT 등록 형태
# --------------------------------------------------------------------------------------
def test_docstring_states_the_interpretation_limits_for_the_llm():
    source = inspect.getsource(vr)
    for sentence in ("NOT calibrated cross-target affinities",
                     "Do not convert a Vina score into an affinity",
                     "Do not claim",
                     "convergence or reproducibility"):
        assert sentence in source


def test_result_carries_the_interpretation_warning_and_execution_note():
    r = vr.parse_combination(DOCKING_FIXTURE, "4R6E", "niraparib")
    assert "환산하지 않는다" in r.interpretation_warning
    assert "재현성을 주장하지 않는다" in r.interpretation_warning
    assert "도킹을 실행하지 않는다" in r.execution_note


def test_config_name_and_defaults():
    cfg = vr.VinaReferenceConfig()
    assert vr.VinaReferenceConfig.static_type() == "vina_reference"
    assert cfg.url == "https://drug.flybrain.kr/data/docking/multi-target.json"
    assert cfg.use_cache is True


def test_result_serializes_to_str_for_console():
    r = vr.parse_combination(DOCKING_FIXTURE, "4R6E", "niraparib")
    payload = json.loads(r.model_dump_json())
    assert payload["tool"] == "vina_reference"
    assert payload["evidence_ids"] == ["dock:vina:3fe4e8bb"]
    assert len(payload["fddd_notes"]) == 8
    assert payload["role"] == "co-crystal redocking control"


# --------------------------------------------------------------------------------------
# 네트워크 (기본 실행에서 건너뛴다)
# --------------------------------------------------------------------------------------
@pytest.mark.network
def test_live_fddd_docking_lookup():
    r = vr.lookup("parp1-4r6e-chain-a", "niraparib")
    assert r.found is True
    assert r.score_kcal_mol == -10.178
    assert r.role == "co-crystal redocking control"
    assert r.evidence_ids == ["dock:vina:3fe4e8bb"]
    assert len(r.fddd_notes) == 8
