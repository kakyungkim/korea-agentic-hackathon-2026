"""제출용 그림 생성기.

  1) docs/figures/architecture_pipeline.png      파이프라인 구조와 크리틱 3단
  2) docs/figures/results_case.png               니라파립 두 경로 대조
  3) docs/figures/architecture_pharmasignal.png  PharmaSignal 데이터 흐름 도식
  4) docs/figures/results_pharmasignal.png       케이스 3건 PRR 포레스트 플롯

1) 과 2) 가 이번 제출용이고 3) 과 4) 는 PharmaSignal 도메인 자산으로 남겨 둔다.
수치는 전부 eval/results/ 의 결과 JSON 에서 읽는다(하드코딩 금지).
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
CASE_JSON = ROOT / "eval" / "results" / "case_niraparib.json"

DPI = 300

# 프로젝트 이름은 아직 확정되지 않았다. 확정되면 이 한 줄만 바꾼다.
# 파일 이름에는 넣지 않는다(architecture_pipeline.png, results_case.png).
PROJECT_NAME = "FlyGate"

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


# ---------------------------------------------------------------------------
# 그림 3: 파이프라인 아키텍처 (구조에서 사람까지, 크리틱 3단)
# ---------------------------------------------------------------------------
# 색 약속. 심사 1번 항목이 NVIDIA 기술 활용 심도라 NVIDIA 쪽을 한 색으로 몰아 둔다.
NVIDIA_C = GREEN          # NVIDIA NIM 과 Nemotron 과 NeMo Agent Toolkit
NVIDIA_BG = GREEN_BG
PUBLIC_C = BLUE           # 공개 API 와 외부 실측(FDDD, 초파리 커넥톰)
PUBLIC_BG = BLUE_BG

# 이름과 버전은 저장소 상태에서 가져온 것이다.
#   모델 이름과 도구 구성: docs/notes/topic-decision.md "도구 구성"
#   NeMo Agent Toolkit 버전: .venv 의 nvidia-nat 1.9.0 (pip show)
#   허용 호스트 7곳: docs/notes/topic-decision.md "도구 구성" 의 정책 항목
NAT_VERSION = "1.9.0"
MODEL_PLAN = "nemotron-3-super-120b-a12b"
MODEL_LOOP = "nemotron-3.5-lightning-30b-a3b"
MODEL_GATE = "nemotron-3.5-lightning"
MODEL_CRITIC = "nemotron-3-super-120b-a12b"
# 코드가 실제로 부르는 호스트만 적는다. 정책 파일과 일치해야 한다.
# BindingDB 참조는 bindingdb.org 를 직접 부르지 않고 FDDD 가 캡처해 둔 근거 요약을 읽는다.
ALLOWED_HOSTS = [
    "health.api.nvidia.com",
    "integrate.api.nvidia.com",
    "files.rcsb.org",
    "drug.flybrain.kr",
    "api.fda.gov",
    "dailymed.nlm.nih.gov",
    "eutils.ncbi.nlm.nih.gov",
]

# 네 번째 값은 구현 여부다. False 면 점선과 "계획" 표시로 그린다.
# 되지 않는 것을 되는 것처럼 그리지 않는다는 저장소 규율을 그림에도 적용한다.
BIND_TOOLS = [
    ("diffdock_nim", "NVIDIA NIM 포즈와 confidence", NVIDIA_C, True),
    ("vina_reference", "FDDD AutoDock Vina 실측", PUBLIC_C, True),
    ("flybrain_pose", "초파리 커넥톰 포즈 탐색", PUBLIC_C, False),
]
HUMAN_TOOLS = [
    ("openfda_faers", "FAERS 2x2 와 PRR", PUBLIC_C),
    ("dailymed_label", "라벨 기재와 PK", PUBLIC_C),
    ("pubmed_search", "문헌 건수와 PMID", PUBLIC_C),
    ("bindingdb_ref", "참조 친화도, 종점 4종 분리", PUBLIC_C),
]


def _tool_row(ax, x0, x1, cy, name, desc, color, h=1.9, implemented=True):
    """도구 한 줄. 왼쪽 색 칩과 배경으로 NVIDIA 와 공개 API 를 가른다.

    implemented 가 False 면 점선 테두리와 흐린 글자로 그리고 "계획" 태그를 붙인다.
    아직 등록되지 않은 도구를 등록된 것처럼 보이지 않게 하기 위한 것이다.
    """
    nvidia = color == NVIDIA_C
    box(ax, x0, cy - h / 2, x1 - x0, h,
        edge=NVIDIA_C if nvidia else ("#DFE4E8" if implemented else "#C9CFD5"),
        face=NVIDIA_BG if nvidia else PAPER,
        lw=0.9 if nvidia else 0.6, radius=0.55, shadow=False, z=5,
        ls="-" if implemented else (0, (3, 2)))
    ax.add_patch(Rectangle((x0 + 0.5, cy - h * 0.32), 0.55, h * 0.64,
                           facecolor=color, edgecolor="none", zorder=7))
    ax.text(x0 + 1.5, cy, name, ha="left", va="center", fontsize=5.2,
            fontweight="semibold", color=INK if implemented else "#8A939B", zorder=8)
    if implemented:
        ax.text(x1 - 0.6, cy, desc, ha="right", va="center", fontsize=4.6,
                color=INK_SOFT, zorder=8)
    else:
        # 미구현 행은 설명 대신 "계획" 만 오른쪽에 둔다. 이름과 겹치지 않게 하고
        # 등록된 도구와 한눈에 구분되게 한다.
        ax.text(x1 - 0.6, cy, "계획. 아직 NAT 에 등록 안 됨",
                ha="right", va="center", fontsize=4.4, color=BRICK,
                fontweight="semibold", zorder=8)


def make_pipeline_architecture(out_path: Path) -> Path:
    fig = plt.figure(figsize=(8.0, 5.2))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 65)
    ax.axis("off")

    ax.text(2.0, 62.2, f"{PROJECT_NAME} 파이프라인 구조", fontsize=13,
            fontweight="bold", color=INK)
    ax.text(2.0, 59.2,
            "타깃 구조와 후보 화합물에서 사람 근거까지 잇고, 각 단계에서 나올 수 없는 주장을 크리틱 3단이 반려한다.",
            fontsize=6.6, color=INK_SOFT)
    tag(ax, 76.0, 62.2, "NVIDIA 기술", color=NVIDIA_C, bg=NVIDIA_BG, size=5.2)
    tag(ax, 85.0, 62.2, "공개 API 와 외부 실측", color=PUBLIC_C, bg=PUBLIC_BG, size=5.2)

    # --- OpenShell 정책 경계 -------------------------------------------------
    bx0, by0, bx1, by1 = 16.5, 11.8, 98.6, 55.0
    ax.add_patch(
        FancyBboxPatch((bx0, by0), bx1 - bx0, by1 - by0,
                       boxstyle="round,pad=0,rounding_size=1.6",
                       linewidth=1.2, edgecolor=GREY, facecolor="#FBFCFD",
                       linestyle=(0, (5, 3)), zorder=1))
    ax.text(bx0 + 0.6, by1 + 1.5, "OpenShell 정책 경계", fontsize=7.0,
            fontweight="bold", color=INK_SOFT, va="center")
    ax.text(18.0, 53.2, "네트워크 deny-by-default. 쓰기는 /work/out 만",
            fontsize=5.0, color=INK_FAINT, ha="left", va="center", zorder=8)

    # --- 입력 ---------------------------------------------------------------
    box(ax, 0.8, 37.6, 14.4, 13.4, edge=GREY, face=GREY_BG)
    ax.text(8.0, 48.6, "입력", ha="center", va="center", fontsize=7.2,
            fontweight="bold", color=INK, zorder=8)
    ax.text(8.0, 45.9, "타깃 단백질 구조", ha="center", va="center", fontsize=5.7,
            color=INK_SOFT, zorder=8)
    ax.text(8.0, 43.9, "PDB 4R6E, 2P16", ha="center", va="center", fontsize=5.0,
            color=INK_FAINT, zorder=8)
    ax.text(8.0, 41.5, "후보 화합물 SMILES", ha="center", va="center", fontsize=5.7,
            color=INK_SOFT, zorder=8)
    ax.text(8.0, 39.5, "니라파립", ha="center", va="center", fontsize=5.0,
            color=INK_FAINT, zorder=8)
    arrow(ax, (15.2, 44.3), (17.8, 44.3))

    # --- 허용 호스트 목록 ----------------------------------------------------
    box(ax, 0.8, 14.6, 14.4, 17.0, edge=GREY, face=PAPER, lw=0.9,
        ls=(0, (4, 2.5)), shadow=False)
    ax.text(8.0, 29.9, "허용 호스트 7곳", ha="center", va="center", fontsize=5.8,
            fontweight="bold", color=INK_SOFT, zorder=8)
    for i, host in enumerate(ALLOWED_HOSTS):
        ax.text(8.0, 27.5 - i * 1.85, host, ha="center", va="center",
                fontsize=4.3, color=INK_FAINT, zorder=8)
    ax.text(8.0, 12.9, "그 밖은 차단되고 감사 로그에 남는다", ha="center", va="center",
            fontsize=4.7, color=BRICK, zorder=8)

    # --- 선택 게이트 ---------------------------------------------------------
    box(ax, 18.0, 37.6, 12.4, 13.4, edge=GREY, face=PAPER, lw=1.0,
        ls=(0, (4, 2.5)))
    ax.text(24.2, 48.6, "선택 게이트", ha="center", va="center", fontsize=6.8,
            fontweight="bold", color=INK, zorder=8)
    ax.text(24.2, 46.1, "후보 분류", ha="center", va="center", fontsize=5.5,
            color=INK_SOFT, zorder=8)
    ax.text(24.2, 44.3, "screen / skip / review", ha="center", va="center",
            fontsize=4.8, color=INK_FAINT, zorder=8)
    tag(ax, 24.2, 41.9, "jev_triage", color=PUBLIC_C, bg=PUBLIC_BG, size=4.8, ha="center")
    tag(ax, 24.2, 39.3, MODEL_GATE, color=NVIDIA_C, bg=NVIDIA_BG, size=4.3, ha="center")
    ax.text(24.2, 35.9, "점선은 생략 가능한 단계", ha="center", va="center",
            fontsize=4.7, color=INK_FAINT, zorder=8)
    arrow(ax, (30.4, 44.3), (32.2, 44.3))

    # --- 작성자 워크플로 -----------------------------------------------------
    box(ax, 32.4, 35.8, 16.2, 15.4, edge=NVIDIA_C, face=NVIDIA_BG, lw=1.1)
    ax.text(40.5, 49.4, "작성자 워크플로", ha="center", va="center", fontsize=7.2,
            fontweight="bold", color=INK, zorder=8)
    ax.text(40.5, 46.9, "계획", ha="center", va="center", fontsize=5.4,
            color=INK_SOFT, zorder=8)
    tag(ax, 40.5, 45.0, MODEL_PLAN, color=NVIDIA_C, bg=PAPER, size=4.3, ha="center")
    ax.text(40.5, 42.5, "반복", ha="center", va="center", fontsize=5.4,
            color=INK_SOFT, zorder=8)
    tag(ax, 40.5, 40.6, MODEL_LOOP, color=NVIDIA_C, bg=PAPER, size=4.1, ha="center")
    ax.text(40.5, 37.6, f"NeMo Agent Toolkit {NAT_VERSION}", ha="center",
            va="center", fontsize=5.0, color=INK_FAINT, zorder=8)
    arrow(ax, (48.6, 44.3), (50.4, 44.3))

    # --- 도구 층 -------------------------------------------------------------
    box(ax, 50.6, 30.0, 29.0, 24.2, edge=GREY, face="#F7F9FA", lw=1.0)
    ax.text(52.0, 52.6, "도구 층", ha="left", va="center", fontsize=7.0,
            fontweight="bold", color=INK, zorder=8)
    ax.text(78.2, 52.6, "NAT 함수로 등록", ha="right", va="center", fontsize=4.8,
            color=INK_FAINT, zorder=8)

    box(ax, 51.6, 42.6, 27.0, 9.0, edge="#E2E7EB", face=PAPER, lw=0.7,
        radius=0.8, shadow=False, z=3)
    ax.text(52.6, 50.5, "결합", ha="left", va="center", fontsize=5.8,
            fontweight="bold", color=INK_SOFT, zorder=8)
    for i, (name, desc, color, impl) in enumerate(BIND_TOOLS):
        _tool_row(ax, 52.4, 77.8, 48.3 - i * 2.05, name, desc, color, implemented=impl)

    box(ax, 51.6, 30.8, 27.0, 11.0, edge="#E2E7EB", face=PAPER, lw=0.7,
        radius=0.8, shadow=False, z=3)
    ax.text(52.6, 40.6, "사람 근거", ha="left", va="center", fontsize=5.8,
            fontweight="bold", color=INK_SOFT, zorder=8)
    for i, (name, desc, color) in enumerate(HUMAN_TOOLS):
        _tool_row(ax, 52.4, 77.8, 38.4 - i * 2.0, name, desc, color, h=1.8)
    arrow(ax, (79.6, 44.3), (81.4, 44.3))

    # --- 경계 밖 호출 차단 ---------------------------------------------------
    arrow(ax, (65.0, 54.4), (65.0, 55.6), color=BRICK, lw=1.0, ls=(0, (3, 2)))
    icon_block(ax, 65.0, 56.6, BRICK, r=1.0)
    ax.text(66.8, 56.6, "허용 밖 호스트 요청은 경계에서 막힌다", ha="left",
            va="center", fontsize=5.0, color=BRICK, zorder=8)

    # --- 근거 ID 붙은 주장 JSON ---------------------------------------------
    box(ax, 81.6, 37.6, 16.4, 13.4, edge=SAND, face=SAND_BG, lw=1.1)
    ax.text(89.8, 48.8, "근거 ID 붙은", ha="center", va="center", fontsize=6.4,
            fontweight="bold", color=INK, zorder=8)
    ax.text(89.8, 46.6, "주장 JSON", ha="center", va="center", fontsize=6.4,
            fontweight="bold", color=INK, zorder=8)
    for i, line in enumerate((
            "dock:vina:<sha256>",
            "dock:diffdock:<req>:pose1",
            "bindingdb:<uniprot>",
            "faers:2x2:<drug>-<event>",
            "dailymed:setid, pubmed:<pmid>")):
        ax.text(89.8, 44.3 - i * 1.45, line, ha="center", va="center",
                fontsize=4.2, color=INK_SOFT, zorder=8)
    arrow(ax, (89.8, 37.6), (89.8, 28.9))

    # --- 크리틱 3단 ----------------------------------------------------------
    box(ax, 18.0, 12.5, 78.6, 16.1, edge=PLUM, face=PLUM_BG, lw=1.3)
    ax.text(19.4, 27.0, "크리틱 3단", ha="left", va="center", fontsize=7.4,
            fontweight="bold", color=INK, zorder=8)
    ax.text(95.2, 27.0, "별도 워크플로 critic.yml. 크리틱에 쓰기 도구 없음",
            ha="right", va="center", fontsize=5.0, color=INK_FAINT, zorder=8)

    box(ax, 19.4, 13.6, 44.6, 11.6, edge=GREY, face=PAPER, lw=0.9,
        radius=0.8, shadow=False, z=3)
    ax.text(20.6, 24.1, "비-LLM. 고정된 규칙과 계산", ha="left", va="center",
            fontsize=5.6, fontweight="bold", color=INK_SOFT, zorder=8)

    stage_left = [
        (20.4, 41.0, "1단 결정 규칙",
         ["주장 존재와 근거 ID 유무", "빈 문자열 점검"]),
        (42.2, 62.8, "2단 숫자 오라클",
         ["포즈 점수와 로그 대조", "SHA256 확인, PRR 재계산"]),
    ]
    for x0, x1, title, lines in stage_left:
        box(ax, x0, 14.4, x1 - x0, 8.4, edge=GREY, face=GREY_BG, lw=0.8,
            radius=0.7, shadow=False, z=5)
        cx = (x0 + x1) / 2
        ax.text(cx, 21.4, title, ha="center", va="center", fontsize=6.2,
                fontweight="bold", color=INK, zorder=8)
        for i, line in enumerate(lines):
            ax.text(cx, 19.2 - i * 1.8, line, ha="center", va="center",
                    fontsize=5.0, color=INK_SOFT, zorder=8)
        ax.text(cx, 15.6, "모델을 부르지 않는다", ha="center", va="center",
                fontsize=4.7, color=INK_FAINT, zorder=8)

    box(ax, 65.4, 13.6, 29.8, 11.6, edge=PLUM, face=PAPER, lw=1.6,
        radius=0.8, z=3)
    ax.text(80.3, 23.4, "3단 과잉해석 LLM 판정", ha="center", va="center",
            fontsize=6.6, fontweight="bold", color=INK, zorder=8)
    tag(ax, 80.3, 21.0, MODEL_CRITIC, color=PLUM, bg=PLUM_BG, size=4.4, ha="center")
    ax.text(80.3, 18.7, "근거 ID 와 숫자가 맞아도", ha="center", va="center",
            fontsize=5.0, color=INK_SOFT, zorder=8)
    ax.text(80.3, 17.1, "추론이 틀린 주장을 반려한다", ha="center", va="center",
            fontsize=5.0, color=INK_SOFT, zorder=8)
    ax.text(80.3, 15.0, "과잉해석 규칙 14종", ha="center", va="center",
            fontsize=5.4, fontweight="semibold", color=PLUM, zorder=8)

    arrow(ax, (30.0, 12.5), (30.0, 9.1), color=TEAL)
    ax.text(30.8, 10.8, "통과", ha="left", va="center", fontsize=5.6,
            fontweight="semibold", color=TEAL, zorder=8)
    arrow(ax, (84.0, 12.5), (84.0, 9.1), color=BRICK)
    ax.text(84.8, 10.8, "반려", ha="left", va="center", fontsize=5.6,
            fontweight="semibold", color=BRICK, zorder=8)

    # --- 결과 ---------------------------------------------------------------
    box(ax, 18.0, 1.7, 34.0, 7.2, edge=TEAL, face=TEAL_BG)
    icon_person(ax, 22.2, 5.2, TEAL)
    ax.text(25.2, 6.5, "사람 검토로 전달", ha="left", va="center", fontsize=6.6,
            fontweight="bold", color=INK, zorder=8)
    ax.text(25.2, 3.7, "근거 ID 가 붙은 주장만 넘어간다", ha="left", va="center",
            fontsize=5.2, color=INK_SOFT, zorder=8)

    box(ax, 62.6, 1.7, 34.0, 7.2, edge=BRICK, face=BRICK_BG)
    ax.text(79.6, 6.5, "사유 원문과 함께 반려", ha="center", va="center",
            fontsize=6.6, fontweight="bold", color=INK, zorder=8)
    ax.text(79.6, 3.7, "어느 규칙을 어겼는지 적어 작성자에게 되돌린다",
            ha="center", va="center", fontsize=5.2, color=INK_SOFT, zorder=8)

    ax.text(98.6, 0.7,
            "출처: docs/notes/topic-decision.md(도구 구성과 규칙 14종), configs/author.yml, configs/critic.yml, nvidia-nat "
            + NAT_VERSION,
            ha="right", va="center", fontsize=4.6, color=INK_FAINT)

    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# 그림 4: 케이스 결과 (니라파립 두 경로 대조)
# ---------------------------------------------------------------------------
class CaseKeyError(RuntimeError):
    """케이스 JSON 에 그림이 요구하는 키가 없을 때. 그리지 않고 멈춘다."""


_MISSING = object()


def _dig(payload, dotted: str):
    """'paths.0.steps.vina.score_kcal_mol' 처럼 점으로 이어진 경로를 따라간다."""
    cur = payload
    for part in dotted.split("."):
        if isinstance(cur, list):
            if not part.isdigit() or int(part) >= len(cur):
                return _MISSING
            cur = cur[int(part)]
            continue
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def load_case(path: Path) -> dict:
    """케이스 JSON 에서 그림에 쓰는 값만 꺼낸다.

    하나라도 없으면 무엇이 없는지 모두 모아 알리고 그리지 않는다.
    """
    if not path.exists():
        raise CaseKeyError(f"케이스 파일이 없습니다: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))

    missing: list[str] = []

    def need(dotted: str):
        value = _dig(payload, dotted)
        if value is _MISSING:
            missing.append(dotted)
            return None
        return value

    case = {
        "case_id": need("case_id"),
        "generated_at": need("generated_at"),
        "compound": need("compound.name"),
        "event": need("compound.adverse_event"),
        "event_ko": need("compound.adverse_event_ko"),
        "fddd_sha256": need("sources.fddd_docking_sha256"),
        "paths": [],
        "critic": {},
    }

    for i in (0, 1):
        p = f"paths.{i}"
        case["paths"].append({
            "path": need(f"{p}.path"),
            "title": need(f"{p}.title"),
            "pdb_id": need(f"{p}.pdb_id"),
            "chain": need(f"{p}.chain"),
            "vina_score": need(f"{p}.steps.vina.score_kcal_mol"),
            "vina_units": need(f"{p}.steps.vina.units"),
            "vina_role": need(f"{p}.steps.vina.role"),
            "diffdock": need(f"{p}.steps.diffdock.position_confidence"),
            "bdb_present": need(f"{p}.steps.bindingdb.reference_set_present"),
            "bdb_records": _none(_dig(payload, f"{p}.steps.bindingdb.record_count")),
            "bdb_compounds": _none(_dig(payload, f"{p}.steps.bindingdb.compound_count")),
            "bdb_uniprot": need(f"{p}.steps.bindingdb.uniprot"),
            "bdb_endpoints": need(f"{p}.steps.bindingdb.endpoint_counts"),
            "labeled": need(f"{p}.steps.label.labeled"),
            "label_sections": need(f"{p}.steps.label.mentioned_sections"),
            "prr": need(f"{p}.steps.faers.prr"),
            "prr_ci95": need(f"{p}.steps.faers.prr_ci95"),
            "faers_a": need(f"{p}.steps.faers.counts.a"),
            "faers_asof": need(f"{p}.steps.faers.data_last_updated"),
            "pubmed_total": need(f"{p}.steps.pubmed.total_count"),
            "pubmed_pmid": need(f"{p}.steps.pubmed.representative_pmid"),
        })

    for key in ("supported", "overclaim"):
        c = f"critic_verdicts.{key}"
        case["critic"][key] = {
            "final": need(f"{c}.final_verdict"),
            "stage1_passed": need(f"{c}.stage1.rules_passed"),
            "stage1_checks": need(f"{c}.stage1.checks"),
            "stage2_ok": need(f"{c}.stage2.ok"),
            "stage2_line": need(f"{c}.stage2.summary_line"),
            "stage3_verdict": need(f"{c}.stage3.verdict"),
            "stage3_checks": need(f"{c}.stage3.checks"),
            "stage3_model": need(f"{c}.stage3.model"),
            "claims": need(f"claim_sets.{key}.claims"),
        }

    if missing:
        raise CaseKeyError(
            "케이스 JSON 에 없는 키가 있어 그림을 그리지 않습니다: "
            + ", ".join(missing) + f"  (파일 {path})")
    return case


def _none(value):
    return None if value is _MISSING else value


def _fmt_conf(value: float) -> str:
    return ("%.3f" % value).replace("-", "−")


def make_case_results(out_path: Path) -> tuple[Path, dict]:
    case = load_case(CASE_JSON)
    a, b = case["paths"]
    crit = case["critic"]

    fig = plt.figure(figsize=(8.0, 6.2))
    H = 77.5

    def rect(x0, y0, x1, y1):
        return [x0 / 100.0, y0 / H, (x1 - x0) / 100.0, (y1 - y0) / H]

    # --- 결합 1: Vina 막대 --------------------------------------------------
    ax_vina = fig.add_axes(rect(13.5, 49.0, 99.0, 62.0))
    scores = [a["vina_score"], b["vina_score"]]
    floor = min(scores) * 1.18
    ax_vina.set_xlim(0, 1)
    ax_vina.set_ylim(floor, 0)
    ax_vina.set_xticks([])
    for spine in ("top", "right", "bottom"):
        ax_vina.spines[spine].set_visible(False)
    ax_vina.spines["left"].set_color(GREY)
    ax_vina.spines["left"].set_linewidth(0.7)
    ticks = [0, -2, -4, -6, -8, -10]
    ax_vina.set_yticks([t for t in ticks if t >= floor])
    ax_vina.set_yticklabels(["%g" % t for t in ticks if t >= floor],
                            fontsize=5.4, color=INK_SOFT)
    ax_vina.tick_params(axis="y", length=2.0, color=GREY, pad=1.5)
    ax_vina.grid(axis="y", color="#EEF1F3", linewidth=0.6, zorder=0)
    ax_vina.set_axisbelow(True)
    ax_vina.axhline(0, color=INK_FAINT, linewidth=0.9, zorder=3)

    centers = (0.2456, 0.7544)
    colors = (BLUE, GREY)
    for cx, score, color in zip(centers, scores, colors):
        ax_vina.bar(cx, score, width=0.13, color=color, edgecolor="none", zorder=4)
        ax_vina.text(cx, score - abs(floor) * 0.055, "%.3f" % score, ha="center",
                     va="top", fontsize=7.4, fontweight="bold", color=color,
                     zorder=6)
        ax_vina.text(cx, score - abs(floor) * 0.140, "kcal/mol", ha="center",
                     va="top", fontsize=5.0, color=INK_FAINT, zorder=6)

    # --- 결합 2: DiffDock 신뢰도 -------------------------------------------
    ax_dd = fig.add_axes(rect(13.5, 34.6, 99.0, 46.8))
    ax_dd.set_xlim(0, 1)
    conf_all = list(a["diffdock"]) + list(b["diffdock"])
    lim = max(abs(min(conf_all)), abs(max(conf_all))) * 1.45
    ax_dd.set_ylim(-lim, lim)
    ax_dd.set_xticks([])
    for spine in ("top", "right", "bottom"):
        ax_dd.spines[spine].set_visible(False)
    ax_dd.spines["left"].set_color(GREY)
    ax_dd.spines["left"].set_linewidth(0.7)
    dd_ticks = [-0.8, -0.4, 0.0, 0.4, 0.8]
    ax_dd.set_yticks(dd_ticks)
    ax_dd.set_yticklabels([("%.1f" % t).replace("-", "−") for t in dd_ticks],
                          fontsize=5.4, color=INK_SOFT)
    ax_dd.tick_params(axis="y", length=2.0, color=GREY, pad=1.5)
    ax_dd.grid(axis="y", color="#EEF1F3", linewidth=0.6, zorder=0)
    ax_dd.set_axisbelow(True)
    ax_dd.axhline(0, color=INK_SOFT, linewidth=1.0, zorder=5)

    for cx, confs in zip(centers, (a["diffdock"], b["diffdock"])):
        for j, value in enumerate(confs):
            px = cx + (j - 1) * 0.078
            color = BLUE if value >= 0 else BRICK
            ax_dd.bar(px, value, width=0.058, color=color, edgecolor="none", zorder=4)
            off = lim * 0.07
            ax_dd.text(px, value + (off if value >= 0 else -off),
                       _fmt_conf(value), ha="center",
                       va="bottom" if value >= 0 else "top", fontsize=5.2,
                       fontweight="semibold", color=color, zorder=6)

    # --- 배경 도화지 (마지막에 얹어 안내선과 상자를 위로 둔다) --------------
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.patch.set_visible(False)

    ax.text(2.0, 74.6, f"{PROJECT_NAME} 케이스: 니라파립 두 경로 대조", fontsize=13,
            fontweight="bold", color=INK)
    ax.text(2.0, 71.5,
            "같은 화합물을 같은 도구로 두 번 돌렸다. 두 경로를 가른 것은 점수 차이가 아니라 그 점수를 받쳐 줄 실험 근거의 유무다.",
            fontsize=6.6, color=INK_SOFT)

    # 경로 머리
    box(ax, 13.5, 63.4, 42.0, 5.2, edge=BLUE, face=BLUE_BG, lw=1.0, radius=0.7)
    ax.text(34.5, 66.9, "경로 A. %s" % a["title"], ha="center", va="center",
            fontsize=6.8, fontweight="bold", color=INK, zorder=8)
    ax.text(34.5, 64.8, "PDB %s chain %s, role %s" % (a["pdb_id"], a["chain"], a["vina_role"]),
            ha="center", va="center", fontsize=4.6, color=INK_FAINT, zorder=8)
    box(ax, 57.0, 63.4, 42.0, 5.2, edge=GREY, face=GREY_BG, lw=1.0, radius=0.7)
    ax.text(78.0, 66.9, "경로 B. %s" % b["title"], ha="center", va="center",
            fontsize=6.8, fontweight="bold", color=INK, zorder=8)
    ax.text(78.0, 64.8, "PDB %s chain %s, role %s" % (b["pdb_id"], b["chain"], b["vina_role"]),
            ha="center", va="center", fontsize=4.6, color=INK_FAINT, zorder=8)

    # 왼쪽 단계 이름
    rows = [
        (56.5, "결합 1", ["AutoDock Vina 실측", "kcal/mol, 1순위 포즈"]),
        (41.5, "결합 2", ["DiffDock NIM", "position_confidence", "포즈 3개"]),
        (29.8, "참조", ["BindingDB", "실험 친화도"]),
        (18.4, "사람", ["라벨, FAERS, 문헌"]),
        (7.2, "크리틱", ["3단 판정"]),
    ]
    for cy, name, subs in rows:
        ax.text(9.8, cy, name, ha="right", va="center", fontsize=6.4,
                fontweight="bold", color=INK, zorder=8)
        for i, line in enumerate(subs):
            ax.text(9.8, cy - 2.2 - i * 1.7, line, ha="right", va="center",
                    fontsize=4.7, color=INK_FAINT, zorder=8)

    # 두 경로를 가르는 선과 교차 비교 금지 경고
    ax.add_line(Line2D([56.25, 56.25], [24.6, 62.4], color="#D7DCE1",
                       linewidth=0.9, linestyle=(0, (2, 2.6)), zorder=3))
    icon_block(ax, 56.25, 57.6, BRICK, r=1.35)
    ax.text(56.25, 54.3, "서로 다른 단백질", ha="center", va="center", fontsize=5.4,
            fontweight="bold", color=BRICK, zorder=9,
            bbox=dict(boxstyle="round,pad=0.30", facecolor=PAPER, edgecolor=BRICK,
                      linewidth=0.6))
    ax.text(56.25, 51.4, "교차 비교 불가", ha="center", va="center", fontsize=5.4,
            fontweight="bold", color=BRICK, zorder=9,
            bbox=dict(boxstyle="round,pad=0.30", facecolor=PAPER, edgecolor=BRICK,
                      linewidth=0.6))
    ax.text(13.5, 47.9, "두 막대는 같은 눈금이지만 같은 자리에서 잰 값이 아니다",
            ha="left", va="center", fontsize=4.8, color=INK_FAINT, zorder=8)

    # DiffDock 주석
    ax.text(14.6, 38.4, "음수는 확률이 아니라 로짓 척도로 읽는다. 친화도로 환산하지 않는다.",
            ha="left", va="center", fontsize=4.9, color=INK_SOFT, zorder=8)
    ax.text(14.6, 36.6, "음수가 결합하지 않는다는 증거는 아니다.",
            ha="left", va="center", fontsize=4.9, color=INK_SOFT, zorder=8)

    # --- 참조 집합 ----------------------------------------------------------
    box(ax, 13.5, 24.9, 42.0, 7.4, edge=BLUE, face=PAPER, lw=0.9, radius=0.7,
        shadow=False)
    ax.text(34.5, 30.3, "레코드 %s건, 화합물 %s종" % (f"{a['bdb_records']:,}",
                                                f"{a['bdb_compounds']:,}"),
            ha="center", va="center", fontsize=6.6, fontweight="bold",
            color=INK, zorder=8)
    ep = a["bdb_endpoints"]
    ax.text(34.5, 27.9, "UniProt %s. 종점 %s" % (
        a["bdb_uniprot"],
        ", ".join("%s %s" % (k, f"{v:,}") for k, v in ep.items())),
        ha="center", va="center", fontsize=4.5, color=INK_SOFT, zorder=8)
    ax.text(34.5, 26.1, "네 종점을 하나의 친화도로 합치지 않는다", ha="center",
            va="center", fontsize=4.5, color=INK_FAINT, zorder=8)

    box(ax, 57.0, 24.9, 42.0, 7.4, edge=BRICK, face=PAPER, lw=1.1, radius=0.7,
        ls=(0, (4, 2.5)), shadow=False)
    ax.text(78.0, 30.0, "참조 집합 없음", ha="center", va="center", fontsize=7.2,
            fontweight="bold", color=BRICK, zorder=8)
    ax.text(78.0, 27.4, "응고인자 Xa 에 대응하는 참조 친화도 집합이 이 실행에 없다",
            ha="center", va="center", fontsize=4.8, color=INK_SOFT, zorder=8)
    ax.text(78.0, 25.8, "이 공백이 두 경로를 가른다", ha="center", va="center",
            fontsize=5.0, fontweight="semibold", color=BRICK, zorder=8)

    # --- 사람 근거 ----------------------------------------------------------
    same_human = (a["prr"] == b["prr"] and a["labeled"] == b["labeled"]
                  and a["pubmed_total"] == b["pubmed_total"])
    box(ax, 13.5, 13.9, 85.5, 9.3, edge=SAND, face=SAND_BG, lw=1.1)
    head = "두 경로에 같은 값" if same_human else "경로 A 기준. 두 경로의 값이 갈렸다"
    ax.text(15.0, 21.6, head, ha="left", va="center", fontsize=6.2,
            fontweight="bold", color=INK, zorder=8)
    ax.text(97.5, 21.6, "화합물 단위 근거라 타깃을 가리지 않는다", ha="right",
            va="center", fontsize=5.0, color=INK_SOFT, zorder=8)
    lo, hi = a["prr_ci95"]
    sec_ko = {"boxed_warning": "박스 경고",
              "warnings_and_precautions": "경고와 주의",
              "adverse_reactions": "이상반응"}
    human_cols = [
        (28.0, "FAERS PRR %.2f" % a["prr"],
         "95%% CI %.2f~%.2f" % (lo, hi),
         "동반보고 %s건" % f"{a['faers_a']:,}"),
        (56.0, "라벨 기재 있음" if a["labeled"] else "라벨 미기재",
         ", ".join(sec_ko.get(s, s) for s in a["label_sections"]),
         "ZEJULA SPL"),
        (84.0, "문헌 %s건" % f"{a['pubmed_total']:,}",
         "niraparib AND Thrombocytopenia",
         "대표 PMID %s" % a["pubmed_pmid"]),
    ]
    for cx, line1, line2, line3 in human_cols:
        ax.text(cx, 19.1, line1, ha="center", va="center", fontsize=6.2,
                fontweight="bold", color=INK, zorder=8)
        ax.text(cx, 17.1, line2, ha="center", va="center", fontsize=4.9,
                color=INK_SOFT, zorder=8)
        ax.text(cx, 15.4, line3, ha="center", va="center", fontsize=4.6,
                color=INK_FAINT, zorder=8)

    # --- 크리틱 3단 판정 ----------------------------------------------------
    sup, over = crit["supported"], crit["overclaim"]
    stage1_both = bool(sup["stage1_passed"]) and bool(over["stage1_passed"])
    stage2_both = bool(sup["stage2_ok"]) and bool(over["stage2_ok"])
    n_checks1 = len(sup["stage1_checks"])
    n_reject = sum(1 for c in over["stage3_checks"] if not c.get("passed"))
    n_pass3 = sum(1 for c in sup["stage3_checks"] if c.get("passed"))

    box(ax, 13.5, 1.9, 85.5, 10.4, edge=PLUM, face=PLUM_BG, lw=1.3)
    box(ax, 15.0, 2.9, 25.0, 8.0, edge=GREY, face=PAPER, lw=0.8, radius=0.7,
        shadow=False, z=4)
    ax.text(27.5, 9.4, "1단 결정 규칙", ha="center", va="center", fontsize=6.0,
            fontweight="bold", color=INK, zorder=8)
    icon_check(ax, 21.6, 7.2, TEAL, scale=0.9)
    ax.text(23.0, 7.2, "양쪽 통과. 점검 %d/%d" % (n_checks1, n_checks1) if stage1_both
            else "통과하지 못함", ha="left", va="center", fontsize=5.3,
            fontweight="semibold", color=TEAL if stage1_both else BRICK, zorder=8)
    ax.text(27.5, 4.8, "비-LLM 고정 규칙", ha="center", va="center", fontsize=4.7,
            color=INK_FAINT, zorder=8)

    box(ax, 41.5, 2.9, 25.0, 8.0, edge=GREY, face=PAPER, lw=0.8, radius=0.7,
        shadow=False, z=4)
    ax.text(54.0, 9.4, "2단 숫자 오라클", ha="center", va="center", fontsize=6.0,
            fontweight="bold", color=INK, zorder=8)
    icon_check(ax, 44.6, 7.2, TEAL, scale=0.9)
    ax.text(46.0, 7.2, "양쪽 통과. %s" % sup["stage2_line"] if stage2_both
            else "통과하지 못함", ha="left", va="center", fontsize=5.3,
            fontweight="semibold", color=TEAL if stage2_both else BRICK, zorder=8)
    ax.text(54.0, 4.8, "비-LLM 계산", ha="center", va="center", fontsize=4.7,
            color=INK_FAINT, zorder=8)

    box(ax, 68.0, 2.9, 29.5, 8.0, edge=BRICK, face=PAPER, lw=1.7, radius=0.7, z=4)
    ax.text(82.7, 9.7, "3단 과잉해석 LLM 판정", ha="center", va="center",
            fontsize=6.4, fontweight="bold", color=INK, zorder=8)
    ax.text(82.7, 7.6, "뒷받침 요약 %d건: 통과 (점검 %d건)"
            % (len(sup["claims"]), n_pass3), ha="center", va="center",
            fontsize=5.1, color=TEAL, zorder=8)
    ax.text(82.7, 5.5, "과잉해석 요약 %d건: 반려" % n_reject, ha="center",
            va="center", fontsize=6.4, fontweight="bold", color=BRICK, zorder=8)
    ax.text(82.7, 3.6, "1단과 2단을 통과한 주장을 3단만 잡았다", ha="center",
            va="center", fontsize=4.7, color=INK_FAINT, zorder=8)

    ax.text(99.0, 0.7,
            "출처: eval/results/%s.json (%s 실행). FAERS 데이터 기준일 %s. Vina 실측은 FDDD 도킹 매니페스트 %s, DiffDock 는 NVIDIA NIM 호출."
            % (case["case_id"], case["generated_at"][:10], a["faers_asof"],
               case["fddd_sha256"][:8]),
            ha="right", va="center", fontsize=4.5, color=INK_FAINT)

    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    return out_path, case


def main() -> None:
    family = register_fonts()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    pipeline = make_pipeline_architecture(FIG_DIR / "architecture_pipeline.png")
    case_fig, case = make_case_results(FIG_DIR / "results_case.png")
    arch = make_architecture(FIG_DIR / "architecture_pharmasignal.png")
    res, rows = make_results(FIG_DIR / "results_pharmasignal.png")

    print(f"폰트 family: {family}")
    print(f"프로젝트 이름 자리표시자: {PROJECT_NAME}")
    for path in (pipeline, case_fig, arch, res):
        import subprocess
        size = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
                              capture_output=True, text=True).stdout.strip().splitlines()[-2:]
        print(f"저장: {path.relative_to(ROOT)}  {' '.join(s.strip() for s in size)}")

    a, b = case["paths"]
    over = case["critic"]["overclaim"]
    print(f"케이스 {case['case_id']} ({case['generated_at']}) 반영:")
    print("  경로 A %s %s: Vina %.3f, DiffDock %s"
          % (a["path"], a["pdb_id"], a["vina_score"],
             ", ".join("%.3f" % v for v in a["diffdock"])))
    print("  경로 B %s %s: Vina %.3f, DiffDock %s"
          % (b["path"], b["pdb_id"], b["vina_score"],
             ", ".join("%.3f" % v for v in b["diffdock"])))
    print("  BindingDB 경로 A 레코드 %s 화합물 %s, 경로 B 참조 집합 %s"
          % (a["bdb_records"], a["bdb_compounds"],
             "있음" if b["bdb_present"] else "없음"))
    print("  사람 근거 PRR %.2f (%.2f~%.2f), 라벨 %s, 문헌 %d건"
          % (a["prr"], a["prr_ci95"][0], a["prr_ci95"][1],
             "기재" if a["labeled"] else "미기재", a["pubmed_total"]))
    print("  크리틱 3단 과잉해석 반려 %d건"
          % sum(1 for c in over["stage3_checks"] if not c.get("passed")))

    print(f"PharmaSignal 케이스 {len(rows)}건 반영:")
    for r in rows:
        print("  %-12s %-20s PRR=%.2f (%.2f~%.2f) labeled=%s pubmed=%d"
              % (r["drug"], r["reaction"], r["prr"], r["lo"], r["hi"], r["labeled"], r["pubmed"]))


if __name__ == "__main__":
    main()
