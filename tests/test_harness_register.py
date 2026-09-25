"""공통 하네스 단위 테스트: PRR/ROR 수치, 스키마 직렬화, 크리틱 결정 규칙, 평가기 점수. 네트워크 없음."""

import json
import math

import pytest

from harness.critic import deterministic_checks
from harness.critic import judge_offline
from harness.critic import extract_json_object
from harness.critic import parse_author_output
from harness.critic import parse_critic_report
from harness.evaluators import extract_verdict
from harness.evaluators import score_item
from harness.register import compute_prr_ror
from harness.schemas import AuthorOutput
from harness.schemas import Check
from harness.schemas import Claim
from harness.schemas import CriticReport


# --------------------------------------------------------------------------------------
# prr_calculator
# --------------------------------------------------------------------------------------
def test_prr_ror_reference_values():
    r = compute_prr_ror(a=40, b=960, c=200, d=98800)
    expected_prr = (40 / 1000) / (200 / 99000)
    expected_ror = (40 * 98800) / (960 * 200)
    assert math.isclose(r.prr, expected_prr, rel_tol=1e-12)
    assert math.isclose(r.prr, 19.8, rel_tol=1e-12)
    assert math.isclose(r.ror, expected_ror, rel_tol=1e-12)
    assert r.prr_ci95[0] < r.prr < r.prr_ci95[1]
    assert r.ror_ci95[0] < r.ror < r.ror_ci95[1]
    assert r.signal_prr_rule is True
    assert r.evidence_id == "calc:prr:40-960-200-98800"


def test_prr_ci_matches_lognormal_formula():
    a, b, c, d = 40, 960, 200, 98800
    r = compute_prr_ror(a, b, c, d)
    se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    assert math.isclose(r.prr_ci95[0], math.exp(math.log(r.prr) - 1.96 * se), rel_tol=1e-12)
    assert math.isclose(r.prr_ci95[1], math.exp(math.log(r.prr) + 1.96 * se), rel_tol=1e-12)


def test_prr_no_signal_when_below_threshold():
    r = compute_prr_ror(a=5, b=995, c=500, d=98500)
    assert r.prr < 2
    assert r.signal_prr_rule is False


@pytest.mark.parametrize("cell", [dict(a=0, b=1, c=1, d=1), dict(a=1, b=0, c=1, d=1), dict(a=1, b=1, c=1, d=-1)])
def test_prr_rejects_zero_or_negative_cells(cell):
    with pytest.raises(ValueError):
        compute_prr_ror(**cell)


def test_prr_result_serializes_to_json():
    payload = compute_prr_ror(40, 960, 200, 98800).model_dump_json()
    data = json.loads(payload)
    assert set(data) >= {"prr", "ror", "prr_ci95", "ror_ci95", "chi_square", "evidence_id"}


# --------------------------------------------------------------------------------------
# schemas
# --------------------------------------------------------------------------------------
def test_author_output_roundtrip():
    author = AuthorOutput(claims=[Claim(text="PRR 19.8", evidence_ids=["calc:prr:40-960-200-98800"])],
                          summary="시그널")
    dumped = author.model_dump_json()
    assert AuthorOutput.model_validate_json(dumped) == author


def test_critic_report_roundtrip_and_verdict_literal():
    report = CriticReport(verdict="reject",
                          checks=[Check(name="all_claims_have_evidence", passed=False, reason="idx [1]")],
                          required_followups=["근거 추가"])
    assert CriticReport.model_validate_json(report.model_dump_json()) == report
    with pytest.raises(ValueError):
        CriticReport(verdict="maybe")  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------
# critic 결정 규칙
# --------------------------------------------------------------------------------------
def test_parse_author_output_rejects_bad_json():
    author, check = parse_author_output("{not json")
    assert author is None and check.name == "schema_valid" and check.passed is False


def test_deterministic_checks_flag_missing_evidence():
    author = AuthorOutput(claims=[Claim(text="ok", evidence_ids=["x:1"]), Claim(text="unsupported", evidence_ids=[])],
                          summary="s")
    by_name = {c.name: c for c in deterministic_checks(author)}
    assert by_name["all_claims_have_evidence"].passed is False
    assert "[1]" in by_name["all_claims_have_evidence"].reason


def test_judge_offline_rejects_planted_case_and_holds_good_case():
    good = AuthorOutput(claims=[Claim(text="PRR 19.8", evidence_ids=["calc:prr:40-960-200-98800"])],
                        summary="시그널").model_dump_json()
    planted = AuthorOutput(claims=[Claim(text="문헌 3편이 인과관계를 확정", evidence_ids=[])],
                           summary="라벨 개정 권고").model_dump_json()
    assert judge_offline(planted).verdict == "reject"
    assert judge_offline(good).verdict == "needs_human"  # 결정 규칙 통과, 의미 판단은 LLM/사람 몫


def test_eval_cases_file_matches_offline_rules():
    """eval/cases.jsonl 의 단별 기대를 결정 규칙으로 확인한다.

    약물감시 부정 케이스 1건만 1단 결정 규칙으로 reject 되고, 과잉해석 부정 케이스는 근거 ID 와
    수치가 모두 실측이라 1단을 통과해 needs_human 이 된다. 그래야 3단 LLM 판정을 재는 데이터가 된다.
    """
    from pathlib import Path
    rows = [json.loads(line) for line in (Path(__file__).parents[1] / "eval" / "cases.jsonl").read_text().splitlines()
            if line.strip()]
    assert len(rows) == 33  # 약물감시 3건 + 과잉해석 규칙 15종 x (통과, 반려)
    verdicts = {r["id"]: judge_offline(r["input"]).verdict for r in rows}

    assert verdicts["planted_unsupported_claim"] == "reject"   # 1단이 잡는 유일한 케이스
    assert verdicts["prr_signal_ok"] == "needs_human"
    assert verdicts["label_listed_ok"] == "needs_human"

    llm_only = [r["id"] for r in rows if r["id"] != "planted_unsupported_claim"]
    assert all(verdicts[i] == "needs_human" for i in llm_only)
    assert len([r for r in rows if r["expected_verdict"] == "reject"]) == 16
    assert len([r for r in rows if r["expected_verdict"] == "pass"]) == 17


def test_eval_case_inputs_pass_the_deterministic_evidence_rules():
    """모든 케이스의 주장이 비지 않은 근거 ID 를 갖는지. 하나라도 비면 3단 측정이 무너진다."""
    from pathlib import Path
    rows = [json.loads(line) for line in (Path(__file__).parents[1] / "eval" / "cases.jsonl").read_text().splitlines()
            if line.strip()]
    for row in rows:
        if row["id"] == "planted_unsupported_claim":
            continue  # 일부러 근거를 비운 1단 케이스
        author = AuthorOutput.model_validate_json(row["input"])
        assert author.claims, row["id"]
        for claim in author.claims:
            assert claim.evidence_ids and all(e.strip() for e in claim.evidence_ids), row["id"]


# --------------------------------------------------------------------------------------
# 크리틱 LLM 응답 파싱 (추론 모델이 생각 과정을 섞어 내보내는 경우)
# --------------------------------------------------------------------------------------
def test_extract_json_object_strips_thinking_and_fence():
    text = (
        "<think>먼저 {중괄호} 를 세어 본다</think>\n"
        "판정은 다음과 같습니다.\n"
        "```json\n"
        '{"verdict": "pass", "checks": [], "required_followups": []}\n'
        "```\n"
        "이상입니다.")
    assert extract_json_object(text) == {"verdict": "pass", "checks": [], "required_followups": []}


def test_extract_json_object_prefers_verdict_object_and_unwraps_one_level():
    text = '{"note": "생각 정리"} {"critic_report": {"verdict": "reject", "checks": []}}'
    assert extract_json_object(text) == {"verdict": "reject", "checks": []}


def test_extract_json_object_ignores_braces_inside_strings():
    text = '{"verdict": "pass", "required_followups": ["요약에 {중괄호} 가 있음"]}'
    assert extract_json_object(text)["required_followups"] == ["요약에 {중괄호} 가 있음"]


def test_parse_critic_report_returns_none_on_malformed_output():
    assert parse_critic_report("JSON 이 하나도 없는 서술") is None
    assert parse_critic_report('{"verdict": "maybe"}') is None          # Verdict 리터럴 위반
    report = parse_critic_report('설명\n{"verdict": "needs_human"}\n끝')
    assert report is not None and report.verdict == "needs_human" and report.checks == []


# --------------------------------------------------------------------------------------
# critic_verdict 평가기
# --------------------------------------------------------------------------------------
def test_extract_verdict_from_various_shapes():
    assert extract_verdict(CriticReport(verdict="pass")) == "pass"
    assert extract_verdict({"verdict": "reject"}) == "reject"
    assert extract_verdict('{"verdict": "needs_human"}') == "needs_human"
    assert extract_verdict("The critic decided to reject this.") == "reject"
    assert extract_verdict("pass or reject, unclear") is None


def test_score_item_scores_match_and_mismatch():
    from nat.data_models.evaluator import EvalInputItem

    def item(expected, output):
        return EvalInputItem(id="x", input_obj="{}", expected_output_obj=expected, output_obj=output,
                             full_dataset_entry={})

    assert score_item(item("reject", {"verdict": "reject"})).score == 1.0
    assert score_item(item("pass", {"verdict": "reject"})).score == 0.0
    assert score_item(item("pass", None)).score == 0.0
    bad = score_item(item("maybe", {"verdict": "pass"}))
    assert bad.error is not None


# --------------------------------------------------------------------------------------
# NAT 레지스트리 등록 (register.py 하단 import 블록이 살아 있어야 통과한다)
# --------------------------------------------------------------------------------------
def test_domain_tools_are_registered_under_expected_names():
    """도구 3종이 YAML 의 _type 이름으로 레지스트리에 실렸는지. import 가 빠지면 여기서 잡힌다."""
    import harness.register  # noqa: F401  (entry point 와 같은 경로로 등록을 발동시킨다)
    from nat.cli.type_registry import GlobalTypeRegistry

    registered = {i.local_name for i in GlobalTypeRegistry.get().get_registered_functions()}
    assert {"openfda_faers", "dailymed_label", "pubmed_search", "diffdock_nim"} <= registered
    assert {"echo_tool", "prr_calculator", "critic_judge"} <= registered


def test_registered_tool_names_are_unique():
    """같은 짧은 이름이 둘이면 NAT 가 YAML 의 _type 을 해석하지 못한다.

    도구 모듈을 패키지(harness.tools.X)와 최상위(X)로 두 번 import 하면 실제로 그렇게 된다.
    """
    import harness.register  # noqa: F401
    from nat.cli.type_registry import GlobalTypeRegistry

    names = [i.local_name for i in GlobalTypeRegistry.get().get_registered_functions()]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    assert duplicated == [], f"짧은 이름이 겹친다: {duplicated}"


def test_domain_tool_config_types_resolve_to_registered_builders():
    """설정 클래스의 name= 이 YAML 의 _type 이고, 그 클래스로 빌더를 다시 찾을 수 있어야 한다."""
    from harness.tools.pharmasignal_dailymed import DailyMedLabelConfig
    from harness.tools.pharmasignal_openfda import OpenFdaFaersConfig
    from harness.tools.pharmasignal_pubmed import PubmedSearchConfig
    from nat.cli.type_registry import GlobalTypeRegistry

    registry = GlobalTypeRegistry.get()
    for config_type, expected in ((OpenFdaFaersConfig, "openfda_faers"),
                                  (DailyMedLabelConfig, "dailymed_label"),
                                  (PubmedSearchConfig, "pubmed_search")):
        assert config_type.static_type() == expected
        info = registry.get_function(config_type)
        assert info.config_type is config_type
