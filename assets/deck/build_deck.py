#!/usr/bin/env python3
# 이식 출처: AgentForgeAI(2026-08 Agent Forge AI Hackathon) 의 deck/build_deck.py
# 이식 시각: 2026-09-25
# 바꾼 것: 그대로 가져왔다. 슬라이드 문구는 v1 스택(Bright Data, Qwen, Daytona, Nosana) 기준이라 전면 교체가 필요하다.
"""발표자료 생성 — 한국어판과 영어판을 한 정의에서 함께 만든다.

  python deck/build_deck.py

두 판을 따로 손으로 고치면 반드시 어긋난다. 문구를 (ko, en) 쌍으로 두고
같은 뼈대에 넣는다.

해커톤 제출본은 `pharmasignal-*-v1.html`로 남겨 두었다. 이 파일이 만드는 것은
그 이후 갱신본이다. 4/4 실호출, 대조 단계, 실행 원장이 새로 들어갔다.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

BG, PANEL, LINE = "#0f1418", "#161d23", "#26313a"
FG, MUTED, ACCENT, WARN = "#eef3f6", "#93a4b1", "#4fd1a5", "#e8b04b"
BD, QW, DY, NO = "#5b8def", "#a97bf0", "#4fd1a5", "#f0776c"
TBD, TQW, TDY, TNO = "#1d2a3f", "#2b273f", "#1b3631", "#382627"

CSS = f"""
:root{{--bg:{BG};--panel:{PANEL};--line:{LINE};--fg:{FG};--muted:{MUTED};
 --accent:{ACCENT};--warn:{WARN};--bd:{BD};--qw:{QW};--dy:{DY};--no:{NO};
 --tbd:{TBD};--tqw:{TQW};--tdy:{TDY};--tno:{TNO};--pad:clamp(24px,5vw,72px)}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-snap-type:y mandatory;scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--fg);cursor:pointer;
 font-family:Pretendard,-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif;
 line-height:1.55;-webkit-font-smoothing:antialiased}}
section{{min-height:100vh;scroll-snap-align:start;padding:var(--pad);
 display:flex;flex-direction:column;justify-content:center;gap:clamp(16px,2.6vh,34px);
 border-bottom:1px solid var(--line);position:relative}}
section.center{{align-items:center;text-align:center}}
.num{{position:absolute;top:var(--pad);right:var(--pad);color:var(--muted);
 font-size:.8rem;letter-spacing:.18em}}
.kicker{{color:var(--accent);font-size:clamp(.8rem,1.6vw,1rem);letter-spacing:.2em;
 text-transform:uppercase;font-weight:600}}
h1{{font-size:clamp(2.2rem,7vw,4.6rem);line-height:1.1;letter-spacing:-.025em;font-weight:800}}
h2{{font-size:clamp(1.6rem,4.4vw,3rem);line-height:1.18;letter-spacing:-.02em;font-weight:700}}
.lead{{color:var(--muted);font-size:clamp(1rem,2.2vw,1.4rem);max-width:64ch}}
ul{{list-style:none;display:flex;flex-direction:column;gap:.66em;
 font-size:clamp(.96rem,1.9vw,1.28rem);max-width:66ch}}
li{{padding-left:1.4em;position:relative}}
li::before{{content:"";position:absolute;left:0;top:.6em;width:.5em;height:.5em;
 border-radius:50%;background:var(--accent)}}
.grid{{display:grid;gap:clamp(10px,1.4vw,18px);
 grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}}
.card{{background:var(--t);border:1px solid var(--line);border-top:4px solid var(--c);
 border-radius:14px;padding:clamp(16px,2vw,26px);display:flex;flex-direction:column;gap:.42em}}
.card .step{{color:var(--muted);font-size:.76rem;letter-spacing:.16em;text-transform:uppercase}}
.card .who{{font-size:clamp(1.05rem,2vw,1.34rem);font-weight:700;color:var(--c)}}
.card .role{{font-size:clamp(.86rem,1.5vw,1rem)}}
.card .why{{font-size:clamp(.76rem,1.3vw,.9rem);color:var(--muted)}}
.stats{{display:grid;gap:clamp(10px,1.4vw,18px);
 grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:14px;
 padding:clamp(14px,1.8vw,24px)}}
.stat b{{display:block;font-size:clamp(1.6rem,4vw,2.6rem);font-weight:800;
 color:var(--accent);line-height:1.1}}
.stat span{{color:var(--muted);font-size:clamp(.76rem,1.3vw,.9rem)}}
.quote{{border-left:3px solid var(--accent);padding-left:1em;
 font-size:clamp(1.05rem,2.4vw,1.55rem);max-width:54ch}}
.term{{background:#0a0f13;border:1px solid var(--line);border-radius:12px;
 padding:clamp(12px,1.7vw,22px);overflow-x:auto;font-family:'SF Mono',ui-monospace,Menlo,monospace;
 font-size:clamp(.62rem,1.16vw,.86rem);line-height:1.6;white-space:pre}}
.term .g{{color:var(--accent);font-weight:600}} .term .c{{color:var(--muted)}}
.term .r{{color:var(--no)}} .term .y{{color:var(--warn)}}
.bars{{display:flex;flex-direction:column;gap:.5em;font-size:clamp(.8rem,1.5vw,1.02rem)}}
.bar{{display:flex;align-items:center;gap:.9em}}
.bar i{{font-style:normal;width:min(34vw,190px);flex:none}}
.bar .t{{flex:1;height:1.5em;background:var(--panel);border-radius:6px;overflow:hidden}}
.bar .t u{{display:block;height:100%;background:var(--c);text-decoration:none}}
.bar em{{font-style:normal;width:3.4em;text-align:right;font-weight:700;color:var(--c)}}
.tags{{display:flex;flex-wrap:wrap;gap:.5em}}
.tags span{{border:1px solid var(--line);background:var(--panel);border-radius:999px;
 padding:.32em .95em;font-size:clamp(.74rem,1.4vw,.92rem);color:var(--muted)}}
.thanks{{font-size:clamp(2.2rem,7.4vw,5rem);font-weight:800;letter-spacing:-.03em;
 background:linear-gradient(92deg,{ACCENT},{BD} 55%,{QW});
 -webkit-background-clip:text;background-clip:text;color:transparent}}
.navbar{{position:fixed;left:0;bottom:0;width:100%;height:3px;
 background:rgba(255,255,255,.08);z-index:50}}
.navfill{{height:100%;width:0;background:var(--accent);transition:width .3s ease}}
.lang{{position:fixed;left:var(--pad);bottom:14px;z-index:60;color:var(--muted);
 font-size:.75rem;text-decoration:none;border:1px solid var(--line);border-radius:999px;
 padding:.25em .8em;background:var(--panel)}}
.hint{{position:fixed;right:var(--pad);bottom:18px;z-index:50;color:var(--muted);
 font-size:.75rem;letter-spacing:.12em;transition:opacity 1s ease;pointer-events:none}}
@media (max-width:640px){{section{{min-height:auto;padding-block:13vh}} .num{{display:none}}
 .bar i{{width:30vw}}}}
"""

NAV = """
<div class="navbar" aria-hidden="true"><div class="navfill" id="navfill"></div></div>
<div class="hint" id="hint">click / → / space</div>
<script>
(function(){
  var s=[].slice.call(document.querySelectorAll('section')),i=0,
      f=document.getElementById('navfill'),h=document.getElementById('hint');
  function paint(){f.style.width=((i+1)/s.length*100)+'%'}
  function go(n){i=Math.max(0,Math.min(s.length-1,n));s[i].scrollIntoView({behavior:'smooth'});paint()}
  new IntersectionObserver(function(es){es.forEach(function(e){
    if(e.isIntersecting){i=s.indexOf(e.target);paint()}})},{threshold:.5})
    .observe&&s.forEach(function(x,_,__){},0);
  var io=new IntersectionObserver(function(es){es.forEach(function(e){
    if(e.isIntersecting){i=s.indexOf(e.target);paint()}})},{threshold:.5});
  s.forEach(function(x){io.observe(x)});
  document.addEventListener('click',function(e){
    if(e.target.closest('a,code,.term')) return;
    go(e.clientX<window.innerWidth*0.25?i-1:i+1)});
  document.addEventListener('keydown',function(e){var k=e.key;
    if(k==='ArrowRight'||k==='ArrowDown'||k===' '||k==='PageDown'){e.preventDefault();go(i+1)}
    else if(k==='ArrowLeft'||k==='ArrowUp'||k==='PageUp'){e.preventDefault();go(i-1)}
    else if(k==='Home'){e.preventDefault();go(0)}
    else if(k==='End'){e.preventDefault();go(s.length-1)}});
  setTimeout(function(){h.style.opacity=0},4000); paint();
})();
</script>"""

MODALITIES = [("GLP-1", "GLP-1", 50, WARN), ("펩타이드 치료제", "Peptide", 42, WARN),
              ("방사성리간드", "Radioligand", 23, BD), ("siRNA", "siRNA", 22, BD),
              ("단일클론항체", "mAb", 21, BD), ("ADC", "ADC", 16, DY),
              ("mRNA 백신", "mRNA vaccine", 12, QW), ("이중항체", "Bispecific", 11, QW),
              ("CAR-T", "CAR-T", 0, NO)]


def bars(ko: bool) -> str:
    return "".join(
        f'<div class="bar"><i>{k if ko else e}</i><div class="t">'
        f'<u style="--c:{c};width:{max(v,1)*1.9}%"></u></div>'
        f'<em style="--c:{c}">{v}%</em></div>' for k, e, v, c in MODALITIES)


def cards(ko: bool) -> str:
    rows = [
        ("1 · 수집", "1 · Collect", "Bright Data", BD, TBD,
         "임상시험 등록과 규제 공시, 이상사례 문헌 검색",
         "Trial registries, filings, and a literature search for adverse events",
         "봇 차단과 지역 제한을 넘어야 함", "Bot blocking and geo limits stand in the way"),
        ("2 · 판단", "2 · Reason", "Qwen Cloud", QW, TQW,
         "문서를 스키마로 뽑고 분석 코드를 작성",
         "Extracts a schema and writes the analysis code itself",
         "형식이 제각각인 긴 문서를 다룸", "Long documents, no two formatted alike"),
        ("3 · 실행", "3 · Execute", "Daytona", DY, TDY,
         "생성된 코드를 격리 샌드박스에서 실행",
         "Runs the generated code in an isolated sandbox",
         "모델이 쓴 코드를 호스트에 두지 않음", "Model-written code never touches the host"),
        ("4 · 반출 금지", "4 · Restricted", "Nosana", NO, TNO,
         "반출 금지 텍스트를 상용 제공자에게 보내지 않음",
         "Restricted text never reaches a commercial provider",
         "이 경로가 없으면 민감 문서는 다루지 못함", "Without it, restricted documents cannot be touched at all"),
    ]
    out = []
    for sk, se, name, c, t, rk, re_, wk, we in rows:
        out.append(f'<div class="card" style="--c:{c};--t:{t}">'
                   f'<span class="step">{sk if ko else se}</span>'
                   f'<span class="who">{name}</span>'
                   f'<span class="role">{rk if ko else re_}</span>'
                   f'<span class="why">{wk if ko else we}</span></div>')
    return "".join(out)


def slides(ko: bool) -> list[str]:
    b = bars(ko)
    c = cards(ko)
    if ko:
        return [
            f'''<section class="center"><p class="kicker">Agent Forge Seoul 2026</p>
<h1>PharmaSignal</h1>
<p class="lead">신약 안전성 신호를 훑고, 근거까지 스스로 만드는 에이전트</p>
<div class="tags"><span>Bright Data</span><span>Qwen Cloud</span><span>Daytona</span><span>Nosana</span></div></section>''',

            f'''<section><p class="kicker">문제</p>
<h2>흩어진 출처를 매일 손으로 훑음</h2>
<ul><li>임상시험 등록, 규제 공시, 전문지가 각각 다른 형식으로 갱신</li>
<li>상당수 사이트가 자동 수집을 막아 둠</li>
<li>담당자가 아침마다 창을 열 개씩 띄우는 일이 반복</li></ul>
<p class="lead">그런데 더 큰 벽이 따로 있음.</p></section>''',

            f'''<section><p class="kicker">더 큰 벽</p>
<h2>사내 임상 문서는 밖으로 내보낼 수 없음</h2>
<p class="quote">공개 정보 분석을 자동화해도, 정작 중요한 내부 데이터에는 손을 못 댐</p>
<p class="lead">제약과 의료에서 AI 도입이 막히는 이유가 성능이 아니라 이 데이터 반출 제약임.
쓸 GPU가 없다는 조건까지 겹치는 것이 현장에서 흔함.</p></section>''',

            f'''<section><p class="kicker">해법</p>
<h2>민감도에 따라 추론 경로를 나눔</h2>
<div class="grid">{c}</div>
<p class="lead">공개 데이터는 상용 API로 처리하고, 반출 금지 텍스트는 지정한 엔드포인트로만 보냄.</p>
<p class="lead" style="font-size:clamp(.86rem,1.6vw,1.02rem)">이 발상 자체는 선행이 있음.
LiteLLM과 Portkey가 같은 라우팅을 제공하고 PAPILLON(NAACL 2025)이 같은 문제를 다룸.
여기서 다른 것은 기본값으로, 교차 등급 폴백을 금지함.</p></section>''',

            f'''<section><p class="kicker">설계</p>
<h2>이 경로에만 폴백을 두지 않음</h2>
<div class="term">build_sovereign() → <span class="r">None</span>
<span class="c">쓸 수 없으면 기능을 포기하고 단계를 건너뜀</span></div>
<p class="lead">다른 단계는 실패하면 폴백으로 넘어감. 여기에 폴백을 두면 민감 텍스트가
슬쩍 상용 API로 새기 때문에, 기능을 잃는 쪽을 택함.</p></section>''',

            f'''<section><p class="kicker">검증</p>
<h2>생성된 집계를 코드가 다시 따짐</h2>
<p class="lead" style="font-size:clamp(.86rem,1.6vw,1.02rem)">확립된 기법임. PAL과 PoT, LEVER가 원리를 세웠고 약물감시에도 이미 적용된 사례가 있음.</p>
<div class="term"><span class="c">[대조] 생성된 집계를 고정 로직으로 다시 계산</span>
  <span class="g">11/11 일치</span></div>
<p class="lead">모델이 낸 숫자가 맞는지를 모델에게 묻지 않음. 같은 집계를 고정 로직으로
다시 구해 대조하고, 어긋나면 어긋난 항목을 그대로 표시함.</p>
<p class="lead">매 실행은 원장으로 남아 어느 단계가 어느 제공자로 돌았는지 파일에 기록됨.</p></section>''',

            f'''<section><p class="kicker">실행</p>
<h2>네 플랫폼이 실제로 호출됨</h2>
<div class="term"><span class="c">$ pharmasignal run "antibody-drug conjugate"</span>

  단계      제공자                      상태
  <span class="c">--------------------------------------------</span>
  수집      Bright Data (SERP)          <span class="g">실행</span>
  판단      Qwen Cloud                  <span class="g">실행</span>
  실행      Daytona                     <span class="g">실행</span>
  반출금지  Nosana                      <span class="g">실행</span>

  실제 호출된 스폰서 플랫폼: <span class="g">4개</span></div>
<p class="lead">폴백이 조용히 일어나면 데모가 거짓말이 됨. 단계마다 실경로인지 폴백인지
기록해 마지막에 표로 냄.</p></section>''',

            f'''<section><p class="kicker">결과</p>
<h2>계열을 나란히 놓으면 지형이 보임</h2>
<div class="bars">{b}</div>
<p class="lead">계열당 마흔 건 수집. 오른쪽은 후기 임상 비중으로, 분모는 단계가 표기된
시험만 씀. 표본이 세 건뿐이던 계열은 비율이 우연에 좌우되어 뺌.</p></section>''',

            f'''<section><p class="kicker">완성도</p>
<h2>되는 것과 안 되는 것을 구분해서 씀</h2>
<div class="stats">
<div class="stat"><b>4/4</b><span>실제 호출된 플랫폼</span></div>
<div class="stat"><b>19</b><span>자동 테스트</span></div>
<div class="stat"><b>4/4</b><span>완료 게이트</span></div>
<div class="stat"><b>0</b><span>반출 금지 경로의 폴백</span></div></div>
<p class="lead">키가 하나도 없는 상태에서도 파이프라인이 완주하는지를 테스트로 확인함.
만든 쪽과 검수하는 쪽을 나눠, 검수 에이전트가 직접 실행해 판정함.</p></section>''',

            f'''<section class="center"><p class="kicker">PharmaSignal</p>
<h1>데이터를 못 내보낸다면,<br>에이전트를 그리로 보냄</h1>
<p class="lead">규제가 막는 것은 데이터의 이동이지 분석 자체가 아님. 경로를 나누면 둘 다 됨.</p>
<p class="thanks">감사합니다</p>
<p class="lead">github.com/kakyungkim/pharmasignal</p></section>''',
        ]
    return [
        f'''<section class="center"><p class="kicker">Agent Forge Seoul 2026</p>
<h1>PharmaSignal</h1>
<p class="lead">An agent that scans drug-safety signals and builds its own evidence.</p>
<div class="tags"><span>Bright Data</span><span>Qwen Cloud</span><span>Daytona</span><span>Nosana</span></div></section>''',

        f'''<section><p class="kicker">The problem</p>
<h2>Scattered sources, scanned by hand every day</h2>
<ul><li>Registries, regulatory filings and trade press all update in different formats</li>
<li>Many of those sites block automated collection outright</li>
<li>Analysts open ten tabs every morning and start reading</li></ul>
<p class="lead">And a larger wall sits behind all of it.</p></section>''',

        f'''<section><p class="kicker">The larger wall</p>
<h2>Internal clinical documents cannot leave</h2>
<p class="quote">Automate the public analysis and the data that matters most is still out of reach</p>
<p class="lead">What blocks AI in pharma is not model quality. It is this export restriction,
and it usually arrives alongside a team that has no GPU on hand.</p></section>''',

        f'''<section><p class="kicker">The approach</p>
<h2>Split the inference path by data sensitivity</h2>
<div class="grid">{c}</div>
<p class="lead">Public data goes through commercial APIs. Restricted text is sent only
to an endpoint we designate.</p>
<p class="lead" style="font-size:clamp(.86rem,1.6vw,1.02rem)">The idea is not new. LiteLLM and
Portkey ship the same routing, and PAPILLON (NAACL 2025) studies the same problem. What differs
here is the default: cross-tier fallback is forbidden.</p></section>''',

        f'''<section><p class="kicker">By design</p>
<h2>This path alone has no fallback</h2>
<div class="term">build_sovereign() → <span class="r">None</span>
<span class="c">unavailable means we drop the feature and skip the stage</span></div>
<p class="lead">Every other stage degrades gracefully. A fallback here would quietly leak
restricted text to a commercial API, so losing the feature is the better trade.</p></section>''',

        f'''<section><p class="kicker">Verification</p>
<h2>Code re-checks what the model produced</h2>
<p class="lead" style="font-size:clamp(.86rem,1.6vw,1.02rem)">An established technique. PAL, PoT and LEVER set the principle, and it has already been applied in pharmacovigilance.</p>
<div class="term"><span class="c">[crosscheck] recomputing the aggregates with fixed logic</span>
  <span class="g">11/11 agree</span></div>
<p class="lead">We never ask the model whether its own numbers are right. The same aggregates
are recomputed in fixed code and compared, and any disagreement is printed as it is.</p>
<p class="lead">Every run also writes a ledger recording which provider served which stage.</p></section>''',

        f'''<section><p class="kicker">Live run</p>
<h2>All four platforms are actually called</h2>
<div class="term"><span class="c">$ pharmasignal run "antibody-drug conjugate"</span>

  stage      provider                    status
  <span class="c">--------------------------------------------</span>
  collect    Bright Data (SERP)          <span class="g">LIVE</span>
  reason     Qwen Cloud                  <span class="g">LIVE</span>
  execute    Daytona                     <span class="g">LIVE</span>
  restricted Nosana                      <span class="g">LIVE</span>

  sponsor platforms actually called: <span class="g">4</span></div>
<p class="lead">A fallback that happens quietly turns a demo into a lie. Each stage records
whether it ran live, and the table at the end says so plainly.</p></section>''',

        f'''<section><p class="kicker">Findings</p>
<h2>Put the modalities side by side</h2>
<div class="bars">{b}</div>
<p class="lead">Forty records queried per modality. The right column is the late-phase share,
with only staged trials in the denominator. One modality returned three records and was
dropped, since a ratio drawn from three is noise.</p></section>''',

        f'''<section><p class="kicker">Rigor</p>
<h2>Say plainly what worked and what did not</h2>
<div class="stats">
<div class="stat"><b>4/4</b><span>platforms called live</span></div>
<div class="stat"><b>19</b><span>automated tests</span></div>
<div class="stat"><b>4/4</b><span>completion gates</span></div>
<div class="stat"><b>0</b><span>fallbacks on the restricted path</span></div></div>
<p class="lead">One test runs the whole pipeline with zero API keys to prove it still finishes.
A separate verifier agent executed everything and judged it, so nothing passed on looks-right alone.</p></section>''',

        f'''<section class="center"><p class="kicker">PharmaSignal</p>
<h1>If the data can't leave,<br>send the agent to it</h1>
<p class="lead">Regulation blocks the movement of data, not the analysis.
Split the path and you get both.</p>
<p class="thanks">Thank you</p>
<p class="lead">github.com/kakyungkim/pharmasignal</p></section>''',
    ]


def render(ko: bool) -> str:
    body = slides(ko)
    total = len(body)
    out = []
    for i, s in enumerate(body, 1):
        out.append(s.replace("<section", f'<section', 1).replace(
            ">", f'><span class="num">{i:02d} / {total:02d}</span>', 1))
    other = "pharmasignal-en.html" if ko else "pharmasignal-ko.html"
    label = "EN" if ko else "한국어"
    lang = "ko" if ko else "en"
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>PharmaSignal</title><style>{CSS}</style></head><body>'
            + "\n".join(out)
            + f'<a class="lang" href="{other}">{label}</a>' + NAV + "</body></html>")


if __name__ == "__main__":
    for ko, name in [(True, "pharmasignal-ko.html"), (False, "pharmasignal-en.html")]:
        p = HERE / name
        p.write_text(render(ko))
        print(f"  {name}  {p.stat().st_size // 1024}KB")
    print("\n해커톤 제출본은 pharmasignal-*-v1.html로 보존됨")
