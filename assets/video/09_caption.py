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
    # 숫자 (긴 것부터). 짧은 항목이 앞에 오면 긴 말 안에서 잘못 잡힌다.
    ('십육만 칠천백이십이 개', '167,122개'), ('천사백이십팔 개', '1,428개'),
    ('마이너스 십점일칠팔', '-10.178'), ('마이너스 칠점구육칠', '-7.967'),
    ('에이치티티피 이백', 'HTTP 200'), ('영점칠육일', '0.761'),
    ('구점일삼', '9.13'), ('사점영 초', '4.0초'), ('구십이 건', '92건'),
    ('열여섯 건 중 한 건만', '16건 중 1건만'),
    ('열여섯 건', '16건'), ('열일곱 건', '17건'), ('열여덟 건', '18건'),
    ('열다섯 종', '15종'), ('여덟 종', '8종'), ('네 종', '4종'), ('네 건', '4건'),
    ('세 개', '3개'), ('세 단계', '3단계'), ('일곱 곳', '7곳'), ('한 곳', '1곳'),
    ('사백삼', '403'),
    # 영어는 영어로. 음차한 것을 되돌린다
    ('플라이게이트', 'FlyGate'), ('파마시그널 브이 영', 'PharmaSignal v0'),
    ('니모트론 삼 슈퍼', 'Nemotron 3 Super'), ('니모가드', 'NemoGuard'),
    ('엔비디아 디프독', 'NVIDIA DiffDock'), ('디프독', 'DiffDock'),
    ('알씨에스비', 'RCSB'), ('바인딩디비', 'BindingDB'),
    ('데일리메드', 'DailyMed'), ('페어스', 'FAERS'), ('펍메드', 'PubMed'),
    ('오픈셸', 'OpenShell'), ('깃허브를', 'github.com을'), ('깃허브', 'github.com'),
    ('워크 아웃', '/work/out'), ('니라파립', 'niraparib'), ('파프원', 'PARP1'),
    ('응고인자 텐에이', '응고인자 Xa'), ('비나', 'Vina'),
    ('피알알', 'PRR'), ('엘엘엠', 'LLM'), ('티엘에스', 'TLS'),
    ('근거 아이디', '근거 ID'),
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
