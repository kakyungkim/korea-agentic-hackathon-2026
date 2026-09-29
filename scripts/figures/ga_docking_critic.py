#!/usr/bin/env python3
"""Graphical abstract for the docking overclaim-critic paper (arXiv + workshop).

The design this figure encodes
------------------------------
  failure mode  a claim whose citations resolve and whose numbers match, yet whose
                conclusion exceeds what the tool's output licenses
  provenance    rules are transcribed from limitations the tool and data providers state
                in their own documentation, not authored by us, so each rule has a source
                a reviewer can check
  pipeline      two deterministic gates before the model sees anything, so a failure can
                be attributed to one stage
  ablation      what the rule set adds over unaided judgement, and what kind of thing
                those additions are

The centre panel is the contribution: an arrow from a quoted sentence in a vendor document
to the rule it becomes. Everything else in the figure supports that transcription step.
"""
from __future__ import annotations

from matplotlib.patches import Rectangle

from ga_style import (BLUE, GREEN, HAIR, INK, RED, SAND, SUB, WASH, arrow, canvas, card,
                      columns, conclusion, header, save)


def main() -> int:
    fig, ax = canvas()
    header(ax, "도구가 스스로 금지한 추론을 규칙으로 옮겨 과잉해석을 거른다",
           "도킹 크리틱  ·  규칙 17종")
    columns(ax, [(0.018, "A  형식 검사가 못 잡는 실패"),
                 (0.352, "B  규칙의 출처"),
                 (0.672, "C  3단 검사와 절제")],
            [0.338, 0.658])

    # ══ A. the failure mode ═══════════════════════════════════════════════════
    card(ax, 0.030, 0.700, 0.290, 0.150, ec=RED, lw=1.5)
    ax.add_patch(Rectangle((0.030, 0.822), 0.290, 0.028, fc="#f3e7e9", ec="none", zorder=3))
    ax.text(0.044, 0.836, "모델이 낸 주장", fontsize=8.4, color=RED, va="center",
            fontweight="semibold")
    ax.text(0.306, 0.836, "반려", fontsize=8.4, color=RED, va="center", ha="right",
            fontweight="bold")
    ax.text(0.044, 0.812, "니라파립과 혈소판감소증의 PRR 은 38.24 이며\n"
                          "이는 니라파립이 혈소판감소증을 일으킨다는\n"
                          "강력한 증거다.",
            fontsize=9.2, color=INK, va="top", linespacing=1.6)
    ax.text(0.044, 0.712, "faers:2x2:NIRAPARIB:THROMBOCYTOPENIA@2026Q2",
            fontsize=7.4, color=SUB, family="monospace")

    checks = [("인용한 근거가 실재하는가", "통과", GREEN),
              ("문장 속 숫자가 원본과 맞는가", "통과", GREEN),
              ("스키마가 유효한가", "통과", GREEN),
              ("결론이 근거를 넘지 않는가", "반려", RED)]
    y = 0.646
    for q, verdict, color in checks:
        ax.plot([0.044], [y + 0.010], "o", ms=6, color=color, zorder=4)
        ax.text(0.060, y + 0.004, q, fontsize=8.6, color=INK)
        ax.text(0.306, y + 0.004, verdict, fontsize=8.6, color=color, ha="right",
                fontweight="bold")
        y -= 0.036
    ax.text(0.030, 0.474, "숫자도 출처도 맞는데 결론만 넘어선 경우를\n"
                          "형식 검사로는 걸러 낼 수 없다.",
            fontsize=8.8, color=INK, va="top", linespacing=1.6)

    ax.plot([0.030, 0.320], [0.418, 0.418], color=HAIR, lw=1.0)
    ax.text(0.030, 0.384, "실제로 일어나는 일이다", fontsize=9.8, color=INK,
            fontweight="semibold")

    cases = [("초파리 커넥톰 게시물", "홍보는 뉴런 16만 7천,\n파일은 노드 80개", "12만 회 읽힘"),
             ("아두카누맙 통념", "통념도 회사 발표도 근거를 넘고\n확인되는 것은 규제 기록뿐", "")]
    y = 0.286
    for title, body, note in cases:
        card(ax, 0.030, y, 0.290, 0.078, fc=WASH, ec=HAIR)
        ax.text(0.044, y + 0.054, title, fontsize=8.8, color=INK, fontweight="semibold")
        if note:
            ax.text(0.306, y + 0.054, note, fontsize=7.8, color=RED, ha="right",
                    fontweight="semibold")
        ax.text(0.044, y + 0.034, body, fontsize=7.9, color=SUB, va="top", linespacing=1.5)
        y -= 0.094
    ax.text(0.030, 0.158, "부정 케이스를 지어내지 않아도 된다는 뜻이다",
            fontsize=8.6, color=INK, fontweight="semibold")

    conclusion(ax, 0.030, 0.062, 0.290, 0.082,
               "지어낸 인용이 아니라 넘어선 결론이 문제다.\n"
               "그 경계를 누가 정하느냐가 이 논문의 물음이다.")

    # ══ B. provenance: doc sentence → rule ════════════════════════════════════
    ax.text(0.352, 0.862, "규칙을 짓지 않고 도구 문서에서 옮긴다", fontsize=9.4, color=SUB)

    card(ax, 0.352, 0.742, 0.290, 0.100, ec=BLUE, lw=1.3)
    ax.add_patch(Rectangle((0.352, 0.742), 0.0055, 0.100, fc=BLUE, ec="none", zorder=3))
    ax.text(0.368, 0.816, "NVIDIA DiffDock 문서", fontsize=8.6, color=BLUE,
            fontweight="semibold")
    ax.text(0.368, 0.790, "“Do not convert confidence directly\ninto binding affinity.”",
            fontsize=9, color=INK, va="top", linespacing=1.5, style="italic")

    arrow(ax, (0.497, 0.736), (0.497, 0.700), color=INK, lw=1.8, ms=12)
    ax.text(0.507, 0.718, "그대로 옮긴다", fontsize=8.4, color=INK, va="center")

    card(ax, 0.352, 0.596, 0.290, 0.094, ec=GREEN, lw=1.3)
    ax.add_patch(Rectangle((0.352, 0.596), 0.0055, 0.094, fc=GREEN, ec="none", zorder=3))
    ax.text(0.368, 0.664, "규칙  친화도 환산 금지", fontsize=9.2, color=INK,
            fontweight="semibold")
    ax.text(0.368, 0.640, "도킹 신뢰도를 결합 세기로 환산한 문장은 반려",
            fontsize=8.2, color=SUB)
    ax.text(0.368, 0.614, "반박하려면 제공자 문서를 반박해야 한다", fontsize=7.8,
            color=GREEN, fontweight="semibold")

    ax.text(0.352, 0.556, "규칙 17종의 뒷받침 강도", fontsize=9.6, color=INK,
            fontweight="semibold")
    ax.text(0.352, 0.534, "없는 것을 없다고 적은 것이 이 표의 값어치다", fontsize=8.1,
            color=SUB)
    strengths = [("매우 강함", 1, GREEN), ("강함", 2, GREEN), ("중간", 6, SAND),
                 ("약함", 2, SAND), ("없음", 4, RED)]
    x = 0.352
    for name, n, color in strengths:
        w = 0.290 * n / 15
        ax.add_patch(Rectangle((x, 0.478), w, 0.036, fc=color, ec="white", lw=1.2, zorder=3))
        if n >= 2:
            ax.text(x + w / 2, 0.496, str(n), fontsize=8.6, color="white", ha="center",
                    va="center", fontweight="bold", zorder=4)
        x += w
    x = 0.352
    for name, n, color in strengths:
        w = 0.290 * n / 15
        if n >= 2:
            ax.text(x + w / 2, 0.456, name, fontsize=7.6, color=SUB, ha="center")
        x += w
    ax.text(0.352, 0.430, "맨 왼쪽 한 칸이 매우 강함 1종이다. 없음 넷은 도구 문서 수준의\n사실이라 문헌을 억지로 붙이지 않고 사유를 따로 적었다. 15종 전부에\n논문을 달아 두면 하나만 어긋나도 나머지가 의심받는다.",
            fontsize=8.2, color=SUB, va="top", linespacing=1.6)

    ax.plot([0.352, 0.642], [0.340, 0.340], color=HAIR, lw=1.0)
    ax.text(0.352, 0.308, "규칙 하나는 우리가 직접 쟀다", fontsize=9.8, color=INK,
            fontweight="semibold")
    ax.text(0.352, 0.284, "같은 수용체와 리간드로 DiffDock 을 두 번 호출", fontsize=8.2,
            color=SUB)
    for i, (lab, vals, color) in enumerate([("1차", [0.798, 0.751, 0.725], SUB),
                                            ("2차", [0.761, 0.693, 0.515], RED)]):
        yy = 0.236 - i * 0.042
        ax.text(0.356, yy + 0.010, lab, fontsize=8.4, color=color, fontweight="semibold")
        for j, v in enumerate(vals):
            xx = 0.392 + j * 0.076
            ax.add_patch(Rectangle((xx, yy), 0.068, 0.024, fc="#eeeae4", ec="none", zorder=2))
            ax.add_patch(Rectangle((xx, yy), 0.068 * v, 0.024, fc=color, ec="none", zorder=3))
            ax.text(xx + 0.068 * v - 0.004, yy + 0.012, f"{v:.3f}", fontsize=7.4,
                    color="white", va="center", ha="right", family="monospace", zorder=4)
    ax.text(0.352, 0.164, "호스팅 API 에 시드가 없어 세 번째 포즈가 0.725 에서 0.515 로\n갈렸다. 재현성 주장 금지 규칙의 1차 근거가 우리 측정이다.",
            fontsize=8.2, color=INK, va="top", linespacing=1.6)

    conclusion(ax, 0.352, 0.028, 0.290, 0.076,
               "제공자가 밝힌 한계를 옮기면 과잉해석 판정이\n취향 다툼에서 벗어난다.")

    # ══ C. gates and ablation ═════════════════════════════════════════════════
    ax.text(0.672, 0.862, "모델은 마지막 한 단계에만 쓴다", fontsize=9.4, color=SUB)

    tiers = [("T1", "근거 ID 실재", "문자열 대조", "모델 안 씀", GREEN),
             ("T2", "숫자 일치  ±1.1%", "원본 쿼리와 비교", "모델 안 씀", GREEN),
             ("T3", "근거 범위 초과", "규칙 17종 + 안전 모델 2종", "모델 사용", RED)]
    y = 0.772
    for tag, name, how, who, color in tiers:
        card(ax, 0.672, y, 0.310, 0.072, ec=HAIR)
        ax.add_patch(Rectangle((0.672, y), 0.0055, 0.072, fc=color, ec="none", zorder=3))
        ax.text(0.688, y + 0.044, tag, fontsize=9.4, color=color, fontweight="bold")
        ax.text(0.714, y + 0.044, name, fontsize=9.2, color=INK, fontweight="semibold")
        ax.text(0.688, y + 0.019, how, fontsize=8.0, color=SUB)
        ax.text(0.972, y + 0.032, who, fontsize=7.8, color=color, ha="right",
                fontweight="semibold")
        y -= 0.082
    ax.text(0.672, 0.586, "앞의 둘이 기계라서 3단이 틀렸을 때 3단만 틀렸다고 말할 수 있다",
            fontsize=8.2, color=INK)

    ax.plot([0.672, 0.982], [0.558, 0.558], color=HAIR, lw=1.0)
    ax.text(0.672, 0.526, "규칙이 더한 몫", fontsize=9.8, color=INK, fontweight="semibold")
    ax.text(0.672, 0.502, "평가 문장 50건 · 규칙 유무로 절제", fontsize=8.2, color=SUB)

    for i, (lab, hit, fp, color) in enumerate([("규칙 없음", 13, 1, SUB),
                                               ("규칙 17종", 16, 0, BLUE)]):
        yy = 0.436 - i * 0.062
        ax.text(0.672, yy + 0.040, lab, fontsize=8.8, color=INK, fontweight="semibold")
        ax.add_patch(Rectangle((0.672, yy), 0.190, 0.032, fc="#eeeae4", ec="none", zorder=2))
        ax.add_patch(Rectangle((0.672, yy), 0.190 * hit / 16, 0.032, fc=color, ec="none",
                               zorder=3))
        ax.text(0.676, yy + 0.016, f"적발 {hit}/16", fontsize=8.2, color="white",
                va="center", fontweight="bold", zorder=4)
        ax.text(0.872, yy + 0.016, f"거짓 양성 {fp}/17", fontsize=8.2,
                color=RED if fp else GREEN, va="center", fontweight="semibold")

    ax.add_patch(Rectangle((0.672, 0.278), 0.310, 0.082, fc="#f3e7e9", ec=RED, lw=1.0,
                           zorder=2))
    ax.text(0.686, 0.342, "규칙이 추가로 잡은 것은 3건뿐이다", fontsize=8.8, color=RED,
            fontweight="bold", zorder=3)
    for i, t in enumerate(["단일 시드로 재현성을 주장",
                           "SMILES 를 실행 입력이라 부름",
                           "DiffDock 에 시드가 없다는 사실"]):
        ax.text(0.694, 0.320 - i * 0.018, f"·  {t}", fontsize=7.8, color=RED, zorder=3)

    ax.text(0.672, 0.252, "셋 다 도구를 두 번 불러 봐야 아는 것이고\n"
                          "일반 상식으로는 잡히지 않는다.",
            fontsize=8.4, color=INK, va="top", linespacing=1.6)

    ax.text(0.672, 0.184, "정직하게 적는 한계", fontsize=9.6, color=INK, fontweight="semibold")
    for i, t in enumerate(["규칙당 케이스가 1건씩이라 규칙별 구분력을 주장할 수 없다",
                           "부정 케이스를 우리가 지어냈다",
                           "규칙 귀속이 인접 규칙으로 번진다 (21건 중 4건)",
                           "표본 확대 전이라 기존 소프트웨어와 직접 비교가 없다"]):
        ax.text(0.672, 0.158 - i * 0.021, f"·  {t}", fontsize=8.0, color=SUB)

    conclusion(ax, 0.672, 0.006, 0.310, 0.076,
               "규칙의 값어치는 적발 건수가 아니라 적발한 것의\n"
               "종류에 있다. 도구를 써 본 사람만 아는 셋이었다.")

    save(fig, "ga-docking-critic.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
