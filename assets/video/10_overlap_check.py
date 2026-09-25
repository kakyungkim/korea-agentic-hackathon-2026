#!/usr/bin/env python
# 이식 출처: AgentForgeAI(2026-08 Agent Forge AI Hackathon) 의 video/explain/10_overlap_check.py
# 이식 시각: 2026-09-25
# 바꾼 것: 그대로 가져왔다.
"""자막이 놓일 자리를 슬라이드 본문이 침범했는지 검사한다.

슬라이드는 내용을 세로 가운데로 놓기 때문에, 표나 흐름도가 길면 아래쪽으로 자라
자막 상자에 가려진다. 눈으로 놓치기 쉬워 기계로 먼저 잡는다.

판정: 자막이 덮을 띠 안에서 배경보다 밝은 화소를 센다. 배경은 어두운 단색 그라데이션이라
      글자·카드·figure는 확실히 밝다.

사용법: python overlap_check.py [슬라이드폴더]
반환: 침범한 슬라이드가 있으면 1
"""
import pathlib
import sys

from PIL import Image

W, H = 1920, 1080
BOTTOM = 76          # caption.py 의 값과 같아야 한다
MAX_CAP_H = 170      # 두 줄짜리 자막 상자 높이 (46*2 + 16 + 26*2)
BAR_H = 12           # 맨 아래 진행 바는 셈에서 뺀다
LUMA = 100           # 이보다 밝으면 내용으로 본다
RATIO = 0.004        # 띠 화소의 0.4%를 넘으면 침범으로 본다


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    slides = sorted(root.glob('slide_*.png'))
    if not slides:
        print('  슬라이드를 찾지 못했다'); return 2

    y0, y1 = H - BOTTOM - MAX_CAP_H, H - BAR_H
    total = (y1 - y0) * W
    bad = []
    for p in slides:
        band = Image.open(p).convert('L').crop((0, y0, W, y1))
        ink = sum(1 for v in band.getdata() if v > LUMA)
        if ink > total * RATIO:
            bad.append((p.name, ink / total * 100))

    if bad:
        print(f'  ⚠ 자막 자리를 침범한 슬라이드 {len(bad)}장')
        for name, pct in bad:
            print(f'      {name}  띠 안 내용 {pct:.1f}%')
        print('      → 07_슬라이드.html 의 .stage 아래 여백을 늘리거나 해당 슬라이드 내용을 줄인다')
        return 1
    print(f'  자막 자리 침범 없음 (슬라이드 {len(slides)}장 검사)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
