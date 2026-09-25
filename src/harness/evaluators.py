"""`nat eval` 용 평가기 `critic_verdict`.

eval/cases.jsonl 의 각 행은 작성자 출력(input)과 기대 판정(expected_verdict)을 담는다.
평가 대상 워크플로는 configs/eval.yml 의 critic_judge 이고, 이 평가기는 워크플로가 낸 CriticReport 의
verdict 가 기대값과 같으면 1.0, 다르면 0.0 을 준다. 평균 점수가 곧 "크리틱 적발률" 이다.

NAT 1.9.0 평가기 등록 패턴 (nat/plugins/langchain/eval/trajectory_evaluator.py 에서 확인)
- `EvaluatorBaseConfig` 상속 + name="..." -> YAML 의 eval.evaluators.<키>._type
- `@register_evaluator(config_type=...)` async generator 가 `EvaluatorInfo(config=, evaluate_fn=, description=)` 를 yield
- evaluate_fn: `EvalInput -> EvalOutput`. 항목은 EvalInputItem(id, input_obj, expected_output_obj, output_obj, ...)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import Field

from nat.builder.builder import EvalBuilder
from nat.builder.evaluator import EvaluatorInfo
from nat.cli.register_workflow import register_evaluator
from nat.data_models.evaluator import EvalInput
from nat.data_models.evaluator import EvalInputItem
from nat.data_models.evaluator import EvaluatorBaseConfig
from nat.plugins.eval.data_models.evaluator_io import EvalOutput
from nat.plugins.eval.data_models.evaluator_io import EvalOutputItem

logger = logging.getLogger(__name__)

_VERDICTS = ("pass", "reject", "needs_human")


def extract_verdict(output_obj: Any) -> str | None:
    """워크플로 출력(CriticReport 모델, dict, JSON 문자열, 자유 텍스트)에서 verdict 를 뽑는다."""
    if output_obj is None:
        return None
    if hasattr(output_obj, "verdict"):
        return str(output_obj.verdict)
    if isinstance(output_obj, dict):
        v = output_obj.get("verdict")
        return str(v) if v is not None else None
    if isinstance(output_obj, str):
        text = output_obj.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "verdict" in data:
                return str(data["verdict"])
        except json.JSONDecodeError:
            pass
        # 자유 텍스트 폴백: 판정 단어가 정확히 하나만 등장할 때만 인정한다.
        found = [v for v in _VERDICTS if v in text.lower()]
        return found[0] if len(found) == 1 else None
    return None


def score_item(item: EvalInputItem) -> EvalOutputItem:
    expected = str(item.expected_output_obj).strip().lower() if item.expected_output_obj is not None else None
    got = extract_verdict(item.output_obj)
    if expected not in _VERDICTS:
        return EvalOutputItem(id=item.id, score=float("nan"),
                              reasoning=f"기대 판정이 유효하지 않음: {expected!r}",
                              error="invalid expected_verdict")
    if got is None:
        return EvalOutputItem(id=item.id, score=0.0,
                              reasoning=f"출력에서 verdict 를 찾지 못함 (기대: {expected})")
    match = got.lower() == expected
    return EvalOutputItem(id=item.id, score=1.0 if match else 0.0,
                          reasoning=f"expected={expected} got={got.lower()}")


class CriticVerdictEvaluatorConfig(EvaluatorBaseConfig, name="critic_verdict"):
    """크리틱 verdict 가 기대값과 일치하는 비율(적발률)을 계산하는 평가기. LLM 을 쓰지 않는다."""

    strict_needs_human: bool = Field(
        default=True,
        description="False 면 기대값이 reject 일 때 needs_human 도 절반(0.5) 점수를 준다.")


@register_evaluator(config_type=CriticVerdictEvaluatorConfig)
async def critic_verdict_evaluator(config: CriticVerdictEvaluatorConfig, _builder: EvalBuilder):

    async def _evaluate(eval_input: EvalInput) -> EvalOutput:
        items: list[EvalOutputItem] = []
        for item in eval_input.eval_input_items:
            out = score_item(item)
            if (not config.strict_needs_human and out.score == 0.0
                    and str(item.expected_output_obj).lower() == "reject"
                    and extract_verdict(item.output_obj) == "needs_human"):
                out = EvalOutputItem(id=out.id, score=0.5, reasoning=out.reasoning + " (needs_human 부분 점수)")
            items.append(out)
        numeric = [i.score for i in items if isinstance(i.score, float) and i.score == i.score]
        avg = round(sum(numeric) / len(numeric), 4) if numeric else None
        return EvalOutput(average_score=avg, eval_output_items=items)

    yield EvaluatorInfo(config=config, evaluate_fn=_evaluate,
                        description="크리틱 verdict 일치율 (적발률) 평가기")
