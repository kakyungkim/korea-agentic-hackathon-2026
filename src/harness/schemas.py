"""작성자(author)와 크리틱(critic) 사이에 오가는 데이터 스키마.

작성자 워크플로는 AuthorOutput 형태의 JSON 을 내고, 크리틱 워크플로는 그 JSON 을 받아
CriticReport 로 판정한다. 두 후보(PharmaSignal, Night Shift)가 같은 스키마를 쓰고,
도메인별 차이는 Claim.evidence_ids 에 담기는 ID 의 종류(레코드 ID, 커밋 해시, 테스트 이름)로만 드러난다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class Claim(BaseModel):
    """작성자가 내놓은 주장 하나. 근거 ID 가 비어 있으면 크리틱이 자동 반려한다."""

    text: str = Field(description="주장 문장. 한 문장에 한 주장.")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="주장을 뒷받침하는 근거 식별자. 예: faers:2x2:drugX-eventY, dailymed:setid:...:section:6, "
        "pubmed:PMID, calc:prr, git:abc1234, pytest:tests/test_x.py::test_y",
    )


class AuthorOutput(BaseModel):
    """작성자 워크플로의 최종 출력."""

    claims: list[Claim] = Field(default_factory=list, description="근거 ID 가 붙은 주장 목록.")
    summary: str = Field(default="", description="사람이 읽을 요약. 주장에 없는 새 사실을 넣지 않는다.")


Verdict = Literal["pass", "reject", "needs_human"]


class Check(BaseModel):
    """크리틱이 수행한 점검 항목 하나."""

    name: str = Field(description="점검 이름. 예: schema_valid, all_claims_have_evidence")
    passed: bool = Field(description="통과 여부.")
    reason: str = Field(default="", description="판정 근거. 실패 시 무엇이 어긋났는지 구체적으로.")


class CriticReport(BaseModel):
    """크리틱 워크플로의 최종 출력. 통과분만 사람에게, 반려분은 사유와 함께 되돌린다."""

    verdict: Verdict = Field(description="pass | reject | needs_human")
    checks: list[Check] = Field(default_factory=list, description="수행한 점검 목록.")
    required_followups: list[str] = Field(
        default_factory=list,
        description="반려 또는 보류 시 작성자가 해야 할 후속 조치.",
    )
