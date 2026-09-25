#!/usr/bin/env python3
# 이식 출처: AgentForgeAI(2026-08 Agent Forge AI Hackathon) 의 video/explain/slides.py
# 이식 시각: 2026-09-25
# 바꾼 것: 폰트 경로를 이 폴더의 fonts/ 로, 크롬 경로를 환경변수로 바꿨다. 슬라이드 내용은 v1 주제 그대로라 이번 주제로 다시 써야 한다.
"""설명 영상 슬라이드 생성 — 1920x1080 PNG.

  python video/explain/slides.py

내용은 전부 실행으로 확인된 사실만 담는다. 숫자는 실행 원장과 게이트 결과에서
가져왔다. 렌더 후 PNG를 직접 열어 겹침과 잘림을 확인한다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "slides"
import os
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
# v1 은 다른 프로젝트 폴더의 폰트를 절대경로로 가리켰다. 이 저장소 안으로 옮겼다.
FONT_DIR = Path(os.environ.get("FONT_DIR", HERE / "fonts"))
W, H = 1920, 1080

BG, PANEL, LINE = "#0f1418", "#161d23", "#26313a"
FG, MUTED = "#eef3f6", "#93a4b1"
ACCENT, WARN = "#4fd1a5", "#e8b04b"
BD, QW, DY, NO = "#5b8def", "#a97bf0", "#4fd1a5", "#f0776c"
# 배경색과 미리 섞은 카드 바탕. 반투명보다 어두운 화면에서 선명하다.
TBD, TQW, TDY, TNO = "#1d2a3f", "#2b273f", "#1b3631", "#382627"


def faces() -> str:
    out = []
    for n, w in [("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700)]:
        p = FONT_DIR / f"Pretendard-{n}.otf"
        if p.exists():
            out.append(f"@font-face{{font-family:Pretendard;src:url('file://{p}');font-weight:{w}}}")
    return "\n".join(out)


CSS = f"""
{faces()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:{BG};color:{FG};font-family:Pretendard,sans-serif;
 padding:96px 120px 240px;display:flex;flex-direction:column;justify-content:center;
 gap:44px;overflow:hidden}}
body.center{{align-items:center;text-align:center}}
.k{{color:{ACCENT};font-size:30px;font-weight:600;letter-spacing:.18em}}
h1{{font-size:88px;font-weight:800;line-height:1.16;letter-spacing:-.025em}}
h2{{font-size:74px;font-weight:700;line-height:1.22;letter-spacing:-.02em}}
.lead{{color:{MUTED};font-size:36px;line-height:1.5;max-width:1400px}}
.row{{display:flex;gap:26px}}
.card{{flex:1;background:var(--t);border:1px solid {LINE};border-top:5px solid var(--c);
 border-radius:18px;padding:32px 30px;box-shadow:0 18px 40px rgba(0,0,0,.5)}}
.card em{{font-style:normal;color:{MUTED};font-size:22px;letter-spacing:.14em}}
.card b{{display:block;font-size:38px;font-weight:700;color:var(--c);margin:8px 0 10px}}
.card span{{color:{MUTED};font-size:25px;line-height:1.45}}
.big{{background:var(--t);border:1px solid {LINE};border-left:8px solid var(--c);
 border-radius:20px;padding:46px 52px;display:flex;align-items:center;gap:44px}}
.big .no{{font-size:96px;font-weight:800;color:var(--c);line-height:1}}
.big .tx b{{display:block;font-size:52px;font-weight:700;margin-bottom:12px}}
.big .tx span{{color:{MUTED};font-size:31px;line-height:1.45}}
.note{{color:{MUTED};font-size:31px;border-left:5px solid {ACCENT};padding-left:26px;line-height:1.5}}
.term{{background:#0a0f13;border:1px solid {LINE};border-radius:18px;padding:38px 44px;
 font-family:'SF Mono',Menlo,monospace;font-size:29px;line-height:1.65;white-space:pre}}
.term .g{{color:{ACCENT};font-weight:600}} .term .c{{color:{MUTED}}} .term .r{{color:{NO}}}
.stats{{display:flex;gap:26px}}
.stats>div{{flex:1;background:{PANEL};border:1px solid {LINE};border-radius:18px;
 padding:34px;text-align:center}}
.stats b{{display:block;font-size:76px;font-weight:800;color:{ACCENT};line-height:1.1}}
.stats span{{color:{MUTED};font-size:26px}}
.bars{{display:flex;flex-direction:column;gap:13px}}
.bar{{display:flex;align-items:center;gap:20px}}
.bar i{{font-style:normal;width:210px;font-size:27px;color:{FG}}}
.bar .t{{flex:1;height:34px;background:{PANEL};border-radius:8px;overflow:hidden}}
.bar .t u{{display:block;height:100%;background:var(--c);text-decoration:none}}
.bar em{{font-style:normal;width:90px;text-align:right;font-size:27px;font-weight:700;color:var(--c)}}
.tag{{display:inline-block;background:{PANEL};border:1px solid {LINE};border-radius:999px;
 padding:10px 26px;font-size:26px;color:{MUTED};margin-right:12px}}
"""


def card(step: str, name: str, desc: str, c: str, t: str) -> str:
    return (f'<div class="card" style="--c:{c};--t:{t}"><em>{step}</em>'
            f'<b>{name}</b><span>{desc}</span></div>')


def big(no: str, title: str, desc: str, c: str, t: str) -> str:
    return (f'<div class="big" style="--c:{c};--t:{t}"><div class="no">{no}</div>'
            f'<div class="tx"><b>{title}</b><span>{desc}</span></div></div>')


PIPE_ROW = (card("1 수집", "Bright Data", "흩어진 공시를 한곳으로", BD, TBD)
            + card("2 판단", "Qwen Cloud", "구조로 바꾸고 코드를 쓴다", QW, TQW)
            + card("3 실행", "Daytona", "격리 샌드박스에서 실행", DY, TDY)
            + card("4 반출 금지", "Nosana", "상용 제공자에게 보내지 않음", NO, TNO))

MODALITIES = [("GLP-1", 50, WARN), ("펩타이드 치료제", 42, WARN), ("방사성리간드", 23, BD),
              ("siRNA", 22, BD), ("단일클론항체", 21, BD), ("ADC", 16, DY),
              ("mRNA 백신", 12, QW), ("이중항체", 11, QW), ("CAR-T", 0, NO)]
BARS = "".join(
    f'<div class="bar"><i>{n}</i><div class="t"><u style="--c:{c};width:{max(v,1)*1.9}%"></u></div>'
    f'<em style="--c:{c}">{v}%</em></div>' for n, v, c in MODALITIES)

SLIDES: list[tuple[str, str]] = [
    ("01", f'''<body class="center">
      <div class="k">AGENT FORGE SEOUL 2026</div>
      <h1>PharmaSignal</h1>
      <div class="lead">신약 안전성 신호를 훑고,<br>근거까지 스스로 만드는 에이전트</div></body>'''),

    ("02", f'''<body>
      <div class="k">문제</div>
      <h2>흩어진 출처를 매일 손으로 훑는다</h2>
      <div class="lead">임상시험 등록, 규제 공시, 전문지가 각각 다른 형식으로 갱신된다.
      상당수는 자동 수집을 막아 두었다.</div>
      <div><span class="tag">ClinicalTrials.gov</span><span class="tag">FDA 공시</span>
      <span class="tag">EMA</span><span class="tag">PubMed</span><span class="tag">FAERS</span></div></body>'''),

    ("03", f'''<body>
      <div class="k">더 큰 벽</div>
      <h2>사내 임상 문서는<br>밖으로 내보낼 수 없다</h2>
      <div class="note">공개 정보 분석을 자동화해도<br>정작 중요한 내부 데이터에는 손을 못 댄다</div>
      <div class="lead">제약과 의료에서 AI 도입이 막히는 진짜 이유가 여기에 있다.</div></body>'''),

    ("04", f'''<body>
      <div class="k">해법</div>
      <h2>민감도에 따라 추론 경로를 나눈다</h2>
      <div class="row">{PIPE_ROW}</div>
      <div class="note">공개 데이터는 상용 API로, 반출 금지 텍스트는 지정한 엔드포인트로만</div></body>'''),

    ("05", f'''<body>
      <div class="k">1 · 수집</div>
      <h2>봇 차단을 넘어 데이터를 가져온다</h2>
      {big("01", "Bright Data", "임상시험 등록은 등록 API에서, 이상사례 논의가 오가는 문헌과 전문지는 검색으로 찾는다", BD, TBD)}
      <div class="lead">계정에 열려 있는 제품에 따라 Web Unlocker, SERP API, 프록시 가운데 하나를 자동으로 고른다.</div></body>'''),

    ("06", f'''<body>
      <div class="k">2 · 판단</div>
      <h2>분석 코드를 모델이 직접 쓴다</h2>
      {big("02", "Qwen Cloud", "형식이 제각각인 문서를 스키마로 뽑고, 그 데이터를 분석하는 코드까지 작성한다", QW, TQW)}
      <div class="lead">사람이 미리 짜 둔 코드가 아니라 그때그때 만드는 코드다.</div></body>'''),

    ("07", f'''<body>
      <div class="k">3 · 실행</div>
      <h2>모델이 쓴 코드를<br>내 컴퓨터에서 돌리지 않는다</h2>
      {big("03", "Daytona", "생성된 코드는 격리 샌드박스에서만 실행된다", DY, TDY)}
      <div class="term"><span class="c">로컬  </span>python 3.12.8  macOS
<span class="c">샌드박스</span> <span class="g">python 3.14.4</span>   ← 진짜 원격에서 돌았다</div></body>'''),

    ("08", f'''<body>
      <div class="k">4 · 반출 금지</div>
      <h2>이 경로에만<br>폴백을 두지 않았다</h2>
      {big("04", "Nosana", "반출 금지 텍스트를 상용 LLM 제공자에게 보내지 않고 지정한 엔드포인트로만 추론한다", NO, TNO)}
      <div class="term">build_sovereign() → <span class="r">None</span>
<span class="c">쓸 수 없으면 기능을 포기하고 단계를 건너뛴다</span></div></body>'''),

    ("09", f'''<body class="center">
      <div class="k">설계 근거</div>
      <h2>기능을 잃는 쪽이<br>데이터가 새는 것보다 낫다</h2>
      <div class="lead">폴백을 두면 민감 텍스트가 슬쩍 상용 API로 샌다.<br>
      쓸 수 없으면 그 단계를 건너뛰도록 했다.</div></body>'''),

    ("10", f'''<body>
      <div class="k">검증</div>
      <h2>생성된 집계를<br>고정 로직으로 다시 따진다</h2>
      <div class="term"><span class="c">[대조] 생성된 집계를 고정 로직으로 다시 계산</span>
  <span class="g">11/11 일치</span></div>
      <div class="lead">확립된 기법이다. 모델이 낸 숫자의 판정을 모델에게 맡기지 않는다.
      같은 집계를 코드로 다시 구해 대조한다.</div></body>'''),

    ("11", f'''<body>
      <div class="k">결과</div>
      <h2>계열을 나란히 놓으면 지형이 보인다</h2>
      <div class="bars">{BARS}</div>
      <div class="note">계열당 마흔 건 수집. 오른쪽은 후기 임상 비중(3·4상 / 단계 표기)</div></body>'''),

    ("12", f'''<body>
      <div class="k">완성도</div>
      <h2>되는 것과 안 되는 것을<br>표로 구분해서 쓴다</h2>
      <div class="stats"><div><b>4/4</b><span>실제 호출된 플랫폼</span></div>
      <div><b>19</b><span>자동 테스트</span></div>
      <div><b>4/4</b><span>완료 게이트</span></div></div>
      <div class="lead">폴백이 조용히 일어나면 데모가 거짓말이 된다.
      단계마다 실경로인지 폴백인지 기록해 마지막에 표로 낸다.</div></body>'''),

    ("13", f'''<body class="center">
      <div class="k">PHARMASIGNAL</div>
      <h1>데이터를 못 내보낸다면,<br>에이전트를 그리로 보낸다</h1>
      <div class="lead">github.com/kakyungkim/pharmasignal</div></body>'''),
]


def build(n: str, body: str, total: int) -> str:
    return f"<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><style>{CSS}</style></head>{body}</html>"


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    total = len(SLIDES)
    for n, body in SLIDES:
        html = OUT / f"s{n}.html"
        png = OUT / f"s{n}.png"
        html.write_text(build(n, body, total))
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                        f"--screenshot={png}", f"--window-size={W},{H}", f"file://{html}"],
                       capture_output=True, check=True)
        print(f"  s{n}.png  {png.stat().st_size // 1024}KB")
    print(f"\n{total}장 생성: {OUT}")
