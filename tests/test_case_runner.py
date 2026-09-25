"""case_runner 오프라인 테스트. 네트워크도 API 키도 쓰지 않는다.

실행: .venv/bin/python -m pytest tests/test_case_runner.py -q -m "not network"

픽스처 값의 출처
- FDDD 도킹 값과 프로토콜: ``drug.flybrain.kr/data/docking/multi-target.json`` (2026-09-25 수신).
  필요한 두 조합(PARP1 4R6E chain A, factor Xa 2P16)과 그 프로토콜만 남겨 줄였고 수치는 원값이다.
- 구조 SHA256 과 ATOM 줄 수: 2026-09-25 RCSB 에서 받아 ``extract_atom_records`` 로 추린 값.
- FAERS 2x2 카운트: 2026-09-25 openFDA 조회값(데이터 최종 갱신 2026-07-30). 지표는 픽스처에
  숫자로 박지 않고 ``disproportionality`` 로 다시 계산해 오라클과 같은 값을 쓴다.
- 라벨과 문헌: ZEJULA setid b7f675e2-...-3f16d9492b7d 와 PubMed 검색 결과(2026-09-25).
"""

from __future__ import annotations

import json

import pytest

from harness.tools import bionemo_client as bc
from harness.tools import case_runner as cr
from harness.tools.pharmasignal_openfda import disproportionality

# --------------------------------------------------------------------------------------
# 픽스처. 실측값만 담는다.
# --------------------------------------------------------------------------------------
ATOM_SHA_A = "290872054fd93e027b84a809b7b4521000e44b8aef4f3b949d045d5da91c0532"
ATOM_SHA_B = "533a3c5b605f97dd3e8e565fd46bf309b153f06ecd4109e5f8c4981f42fbf94c"
LOG_SHA_A = "3fe4e8bb90aaf7c05e148760e714186b27c2815a1c43e18fdcf9ed4b541ff7be"
LOG_SHA_B = "e3970b3cf97bc8ac6d7859465d9c0ec769051a7e1773a4ccba88de6b127b4294"
FAERS_COUNTS = {"a": 1065, "b": 21051, "c": 108978, "d": 20561596,
                "n_drug": 22116, "n_reaction": 110043, "n_total": 20692690}

PDB_SAMPLE = "\n".join([
    "HEADER    TRANSFERASE                             01-JAN-00   4R6E",
    "ATOM      1  N   SER A 662      10.000  20.000  30.000  1.00 20.00           N",
    "ATOM      2  CA  SER A 662      11.000  21.000  31.000  1.00 20.00           C",
    "HETATM    3  O   HOH A 900      13.000  23.000  33.000  1.00 30.00           O",
    "ATOM      4  N   GLY B   1      12.000  22.000  32.000  1.00 20.00           N",
    "END",
])

DOCKING_DOC = {
    "schemaVersion": "fddd-multi-target-docking-v1",
    "computed": True,
    "generatedAt": "2026-09-14T19:57:35.667Z",
    "targets": [
        {"id": "parp1-4r6e-chain-a", "name": "Human PARP1 catalytic domain", "pdbId": "4R6E",
         "organism": "Homo sapiens", "protocolId": "vina-parp1-4r6e-chain-a",
         "receptorSha256": "573b53e7cff5fcd49bfcff94b0af2e0a640820abe4c6125af07eecb8190f9aff"},
        {"id": "factor-xa-2p16", "name": "Human coagulation factor Xa", "pdbId": "2P16",
         "organism": "Homo sapiens", "protocolId": "vina-factor-xa-2p16",
         "receptorSha256": "468d654f0b0c0cda3f0cdbbb707579bdc21a527a6bd1c4bb7e26fc72f8782287"},
    ],
    "protocols": [
        {"id": "vina-parp1-4r6e-chain-a", "tool": "AutoDock Vina", "version": "1.2.3",
         "runtime": "Webina/MolModa WASM in Node worker_threads", "scoringFunction": "vina",
         "units": "kcal/mol", "seed": 20260914, "exhaustiveness": 4, "cpu": 1, "numModes": 5,
         "box": {"center": [-39, 5, -8], "size": [15, 20, 14]}},
        {"id": "vina-factor-xa-2p16", "tool": "AutoDock Vina", "version": "1.2.3",
         "runtime": "Webina/MolModa WASM in Node worker_threads", "scoringFunction": "vina",
         "units": "kcal/mol", "seed": 20260914, "exhaustiveness": 4, "cpu": 1, "numModes": 5,
         "box": {"center": [7.48497143, 43.97488571, 62.17711429], "size": [20, 20, 20]}},
    ],
    "combinations": [
        {"id": "parp1-4r6e-chain-a--niraparib", "targetId": "parp1-4r6e-chain-a",
         "compoundId": "niraparib", "smiles": cr.COMPOUND_SMILES,
         "smilesKind": "PubChem connectivity SMILES",
         "protocolId": "vina-parp1-4r6e-chain-a",
         "inputUrl": "/data/docking/inputs/4R6E_ligand_niraparib.pdbqt",
         "inputSha256": "a561742a0c8a99705ce18c2922e7912f578c3c2318b3294ee8e38b6b0390468a",
         "role": "co-crystal redocking control", "score": -10.178, "scoreKcalMol": -10.178,
         "posesSha256": "b90fc9d4872c3fc28683bc9f8408850e89197a571c4153d5636992ee3d1ac794",
         "logSha256": LOG_SHA_A, "computed": True,
         "computedAt": "2026-09-14T18:57:21.792Z",
         "poses": [{"rank": 1, "score": -10.178, "rmsdLowerBoundFromBest": 0}]},
        {"id": "factor-xa-2p16--niraparib", "targetId": "factor-xa-2p16",
         "compoundId": "niraparib", "smiles": cr.COMPOUND_SMILES,
         "smilesKind": "PubChem connectivity SMILES; prepared PDBQT is the executed 3D input",
         "protocolId": "vina-factor-xa-2p16",
         "inputUrl": "/data/docking/inputs/4R6E_ligand_niraparib.pdbqt",
         "inputSha256": "a561742a0c8a99705ce18c2922e7912f578c3c2318b3294ee8e38b6b0390468a",
         "role": "Exploratory cross-docking; no claim of validated binding",
         "score": -7.967, "scoreKcalMol": -7.967,
         "posesSha256": "0f2a1b6c9d4e8f37a5b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0",
         "logSha256": LOG_SHA_B, "computed": True,
         "computedAt": "2026-09-14T19:30:00.000Z",
         "poses": [{"rank": 1, "score": -7.967, "rmsdLowerBoundFromBest": 0}]},
    ],
    "provenance": {"runtimeWasmSha256":
                   "702192bed93a6a254b8a06dc10c886d68bfc4079a2613853cbe1de39a6ac7d87"},
    "notes": [
        "These are three DIFFERENT proteins, not three PARP1 structures.",
        "Raw Vina scores from different targets are NOT calibrated cross-target affinities.",
        "Niraparib on factor Xa and COX-2 is exploratory computational cross-docking.",
    ],
}

EVIDENCE_DOC = {
    "capturedAt": "2026-09-14T19:09:16.499Z",
    "bindingdb": {
        "sourceUrl": "https://www.bindingdb.org/rest/getLigandsByUniprots?uniprot=P09874"
                     "&cutoff=10000&response=application/json",
        "target": "Human PARP1 / UniProt P09874",
        "recordCount": 7311, "compoundCount": 5769,
        "counts": {"Ki": 1194, "IC50": 5588, "Kd": 214, "EC50": 315},
        "warning": "Ki, Kd, IC50 and EC50 are distinct endpoints and are NOT pooled into one "
                   "affinity score.",
        "filter": "API affinity cutoff10000nM.",
    },
}

DIFFDOCK_BODY = {
    "status": "success", "details": "success without retry",
    "ligand_positions": ["pose1\n     RDKit          3D\n$$$$",
                         "pose2\n     RDKit          3D\n$$$$",
                         "pose3\n     RDKit          3D\n$$$$"],
    "position_confidence": [0.7607949376106262, 0.693301260471344, 0.514950692653656],
    "trajectory": None,
}


# 경로 B(응고인자 Xa) DiffDock 실측. 2026-09-25 실행한 eval/results/case_niraparib.json 의 값이다.
DIFFDOCK_BODY_B = {
    "status": "success", "details": "success without retry",
    "position_confidence": [-0.17230159044265747, -0.2045024335384369, -0.6646066308021545],
}
DIFFDOCK_REQUEST_SHA_B = "91b182ea53cf09657b9670738d7bcfb39c17866495d7a8126f22cc630df323b3"
DIFFDOCK_RESPONSE_SHA_B = "6b9c88eeb2a5ebf4137ce6d9050c64f4e2d1adfb0c9b5b7487b2f2121622defd"


def _docking_fixture() -> dict:
    return {"ok": True, "errors": [], "doc": DOCKING_DOC, "url": cr.FDDD_DOCKING_URL,
            "doc_sha256": bc.sha256_text(bc.canonical_json(DOCKING_DOC)),
            "generated_at": DOCKING_DOC["generatedAt"], "notes": DOCKING_DOC["notes"]}


def _evidence_fixture() -> dict:
    return {"ok": True, "errors": [], "doc": EVIDENCE_DOC, "url": cr.FDDD_EVIDENCE_URL,
            "doc_sha256": bc.sha256_text(bc.canonical_json(EVIDENCE_DOC)),
            "captured_at": EVIDENCE_DOC["capturedAt"]}


def _structure_fixture(pdb_id: str, chain: str, atoms: int, digest: str) -> dict:
    return {"step": "structure", "source": "RCSB", "ok": True, "pdb_id": pdb_id, "chain": chain,
            "chain_note": "", "pdb_bytes": 1879848, "pdb_sha256": digest,
            "atom_count_total": 10997, "chains_present": ["A", "B", "C", "D"],
            "atom_count_chain": atoms, "atom_text_bytes": 222911, "atom_text_sha256": digest,
            "evidence_ids": [cr.rcsb_evidence_id(pdb_id, chain, digest)], "errors": []}


def _diffdock_fixture(ok: bool = True) -> dict:
    if not ok:
        return {"step": "diffdock", "ok": False, "skipped": True,
                "skip_reason": "NVIDIA_API_KEY 가 없어 DiffDock 을 부르지 않았다.",
                "position_confidence": [], "poses": [], "evidence_ids": [], "errors": []}
    request_sha = "f31b513b3d160866e70e0804bf4b89181bfb06459436d40e06881e4ce523fb6a"
    return {"step": "diffdock", "ok": True, "skipped": False, "skip_reason": None,
            "num_poses_returned": 3,
            "position_confidence": list(DIFFDOCK_BODY["position_confidence"]),
            "poses": [{"rank": i + 1, "position_confidence": c,
                       "evidence_id": cr.diffdock_evidence_id(request_sha, i + 1)}
                      for i, c in enumerate(DIFFDOCK_BODY["position_confidence"])],
            "request_sha256": request_sha, "response_sha256": "a3f5fdbd1bb3ee98edbb0ee1cb8fe27c",
            "from_cache": False, "elapsed_s": 4.02, "protein_atom_count": 2752,
            "evidence_ids": [cr.diffdock_evidence_id(request_sha, i + 1) for i in range(3)],
            "errors": []}


def _diffdock_fixture_b() -> dict:
    """경로 B DiffDock 실측. 1순위 신뢰도가 음수다."""
    confs = list(DIFFDOCK_BODY_B["position_confidence"])
    return {"step": "diffdock", "ok": True, "skipped": False, "skip_reason": None,
            "num_poses_returned": 3, "position_confidence": confs,
            "poses": [{"rank": i + 1, "position_confidence": c,
                       "evidence_id": cr.diffdock_evidence_id(DIFFDOCK_REQUEST_SHA_B, i + 1)}
                      for i, c in enumerate(confs)],
            "request_sha256": DIFFDOCK_REQUEST_SHA_B,
            "response_sha256": DIFFDOCK_RESPONSE_SHA_B,
            "from_cache": True, "elapsed_s": 0.0, "protein_atom_count": 1853,
            "evidence_ids": [cr.diffdock_evidence_id(DIFFDOCK_REQUEST_SHA_B, i + 1)
                             for i in range(3)],
            "errors": []}


def _label_fixture() -> dict:
    return {"step": "label", "ok": True, "setid": cr.ZEJULA_SETID, "labeled": True,
            "title": "ZEJULA (niraparib) tablets, for oral use",
            "mentioned_sections": ["adverse_reactions", "warnings_and_precautions"],
            "mention_count": 6, "snippet": "... including thrombocytopenia, anemia ...",
            "pk": {"ok": True, "section_code": cr.PK_SECTION_CODE,
                   "section_number": cr.PK_SECTION_NUMBER, "text_length": 3069,
                   "values": {"half_life_hours": 50.0, "bioavailability_percent": 73.0,
                              "plasma_protein_binding_percent": 83.0, "cmax_ng_ml": 603.0},
                   "snippets": {}, "errors": []},
            "pk_evidence_ids": [cr.dailymed_evidence_id(cr.ZEJULA_SETID, cr.PK_SECTION_NUMBER)],
            "event_evidence_ids": [cr.dailymed_evidence_id(cr.ZEJULA_SETID, "5"),
                                   cr.dailymed_evidence_id(cr.ZEJULA_SETID, "6")],
            "evidence_ids": [cr.dailymed_evidence_id(cr.ZEJULA_SETID, cr.PK_SECTION_NUMBER),
                             cr.dailymed_evidence_id(cr.ZEJULA_SETID, "5"),
                             cr.dailymed_evidence_id(cr.ZEJULA_SETID, "6")],
            "errors": []}


def _faers_fixture() -> dict:
    metrics = disproportionality(FAERS_COUNTS["a"], FAERS_COUNTS["b"],
                                 FAERS_COUNTS["c"], FAERS_COUNTS["d"])
    return {"step": "faers", "ok": True, "drug": cr.COMPOUND_ID, "event": cr.ADVERSE_EVENT,
            "counts": dict(FAERS_COUNTS), **metrics, "data_last_updated": "2026-07-30",
            "evidence_ids": [cr.faers_evidence_id()], "errors": []}


def _pubmed_fixture() -> dict:
    return {"step": "pubmed", "ok": True, "term": 'niraparib AND "Thrombocytopenia"',
            "total_count": 92, "pmids": ["40687421"],
            "articles": [{"pmid": "40687421", "year": 2025,
                          "title": "Severe thrombocytopenia induced by niraparib in ovarian "
                                   "cancer patients: a case report and literature review.",
                          "journal": "Frontiers in pharmacology"}],
            "representative_pmid": "40687421",
            "representative_title": "Severe thrombocytopenia induced by niraparib in ovarian "
                                    "cancer patients: a case report and literature review.",
            "evidence_ids": [cr.pubmed_evidence_id("40687421")], "errors": []}


def case_fixture(diffdock_ok: bool = True, use_vina: bool = True) -> dict:
    """두 경로가 담긴 케이스 한 벌. 단계 계산은 실제 함수로 하고 나머지는 실측 픽스처다.

    ``use_vina=False`` 는 ``--no-vina`` 실행을 흉내 낸다. Vina 단계는 실행 코드와 같은
    ``cr.vina_skip_step()`` 을 쓰고, 결합 근거가 DiffDock 하나로 줄므로 경로 B 에도 실측
    DiffDock 값을 둔다.
    """
    docking, evidence = _docking_fixture(), _evidence_fixture()
    paths = []
    for spec, atoms, digest in ((cr.PATH_A, 2752, ATOM_SHA_A), (cr.PATH_B, 1853, ATOM_SHA_B)):
        if spec.key == "A":
            diffdock = _diffdock_fixture(diffdock_ok)
        elif use_vina:
            diffdock = _diffdock_fixture(False)
        else:
            diffdock = _diffdock_fixture_b() if diffdock_ok else _diffdock_fixture(False)
        steps = {
            "structure": _structure_fixture(spec.pdb_id, spec.chain, atoms, digest),
            "vina": cr.step_vina(spec, docking) if use_vina else cr.vina_skip_step(),
            "diffdock": diffdock,
            "bindingdb": cr.step_bindingdb(spec, evidence),
            "label": _label_fixture(),
            "faers": _faers_fixture(),
            "pubmed": _pubmed_fixture(),
        }
        ids: list[str] = []
        for step in steps.values():
            for eid in step.get("evidence_ids") or []:
                if eid not in ids:
                    ids.append(eid)
        paths.append({**spec.as_dict(), "steps": steps, "evidence_ids": ids, "errors": {}})
    return {"case_id": "case_niraparib", "generated_at": "2026-09-25T00:00:00+00:00",
            "offline": True, "use_vina": use_vina,
            "compound": {"id": cr.COMPOUND_ID, "name": cr.COMPOUND_NAME,
                         "smiles": cr.COMPOUND_SMILES, "adverse_event": cr.ADVERSE_EVENT,
                         "adverse_event_ko": cr.ADVERSE_EVENT_KO},
            "sources": {}, "fddd_notes": DOCKING_DOC["notes"], "paths": paths}


# --------------------------------------------------------------------------------------
# 1. 근거 ID
# --------------------------------------------------------------------------------------
def test_evidence_id_formats():
    assert cr.rcsb_evidence_id("4r6e", "A", ATOM_SHA_A) == "rcsb:4R6E:chainA:29087205"
    assert cr.vina_evidence_id(LOG_SHA_A) == "dock:vina:3fe4e8bb"
    assert cr.bindingdb_evidence_id("p09874") == "bindingdb:P09874"
    assert (cr.dailymed_evidence_id(cr.ZEJULA_SETID, "12.3")
            == f"dailymed:setid:{cr.ZEJULA_SETID}:section:12.3")
    assert cr.faers_evidence_id() == "faers:2x2:niraparib-thrombocytopenia"
    assert cr.faers_evidence_id("drug X", "Lactic acidosis") == "faers:2x2:drug x-lactic_acidosis"
    assert cr.pubmed_evidence_id(40687421) == "pubmed:40687421"
    assert cr.diffdock_evidence_id(ATOM_SHA_A, 2) == "dock:diffdock:29087205:pose2"


def test_sha8_rejects_short_input():
    with pytest.raises(ValueError):
        cr.sha8("abc")


# --------------------------------------------------------------------------------------
# 2. 단계
# --------------------------------------------------------------------------------------
def test_step_structure_uses_injected_fetch(monkeypatch, tmp_path):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(cr, "http_get", lambda url, **kw: PDB_SAMPLE)
    out = cr.step_structure(cr.PATH_A)
    assert out["ok"] is True
    assert out["atom_count_total"] == 3            # HETATM 과 END 는 세지 않는다
    assert out["atom_count_chain"] == 2            # chain A 만 남긴다
    assert out["chains_present"] == ["A", "B"]
    assert out["evidence_ids"][0].startswith("rcsb:4R6E:chainA:")
    assert out["_atom_text"].count("ATOM") == 2


def test_step_structure_records_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(cr, "http_get", lambda url, **kw: {"__error__": 503, "body": "down"})
    out = cr.step_structure(cr.PATH_B)
    assert out["ok"] is False and out["evidence_ids"] == []
    assert out["errors"] == ["rcsb_fetch_failed:503"]


def test_step_vina_reads_fddd_values():
    a = cr.step_vina(cr.PATH_A, _docking_fixture())
    assert a["ok"] is True
    assert a["score_kcal_mol"] == -10.178 and a["units"] == "kcal/mol"
    assert a["role"] == "co-crystal redocking control"
    assert a["protocol"]["seed"] == 20260914 and a["protocol"]["exhaustiveness"] == 4
    assert a["protocol"]["box_center"] == [-39, 5, -8]
    assert a["sha256"]["log"] == LOG_SHA_A
    assert a["evidence_ids"] == ["dock:vina:3fe4e8bb"]

    b = cr.step_vina(cr.PATH_B, _docking_fixture())
    assert b["score_kcal_mol"] == -7.967
    assert b["role"] == "Exploratory cross-docking; no claim of validated binding"
    assert b["evidence_ids"] == ["dock:vina:e3970b3c"]


def test_step_vina_reports_missing_source():
    out = cr.step_vina(cr.PATH_A, {"ok": False, "errors": ["fddd_docking_fetch_failed:503"]})
    assert out["ok"] is False and out["errors"] == ["fddd_docking_fetch_failed:503"]


def test_step_bindingdb_present_for_parp1_absent_for_factor_xa():
    a = cr.step_bindingdb(cr.PATH_A, _evidence_fixture())
    assert a["reference_set_present"] is True
    assert a["record_count"] == 7311 and a["compound_count"] == 5769
    assert a["endpoint_counts"] == {"Ki": 1194, "IC50": 5588, "Kd": 214, "EC50": 315}
    assert a["evidence_ids"] == ["bindingdb:P09874"]
    assert "NOT pooled" in a["endpoint_warning"]

    b = cr.step_bindingdb(cr.PATH_B, _evidence_fixture())
    assert b["ok"] is True and b["reference_set_present"] is False
    assert b["record_count"] is None and b["endpoint_counts"] == {}
    assert "대응하는 참조 집합은 없다" in b["absent_note"]


def test_label_step_separates_pk_and_event_evidence():
    """12.3 절 근거를 이상사례 기재 주장에 붙이지 않는다."""
    label = _label_fixture()
    assert label["pk_evidence_ids"] == [
        cr.dailymed_evidence_id(cr.ZEJULA_SETID, cr.PK_SECTION_NUMBER)]
    assert all(":section:12.3" not in i for i in label["event_evidence_ids"])
    case = case_fixture()
    supported = cr.build_supported_claims(case)
    event_claim = next(c for c in supported["claims"] if "기재되어 있고" in c["text"])
    assert all(":section:12.3" not in i for i in event_claim["evidence_ids"])
    pk_claim = next(c for c in supported["claims"] if "반감기" in c["text"])
    assert pk_claim["evidence_ids"] == [
        cr.dailymed_evidence_id(cr.ZEJULA_SETID, cr.PK_SECTION_NUMBER)]


def test_step_diffdock_skips_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    structure = {**_structure_fixture("4R6E", "A", 2752, ATOM_SHA_A),
                 "_atom_text": PDB_SAMPLE}
    out = cr.step_diffdock(cr.PATH_A, structure)
    assert out["skipped"] is True and out["ok"] is False
    assert "NVIDIA_API_KEY" in out["skip_reason"]
    assert out["evidence_ids"] == []


def test_step_diffdock_parses_injected_response(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))

    def fake_post(url, payload, timeout=None, **kw):
        return bc.NimResponse(status=200, body=DIFFDOCK_BODY, headers={"nvcf-status": "fulfilled"},
                              url=url, request_sha256=bc.payload_sha256(payload),
                              response_sha256=bc.sha256_text(bc.canonical_json(DIFFDOCK_BODY)),
                              elapsed_s=4.02)

    structure = {**_structure_fixture("4R6E", "A", 2, ATOM_SHA_A), "_atom_text": PDB_SAMPLE}
    out = cr.step_diffdock(cr.PATH_A, structure, post=fake_post)
    assert out["ok"] is True and out["num_poses_returned"] == 3
    assert out["position_confidence"] == DIFFDOCK_BODY["position_confidence"]
    assert len(out["evidence_ids"]) == 3
    assert out["evidence_ids"][0].endswith(":pose1")
    assert out["request_sha256"] and out["response_sha256"]
    assert "시드" in out["reproducibility_note"]


def test_step_diffdock_skips_when_structure_failed():
    out = cr.step_diffdock(cr.PATH_B, {"ok": False, "errors": ["rcsb_fetch_failed:503"]})
    assert out["skipped"] is True and "수용체 구조" in out["skip_reason"]


# --------------------------------------------------------------------------------------
# 3. 오프라인 경로
# --------------------------------------------------------------------------------------
def test_cache_only_get_reports_miss(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    from harness.tools.pharmasignal_common import ResponseCache
    cache = ResponseCache("rcsb", "TEST")
    out = cr.cache_only_get("https://example.invalid/x", cache=cache)
    assert out == {"__error__": cr.OFFLINE_MISS, "body": "https://example.invalid/x"}
    cache.put("https://example.invalid/x", {"hit": 1})
    assert cr.cache_only_get("https://example.invalid/x", cache=cache) == {"hit": 1}


def test_offline_http_patches_and_restores():
    from harness.tools import pharmasignal_openfda, pharmasignal_pubmed
    original = pharmasignal_openfda.http_get
    with cr.offline_http():
        assert pharmasignal_openfda.http_get is cr.cache_only_get
        assert pharmasignal_pubmed.http_get is cr.cache_only_get
    assert pharmasignal_openfda.http_get is original


def test_cache_only_post_raises_without_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    with pytest.raises(bc.NimError) as exc:
        cr.cache_only_post(cr.dd.DIFFDOCK_URL, {"protein": "ATOM x", "ligand": "C"},
                           cache_source="bionemo_diffdock")
    assert "offline" in str(exc.value)


# --------------------------------------------------------------------------------------
# 4. 주장 두 벌
# --------------------------------------------------------------------------------------
def test_supported_claims_all_carry_evidence():
    case = case_fixture()
    supported = cr.build_supported_claims(case)
    assert len(supported["claims"]) >= 10
    for claim in supported["claims"]:
        assert claim["text"].strip()
        assert claim["evidence_ids"] and all(i.strip() for i in claim["evidence_ids"])
    text = " ".join(c["text"] for c in supported["claims"])
    assert "-10.178" in text and "-7.967" in text
    assert "no claim of validated binding" in text
    assert "교차 타깃으로 보정되지 않았다" in text


def test_overclaim_claims_plant_at_least_three_bad_inferences():
    case = case_fixture()
    overclaim = cr.build_overclaim_claims(case)
    assert len(overclaim["planted_overclaims"]) >= 3
    for claim in overclaim["claims"]:
        assert claim["text"].strip()
        assert claim["evidence_ids"] and all(i.strip() for i in claim["evidence_ids"])
    text = " ".join(c["text"] for c in overclaim["claims"]) + overclaim["summary"]
    assert "선택성" in text                      # 교차 타깃 비교
    assert "Kd" in text                          # 친화도 환산
    assert "항응고" in text                      # 교차 도킹 해석


def test_both_claim_sets_use_the_same_evidence_ids():
    case = case_fixture()
    supported = cr.build_supported_claims(case)
    overclaim = cr.build_overclaim_claims(case)
    used_over = {i for c in overclaim["claims"] for i in c["evidence_ids"]}
    used_ok = {i for c in supported["claims"] for i in c["evidence_ids"]}
    assert used_over <= used_ok, "과잉해석 벌이 새 근거 ID 를 만들어 냈다"


def test_author_output_json_keeps_only_schema_keys():
    case = case_fixture()
    payload = json.loads(cr.author_output_json(cr.build_overclaim_claims(case)))
    assert set(payload) == {"claims", "summary"}
    from harness.schemas import AuthorOutput
    AuthorOutput.model_validate(payload)


# --------------------------------------------------------------------------------------
# 5. 크리틱 3단
# --------------------------------------------------------------------------------------
def test_stage1_cannot_separate_the_two_sets():
    """1단 결정 규칙은 (가)와 (나)를 가르지 못한다. 그것이 이 시연의 요지다."""
    case = case_fixture()
    for payload in (cr.build_supported_claims(case), cr.build_overclaim_claims(case)):
        stage1 = cr.critic_stage1(payload)
        assert stage1["ran"] is True
        assert stage1["rules_passed"] is True
        assert stage1["verdict"] == "needs_human"


def test_stage1_rejects_empty_evidence_id():
    broken = {"claims": [{"text": "근거 없는 주장", "evidence_ids": []}], "summary": "요약"}
    stage1 = cr.critic_stage1(broken)
    assert stage1["rules_passed"] is False
    assert any(c["name"] == "all_claims_have_evidence" and not c["passed"]
               for c in stage1["checks"])


def test_stage2_numeric_oracle_agrees_for_both_sets():
    """2단 숫자 오라클도 (가)와 (나)를 가르지 못한다. 숫자는 양쪽이 같고 전부 맞다."""
    case = case_fixture()
    counts = cr.path_by_key(case, "A")["steps"]["faers"]["counts"]
    for payload in (cr.build_supported_claims(case), cr.build_overclaim_claims(case)):
        stage2 = cr.critic_stage2(payload, counts)
        assert stage2["ran"] is True
        assert stage2["mismatches"] == []
        assert stage2["ok"] is True
        assert stage2["checked"] >= 4


def test_stage2_catches_a_wrong_number():
    counts = dict(FAERS_COUNTS)
    wrong = {"claims": [{"text": "PRR 은 2.00 이다.", "evidence_ids": ["faers:2x2:x-y"]}],
             "summary": ""}
    stage2 = cr.critic_stage2(wrong, counts)
    assert stage2["ok"] is False and stage2["mismatches"]


def test_stage3_skipped_offline():
    case = case_fixture()
    stage3 = cr.critic_stage3(cr.build_overclaim_claims(case), offline=True)
    assert stage3["ran"] is False
    assert "오프라인" in stage3["skip_reason"]
    assert len(stage3["rules"]) >= 13


def test_stage3_skipped_without_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    case = case_fixture()
    stage3 = cr.critic_stage3(cr.build_supported_claims(case))
    assert stage3["ran"] is False and "NVIDIA_API_KEY" in stage3["skip_reason"]


def test_judge_claim_set_offline_ends_in_needs_human(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    case = case_fixture()
    counts = cr.path_by_key(case, "A")["steps"]["faers"]["counts"]
    verdict = cr.judge_claim_set(cr.build_overclaim_claims(case), counts, offline=True)
    assert verdict["final_verdict"] == "needs_human"
    assert verdict["decided_by"].startswith("3단을 돌리지 못해")


def test_judge_claim_set_rejects_on_stage1(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    broken = {"claims": [{"text": "근거 없는 주장", "evidence_ids": []}], "summary": "요약"}
    verdict = cr.judge_claim_set(broken, dict(FAERS_COUNTS), offline=True)
    assert verdict["final_verdict"] == "reject"
    assert verdict["decided_by"] == "1단 결정 규칙"
    assert verdict["reject_reasons"]


# --------------------------------------------------------------------------------------
# 6. 브리프
# --------------------------------------------------------------------------------------
def _brief(case: dict) -> str:
    supported = cr.build_supported_claims(case)
    overclaim = cr.build_overclaim_claims(case)
    counts = cr.path_by_key(case, "A")["steps"]["faers"]["counts"]
    verdicts = {"supported": cr.judge_claim_set(supported, counts, offline=True),
                "overclaim": cr.judge_claim_set(overclaim, counts, offline=True)}
    return cr.render_brief(case, supported, overclaim, verdicts)


def test_render_brief_has_required_sections():
    text = _brief(case_fixture())
    for heading in ("# ", "## 단계별 근거", "## 크리틱 판정 두 벌", "## 말할 수 있는 것",
                    "## 말할 수 없는 것", "## 시사점"):
        assert heading in text
    for row in ("구조", "결합 1 (Vina 실측)", "결합 2 (DiffDock NIM)", "참조 (BindingDB)",
                "사람 1 (DailyMed 라벨)", "사람 2 (FAERS)", "사람 3 (PubMed)"):
        assert f"| {row} |" in text


def test_render_brief_carries_numbers_and_evidence_ids():
    text = _brief(case_fixture())
    assert "-10.178 kcal/mol" in text and "-7.967 kcal/mol" in text
    assert "`dock:vina:3fe4e8bb`" in text and "`dock:vina:e3970b3c`" in text
    assert "`rcsb:4R6E:chainA:29087205`" in text
    assert "`bindingdb:P09874`" in text
    assert "`faers:2x2:niraparib-thrombocytopenia`" in text
    assert "`pubmed:40687421`" in text
    assert "참조 집합 없음" in text
    assert "2.211 kcal/mol" in text


def test_render_brief_has_no_em_dash():
    text = _brief(case_fixture())
    assert "—" not in text


def test_render_brief_states_skipped_diffdock():
    text = _brief(case_fixture(diffdock_ok=False))
    assert "건너뜀" in text
    assert "NVIDIA_API_KEY" in text


def test_brief_table_rows_are_well_formed():
    """표 한 줄에 파이프가 네 개다(양 끝 둘과 칸 구분 둘). 칸 안의 파이프를 막았는지 본다."""
    text = _brief(case_fixture())
    rows = [l for l in text.splitlines() if l.startswith("| ")]
    assert rows
    for row in rows:
        assert row.count("|") == 4, row[:80]


# --------------------------------------------------------------------------------------
# 7. --no-vina 경로. FDDD 도킹 자산을 쓸 수 없게 된 경우를 대비한 경로다.
#    결합 근거가 DiffDock NIM 하나로 줄어도 두 경로 대조는 그대로 선다.
# --------------------------------------------------------------------------------------
def test_vina_skip_step_leaves_no_placeholder_score():
    step = cr.vina_skip_step()
    assert step["skipped"] is True and step["ok"] is False
    assert "score_kcal_mol" not in step          # 건너뛴 값을 0 이나 빈 값으로 채우지 않는다
    assert "--no-vina" in step["skip_reason"]
    assert step["evidence_ids"] == []
    assert cr.vina_skipped(step) is True


def test_vina_skipped_tells_a_skip_from_a_failure():
    """조회 실패는 건너뜀이 아니다. 실패한 단계에는 점수 키가 None 으로 남아 있다."""
    failed = cr.step_vina(cr.PATH_A, {"ok": False, "errors": ["fddd_docking_fetch_failed:503"]})
    assert failed["score_kcal_mol"] is None
    assert cr.vina_skipped(failed) is False
    assert cr.case_uses_vina(case_fixture()) is True
    assert cr.case_uses_vina(case_fixture(use_vina=False)) is False


def test_no_vina_builds_both_claim_sets_without_vina_numbers():
    case = case_fixture(use_vina=False)
    supported = cr.build_supported_claims(case)
    overclaim = cr.build_overclaim_claims(case)
    assert len(supported["claims"]) == 12        # Vina 주장 넷이 빠지고 경로 B DiffDock 셋이 온다
    assert len(overclaim["claims"]) == 7
    for payload in (supported, overclaim):
        for claim in payload["claims"]:
            assert claim["text"].strip()
            assert claim["evidence_ids"] and all(i.strip() for i in claim["evidence_ids"])
            assert all(not i.startswith("dock:vina") for i in claim["evidence_ids"])
    text = " ".join(c["text"] for c in supported["claims"] + overclaim["claims"])
    text += supported["summary"] + overclaim["summary"]
    assert "kcal/mol" not in text
    assert "-10.178" not in text and "-7.967" not in text
    assert "0.761" in text and "-0.172" in text  # 실제로 받은 DiffDock 값이다


def test_no_vina_overclaims_are_rebuilt_on_diffdock_confidence():
    case = case_fixture(use_vina=False)
    overclaim = cr.build_overclaim_claims(case)
    assert len(overclaim["planted_overclaims"]) >= 3
    text = " ".join(c["text"] for c in overclaim["claims"]) + overclaim["summary"]
    assert "선택성" in text                      # 교차 타깃 순위
    assert "Kd" in text                          # 친화도 환산
    assert "항응고" in text                      # 음수 신뢰도를 비결합으로 읽기
    ids = {i for c in overclaim["claims"] for i in c["evidence_ids"]}
    assert "dock:diffdock:f31b513b:pose1" in ids
    assert f"dock:diffdock:{DIFFDOCK_REQUEST_SHA_B[:8]}:pose1" in ids
    supported_ids = {i for c in cr.build_supported_claims(case)["claims"]
                     for i in c["evidence_ids"]}
    assert ids <= supported_ids, "과잉해석 벌이 새 근거 ID 를 만들어 냈다"


def test_no_vina_claim_sets_pass_stage1_and_stage2(monkeypatch):
    """1단과 2단을 통과해야 3단 과잉해석 판정의 시연 가치가 남는다."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    case = case_fixture(use_vina=False)
    counts = cr.path_by_key(case, "A")["steps"]["faers"]["counts"]
    for payload in (cr.build_supported_claims(case), cr.build_overclaim_claims(case)):
        stage1 = cr.critic_stage1(payload)
        assert stage1["ran"] is True and stage1["rules_passed"] is True
        assert stage1["verdict"] == "needs_human"
        stage2 = cr.critic_stage2(payload, counts)
        assert stage2["ran"] is True and stage2["ok"] is True
        assert stage2["mismatches"] == [] and stage2["checked"] >= 4
        verdict = cr.judge_claim_set(payload, counts, offline=True)
        assert verdict["final_verdict"] == "needs_human"


def test_no_vina_brief_renders_vina_row_as_skipped():
    text = _brief(case_fixture(use_vina=False))
    vina_row = next(l for l in text.splitlines() if l.startswith("| 결합 1 (Vina 실측) |"))
    assert "건너뜀" in vina_row and "--no-vina" in vina_row
    assert "Vina 건너뜀(--no-vina)" in text
    assert "kcal/mol" not in text                # 점수 차이 문구를 쓰지 않는다
    assert "0.761" in text and "-0.172" in text
    assert "AutoDock Vina 결과를 이 실행의 근거로 말하는 것" in text
    assert "—" not in text
    for row in [l for l in text.splitlines() if l.startswith("| ")]:
        assert row.count("|") == 4, row[:80]


def test_no_vina_brief_keeps_the_two_path_contrast():
    text = _brief(case_fixture(use_vina=False))
    tail = text.split("## 시사점", 1)[1]
    assert "실험 근거가 있는지다" in tail
    assert "kcal/mol" not in tail


def test_use_vina_path_is_untouched_by_the_no_vina_branch():
    """기존 경로의 산출물이 그대로인지 못 박는다. 이 수치가 바뀌면 회귀다."""
    case = case_fixture()
    supported = cr.build_supported_claims(case)
    overclaim = cr.build_overclaim_claims(case)
    assert len(supported["claims"]) == 14
    assert len(overclaim["claims"]) == 7 and len(overclaim["planted_overclaims"]) == 7
    assert "Vina 점수 하나만" in supported["summary"]
    text = _brief(case)
    assert "점수 차이는 2.211 kcal/mol" in text
    assert "-10.178 kcal/mol" in text and "-7.967 kcal/mol" in text
    assert "포즈 사이 RMSD" in text
    assert "--no-vina" not in text and "건너뜀(--no-vina)" not in text


# --------------------------------------------------------------------------------------
# 8. 네트워크 (기본 실행에서 제외)
# --------------------------------------------------------------------------------------
@pytest.mark.network
def test_fddd_manifest_still_reports_the_documented_scores():
    docking = cr.fetch_fddd_docking(use_cache=False)
    assert docking["ok"], docking.get("errors")
    a = cr.step_vina(cr.PATH_A, docking)
    b = cr.step_vina(cr.PATH_B, docking)
    assert a["score_kcal_mol"] == -10.178
    assert b["score_kcal_mol"] == -7.967
    assert b["role"] == "Exploratory cross-docking; no claim of validated binding"
