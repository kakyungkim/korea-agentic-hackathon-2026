"""Night Shift 아침 보고서 생성기 (LLM 없이 동작).

실험 결과 목록(runner 결과 + critic 판정)을 받아 `morning_report.md`와 단일 파일
`morning_report.html`을 만든다. HTML은 반응형(viewport meta, max-width 컨테이너,
640px 이하 단일 컬럼)이고 외부 자원을 참조하지 않는다.

입력 레코드 형식(make_record로 생성):
{"goal": str, "runner": <run_experiment 결과>, "critic": <evaluate_experiment 결과>}
정책 감사 요약은 dict로 받는다. 예: {"blocked_network": 3, "blocked_write": 1, "blocked_exec": 0,
"allowed_hosts": [...], "log_path": "..."}.
"""
from __future__ import annotations

import html
import json
import os
import time
from typing import Any, Sequence

VERDICT_LABEL = {"accept": "통과", "reject": "반려"}
STATUS_LABEL = {"ok": "테스트 통과", "tests_failed": "테스트 실패", "apply_failed": "패치 적용 실패",
                "timeout": "시간 초과", "error": "실행 오류"}
AUDIT_LABEL = {"blocked_network": "차단된 네트워크 시도", "blocked_write": "차단된 쓰기 시도",
               "blocked_exec": "차단된 실행 시도", "blocked_secret_access": "차단된 비밀 접근",
               "guardrail_rejected_goals": "가드레일이 거절한 목표 입력"}


def make_record(goal: str, runner_result: dict[str, Any], critic_report: dict[str, Any]) -> dict[str, Any]:
    r = dict(runner_result)
    r.pop("diff_text", None)  # 보고서에는 diff 전문 대신 stat만 싣는다
    return {"goal": goal, "runner": r, "critic": critic_report}


# ---------------------------------------------------------------------------
# 수치 정리
# ---------------------------------------------------------------------------
def _fmt(v: Any, suffix: str = "", nd: int = 2) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{nd}f}{suffix}"
    return f"{v}{suffix}"


def _metrics_rows(runner: dict[str, Any]) -> list[tuple[str, str, str]]:
    b, a = runner.get("before") or {}, runner.get("after") or {}
    tb, ta = b.get("tests") or {}, a.get("tests") or {}
    rows = [
        ("통과 테스트", _fmt(tb.get("passed")), _fmt(ta.get("passed"))),
        ("실패·오류", _fmt((tb.get("failed", 0) or 0) + (tb.get("errors", 0) or 0)) if tb else "-",
         _fmt((ta.get("failed", 0) or 0) + (ta.get("errors", 0) or 0)) if ta else "-"),
        ("건너뜀(skip/xfail)", _fmt((tb.get("skipped", 0) or 0) + (tb.get("xfailed", 0) or 0)) if tb else "-",
         _fmt((ta.get("skipped", 0) or 0) + (ta.get("xfailed", 0) or 0)) if ta else "-"),
        ("커버리지", _fmt(b.get("coverage_pct"), "%"), _fmt(a.get("coverage_pct"), "%")),
        ("테스트 소요", _fmt(tb.get("duration_s"), "s", 1), _fmt(ta.get("duration_s"), "s", 1)),
    ]
    bb, ab = b.get("bench") or {}, a.get("bench") or {}
    if bb or ab:
        rows.append(("벤치마크 중앙값", _fmt(bb.get("median_s"), "s", 4), _fmt(ab.get("median_s"), "s", 4)))
    return rows


def _summary(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    acc = sum(1 for r in records if (r.get("critic") or {}).get("verdict") == "accept")
    rej = n - acc
    failed_checks: dict[str, int] = {}
    for r in records:
        for c in (r.get("critic") or {}).get("checks", []):
            if not c.get("passed"):
                failed_checks[c["name"]] = failed_checks.get(c["name"], 0) + 1
    total_s = sum(((r.get("runner") or {}).get("durations_s") or {}).get("total", 0) or 0 for r in records)
    return {"total": n, "accepted": acc, "rejected": rej, "failed_checks": failed_checks, "wall_s": round(total_s, 1)}


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def render_markdown(records: Sequence[dict[str, Any]], policy_audit: dict[str, Any] | None = None,
                    title: str = "Night Shift 아침 보고서", generated_at: str | None = None) -> str:
    generated_at = generated_at or time.strftime("%Y-%m-%d %H:%M:%S %z")
    s = _summary(records)
    out = [f"# {title}", "", f"생성 시각: {generated_at}", "",
           f"실험 {s['total']}건 중 통과 {s['accepted']}건, 반려 {s['rejected']}건. 실행 시간 합계 {s['wall_s']}초.", ""]
    if s["failed_checks"]:
        out.append("반려 사유별 건수: " + ", ".join(f"{k} {v}건" for k, v in sorted(s["failed_checks"].items())))
        out.append("")
    out.append("## 실험 카드")
    out.append("")
    for i, rec in enumerate(records, 1):
        run, crit = rec.get("runner") or {}, rec.get("critic") or {}
        verdict = crit.get("verdict", "reject")
        out.append(f"### {i}. [{VERDICT_LABEL.get(verdict, verdict)}] {rec.get('goal') or run.get('goal') or '(목표 없음)'}")
        out.append("")
        out.append(f"- 실험 ID: `{run.get('id')}`, 브랜치 `{run.get('branch')}`, 실행 상태: {STATUS_LABEL.get(run.get('status'), run.get('status'))}")
        fc = run.get("files_changed") or []
        out.append(f"- 변경 파일 {len(fc)}개: " + (", ".join(f"`{f}`" for f in fc) if fc else "-"))
        if run.get("diff_stat"):
            out.append("")
            out.append("```")
            out.append(run["diff_stat"])
            out.append("```")
        out.append("")
        out.append("| 지표 | 전 | 후 |")
        out.append("|---|---|---|")
        for name, bv, av in _metrics_rows(run):
            out.append(f"| {name} | {bv} | {av} |")
        out.append("")
        out.append(f"크리틱 판정: **{VERDICT_LABEL.get(verdict, verdict)}**")
        out.append("")
        for c in crit.get("checks", []):
            mark = "통과" if c.get("passed") else "실패"
            out.append(f"- [{mark}] {c.get('name')}: {c.get('reason')}")
        if crit.get("required_followups"):
            out.append("")
            out.append("후속 조치:")
            for f in crit["required_followups"]:
                out.append(f"- {f}")
        out.append("")
        if verdict == "accept" and run.get("apply_cmd"):
            out.append("적용 명령:")
            out.append("")
            out.append("```bash")
            out.append(run["apply_cmd"])
            out.append("```")
            out.append("")
    out.append("## 정책 감사 요약")
    out.append("")
    audit = policy_audit or {}
    if not audit:
        out.append("정책 감사 입력이 없다. [unverified]")
    else:
        out.append("| 항목 | 값 |")
        out.append("|---|---|")
        for k, v in audit.items():
            label = AUDIT_LABEL.get(k, k)
            val = ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v)
            out.append(f"| {label} | {val} |")
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
_CSS = """
:root{--bg:#f6f7f9;--card:#ffffff;--ink:#1f2933;--muted:#616e7c;--line:#e4e7eb;--accept:#2f7d4f;--accept-bg:#e6f4ea;
--reject:#a4402a;--reject-bg:#fbe9e5;--code:#f0f2f5;--accent:#3b5bdb}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;line-height:1.55}
.wrap{width:100%;max-width:1080px;margin:0 auto;padding:clamp(16px,3vw,32px)}
header h1{font-size:clamp(1.4rem,2.5vw,2rem);margin:0 0 4px}
header p{margin:0;color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi .n{font-size:clamp(1.4rem,2.2vw,1.9rem);font-weight:700}
.kpi .l{color:var(--muted);font-size:.85rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;display:flex;flex-direction:column;gap:12px;min-width:0}
.card h3{margin:0;font-size:1.05rem;display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap}
.badge{display:inline-block;font-size:.75rem;font-weight:700;padding:2px 8px;border-radius:999px;white-space:nowrap}
.badge.accept{background:var(--accept-bg);color:var(--accept)}
.badge.reject{background:var(--reject-bg);color:var(--reject)}
.meta{color:var(--muted);font-size:.85rem;word-break:break-all}
pre{background:var(--code);border-radius:8px;padding:10px 12px;margin:0;overflow-x:auto;font-size:.8rem;line-height:1.45}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.85em}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
ul.checks{list-style:none;margin:0;padding:0;font-size:.88rem}
ul.checks li{padding:4px 0;border-bottom:1px dashed var(--line);display:flex;gap:8px;align-items:flex-start}
ul.checks li:last-child{border-bottom:0}
.dot{flex:0 0 10px;width:10px;height:10px;border-radius:50%;margin-top:7px}
.dot.ok{background:var(--accept)}.dot.ng{background:var(--reject)}
.followups{background:var(--reject-bg);border-radius:8px;padding:10px 12px;font-size:.88rem}
.followups ul{margin:4px 0 0 18px;padding:0}
.apply{font-size:.85rem}.apply pre{white-space:pre-wrap;word-break:break-all}
section.audit{margin-top:32px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}
section.audit h2{margin:0 0 10px;font-size:1.15rem}
section.audit th{white-space:nowrap;width:1%}section.audit td{word-break:break-word}
footer{color:var(--muted);font-size:.8rem;margin-top:28px;text-align:center}
@media (max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}.cards{grid-template-columns:1fr}.card{padding:14px}table{font-size:.85rem}}
"""


def _e(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def _card_html(i: int, rec: dict[str, Any]) -> str:
    run, crit = rec.get("runner") or {}, rec.get("critic") or {}
    verdict = crit.get("verdict", "reject")
    goal = rec.get("goal") or run.get("goal") or "(목표 없음)"
    fc = run.get("files_changed") or []
    rows = "".join(f"<tr><td>{_e(n)}</td><td class='num'>{_e(b)}</td><td class='num'>{_e(a)}</td></tr>" for n, b, a in _metrics_rows(run))
    checks = "".join(
        f"<li><span class='dot {'ok' if c.get('passed') else 'ng'}'></span><span><strong>{_e(c.get('name'))}</strong> {_e(c.get('reason'))}</span></li>"
        for c in crit.get("checks", []))
    follow = ""
    if crit.get("required_followups"):
        follow = "<div class='followups'><strong>후속 조치</strong><ul>" + "".join(f"<li>{_e(f)}</li>" for f in crit["required_followups"]) + "</ul></div>"
    apply_html = ""
    if verdict == "accept" and run.get("apply_cmd"):
        apply_html = f"<div class='apply'><strong>적용 명령</strong><pre><code>{_e(run['apply_cmd'])}</code></pre></div>"
    stat = f"<pre>{_e(run.get('diff_stat'))}</pre>" if run.get("diff_stat") else ""
    return f"""<article class="card" data-verdict="{_e(verdict)}">
<h3><span class="badge {_e(verdict)}">{_e(VERDICT_LABEL.get(verdict, verdict))}</span><span>{i}. {_e(goal)}</span></h3>
<div class="meta">ID <code>{_e(run.get('id'))}</code> · 브랜치 <code>{_e(run.get('branch'))}</code> · {_e(STATUS_LABEL.get(run.get('status'), run.get('status')))} · 변경 파일 {len(fc)}개{(': ' + _e(', '.join(fc))) if fc else ''}</div>
{stat}
<table><thead><tr><th>지표</th><th class="num">전</th><th class="num">후</th></tr></thead><tbody>{rows}</tbody></table>
<div><strong>크리틱 판정: {_e(VERDICT_LABEL.get(verdict, verdict))}</strong><ul class="checks">{checks}</ul></div>
{follow}{apply_html}
</article>"""


def render_html(records: Sequence[dict[str, Any]], policy_audit: dict[str, Any] | None = None,
                title: str = "Night Shift 아침 보고서", generated_at: str | None = None) -> str:
    generated_at = generated_at or time.strftime("%Y-%m-%d %H:%M:%S %z")
    s = _summary(records)
    cards = "\n".join(_card_html(i, r) for i, r in enumerate(records, 1))
    audit = policy_audit or {}
    if audit:
        tabular = {k: v for k, v in audit.items() if not (isinstance(v, str) and len(v) > 40)}
        notes = {k: v for k, v in audit.items() if k not in tabular}
        audit_rows = "".join(
            f"<tr><th>{_e(AUDIT_LABEL.get(k, k))}</th><td class='num'>{_e(', '.join(map(str, v)) if isinstance(v, (list, tuple)) else v)}</td></tr>"
            for k, v in tabular.items())
        audit_html = f"<table><tbody>{audit_rows}</tbody></table>" + "".join(
            f"<p class='meta'><strong>{_e(AUDIT_LABEL.get(k, k))}</strong>: {_e(v)}</p>" for k, v in notes.items())
    else:
        audit_html = "<p class='meta'>정책 감사 입력이 없다. [unverified]</p>"
    fails = ", ".join(f"{k} {v}건" for k, v in sorted(s["failed_checks"].items())) or "없음"
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
<header>
<h1>{_e(title)}</h1>
<p>생성 시각 {_e(generated_at)} · 실험 {s['total']}건 · 실행 시간 합계 {s['wall_s']}초</p>
</header>
<section class="kpis">
<div class="kpi"><div class="n">{s['total']}</div><div class="l">실험</div></div>
<div class="kpi"><div class="n" style="color:var(--accept)">{s['accepted']}</div><div class="l">통과</div></div>
<div class="kpi"><div class="n" style="color:var(--reject)">{s['rejected']}</div><div class="l">반려</div></div>
<div class="kpi"><div class="n">{sum(int(v) for k, v in audit.items() if k.startswith('blocked') and isinstance(v, (int, float)))}</div><div class="l">정책 차단 시도</div></div>
</section>
<p class="meta">반려 사유별 건수: {_e(fails)}</p>
<section class="cards">
{cards}
</section>
<section class="audit">
<h2>정책 감사 요약</h2>
{audit_html}
</section>
<footer>Night Shift · 규칙 기반 크리틱과 실행기는 LLM 없이 동작한다. 모든 수치는 실행 출력에서 읽었다.</footer>
</div>
</body>
</html>
"""


def write_report(records: Sequence[dict[str, Any]], out_dir: str, policy_audit: dict[str, Any] | None = None,
                 title: str = "Night Shift 아침 보고서", basename: str = "morning_report") -> dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S %z")
    md_path = os.path.join(out_dir, f"{basename}.md")
    html_path = os.path.join(out_dir, f"{basename}.html")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(records, policy_audit, title, generated_at))
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(records, policy_audit, title, generated_at))
    return {"md": md_path, "html": html_path}


if __name__ == "__main__":  # python nightshift_report.py results.json out_dir
    import sys

    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    recs = data["experiments"] if isinstance(data, dict) else data
    audit = data.get("policy_audit") if isinstance(data, dict) else None
    print(json.dumps(write_report(recs, sys.argv[2], audit), ensure_ascii=False))
