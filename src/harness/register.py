"""NAT 컴포넌트 등록 모듈.

pyproject.toml 의 `[project.entry-points.'nat.components'] harness = "harness.register"` 가
이 모듈을 가리키므로, 여기서 import 되는 모든 `@register_*` 데코레이터가 NAT 레지스트리에 실린다.
`nat validate`, `nat run`, `nat eval` 은 시작할 때 entry point 를 스캔한다(nat/runtime/loader.py).

등록 패턴 (NAT 1.9.0, 설치본에서 확인)
------------------------------------
1. `FunctionBaseConfig` 를 상속한 설정 클래스를 만들고 `name="..."` 으로 YAML 의 `_type` 값을 정한다.
   설정 필드(pydantic Field)는 YAML 에서 그대로 채워진다.
2. `@register_function(config_type=...)` 를 붙인 async generator 가 `(config, builder)` 를 받아
   `FunctionInfo.from_fn(fn, description=...)` 을 yield 한다.
   - fn 의 인자가 하나면 그 타입이 입력 스키마, 여러 개면 NAT 가 pydantic 모델을 자동 생성한다
     (nat/builder/function_info.py 의 create_model 경로). 반환 타입 힌트가 출력 스키마가 된다.
   - LLM 이 필요하면 `await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)`.
3. YAML 에서 `functions: {별명: {_type: <name>, ...}}` 로 인스턴스를 만들고,
   에이전트 워크플로의 `tool_names: [별명, ...]` 에 넣으면 도구가 된다.

도메인 도구 추가 절차
--------------------
- `src/harness/tools/<domain>_<tool>.py` 에 위 패턴으로 설정 클래스와 등록 함수를 작성한다.
- 이 파일 하단의 "도메인 도구 import" 블록에 `from harness.tools import <module>  # noqa: F401` 를 한 줄 추가한다.
- `configs/author.yml` 의 functions 와 tool_names 에 별명을 추가한다.
- `tests/test_<domain>_<tool>.py` 에 순수 계산 부분 단위 테스트를 둔다. 네트워크가 필요하면 `@pytest.mark.network`.
- `.venv/bin/nat validate --config_file configs/author.yml` 로 로딩을 확인한다.
"""

from __future__ import annotations

import logging
import math

from pydantic import BaseModel
from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

# 크리틱 함수와 평가기는 별도 모듈에 두고 여기서 import 해 등록을 발동시킨다.
from harness import critic as _critic  # noqa: F401  (critic_judge 등록)
from harness import evaluators as _evaluators  # noqa: F401  (critic_verdict 등록)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
# 예시 1. echo_tool: 입력을 그대로 돌려준다. 등록 배선 확인용.
# --------------------------------------------------------------------------------------
class EchoToolConfig(FunctionBaseConfig, name="echo_tool"):
    """입력 문자열을 접두어와 함께 그대로 돌려주는 도구. 배선 점검용."""

    prefix: str = Field(default="", description="반환 문자열 앞에 붙일 접두어.")


@register_function(config_type=EchoToolConfig)
async def echo_tool(config: EchoToolConfig, _builder: Builder):

    async def _echo(text: str) -> str:
        """Return the input text unchanged (optionally prefixed). Use to confirm tool wiring."""
        return f"{config.prefix}{text}" if config.prefix else text

    yield FunctionInfo.from_fn(_echo, description=_echo.__doc__)


# --------------------------------------------------------------------------------------
# 예시 2. prr_calculator: 2x2 표에서 PRR 과 ROR 을 계산한다. 순수 파이썬.
# --------------------------------------------------------------------------------------
class DisproportionalityResult(BaseModel):
    """불균형 분석 결과. 수치는 파이썬이 계산하고 모델은 해석만 한다."""

    a: int
    b: int
    c: int
    d: int
    prr: float = Field(description="Proportional Reporting Ratio = (a/(a+b)) / (c/(c+d))")
    prr_ci95: tuple[float, float] = Field(description="PRR 의 95% 신뢰구간 (로그 정규 근사)")
    ror: float = Field(description="Reporting Odds Ratio = (a*d) / (b*c)")
    ror_ci95: tuple[float, float] = Field(description="ROR 의 95% 신뢰구간 (로그 정규 근사)")
    signal_prr_rule: bool = Field(
        description="Evans 기준: PRR >= 2, a >= 3, chi-square >= 4 를 모두 만족하면 True")
    chi_square: float = Field(description="Yates 보정 없는 2x2 카이제곱 통계량")
    evidence_id: str = Field(description="크리틱이 추적할 근거 ID. 형식 calc:prr:a-b-c-d")


def compute_prr_ror(a: int, b: int, c: int, d: int) -> DisproportionalityResult:
    """2x2 표 (a: 약물+사례, b: 약물+기타사례, c: 기타약물+사례, d: 기타약물+기타사례)에서 PRR, ROR 계산.

    PRR = (a/(a+b)) / (c/(c+d)), ROR = (a*d)/(b*c).
    신뢰구간은 ln 값의 표준오차를 이용한 로그 정규 근사(PRR: sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d)),
    ROR: sqrt(1/a + 1/b + 1/c + 1/d)). 0 셀이 있으면 ZeroDivisionError 대신 ValueError 를 낸다.
    """
    for name, v in (("a", a), ("b", b), ("c", c), ("d", d)):
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"{name} 은 0 이상의 정수여야 합니다: {v!r}")
    if a == 0 or b == 0 or c == 0 or d == 0:
        raise ValueError("셀 값이 0 이면 PRR/ROR 을 정의할 수 없습니다. 연속성 보정(0.5 가산)은 호출자가 결정하세요.")

    prr = (a / (a + b)) / (c / (c + d))
    se_ln_prr = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    prr_ci = (math.exp(math.log(prr) - 1.96 * se_ln_prr), math.exp(math.log(prr) + 1.96 * se_ln_prr))

    ror = (a * d) / (b * c)
    se_ln_ror = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    ror_ci = (math.exp(math.log(ror) - 1.96 * se_ln_ror), math.exp(math.log(ror) + 1.96 * se_ln_ror))

    n = a + b + c + d
    expected_a = (a + b) * (a + c) / n
    expected_b = (a + b) * (b + d) / n
    expected_c = (c + d) * (a + c) / n
    expected_d = (c + d) * (b + d) / n
    chi_square = sum((obs - exp) ** 2 / exp for obs, exp in (
        (a, expected_a), (b, expected_b), (c, expected_c), (d, expected_d)))

    return DisproportionalityResult(
        a=a, b=b, c=c, d=d,
        prr=prr, prr_ci95=prr_ci,
        ror=ror, ror_ci95=ror_ci,
        chi_square=chi_square,
        signal_prr_rule=(prr >= 2.0 and a >= 3 and chi_square >= 4.0),
        evidence_id=f"calc:prr:{a}-{b}-{c}-{d}",
    )


class PRRCalculatorConfig(FunctionBaseConfig, name="prr_calculator"):
    """2x2 표에서 PRR, ROR, 95% 신뢰구간, 카이제곱을 계산한다. 도구 설정값은 없다."""


@register_function(config_type=PRRCalculatorConfig)
async def prr_calculator(_config: PRRCalculatorConfig, _builder: Builder):

    async def _prr(a: int, b: int, c: int, d: int) -> DisproportionalityResult:
        """Compute pharmacovigilance disproportionality metrics from a 2x2 table.

        a: reports with the drug AND the event; b: drug AND other events;
        c: other drugs AND the event; d: other drugs AND other events.
        Returns PRR, ROR, their 95% CIs, chi-square, the Evans signal rule and an evidence_id
        that must be cited in any claim built from these numbers.
        """
        return compute_prr_ror(a, b, c, d)

    def _result_to_str(result: DisproportionalityResult) -> str:
        """도구 출력이 문자열을 요구하는 경로(콘솔, 일부 도구 래퍼)용 변환기."""
        return result.model_dump_json()

    yield FunctionInfo.from_fn(_prr, description=_prr.__doc__, converters=[_result_to_str])


# --------------------------------------------------------------------------------------
# 도메인 도구 import (담당자가 한 줄씩 추가)
#
# 여기서 import 된 모듈의 @register_function 만 레지스트리에 실린다. import 가 빠지면
# YAML 의 _type 이 해석되지 않아 `nat validate` 가 실패한다.
# --------------------------------------------------------------------------------------
from harness.tools import pharmasignal_openfda as _openfda  # noqa: F401,E402  (openfda_faers 등록)
from harness.tools import pharmasignal_dailymed as _dailymed  # noqa: F401,E402  (dailymed_label 등록)
from harness.tools import pharmasignal_pubmed as _pubmed  # noqa: F401,E402  (pubmed_search 등록)
from harness.tools import dock_diffdock as _diffdock  # noqa: F401,E402  (diffdock_nim 등록)
from harness.tools import dock_vina_reference as _vina_ref  # noqa: F401,E402  (vina_reference 등록)
from harness.tools import dock_bindingdb_ref as _bindingdb_ref  # noqa: F401,E402  (bindingdb_ref 등록)
# Night Shift 쪽 도구(nightshift_runner, nightshift_report 등)는 아직 @register_function 이 없어
# import 하지 않는다. 예시로 적혀 있던 nightshift_repo 모듈은 존재하지 않는다.
