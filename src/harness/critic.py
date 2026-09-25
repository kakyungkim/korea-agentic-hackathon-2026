"""크리틱 워크플로 함수 `critic_judge`.

작성자 출력(AuthorOutput JSON 문자열)을 받아 CriticReport 로 판정한다. 도구는 쓰지 않는다(읽기 전용).

두 단계로 나눈다.
1. 결정 규칙(순수 파이썬, 키 없이 동작): JSON 파싱, 근거 ID 유무, 빈 문자열 여부.
   하나라도 실패하면 LLM 을 부르지 않고 바로 reject. "근거 없는 주장을 심은" 부정 케이스는 여기서 걸린다.
2. 의미 판단(LLM, planner 모델): 결정 규칙을 모두 통과한 경우에만 요약이 주장 범위를 넘는지 등을 묻는다.
   `deterministic_only: true` 이거나 LLM 호출이 실패하면 verdict 를 needs_human 으로 두고 사유를 남긴다.
   (API 키가 없어도 워크플로가 끝까지 돌아가게 하려는 규약. CLAUDE.md "키 없이도 돌아가는 모의 경로".)

구조화 출력은 `with_structured_output` 을 쓰지 않는다. LangChain ChatNVIDIA 의 그 경로는 실패 시
`nvext.guided_json` 으로 되돌아가는데 Nemotron 3 엔드포인트가 그 필드를 400 으로 거부한다
(실측: "unknown field `guided_json`"). 대신 OpenAI 호환 `response_format` 의 json_schema 를
`llm.bind()` 로 직접 실어 보내고, 응답 본문에서 JSON 객체를 뽑아 `CriticReport.model_validate` 로 검증한다.
그마저 어긋나면 "JSON 만 출력하라"고 한 번 더 요청한다(추론 모델이라 생각 과정이 섞여 나오는 것을 대비).
"""

from __future__ import annotations

import json
import logging
from typing import Any
from typing import Iterator

from pydantic import Field
from pydantic import ValidationError

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import LLMRef
from nat.data_models.function import FunctionBaseConfig

from harness.schemas import AuthorOutput
from harness.schemas import Check
from harness.schemas import CriticReport

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are an independent critic inside an evidence-tracking pipeline. The input is a JSON object with "
    "`claims` (each with `text` and `evidence_ids`) and a `summary`.\n"
    "The evidence_ids are opaque provenance handles emitted by upstream tools (FAERS 2x2 extracts, DailyMed "
    "set ids, PubMed ids, calculator runs). You cannot open them and you must NOT judge whether their "
    "content is real, plausible or well formed. Treat every non-empty id as valid provenance; a separate "
    "deterministic stage has already verified that each claim carries one.\n"
    "Judge exactly two things.\n"
    "1. summary_within_claims: every assertion in `summary` must follow from the claims. Fail it when the "
    "summary introduces a new fact, a causal conclusion or a recommendation that no claim supports. A "
    "suggested next step or an open question is not a new fact.\n"
    "2. claims_are_checkable: each claim must be concrete enough that its cited evidence could in principle "
    "verify it. Fail it only for claims so vague that no evidence could confirm them.\n"
    "Set verdict `pass` when both checks pass, `reject` when either fails, and `needs_human` only when the "
    "input is malformed or you genuinely cannot decide.\n"
    "Answer with a single JSON object and nothing else, no markdown fence and no commentary:\n"
    '{"verdict": "pass|reject|needs_human", "checks": [{"name": "...", "passed": true, "reason": "..."}], '
    '"required_followups": ["..."]}')

_RETRY_INSTRUCTION = (
    "Your previous answer was not a valid CriticReport JSON object. Output the JSON object only: no "
    "reasoning, no markdown fence, no text before or after. Schema: "
    '{"verdict": "pass|reject|needs_human", "checks": [{"name": string, "passed": boolean, "reason": string}], '
    '"required_followups": [string]}')

# OpenAI 호환 구조화 출력. build.nvidia.com 의 Nemotron 3 엔드포인트가 받는 형식이다(실측).
_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "CriticReport",
        "schema": CriticReport.model_json_schema(),
        "strict": True,
    },
}


# --------------------------------------------------------------------------------------
# 0. 응답 본문에서 JSON 뽑기 (추론 모델 대비)
# --------------------------------------------------------------------------------------
def message_text(message: Any) -> str:
    """LangChain 메시지의 content 를 문자열로 만든다. 콘텐츠 블록 리스트도 받는다."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return "" if content is None else str(content)


def _iter_balanced_objects(text: str) -> Iterator[str]:
    """중괄호 균형을 세어 최상위 JSON 객체 후보를 순서대로 내놓는다. 문자열 안의 괄호는 세지 않는다."""
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                yield text[start:i + 1]
                start = -1


def extract_json_object(text: str) -> dict | None:
    """마크다운 펜스와 앞뒤 서술, `<think>` 생각 과정을 걷어내고 JSON 객체 하나를 뽑는다.

    추론 모델은 판정 앞뒤에 서술을 붙이므로 `verdict` 키를 가진 객체를 우선하고, 없으면 마지막 객체를 쓴다.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1]
    text = text.replace("<think>", " ")

    last_object: dict | None = None
    verdict_object: dict | None = None
    for chunk in _iter_balanced_objects(text):
        try:
            data = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        last_object = data
        if "verdict" in data:
            verdict_object = data
        # {"critic_report": {...}} 처럼 한 겹 감싸 나오는 경우를 푼다.
        if len(data) == 1:
            inner = next(iter(data.values()))
            if isinstance(inner, dict) and "verdict" in inner:
                verdict_object = inner
    return verdict_object if verdict_object is not None else last_object


def parse_critic_report(text: str) -> CriticReport | None:
    """응답 본문을 CriticReport 로 검증한다. 형식이 어긋나면 None."""
    data = extract_json_object(text)
    if data is None:
        return None
    try:
        return CriticReport.model_validate(data)
    except ValidationError:
        return None


# --------------------------------------------------------------------------------------
# 1. 결정 규칙 (순수 파이썬)
# --------------------------------------------------------------------------------------
def parse_author_output(payload: str | dict) -> tuple[AuthorOutput | None, Check]:
    """JSON 문자열 또는 dict 를 AuthorOutput 으로 파싱한다. 실패하면 (None, 실패 Check)."""
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
        parsed = AuthorOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        return None, Check(name="schema_valid", passed=False, reason=f"AuthorOutput 스키마 불일치: {exc}")
    return parsed, Check(name="schema_valid", passed=True, reason="AuthorOutput 스키마 일치")


def deterministic_checks(author: AuthorOutput) -> list[Check]:
    """LLM 없이 판정 가능한 규칙. 모두 통과해야 의미 판단 단계로 넘어간다."""
    checks: list[Check] = []

    if not author.claims:
        checks.append(Check(name="has_claims", passed=False, reason="주장이 하나도 없습니다."))
        return checks
    checks.append(Check(name="has_claims", passed=True, reason=f"주장 {len(author.claims)}건"))

    missing = [i for i, c in enumerate(author.claims) if not c.evidence_ids]
    checks.append(Check(
        name="all_claims_have_evidence",
        passed=not missing,
        reason=("모든 주장에 근거 ID 가 있습니다." if not missing else
                f"근거 ID 가 없는 주장 인덱스: {missing}"),
    ))

    blank = [i for i, c in enumerate(author.claims)
             if any((not isinstance(e, str)) or not e.strip() for e in c.evidence_ids)]
    checks.append(Check(
        name="evidence_ids_nonblank",
        passed=not blank,
        reason=("근거 ID 가 모두 비어 있지 않은 문자열입니다." if not blank else
                f"빈 근거 ID 를 가진 주장 인덱스: {blank}"),
    ))

    empty_text = [i for i, c in enumerate(author.claims) if not c.text.strip()]
    checks.append(Check(
        name="claim_text_nonblank",
        passed=not empty_text,
        reason=("주장 문장이 모두 채워져 있습니다." if not empty_text else
                f"빈 주장 문장 인덱스: {empty_text}"),
    ))
    return checks


def judge_offline(payload: str | dict) -> CriticReport:
    """결정 규칙만으로 판정한다. 규칙을 모두 통과하면 needs_human (의미 판단은 아직 안 함)."""
    author, schema_check = parse_author_output(payload)
    if author is None:
        return CriticReport(verdict="reject", checks=[schema_check],
                            required_followups=["AuthorOutput 스키마(claims[].text, claims[].evidence_ids, summary)로 다시 출력"])

    checks = [schema_check, *deterministic_checks(author)]
    failed = [c for c in checks if not c.passed]
    if failed:
        return CriticReport(
            verdict="reject",
            checks=checks,
            required_followups=[f"{c.name}: {c.reason}" for c in failed],
        )
    return CriticReport(
        verdict="needs_human",
        checks=checks,
        required_followups=["결정 규칙은 통과. 의미 판단(LLM 또는 사람)이 아직 수행되지 않았습니다."],
    )


# --------------------------------------------------------------------------------------
# 2. NAT 함수 등록
# --------------------------------------------------------------------------------------
class CriticJudgeConfig(FunctionBaseConfig, name="critic_judge"):
    """작성자 출력 JSON 을 받아 CriticReport 를 내는 읽기 전용 판정 함수."""

    llm_name: LLMRef = Field(description="의미 판단에 쓸 LLM (configs 의 llms 키). 계획/크리틱은 planner.")
    deterministic_only: bool = Field(
        default=False,
        description="True 면 LLM 을 호출하지 않고 결정 규칙만 적용한다. API 키가 없을 때의 드라이런 경로.")
    system_prompt: str = Field(default=_DEFAULT_SYSTEM_PROMPT, description="의미 판단용 시스템 프롬프트.")


@register_function(config_type=CriticJudgeConfig)
async def critic_judge(config: CriticJudgeConfig, builder: Builder):
    llm = None
    if not config.deterministic_only:
        llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    async def _ask(messages: list[tuple[str, str]], use_schema: bool) -> str:
        """LLM 을 한 번 부르고 본문 문자열을 돌려준다. use_schema 면 response_format 을 실어 보낸다."""
        target = llm.bind(response_format=_RESPONSE_FORMAT) if use_schema else llm
        return message_text(await target.ainvoke(messages))

    async def _judge_with_llm(author_output_json: str) -> CriticReport:
        """response_format 1회, 형식이 어긋나면 프롬프트 재요청 1회. 둘 다 실패하면 예외를 올린다."""
        base: list[tuple[str, str]] = [("system", config.system_prompt), ("human", author_output_json)]

        first_error = ""
        try:
            text = await _ask(base, use_schema=True)
            parsed = parse_critic_report(text)
            if parsed is not None:
                return parsed
            first_error = "response_format 응답이 CriticReport 로 검증되지 않음"
            logger.warning("critic_judge: %s. 본문 앞부분: %s", first_error, text[:200])
        except Exception as exc:  # response_format 자체를 거부하는 엔드포인트 대비
            first_error = f"{type(exc).__name__}: {exc}"
            logger.warning("critic_judge: response_format 호출 실패(%s). 프롬프트 경로로 재시도합니다.", first_error)

        retry = [*base, ("system", _RETRY_INSTRUCTION)]
        text = await _ask(retry, use_schema=False)
        parsed = parse_critic_report(text)
        if parsed is None:
            raise ValueError(f"재시도 응답도 CriticReport 형식이 아님 (1차: {first_error or '형식 불일치'})")
        return parsed

    async def _judge(author_output_json: str) -> CriticReport:
        """Judge an AuthorOutput JSON string and return a CriticReport (pass | reject | needs_human)."""
        report = judge_offline(author_output_json)
        if report.verdict == "reject" or llm is None:
            return report

        # 결정 규칙 통과: 의미 판단을 LLM 에 맡긴다.
        try:
            llm_report = await _judge_with_llm(author_output_json)
        except Exception as exc:  # 네트워크, 키, 파싱 실패 모두 사람에게 넘긴다.
            logger.warning("critic_judge: LLM 판정 실패, needs_human 으로 반환: %s", exc)
            report.required_followups = [
                f"LLM 판정 실패({type(exc).__name__}: {exc}). 사람이 의미 판단을 해야 합니다."
            ]
            return report

        deterministic = [c for c in report.checks]
        return CriticReport(
            verdict=llm_report.verdict,
            checks=deterministic + llm_report.checks,
            required_followups=llm_report.required_followups,
        )

    def _report_to_str(report: CriticReport) -> str:
        """콘솔/HTTP 프런트엔드는 str 출력을 요구하므로 CriticReport -> JSON 문자열 변환기를 등록한다."""
        return report.model_dump_json(indent=2)

    yield FunctionInfo.from_fn(_judge, description=_judge.__doc__, converters=[_report_to_str])
