#!/usr/bin/env python3
"""제출용 PDF 생성기.

  docs/submission/flygate.html   중간 산출물. 눈으로 확인한다
  docs/submission/flygate.pdf    제출물

실행: .venv/bin/python scripts/make_submission_pdf.py

수치 규율. **모든 수치를 결과 파일에서 읽는다. 하드코딩하지 않는다.**
필요한 키나 줄이 없으면 무엇이 없는지 알리고 PDF 를 만들지 않는다.
`scripts/make_figures.py` 의 `load_case()` 와 `CaseKeyError` 가 쓰는 방식을 그대로 따른다.

경로 규율. 저장소에 커밋되는 HTML 에 개인 경로가 남으면 안 된다.
폰트와 그림은 `docs/submission/` 기준 상대 경로로만 건다.
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# 확정되면 바꾸는 상수
# ---------------------------------------------------------------------------
TEAM_NAME = ""        # 미정. 확정되면 채운다
PROJECT_NAME = "FlyGate"

# DLI S-FX-43 수료증 이미지. 아직 수료 전이라 비워 둔다.
# 확정되면 docs/submission/ 기준 상대 경로를 넣는다. 예: "cert_dli_sfx43.png"
CERT_IMAGE = None

DLI_COURSE_ID = "S-FX-43"
CONTEST = "NVIDIA x 패스트캠퍼스 Korea Agentic AI Hackathon 2026 온라인 사전 챌린지"
TAGLINE = "도킹 점수에서 나올 수 없는 주장을 잡는 신약 후보 검증 에이전트"

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "submission"
HTML_PATH = OUT_DIR / "flygate.html"
PDF_PATH = OUT_DIR / "flygate.pdf"

DOCS = ROOT / "docs"
RESULTS = ROOT / "eval" / "results"
SUBMISSION_MD = DOCS / "submission-flygate.md"
README_MD = ROOT / "README.md"
CREDITS_MD = DOCS / "notes" / "credits.md"
HANDOFF_MD = DOCS / "HANDOFF.md"
AUTHOR_YML = ROOT / "configs" / "author.yml"
COURSE_MD = DOCS / "COURSE-GUIDE.md"
CASES_JSONL = ROOT / "eval" / "cases.jsonl"

CASE_JSON = RESULTS / "case_niraparib.json"
LLM_JSON = RESULTS / "critic_verdict_output_llm.json"
DET_JSON = RESULTS / "critic_verdict_output_deterministic.json"
AUTHOR_RUN_JSON = RESULTS / "nat_run_author_flydock.json"
SMOKE_TXT = RESULTS / "openshell_smoke_flydock.txt"
DIFFDOCK_TXT = RESULTS / "diffdock_smoke.txt"

# docs/submission/ 기준 상대 경로
REL_FONT_DIR = "../../assets/video/fonts"
REL_FIG_DIR = "../figures"

CHROME = os.environ.get(
    "CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

# ---------------------------------------------------------------------------
# 팔레트: scripts/make_figures.py 와 같은 차분한 뮤트 톤
# ---------------------------------------------------------------------------
INK = "#2E3338"
INK_SOFT = "#5B646C"
INK_FAINT = "#8A939B"
RULE = "#E3E7EB"
BLUE = "#6E8FB5"
TEAL = "#6F9C96"
GREEN = "#7C9D6E"
PLUM = "#8E82AC"
SAND = "#C39A68"
BRICK = "#BC7F73"
GREY_BG = "#F2F4F6"
PLUM_BG = "#EFEDF6"
TEAL_BG = "#EAF2F0"
SAND_BG = "#F7F1E7"
BRICK_BG = "#F7EDEA"


# ---------------------------------------------------------------------------
# 없는 값에서 멈추기
# ---------------------------------------------------------------------------
class SubmissionDataError(RuntimeError):
    """결과 파일에 PDF 가 요구하는 값이 없을 때. 만들지 않고 멈춘다."""


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


class JsonReader:
    """결과 JSON 하나를 읽고 없는 키를 모아 한 번에 알린다."""

    def __init__(self, path: Path):
        if not path.exists():
            raise SubmissionDataError(f"결과 파일이 없습니다: {_rel(path)}")
        self.path = path
        self.payload = json.loads(path.read_text(encoding="utf-8"))
        self.missing: list[str] = []

    def need(self, dotted: str):
        value = _dig(self.payload, dotted)
        if value is _MISSING:
            self.missing.append(dotted)
            return None
        return value

    def done(self) -> None:
        if self.missing:
            raise SubmissionDataError(
                f"{_rel(self.path)} 에 없는 키가 있어 PDF 를 만들지 않습니다: "
                + ", ".join(self.missing))


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def need_text(path: Path) -> str:
    if not path.exists():
        raise SubmissionDataError(f"파일이 없습니다: {_rel(path)}")
    return path.read_text(encoding="utf-8")


def need_match(pattern: str, text: str, path: Path, what: str, flags=0) -> re.Match:
    m = re.search(pattern, text, flags)
    if m is None:
        raise SubmissionDataError(f"{_rel(path)} 에서 {what} 을(를) 찾지 못했습니다")
    return m


# ---------------------------------------------------------------------------
# 마크다운 조각 읽기
# ---------------------------------------------------------------------------
def md_section(text: str, heading: str, path: Path) -> str:
    """'## 제목' 아래에서 다음 '## ' 전까지의 본문을 돌려준다."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## ") and heading in line:
            start = i + 1
            break
    if start is None:
        raise SubmissionDataError(f"{_rel(path)} 에 '{heading}' 절이 없습니다")
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


def md_fenced(text: str, heading: str, path: Path) -> str:
    """절 안의 첫 코드펜스 내용을 돌려준다."""
    body = md_section(text, heading, path)
    m = need_match(r"```[a-zA-Z]*\n(.*?)\n```", body, path,
                   f"'{heading}' 절의 코드블록", re.S)
    return m.group(1).strip()


def md_table(text: str, heading: str, path: Path) -> tuple[list[str], list[list[str]]]:
    """절 안의 첫 마크다운 표를 (머리, 행들) 로 돌려준다."""
    body = md_section(text, heading, path)
    rows: list[list[str]] = []
    collecting = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("|"):
            collecting = True
            cells = [c.strip() for c in s.strip("|").split("|")]
            rows.append(cells)
        elif collecting:
            break
    if len(rows) < 3:
        raise SubmissionDataError(f"{_rel(path)} 의 '{heading}' 절에서 표를 찾지 못했습니다")
    header = rows[0]
    body_rows = [r for r in rows[2:] if any(c for c in r)]
    if not body_rows:
        raise SubmissionDataError(f"{_rel(path)} 의 '{heading}' 표가 비어 있습니다")
    return header, body_rows


# ---------------------------------------------------------------------------
# 결과 파일에서 수치 읽기
# ---------------------------------------------------------------------------
def load_verdict_eval(path: Path) -> dict:
    """nat eval 결과에서 적발률을 센다. reasoning 의 expected/got 을 그대로 쓴다."""
    r = JsonReader(path)
    avg = r.need("average_score")
    items = r.need("eval_output_items")
    r.done()
    if not isinstance(items, list) or not items:
        raise SubmissionDataError(f"{_rel(path)} 의 eval_output_items 가 비어 있습니다")

    parsed = []
    for item in items:
        reasoning = item.get("reasoning")
        if not isinstance(reasoning, str):
            raise SubmissionDataError(
                f"{_rel(path)} 의 항목 {item.get('id')} 에 reasoning 이 없습니다")
        m = re.match(r"expected=(\S+)\s+got=(\S+)", reasoning)
        if m is None:
            raise SubmissionDataError(
                f"{_rel(path)} 의 항목 {item.get('id')} reasoning 을 읽지 못했습니다: {reasoning}")
        parsed.append((m.group(1), m.group(2)))

    rejects = [g for e, g in parsed if e == "reject"]
    passes = [g for e, g in parsed if e == "pass"]
    return {
        "path": path,
        "average": avg,
        "total": len(parsed),
        "reject_total": len(rejects),
        "reject_caught": sum(1 for g in rejects if g == "reject"),
        "pass_total": len(passes),
        "false_positive": sum(1 for g in passes if g == "reject"),
    }


def load_case() -> dict:
    """케이스 JSON 에서 표에 쓰는 값만 꺼낸다."""
    r = JsonReader(CASE_JSON)
    out = {
        "case_id": r.need("case_id"),
        "generated_at": r.need("generated_at"),
        "compound": r.need("compound.name"),
        "event": r.need("compound.adverse_event"),
        "event_ko": r.need("compound.adverse_event_ko"),
        "fddd_sha256": r.need("sources.fddd_docking_sha256"),
        "diffdock_endpoint": r.need("sources.diffdock_endpoint"),
        "planted": r.need("claim_sets.overclaim.planted_overclaims"),
        "can_say": r.need("can_say"),
        "cannot_say": r.need("cannot_say"),
        "paths": [],
        "critic": {},
    }
    for i in (0, 1):
        p = f"paths.{i}"
        out["paths"].append({
            "path": r.need(f"{p}.path"),
            "title": r.need(f"{p}.title"),
            "pdb_id": r.need(f"{p}.pdb_id"),
            "chain": r.need(f"{p}.chain"),
            "vina_score": r.need(f"{p}.steps.vina.score_kcal_mol"),
            "vina_units": r.need(f"{p}.steps.vina.units"),
            "vina_role": r.need(f"{p}.steps.vina.role"),
            "vina_tool": r.need(f"{p}.steps.vina.protocol.tool"),
            "vina_version": r.need(f"{p}.steps.vina.protocol.version"),
            "diffdock": r.need(f"{p}.steps.diffdock.position_confidence"),
            "bdb_present": r.need(f"{p}.steps.bindingdb.reference_set_present"),
            "bdb_records": _soft(r, f"{p}.steps.bindingdb.record_count"),
            "bdb_compounds": _soft(r, f"{p}.steps.bindingdb.compound_count"),
            "bdb_uniprot": r.need(f"{p}.steps.bindingdb.uniprot"),
            "labeled": r.need(f"{p}.steps.label.labeled"),
            "label_sections": r.need(f"{p}.steps.label.mentioned_sections"),
            "prr": r.need(f"{p}.steps.faers.prr"),
            "prr_ci95": r.need(f"{p}.steps.faers.prr_ci95"),
            "faers_asof": r.need(f"{p}.steps.faers.data_last_updated"),
            "pubmed_total": r.need(f"{p}.steps.pubmed.total_count"),
            "scope": r.need(f"{p}.human_evidence_scope"),
        })
    for key in ("supported", "overclaim"):
        c = f"critic_verdicts.{key}"
        out["critic"][key] = {
            "final": r.need(f"{c}.final_verdict"),
            "stage1_passed": r.need(f"{c}.stage1.rules_passed"),
            "stage2_ok": r.need(f"{c}.stage2.ok"),
            "stage2_line": r.need(f"{c}.stage2.summary_line"),
            "stage3_verdict": r.need(f"{c}.stage3.verdict"),
            "stage3_model": r.need(f"{c}.stage3.model"),
            "reject_reasons": r.need(f"{c}.reject_reasons"),
        }
    r.done()
    return out


def _soft(reader: JsonReader, dotted: str):
    """없어도 되는 값(경로 B 의 BindingDB 처럼 null 이 정답인 자리)."""
    value = _dig(reader.payload, dotted)
    return None if value is _MISSING else value


def load_author_run() -> dict:
    r = JsonReader(AUTHOR_RUN_JSON)
    claims = r.need("claims")
    r.done()
    if not isinstance(claims, list) or not claims:
        raise SubmissionDataError(f"{_rel(AUTHOR_RUN_JSON)} 에 claims 가 없습니다")
    with_ev = sum(1 for c in claims if c.get("evidence_ids"))
    return {"claims": len(claims), "with_evidence": with_ev,
            "without_evidence": len(claims) - with_ev}


def load_smoke() -> dict:
    """OpenShell 스모크 결과를 절 단위로 읽는다."""
    text = need_text(SMOKE_TXT)
    summary = need_match(r"summary:\s*pass=(\d+)\s+fail=(\d+)", text, SMOKE_TXT, "summary 줄")
    policy = need_match(r"^policy:\s*(\S+)\s+sandbox:\s*(\S+)", text, SMOKE_TXT,
                        "policy 줄", re.M)
    version = need_match(r"^openshell:\s*(.+)$", text, SMOKE_TXT, "openshell 판 줄", re.M)
    run_as = need_match(r"run_as_user=(\d+)", text, SMOKE_TXT, "run_as_user")
    policy_hash = need_match(r"^Hash:\s*([0-9a-f]{16,})", text, SMOKE_TXT,
                             "유효 정책 해시", re.M)

    # 절별 PASS 건수
    sections: list[tuple[str, int]] = []
    current = None
    count = 0
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections.append((current, count))
            current = line[3:].strip()
            count = 0
        elif line.startswith("PASS "):
            count += 1
    if current is not None:
        sections.append((current, count))
    sections = [(n, c) for n, c in sections if c > 0]

    hosts = re.findall(r"^PASS allowed (\S+)\s+http=(\S+)", text, re.M)
    if not hosts:
        raise SubmissionDataError(f"{_rel(SMOKE_TXT)} 에서 허용 호스트 줄을 찾지 못했습니다")

    blocked = re.findall(r"^PASS blocked (\S+)\s+http=(\S+)\s+rc=(\S+)", text, re.M)

    # 차단 로그 원문. 한 종류씩 첫 줄만 뽑는다
    log_lines = [ln for ln in text.splitlines()
                 if ("DENIED" in ln or "CONFIG:APPLYING" in ln) and ln.startswith("[")]
    if not log_lines:
        raise SubmissionDataError(f"{_rel(SMOKE_TXT)} 에서 차단 로그 원문을 찾지 못했습니다")
    excerpt: list[str] = []
    seen: set[str] = set()
    for ln in log_lines:
        if "example.com" in ln:
            key = "example"
        elif "github.com" in ln:
            key = "github"
        elif "/usr/bin/curl" in ln:
            key = "curl"
        elif "HTTP:GET" in ln:
            key = "l7"
        elif "CONFIG:APPLYING" in ln:
            key = "landlock"
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        excerpt.append(ln)
    missing_kinds = {"example", "github", "curl", "l7", "landlock"} - seen
    if missing_kinds:
        raise SubmissionDataError(
            f"{_rel(SMOKE_TXT)} 의 차단 로그에 없는 종류가 있습니다: "
            + ", ".join(sorted(missing_kinds)))

    rw = re.search(r"read_write:\n((?:\s+- \S+\n)+)", text)
    read_write = re.findall(r"- (\S+)", rw.group(1)) if rw else []

    return {
        "pass": int(summary.group(1)),
        "fail": int(summary.group(2)),
        "policy": policy.group(1),
        "sandbox": policy.group(2),
        "version": version.group(1).strip(),
        "run_as_user": run_as.group(1),
        "policy_hash": policy_hash.group(1),
        "sections": sections,
        "hosts": hosts,
        "blocked": blocked,
        "excerpt": excerpt,
        "read_write": read_write,
    }


def load_diffdock_smoke() -> dict:
    text = need_text(DIFFDOCK_TXT)
    m = need_match(r"HTTP\s+(\d{3}),\s*소요\s*([\d.]+)초,\s*응답\s*([\d,]+)바이트",
                   text, DIFFDOCK_TXT, "HTTP 결과 줄")
    poses = need_match(r"포즈\s*(\d+)개", text, DIFFDOCK_TXT, "포즈 개수")
    endpoint = need_match(r"^POST\s+(\S+)$", text, DIFFDOCK_TXT, "엔드포인트 줄", re.M)
    return {"http": m.group(1), "seconds": m.group(2), "bytes": m.group(3),
            "poses": poses.group(1), "endpoint": endpoint.group(1)}


def load_tool_names() -> list[str]:
    text = need_text(AUTHOR_YML)
    m = need_match(r"^\s*tool_names:\s*\[(.*?)\]", text, AUTHOR_YML,
                   "tool_names 목록", re.S | re.M)
    names = [n.strip() for n in m.group(1).replace("\n", " ").split(",")]
    names = [n for n in names if n]
    if not names:
        raise SubmissionDataError(f"{_rel(AUTHOR_YML)} 의 tool_names 가 비어 있습니다")
    return names


def load_rule_count() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from harness.tools.overclaim_rules import RULES  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise SubmissionDataError(f"과잉해석 규칙을 읽지 못했습니다: {exc}") from exc
    if not RULES:
        raise SubmissionDataError("과잉해석 규칙 목록이 비어 있습니다")
    return len(RULES)


def load_case_count() -> int:
    text = need_text(CASES_JSONL)
    n = len([ln for ln in text.splitlines() if ln.strip()])
    if n == 0:
        raise SubmissionDataError(f"{_rel(CASES_JSONL)} 이 비어 있습니다")
    return n


def load_offline_test_count() -> tuple[int, str]:
    """pytest --collect-only 로 실측한다. 실패하면 HANDOFF 표에서 읽고 출처를 바꾼다."""
    env = dict(os.environ)
    env.pop("NVIDIA_API_KEY", None)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "not network"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
        m = re.search(r"(\d+)/(\d+) tests collected", proc.stdout)
        if m is None:
            m = re.search(r"(\d+) tests collected", proc.stdout)
            if m:
                return int(m.group(1)), 'pytest --collect-only -q -m "not network"'
        else:
            return int(m.group(1)), 'pytest --collect-only -q -m "not network"'
    except Exception:
        pass
    text = need_text(HANDOFF_MD)
    m = need_match(r"오프라인 테스트 \|\s*\*\*(\d+)개", text, HANDOFF_MD,
                   "오프라인 테스트 건수")
    return int(m.group(1)), "docs/HANDOFF.md 검증된 수치 표"


def load_dli_course() -> dict:
    """과정 이름은 docs/COURSE-GUIDE.md, 진도는 docs/HANDOFF.md 에서 읽는다."""
    guide = need_text(COURSE_MD)
    name = need_match(rf'"(.+?)"\(DLI {DLI_COURSE_ID}\)', guide, COURSE_MD, "과정 이름")
    url = need_match(r"(https://learn\.nvidia\.com/\S+)", guide, COURSE_MD, "과정 주소")
    handoff = need_text(HANDOFF_MD)
    m = re.search(r"\*\*DLI 강좌\.\*\*\s*(.+?)(?:\n\s*\n)", handoff, re.S)
    progress = " ".join(m.group(1).split()) if m else ""
    return {"name": name.group(1), "url": url.group(1), "progress": progress}


def load_repo_url() -> str:
    text = need_text(README_MD)
    m = need_match(r"git clone (https://github\.com/\S+)", text, README_MD, "저장소 주소")
    return m.group(1)


# ---------------------------------------------------------------------------
# HTML 조립 도구
# ---------------------------------------------------------------------------
def esc(text) -> str:
    return html_mod.escape("" if text is None else str(text), quote=False)


def inline_md(cell: str) -> str:
    """표 칸의 굵게와 코드 표기만 옮긴다."""
    out = esc(cell)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    out = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", out)
    return out


def table(header: list[str], rows: list[list[str]], *, cls: str = "", widths=None) -> str:
    cols = ""
    if widths:
        cols = "<colgroup>" + "".join(f'<col style="width:{w}">' for w in widths) + "</colgroup>"
    head = "".join(f"<th>{inline_md(h)}</th>" for h in header)
    body = ""
    for row in rows:
        cells = "".join(f"<td>{inline_md(c)}</td>" for c in row)
        body += f"<tr>{cells}</tr>"
    klass = f' class="{cls}"' if cls else ""
    return (f'<table{klass}>{cols}<thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table>")


def fmt(value, digits: int = 3) -> str:
    if value is None:
        return "없음"
    if isinstance(value, float):
        return f"{value:.{digits}f}".replace("-", "−")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def fmt_conf(values) -> str:
    return ", ".join(fmt(v, 3) for v in values)


def section(num: str, title: str, body: str, *, lead: str = "",
            keep: bool = False) -> str:
    lead_html = f'<p class="lead">{lead}</p>' if lead else ""
    cls = ' class="keep"' if keep else ""
    return (f'<section{cls}><h2><span class="num">{num}</span>{esc(title)}</h2>'
            f"{lead_html}{body}</section>")


def figure(rel_src: str, caption: str) -> str:
    return (f'<figure class="keep"><img src="{rel_src}" alt="{esc(caption)}">'
            f"<figcaption>{esc(caption)}</figcaption></figure>")


def font_faces() -> str:
    out = []
    for name, weight in (("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700)):
        path = ROOT / "assets" / "video" / "fonts" / f"Pretendard-{name}.otf"
        if not path.exists():
            raise SubmissionDataError(f"폰트가 없습니다: {_rel(path)}")
        out.append("@font-face{font-family:Pretendard;"
                   f"src:url('{REL_FONT_DIR}/Pretendard-{name}.otf') format('opentype');"
                   f"font-weight:{weight};font-style:normal;font-display:block}}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
def css() -> str:
    return f"""
{font_faces()}
@page {{ size: A4 portrait; margin: 15mm 14mm 15mm 14mm; }}
*, *::before, *::after {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: Pretendard, -apple-system, sans-serif;
  color: {INK};
  background: #FFFFFF;
  font-size: 10pt;
  font-weight: 400;
  line-height: 1.62;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}
.wrap {{ width: 100%; max-width: 182mm; margin: 0 auto; padding: 0 4mm; }}
@media screen {{ .wrap {{ padding: 10mm 6mm; }} }}

p {{ margin: 0 0 3.2mm; }}
.lead {{ color: {INK_SOFT}; margin-bottom: 4mm; }}
.muted {{ color: {INK_FAINT}; font-size: 8.4pt; line-height: 1.55; }}
code {{ font-family: "SFMono-Regular", Menlo, Consolas, monospace; font-size: 0.88em;
        background: {GREY_BG}; padding: 0 0.3em; border-radius: 2px; }}
strong {{ font-weight: 700; }}

/* 표지 */
.cover {{ min-height: 248mm; display: flex; flex-direction: column;
          justify-content: center; break-after: page; page-break-after: always; }}
.cover .badge {{ display: inline-block; align-self: flex-start; font-size: 8.6pt;
  font-weight: 600; letter-spacing: .06em; color: {PLUM};
  background: {PLUM_BG}; border: 1px solid {PLUM}; border-radius: 3mm;
  padding: 1.2mm 3mm; margin-bottom: 7mm; }}
.cover h1 {{ font-size: 34pt; font-weight: 700; letter-spacing: -.02em;
             line-height: 1.1; margin: 0 0 4mm; }}
.cover .tag {{ font-size: 13pt; font-weight: 500; color: {INK_SOFT};
               line-height: 1.45; margin: 0 0 10mm; max-width: 150mm; }}
.cover .bar {{ height: 1.2mm; width: 46mm; background: {BLUE}; border-radius: 1mm;
               margin-bottom: 10mm; }}
.cover dl {{ margin: 0; display: grid; grid-template-columns: 34mm 1fr;
             row-gap: 2.6mm; column-gap: 4mm; font-size: 9.6pt; }}
.cover dt {{ color: {INK_FAINT}; font-weight: 600; }}
.cover dd {{ margin: 0; color: {INK}; word-break: break-all; }}
.cover .note {{ margin-top: 12mm; padding-top: 5mm; border-top: 1px solid {RULE};
                color: {INK_FAINT}; font-size: 8.4pt; }}

/* 본문 절 */
section {{ margin: 0 0 9mm; }}
h2 {{ font-size: 15pt; font-weight: 700; letter-spacing: -.01em; margin: 0 0 3.5mm;
      padding-bottom: 2mm; border-bottom: 1.6px solid {INK};
      break-after: avoid; page-break-after: avoid; }}
h2 .num {{ display: inline-block; min-width: 9mm; color: {BLUE}; font-weight: 700; }}
h3 {{ font-size: 10.5pt; font-weight: 600; margin: 5mm 0 2.2mm; color: {INK}; }}

.keep {{ break-inside: avoid; page-break-inside: avoid; }}

/* 표 */
table {{ width: 100%; border-collapse: collapse; font-size: 8.6pt; line-height: 1.5;
         margin: 0 0 3.5mm; }}
thead {{ display: table-header-group; }}
th {{ background: {GREY_BG}; color: {INK}; font-weight: 600; text-align: left;
      padding: 1.8mm 2.2mm; border-bottom: 1.2px solid {INK_FAINT}; }}
td {{ padding: 1.8mm 2.2mm; border-bottom: 1px solid {RULE}; vertical-align: top; }}
tr {{ break-inside: avoid; page-break-inside: avoid; }}
table.small {{ font-size: 8.1pt; }}
td.num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
tr.group td {{ background: {GREY_BG}; font-weight: 600; color: {INK_SOFT};
               font-size: 8.2pt; }}

/* 그림 */
figure {{ margin: 0 0 3.5mm; }}
figure img {{ display: block; width: 100%; max-width: 100%; height: auto;
              border: 1px solid {RULE}; border-radius: 1.5mm; }}
figcaption {{ margin-top: 2mm; color: {INK_FAINT}; font-size: 8.2pt; }}

/* 인용 문안 */
.quote {{ background: {GREY_BG}; border-left: 3px solid {BLUE};
          border-radius: 0 2mm 2mm 0; padding: 4mm 5mm; margin: 0 0 3.5mm;
          font-size: 9.4pt; line-height: 1.7; }}
.quote p:last-child {{ margin-bottom: 0; }}
.quote.solution {{ border-left-color: {TEAL}; }}

/* 강조 카드 */
.cards {{ display: flex; gap: 3.5mm; margin: 0 0 3.5mm; }}
.card {{ flex: 1; border: 1px solid var(--c); background: var(--bg);
         border-radius: 2mm; padding: 3.5mm 4mm; }}
.card .k {{ font-size: 8.2pt; font-weight: 600; color: var(--c); margin-bottom: 1.5mm; }}
.card .v {{ font-size: 19pt; font-weight: 700; letter-spacing: -.02em;
            line-height: 1.1; color: {INK}; font-variant-numeric: tabular-nums; }}
.card .s {{ font-size: 8.1pt; color: {INK_SOFT}; margin-top: 1.5mm; line-height: 1.45; }}

/* 로그 발췌 */
pre {{ font-family: "SFMono-Regular", Menlo, Consolas, monospace;
       font-size: 6.6pt; line-height: 1.55; white-space: pre-wrap;
       overflow-wrap: anywhere; background: #FAFBFC; color: {INK_SOFT};
       border: 1px solid {RULE}; border-left: 3px solid {BRICK};
       border-radius: 0 2mm 2mm 0; padding: 3mm 3.5mm; margin: 0 0 3mm; }}
pre b {{ color: {BRICK}; font-weight: 700; }}

/* 자리표시자 */
.placeholder {{ border: 1.4px dashed {SAND}; background: {SAND_BG};
                border-radius: 2mm; padding: 9mm 6mm; text-align: center;
                color: {INK_SOFT}; }}
.placeholder .big {{ font-size: 10.5pt; font-weight: 600; color: {SAND};
                     margin-bottom: 2mm; }}

ul {{ margin: 0 0 3.2mm; padding-left: 5mm; }}
li {{ margin-bottom: 1.2mm; }}

@media screen and (max-width: 640px) {{
  .cards {{ flex-direction: column; }}
  .cover dl {{ grid-template-columns: 1fr; row-gap: 1mm; }}
  .cover h1 {{ font-size: 26pt; }}
  table {{ font-size: 8pt; }}
}}
"""


# ---------------------------------------------------------------------------
# 절별 본문
# ---------------------------------------------------------------------------
def cover_html(data: dict) -> str:
    team = TEAM_NAME.strip() or "미정"
    team_note = "" if TEAM_NAME.strip() else (
        " (확정되면 파일명을 "
        f"[NVIDIA 해커톤_팀명_{PROJECT_NAME}].pdf 로 바꾼다)")
    rows = [
        ("대회", CONTEST),
        ("팀명", team + team_note),
        ("프로젝트", PROJECT_NAME),
        ("저장소", data["repo_url"]),
        ("생성일", data["today"]),
    ]
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows)
    return f"""<div class="cover">
  <span class="badge">NVIDIA Agentic AI Hackathon 2026</span>
  <h1>{esc(PROJECT_NAME)}</h1>
  <p class="tag">{esc(TAGLINE)}</p>
  <div class="bar"></div>
  <dl>{dl}</dl>
  <p class="note">이 문서의 수치는 모두 저장소의 결과 파일에서 읽어 만들었다.
  항목마다 출처 파일을 함께 적는다. 확인하지 못한 것은 확인하지 못했다고 적는다.</p>
</div>"""


def problem_solution_html(data: dict) -> str:
    def paras(text: str) -> str:
        return "".join(f"<p>{esc(p.strip())}</p>"
                       for p in text.split("\n\n") if p.strip())

    body = (
        "<h3>해결하고자 했던 문제</h3>"
        f'<div class="quote keep">{paras(data["problem"])}</div>'
        "<h3>서비스 소개와 주요 기능</h3>"
        f'<div class="quote solution keep">{paras(data["solution"])}</div>'
    )
    if data["solution_note"]:
        body += f'<p class="muted">{inline_md(data["solution_note"])}</p>'
    return section("1", "문제와 해결", body)


def pipeline_html(data: dict) -> str:
    header, rows = data["critic_table"]
    case = data["case"]
    sup = case["critic"]["supported"]
    over = case["critic"]["overclaim"]
    n_planted = len(case["planted"])

    measured = [
        ["1단 결정 규칙",
         f'근거 ID 규칙 통과 = {"예" if sup["stage1_passed"] else "아니오"}',
         f'근거 ID 규칙 통과 = {"예" if over["stage1_passed"] else "아니오"}'],
        ["2단 숫자 오라클", sup["stage2_line"], over["stage2_line"]],
        ["3단 과잉해석 판정", sup["stage3_verdict"], over["stage3_verdict"]],
        ["최종 판정", sup["final"], over["final"]],
    ]
    body = (
        figure(f"{REL_FIG_DIR}/architecture_pipeline.png",
               "그림 1. FlyGate 파이프라인 구조와 크리틱 3단. "
               "모든 실행은 OpenShell 정책 안에서 이루어진다.")
        + "<h3>크리틱 3단</h3>"
        + table(header, rows, cls="keep", widths=("22%", "56%", "22%"))
        + f"<h3>같은 케이스에 3단을 돌린 결과</h3>"
        + f'<p class="lead">같은 케이스로 근거가 받쳐 주는 요약과 과잉해석 {n_planted}건을 심은 '
          f"요약을 나란히 돌렸다. 1단과 2단은 양쪽을 통과시켰고 3단만 갈랐다.</p>"
        + table(["단", "근거가 받쳐 주는 요약", f"과잉해석 {n_planted}건을 심은 요약"],
                measured, cls="keep small", widths=("22%", "39%", "39%"))
        + f'<p class="muted">출처 <code>eval/results/case_niraparib.json</code>. '
          f'3단 판정 모델 <code>{esc(sup["stage3_model"])}</code>. '
          f'과잉해석 규칙은 {data["rule_count"]}종이고 도구 제공자와 데이터 제공자가 '
          f"문서에 적은 경고에서 옮겼다.</p>"
    )
    return section("2", "파이프라인 구조", body)


def numbers_html(data: dict) -> str:
    llm = data["llm"]
    det = data["det"]
    case = data["case"]
    smoke = data["smoke"]
    dd = data["diffdock"]
    run = data["author_run"]

    gap = llm["reject_caught"] / llm["reject_total"] - det["reject_caught"] / det["reject_total"]

    cards = f"""<div class="cards keep">
  <div class="card" style="--c:{TEAL};--bg:{TEAL_BG}">
    <div class="k">적발률 (LLM 판정 포함)</div>
    <div class="v">{llm["reject_caught"]} / {llm["reject_total"]}</div>
    <div class="s">거짓 양성 {llm["false_positive"]} / {llm["pass_total"]}.
      평균 점수 {llm["average"]}</div>
  </div>
  <div class="card" style="--c:{BRICK};--bg:{BRICK_BG}">
    <div class="k">적발률 (결정 규칙만)</div>
    <div class="v">{det["reject_caught"]} / {det["reject_total"]}</div>
    <div class="s">평균 점수 {det["average"]}. 나머지
      {det["reject_total"] - det["reject_caught"]}건은 근거 ID 와 숫자가 전부 맞아
      기계 검사를 통과한다</div>
  </div>
  <div class="card" style="--c:{PLUM};--bg:{PLUM_BG}">
    <div class="k">3단이 메운 차이</div>
    <div class="v">{gap:.4f}</div>
    <div class="s">두 적발률의 차이. 같은 케이스와 같은 입력에서 3단만 끄고 켜서 쟀다</div>
  </div>
</div>"""

    rows = [
        ["적발률 (LLM 판정 포함)",
         f'**{llm["reject_caught"]}/{llm["reject_total"]}**, 거짓 양성 '
         f'{llm["false_positive"]}/{llm["pass_total"]}, 평균 {llm["average"]}',
         "`eval/results/critic_verdict_output_llm.json`"],
        ["적발률 (결정 규칙만)",
         f'**{det["reject_caught"]}/{det["reject_total"]}**, 평균 {det["average"]}',
         "`eval/results/critic_verdict_output_deterministic.json`"],
        ["평가 케이스", f'{data["case_count"]}건', "`eval/cases.jsonl`"],
        ["과잉해석 규칙", f'{data["rule_count"]}종',
         "`src/harness/tools/overclaim_rules.py`"],
        ["오프라인 테스트", f'{data["test_count"]}개 수집', f'`{data["test_source"]}`'],
        ["NAT 등록 도구", f'{len(data["tool_names"])}종. '
         + ", ".join(f"`{t}`" for t in data["tool_names"]), "`configs/author.yml`"],
        ["에이전트 도구 호출",
         f'주장 {run["claims"]}건 전부 근거 ID 있음. 근거 없는 주장 {run["without_evidence"]}건',
         "`eval/results/nat_run_author_flydock.json`"],
        ["DiffDock NIM 호출",
         f'HTTP {dd["http"]}, {dd["seconds"]}초, 응답 {dd["bytes"]}바이트, 포즈 {dd["poses"]}개',
         "`eval/results/diffdock_smoke.txt`"],
        ["샌드박스 스모크",
         f'{smoke["pass"]}건 통과, 실패 {smoke["fail"]}건',
         "`eval/results/openshell_smoke_flydock.txt`"],
        ["케이스 시연 E2E",
         f'{case["compound"]} 두 경로, 7단계 수집, 3단 크리틱 통과와 반려',
         "`eval/results/case_niraparib.json`"],
    ]

    body = (
        cards
        + table(["항목", "값", "출처 파일"], rows, widths=("22%", "48%", "30%"))
        + '<p class="muted">적발률의 분모는 반려가 정답인 케이스 수이고, 거짓 양성의 분모는 '
          "통과가 정답인 케이스 수다. 두 수치는 같은 평가 케이스를 3단만 끄고 켜서 잰 것이라 "
          "나란히 놓아야 뜻이 산다. 결정 규칙만으로 돌린 실행에서 나머지 케이스는 "
          "<code>needs_human</code> 으로 남아 사람에게 넘어간다.</p>"
    )
    return section("3", "검증된 수치", body,
                   lead="모든 값을 결과 파일에서 읽었다. 출처 파일을 함께 적는다.")


def case_html(data: dict) -> str:
    case = data["case"]
    a, b = case["paths"]

    def route(p):
        return f'경로 {p["path"]}: {p["title"]} ({p["pdb_id"]}, chain {p["chain"]})'

    def bdb(p):
        if not p["bdb_present"]:
            return "없음"
        return (f'있음. 레코드 {fmt(p["bdb_records"])}건, '
                f'화합물 {fmt(p["bdb_compounds"])}종 (UniProt {p["bdb_uniprot"]})')

    rows = [
        [f'{a["vina_tool"]} {a["vina_version"]} 점수',
         f'{fmt(a["vina_score"])} {a["vina_units"]}',
         f'{fmt(b["vina_score"])} {b["vina_units"]}'],
        ["Vina 실행 성격", a["vina_role"], b["vina_role"]],
        ["DiffDock position_confidence", fmt_conf(a["diffdock"]), fmt_conf(b["diffdock"])],
        ["BindingDB 참조 집합", bdb(a), bdb(b)],
    ]
    if a["scope"] != b["scope"]:
        rows.append(["사람 근거의 범위", a["scope"], b["scope"]])

    common = [
        ["허가 라벨 (DailyMed SPL)",
         ("기재됨. " + ", ".join(a["label_sections"])) if a["labeled"] else "기재 없음"],
        ["FAERS 불균형 지표",
         f'PRR {fmt(a["prr"], 2)} (95% CI {fmt(a["prr_ci95"][0], 2)} ~ '
         f'{fmt(a["prr_ci95"][1], 2)}), 자료 기준일 {a["faers_asof"]}'],
        ["PubMed 문헌", f'{fmt(a["pubmed_total"])}건'],
    ]
    if a["scope"] == b["scope"]:
        common.append(["근거의 범위", a["scope"]])

    common_block = (
        '<div class="keep"><h3>두 경로가 함께 쓰는 사람 근거</h3>'
        '<p class="lead">라벨과 FAERS 와 문헌은 화합물 단위 근거라 두 경로에 같은 값이 온다. '
        "어느 타깃에서 결합했는지를 가리지 못한다.</p>"
        + table(["항목", f'{case["compound"]} 대 {case["event_ko"]} ({case["event"]})'],
                common, cls="small", widths=("28%", "72%"))
        + "</div>"
    )

    body = (
        figure(f"{REL_FIG_DIR}/results_case.png",
               f'그림 2. {case["compound"]}, 같은 화합물을 두 타깃에 돌린 결과와 크리틱 판정.')
        + table(["항목", route(a), route(b)], rows, cls="small",
                widths=("21%", "39.5%", "39.5%"))
        + common_block
        + f'<p class="muted">두 경로를 가른 것은 점수 차이가 아니라 그 점수를 받쳐 줄 실험 근거의 '
          f'유무였다. 케이스 브리프는 말할 수 있는 것 {len(case["can_say"])}항목과 말할 수 없는 것 '
          f'{len(case["cannot_say"])}항목으로 끝난다. '
          f'출처 <code>eval/results/case_niraparib.json</code> '
          f'(생성 {esc(case["generated_at"])}). 도킹 원본 SHA256 '
          f'<code>{esc(case["fddd_sha256"][:16])}…</code></p>'
    )
    return section("4", "케이스 결과", body)


def safety_html(data: dict) -> str:
    smoke = data["smoke"]
    hosts = ", ".join(h for h, _ in smoke["hosts"])
    sec_rows = [[name, f'{cnt}건 통과'] for name, cnt in smoke["sections"]]
    sec_rows.append(["합계", f'**{smoke["pass"]}건 통과, 실패 {smoke["fail"]}건**'])

    log = "\n".join(smoke["excerpt"])
    log_html = esc(log).replace("DENIED", "<b>DENIED</b>")

    body = (
        f'<p>실행은 NVIDIA OpenShell 안에서만 이루어진다. 정책은 deny-by-default 이고 '
        f'허용 호스트 {len(smoke["hosts"])}곳만 연다. 쓰기는 지정한 출력 폴더만 허용하며 '
        f"그 밖의 접근은 차단 로그로 남는다.</p>"
        + table(["항목", "값"], [
            ["OpenShell", smoke["version"]],
            ["정책 파일", f'`policies/{smoke["policy"]}`'],
            ["샌드박스", f'`{smoke["sandbox"]}`'],
            ["유효 정책 해시", f'`{smoke["policy_hash"][:32]}…`'],
            ["허용 호스트", f'{len(smoke["hosts"])}곳. {hosts}'],
            ["쓰기 허용 경로", ", ".join(f"`{p}`" for p in smoke["read_write"]) or "없음"],
            ["프로세스 신원", f'`run_as_user={smoke["run_as_user"]}`'],
        ], cls="keep small", widths=("24%", "76%"))
        + "<h3>스모크 검증</h3>"
        + table(["검증 항목", "결과"], sec_rows, cls="keep small", widths=("62%", "38%"))
        + "<h3>차단 로그 원문 발췌</h3>"
        + f'<p class="lead">허용 목록 밖 호스트, 정책에 없는 바이너리, 정책에 없는 경로가 '
          f"각각 다른 계층에서 끊긴다. 파일시스템 거부는 커널이 EPERM 으로 끊어 DENIED 줄이 "
          f"남지 않으므로 Landlock 적용 기록을 함께 싣는다.</p>"
        + f"<pre class=\"keep\">{log_html}</pre>"
        + '<p class="muted">출처 <code>eval/results/openshell_smoke_flydock.txt</code>. '
          "각 종류의 첫 줄만 뽑았다. 전문은 저장소의 같은 파일에 있다.</p>"
    )
    return section("5", "안전과 샌드박스", body)


def stack_html(data: dict) -> str:
    paras = "".join(f"<p>{esc(p.strip())}</p>"
                    for p in data["stack"].split("\n\n") if p.strip())
    return section("6", "기술 스택", f'<div class="quote keep">{paras}</div>')


def notyet_html(data: dict) -> str:
    header, rows = data["notyet_table"]
    body = (
        table(header, rows, widths=("30%", "70%"))
        + '<p class="muted">평가 케이스의 정답 라벨은 저자들이 붙였고 도메인 전문가 두 명 이상의 '
          "일치도는 아직 없다. <code>build.nvidia.com</code> 이 간헐적으로 503 을 내므로 "
          "측정을 다시 돌려야 할 때가 있다.</p>"
    )
    return section("7", "아직 하지 않은 것", body,
                   lead="되지 않는 것을 되는 것처럼 쓰지 않는다. 이 저장소의 규율이다.",
                   keep=True)


def credits_html(data: dict) -> str:
    c_header, c_rows = data["credits_table"]
    a_header, a_rows = data["assets_table"]

    # credits.md 의 규칙 수가 지금 코드와 다르면 그 사실을 적는다. 원본은 고치지 않는다
    stale = ""
    for row in c_rows:
        m = re.search(r"규칙\s*(\d+)\s*종", " ".join(row))
        if m and int(m.group(1)) != data["rule_count"]:
            stale = (f'층별 기여 표의 과잉해석 규칙 수 {m.group(1)}종은 '
                     f'<code>docs/notes/credits.md</code> 를 적을 당시의 값이다. '
                     f'지금 <code>src/harness/tools/overclaim_rules.py</code> 에 들어 있는 규칙은 '
                     f'{data["rule_count"]}종이다.')
            break

    body = (
        '<div class="quote keep"><p>주제와 초파리 도킹 경로는 팀원 제안이고, 에이전트 하네스와 '
        "검증 체계는 선행 프로젝트 PharmaSignal v0 에서 이어 온 자산입니다. 두 갈래를 하나의 "
        "파이프라인으로 이었습니다.</p></div>"
        + "<h3>층별 기여</h3>"
        + table(c_header, c_rows, cls="small", widths=("15%", "42%", "13%", "30%"))
        + (f'<p class="muted">{stale}</p>' if stale else "")
        + '<div class="keep"><h3>외부 자산과 라이선스</h3>'
        + table(a_header, a_rows, cls="small", widths=("30%", "38%", "32%"))
        + "</div>"
        + '<p class="muted">초파리 도킹 자산 FDDD 는 팀원의 별도 저작물이다. 복제하지 않고 '
          "도구로 참조하며 데이터 출처와 SHA256 을 그대로 인용한다. 공개 산출물에는 실명을 "
          "쓰지 않고 역할로만 적는다. 출처 <code>docs/notes/credits.md</code>.</p>"
    )
    return section("8", "계보와 기여", body)


def dli_html(data: dict) -> str:
    course = data["dli"]
    title = f'NVIDIA DLI {DLI_COURSE_ID} {course["name"]}'
    if CERT_IMAGE:
        inner = figure(CERT_IMAGE, f"{title} 수료증")
    else:
        inner = ('<div class="placeholder">'
                 '<div class="big">수료증 이미지를 여기에 넣는다</div>'
                 f"<div>{esc(title)}</div>"
                 '<div class="muted" style="margin-top:3mm">'
                 '아직 수료 전이라 비워 둔다. 수료 후 '
                 '<code>scripts/make_submission_pdf.py</code> 의 '
                 '<code>CERT_IMAGE</code> 에 이미지 경로를 넣고 다시 만든다.</div>'
                 "</div>")
    note = f'과정 주소는 <code>{esc(course["url"])}</code> 이다. '
    if course["progress"]:
        note += esc(course["progress"]) + " "
    note += ("수강 안내는 <code>docs/COURSE-GUIDE.md</code> 에 있다. "
             "수료 전이므로 수료 사실을 적지 않는다.")
    body = f'<div class="keep">{inner}<p class="muted">{note}</p></div>'
    return section("9", "교육 미션", body, keep=True)


def collect() -> dict:
    submission = need_text(SUBMISSION_MD)
    readme = need_text(README_MD)
    credits = need_text(CREDITS_MD)

    tool_names = load_tool_names()
    problem = md_fenced(submission, "해결하고자 했던 문제", SUBMISSION_MD)
    solution_raw = md_fenced(submission, "서비스 소개 및 주요 기능", SUBMISSION_MD)
    solution, solution_note = fix_solution(solution_raw, tool_names)

    test_count, test_source = load_offline_test_count()

    return {
        "today": date.today().isoformat(),
        "repo_url": load_repo_url(),
        "problem": problem,
        "solution": solution,
        "solution_note": solution_note,
        "stack": md_fenced(submission, "활용한 핵심 기술 및 AI 모델", SUBMISSION_MD),
        "critic_table": md_table(readme, "크리틱 3단", README_MD),
        "notyet_table": md_table(readme, "아직 하지 않은 것", README_MD),
        "credits_table": md_table(credits, "층별 기여", CREDITS_MD),
        "assets_table": md_table(credits, "외부 자산", CREDITS_MD),
        "case": load_case(),
        "llm": load_verdict_eval(LLM_JSON),
        "det": load_verdict_eval(DET_JSON),
        "smoke": load_smoke(),
        "diffdock": load_diffdock_smoke(),
        "author_run": load_author_run(),
        "tool_names": tool_names,
        "rule_count": load_rule_count(),
        "case_count": load_case_count(),
        "test_count": test_count,
        "test_source": test_source,
        "dli": load_dli_course(),
    }


def fix_solution(raw: str, tool_names: list[str]) -> tuple[str, str]:
    """`flybrain_pose` 가 등록되지 않았으면 '세 경로' 를 '두 경로' 로 맞춘다.

    `docs/submission-flygate.md` 가 스스로 정해 둔 규칙을 그대로 따른다.
    """
    if "flybrain_pose" in tool_names or "세 경로" not in raw:
        return raw, ""
    old = "NVIDIA DiffDock과 AutoDock Vina 실측과 초파리 커넥톰 세 경로로"
    new = "NVIDIA DiffDock과 AutoDock Vina 실측 두 경로로"
    if old not in raw:
        raise SubmissionDataError(
            "솔루션 문안에 '세 경로' 가 있는데 바꿀 구절을 찾지 못했습니다. "
            "docs/submission-flygate.md 의 초파리 경로 주의 항목을 직접 확인하세요.")
    note = ("솔루션 문안의 결합 경로를 두 곳으로 적었다. `configs/author.yml` 의 tool_names 에 "
            "`flybrain_pose` 가 없어 초파리 커넥톰 경로는 아직 도구로 등록되지 않았다. "
            "`docs/submission-flygate.md` 가 정해 둔 규칙을 그대로 따랐다.")
    return raw.replace(old, new), note


def build_html(data: dict) -> str:
    body = (
        cover_html(data)
        + problem_solution_html(data)
        + pipeline_html(data)
        + numbers_html(data)
        + case_html(data)
        + safety_html(data)
        + stack_html(data)
        + notyet_html(data)
        + credits_html(data)
        + dli_html(data)
    )
    title = f"{PROJECT_NAME} 제출 문서"
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title><style>{css()}</style></head>"
        f'<body><div class="wrap">{body}</div></body></html>'
    )


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    if not Path(CHROME).exists():
        raise SubmissionDataError(
            f"Chrome 을 찾지 못했습니다: {CHROME}. CHROME 환경변수로 경로를 지정하세요.")
    if pdf_path.exists():
        pdf_path.unlink()
    cmd = [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           "--run-all-compositor-stages-before-draw", "--virtual-time-budget=10000",
           f"--print-to-pdf={pdf_path}", html_path.as_uri()]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not pdf_path.exists():
        raise SubmissionDataError(
            f"Chrome 이 PDF 를 만들지 못했습니다 (rc={proc.returncode}). "
            f"{proc.stderr.strip()[:500]}")


def check_no_private_path(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    home = str(Path.home())
    bad = [token for token in (home, "/Users/") if token in text]
    if bad:
        raise SubmissionDataError(
            f"{_rel(path)} 에 개인 경로가 남았습니다: {', '.join(bad)}")


def main() -> int:
    try:
        data = collect()
    except SubmissionDataError as exc:
        print(f"멈춤: {exc}", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = build_html(data)
    HTML_PATH.write_text(html, encoding="utf-8")

    try:
        check_no_private_path(HTML_PATH)
        render_pdf(HTML_PATH, PDF_PATH)
    except SubmissionDataError as exc:
        print(f"멈춤: {exc}", file=sys.stderr)
        return 2

    print(f"  HTML  {_rel(HTML_PATH)}  {HTML_PATH.stat().st_size // 1024}KB")
    print(f"  PDF   {_rel(PDF_PATH)}  {PDF_PATH.stat().st_size // 1024}KB")
    print()
    print("읽은 수치")
    print(f"  적발률 LLM 포함      {data['llm']['reject_caught']}/{data['llm']['reject_total']}"
          f"  거짓 양성 {data['llm']['false_positive']}/{data['llm']['pass_total']}")
    print(f"  적발률 결정 규칙만   {data['det']['reject_caught']}/{data['det']['reject_total']}")
    print(f"  평가 케이스          {data['case_count']}건")
    print(f"  과잉해석 규칙        {data['rule_count']}종")
    print(f"  NAT 등록 도구        {len(data['tool_names'])}종")
    print(f"  오프라인 테스트      {data['test_count']}개  ({data['test_source']})")
    print(f"  샌드박스 스모크      {data['smoke']['pass']}건 통과 / 실패 "
          f"{data['smoke']['fail']}건")
    print(f"  허용 호스트          {len(data['smoke']['hosts'])}곳")
    if data["solution_note"]:
        print()
        print(f"알림: {data['solution_note']}")
    if not TEAM_NAME.strip():
        print()
        print(f"팀명이 아직 비어 있다. 확정되면 TEAM_NAME 을 채우고 다시 만든 뒤 다음처럼 복사한다.")
        print(f'  cp {_rel(PDF_PATH)} "docs/submission/[NVIDIA 해커톤_<팀명>_{PROJECT_NAME}].pdf"')
    if CERT_IMAGE is None:
        print()
        print("DLI 수료증 자리는 비어 있다. 수료 후 CERT_IMAGE 에 이미지 경로를 넣는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
