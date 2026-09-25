"""과잉해석 규칙 모듈 단위 테스트. 네트워크와 모델 호출 없음.

재는 것은 셋이다. 규칙 자체의 정합(개수, 중복, 출처, 강도), 규칙이 실제로 프롬프트에 실렸는지
(케이스 러너 3단과 configs/eval.yml), 그리고 평가 케이스가 규칙마다 통과와 반려를 한 쌍씩 갖추고
부정 케이스가 1단 결정 규칙을 통과하는지다.
"""

import json
import os
from pathlib import Path

import pytest

from harness.tools import overclaim_rules as ocr
from harness.tools.overclaim_rules import RULES
from harness.tools.overclaim_rules import SOURCES
from harness.tools.overclaim_rules import STRENGTHS
from harness.tools.overclaim_rules import TABLE_RULE_IDS

ROOT = Path(__file__).parents[1]


# --------------------------------------------------------------------------------------
# 규칙 자체
# --------------------------------------------------------------------------------------
def test_rule_count_is_table_fourteen_plus_evidence_scope():
    """docs/notes/topic-decision.md 표 14종 + case_runner 가 쓰고 있던 근거 범위 준수 1종."""
    assert len(TABLE_RULE_IDS) == 14
    assert len(RULES) == 15
    assert set(TABLE_RULE_IDS) < set(ocr.rule_ids())
    assert set(ocr.rule_ids()) - set(TABLE_RULE_IDS) == {"evidence_scope"}


def test_rule_ids_are_unique_and_ordered_as_defined():
    ids = ocr.rule_ids()
    assert len(set(ids)) == len(ids), f"중복 id: {[i for i in ids if ids.count(i) > 1]}"
    assert ids[0] == "cross_target_ranking" and ids[-1] == "evidence_scope"
    assert set(ocr.RULES_BY_ID) == set(ids)


def test_every_rule_has_source_and_quote_from_the_allowed_three():
    """출처는 셋 중 하나이고 원문 인용이나 경로가 함께 있어야 한다. 지어낸 출처를 막는다."""
    for rule in RULES:
        assert rule.source in SOURCES, f"{rule.id}: 허용되지 않은 출처 {rule.source!r}"
        assert len(rule.source_quote) >= 20, f"{rule.id}: 출처 인용이 비었거나 너무 짧다"


def test_every_rule_strength_is_graded_or_explicitly_ungraded():
    for rule in RULES:
        assert rule.strength in STRENGTHS, f"{rule.id}: 알 수 없는 강도 {rule.strength!r}"
        assert rule.strength_note, f"{rule.id}: 강도 근거가 비었다"


def test_paper_plan_graded_rules_match_the_table():
    """docs/notes/paper-plan.md 의 강도 표 5줄이 그대로 들어왔는지."""
    expected = {
        "cross_target_ranking": ocr.STRENGTH_STRONG,
        "diffdock_confidence_affinity": ocr.STRENGTH_VERY_STRONG,
        "cross_docking_binding": ocr.STRENGTH_WEAK,
        "endpoint_merge": ocr.STRENGTH_MEDIUM,
        "convergence_claim": ocr.STRENGTH_MEDIUM,
        "diffdock_reproducibility": ocr.STRENGTH_MEDIUM,
    }
    for rule_id, strength in expected.items():
        assert ocr.get_rule(rule_id).strength == strength


def test_reject_conditions_are_concrete_not_advisory():
    """\"주의하라\" 가 아니라 무엇을 하면 반려인지 적혀 있어야 한다."""
    for rule in RULES:
        assert "반려" in rule.reject_when, f"{rule.id}: 반려 조건이 아니다"
        assert len(rule.reject_when) >= 60, f"{rule.id}: 반려 조건이 너무 짧다"
        assert "주의하라" not in rule.reject_when


def test_get_rule_raises_for_unknown_id():
    with pytest.raises(KeyError):
        ocr.get_rule("no_such_rule")


# --------------------------------------------------------------------------------------
# 프롬프트 배선
# --------------------------------------------------------------------------------------
def test_prompt_contains_every_rule_line_and_the_json_contract():
    prompt = ocr.stage3_prompt()
    for rule in RULES:
        assert rule.prompt_line() in prompt, f"{rule.id}: 프롬프트에 실리지 않았다"
    assert prompt.count("verdict") >= 2
    assert ocr.numbered_rules_block().splitlines()[0].startswith("1. ")


def test_eval_variant_prompt_drops_the_numeric_oracle_claim():
    """nat eval 경로에는 2단 숫자 오라클이 없다. 있다고 적으면 안 된다."""
    eval_prompt = ocr.stage3_prompt(numbers_verified=False)
    assert "every number in the text was recomputed" not in eval_prompt
    assert "arithmetic" in eval_prompt
    assert "every number in the text was recomputed" in ocr.stage3_prompt()


def test_case_runner_uses_this_module_as_the_single_source():
    from harness.tools import case_runner

    assert case_runner._STAGE3_RULES == ocr.rule_lines()
    assert case_runner._STAGE3_PROMPT == ocr.stage3_prompt(numbers_verified=True)


def test_eval_config_system_prompt_equals_module_output():
    """configs/eval.yml 의 블록 스칼라가 모듈 출력과 한 글자도 다르지 않아야 한다."""
    os.environ.setdefault("NVIDIA_API_KEY", "nvapi-dummy-for-schema-load")
    from nat.runtime.loader import load_config

    cfg = load_config(ROOT / "configs" / "eval.yml")
    assert cfg.workflow.system_prompt == ocr.stage3_prompt(numbers_verified=False)


# --------------------------------------------------------------------------------------
# 평가 케이스
# --------------------------------------------------------------------------------------
def _cases() -> list[dict]:
    text = (ROOT / "eval" / "cases.jsonl").read_text()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_every_rule_has_one_pass_case_and_one_reject_case():
    by_id = {c["id"]: c for c in _cases()}
    for rule in RULES:
        reject, passing = by_id.get(f"{rule.id}_reject"), by_id.get(f"{rule.id}_pass")
        assert reject is not None and passing is not None, f"{rule.id}: 케이스 쌍이 없다"
        assert reject["expected_verdict"] == "reject"
        assert passing["expected_verdict"] == "pass"


def test_case_notes_say_which_stage_should_catch_it():
    for case in _cases():
        assert any(token in case["note"] for token in ("1단", "2단", "3단")), case["id"]


def test_pharmacovigilance_cases_are_kept():
    ids = {c["id"] for c in _cases()}
    assert {"prr_signal_ok", "label_listed_ok", "planted_unsupported_claim"} <= ids
