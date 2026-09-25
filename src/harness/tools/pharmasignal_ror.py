"""보고오즈비(ROR) 오라클 — 고정 로직으로만 돌아가는 독립 계산기.

이식 출처
---------
2026-08 Agent Forge AI Hackathon 제출작(AgentForgeAI)의 `code/src/pharmasignal/signal.py`.
그 파일의 2x2 분할표 계산, Haldane 0.5 보정, 95% 신뢰구간, "CI 하한 > 1 이면 신호 후보"
관례를 가져왔다.

가져오면서 바꾼 것
- v1 은 ClinicalTrials.gov 의 `adverseEventsModule`(영향 인원/위험 인원)에서 표를 짰다.
  이 저장소는 openFDA FAERS 의 보고 건수로 표를 짜므로, 데이터 구조에 매인 부분
  (`AdverseEvent` 집계, `provenance`, 콘솔 표 출력)은 가져오지 않고 **산술과 판정 관례만**
  옮겼다. 표를 짜는 쪽은 `pharmasignal_openfda.faers_disproportionality` 가 맡는다.
- v1 은 보정을 적용해도 그 사실을 남기지 않았다. 보정한 값과 보정하지 않은 값이
  겉보기에 같아 보이면 나중에 구분할 수 없으므로 `haldane_applied` 플래그를 더했다.
- v1 의 `is_signal` 은 `ci_low > 1` 하나였다. 3건 미만을 미리 걸러 내기 때문에 실질적으로는
  `a >= 3` 이 함께 걸려 있었는데, 그 조건이 `analyze()` 안에 숨어 있었다. 여기서는
  `min_a` 인자로 드러내 놓았다.

무엇을 계산하나
---------------
어떤 반응이 이 약물에서 다른 약물들에 견주어 유독 많이 보고되는지를 본다.

                     해당 반응    다른 반응
    이 약물             a            b
    다른 약물 전부      c            d

    ROR = (a/b) / (c/d) = ad / bc
    95% CI = exp( ln(ROR) +- 1.96 * sqrt(1/a + 1/b + 1/c + 1/d) )

신뢰구간 하한이 1을 넘으면 신호 후보로 본다(van Puijenbroek 등이 정리한 ROR 관례).
칸이 하나라도 0이면 비가 정의되지 않으므로 네 칸에 0.5 를 더한다(Haldane-Anscombe 보정).

무엇이 아닌가
-------------
불균형 분석은 "같이 자주 보고된다"만 말하고 "약이 원인이다"를 말하지 않는다. 보고 편향,
적응증 교란, 노출 규모 차이가 그대로 남는다. 여기서 나오는 것은 사람이 들여다볼 후보
목록이지 결론이 아니다.
"""

from __future__ import annotations

import math
from typing import Any

Z95 = 1.96
HALDANE = 0.5
MIN_A = 3  # 신호 후보로 올리기 전 최소 보고 건수. Evans 2001 과 같은 관례다.


def ror_2x2(a: float, b: float, c: float, d: float, *,
            haldane: bool = True, min_a: int = MIN_A) -> dict[str, Any]:
    """2x2 표에서 ROR, 95% 신뢰구간, 신호 판정을 돌려준다. 네트워크가 필요 없다.

    Args:
        a, b, c, d: 분할표의 네 칸. 음수는 받지 않는다.
        haldane: 칸이 하나라도 0일 때 네 칸에 0.5 를 더한다. False 면 그 경우 `ror=None`.
        min_a: 신호 판정에 요구하는 최소 a. 보정 전의 a 로 따진다.

    Returns:
        ror, ci_low, ci_high, se_log, haldane_applied, is_signal, cells.
        계산이 성립하지 않으면 ror, ci_low, ci_high, se_log 가 None 이고 is_signal 은 False.
    """
    if min(a, b, c, d) < 0:
        raise ValueError(f"분할표에 음수가 있다: a={a} b={b} c={c} d={d}")

    raw_a = a
    applied = False
    if 0 in (a, b, c, d):
        if not haldane:
            return {"ror": None, "ci_low": None, "ci_high": None, "se_log": None,
                    "haldane_applied": False, "is_signal": False,
                    "cells": {"a": a, "b": b, "c": c, "d": d}}
        a, b, c, d = a + HALDANE, b + HALDANE, c + HALDANE, d + HALDANE
        applied = True

    ror = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    ci_low = math.exp(math.log(ror) - Z95 * se)
    ci_high = math.exp(math.log(ror) + Z95 * se)
    return {
        "ror": ror,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "se_log": se,
        "haldane_applied": applied,
        # 보정 전 a 로 따진다. 보정값 0.5 가 건수 기준을 넘기게 두면 안 된다.
        "is_signal": bool(raw_a >= min_a and ci_low > 1.0),
        "cells": {"a": a, "b": b, "c": c, "d": d},
    }


def rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """신호가 강한 순으로 정렬한다.

    v1 의 정렬 기준을 그대로 가져왔다. 점추정값(ROR)이 아니라 **신뢰구간 하한**을 1순위로
    둔다. 건수가 적어 구간이 넓은 항목은 ROR 이 커도 하한이 낮아 뒤로 밀리므로, 우연히
    커진 비가 목록 위로 올라오는 것을 막는다. 하한이 같으면 ROR 로 가린다.
    """
    return sorted(rows, key=lambda r: (r.get("ci_low") or 0.0, r.get("ror") or 0.0),
                  reverse=True)


def summary_line(term: str, row: dict[str, Any]) -> str:
    """대조용 한 줄 표기. `pharmasignal_verify` 가 이 형식을 읽는다."""
    if row["ror"] is None:
        return f"{term} | ROR = n/a | CI = n/a"
    mark = " *" if row["is_signal"] else ""
    return (f"{term} | ROR = {row['ror']:.2f} | "
            f"CI = {row['ci_low']:.2f} - {row['ci_high']:.2f}{mark}")
