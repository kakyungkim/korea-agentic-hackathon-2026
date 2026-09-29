"""Shared drawing vocabulary for the graphical abstracts.

Three papers come out of one study, so their graphical abstracts have to read as a set:
same header band, same card shape, same palette, same meaning for each colour. Keeping
that in one module is also what stops the three scripts from drifting apart when a number
changes in one of them.

Colour carries meaning and is not decoration:
    BLUE   the pipeline and its outputs
    RED    what we are warning about (leakage, masking, a claim that overreaches)
    GREEN  something that holds up under checking
    SAND   partial coverage
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle, Wedge

ROOT = Path(__file__).resolve().parents[2]
FIGS = ROOT / "docs" / "figures"

INK, SUB, HAIR = "#1d242b", "#7b848c", "#dcd9d3"
BLUE, RED, GREEN, SAND = "#35618f", "#a4404e", "#4a7c59", "#b3944f"
CARD, WASH = "#ffffff", "#f6f4f0"


def use_pretendard() -> None:
    for ttf in (FIGS / "fonts").glob("Pretendard-*.ttf"):
        font_manager.fontManager.addfont(str(ttf))
    plt.rcParams["font.family"] = "Pretendard"
    plt.rcParams["axes.unicode_minus"] = False


def canvas(w: float = 15.6, h: float = 7.4):
    use_pretendard()
    fig, ax = plt.subplots(figsize=(w, h), dpi=300)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def header(ax, title: str, right: str) -> None:
    ax.add_patch(Rectangle((0, 0.935), 1, 0.065, fc=INK, ec="none", zorder=1))
    ax.text(0.018, 0.9665, title, fontsize=15, color="white", fontweight="bold",
            va="center", zorder=3)
    ax.text(0.982, 0.9665, right, fontsize=10.5, color="#b9c2ca", va="center",
            ha="right", zorder=3)


def columns(ax, labels: list[tuple[float, str]], rules: list[float]) -> None:
    for x, lab in labels:
        ax.text(x, 0.895, lab, fontsize=11, color=INK, fontweight="bold", va="center")
    for x in rules:
        ax.plot([x, x], [0.055, 0.905], color=HAIR, lw=1.0, zorder=1)


def card(ax, x, y, w, h, ec=HAIR, fc=CARD, lw=1.1, z=2, r=0.008) -> None:
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


def arrow(ax, a, b, color=SUB, lw=1.8, ms=12, style="-|>", rad=0.0, z=4) -> None:
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=ms, color=color,
                                 lw=lw, zorder=z, shrinkA=0, shrinkB=0,
                                 connectionstyle=f"arc3,rad={rad}"))


def ring(ax, cx, cy, r, frac, color) -> None:
    ax.add_patch(Circle((cx, cy), r, fc="none", ec="#e8e4dd", lw=3.4, zorder=3))
    ax.add_patch(Wedge((cx, cy), r + 0.0018, 90, 90 - 360 * frac, width=0.0036,
                       fc=color, ec=color, lw=3.4, zorder=4))


def redact(ax, x, y, w, h=0.020) -> None:
    """A black bar standing in for a removed entity name."""
    ax.add_patch(Rectangle((x, y), w, h, fc=INK, ec="none", zorder=4))


def conclusion(ax, x, y, w, h, lines: str, fs=8.5) -> None:
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.008",
                                fc=WASH, ec=HAIR, lw=1.0, zorder=2))
    ax.text(x + 0.016, y + h - 0.022, "결론", fontsize=8.4, color=SUB, fontweight="bold")
    ax.text(x + 0.016, y + h - 0.044, lines, fontsize=fs, color=INK, va="top",
            linespacing=1.6)


def save(fig, name: str) -> None:
    out = FIGS / name
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor="white", pad_inches=0.06)
    print(f"{out.relative_to(ROOT)}  {out.stat().st_size // 1024} KB")
