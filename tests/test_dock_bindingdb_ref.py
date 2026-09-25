"""dock_bindingdb_ref 오프라인 테스트. 네트워크도 API 키도 쓰지 않는다.

실행: .venv/bin/python -m pytest tests/test_dock_bindingdb_ref.py -q -m "not network"

픽스처는 2026-09-25 에 받아 둔 FDDD ``evidence/summary.json`` 의 ``bindingdb`` 블록 실측값이다
(캐시 파일 ``eval/results/pharmasignal_cache_fddd_dae2fd5150a8.json``). 건수와 경고 문장은 원값 그대로다.

도구 모듈은 반드시 패키지 경로로 import 한다(docs/TROUBLESHOOTING.md 8번).
"""

from __future__ import annotations

import inspect
import json

import pytest

from harness.tools import dock_bindingdb_ref as bd

WARNING_VERBATIM = (
    "Ki, Kd, IC50 and EC50 are distinct endpoints and are NOT pooled into one affinity score.")
BINDINGDB_QUERY_URL = ("https://www.bindingdb.org/rest/getLigandsByUniprots"
                       "?uniprot=P09874&cutoff=10000&response=application/json")

EVIDENCE_FIXTURE = {
    "capturedAt": "2026-09-14T19:09:16.499Z",
    "bindingdb": {
        "sourceUrl": BINDINGDB_QUERY_URL,
        "target": "Human PARP1 / UniProt P09874",
        "recordCount": 7311,
        "compoundCount": 5769,
        "counts": {"Ki": 1194, "IC50": 5588, "Kd": 214, "EC50": 315},
        "rawPath": "/data/evidence/bindingdb-parp1-raw.json",
        "filter": ("API affinity cutoff10000nM. This is a filtered reference set, not the "
                   "complete database or an unbiased negative set."),
        "warning": WARNING_VERBATIM + " Not used as the DOCKSTRING training labels.",
    },
    "pharmacokinetics": [{"compoundId": "niraparib", "name": "Niraparib", "halfLifeHours": 50}],
}


def _getter(doc=None, error=None):
    """``pharmasignal_common.http_get`` 자리에 끼우는 가짜 GET. 네트워크를 타지 않는다."""
    def get(url, cache=None, is_json=True, **_kwargs):
        return error if error is not None else (EVIDENCE_FIXTURE if doc is None else doc)
    return get


# --------------------------------------------------------------------------------------
# 근거 ID 와 UniProt 파싱
# --------------------------------------------------------------------------------------
def test_evidence_id_format():
    assert bd.evidence_id("P09874") == "bindingdb:P09874"
    assert bd.evidence_id("p09874") == "bindingdb:P09874"
    with pytest.raises(ValueError):
        bd.evidence_id("")


def test_uniprot_is_read_from_the_captured_query_url():
    assert bd.parse_uniprot(BINDINGDB_QUERY_URL) == "P09874"
    assert bd.parse_uniprot("https://example.org/no-uniprot") == ""


# --------------------------------------------------------------------------------------
# 참조 집합이 있는 경로
# --------------------------------------------------------------------------------------
def test_present_reference_set_reports_counts_and_ids():
    r = bd.parse_bindingdb_block(EVIDENCE_FIXTURE, "PARP1")
    assert r.tool == "bindingdb_ref"
    assert r.reference_set_present is True
    assert r.target == "Human PARP1 / UniProt P09874"
    assert r.uniprot == "P09874"
    assert r.record_count == 7311 and r.compound_count == 5769
    assert r.evidence_ids == ["bindingdb:P09874"]
    assert r.captured_at == "2026-09-14T19:09:16.499Z"
    assert r.source_query_url == BINDINGDB_QUERY_URL
    assert r.absent_note is None
    assert r.errors == []


@pytest.mark.parametrize("target", ["PARP1", "parp1", "parp-1", "P09874", "4R6E",
                                    "parp1-4r6e-chain-a", "Human PARP1"])
def test_target_aliases_resolve_to_the_parp1_reference_set(target):
    assert bd.parse_bindingdb_block(EVIDENCE_FIXTURE, target).reference_set_present is True


def test_endpoint_counts_stay_separated():
    """종점 4종은 별개다. 합계 필드를 두지 않고 값도 합치지 않는다."""
    r = bd.parse_bindingdb_block(EVIDENCE_FIXTURE, "P09874")
    counts = r.endpoint_counts
    assert (counts.Ki, counts.IC50, counts.Kd, counts.EC50) == (1194, 5588, 214, 315)
    dumped = json.loads(r.model_dump_json())
    assert dumped["endpoint_counts"] == {"Ki": 1194, "IC50": 5588, "Kd": 214, "EC50": 315}
    # 합계나 평균 필드가 생기면 종점 혼합을 도구가 먼저 저지르는 셈이 된다.
    for banned in ("total", "sum", "pooled", "affinity", "mean"):
        assert not any(banned in key.lower() for key in dumped["endpoint_counts"])
        assert not any(banned in key.lower() for key in dumped if key != "source_query_url")
    # 네 종점 합(7,311)이 record_count 와 같아도 record_count 는 FDDD 가 적은 값이다.
    assert counts.Ki + counts.IC50 + counts.Kd + counts.EC50 == 7311
    assert bd.ENDPOINTS == ("Ki", "IC50", "Kd", "EC50")


def test_endpoint_warning_is_carried_verbatim():
    r = bd.parse_bindingdb_block(EVIDENCE_FIXTURE, "PARP1")
    assert WARNING_VERBATIM in r.endpoint_warning
    assert WARNING_VERBATIM == bd.ENDPOINT_WARNING


def test_filter_note_says_the_set_is_not_complete():
    r = bd.parse_bindingdb_block(EVIDENCE_FIXTURE, "PARP1")
    assert "not the complete database" in (r.filter_note or "")
    assert r.raw_path == "/data/evidence/bindingdb-parp1-raw.json"


# --------------------------------------------------------------------------------------
# 참조 집합이 없는 경로. 케이스 시연에서 두 경로를 가르는 지점이다.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("target", ["factor-xa-2p16", "2P16", "factor Xa", "COX-2", "3LN1"])
def test_absent_reference_set_is_reported_as_absent(target):
    r = bd.parse_bindingdb_block(EVIDENCE_FIXTURE, target)
    assert r.reference_set_present is False
    assert r.record_count is None and r.compound_count is None
    assert r.absent_note and "집합은 없다" in r.absent_note
    assert r.available_reference_sets == ["Human PARP1 / UniProt P09874"]


def test_absent_case_does_not_borrow_the_other_targets_counts():
    r = bd.parse_bindingdb_block(EVIDENCE_FIXTURE, "2P16")
    counts = r.endpoint_counts.model_dump()
    assert set(counts) == {"Ki", "IC50", "Kd", "EC50"}
    assert all(v is None for v in counts.values())      # 0 이 아니라 None 이다
    assert "0 으로 읽지 말고" in (r.absent_note or "")


def test_missing_block_is_an_error_not_an_empty_set():
    r = bd.parse_bindingdb_block({"capturedAt": "2026-09-14T19:09:16.499Z"}, "PARP1")
    assert r.reference_set_present is False
    assert r.errors == ["bindingdb_block_missing"]
    assert r.uniprot is None


def test_fetch_failure_is_reported_not_filled_in():
    r = bd.lookup("PARP1", use_cache=False, getter=_getter(error={"__error__": "network: boom"}))
    assert r.reference_set_present is False
    assert r.errors == ["fddd_evidence_fetch_failed:network: boom"]
    assert r.record_count is None


def test_uniprot_missing_from_query_url_is_flagged():
    doc = json.loads(json.dumps(EVIDENCE_FIXTURE))
    doc["bindingdb"]["sourceUrl"] = "https://www.bindingdb.org/rest/getLigandsByUniprots"
    r = bd.parse_bindingdb_block(doc, "PARP1")
    assert "uniprot_not_found_in_source_url" in r.errors
    assert r.evidence_ids == []                      # 없는 ID 를 만들지 않는다
    assert r.reference_set_present is True            # 타깃 표기로는 여전히 같은 집합이다


# --------------------------------------------------------------------------------------
# 출처 고지: bindingdb.org 를 직접 부르지 않는다
# --------------------------------------------------------------------------------------
def test_result_says_it_reads_the_fddd_capture_not_bindingdb():
    r = bd.parse_bindingdb_block(EVIDENCE_FIXTURE, "PARP1")
    assert r.direct_bindingdb_call is False
    assert r.url == "https://drug.flybrain.kr/data/evidence/summary.json"
    assert "직접 부르지 않는다" in r.source_note
    assert "FDDD" in r.source


def test_docstring_states_the_source_and_the_endpoint_rule_for_the_llm():
    source = inspect.getsource(bd)
    assert "does NOT call bindingdb.org" in source
    assert WARNING_VERBATIM in source
    assert "Never add the four counts together" in source
    assert "neither the complete database" in source
    assert "Absence of a record is not evidence of no binding" in source


def test_lookup_passes_through_the_injected_getter():
    r = bd.lookup("P09874", use_cache=False, getter=_getter())
    assert r.reference_set_present is True and r.evidence_ids == ["bindingdb:P09874"]


def test_config_name_and_defaults():
    cfg = bd.BindingDbRefConfig()
    assert bd.BindingDbRefConfig.static_type() == "bindingdb_ref"
    assert cfg.url == "https://drug.flybrain.kr/data/evidence/summary.json"
    assert cfg.use_cache is True


def test_result_serializes_to_str_for_console():
    payload = json.loads(bd.parse_bindingdb_block(EVIDENCE_FIXTURE, "PARP1").model_dump_json())
    assert payload["tool"] == "bindingdb_ref"
    assert payload["reference_set_present"] is True
    assert payload["endpoint_counts"]["Ki"] == 1194
    assert WARNING_VERBATIM in payload["endpoint_warning"]


# --------------------------------------------------------------------------------------
# 네트워크 (기본 실행에서 건너뛴다)
# --------------------------------------------------------------------------------------
@pytest.mark.network
def test_live_fddd_evidence_lookup():
    present = bd.lookup("PARP1")
    assert present.reference_set_present is True
    assert present.uniprot == "P09874"
    assert present.endpoint_counts.Ki == 1194 and present.endpoint_counts.IC50 == 5588
    assert WARNING_VERBATIM in present.endpoint_warning
    absent = bd.lookup("factor-xa-2p16")
    assert absent.reference_set_present is False
