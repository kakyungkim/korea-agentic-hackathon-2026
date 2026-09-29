#!/usr/bin/env python3
"""Graphical abstract for the pharmacovigilance evaluation-design paper.

What a graphical abstract has to do
-----------------------------------
It is printed at the head of the article and a reader decides from it alone whether to
read on. So it carries the study design, not a list of claims: where the data came from,
what was manipulated, what was compared against what, and what came out. Text is a label
on a visual element, never a substitute for one.

The design this figure encodes
------------------------------
  cohort        FAERS 2012Q4-2026Q2, 17.6M deduplicated cases
  evaluation    SIDER 64,796 drug-event pairs; 440 reports with outcome codes masked
  manipulation  the same record shown with entity names visible or redacted, numbers held
                constant -- this is the one contrast the whole paper turns on
  comparison    four routing conditions over the identical 440 reports (paired)
  readout       AUC against a permutation null, and human-first workload

The redaction block is the visual argument: two cards identical except for the black bars,
one scoring 0.960 and the other 0.790. A reader who takes only that away has the paper.

Run:
  /opt/anaconda3/envs/rag/bin/python scripts/figures/ga_pv_main.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import (Circle, FancyArrowPatch, FancyBboxPatch, PathPatch, Rectangle,
                                Wedge)
from matplotlib.path import Path as MPath

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "figures" / "ga-pv-main.png"

for ttf in (ROOT / "docs" / "figures" / "fonts").glob("Pretendard-*.ttf"):
    font_manager.fontManager.addfont(str(ttf))
plt.rcParams["font.family"] = "Pretendard"
plt.rcParams["axes.unicode_minus"] = False

INK, SUB, HAIR = "#1d242b", "#7b848c", "#dcd9d3"
BLUE, RED, GREEN, SAND = "#35618f", "#a4404e", "#4a7c59", "#b3944f"
CARD, WASH = "#ffffff", "#f6f4f0"


def card(ax, x, y, w, h, ec=HAIR, fc=CARD, lw=1.1, z=2, r=0.008):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


def arrow(ax, a, b, color=SUB, lw=1.8, ms=12, style="-|>", rad=0.0, z=4):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=ms, color=color,
                                 lw=lw, zorder=z,
                                 connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=0, shrinkB=0))


def ring(ax, cx, cy, r, frac, color):
    """A filled ring. Used for 'how much of this label family is usable'."""
    ax.add_patch(Circle((cx, cy), r, fc="none", ec="#e8e4dd", lw=3.4, zorder=3))
    ax.add_patch(Wedge((cx, cy), r + 0.0018, 90, 90 - 360 * frac, width=0.0036,
                       fc=color, ec=color, lw=3.4, zorder=4))


def funnel(ax, x, y_top, y_bot, w_top, w_bot, fc):
    v = [(x - w_top / 2, y_top), (x + w_top / 2, y_top),
         (x + w_bot / 2, y_bot), (x - w_bot / 2, y_bot)]
    ax.add_patch(PathPatch(MPath(v + [v[0]], [MPath.MOVETO] + [MPath.LINETO] * 3 + [MPath.CLOSEPOLY]),
                           fc=fc, ec="none", alpha=0.5, zorder=1))


def main() -> int:
    fig, ax = plt.subplots(figsize=(15.6, 7.4), dpi=300)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    fig.patch.set_facecolor("white")

    # ── header ────────────────────────────────────────────────────────────────
    ax.add_patch(Rectangle((0, 0.935), 1, 0.065, fc=INK, ec="none", zorder=1))
    ax.text(0.018, 0.9665, "정답이 부실한 도메인에서 판정 모델을 평가하는 설계",
            fontsize=15, color="white", fontweight="bold", va="center", zorder=3)
    ax.text(0.982, 0.9665, "약물감시  ·  FAERS 2012Q4–2026Q2", fontsize=10.5,
            color="#b9c2ca", va="center", ha="right", zorder=3)

    for x, lab in ((0.018, "A  코호트와 평가 세트"), (0.318, "B  조작: 개체명 가림"),
                   (0.648, "C  비교와 판독")):
        ax.text(x, 0.895, lab, fontsize=11, color=INK, fontweight="bold", va="center")
    for x in (0.305, 0.635):
        ax.plot([x, x], [0.055, 0.905], color=HAIR, lw=1.0, zorder=1)

    # ══ A. cohort → evaluation sets ═══════════════════════════════════════════
    funnel(ax, 0.150, 0.845, 0.470, 0.245, 0.135, "#e9eef4")

    card(ax, 0.040, 0.770, 0.220, 0.075)
    ax.add_patch(Rectangle((0.040, 0.770), 0.005, 0.075, fc=BLUE, ec="none", zorder=3))
    ax.text(0.056, 0.822, "FAERS 자발보고", fontsize=10.5, color=INK, fontweight="semibold")
    ax.text(0.056, 0.792, "55개 분기 · 중복 제거 후", fontsize=8.8, color=SUB)
    ax.text(0.250, 0.806, "17.6M", fontsize=15, color=BLUE, fontweight="bold", ha="right")

    for i, (yy, t, sub) in enumerate([
            (0.700, "중복 제거", "caseid 마다 최신 primaryid, FDA 삭제분 제외"),
            (0.640, "약물명 정규화", "627,606 → 482,191종"),
            (0.580, "2×2 표와 불균형 지표", "PRR · ROR₀₂₅ · IC₀₂₅ · χ²  (전부 SQL)")]):
        ax.plot([0.062], [yy + 0.012], "o", ms=5, color=BLUE, zorder=4)
        ax.text(0.078, yy + 0.020, t, fontsize=9.5, color=INK, fontweight="semibold")
        ax.text(0.078, yy - 0.006, sub, fontsize=8.2, color=SUB)
    ax.plot([0.062, 0.062], [0.596, 0.712], color=BLUE, lw=1.2, zorder=2)

    arrow(ax, (0.150, 0.552), (0.150, 0.500), color=BLUE, lw=2.0)

    card(ax, 0.040, 0.385, 0.105, 0.105, ec=BLUE, lw=1.4)
    ax.text(0.0925, 0.462, "평가 세트 1", fontsize=8.4, color=SUB, ha="center")
    ax.text(0.0925, 0.425, "64,796", fontsize=14, color=BLUE, fontweight="bold", ha="center")
    ax.text(0.0925, 0.400, "SIDER 약물–반응 쌍", fontsize=8.2, color=INK, ha="center")

    card(ax, 0.157, 0.385, 0.105, 0.105, ec=BLUE, lw=1.4)
    ax.text(0.2095, 0.462, "평가 세트 2", fontsize=8.4, color=SUB, ha="center")
    ax.text(0.2095, 0.425, "440", fontsize=14, color=BLUE, fontweight="bold", ha="center")
    ax.text(0.2095, 0.400, "FAERS 보고", fontsize=8.2, color=INK, ha="center")

    ax.add_patch(FancyBboxPatch((0.157, 0.345), 0.105, 0.028,
                                boxstyle="round,pad=0,rounding_size=0.005",
                                fc="#f3e7e9", ec=RED, lw=0.9, zorder=3))
    ax.text(0.2095, 0.359, "결과 코드 가림", fontsize=8.2, color=RED, ha="center",
            va="center", fontweight="semibold")

    # four label families, as rings showing how much of each is usable
    ax.text(0.040, 0.300, "제3자가 연구 이전에 확정한 라벨 네 계열", fontsize=9.6,
            color=INK, fontweight="semibold")
    ax.text(0.040, 0.272, "고리는 각 계열이 실제로 덮는 범위", fontsize=8.2, color=SUB)
    fams = [("규제 문서", 0.474, SAND, "52.6% 무신호"),
            ("조치 이력", 0.150, RED, "조치 9건"),
            ("목록·규칙", 1.000, GREEN, "정의로 주어짐"),
            ("운영 종점", 0.550, SAND, "행정 분류")]
    for i, (name, frac, color, note) in enumerate(fams):
        cx = 0.070 + i * 0.060
        ring(ax, cx, 0.212, 0.0175, frac, color)
        ax.text(cx, 0.209, f"{frac*100:.0f}" if frac < 1 else "100", fontsize=7.6,
                color=INK, ha="center", va="center", fontweight="bold", zorder=5)
        ax.text(cx, 0.174, name, fontsize=8.2, color=INK, ha="center")
        ax.text(cx, 0.152, note, fontsize=7.0, color=SUB, ha="center")
    ax.text(0.040, 0.108, "덮지 못한 몫은 결함이 아니라 측정값이다", fontsize=8.0, color=SUB)
    ax.text(0.040, 0.066, "정확도를 100%가 아니라 계열별 천장에 대고 읽는다",
            fontsize=9, color=INK, fontweight="semibold")

    # ══ B. the manipulation ═══════════════════════════════════════════════════
    ax.text(0.318, 0.862, "같은 레코드, 통계값은 고정, 이름만 가린다",
            fontsize=9.4, color=SUB)

    def record(y, blinded):
        card(ax, 0.318, y, 0.300, 0.175, ec=RED if blinded else HAIR,
             lw=1.5 if blinded else 1.1)
        ax.add_patch(Rectangle((0.318, y + 0.148), 0.300, 0.027,
                               fc="#f0ece6" if not blinded else "#f3e7e9", ec="none", zorder=3))
        ax.text(0.330, y + 0.1615, "약물–반응 레코드", fontsize=8.2,
                color=RED if blinded else SUB, va="center", fontweight="semibold")
        ax.text(0.606, y + 0.1615, "가림" if blinded else "그대로", fontsize=8.2,
                color=RED if blinded else SUB, va="center", ha="right", fontweight="bold")
        rows = [("약물", "NIRAPARIB"), ("이상반응", "THROMBOCYTOPENIA")]
        yy = y + 0.113
        for k, v in rows:
            ax.text(0.332, yy, k, fontsize=8.4, color=SUB)
            if blinded:
                ax.add_patch(Rectangle((0.404, yy - 0.007), 0.128, 0.020,
                                       fc=INK, ec="none", zorder=4))
            else:
                ax.text(0.404, yy, v, fontsize=9.2, color=INK, fontweight="semibold",
                        family="monospace")
            yy -= 0.034
        ax.plot([0.332, 0.606], [y + 0.058, y + 0.058], color=HAIR, lw=0.9, zorder=3)
        nums = [("PRR", "38.24"), ("χ²", "144,679"), ("보고 건수", "1,065")]
        xx = 0.338
        for k, v in nums:
            ax.text(xx, y + 0.034, k, fontsize=7.8, color=SUB)
            ax.text(xx, y + 0.012, v, fontsize=9.4, color=BLUE, fontweight="bold",
                    family="monospace")
            xx += 0.095
        ax.text(0.606, y + 0.020, "숫자 동일", fontsize=7.8, color=GREEN, ha="right",
                fontweight="semibold")

    record(0.630, blinded=False)
    record(0.408, blinded=True)
    arrow(ax, (0.468, 0.622), (0.468, 0.592), color=INK, lw=1.6, ms=11)
    ax.text(0.478, 0.607, "약물명과 반응명만 제거", fontsize=8.4, color=INK, va="center")

    ax.text(0.318, 0.352, "가림 사다리 (실험 1 · 3)", fontsize=9.6, color=INK,
            fontweight="semibold")
    rungs = [("A", "전체 이름", 1.00, SUB), ("B", "약물명만", 0.72, SUB),
             ("C", "계열 단서까지", 0.44, SUB), ("D", "개체 정보 없음", 0.16, RED)]
    for i, (tag, name, frac, color) in enumerate(rungs):
        x = 0.330 + i * 0.073
        ax.add_patch(Rectangle((x, 0.268), 0.055, 0.044, fc="#eeeae4", ec="none", zorder=2))
        ax.add_patch(Rectangle((x, 0.268), 0.055 * frac, 0.044,
                               fc=INK if frac > 0.5 else color, ec="none", zorder=3))
        ax.text(x + 0.0275, 0.322, tag, fontsize=9, color=INK, ha="center", fontweight="bold")
        ax.text(x + 0.0275, 0.248, name, fontsize=7.6, color=SUB, ha="center")
        if i < 3:
            arrow(ax, (x + 0.058, 0.290), (x + 0.070, 0.290), color=HAIR, lw=1.4, ms=9)
    ax.text(0.318, 0.206, "검은 칸이 모델에게 보이는 개체 정보의 양", fontsize=8.2, color=SUB)

    ax.text(0.318, 0.150, "기준선도 데이터에서 구한다", fontsize=9.6, color=INK,
            fontweight="semibold")
    ax.text(0.318, 0.108, "라벨을 무작위로 섞어 같은 계산을 반복하면 귀무 AUC 가 0.5 가\n"
                          "아니라 0.532 로 나온다. 양성과 음성이 42% 겹치기 때문이다.",
            fontsize=8.4, color=SUB, va="top", linespacing=1.6)

    # ══ C. comparison and readout ═════════════════════════════════════════════
    ax.text(0.648, 0.862, "① 판별력의 출처", fontsize=9.8, color=INK, fontweight="semibold")

    sx0, sx1 = 0.700, 0.800
    ytop, ybot = 0.800, 0.660
    def yv(v):  # 0.75 → ybot, 1.00 → ytop
        return ybot + (v - 0.75) / 0.25 * (ytop - ybot)
    ax.plot([sx0 - 0.012, sx1 + 0.075], [yv(0.815), yv(0.815)], color=SUB, lw=0.9,
            ls=(0, (4, 3)), zorder=2)
    ax.text(sx1 + 0.078, yv(0.815), "0.815  최고 통계 지표", fontsize=8.2, color=SUB, va="center")
    ax.plot([sx0 - 0.012, sx1 + 0.075], [yv(0.90), yv(0.90)], color=SUB, lw=0.9,
            ls=(0, (4, 3)), zorder=2)
    ax.text(sx1 + 0.078, yv(0.90), "0.90   선행연구 MALADE", fontsize=8.2, color=SUB, va="center")
    ax.plot([sx0, sx1], [yv(0.960), yv(0.790)], color=RED, lw=2.4, zorder=4)
    for x, v, lab, col in ((sx0, 0.960, "이름 보임", INK), (sx1, 0.790, "이름 가림", RED)):
        ax.plot([x], [yv(v)], "o", ms=10, color=col, zorder=5,
                markeredgecolor="white", markeredgewidth=1.4)
        ax.text(x, yv(v) + 0.026, f"{v:.3f}", fontsize=10.5, color=col, ha="center",
                fontweight="bold")
        ax.text(x, 0.630, lab, fontsize=8.6, color=col, ha="center")
    ax.add_patch(FancyBboxPatch((0.648, 0.752), 0.036, 0.042,
                                boxstyle="round,pad=0,rounding_size=0.006",
                                fc="#f3e7e9", ec=RED, lw=0.8, zorder=3))
    ax.text(0.666, 0.779, "0.170", fontsize=10.5, color=RED, ha="center", fontweight="bold",
            zorder=4)
    ax.text(0.666, 0.761, "누수", fontsize=7.8, color=RED, ha="center", zorder=4)
    ax.text(0.648, 0.592, "가린 값이 단순 통계 지표에도 진다", fontsize=8.6, color=INK,
            fontweight="semibold")

    ax.plot([0.648, 0.982], [0.560, 0.560], color=HAIR, lw=1.0)
    ax.text(0.648, 0.520, "② 업무량이 줄어든 곳", fontsize=9.8, color=INK, fontweight="semibold")
    ax.text(0.648, 0.492, "같은 440건 · 같은 모델 (AUROC 0.898) · 짝지은 McNemar",
            fontsize=8.2, color=SUB)

    # routing: two stacked flow bars over the identical 440 reports
    def flow(y, label, segs, note):
        ax.text(0.648, y + 0.050, label, fontsize=8.8, color=INK, fontweight="semibold")
        x = 0.648
        total = 0.334
        for w, color, txt, tcol in segs:
            ax.add_patch(Rectangle((x, y), total * w, 0.038, fc=color, ec="white",
                                   lw=1.1, zorder=3))
            if w > 0.16:
                ax.text(x + total * w / 2, y + 0.019, txt, fontsize=8, color=tcol,
                        ha="center", va="center", fontweight="bold", zorder=4)
            x += total * w
        ax.text(0.648, y - 0.024, note, fontsize=7.9, color=SUB)

    flow(0.392, "경로 2개  ·  모델 단독",
         [(302 / 440, RED, "사람 우선 302", "white"),
          (138 / 440, "#e6e2da", "자동 138", SUB)],
         "검토에 닿은 중대 234 / 250      특이도 0.642")
    flow(0.286, "경로 3개  ·  결정 정책",
         [(138 / 440, BLUE, "사람 우선 138", "white"),
          (109 / 440, "#9fb7d1", "System 2", "white"),
          (193 / 440, "#e6e2da", "자동 193", SUB)],
         "검토에 닿은 중대 247 / 250      특이도 0.984")
    arrow(ax, (0.968, 0.378), (0.968, 0.338), color=BLUE, lw=2.0, ms=12)

    ax.text(0.648, 0.222, "순위를 올리지 않고 경로를 늘려 사람 일을 164건 줄이고\n"
                          "중대 사례는 13건 더 검토에 닿게 했다.",
            fontsize=8.8, color=INK, va="top", linespacing=1.6)

    ax.add_patch(FancyBboxPatch((0.648, 0.052), 0.334, 0.106,
                                boxstyle="round,pad=0,rounding_size=0.008",
                                fc=WASH, ec=HAIR, lw=1.0, zorder=2))
    ax.text(0.664, 0.136, "결론", fontsize=8.4, color=SUB, fontweight="bold")
    ax.text(0.664, 0.114, "정확도는 계열별 천장에 대고 읽고, 판별력은 가림으로\n"
                          "출처를 가른다. 업무량은 판정기가 아니라 경로가 줄인다.",
            fontsize=8.5, color=INK, va="top", linespacing=1.6)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", facecolor="white", pad_inches=0.06)
    print(f"{OUT.relative_to(ROOT)}  {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
