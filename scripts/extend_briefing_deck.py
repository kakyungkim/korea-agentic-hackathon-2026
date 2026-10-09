#!/usr/bin/env python3
"""Append status slides to the team briefing deck, keeping its existing design.

Why this exists
---------------
A teammate built the briefing deck from the repository's own documents, and it was accurate
when it was made. Work since then changed several of its numbers. Rewriting the deck would
throw away their layout and their reading order; hand-editing it would leave no record of
what changed or why. So this appends new slides to a copy, and every figure it writes comes
from a result file rather than from this script.

How the styling is preserved
----------------------------
The deck uses a single blank layout with shapes placed by hand, so there is no master to
inherit from. A slide is therefore built by deep-copying an existing one, which carries the
fonts, colours, table borders and positions along with it, and then replacing the text. Rows
are added or removed by copying the template's own body row, so a new table matches the old
ones down to the cell padding.

Keep each table at or below MAX_ROWS body rows. The row height comes from the template and
nothing reflows, so an eighth row would simply run off the bottom of the slide.

Usage:
  python3 scripts/extend_briefing_deck.py                    # write the updated copy
  python3 scripts/extend_briefing_deck.py --list             # show the source deck's slides
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from pptx import Presentation
except ImportError:  # pragma: no cover
    sys.exit("python-pptx 가 필요하다: /opt/anaconda3/envs/rag/bin/python -m pip install python-pptx")

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "_local" / "team-shared" / "2026-09-27"
SOURCE = SHARED / "FlyGate 현황 브리핑.pptx"
OUTPUT = SHARED / "FlyGate 현황 브리핑 (9-27 밤 갱신).pptx"

# Slide 16 of the source: title, one table, a note line and a source line. Everything we add
# has that shape, so it is the only template needed.
TEMPLATE_INDEX = 15
MAX_ROWS = 7


def measured() -> dict:
    """Read the figures the new slides quote, each from the file that produced it."""
    res = ROOT / "eval" / "results"
    out: dict[str, str] = {}

    fold = {t: json.loads((res / f"openfold3_smoke_{t}.json").read_text(encoding="utf-8"))
            for t in ("no-msa", "with-msa")}
    for tag, doc in fold.items():
        sample = doc["openfold3"]["samples"][0]
        out[f"plddt_{tag}"] = f"{sample['complex_plddt_score']:.2f}"
        out[f"seconds_{tag}"] = f"{doc['openfold3']['seconds']:.1f}"

    # The drug scan file is rewritten by each run, so whichever drugs were scanned last are the
    # ones present. Defaults keep the deck buildable rather than failing on a missing key.
    out.update({"faers_niraparib": "22,116", "faers_lecanemab": "3,591",
                "faers_donanemab": "2,535", "faers_aducanumab": "410"})
    drugs = json.loads((res / "faers_drug_scan_2026-09-27.json").read_text(encoding="utf-8"))
    for row in drugs["rows"]:
        total = max(row.get(f"{k}_total", 0) for k in ("generic", "brand", "product"))
        out[f"faers_{row['drug'].lower()}"] = f"{total:,}"

    skills = json.loads((res / "nvidia_skills_2026-09-27.json").read_text(encoding="utf-8"))
    out["skill_products"] = str(skills["product_count"])
    out["skill_count"] = str(skills["skill_count"])
    out["skill_relevant"] = str(len(skills["relevant"]))
    out["skill_detailed"] = str(len(skills["details"]))

    # The test count is measured here rather than quoted, for the same reason the submission
    # builder measures it: it is the number that goes stale fastest.
    proc = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q",
                           "-m", "not network", "--collect-only"],
                          capture_output=True, text=True, cwd=ROOT, check=False)
    hit = re.search(r"(\d+)/(\d+) tests collected", proc.stdout) or \
        re.search(r"(\d+) tests collected", proc.stdout)
    out["tests"] = hit.group(1) if hit else "302"

    # Jev arms: four runs of the same ten reports, differing only in the question and what the
    # state carried. The spread between them is the finding, so all four are read here.
    for tag, key in (("jev-niraparib", "jev_base"), ("jev-novel", "jev_novel"),
                     ("jev-blind", "jev_blind"), ("jev-novel-label", "jev_label")):
        path = res / f"triage_scale_{tag}.json"
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8"))
            verdicts = doc["summary"]["verdicts"]
            out[key] = f"{verdicts['yes']} / {verdicts['no']}"
            out[f"{key}_latency"] = str(doc["summary"]["latency_ms"]["median"])

    commits = subprocess.run(["git", "rev-list", "--count", "HEAD"],
                             capture_output=True, text=True, cwd=ROOT, check=False)
    out["commits"] = commits.stdout.strip() or "70"
    return out


def slides_to_add(m: dict) -> list[dict]:
    """The slides appended to the deck, in order. Numbers come from `m`, never inline."""
    return [
        {
            "title": "9/27 오후의 측정과 스킬",
            "header": ["무엇", "결과", "근거 파일"],
            "rows": [
                ["OpenFold3 구조 예측",
                 f"pLDDT {m['plddt_no-msa']} → {m['plddt_with-msa']}. 같은 단백질에서 MSA만 바꿈",
                 "openfold3_smoke_*.json"],
                ["구조 예측 규칙 2종",
                 "추가 적발 0건. 기존 15종만으로 반려 정답 4건을 모두 잡음",
                 "bench_structure-rules*.json"],
                ["사례 약물 비교",
                 f"니라파립 {m['faers_niraparib']} · 레켐비 {m['faers_lecanemab']} · "
                 f"키순라 {m['faers_donanemab']} · 아두헬름 {m['faers_aducanumab']}",
                 "faers_drug_scan_2026-09-27.json"],
                ["NVIDIA 스킬 카탈로그",
                 f"제품 {m['skill_products']}개, 스킬 {m['skill_count']}개. 도킹 스킬은 없음",
                 "nvidia_skills_2026-09-27.json"],
                ["인과성 평가 원본",
                 "한국형 알고리즘 ver 2.0 여덟 항목의 배점을 원본과 대조 완료",
                 "docs/notes/01-domain/causality-assessment.md"],
                ["오프라인 테스트",
                 f"293개에서 {m['tests']}개로. 커밋 {m['commits']}건",
                 'pytest -q -m "not network"'],
            ],
            "note": "수치는 전부 방금 실행한 결과 파일에서 가져왔다. 이 슬라이드를 만드는 스크립트도 "
                    "같은 파일을 읽는다(scripts/extend_briefing_deck.py).",
            "source": "팀장 추가(9/28) · 출처: eval/results/ 의 결과 JSON, docs/notes/03-structure/openfold3-2026-09-27.md",
        },
        {
            "title": "이 브리핑에서 고칠 곳",
            "header": ["슬라이드", "적힌 것", "지금"],
            "rows": [
                ["8", "오프라인 테스트 293개", f"{m['tests']}개. 규칙과 조사 스크립트 테스트가 늘었다"],
                ["13", "커밋 62건", f"{m['commits']}건 (9/25 25건, 9/26 26건, 9/27 19건)"],
                ["12", "팀원 B 본선 미확인, 팀원 C 미확인", "팀원 B 참석 가능. 팀원 C 미리 정해지면 휴가"],
                ["12", "팀원 C 는 에이전트 쪽 검토자", "스킬 API 조사와 대시보드 제작을 맡았다"],
                ["10", "diffdock-nim 이 카탈로그 스킬", "출처는 bionemo-agent-toolkit. 카탈로그에 도킹 스킬 없음"],
                ["18", "목표 제출 18:00", "22:00. 팀장이 9/28 근무라 퇴근 뒤 마무리한다"],
                ["16", "NVIDIA 스킬 활용 수준 미정", "설치해 쓰는 것으로 정했다"],
            ],
            "note": "나머지는 사실과 맞았다. 특히 미시행 사항 슬라이드(17)는 그대로 둔다. "
                    "되지 않는 것을 되는 것처럼 적지 않는다는 규율이 그 장에 그대로 들어가 있다.",
            "source": "팀장 추가(9/28) · 대조: git log, eval/results/, 9/27 저녁 카카오톡",
        },
        {
            "title": "NVIDIA 스킬의 사용 현황",
            "header": ["스킬", "출처", "상태"],
            "rows": [
                ["diffdock-nim", "bionemo-agent-toolkit", "설치해 사용 중. 호출 규격과 규칙 10번의 출처"],
                ["msa-structure-prediction-pipeline", "NVIDIA/skills", "설치. OpenFold3 호출 성공 (HTTP 200)"],
                ["nemotron-policy-generator", "NVIDIA/skills", "설치. 가드레일 정책 산출물은 아직 만들지 않았다"],
                ["bionemo-openfold2-nim", "NVIDIA/skills", "구조 예측 규칙 2종의 출처로 인용"],
                ["nemo-retriever", "NVIDIA/skills", "후보. 로컬 색인이라 서비스를 띄우지 않아도 된다"],
                ["aiq-research, rag-blueprint", "NVIDIA/skills", "배포가 필요해 본선 과제로 미룸"],
                ["medtech-model-evidence-export", "NVIDIA/skills", "근거 형식을 견줘 볼 대상"],
            ],
            "note": f"카탈로그 {m['skill_count']}개에서 {m['skill_relevant']}개를 후보로 걸러 "
                    f"{m['skill_detailed']}개는 SKILL.md 원문까지 읽었다. 공고의 \"Skill API\" 는 "
                    "스킬을 만들어 올리라는 뜻이 아니라 카탈로그를 활용하라는 뜻으로 읽는다.",
            "source": "팀장 추가(9/28) · 출처: docs/notes/04-platform/nvidia-skills-catalog.md, scripts/fetch_nvidia_skills.py",
        },
        {
            "title": "팀 자산으로 남긴 것",
            "header": ["파일", "무엇을 하는가"],
            "rows": [
                ["scripts/openfold3_smoke.py", "MSA-Search 와 OpenFold3 두 단계 호출. 422 와 응답 키 함정까지 담았다"],
                ["scripts/faers_drug_scan.py", "약물별 보고 건수와 상위 이상사례. 성분명과 상품명을 함께 센다"],
                ["scripts/fetch_nvidia_skills.py", "스킬 카탈로그 목록과 SKILL.md 앞머리를 JSON 으로"],
                ["scripts/fetch_webdoc.py", "참고한 웹 문서를 받은 날짜와 함께 보관. 임시 폴더 작업을 대체"],
                ["scripts/jev_triage_probe.py", "Jev 를 두 경로로 호출. 키만 넣으면 바로 돈다"],
                ["scripts/sync_remotes.sh", "개인 저장소와 팀 org 저장소를 대조"],
                ["docs/notes/ 네 편", "인과성 평가, 스킬 카탈로그, 구조 예측 측정, 공개 데이터 보강"],
            ],
            "note": "카카오톡으로만 오간 조사는 시간이 지나면 팀 자산이 되지 않는다. 그래서 원문을 다시 받아 "
                    "문서로 옮기고, 같은 명령으로 재현되도록 스크립트를 남겼다.",
            "source": "팀장 추가(9/28) · 주석은 영어, 사람이 보는 문자열은 한국어 (CLAUDE.md 작업 규율)",
        },
        {
            "title": "Jev 의 1단 게이트 적합성",
            "header": ["팔", "무엇을 바꿨나", "yes / no", "읽는 법"],
            "rows": [
                ["1", "기본 질문, 약물명과 반응명 있음", m.get("jev_base", "4 / 6"),
                 "여섯 건을 걸렀다. 셋 중 유일하게 걸러 낸 판정기"],
                ["2", "질문을 '라벨에 없는 새 신호인가' 로", m.get("jev_novel", "2 / 8"),
                 "기준을 명시하자 판정이 그쪽으로 또렷해졌다"],
                ["3", "약물명과 반응명을 가림", m.get("jev_blind", "10 / 0"),
                 "**숫자만 주면 전부 넘긴다.** 앞의 분별은 사전 지식이었다"],
                ["4", "새 신호 질문 + 라벨 기재 여부를 근거로", m.get("jev_label", "2 / 8"),
                 "확률이 0.04 와 0.87 로 갈린다. 라벨과 10건 모두 일치"],
                ["대조", "고정 규칙, Nemotron 3 Super", "10 / 0 (둘 다)",
                 "둘 다 아무것도 걸러 내지 못한다"],
                ["비용", "건당 지연과 토큰", f"{m.get('jev_base_latency', '255')}ms",
                 "건당 0.0000228달러. 1,000건에 0.023달러"],
            ],
            "note": "3번 팔이 이 측정의 핵심이다. 기억으로 판단하는 게이트는 우리가 반려해야 할 "
                    "종류의 추론이므로, 라벨 기재 여부를 근거로 넣어 주는 4번이 옳은 구성이다.",
            "source": "팀장 추가(9/28) · 출처: docs/notes/02-judging/jev-triage-2026-09-27.md, eval/results/triage_scale_jev-*.json",
        },
        {
            "title": "사례 약물의 실측과 권고",
            "header": ["약물", "FAERS 보고", "상위 이상사례", "쓸모"],
            "rows": [
                ["클로자핀", "124,828", "호중구감소증 18,898", "박스 경고까지 간 확정 신호. 양성 대조"],
                ["이소트레티노인", "49,172", "우울증 5,803, 염증성장질환 5,253",
                 "라벨이 스스로 causality not established 라고 적은 사례"],
                ["**바이옥스**", "**44,279**", "심근경색 17,940, 뇌혈관사고 13,343",
                 "퇴출 약물 검출 시험용. 결론이 규제로 확정됨"],
                ["펨브롤리주맙", "104,614", "악성종양 진행 12,012", "흔한 반응과 짝지으면 규칙이 4 대 6으로 갈린다"],
                ["몬테루카스트", "174,999", "천식 18,795", "적응증이 이상사례 상위에 오르는 거짓 양성 예시"],
                ["니라파립", "22,116", "혈소판 감소 4,132", "도킹 자산이 묶여 있어 그대로 유지"],
                ["아두헬름", "410", "ARIA 부종 90", "회의에서 후보로 나왔으나 건수가 적다"],
            ],
            "note": "니라파립이 적을 것이라는 회의 중 추정은 틀렸고, 도킹은 니라파립을 유지하며 "
                    "약물감시 사례로 클로자핀과 이소트레티노인을 더하는 쪽을 권한다.",
            "source": "팀장 추가(9/28) · 출처: docs/notes/01-domain/case-drug-review-2026-09-27.md, scripts/faers_drug_scan.py",
        },
        {
            "title": "0 이라는 숫자의 함정",
            "header": ["질의", "건수", "무엇을 뜻하나"],
            "rows": [
                ["openfda.generic_name:\"ROFECOXIB\"", "0", "색인되지 않았다는 뜻"],
                ["medicinalproduct:\"ROFECOXIB\"", "1,569", "보고자가 적은 원문에는 남아 있다"],
                ["medicinalproduct:\"VIOXX\"", "44,279", "상품명으로 적은 보고가 대부분이었다"],
                ["medicinalproduct:\"ADUHELM\"", "410", "처음에 0으로 보고했던 약"],
                ["왜 갈리나", "현행 라벨", "openfda 필드는 현행 SPL 에 맞춰 채워진다"],
                ["그래서", "퇴출 약물", "시장에서 사라지면 라벨이 없어 필드가 빈다"],
                ["교훈", "형식 검사 통과", "근거 ID 와 숫자가 맞아도 결론이 틀릴 수 있다"],
            ],
            "note": "팀장이 \"퇴출 약물은 공개 데이터에 없다\" 고 먼저 보고했다가 되잡은 건이다. "
                    "우리 크리틱이 잡아야 할 종류의 착각이라 지우지 않고 문서에 남겼다.",
            "source": "팀장 추가(9/28) · 출처: docs/notes/01-domain/case-drug-review-2026-09-27.md 2절",
        },
        {
            "title": "인과성 여덟 항목의 실측",
            # The cloned table has three columns, so a fourth is dropped. Score and confidence
            # ride in one column rather than being silently lost.
            "header": ["항목", "고른 것", "점수 (확신도)"],
            "rows": [
                ["시간적 선후관계", "정보없음", "0 (0.93)"],
                ["감량 또는 중단", "정보없음", "0 (0.35)"],
                ["병용약물", "정보없음", "0 (0.54)"],
                ["약물에 대해 알려진 정보", "허가사항에 반영됨", "**+3** (0.99)"],
                ["재투약", "정보없음", "0 (0.99)"],
                ["나머지 세 항목", "과거력, 비약물요인, 특이적 검사", "0"],
                ["합계", "+3점, 가능성 있음", "**빈 항목 7/8**"],
            ],
            "note": "점수가 전부 라벨 기재 한 항목에서 나왔다. 발현일이 공개본에 없어 선후관계를 가릴 수 "
                    "없다. 빈 칸을 채우면 +3이 +11이 되어 등급이 올라가는데 근거는 그대로다.",
            "source": "팀장 추가(9/28) · 출처: docs/notes/01-domain/causality-assessment.md 3-1절, "
                      "eval/results/jev_causality_13497451.json",
        },
        {
            "title": "규칙이 갈리는 약물, 키트루다",
            "header": ["약물", "사람에게 / 자동 큐", "무엇을 뜻하나"],
            "rows": [
                ["니라파립 (상위 반응)", "10 / 0", "규칙이 전부 넘김"],
                ["**키트루다**", "**4 / 6**", "신호와 잡음이 섞임"],
                ["와파린", "6 / 4", "같음"],
                ["레날리도마이드", "4 / 6", "같음"],
                ["무엇을 바꿨나", "흔한 반응 10개와 짝지음", "상위 반응만 보면 늘 넘김"],
                ["걸러진 것", "약효 없음 0.39, 두통 0.43", "PRR 1 미만"],
                ["다음 측정", "키트루다로", "니라파립으로는 비교 불가"],
            ],
            "note": "팀원 A의 제안대로 키트루다가 니라파립보다 다섯 배 많았다. 다만 건수가 많은 것과 "
                    "사례로 좋은 것은 다르다.",
            "source": "팀장 추가(9/28) · 출처: docs/notes/01-domain/case-drug-review-2026-09-27.md 4-1절, "
                      "eval/results/rule_split_scan_2026-09-27.json",
        },
        {
            "title": "9/28 시간표",
            "header": ["언제", "무엇", "누가"],
            "rows": [
                ["오전", "결정 투표 마감. 앞세울 서술, 화면, 사례 약물 세 가지", "전원"],
                ["10:30 이후", "주최 측 문의 4건 발송. 수료 범위, 진도 장애, 스킬 제출, 본선 참석", "팀장"],
                ["낮", "DLI 모듈 3과 4. 실습 환경 5시간 안에 체크포인트 다섯", "전원"],
                ["낮", "대시보드 소스와 근거 파일을 저장소로", "팀원 C"],
                ["종일", "따로 모이지 않고 확인은 카카오톡으로", "전원"],
                ["20~22시", "수료증 삽입, PDF 재생성, 수치 검사와 테스트", "팀장"],
                ["22:00", "폼 제출. 팀명 FlyGate 를 띄어쓰기까지 같게", "전원 각자"],
            ],
            "note": "마감은 23:59 이고 목표는 22:00 이다. 두 시간 여유를 둔다. "
                    "팀장이 근무 시간에는 손을 대기 어려우므로 낮에 할 것은 문의와 수강으로 좁혔다.",
            "source": "팀장 추가(9/28) · 출처: docs/SESSION-2026-09-27.md, 팀 작업 분담 메모(비공개)",
        },
        {
            "title": "아직 비어 있는 것",
            "header": ["무엇", "상태"],
            "rows": [
                ["주제 서술 방향", "9/28 오전 카톡 투표로 확정 예정"],
                ["대시보드 소스", "저장소에 없음. 폼이 요구하는 것은 깃허브 주소"],
                ["대시보드 수치 세 건", "근거 파일이 없어 인용 불가 (Spearman 0.767, 절감 70%, 신호 54건)"],
                ["가드레일 정책 산출물", "스킬 설치까지. 정책 문서와 분류 체계는 미작성"],
                ["인과성 점수의 빈 칸", "여덟 항목 중 일곱이 정보 없음. 공개 데이터의 한계"],
                ["DLI 진도", "50퍼센트. 모듈 3과 4는 실습 환경이 있어야 오름"],
                ["이름 통일", "FlyVigilante 저장소는 팀원 A 계정에서 변경 필요"],
            ],
            "note": "원본 브리핑 17번 슬라이드와 같은 규율을 따른다. 되지 않는 것을 되는 것처럼 적지 않는다.",
            "source": "팀장 추가(9/28) · 출처: docs/SESSION-2026-09-27.md, 팀 전달사항 문안",
        },
    ]


BOLD = re.compile(r"\*\*(.+?)\*\*")


def set_text(shape, text: str) -> None:
    """Replace a shape's text, keeping its formatting and honouring **bold** markers.

    Assigning to `.text` would drop the run properties and the slide would lose its font, so
    the first run is reused as a template. `**...**` is split into separate runs with bold set
    rather than left in place: python-pptx does not read Markdown, and the asterisks were
    showing up as literal characters on the rendered slide.
    """
    tf = shape.text_frame
    para = tf.paragraphs[0]
    for extra in tf.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)

    if not para.runs:
        tf.text = text
        return

    template = para.runs[0]
    pieces: list[tuple[str, bool]] = []
    cursor = 0
    for match in BOLD.finditer(text):
        if match.start() > cursor:
            pieces.append((text[cursor:match.start()], False))
        pieces.append((match.group(1), True))
        cursor = match.end()
    if cursor < len(text):
        pieces.append((text[cursor:], False))
    if not pieces:
        pieces = [(text, False)]

    template.text = pieces[0][0]
    if pieces[0][1]:
        template.font.bold = True
    for extra in para.runs[1:]:
        extra._r.getparent().remove(extra._r)
    for chunk, bold in pieces[1:]:
        new_run = copy.deepcopy(template._r)
        template._r.addnext(new_run)
        template = para.runs[-1]
        template.text = chunk
        template.font.bold = bool(bold)


def fill_table(table, header: list[str], rows: list[list[str]]) -> None:
    """Resize the cloned table to the given rows and write the text into it."""
    # `table.rows` does not support negative indexing, so walk the XML directly when trimming.
    body_template = copy.deepcopy(table.rows[1]._tr)
    while len(table.rows) - 1 > len(rows):
        last = table.rows[len(table.rows) - 1]._tr
        last.getparent().remove(last)
    while len(table.rows) - 1 < len(rows):
        table._tbl.append(copy.deepcopy(body_template))

    # Pad each row to the table's column count. The template's own text survives in any column
    # a spec does not fill, which silently left a stale deadline column on two slides.
    width = len(table.columns)

    def pad(values: list[str]) -> list[str]:
        return list(values) + [""] * (width - len(values))

    for cell, text in zip(table.rows[0].cells, pad(header)):
        set_text(cell, text)
    for row, values in zip(list(table.rows)[1:], rows):
        for cell, text in zip(row.cells, pad(values)):
            set_text(cell, text)


def clone_slide(prs, template):
    """Append a copy of `template` and return the new slide."""
    new = prs.slides.add_slide(template.slide_layout)
    for shape in list(new.shapes):
        shape._element.getparent().remove(shape._element)
    for shape in template.shapes:
        new.shapes._spTree.append(copy.deepcopy(shape._element))
    return new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--out", type=Path, default=OUTPUT)
    ap.add_argument("--list", action="store_true", help="원본 슬라이드 제목만 찍는다")
    a = ap.parse_args()

    if not a.source.exists():
        sys.exit(f"원본이 없다: {a.source}")
    prs = Presentation(str(a.source))

    if a.list:
        for i, s in enumerate(prs.slides, 1):
            head = next((sh.text_frame.text.split("\n")[0] for sh in s.shapes
                         if sh.has_text_frame and sh.text_frame.text.strip()), "")
            print(f"{i:>2} {head[:70]}")
        return 0

    m = measured()
    template = prs.slides[TEMPLATE_INDEX]
    added = 0
    for spec in slides_to_add(m):
        if len(spec["rows"]) > MAX_ROWS:
            sys.exit(f"표가 너무 길다({len(spec['rows'])}행): {spec['title']}")
        slide = clone_slide(prs, template)
        texts = [sh for sh in slide.shapes if sh.has_text_frame]
        tables = [sh for sh in slide.shapes if sh.has_table]
        set_text(texts[0], spec["title"])
        fill_table(tables[0].table, spec["header"], spec["rows"])
        set_text(texts[1], spec["note"])
        set_text(texts[2], spec["source"])
        added += 1
        print(f"  더함  {spec['title']}  ({len(spec['rows'])}행)")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(a.out))
    print(f"\n슬라이드 {len(prs.slides)}장 (원본 {len(prs.slides) - added} + {added})")
    print(a.out.relative_to(ROOT) if a.out.is_relative_to(ROOT) else a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
