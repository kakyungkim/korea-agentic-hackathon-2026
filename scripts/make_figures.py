"""제출용 그림 2종 생성기.

  1) docs/figures/architecture_pharmasignal.png  PharmaSignal 데이터 흐름 도식
  2) docs/figures/results_pharmasignal.png       케이스 3건 PRR 포레스트 플롯

수치는 전부 eval/results/pharmasignal_cases.json 에서 읽는다(하드코딩 금지).
폰트는 docs/figures/fonts/Pretendard-*.ttf 를 fontManager 에 등록해 쓴다.

실행: .venv/bin/python scripts/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
FONT_DIR = FIG_DIR / "fonts"
CASES_JSON = ROOT / "eval" / "results" / "pharmasignal_cases.json"

DPI = 300

# ---------------------------------------------------------------------------
# 팔레트: 차분한 Tableau 뮤트 톤. 원색을 쓰지 않는다.
# ---------------------------------------------------------------------------
INK = "#2E3338"
INK_SOFT = "#5B646C"
INK_FAINT = "#8A939B"
PAPER = "#FFFFFF"
SHADOW = "#DFE3E7"

BLUE = "#6E8FB5"          # 모델(Nemotron) 계열
BLUE_BG = "#EBF1F7"
TEAL = "#6F9C96"          # 도구 계열
TEAL_BG = "#EAF2F0"
GREEN = "#7C9D6E"         # 파이썬 계산(모델이 계산하지 않는 지점)
GREEN_BG = "#EDF3E9"
PLUM = "#8E82AC"          # 크리틱
PLUM_BG = "#EFEDF6"
SAND = "#C39A68"          # 메모
SAND_BG = "#F7F1E7"
BRICK = "#BC7F73"         # 차단
BRICK_BG = "#F7EDEA"
GREY = "#9BA4AC"
GREY_BG = "#F2F4F6"

CHECK_TICK = "#6F9C96"


def register_fonts() -> str:
    """Pretendard 4종을 등록하고 기본 family 로 지정한다."""
    found = sorted(FONT_DIR.glob("Pretendard-*.ttf"))
    if not found:
        raise FileNotFoundError(
            f"Pretendard 폰트가 없습니다: {FONT_DIR}. docs/notes/figures.md 의 설치 절차를 따르세요.")
    for path in found:
        font_manager.fontManager.addfont(str(path))
    family = font_manager.FontProperties(fname=str(found[0])).get_name()
    plt.rcParams["font.family"] = family
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["savefig.facecolor"] = PAPER
    plt.rcParams["figure.facecolor"] = PAPER
    return family


# ---------------------------------------------------------------------------
# 그림 1 보조: 상자, 화살표, 플랫 아이콘
# ---------------------------------------------------------------------------
def box(ax, x, y, w, h, *, edge, face, lw=1.0, radius=1.1, shadow=True, ls="solid", z=2):
    if shadow:
        ax.add_patch(
            FancyBboxPatch((x + 0.45, y - 0.55), w, h,
                           boxstyle=f"round,pad=0,rounding_size={radius}",
                           linewidth=0, facecolor=SHADOW, alpha=0.55, zorder=z - 1))
    patch = FancyBboxPatch((x, y), w, h,
                           boxstyle=f"round,pad=0,rounding_size={radius}",
                           linewidth=lw, edgecolor=edge, facecolor=face,
                           linestyle=ls, zorder=z)
    ax.add_patch(patch)
    return patch


def arrow(ax, p0, p1, *, color=INK_SOFT, lw=1.1, z=6, style="-|>", ls="solid"):
    ax.add_patch(
        FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=9,
                        linewidth=lw, color=color, zorder=z, linestyle=ls,
                        shrinkA=0, shrinkB=0))


def tag(ax, x, y, text, *, color, bg, size=5.0, ha="left"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=size, color=color,
            fontweight="semibold", zorder=8,
            bbox=dict(boxstyle="round,pad=0.30", facecolor=bg, edgecolor=color,
                      linewidth=0.5, alpha=1.0))


def icon_bars(ax, cx, cy, color):
    for i, hgt in enumerate((1.0, 1.7, 1.3)):
        ax.add_patch(Rectangle((cx - 1.35 + i * 0.95, cy - 0.9), 0.62, hgt,
                               facecolor=color, edgecolor="none", zorder=7))


def icon_doc(ax, cx, cy, color):
    ax.add_patch(Rectangle((cx - 1.0, cy - 1.15), 1.85, 2.3, facecolor="none",
                           edgecolor=color, linewidth=0.8, zorder=7))
    for i in range(3):
        ax.add_patch(Rectangle((cx - 0.65, cy + 0.52 - i * 0.62), 1.15, 0.2,
                               facecolor=color, edgecolor="none", zorder=7))


def icon_search(ax, cx, cy, color):
    ax.add_patch(Circle((cx - 0.25, cy + 0.25), 0.85, facecolor="none",
                        edgecolor=color, linewidth=0.9, zorder=7))
    ax.add_line(Line2D([cx + 0.35, cx + 1.1], [cy - 0.35, cy - 1.05],
                       color=color, linewidth=1.0, zorder=7))


def icon_table(ax, cx, cy, color):
    ax.add_patch(Rectangle((cx - 1.25, cy - 1.25), 2.5, 2.5, facecolor="none",
                           edgecolor=color, linewidth=0.9, zorder=7))
    ax.add_line(Line2D([cx, cx], [cy - 1.25, cy + 1.25], color=color, linewidth=0.9, zorder=7))
    ax.add_line(Line2D([cx - 1.25, cx + 1.25], [cy, cy], color=color, linewidth=0.9, zorder=7))


def icon_check(ax, cx, cy, color, scale=1.0):
    ax.add_line(Line2D([cx - 0.55 * scale, cx - 0.15 * scale, cx + 0.62 * scale],
                       [cy + 0.02 * scale, cy - 0.42 * scale, cy + 0.55 * scale],
                       color=color, linewidth=1.2, solid_capstyle="round", zorder=8))


def icon_person(ax, cx, cy, color):
    ax.add_patch(Circle((cx, cy + 0.85), 0.62, facecolor=color, edgecolor="none", zorder=7))
    ax.add_patch(FancyBboxPatch((cx - 1.15, cy - 1.15), 2.3, 1.45,
                                boxstyle="round,pad=0,rounding_size=0.7",
                                facecolor=color, edgecolor="none", zorder=7))


def icon_block(ax, cx, cy, color, r=1.15):
    ax.add_patch(Circle((cx, cy), r, facecolor=PAPER, edgecolor=color,
                        linewidth=1.3, zorder=9))
    off = r * 0.62
    ax.add_line(Line2D([cx - off, cx + off], [cy + off, cy - off],
                       color=color, linewidth=1.3, zorder=10))


# ---------------------------------------------------------------------------
# 그림 1: 아키텍처
# ---------------------------------------------------------------------------
def make_architecture(out_path: Path) -> Path:
    fig = plt.figure(figsize=(8.0, 5.0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 62.5)
    ax.axis("off")

    ax.text(2.0, 59.6, "PharmaSignal 데이터 흐름", fontsize=13, fontweight="bold", color=INK)
    ax.text(2.0, 56.4,
            "약물과 이상사례 한 쌍을 받아 근거 ID를 붙인 메모를 내고, 크리틱이 검증한 뒤 사람에게 넘긴다.",
            fontsize=6.6, color=INK_SOFT)

    # --- OpenShell 샌드박스 경계 ---------------------------------------------
    sx0, sy0, sx1, sy1 = 15.0, 12.5, 98.5, 53.0
    ax.add_patch(
        FancyBboxPatch((sx0, sy0), sx1 - sx0, sy1 - sy0,
                       boxstyle="round,pad=0,rounding_size=1.6",
                       linewidth=1.2, edgecolor=GREY, facecolor="#FBFCFD",
                       linestyle=(0, (5, 3)), zorder=1))
    ax.text(sx0 + 0.6, sy1 + 1.5, "OpenShell 샌드박스 경계", fontsize=7.0,
            fontweight="bold", color=INK_SOFT, va="center")
    ax.text(sx1 - 0.6, sy1 + 1.5,
            "허용 도메인 4곳: api.fda.gov, dailymed.nlm.nih.gov, eutils.ncbi.nlm.nih.gov, integrate.api.nvidia.com",
            fontsize=5.2, color=INK_FAINT, ha="right", va="center")
    ax.text(sx0 + 1.6, 50.6, "쓰기는 /work/out만, 네트워크는 deny-by-default",
            fontsize=5.4, color=INK_FAINT, va="center")

    # --- 사용자 입력 ---------------------------------------------------------
    box(ax, 1.0, 34.0, 12.5, 14.0, edge=GREY, face=GREY_BG)
    icon_person(ax, 7.25, 44.3, GREY)
    ax.text(7.25, 41.0, "사용자 입력", ha="center", va="center", fontsize=7.2,
            fontweight="bold", color=INK, zorder=8)
    ax.text(7.25, 38.0, "약물 + 이상사례\n예: metformin,\nLactic acidosis",
            ha="center", va="center", fontsize=5.8, color=INK_SOFT, zorder=8,
            linespacing=1.45)
    arrow(ax, (13.5, 41.0), (17.3, 41.0))
    # 판정 모델(NemoGuard 토픽 제어)은 호스팅 쪽 500 으로 차단 시연을 못 했다.
    # 배선이 확인된 계층(NAT Guardrails 미들웨어 + NeMo Guardrails Colang 정책)만 적는다.
    tag(ax, 7.25, 31.0, "NeMo Guardrails 정책", color=PLUM, bg=PLUM_BG, size=5.0, ha="center")
    ax.text(7.25, 28.0, "환자 개별 복약 조언을\n차단 주제로 정의", ha="center", va="center",
            fontsize=5.0, color=INK_FAINT, linespacing=1.45)

    # --- 1. 계획 수립 --------------------------------------------------------
    box(ax, 17.5, 34.0, 16.0, 14.0, edge=BLUE, face=BLUE_BG, lw=1.1)
    ax.text(25.5, 45.4, "1. 계획 수립", ha="center", va="center", fontsize=7.4,
            fontweight="bold", color=INK, zorder=8)
    ax.text(25.5, 41.6, "도구 호출 순서와\n질의어를 정한다", ha="center", va="center",
            fontsize=5.9, color=INK_SOFT, zorder=8, linespacing=1.45)
    tag(ax, 25.5, 38.0, "Nemotron 3 Super", color=BLUE, bg=PAPER, size=5.2, ha="center")
    ax.text(25.5, 35.4, "NeMo Agent Toolkit  author.yml", ha="center", va="center",
            fontsize=5.0, color=INK_FAINT, zorder=8)
    arrow(ax, (33.5, 41.0), (36.3, 41.0))

    # --- 2. 도구 3종 ---------------------------------------------------------
    box(ax, 36.5, 28.0, 21.0, 20.0, edge=TEAL, face=TEAL_BG, lw=1.1)
    ax.text(47.0, 45.6, "2. 도구 3종 (읽기 전용)", ha="center", va="center",
            fontsize=7.2, fontweight="bold", color=INK, zorder=8)
    rows = [
        (42.1, "openFDA FAERS", "이상사례 2x2 카운트", icon_bars),
        (37.0, "DailyMed 라벨", "SPL 섹션 분할", icon_doc),
        (31.9, "PubMed", "문헌 근거 PMID", icon_search),
    ]
    for cy, title, sub, icon in rows:
        box(ax, 38.0, cy - 2.05, 18.0, 4.1, edge="#CBD9D6", face=PAPER,
            lw=0.7, radius=0.7, shadow=False, z=5)
        icon(ax, 40.4, cy, TEAL)
        ax.text(42.5, cy + 0.85, title, ha="left", va="center", fontsize=6.0,
                fontweight="semibold", color=INK, zorder=8)
        ax.text(42.5, cy - 1.0, sub, ha="left", va="center", fontsize=5.2,
                color=INK_SOFT, zorder=8)
    ax.text(47.0, 29.3, "NeMo Retriever 라벨 RAG는 확장 계획", ha="center", va="center",
            fontsize=5.0, color=INK_FAINT, style="italic", zorder=8)
    arrow(ax, (57.5, 41.0), (60.3, 41.0))

    # --- 3. 파이썬 계산 (핵심 메시지) ---------------------------------------
    box(ax, 60.5, 34.0, 17.0, 14.0, edge=GREEN, face=GREEN_BG, lw=1.7)
    icon_table(ax, 64.0, 44.6, GREEN)
    ax.text(66.4, 44.6, "3. 지표 계산", ha="left", va="center", fontsize=7.4,
            fontweight="bold", color=INK, zorder=8)
    ax.text(69.0, 40.9, "PRR, ROR, 카이제곱\n95% CI, Evans 기준",
            ha="center", va="center", fontsize=5.9, color=INK_SOFT, zorder=8,
            linespacing=1.45)
    tag(ax, 69.0, 36.4, "파이썬이 계산, 모델은 계산하지 않음",
        color=GREEN, bg=PAPER, size=5.2, ha="center")
    arrow(ax, (77.5, 41.0), (80.3, 41.0))

    # --- 4. 트리아지 메모 ----------------------------------------------------
    box(ax, 80.5, 34.0, 16.0, 14.0, edge=SAND, face=SAND_BG, lw=1.1)
    ax.text(88.5, 45.4, "4. 트리아지 메모", ha="center", va="center", fontsize=7.4,
            fontweight="bold", color=INK, zorder=8)
    ax.text(88.5, 41.5, "주장마다 근거 ID\nFAERS 쿼리, setid, PMID",
            ha="center", va="center", fontsize=5.8, color=INK_SOFT, zorder=8,
            linespacing=1.45)
    tag(ax, 88.5, 37.8, "Nemotron 3.5 Lightning", color=SAND, bg=PAPER, size=5.0, ha="center")
    ax.text(88.5, 35.3, "JSON 스키마 고정 출력", ha="center", va="center",
            fontsize=5.0, color=INK_FAINT, zorder=8)
    arrow(ax, (88.5, 34.0), (88.5, 28.2))

    # --- 5. 독립 크리틱 ------------------------------------------------------
    box(ax, 60.5, 16.5, 36.0, 11.5, edge=PLUM, face=PLUM_BG, lw=1.3)
    ax.text(62.6, 25.6, "5. 독립 크리틱 에이전트", ha="left", va="center",
            fontsize=7.4, fontweight="bold", color=INK, zorder=8)
    ax.text(62.6, 23.1, "별도 워크플로, 쓰기 도구 없음.  NeMo Agent Toolkit critic.yml, Nemotron 3 Super",
            ha="left", va="center", fontsize=5.1, color=INK_FAINT, zorder=8)
    icon_check(ax, 63.4, 20.9, CHECK_TICK)
    ax.text(64.8, 20.9, "모든 주장에 근거 ID가 붙었는가", ha="left", va="center",
            fontsize=5.8, color=INK_SOFT, zorder=8)
    icon_check(ax, 63.4, 18.6, CHECK_TICK)
    ax.text(64.8, 18.6, "라벨 인용이 실제 라벨 텍스트에 있는가", ha="left", va="center",
            fontsize=5.8, color=INK_SOFT, zorder=8)

    arrow(ax, (70.0, 16.5), (70.0, 10.7), color=TEAL)
    ax.text(70.7, 13.6, "통과", ha="left", va="center", fontsize=5.6,
            fontweight="semibold", color=TEAL, zorder=8)
    arrow(ax, (90.0, 16.5), (90.0, 10.7), color=BRICK)
    ax.text(90.7, 13.6, "반려", ha="left", va="center", fontsize=5.6,
            fontweight="semibold", color=BRICK, zorder=8)

    # --- 사람 / 반려 ---------------------------------------------------------
    box(ax, 60.0, 2.2, 21.0, 8.5, edge=TEAL, face=TEAL_BG)
    icon_person(ax, 63.6, 6.3, TEAL)
    ax.text(66.0, 7.5, "사람에게 전달", ha="left", va="center", fontsize=6.8,
            fontweight="bold", color=INK, zorder=8)
    ax.text(66.0, 4.6, "PV 담당자가 최종 판단", ha="left", va="center",
            fontsize=5.5, color=INK_SOFT, zorder=8)

    box(ax, 83.5, 2.2, 15.0, 8.5, edge=BRICK, face=BRICK_BG)
    ax.text(91.0, 7.5, "사유와 함께 반려", ha="center", va="center", fontsize=6.6,
            fontweight="bold", color=INK, zorder=8)
    ax.text(91.0, 4.6, "실패한 검사 항목을 적어\n작성자에게 되돌린다", ha="center", va="center",
            fontsize=5.2, color=INK_SOFT, zorder=8, linespacing=1.4)

    # --- 경계 밖 시도 차단 ---------------------------------------------------
    arrow(ax, (42.0, 28.0), (33.6, 15.4), color=BRICK, lw=1.0, ls=(0, (3, 2)))
    icon_block(ax, 32.0, 13.0, BRICK)
    box(ax, 17.0, 2.2, 28.0, 8.5, edge=BRICK, face=PAPER, lw=1.0, ls=(0, (4, 2.5)))
    ax.text(31.0, 7.6, "허용 목록 밖 도메인", ha="center", va="center", fontsize=6.4,
            fontweight="bold", color=BRICK, zorder=8)
    ax.text(31.0, 4.6, "github.com, example.com 등은 차단되고\n감사 로그에 남는다",
            ha="center", va="center", fontsize=5.2, color=INK_SOFT, zorder=8,
            linespacing=1.4)

    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# 그림 2: 케이스 3건 결과
# ---------------------------------------------------------------------------
def load_cases(path: Path) -> tuple[list[dict], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for case in payload["cases"]:
        faers = case["faers"]
        summary = case["summary"]
        lo, hi = faers["prr_ci95"]
        rows.append({
            "drug": case["drug"],
            "reaction": case["reaction"],
            "prr": faers["prr"],
            "lo": lo,
            "hi": hi,
            "a": summary["faers_a"],
            "labeled": summary["labeled"],
            "sections": summary.get("label_sections") or [],
            "pubmed": summary["pubmed_total"],
            "signal": summary["evans_signal"],
            # 2026-09-25 추가. evans_signal 의 판정 근거가 Yates 보정 카이제곱으로 바뀌었고,
            # ROR 계열 판정(ror_signal)이 새로 생겼다. 두 계열이 어긋나는지 그림에서 한 줄로 밝힌다.
            "chi2_yates": summary.get("chi2_yates"),
            "ror_signal": summary.get("ror_signal"),
        })
    return rows, payload["generated_at"]


def make_results(out_path: Path) -> tuple[Path, list[dict]]:
    rows, generated_at = load_cases(CASES_JSON)
    n = len(rows)

    fig = plt.figure(figsize=(8.0, 4.4))
    fig.text(0.035, 0.945, "케이스 3건의 PRR과 95% 신뢰구간", fontsize=13,
             fontweight="bold", color=INK, va="center")
    fig.text(0.035, 0.884,
             "불균형 지표는 openFDA FAERS 2x2 카운트에서 파이썬이 계산했다. 점은 PRR, 가로 막대는 95% 신뢰구간을 뜻한다.",
             fontsize=6.8, color=INK_SOFT, va="center")

    # Evans 계열과 ROR 계열은 관례가 달라 어긋날 수 있다. 몇 건이 같았는지는 데이터에서 센다.
    agree = sum(1 for r in rows if bool(r["signal"]) == bool(r["ror_signal"]))
    if agree == n:
        cross = "ROR 기준(a≥3, ROR 95%% CI 하한 > 1)과 판정은 %d건 모두 같았다." % n
    else:
        cross = "ROR 기준(a≥3, ROR 95%% CI 하한 > 1)과 판정은 %d건 중 %d건이 같았다." % (n, agree)
    fig.text(0.035, 0.838,
             "Evans 기준의 카이제곱은 Yates 연속성 보정을 한 값이다. " + cross,
             fontsize=6.8, color=INK_SOFT, va="center")

    ax_lab = fig.add_axes([0.035, 0.155, 0.205, 0.615])
    ax = fig.add_axes([0.253, 0.155, 0.435, 0.615])
    ax_txt = fig.add_axes([0.700, 0.155, 0.285, 0.615])

    for a in (ax_lab, ax_txt):
        a.set_xlim(0, 1)
        a.set_ylim(-0.7, n - 0.3)
        a.invert_yaxis()
        a.axis("off")

    ax.set_xscale("log")
    ax.set_xlim(0.35, 260)
    ax.set_ylim(-0.7, n - 0.3)
    ax.invert_yaxis()
    ax.axvline(1.0, color=INK_FAINT, linewidth=1.0, linestyle=(0, (4, 3)), zorder=2)
    ax.text(0.94, -0.62, "PRR = 1 기준선", ha="right", va="bottom", fontsize=5.8,
            color=INK_SOFT)
    ax.axvline(2.0, color=GREY, linewidth=0.7, linestyle=(0, (1, 3)), zorder=2)
    ax.text(2.06, n - 0.42, "Evans 기준 PRR ≥ 2", ha="left", va="bottom", fontsize=5.4,
            color=INK_FAINT)

    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GREY)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.set_yticks([])
    ticks = [0.5, 1, 2, 5, 10, 20, 50, 100, 200]
    ax.set_xticks(ticks)
    ax.set_xticklabels([("%g" % t) for t in ticks], fontsize=6.4, color=INK_SOFT)
    ax.tick_params(axis="x", length=2.5, color=GREY, pad=2)
    ax.set_xlabel("PRR 비례보고비 (로그 눈금)", fontsize=6.6, color=INK_SOFT, labelpad=4)
    ax.grid(axis="x", which="major", color="#EDF0F2", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)

    for i, r in enumerate(rows):
        color = BLUE if r["signal"] else GREY
        ax.plot([r["lo"], r["hi"]], [i, i], color=color, linewidth=1.8,
                solid_capstyle="round", zorder=4)
        for edge_x in (r["lo"], r["hi"]):
            ax.plot([edge_x, edge_x], [i - 0.11, i + 0.11], color=color,
                    linewidth=1.3, zorder=4)
        ax.plot([r["prr"]], [i], marker="o", markersize=6.2, color=color,
                markeredgecolor=PAPER, markeredgewidth=1.0, zorder=5)

        # 왼쪽 라벨
        ax_lab.text(1.0, i - 0.12, r["drug"], ha="right", va="center", fontsize=7.6,
                    fontweight="bold", color=INK)
        ax_lab.text(1.0, i + 0.14, r["reaction"], ha="right", va="center", fontsize=6.4,
                    color=INK_SOFT)
        ax_lab.text(1.0, i + 0.36, "FAERS 동반보고 %s건" % f"{r['a']:,}", ha="right",
                    va="center", fontsize=5.4, color=INK_FAINT)

        # 오른쪽 수치
        ax_txt.text(0.0, i - 0.12, "%.2f  (%.2f~%.2f)" % (r["prr"], r["lo"], r["hi"]),
                    ha="left", va="center", fontsize=6.6, color=INK, fontweight="semibold")
        if r["labeled"]:
            lab_txt = "라벨 기재 (%s)" % ", ".join(
                {"boxed_warning": "박스 경고",
                 "warnings_and_precautions": "경고와 주의",
                 "adverse_reactions": "이상반응"}.get(s, s) for s in r["sections"])
            lab_color = SAND
        else:
            lab_txt = "라벨 미기재"
            lab_color = INK_SOFT
        ax_txt.text(0.0, i + 0.16, lab_txt, ha="left", va="center", fontsize=5.6,
                    color=lab_color)
        ax_txt.text(0.0, i + 0.40, "PubMed %s건" % f"{r['pubmed']:,}", ha="left", va="center",
                    fontsize=5.6, color=INK_FAINT)

    ax_txt.text(0.0, -0.62, "PRR (95% CI), 라벨 기재 여부, 문헌 건수", ha="left",
                va="bottom", fontsize=5.8, fontweight="semibold", color=INK_SOFT)

    legend = [
        Line2D([], [], color=BLUE, marker="o", markersize=5, linewidth=1.8,
               markeredgecolor=PAPER, label="Evans 기준 충족 (a≥3, PRR≥2, Yates 보정 카이제곱≥4)"),
        Line2D([], [], color=GREY, marker="o", markersize=5, linewidth=1.8,
               markeredgecolor=PAPER, label="기준 미충족"),
    ]
    leg = fig.legend(handles=legend, loc="lower left", bbox_to_anchor=(0.035, 0.035),
                     frameon=False, fontsize=6.0, handlelength=1.8, ncol=2,
                     columnspacing=1.4)
    for text in leg.get_texts():
        text.set_color(INK_SOFT)

    fig.text(0.985, 0.045,
             "출처: eval/results/pharmasignal_cases.json (%s 실행), openFDA 데이터 기준일 2026-07-30"
             % generated_at[:10],
             fontsize=5.6, color=INK_FAINT, ha="right", va="center")

    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path, rows


def main() -> None:
    family = register_fonts()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    arch = make_architecture(FIG_DIR / "architecture_pharmasignal.png")
    res, rows = make_results(FIG_DIR / "results_pharmasignal.png")
    print(f"폰트 family: {family}")
    for path in (arch, res):
        import subprocess
        size = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
                              capture_output=True, text=True).stdout.strip().splitlines()[-2:]
        print(f"저장: {path.relative_to(ROOT)}  {' '.join(s.strip() for s in size)}")
    print(f"케이스 {len(rows)}건 반영:")
    for r in rows:
        print("  %-12s %-20s PRR=%.2f (%.2f~%.2f) labeled=%s pubmed=%d"
              % (r["drug"], r["reaction"], r["prr"], r["lo"], r["hi"], r["labeled"], r["pubmed"]))


if __name__ == "__main__":
    main()
