#!/usr/bin/env python3
"""Graphical abstract for the leakage-protocol paper (companion, JAMIA).

The design this figure encodes
------------------------------
  problem       the reference set that supplies the labels is public, and so are the
                papers describing it, so a model may be recalling the answer key
  taxonomy      five leakage types for drug-event pair prediction, each with where it
                enters and what it inflates
  procedure     a four-rung blinding ladder; the rung at which performance falls is what
                identifies which prior the model was using
  readout       AUC per rung against a permutation null, crossed with a time-indexed split

The centre panel is the contribution: a single blinded number cannot tell you which prior
was doing the work, and the descent curve can.
"""
from __future__ import annotations

from matplotlib.patches import Circle, Rectangle

from ga_style import (BLUE, GREEN, HAIR, INK, RED, SAND, SUB, WASH, arrow, canvas, card,
                      columns, conclusion, header, redact, save)


def main() -> int:
    fig, ax = canvas()
    header(ax, "약물감시 참조 세트의 라벨 출처 누수: 유형과 가림 사다리",
           "별편  ·  SIDER 64,796쌍")
    columns(ax, [(0.018, "A  왜 재는 값을 믿기 어려운가"),
                 (0.352, "B  누수 다섯 유형"),
                 (0.672, "C  가림 사다리와 판독")],
            [0.338, 0.658])

    # ══ A. the contamination path ═════════════════════════════════════════════
    card(ax, 0.030, 0.760, 0.128, 0.105, ec=BLUE, lw=1.3)
    ax.text(0.094, 0.838, "참조 세트", fontsize=9.6, color=INK, ha="center",
            fontweight="semibold")
    ax.text(0.094, 0.812, "SIDER · OMOP", fontsize=8.4, color=SUB, ha="center")
    ax.text(0.094, 0.782, "공개", fontsize=8.6, color=BLUE, ha="center", fontweight="bold")

    card(ax, 0.190, 0.760, 0.128, 0.105, ec=BLUE, lw=1.3)
    ax.text(0.254, 0.838, "그 세트를 다룬 논문", fontsize=9.6, color=INK, ha="center",
            fontweight="semibold")
    ax.text(0.254, 0.812, "수치와 쌍 목록 포함", fontsize=8.4, color=SUB, ha="center")
    ax.text(0.254, 0.782, "공개", fontsize=8.6, color=BLUE, ha="center", fontweight="bold")

    arrow(ax, (0.094, 0.752), (0.140, 0.700), color=SUB, lw=1.5, rad=-0.15)
    arrow(ax, (0.254, 0.752), (0.208, 0.700), color=SUB, lw=1.5, rad=0.15)

    ax.add_patch(Circle((0.174, 0.650), 0.048, fc="#eef2f7", ec=BLUE, lw=1.3, zorder=2))
    ax.text(0.174, 0.664, "모델 학습", fontsize=9, color=INK, ha="center", zorder=3,
            fontweight="semibold")
    ax.text(0.174, 0.638, "코퍼스", fontsize=9, color=INK, ha="center", zorder=3,
            fontweight="semibold")

    arrow(ax, (0.174, 0.598), (0.174, 0.556), color=RED, lw=2.0)
    ax.add_patch(Rectangle((0.030, 0.486), 0.288, 0.066, fc="#f3e7e9", ec=RED, lw=1.2,
                           zorder=2))
    ax.text(0.174, 0.528, "정답을 본 적 있는 모델을 그 정답으로 평가한다",
            fontsize=9.6, color=RED, ha="center", fontweight="bold", zorder=3)
    ax.text(0.174, 0.502, "재는 쪽은 그 사실을 알 방법이 없다", fontsize=8.6,
            color=RED, ha="center", zorder=3)

    ax.text(0.030, 0.436, "이름을 가려 보면 알 수 있다", fontsize=10, color=INK,
            fontweight="semibold")

    card(ax, 0.030, 0.300, 0.288, 0.118)
    ax.text(0.044, 0.392, "약물", fontsize=8.4, color=SUB)
    ax.text(0.044, 0.358, "이상반응", fontsize=8.4, color=SUB)
    ax.text(0.110, 0.392, "NIRAPARIB", fontsize=9, color=INK, family="monospace")
    ax.text(0.110, 0.358, "THROMBOCYTOPENIA", fontsize=9, color=INK, family="monospace")
    redact(ax, 0.216, 0.385, 0.090)
    redact(ax, 0.216, 0.351, 0.090)
    ax.text(0.261, 0.420, "가리면", fontsize=8, color=RED, ha="center", fontweight="bold")
    ax.text(0.155, 0.420, "그대로", fontsize=8, color=SUB, ha="center")
    ax.plot([0.044, 0.304], [0.338, 0.338], color=HAIR, lw=0.9, zorder=3)
    ax.text(0.044, 0.314, "PRR 38.24  ·  χ² 144,679  ·  보고 1,065   (통계값은 두 조건에서 동일)",
            fontsize=7.8, color=SUB)

    ax.text(0.030, 0.246, "AUC 0.960", fontsize=13, color=INK, fontweight="bold")
    arrow(ax, (0.118, 0.254), (0.156, 0.254), color=RED, lw=2.0)
    ax.text(0.166, 0.246, "AUC 0.790", fontsize=13, color=RED, fontweight="bold")
    ax.text(0.030, 0.206, "격차 0.170 이 통계가 아니라 이름에서 온 몫이다.\n"
                          "귀무 AUC 는 라벨 뒤섞기로 0.532, 최고 통계 지표는 0.815.",
            fontsize=8.4, color=SUB, va="top", linespacing=1.6)

    conclusion(ax, 0.030, 0.062, 0.288, 0.086,
               "가린 값 하나만 보고하는 것으로는 부족하다.\n"
               "어느 층에서 떨어지는지가 어떤 사전지식을 썼는지 가른다.")

    # ══ B. taxonomy ═══════════════════════════════════════════════════════════
    ax.text(0.352, 0.862, "쌍 예측에서 정답이 입력으로 새는 경로", fontsize=9.4, color=SUB)

    types = [
        ("L1", "개체명 사전지식", "약명과 반응명만으로 답이 나온다", 0.960, 0.790, RED),
        ("L2", "라벨 출처 중복", "정답 라벨이 학습 코퍼스에 있다", None, None, RED),
        ("L3", "계열 단서 잔존", "이름을 가려도 서술로 계열이 복원된다", None, None, SAND),
        ("L4", "시점 역류", "조치 이후 데이터가 조치 예측에 들어간다", None, None, SAND),
        ("L5", "정답 정의 필드", "정답을 정한 필드가 입력에 남아 있다", None, None, RED),
    ]
    y = 0.775
    for tag, name, desc, a, b, color in types:
        card(ax, 0.352, y - 0.008, 0.290, 0.070, ec=HAIR)
        ax.add_patch(Rectangle((0.352, y - 0.008), 0.0055, 0.070, fc=color, ec="none",
                               zorder=3))
        ax.text(0.368, y + 0.040, tag, fontsize=9.4, color=color, fontweight="bold")
        ax.text(0.396, y + 0.040, name, fontsize=9.4, color=INK, fontweight="semibold")
        ax.text(0.368, y + 0.014, desc, fontsize=8.1, color=SUB)
        if a is not None:
            ax.text(0.632, y + 0.040, f"{a:.3f} → {b:.3f}", fontsize=8.6, color=color,
                    ha="right", fontweight="bold")
            ax.text(0.632, y + 0.016, "실측", fontsize=7.6, color=SUB, ha="right")
        else:
            ax.text(0.632, y + 0.028, "미측정", fontsize=7.8, color=SUB, ha="right")
        y -= 0.094

    ax.add_patch(Rectangle((0.352, 0.306), 0.290, 0.050, fc="#f3e7e9", ec=RED, lw=1.0,
                           zorder=2))
    ax.text(0.366, 0.338, "L5 가 가장 흔하고 가장 안 보인다", fontsize=8.8, color=RED,
            fontweight="bold", zorder=3)
    ax.text(0.366, 0.316, "중대성 정답을 결과 코드로 정하면서 그 코드를 입력에 남기는 경우",
            fontsize=7.9, color=RED, zorder=3)

    ax.text(0.352, 0.258, "선행 연구와의 선", fontsize=9.6, color=INK, fontweight="semibold")
    ax.text(0.352, 0.230, "누수 일반 분류(Kapoor 2023)와 화학에서의 가림 실험\n"
                          "(arXiv:2603.25857)은 이미 있다. 약물감시 참조 세트에\n"
                          "특화된 분류가 없고, 거기에 이 표를 낸다.",
            fontsize=8.3, color=SUB, va="top", linespacing=1.6)

    ax.text(0.352, 0.116, "가림 방법론 자체는 남의 것이다. 우리 것은 이 도메인에\n"
                          "적용한 결과이고, 기여 문장에서 그 구분을 지킨다.",
            fontsize=8.3, color=INK, va="top", linespacing=1.6)

    # ══ C. the ladder ═════════════════════════════════════════════════════════
    ax.text(0.672, 0.862, "층마다 개체 정보를 한 겹씩 걷어 낸다", fontsize=9.4, color=SUB)

    rungs = [("A", "전체 이름", 1.00, "64,796 전수"),
             ("B", "약물명만 가림", 0.66, "2,000 부분표본"),
             ("C", "계열 단서까지", 0.33, "2,000 부분표본"),
             ("D", "개체 정보 없음", 0.00, "64,796 전수")]
    for i, (tag, name, frac, n) in enumerate(rungs):
        x = 0.678 + i * 0.078
        ax.text(x + 0.030, 0.822, tag, fontsize=10, color=INK, ha="center",
                fontweight="bold")
        ax.add_patch(Rectangle((x, 0.762), 0.060, 0.048, fc="#eeeae4", ec="none", zorder=2))
        if frac > 0:
            ax.add_patch(Rectangle((x, 0.762), 0.060 * frac, 0.048, fc=INK, ec="none",
                                   zorder=3))
        if frac == 0:
            ax.add_patch(Rectangle((x, 0.762), 0.060, 0.048, fc="none", ec=RED, lw=1.2,
                                   zorder=3))
        ax.text(x + 0.030, 0.740, name, fontsize=7.9, color=SUB, ha="center")
        ax.text(x + 0.030, 0.720, n, fontsize=7.2, color=SUB, ha="center")
        if i < 3:
            arrow(ax, (x + 0.063, 0.786), (x + 0.075, 0.786), color=HAIR, lw=1.4, ms=9)
    ax.text(0.672, 0.694, "검은 칸이 모델에게 보이는 개체 정보의 양", fontsize=8, color=SUB)

    # descent curve
    x0, x1 = 0.700, 0.940
    ytop, ybot = 0.630, 0.430
    def yv(v):
        return ybot + (v - 0.50) / 0.50 * (ytop - ybot)
    ax.plot([x0 - 0.018, x1 + 0.030], [yv(0.532), yv(0.532)], color=RED, lw=1.0,
            ls=(0, (4, 3)), zorder=2)
    ax.text(x1 + 0.033, yv(0.532), "0.532\n귀무", fontsize=7.8, color=RED, va="center",
            linespacing=1.4)
    ax.plot([x0 - 0.018, x1 + 0.030], [yv(0.815), yv(0.815)], color=SUB, lw=1.0,
            ls=(0, (4, 3)), zorder=2)
    ax.text(x1 + 0.033, yv(0.815), "0.815\n통계 지표", fontsize=7.8, color=SUB, va="center",
            linespacing=1.4)

    pts = [(x0, 0.960, INK, "0.960"), (x0 + 0.080, None, SUB, None),
           (x0 + 0.160, None, SUB, None), (x1, 0.790, RED, "0.790")]
    ax.plot([x0, x1], [yv(0.960), yv(0.790)], color=HAIR, lw=2.0, ls=(0, (2, 2)), zorder=3)
    for x, v, c, lab in pts:
        if v is None:
            ax.plot([x], [yv(0.960) + (yv(0.790) - yv(0.960)) * ((x - x0) / (x1 - x0))],
                    "o", ms=8, mfc="white", mec=SUB, mew=1.4, zorder=5)
            ax.text(x, yv(0.960) + (yv(0.790) - yv(0.960)) * ((x - x0) / (x1 - x0)) + 0.030,
                    "?", fontsize=11, color=SUB, ha="center", fontweight="bold")
        else:
            ax.plot([x], [yv(v)], "o", ms=10, color=c, zorder=5, markeredgecolor="white",
                    markeredgewidth=1.4)
            ax.text(x, yv(v) + 0.028, lab, fontsize=10, color=c, ha="center",
                    fontweight="bold")
    ax.text(0.672, 0.392, "가운데 두 점이 이 논문이 채우는 자리다", fontsize=8.8,
            color=INK, fontweight="semibold")
    ax.text(0.672, 0.366, "A 에서 B 가 가파르면 이름 자체를, B 에서 C 가 가파르면\n"
                          "계열 지식을 쓰고 있었다는 뜻이다.",
            fontsize=8.3, color=SUB, va="top", linespacing=1.6)

    ax.plot([0.672, 0.982], [0.310, 0.310], color=HAIR, lw=1.0)
    ax.text(0.672, 0.278, "시점 통제와 교차", fontsize=9.6, color=INK, fontweight="semibold")
    ax.text(0.672, 0.252, "Harpaz 시간 색인 분할을 A 와 D 두 팔에 겹쳐 돌린다.\n"
                          "L1 과 L4 가 독립인지 그 교차로 확인한다.",
            fontsize=8.3, color=SUB, va="top", linespacing=1.6)

    ax.text(0.672, 0.172, "비용", fontsize=9.6, color=INK, fontweight="semibold")
    ax.text(0.672, 0.146, "전수 두 팔 USD 1.6  ·  부분표본 두 팔은 그 20분의 1",
            fontsize=8.3, color=SUB)

    conclusion(ax, 0.672, 0.046, 0.310, 0.078,
               "한 번 가린 값은 보호의 증거가 아니다.\n"
               "성능이 떨어지는 층이 어떤 사전지식을 썼는지 지목한다.")

    save(fig, "ga-ml-leakage.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
