"""데모 케이스 실행기: 세 도구(FAERS, DailyMed, PubMed)를 한 조합에 대해 돌려 한 dict로 묶는다.

LLM은 부르지 않는다. 결과는 ``eval/results/pharmasignal_cases.json``에 저장한다(커밋 안 함).
사용: ``.venv/bin/python src/harness/tools/pharmasignal_cases.py [drug reaction ...]``
      인자가 없으면 DEFAULT_CASES 3건을 돈다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from .pharmasignal_common import DEFAULT_CACHE_DIR, now_iso
    from .pharmasignal_dailymed import find_label_mentions
    from .pharmasignal_openfda import faers_disproportionality
    from .pharmasignal_pubmed import search_pubmed
except ImportError:
    from pharmasignal_common import DEFAULT_CACHE_DIR, now_iso
    from pharmasignal_dailymed import find_label_mentions
    from pharmasignal_openfda import faers_disproportionality
    from pharmasignal_pubmed import search_pubmed

# (약물, 반응, 기대 라벨 상태 메모). 기대는 실행 전 가설이며 결과 JSON의 expectation 필드로만 남긴다.
DEFAULT_CASES: list[tuple[str, str, str]] = [
    ("metformin", "Lactic acidosis", "라벨 기재 예상(박스 경고)"),
    ("semaglutide", "Pancreatitis", "라벨 기재 예상(Warnings and Precautions)"),
    ("amoxicillin", "Retinal detachment", "근거 적음 예상(FAERS 소수, 라벨 미기재)"),
]
RESULTS_PATH = DEFAULT_CACHE_DIR / "pharmasignal_cases.json"


def run_case(drug: str, reaction: str, name_field: str = "generic", pubmed_retmax: int = 10,
             max_labels: int = 1, use_cache: bool = True, expectation: str | None = None) -> dict[str, Any]:
    """한 (약물, 반응) 조합에 대한 세 도구 결과와 요약. JSON 직렬화 가능."""
    faers = faers_disproportionality(drug, reaction, name_field=name_field, use_cache=use_cache)
    label = find_label_mentions(drug, reaction, max_labels=max_labels, use_cache=use_cache)
    lit = search_pubmed(drug, reaction, retmax=pubmed_retmax, use_cache=use_cache)
    summary = {
        "faers_a": (faers.get("counts") or {}).get("a"),
        "prr": faers.get("prr"), "ror": faers.get("ror"), "chi2": faers.get("chi2"),
        # chi2 는 보정 없는 Pearson 이고, evans_signal 의 판정 근거는 Yates 보정 카이제곱이다.
        # 판정과 근거를 함께 읽을 수 있도록 chi2_yates 를 나란히 남긴다.
        "chi2_yates": faers.get("chi2_yates"),
        "evans_signal": faers.get("evans_signal"),
        # ROR 계열 관례(a>=3, 95% CI 하한 > 1)의 판정. Evans 계열과 어긋나는 경우를 사람이 본다.
        "ror_signal": faers.get("ror_signal"),
        # 0 셀이 있어 Haldane-Anscombe 0.5 보정을 적용했는지. ror_signal 을 읽을 때 함께 본다.
        "haldane_applied": faers.get("haldane_applied"),
        "labeled": label.get("labeled"), "label_sections": label.get("mentioned_sections"),
        "pubmed_total": lit.get("total_count"), "pubmed_returned": len(lit.get("pmids") or []),
        "errors": faers.get("errors", []) + label.get("errors", []) + lit.get("errors", []),
    }
    evidence_ids = {
        "faers_query_urls": faers.get("evidence_ids", []),
        "dailymed_setids": label.get("evidence_ids", []),
        "pubmed_pmids": lit.get("evidence_ids", []),
    }
    return {"drug": drug, "reaction": reaction, "expectation": expectation, "summary": summary,
            "evidence_ids": evidence_ids, "faers": faers, "label": label, "pubmed": lit,
            "run_at": now_iso()}


def run_cases(cases: list[tuple[str, str, str]] | None = None, out_path: Path | str = RESULTS_PATH,
              use_cache: bool = True) -> dict[str, Any]:
    cases = cases or DEFAULT_CASES
    results = [run_case(d, r, expectation=e, use_cache=use_cache) for d, r, e in cases]
    doc = {"generated_at": now_iso(), "n_cases": len(results), "cases": results}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(out_path)
    return doc


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and len(args) % 2 == 0:
        selected = [(args[i], args[i + 1], None) for i in range(0, len(args), 2)]
    else:
        selected = None
    doc = run_cases(selected)
    for c in doc["cases"]:
        print(json.dumps({"drug": c["drug"], "reaction": c["reaction"], **c["summary"]}, ensure_ascii=False))
    print("saved:", RESULTS_PATH)
