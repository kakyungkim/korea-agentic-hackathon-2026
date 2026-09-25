#!/usr/bin/env python3
# 출처: 같은 폴더의 slides.py(AgentForgeAI 이식본). CSS 와 렌더 절차를 그대로 쓰고
#       SLIDES 내용만 FlyGate 로 새로 썼다. slides.py 는 손대지 않았다.
# 작성 2026-09-25. 대본은 docs/video/script_flygate.md, 컷 지시는 docs/video/shotlist_flygate.md.
"""FlyGate 데모 영상 슬라이드 13장 — 1920x1080 PNG.

  python assets/video/slides_flygate.py

숫자는 전부 docs/HANDOFF.md 의 검증된 수치 표와 eval/results/ 결과 파일에서 가져왔다.
지어낸 값은 없다. 렌더 후 PNG 를 직접 열어 겹침과 잘림을 확인한다.

build.sh 4단계는 이 폴더의 `slide_NN.png` 를 찾는다. 렌더 뒤에 이름을 맞춰 준다.
  for f in slides/s*.png; do cp "$f" "slide_${f##*/s}"; done
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT = HERE / "slides"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FONT_DIR = Path(os.environ.get("FONT_DIR", HERE / "fonts"))
FIG_DIR = REPO / "docs" / "figures"
W, H = 1920, 1080

BG, PANEL, LINE = "#0f1418", "#161d23", "#26313a"
FG, MUTED = "#eef3f6", "#93a4b1"
ACCENT, WARN = "#4fd1a5", "#e8b04b"
# 경로 A(근거가 받쳐 주는 쪽) 파랑, 경로 B(공백이 있는 쪽) 붉은 계열, 정책은 보라
PA, PB, POL = "#5b8def", "#f0776c", "#a97bf0"
TPA, TPB, TPOL = "#1d2a3f", "#382627", "#2b273f"


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
body.fig{{padding:56px 60px 210px;gap:20px}}
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
 border-radius:20px;padding:40px 46px;display:flex;align-items:center;gap:44px}}
.big .no{{font-size:84px;font-weight:800;color:var(--c);line-height:1;white-space:nowrap}}
.big .tx b{{display:block;font-size:44px;font-weight:700;margin-bottom:10px}}
.big .tx span{{color:{MUTED};font-size:29px;line-height:1.45}}
.note{{color:{MUTED};font-size:31px;border-left:5px solid {ACCENT};padding-left:26px;line-height:1.5}}
.term{{background:#0a0f13;border:1px solid {LINE};border-radius:18px;padding:34px 40px;
 font-family:'SF Mono',Menlo,monospace;font-size:26px;line-height:1.7;white-space:pre}}
.term .g{{color:{ACCENT};font-weight:600}} .term .c{{color:{MUTED}}} .term .r{{color:{PB}}}
.stats{{display:flex;gap:26px}}
.stats>div{{flex:1;background:{PANEL};border:1px solid {LINE};border-radius:18px;
 padding:34px;text-align:center}}
.stats b{{display:block;font-size:72px;font-weight:800;color:{ACCENT};line-height:1.1}}
.stats b.warn{{color:{WARN}}} .stats b.pb{{color:{PB}}}
.stats span{{color:{MUTED};font-size:26px;line-height:1.4}}
.tag{{display:inline-block;background:{PANEL};border:1px solid {LINE};border-radius:999px;
 padding:10px 26px;font-size:26px;color:{MUTED};margin-right:12px}}
.figwrap{{flex:1;display:flex;align-items:center;justify-content:center;min-height:0}}
.figwrap img{{max-width:100%;max-height:100%;object-fit:contain;border-radius:14px;
 background:#fff;box-shadow:0 18px 40px rgba(0,0,0,.5)}}
.src{{color:{MUTED};font-size:24px}}
"""


def card(step: str, name: str, desc: str, c: str, t: str) -> str:
    return (f'<div class="card" style="--c:{c};--t:{t}"><em>{step}</em>'
            f'<b>{name}</b><span>{desc}</span></div>')


def big(no: str, title: str, desc: str, c: str, t: str) -> str:
    return (f'<div class="big" style="--c:{c};--t:{t}"><div class="no">{no}</div>'
            f'<div class="tx"><b>{title}</b><span>{desc}</span></div></div>')


def fig(name: str) -> str:
    return f'<div class="figwrap"><img src="file://{FIG_DIR / name}"></div>'


SLIDES: list[tuple[str, str]] = [
    # 1 · 표지 (문장 1)
    ("01", f'''<body class="center">
      <div class="k">KOREA AGENTIC AI HACKATHON 2026</div>
      <h1>FlyGate</h1>
      <div class="lead">도킹 점수에서 사람 근거까지 잇고,<br>
      넘어선 주장을 되돌리는 크리틱</div></body>'''),

    # 2 · 문제 (문장 2~3)
    ("02", f'''<body>
      <div class="k">문제</div>
      <h2>도킹 점수 해석의 선</h2>
      <div class="row">
      {card("경로 A", "PARP1 4R6E", "AutoDock Vina 실측 -10.178 kcal/mol", PA, TPA)}
      {card("경로 B", "Factor Xa 2P16", "AutoDock Vina 실측 -7.967 kcal/mol", PB, TPB)}
      </div>
      <div class="note">도킹 점수는 순위를 매기는 값. 친화도로 환산하지 않는다</div>
      <div class="src">niraparib · eval/results/case_niraparib.json</div></body>'''),

    # 3 · 과잉해석 (문장 4~5)
    ("03", f'''<body>
      <div class="k">과잉해석</div>
      <h2>숫자는 맞고 결론이 틀린 주장</h2>
      <div class="term"><span class="c">주장  </span>PARP1 -10.178, Factor Xa -7.967 이므로
      <span class="r">niraparib 은 PARP1 선택성을 갖는다</span>
<span class="c">판정  </span>근거 ID <span class="g">있음</span>   숫자 <span class="g">일치</span>   추론 <span class="r">반려</span></div>
      <div class="note">서로 다른 단백질이고 교차 타깃으로 보정되지 않았다</div></body>'''),

    # 4 · 계보와 팀 (문장 6~8) ★ 팀원 A 녹화가 오면 이 한 장을 클립으로 통째 교체한다
    ("04", f'''<body>
      <div class="k">계보와 팀</div>
      <h2>선행 프로젝트와 초파리 도킹 자산</h2>
      <div class="row">
      {card("이어받은 것", "PharmaSignal v0", "NAT 하네스, 근거 ID 검증, 영상 파이프라인", ACCENT, "#1b3631")}
      {card("팀원 저작물", "초파리 도킹 데모", "커넥톰 167,122 뉴런, 미각 뉴런 1,428개에 도킹 점수 주입", PA, TPA)}
      </div>
      <div class="note">해석 한계 목록이 우리 크리틱 규칙의 뼈대가 됐다</div></body>'''),

    # 5 · 흐름 전체 (문장 9~10)
    ("05", f'''<body class="fig">
      <div class="k">흐름</div>
      {fig("architecture_pipeline.png")}
      <div class="src">docs/figures/architecture_pipeline.png · 점선 상자는 아직 계획인 단계</div></body>'''),

    # 6 · 결합 (문장 11~13)
    ("06", f'''<body>
      <div class="k">결합</div>
      <h2>구조에서 포즈까지</h2>
      {big("200", "DiffDock NIM", "HTTP 200, 4.0초, 포즈 3개. 시드가 없어 호출마다 값이 다르다", ACCENT, "#1b3631")}
      <div class="row">
      {card("실측 조회", "AutoDock Vina", "팀원 데모의 도킹 결과를 SHA256 으로 대조", PA, TPA)}
      {card("참조 친화도", "BindingDB", "종점 Ki, IC50, Kd, EC50 을 합치지 않는다", POL, TPOL)}
      </div></body>'''),

    # 7 · 사람 근거 (문장 14~15)
    ("07", f'''<body>
      <div class="k">사람 근거</div>
      <h2>라벨과 보고와 문헌</h2>
      <div class="stats">
      <div><b>기재</b><span>DailyMed 라벨<br>경고와 이상반응</span></div>
      <div><b>9.13</b><span>FAERS PRR<br>95% CI 8.61~9.69</span></div>
      <div><b>92</b><span>PubMed 문헌<br>대표 PMID 40687421</span></div></div>
      <div class="note">에이전트가 도구 4종을 연속 호출해 주장 4건, 근거 없는 주장 0건</div></body>'''),

    # 8 · 크리틱 (문장 16~19)
    ("08", f'''<body>
      <div class="k">크리틱</div>
      <h2>세 단계 검증</h2>
      <div class="row">
      {card("1단", "결정 규칙", "주장 존재와 근거 ID 유무. 모델을 부르지 않는다", MUTED, PANEL)}
      {card("2단", "숫자 오라클", "포즈 점수와 로그 대조, SHA256, PRR 재계산", MUTED, PANEL)}
      {card("3단", "과잉해석 판정", "규칙 15종. 근거와 숫자가 맞아도 추론이 틀리면 반려", POL, TPOL)}
      </div>
      <div class="note">작성자와 크리틱은 서로 다른 워크플로. 크리틱에 쓰기 도구가 없다</div></body>'''),

    # 9 · 케이스 (문장 20~22)
    ("09", f'''<body class="fig">
      <div class="k">결과</div>
      {fig("results_case.png")}
      <div class="src">docs/figures/results_case.png · eval/results/case_niraparib.json</div></body>'''),

    # 10 · 적발률 (문장 23~24)
    ("10", f'''<body>
      <div class="k">적발률</div>
      <h2>고정 규칙과 LLM 판정의 격차</h2>
      <div class="stats">
      <div><b>16/16</b><span>LLM 판정을 붙였을 때<br>심어 둔 과잉해석 적발</span></div>
      <div><b class="pb">1/16</b><span>고정된 규칙만<br>나머지는 그대로 통과</span></div>
      <div><b>0/17</b><span>정상 케이스<br>거짓 양성</span></div></div>
      <div class="note">평가 33건. eval/results/critic_verdict_output_llm.json 과 _deterministic.json 대조</div></body>'''),

    # 11 · 정책 (문장 25~26)
    ("11", f'''<body>
      <div class="k">안전</div>
      <h2>deny-by-default 정책</h2>
      <div class="stats">
      <div><b>7</b><span>허용 호스트<br>그 밖은 전부 차단</span></div>
      <div><b>1</b><span>쓰기 허용<br>/work/out</span></div>
      <div><b>18</b><span>스모크 통과<br>실패 0건</span></div></div>
      <div><span class="tag">health.api.nvidia.com</span><span class="tag">integrate.api.nvidia.com</span>
      <span class="tag">files.rcsb.org</span><span class="tag">api.fda.gov</span>
      <span class="tag">dailymed.nlm.nih.gov</span></div></body>'''),

    # 12 · 차단 로그 (문장 27~29)
    ("12", f'''<body>
      <div class="k">차단 로그</div>
      <h2>경계에서 끊긴 요청</h2>
      <div class="term">NET:OPEN [MED] <span class="r">DENIED</span> python3.12 -> github.com:443
  <span class="c">reason: endpoint github.com:443 is not allowed by any policy</span>
NET:OPEN [MED] <span class="r">DENIED</span> /usr/bin/curl -> integrate.api.nvidia.com:443
  <span class="c">reason: binary '/usr/bin/curl' not allowed in policy</span>
HTTP:GET  [MED] <span class="r">DENIED</span> GET api.fda.gov/drug/label.json
  <span class="c">reason: not permitted by policy</span></div>
      <div class="src">eval/results/openshell_smoke_flydock.txt · OpenShell 0.0.116</div></body>'''),

    # 13 · 마무리 (문장 30~32)
    ("13", f'''<body class="center">
      <div class="k">FLYGATE</div>
      <h1>구조에서 사람까지,<br>근거 ID 로 연결</h1>
      <div class="lead">샌드박스 안에서는 TLS 까지 확인했고 DiffDock 호출은 아직이다.<br>
      초파리 포즈 탐색과 분류 게이트는 계획, NemoGuard 는 배선까지.<br>
      마지막 판단은 사람이 한다.</div></body>'''),
]


def build(body: str) -> str:
    return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head>{body}</html>'


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for n, body in SLIDES:
        html = OUT / f"s{n}.html"
        png = OUT / f"s{n}.png"
        html.write_text(build(body), encoding="utf-8")
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                        f"--screenshot={png}", f"--window-size={W},{H}", f"file://{html}"],
                       capture_output=True, check=True)
        print(f"  s{n}.png  {png.stat().st_size // 1024}KB")
    print(f"\n{len(SLIDES)}장 생성: {OUT}")
    print("build.sh 에 넘기기 전에: for f in slides/s*.png; do cp \"$f\" \"slide_${f##*/s}\"; done")
