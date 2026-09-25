"""ROR 오라클 대조 시험.

선행 프로젝트(AgentForgeAI, 2026-08)의 `code/src/pharmasignal/signal.py` 와 이 저장소의
`pharmasignal_openfda.disproportionality` 가 같은 2x2 표에서 같은 값을 내는지 맞춰 본다.

v1 구현은 이 저장소에 없다(읽기 전용 저장소다). 그래서 v1 의 산술을 이 파일 안에
`v1_reference` 로 그대로 베껴 두고 그것과 대조한다. 원본 164줄 가운데 산술에 해당하는
부분만 옮겼고, 옮긴 자리는 아래 주석에 적었다.
"""

from __future__ import annotations

import math

import pytest

# 도구 모듈은 반드시 패키지 경로로 import 한다. sys.path 로 최상위 모듈로도 불러오면
# @register_function 이 두 번 돌아 같은 짧은 이름(openfda_faers 등)이 둘이 되고,
# NAT 가 YAML 의 _type 을 해석하지 못한다 (nat/cli/type_registry.py _do_compute_annotation).
from harness.tools import pharmasignal_openfda as ofda
from harness.tools import pharmasignal_ror as oracle
from harness.tools import pharmasignal_verify as verify

# ---------------------------------------------------------------------------
# v1 산술 원문 (AgentForgeAI code/src/pharmasignal/signal.py 의 analyze() 안쪽)
#
#     if 0 in (a, b, c, d):
#         a, b, c, d = a + HALDANE, b + HALDANE, c + HALDANE, d + HALDANE
#     ror = (a * d) / (b * c)
#     se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
#     ci_low  = math.exp(math.log(ror) - Z * se)
#     ci_high = math.exp(math.log(ror) + Z * se)
#     is_signal = ci_low > 1.0        # Disproportionality.is_signal 프로퍼티
# ---------------------------------------------------------------------------
V1_Z = 1.96
V1_HALDANE = 0.5


def v1_reference(a, b, c, d):
    """v1 이 하던 계산 그대로. 여기를 고치면 대조의 뜻이 없어지니 손대지 않는다."""
    if 0 in (a, b, c, d):
        a, b, c, d = a + V1_HALDANE, b + V1_HALDANE, c + V1_HALDANE, d + V1_HALDANE
    ror = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return {"ror": ror,
            "ci_low": math.exp(math.log(ror) - V1_Z * se),
            "ci_high": math.exp(math.log(ror) + V1_Z * se)}


# (이름, a, b, c, d). 0 셀, 작은 수, 큰 수를 모두 넣는다.
CASES = [
    ("작은 수, 0 셀 없음", 5, 20, 50, 1000),
    ("경계선 건수 a=3", 3, 100, 200, 100_000),
    ("ROR 이 정확히 1", 10, 90, 100, 900),
    ("a=0, 이 약물에서 해당 반응 없음", 0, 30, 60, 5000),
    ("b=0, 이 약물 보고가 전부 이 반응", 7, 0, 40, 900),
    ("c=0, 다른 약물에서는 한 건도 없음", 6, 120, 0, 900_000),
    ("d=0", 4, 10, 25, 0),
    ("FAERS 규모 큰 수", 1200, 45_000, 30_000, 12_000_000),
    ("실측 FAERS 케이스", 19_411, 420_859, 12_260, 20_240_160),
]
IDS = [c[0] for c in CASES]
NONZERO = [c for c in CASES if 0 not in c[1:]]


# ---------------------------------------------------------------------------
# 1. 이식한 오라클이 v1 과 같은 값을 내는가
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,a,b,c,d", CASES, ids=IDS)
def test_oracle_matches_v1(name, a, b, c, d):
    """`pharmasignal_ror.ror_2x2` 는 0 셀 보정까지 v1 과 같아야 한다."""
    want = v1_reference(a, b, c, d)
    got = oracle.ror_2x2(a, b, c, d)
    assert got["ror"] == pytest.approx(want["ror"], rel=1e-12)
    assert got["ci_low"] == pytest.approx(want["ci_low"], rel=1e-12)
    assert got["ci_high"] == pytest.approx(want["ci_high"], rel=1e-12)
    assert got["haldane_applied"] is (0 in (a, b, c, d))


# ---------------------------------------------------------------------------
# 2. 두 구현 대조 — 0 셀이 없으면 같은 값, 있으면 갈린다
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,a,b,c,d", NONZERO, ids=[c[0] for c in NONZERO])
def test_openfda_equals_v1_when_no_zero_cell(name, a, b, c, d):
    """네 칸이 모두 0보다 크면 기존 구현과 v1 이 소수점 아래까지 같다.

    이것이 대조의 결론이다. 두 구현은 같은 공식을 쓰고 있었고, 어긋나는 곳은 0 셀뿐이었다.
    """
    want = v1_reference(a, b, c, d)
    got = ofda.disproportionality(a, b, c, d)
    assert got["ror"] == pytest.approx(want["ror"], rel=1e-12)
    lo, hi = got["ror_ci95"]
    assert lo == pytest.approx(want["ci_low"], rel=1e-12)
    assert hi == pytest.approx(want["ci_high"], rel=1e-12)


@pytest.mark.parametrize("name,a,b,c,d",
                         [c for c in CASES if 0 in c[1:]],
                         ids=[c[0] for c in CASES if 0 in c[1:]])
def test_zero_cell_keeps_raw_none_and_adds_corrected(name, a, b, c, d):
    """0 셀에서는 보정 없는 ROR 을 None 으로 두고, 보정값을 따로 내놓는다.

    보정한 값과 보정하지 않은 값이 한 열에 섞이면 나중에 구분할 수 없다. v1 은 보정을
    적용하고도 그 사실을 남기지 않았는데, 여기서는 `haldane_applied` 로 드러낸다.
    """
    got = ofda.disproportionality(a, b, c, d)
    assert got["ror"] is None and got["ror_ci95"] is None
    assert got["haldane_applied"] is True
    want = v1_reference(a, b, c, d)
    assert got["ror_haldane"] == pytest.approx(want["ror"], rel=1e-12)
    lo, hi = got["ror_ci95_haldane"]
    assert lo == pytest.approx(want["ci_low"], rel=1e-12)
    assert hi == pytest.approx(want["ci_high"], rel=1e-12)


def test_b_zero_is_the_strongest_signal_not_a_dropped_row():
    """b=0 은 신호가 가장 강한 자리다. 예전 구현은 이 줄을 통째로 떨어뜨렸다."""
    got = ofda.disproportionality(7, 0, 40, 900)
    assert got["ror"] is None          # 보정 없이는 정의되지 않는다
    assert got["ror_haldane"] > 100    # 보정하면 아주 큰 비가 나온다
    assert got["ror_signal"] is True   # 그리고 신호로 잡힌다


# ---------------------------------------------------------------------------
# 3. 신호 판정 관례
# ---------------------------------------------------------------------------
def test_ror_signal_requires_three_reports():
    """CI 하한이 1을 넘어도 보고가 3건 미만이면 신호로 올리지 않는다.

    v1 은 이 조건을 `analyze(min_affected=3)` 안에 숨겨 두어 `is_signal` 만 보면 보이지
    않았다. 드러내 놓고 시험한다.
    """
    strong = oracle.ror_2x2(2, 1, 5, 5000)
    assert strong["ci_low"] > 1.0
    assert strong["is_signal"] is False, "a=2 는 건수 기준에 못 미친다"
    assert oracle.ror_2x2(3, 1, 5, 5000)["is_signal"] is True


def test_haldane_padding_does_not_lift_a_over_the_threshold():
    """보정값 0.5 가 건수 기준을 넘기게 두면 안 된다. a 는 보정 전 값으로 따진다."""
    got = oracle.ror_2x2(2, 0, 5, 5000)
    assert got["haldane_applied"] is True
    assert got["is_signal"] is False


def test_evans_signal_uses_yates_corrected_chi_square():
    """Evans, Waller, Davis(2001) 관례는 Yates 보정 카이제곱을 쓴다.

    보정을 하면 카이제곱이 작아져 기준이 엄해진다. 두 값을 함께 내놓아 어느 쪽을 썼는지
    드러낸다.
    """
    got = ofda.disproportionality(40, 960, 200, 98_800)
    assert got["chi2_yates"] < got["chi2"]
    assert got["evans_signal"] is True          # 경계에서 멀어 판정은 그대로다
    # Yates 보정 공식 자체를 확인한다
    a, b, c, d = 40, 960, 200, 98_800
    n = a + b + c + d
    want = n * max(abs(a * d - b * c) - n / 2, 0) ** 2 / ((a + b) * (c + d) * (a + c) * (b + d))
    assert got["chi2_yates"] == pytest.approx(want, rel=1e-12)


def test_evans_and_ror_conventions_can_disagree():
    """PRR 계열과 ROR 계열은 서로 다른 관례다. 둘 다 내놓아 사람이 보게 한다."""
    got = ofda.disproportionality(*(3, 100, 200, 100_000))
    assert got["evans_signal"] is True and got["ror_signal"] is True
    quiet = ofda.disproportionality(10, 90, 100, 900)   # ROR 이 정확히 1
    assert quiet["evans_signal"] is False and quiet["ror_signal"] is False


def test_negative_cell_is_rejected():
    with pytest.raises(ValueError):
        oracle.ror_2x2(-1, 10, 10, 100)


def test_rank_orders_by_ci_lower_bound_not_point_estimate():
    """건수가 적어 구간이 넓은 항목은 ROR 이 커도 뒤로 밀린다. v1 의 정렬 기준이다."""
    wide = oracle.ror_2x2(3, 1, 100, 10_000)      # ROR 은 크지만 구간이 넓다
    tight = oracle.ror_2x2(300, 700, 100, 10_000)  # ROR 은 작지만 구간이 좁다
    assert wide["ror"] > tight["ror"]
    assert wide["ci_low"] < tight["ci_low"]
    ordered = oracle.rank([dict(wide, term="wide"), dict(tight, term="tight")])
    assert [r["term"] for r in ordered] == ["tight", "wide"]


# ---------------------------------------------------------------------------
# 4. 대조 검증 지표
# ---------------------------------------------------------------------------
COUNTS = {"a": 40, "b": 960, "c": 200, "d": 98_800}


def test_crosscheck_agrees_with_correct_numbers():
    truth = verify.truth_from_counts(COUNTS)
    assert {"prr", "ror", "chi2", "ror_ci_low", "ror_ci_high"} <= set(truth)
    text = (f"PRR 은 {truth['prr']:.2f} 이고 ROR 은 {truth['ror']:.2f} 이다. "
            f"ROR CI 하한 {truth['ror_ci_low']:.2f}, 상한 {truth['ror_ci_high']:.2f}.")
    cc = verify.crosscheck_text(text, truth)
    assert cc.ok is True
    assert cc.checked == 4 and cc.agreed == 4
    assert cc.disagreement_rate == 0.0
    assert 0 < cc.coverage <= 1.0


def test_crosscheck_catches_a_wrong_number():
    truth = verify.truth_from_counts(COUNTS)
    text = f"PRR 은 3.10 이고 ROR 은 {truth['ror']:.2f} 이다."
    cc = verify.crosscheck_text(text, truth)
    assert cc.ok is False
    assert cc.checked == 2 and cc.agreed == 1
    assert cc.disagreement_rate == pytest.approx(0.5)
    assert cc.mismatches and cc.mismatches[0].startswith("prr:")


def test_coverage_falls_when_most_values_go_unchecked():
    """불일치율 0%가 곧 통과는 아니다. 커버리지가 그 한계를 드러낸다."""
    truth = verify.truth_from_counts(COUNTS)
    cc = verify.crosscheck_text(f"ROR 은 {truth['ror']:.2f} 이다.", truth)
    assert cc.ok is True and cc.disagreement_rate == 0.0
    assert cc.coverage < 0.5
    assert cc.notes, "커버리지가 낮으면 그 사실을 적어 둬야 한다"


def test_crosscheck_without_any_label_is_not_a_pass():
    """대조할 것을 못 찾은 것과 대조해서 맞은 것은 다르다."""
    cc = verify.crosscheck_text("숫자가 없는 요약이다.", verify.truth_from_counts(COUNTS))
    assert cc.checked == 0 and cc.ok is False


def test_crosscheck_author_output_reads_claims_and_summary():
    truth = verify.truth_from_counts(COUNTS)
    payload = {
        "claims": [{"text": f"PRR 은 {truth['prr']:.2f} 이다.",
                    "evidence_ids": ["faers:2x2:drugX-eventY"]}],
        "summary": f"ROR 은 {truth['ror']:.2f} 로 계산되었다.",
    }
    cc = verify.crosscheck_author_output(payload, COUNTS)
    assert cc.checked == 2 and cc.agreed == 2


def test_measurement_aggregates_two_numbers_together():
    m = verify.Measurement(rows=[
        verify.CrossCheck(checked=4, agreed=4, checkable=5),
        verify.CrossCheck(checked=4, agreed=3, checkable=5, mismatches=["prr: ..."]),
        verify.CrossCheck(checked=0, agreed=0, checkable=5),  # 대조 불가는 비율에서 뺀다
    ])
    assert m.usable and len(m.usable) == 2
    assert m.disagreement_rate == pytest.approx(1 / 8)
    assert m.run_failure_rate == pytest.approx(0.5)
    assert m.mean_coverage == pytest.approx(0.8)
    assert "검증 커버리지" in m.report()


def test_ledger_appends_instead_of_overwriting(tmp_path):
    """같은 주제로 다시 돌려도 앞선 기록이 남아야 한다. v1 이 덮어써서 고친 자리다."""
    path = tmp_path / "runs-metformin.jsonl"
    verify.append_ledger(path, {"topic": "metformin", "run": 1})
    verify.append_ledger(path, {"topic": "metformin", "run": 2},
                         fingerprints={"code": verify.digest("x")})
    rows = verify.read_ledger(path)
    assert [r["run"] for r in rows] == [1, 2]
    assert rows[1]["fingerprints"]["code"] == verify.digest("x")
    assert all("recorded_at" in r for r in rows)
