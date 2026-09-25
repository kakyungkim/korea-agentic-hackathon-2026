#!/usr/bin/env python3
# 이식 출처: AgentForgeAI(2026-08 Agent Forge AI Hackathon) 의 scripts/record_demo.py
# 이식 시각: 2026-09-25
# 바꾼 것: 그대로 가져왔다. 실행하는 명령이 v1 CLI(pharmasignal.cli)라 이 저장소 진입점으로 바꿔야 한다.
"""데모 영상 생성 — 파이프라인 출력을 터미널 화면으로 렌더해 mp4로 만든다.

  python scripts/record_demo.py "antibody-drug conjugate"

화면 녹화는 권한과 창 배치가 필요해 자동화가 어렵다. 대신 파이프라인을 실제로
돌려 그 출력을 그대로 받아, 터미널처럼 한 줄씩 흘러가는 화면으로 렌더한다.
출력은 실행 결과 그대로이므로 꾸며낸 화면이 아니다.

[해커톤 이후 업데이트 2026-08-22] 제출물만으로 거르는 1차 관문에서는 정적
슬라이드보다 짧은 영상이 낫다는 것을 확인해 추가했다.

의존: Pillow, ffmpeg, 한글 고정폭 폰트(D2Coding 권장).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "video"

# 터미널 느낌의 어두운 팔레트
BG, FG, DIM = (15, 20, 24), (238, 243, 246), (147, 164, 177)
ACCENT, WARN, INFO = (79, 209, 165), (240, 119, 108), (91, 141, 239)

W, H = 1280, 720
PAD, LINE_H, FONT_SIZE = 28, 22, 15
ROWS = (H - PAD * 2) // LINE_H
FPS = 30
LINES_PER_FRAME = 0.09       # 초당 약 2.7줄. 눈으로 따라 읽을 수 있는 속도
HOLD_SEC = 4                   # 마지막 화면을 이만큼 붙잡는다

FONT_CANDIDATES = [
    Path.home() / "Downloads/나눔 글꼴/D2coding/D2CodingAll/D2Coding-Ver1.3.2-20180524-all.ttc",
    Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
    Path("/System/Library/Fonts/SFNSMono.ttf"),
]


def _font() -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), FONT_SIZE)
            except Exception:
                continue
    raise SystemExit("한글 고정폭 폰트를 찾지 못했다. D2Coding을 설치할 것.")


def _color(line: str) -> tuple[int, int, int]:
    """줄 내용에 따라 색을 고른다. 실제 화면과 같은 규칙."""
    if line.startswith("$ "):
        return ACCENT
    if "─" in line or "---" in line or line.strip().startswith("|"):
        return DIM
    if "실행" in line and "제공자" not in line:
        return ACCENT
    if "폴백" in line or "건너뜀" in line or "실패" in line:
        return WARN
    if line.lstrip().startswith("["):
        return INFO
    if line.startswith("    |") or line.strip().startswith("-"):
        return DIM
    return FG


def run_pipeline(topic: str, limit: int) -> list[str]:
    """파이프라인을 실제로 돌려 출력을 줄 단위로 받는다."""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "code" / "src"), PYTHONUNBUFFERED="1")
    cmd = [sys.executable, "-m", "pharmasignal.cli", "run", topic, "--limit", str(limit)]
    print(f"파이프라인 실행 중: {' '.join(cmd[-4:])}")
    proc = subprocess.run(cmd, cwd=ROOT / "code", env=env,
                          capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).splitlines()
    return [f"$ pharmasignal run \"{topic}\" --limit {limit}", ""] + out


def render(lines: list[str], out: Path, topic: str) -> Path:
    font = _font()
    frames_dir = Path(tempfile.mkdtemp(prefix="pharmasignal-frames-"))
    total = len(lines)
    n_frames = int(total / LINES_PER_FRAME) + FPS * HOLD_SEC
    print(f"프레임 렌더 중: {n_frames}장 ({total}줄)")

    for i in range(n_frames):
        shown = min(total, int((i + 1) * LINES_PER_FRAME))
        window = lines[max(0, shown - ROWS):shown]
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        # 상단 창 장식
        d.rectangle([0, 0, W, 26], fill=(22, 29, 35))
        for k, c in enumerate([(240, 119, 108), (232, 176, 75), (79, 209, 165)]):
            d.ellipse([16 + k * 18, 9, 26 + k * 18, 19], fill=c)
        d.text((W // 2 - 90, 6), f"PharmaSignal — {topic}", font=font, fill=DIM)

        y = PAD
        for ln in window:
            d.text((PAD, y), ln[:150], font=font, fill=_color(ln))
            y += LINE_H
        img.save(frames_dir / f"f{i:05d}.png")

    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
         "-i", str(frames_dir / "f%05d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", str(out)],
        check=True)
    shutil.rmtree(frames_dir, ignore_errors=True)
    return out


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "antibody-drug conjugate"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    lines = run_pipeline(topic, limit)
    path = render(lines, OUT_DIR / "demo.mp4", topic)
    size = path.stat().st_size / 1_000_000
    print(f"\n완료: {path}  ({size:.1f} MB, {len(lines)}줄)")
