#!/usr/bin/env python
# 이식 출처: AgentForgeAI(2026-08 Agent Forge AI Hackathon) 의 video/explain/09_caption.py
# 이식 시각: 2026-09-25
# 바꾼 것: 그대로 가져왔다. NUM 치환표는 v1 고유명이라 이번 주제로 바꿔야 한다.
"""문장별 자막 PNG(투명 배경 1920x1080)와 SRT를 만든다.

ffmpeg 8.1.1 빌드에 libass·drawtext가 없어 자막 필터를 못 쓴다.
그래서 투명 PNG를 만들어 overlay 필터로 얹고, 유튜브 업로드용 SRT는 따로 낸다.

입력: _sents.txt (문장 한 줄씩), _durs.txt (문장별 초)
출력: cap_NN.png, final.srt
"""
import pathlib
import re
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONT = 'fonts/Pretendard-SemiBold.otf'
SIZE = 46
LINE_GAP = 16
MAX_W = 1560          # 자막 한 줄 최대 폭
BOTTOM = 76           # 아래 여백
PAD_X, PAD_Y = 44, 26
FG = (240, 246, 252, 255)
BG = (8, 16, 26, 205)  # 반투명 판. 슬라이드 아래쪽 여백에 얹는다


# 나레이션은 TTS가 바르게 읽도록 한글로 적었다. 눈으로 읽는 자막은 숫자와 영어가 빠르다.
#
# 순서가 중요하다. 짧은 항목이 먼저 오면 긴 말 안에서 잘못 잡힌다.
# 예를 들어 '한 개'가 앞에 있으면 '열한 개'가 '열1개'가 된다. 긴 것부터 둔다.
NUM = [
    # 숫자 (긴 것부터)
    ('열아홉 개', '19개'), ('열한 개', '11개'), ('마흔 건', '40건'),
    ('게이트 네 개', '게이트 4개'), ('삼 점 일이', '3.12'), ('삼 점 일사', '3.14'),
    ('삼상 이상', '3상 이상'), ('여섯 건', '6건'),
    # 영어는 영어로. 음차한 것을 되돌린다
    ('파마시그널', 'PharmaSignal'), ('브라이트 데이터', 'Bright Data'),
    ('퀜 클라우드', 'Qwen Cloud'), ('데이토나', 'Daytona'), ('노사나', 'Nosana'),
    ('에이피아이', 'API'), ('지피유', 'GPU'), ('지엘피 원', 'GLP-1'),
    ('카티', 'CAR-T'), ('파이썬', 'Python'),
]


def to_digits(text):
    for a, b in NUM:
        text = text.replace(a, b)
    return text


def _greedy(draw, words, font, max_w):
    lines, cur = [], ''
    for w in words:
        trial = f'{cur} {w}'.strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def wrap(draw, text, font, max_w):
    """어절 단위로 감싼다. 한국어는 공백 기준이 가장 무난하다.

    줄 수를 그대로 두면서 폭을 좁혀 다시 감싸, 마지막 줄에 한 어절만 남는 일을 없앤다.
    """
    words = text.split()
    lines = _greedy(draw, words, font, max_w)
    if len(lines) < 2:
        return lines
    target = max_w
    while True:
        narrower = target - 40
        cand = _greedy(draw, words, font, narrower)
        if len(cand) != len(lines):
            return _greedy(draw, words, font, target)
        target = narrower


def srt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f'{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round(s % 1 * 1000)):03d}'


def main():
    sents = [s for s in pathlib.Path('_sents.txt').read_text(encoding='utf-8').split('\n') if s.strip()]
    durs = [float(x) for x in pathlib.Path('_durs.txt').read_text().split()]
    assert len(sents) == len(durs), f'문장 {len(sents)} vs 길이 {len(durs)}'

    font = ImageFont.truetype(FONT, SIZE)
    probe = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    lh = SIZE + LINE_GAP

    for i, text in enumerate(sents, 1):
        # 자막은 화면용이라 문장부호를 덜어 낸다
        body = to_digits(re.sub(r'\s+', ' ', text).strip())
        lines = wrap(probe, body, font, MAX_W)
        box_w = int(max(probe.textlength(l, font=font) for l in lines)) + PAD_X * 2
        box_h = lh * len(lines) - LINE_GAP + PAD_Y * 2

        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x0, y0 = (W - box_w) // 2, H - BOTTOM - box_h
        d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=16, fill=BG)
        for n, l in enumerate(lines):
            tw = probe.textlength(l, font=font)
            d.text(((W - tw) / 2, y0 + PAD_Y + n * lh), l, font=font, fill=FG)
        img.save(f'cap_{i:02d}.png')

    # SRT
    out, t = [], 0.0
    for i, (text, dur) in enumerate(zip(sents, durs), 1):
        out.append(f'{i}\n{srt_time(t)} --> {srt_time(t + dur)}\n{to_digits(text)}\n')
        t += dur
    pathlib.Path('final.srt').write_text('\n'.join(out), encoding='utf-8')
    print(f'  자막 PNG {len(sents)}장 · final.srt {t:.1f}초')


if __name__ == '__main__':
    main()
