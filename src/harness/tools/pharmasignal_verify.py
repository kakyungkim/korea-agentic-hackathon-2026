"""대조 검증 지표 — 불일치율과 검증 커버리지.

이식 출처
---------
2026-08 Agent Forge AI Hackathon 제출작(AgentForgeAI)의 `code/src/pharmasignal/verify.py`
(`CrossCheck`, `coverage`), `code/src/pharmasignal/measure.py`(`disagreement_rate`,
`run_failure_rate`, `mean_coverage`), `code/src/pharmasignal/ledger.py`(JSONL 덧붙이기와
해시 지문).

**코드를 그대로 옮기지 않았다.** v1 의 대조 대상은 LLM 이 작성한 파이썬 코드를 샌드박스에서
실행한 콘솔 출력이었고, 이 저장소의 대조 대상은 작성자 워크플로가 내는 `AuthorOutput` JSON
이다. 파서와 자료구조가 다르므로 **지표 정의와 그 정의가 지키려는 규율만** 옮기고 구현은
이 저장소 구조에 맞춰 새로 썼다.

왜 가져왔나
-----------
이 저장소의 크리틱(`harness/critic.py`)은 이미 적발률 1.0 을 낸다. 그런데 적발률과 여기서
재는 것은 묻는 질문이 다르다.

- **적발률**은 `eval/cases.jsonl` 의 손으로 라벨링한 케이스에서 크리틱의 판정이 기대값과
  맞는 비율이다. 크리틱이 *라벨대로 분류하는가*를 묻는다.
- **불일치율**은 작성자가 내놓은 **숫자**가 고정 로직으로 다시 구한 값과 어긋난 비율이다.
  작성자의 *산술이 맞는가*를 묻는다.
- **검증 커버리지**는 고정 로직이 기준값을 갖는 항목 가운데 실제로 대조된 비율이다.
  *출력의 몇 퍼센트나 검사했는가*를 묻는다.

크리틱의 결정 규칙은 JSON 형식, 주장 존재, 근거 ID 유무만 본다. **숫자를 다시 구해 보는
단계가 없다.** 근거 ID 가 붙은 틀린 숫자는 그대로 통과한다. 그 빈자리를 메우는 것이 이
모듈이고, 오라클은 `pharmasignal_ror.ror_2x2` 와 `pharmasignal_openfda.disproportionality`
가 맡는다.

커버리지를 함께 내놓는 이유는 불일치율만으로는 읽을 수 없기 때문이다. 대조한 값이 적으면
불일치율 0%는 "다 맞았다"가 아니라 "거의 안 봤다"는 뜻이다. 두 숫자는 함께 보고한다.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 숫자 하나. 1,234.56 처럼 세 자리 구분 쉼표가 붙은 것도 받는다.
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


@dataclass(slots=True)
class CrossCheck:
    """대조 한 건의 결과. 어느 값이 맞았고 어느 값이 어긋났는지 남긴다."""

    checked: int = 0
    agreed: int = 0
    checkable: int = 0  # 고정 로직이 기준값을 갖는 항목 수
    mismatches: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """하나라도 대조했고 전부 일치해야 통과.

        대조할 것을 하나도 찾지 못한 경우는 통과가 아니다. 검사하지 못한 것과 검사해서
        맞은 것은 다르다. v1 이 이 구분을 놓쳤다가 고친 자리다.
        """
        return self.checked > 0 and not self.mismatches

    @property
    def coverage(self) -> float:
        """기준값을 가진 항목 가운데 실제로 대조한 비율."""
        return self.checked / self.checkable if self.checkable else 0.0

    @property
    def disagreement_rate(self) -> float:
        """대조한 값 가운데 어긋난 비율."""
        return (self.checked - self.agreed) / self.checked if self.checked else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {"checked": self.checked, "agreed": self.agreed,
                "checkable": self.checkable, "coverage": round(self.coverage, 4),
                "disagreement_rate": round(self.disagreement_rate, 4),
                "ok": self.ok, "mismatches": list(self.mismatches),
                "notes": list(self.notes)}

    def summary(self) -> str:
        if self.checked == 0:
            return f"대조 실패. 기준값 {self.checkable}개 가운데 하나도 맞춰 보지 못했다"
        head = f"{self.agreed}/{self.checked} 일치, 커버리지 {self.coverage * 100:.0f}%"
        return head if self.ok else f"{head}, 불일치 {len(self.mismatches)}건"


def _near(got: float, want: float, tol: float = 0.02, places: int = 2) -> bool:
    """상대 오차와 표기 자릿수를 함께 허용한다.

    완전 일치를 요구하면 잡음을 재게 된다. 소수 둘째 자리까지 쓰라고 지시해 놓고 반올림
    차이를 불일치로 세면 0.12와 0.12가 어긋났다고 나온다. v1 이 실측으로 확인한 지점이다.
    """
    rounding = 0.5 * 10 ** -places
    return abs(got - want) <= max(tol * abs(want), rounding)


def truth_from_counts(counts: dict[str, Any]) -> dict[str, float]:
    """2x2 카운트에서 고정 로직 기준값을 만든다. 여기에는 LLM 이 개입하지 않는다."""
    try:
        from .pharmasignal_openfda import disproportionality
        from .pharmasignal_ror import ror_2x2
    except ImportError:  # 스크립트/테스트에서 sys.path 로 직접 임포트할 때
        from pharmasignal_openfda import disproportionality
        from pharmasignal_ror import ror_2x2

    a, b, c, d = (counts["a"], counts["b"], counts["c"], counts["d"])
    metrics = disproportionality(a, b, c, d)
    corrected = ror_2x2(a, b, c, d)
    truth: dict[str, float] = {}
    for key in ("prr", "ror", "chi2", "chi2_yates"):
        if metrics.get(key) is not None:
            truth[key] = float(metrics[key])
    if metrics.get("ror_ci95"):
        truth["ror_ci_low"], truth["ror_ci_high"] = (float(x) for x in metrics["ror_ci95"])
    elif corrected["ror"] is not None:
        truth["ror_ci_low"] = float(corrected["ci_low"])
        truth["ror_ci_high"] = float(corrected["ci_high"])
    return truth


# 작성자 출력에서 어떤 말이 어떤 기준값을 가리키는지. 긴 것을 먼저 둬야 짧은 것이 긴 말
# 안에서 잘못 잡히지 않는다(ROR 이 ROR CI 안에서 먼저 걸리는 것을 막는다).
_LABELS: list[tuple[str, str]] = [
    # "ROR 95% CI 하한" 도 "상한" 한 단어도 받는다. 앞의 CI 표기는 있어도 없어도 된다.
    ("ror_ci_low", r"(?:(?:ROR\s*)?(?:95%\s*)?CI(?:\s*95)?\s*)?(?:하한|lower(?:\s*bound)?)"),
    ("ror_ci_high", r"(?:(?:ROR\s*)?(?:95%\s*)?CI(?:\s*95)?\s*)?(?:상한|upper(?:\s*bound)?)"),
    ("chi2_yates", r"(?:chi2_yates|카이제곱\s*\(?Yates\)?|Yates)"),
    ("chi2", r"(?:chi2|chi-?square|카이제곱|χ2|χ²)"),
    ("prr", r"PRR"),
    ("ror", r"ROR"),
]


def crosscheck_text(text: str, truth: dict[str, float], *,
                    tol: float = 0.02, places: int = 2) -> CrossCheck:
    """자유 서술 안의 숫자를 기준값과 대조한다.

    작성자가 출력 형식을 정하므로 고정 파서를 쓸 수 없다. 기준값 쪽 라벨(PRR, ROR, CI 하한)이
    글에 나타난 자리를 찾고, 그 뒤 가까운 곳의 첫 숫자를 그 라벨의 값으로 읽는다. 라벨이
    없으면 그 항목은 세지 않는다. 세지 않은 항목은 커버리지가 떨어뜨려 드러낸다.
    """
    result = CrossCheck(checkable=len(truth))
    if not truth:
        result.notes.append("기준값이 없다. 2x2 카운트가 근거에 담기지 않았다")
        return result

    taken: list[tuple[int, int]] = []  # 이미 읽은 숫자 구간. 한 숫자를 두 번 세지 않는다.
    for key, pattern in _LABELS:
        if key not in truth:
            continue
        for m in re.finditer(pattern, text, re.I):
            tail = text[m.end():m.end() + 24]
            num = _NUMBER.search(tail)
            if not num:
                continue
            lo = m.end() + num.start()
            hi = m.end() + num.end()
            if any(lo < b and a < hi for a, b in taken):
                continue
            taken.append((lo, hi))
            got = float(num.group().replace(",", ""))
            result.checked += 1
            if _near(got, truth[key], tol=tol, places=places):
                result.agreed += 1
            else:
                near = " ".join(text[max(0, m.start() - 12):hi + 12].split())
                result.mismatches.append(
                    f"{key}: 출력 {got:g} vs 기준 {truth[key]:.4g}. 근처: “{near}”")
            break  # 한 라벨은 한 번만 센다

    if result.checked == 0:
        result.notes.append("출력에서 기준 라벨을 찾지 못해 대조하지 못했다")
    elif result.coverage < 0.5:
        result.notes.append(
            f"기준값 {result.checkable}개 가운데 {result.checked}개만 대조됐다. "
            "나머지는 검사되지 않은 채 지나갔다")
    return result


def crosscheck_author_output(author_output: str | dict, counts: dict[str, Any],
                             **kw: Any) -> CrossCheck:
    """`AuthorOutput` JSON 의 주장과 요약에 담긴 숫자를 2x2 카운트 기준값과 대조한다."""
    try:
        data = json.loads(author_output) if isinstance(author_output, str) else author_output
    except json.JSONDecodeError as exc:
        cc = CrossCheck()
        cc.notes.append(f"AuthorOutput 을 JSON 으로 읽지 못했다: {exc}")
        return cc
    parts = [str(c.get("text", "")) for c in (data.get("claims") or [])]
    parts.append(str(data.get("summary", "")))
    return crosscheck_text("\n".join(parts), truth_from_counts(counts), **kw)


@dataclass(slots=True)
class Measurement:
    """여러 번 돌려 모은 대조 결과와 그 요약."""

    rows: list[CrossCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def usable(self) -> list[CrossCheck]:
        """대조가 성립한 실행만. 대조 불가는 비율 계산에서 뺀다."""
        return [r for r in self.rows if r.checked > 0]

    @property
    def disagreement_rate(self) -> float:
        checked = sum(r.checked for r in self.usable)
        agreed = sum(r.agreed for r in self.usable)
        return (checked - agreed) / checked if checked else 0.0

    @property
    def run_failure_rate(self) -> float:
        """한 항목이라도 어긋난 실행의 비율. 사용자가 체감하는 쪽에 가깝다."""
        u = self.usable
        return sum(1 for r in u if r.mismatches) / len(u) if u else 0.0

    @property
    def mean_coverage(self) -> float:
        u = self.usable
        return statistics.fmean(r.coverage for r in u) if u else 0.0

    def as_dict(self) -> dict[str, Any]:
        u = self.usable
        return {
            "runs": len(self.rows),
            "runs_usable": len(u),
            "values_checked": sum(r.checked for r in u),
            "disagreement_rate": round(self.disagreement_rate, 4),
            "run_failure_rate": round(self.run_failure_rate, 4),
            "mean_coverage": round(self.mean_coverage, 4),
            "errors": list(self.errors),
        }

    def report(self) -> str:
        m = self.as_dict()
        return "\n".join([
            "=" * 62,
            "  작성자 출력의 불일치율과 검증 커버리지",
            "=" * 62,
            f"  실행 {m['runs']}회 (대조 성립 {m['runs_usable']}회), 대조한 값 {m['values_checked']}개",
            "",
            f"  불일치율       {m['disagreement_rate'] * 100:>6.1f}%   대조한 값 가운데 어긋난 비율",
            f"  실행 실패율    {m['run_failure_rate'] * 100:>6.1f}%   한 항목이라도 어긋난 실행의 비율",
            f"  검증 커버리지  {m['mean_coverage'] * 100:>6.1f}%   기준값 가운데 실제로 대조된 비율",
            "",
            "  두 숫자는 함께 읽는다. 불일치율이 0이어도 커버리지가 낮으면",
            "  검사되지 않은 채 지나간 것이 많다는 뜻이다.",
            "=" * 62,
        ])


def digest(text: str) -> str:
    """재현 확인용 짧은 해시. 원문을 남기지 않고 같은지만 견줄 수 있게 한다."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def append_ledger(path: str | Path, record: dict[str, Any],
                  fingerprints: dict[str, str] | None = None) -> Path:
    """실행 한 건을 JSON Lines 로 **덧붙인다**.

    v1 은 실행 기록을 `run-<주제>.json` 으로 덮어써서 같은 주제로 다시 돌리면 앞선 기록이
    사라졌다. 여러 번 돌린 결과를 견주겠다는 목적과 코드가 어긋나 있었고, 그래서 덧붙이기로
    바꿨다. 원문은 남기지 않고 해시만 남긴다. 같고 다름은 해시로 견줄 수 있고, 민감한 내용이
    기록에 새는 것도 막는다.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **record}
    if fingerprints:
        row["fingerprints"] = fingerprints
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def read_ledger(path: str | Path) -> list[dict[str, Any]]:
    """기록을 시간순으로 읽는다. 여러 번 돌린 결과를 견줄 때 쓴다."""
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
