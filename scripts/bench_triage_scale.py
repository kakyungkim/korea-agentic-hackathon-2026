#!/usr/bin/env python
"""이상사례를 건별로 선별하는 경로를 만들고, 그 경로를 프런티어 모델로 돌릴 때의 시간과 비용을 재는 벤치마크.

왜 필요한가
-----------
지금 파이프라인은 화합물 하나를 깊게 따라간다. 그 구조에서는 앞단에 싼 분류기를 두는
이점이 드러나지 않는다. 한 건을 처리하는 비용이 애초에 작기 때문이다. 이점은 건수가
많을 때 드러난다. 그래서 여기서는 한 화합물의 이상사례를 여러 건 받아 건마다 판정을
한 번씩 돌리고, 건당 지연과 건당 토큰을 잰다.

무엇을 재는가
-------------
한 화합물의 FAERS 이상사례 목록을 보고 건수 많은 순으로 앞의 N 건을 잡는다. 건마다
openFDA 2x2 집계와 불균형 지표를 붙이고, "이건 사람이 먼저 봐야 하는가" 를 묻는
예아니오 질문을 한 번 던진다. 기록하는 값은 넷이다.

- 판정: yes 는 사람이 먼저 검토, no 는 자동 큐에 남김
- 지연: 건당 밀리초. 평균과 중앙값을 함께 적는다
- 토큰: 입력과 출력을 나눠 세고 건당 값으로 환산한다
- 고정 규칙과의 일치: LLM 없이 도는 규칙(Evans 신호 또는 ROR 신호)과 얼마나 같은 답을 내는가

마지막 항목이 이 실험의 요지다. 예아니오 하나를 받자고 모델이 얼마나 많은 토큰을 쓰는지,
그 답이 공짜로 도는 규칙과 얼마나 다른지를 나란히 놓는다.

판정기는 OpenAI 호환 엔드포인트면 무엇이든 붙는다. ``--base-url`` 과 ``--model`` 과
``--api-key-env`` 셋만 바꾸면 되고, 키는 환경변수에서만 읽어 저장소에 남지 않는다.

사용
----
    # 캐시만 쓰고 LLM 을 부르지 않는 경로. 키 없는 환경에서도 끝까지 돈다
    .venv/bin/python scripts/bench_triage_scale.py --offline --drug niraparib

    # 기준선. 지금 쓰는 NVIDIA 모델로 10건
    set -a; source .env; set +a
    .venv/bin/python scripts/bench_triage_scale.py --drug niraparib --limit 10

    # 판정기를 바꾼다
    .venv/bin/python scripts/bench_triage_scale.py --label jev \\
        --base-url https://<배포주소>/v1 --model typesafe-ai/jev --api-key-env JEV_API_KEY

주의
----
한 건마다 openFDA 를 네 번, 판정기를 한 번 부른다. ``--limit`` 기본값을 10 으로 작게 둔
이유가 그것이다. 호출이 곧 비용이다. openFDA 원응답은 기존 도구의 파일 캐시에 그대로
쌓이므로 같은 화합물을 다시 돌리면 네트워크로 나가지 않는다.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from harness.tools import pharmasignal_openfda as ofda  # noqa: E402
from harness.tools.pharmasignal_common import ResponseCache, http_get, now_iso  # noqa: E402

DEFAULT_DRUG = "niraparib"
DEFAULT_LIMIT = 10
DEFAULT_OUT_DIR = "eval/results"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# 짧고 정형화된 예아니오 질문. 긴 설명을 요구하지 않는다. 이 실험이 보려는 것은
# 판정 하나를 받는 데 드는 토큰이지 판정문의 완성도가 아니다.
SYSTEM_PROMPT = """당신은 약물감시 1차 선별 담당이다. 이상사례 한 건의 FAERS 집계와 불균형 지표만 보고
그 건을 사람이 먼저 봐야 하는지 판정한다.

출력은 아래 두 줄만 쓴다. 다른 문장, 목록, 해설을 붙이지 않는다.
VERDICT: YES 또는 NO
REASON: 한 문장, 60자 이내

YES 는 사람이 먼저 검토해야 하는 건이다. NO 는 자동 큐에 남겨도 되는 건이다.
판단 근거는 주어진 숫자뿐이다. 주어지지 않은 사실을 끌어오지 않는다."""


# ======================================================================================
# 이상사례 목록 받기
# ======================================================================================

def count_url(drug: str, name_field: str = "generic") -> str:
    """한 약물의 반응별 보고 건수를 세는 openFDA 집계 쿼리.

    기존 도구가 쓰는 필드 상수와 절 생성기를 그대로 빌려 쓴다. 도구 파일은 고치지 않는다.
    """
    clause = ofda._drug_clause(drug, name_field)
    return f"{ofda.BASE}?search={clause}&count={ofda.REACTION_FIELD}"


def count_cache(drug: str, name_field: str = "generic", enabled: bool = True) -> ResponseCache:
    """반응 목록 응답을 담는 캐시. 건별 2x2 캐시와 섞이지 않게 source 를 따로 둔다."""
    return ResponseCache("triage_events", f"{drug.strip().lower()}|{name_field}", enabled=enabled)


class CacheOnlyGet:
    """오프라인용 ``http_get`` 대체물. 캐시에 있으면 돌려주고 없으면 오류 표시를 낸다.

    네트워크로 절대 나가지 않는다. 캐시에 없는 URL 은 ``offline_cache_miss`` 로 돌아오고,
    그 건은 집계에서 실패로 잡힌다.
    """

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0

    def __call__(self, url: str, cache: ResponseCache | None = None, **_kwargs: Any) -> Any:
        hit = None if cache is None else cache.get(url)
        if hit is None:
            self.misses += 1
            return {"__error__": "offline_cache_miss", "body": url}
        self.hits += 1
        cache.hits += 1
        return hit


@contextlib.contextmanager
def cache_only_network(*modules: Any):
    """with 블록 안에서만 도구 모듈의 ``http_get`` 을 캐시 전용 대체물로 바꾼다.

    ``pharmasignal_openfda.py`` 파일은 손대지 않는다. 블록을 빠져나올 때 원래 함수를
    되돌린다. 오프라인 경로에서 기존 도구의 2x2 계산과 지표 산식을 그대로 재사용하면서도
    네트워크로 나가는 길만 막는 것이 목적이다.
    """
    stub = CacheOnlyGet()
    saved = [(m, m.http_get) for m in modules]
    try:
        for m in modules:
            m.http_get = stub
        yield stub
    finally:
        for m, fn in saved:
            m.http_get = fn


def fetch_events(drug: str, *, limit: int = DEFAULT_LIMIT, name_field: str = "generic",
                 use_cache: bool = True, offline: bool = False) -> dict[str, Any]:
    """한 화합물의 이상사례를 보고 건수 많은 순으로 앞의 N 건 받아 온다.

    반환: drug, name_field, url, events[{term, count}], total_terms, errors, cache.
    결과 없음(404 NOT_FOUND)은 오류가 아니라 0건으로 읽는다.
    """
    if name_field not in ofda.NAME_FIELDS:
        raise ValueError(f"name_field 는 {sorted(ofda.NAME_FIELDS)} 중 하나여야 합니다: {name_field!r}")
    cache = count_cache(drug, name_field, enabled=use_cache)
    url = count_url(drug, name_field)
    getter = CacheOnlyGet() if offline else http_get
    payload = getter(url, cache=cache, is_json=True)

    errors: list[str] = []
    results: list[dict[str, Any]] = []
    if isinstance(payload, dict) and "__error__" in payload:
        if payload["__error__"] == 404 and "NOT_FOUND" in str(payload.get("body", "")):
            pass  # 보고가 한 건도 없다
        else:
            errors.append(f"events: http_error:{payload['__error__']}")
    elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
        results = payload["results"]
    else:
        errors.append("events: unexpected_payload")

    events = [{"rank": i, "reaction": str(r.get("term", "")), "faers_count": int(r.get("count", 0))}
              for i, r in enumerate(results[:limit], 1) if r.get("term")]
    return {"drug": drug, "name_field": name_field, "url": url, "events": events,
            "total_terms": len(results), "errors": errors,
            "cache": {"path": str(cache.path), "hits": cache.hits, "misses": cache.misses}}


# ======================================================================================
# 건별 판정
# ======================================================================================

def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "없음"
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, (int,)):
        return f"{value:,}"
    return f"{value:,.{digits}f}"


def _fmt_ci(ci: Any) -> str:
    if not ci or len(ci) != 2 or ci[0] is None:
        return "없음"
    return f"{ci[0]:,.2f} 에서 {ci[1]:,.2f}"


def build_evidence(drug: str, event: dict[str, Any], faers: dict[str, Any]) -> str:
    """판정기에 줄 근거. 그 이상사례의 FAERS 집계와 불균형 지표만 담는다."""
    counts = faers.get("counts") or {}
    lines = [
        f"약물: {drug}",
        f"이상사례(MedDRA PT): {event['reaction']}",
        f"이 약물에서의 보고 건수: {_fmt(event.get('faers_count'))}",
        f"2x2 집계: a={_fmt(counts.get('a'))}, b={_fmt(counts.get('b'))}, "
        f"c={_fmt(counts.get('c'))}, d={_fmt(counts.get('d'))}",
        f"PRR: {_fmt(faers.get('prr'))} (95% CI {_fmt_ci(faers.get('prr_ci95'))})",
        f"ROR: {_fmt(faers.get('ror'))} (95% CI {_fmt_ci(faers.get('ror_ci95'))})",
        f"카이제곱(Yates 보정): {_fmt(faers.get('chi2_yates'))}",
        f"Evans 신호: {_fmt(faers.get('evans_signal'))}",
        f"ROR 신호: {_fmt(faers.get('ror_signal'))}",
    ]
    return "\n".join(lines)


def parse_verdict(text: str) -> tuple[str | None, str]:
    """응답에서 판정과 짧은 사유를 꺼낸다. 형식이 어긋나면 판정은 None 이다."""
    verdict = None
    match = re.search(r"VERDICT\s*[:：]\s*\**\s*(YES|NO)", text or "", re.IGNORECASE)
    if match is None:
        match = re.search(r"\b(YES|NO)\b", text or "", re.IGNORECASE)
    if match:
        verdict = match.group(1).lower()
    reason = ""
    rmatch = re.search(r"REASON\s*[:：]\s*(.+)", text or "")
    if rmatch:
        reason = rmatch.group(1).strip()
    return verdict, reason[:200]


def rule_verdict(faers: dict[str, Any]) -> str | None:
    """LLM 없이 도는 고정 규칙. Evans 신호나 ROR 신호가 서면 사람이 먼저 본다.

    집계를 못 받은 건은 판정하지 않고 None 을 돌려준다.
    """
    if not faers.get("counts"):
        return None
    return "yes" if (faers.get("evans_signal") or faers.get("ror_signal")) else "no"


def rule_one(faers: dict[str, Any]) -> dict[str, Any]:
    """고정 규칙 한 건. LLM 을 부르지 않으므로 토큰은 없고 지연은 계산 시간뿐이다."""
    started = time.perf_counter()
    verdict = rule_verdict(faers)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    if verdict is None:
        return {"ok": False, "error": "FAERS 집계를 받지 못해 판정하지 않았다",
                "verdict": None, "reason": "", "latency_ms": latency_ms,
                "usage": None, "judge": "rule"}
    return {"ok": True, "error": None, "verdict": verdict,
            "reason": "Evans 또는 ROR 신호" if verdict == "yes" else "신호 기준 미달",
            "latency_ms": latency_ms, "usage": None, "judge": "rule"}


def judge_one(client: Any, model: str, evidence: str, *, timeout: float,
              max_tokens: int) -> dict[str, Any]:
    """한 건을 한 번 부르고 판정과 지연과 토큰을 돌려준다."""
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": evidence}],
            temperature=0.2, top_p=0.95, max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    except Exception as exc:  # noqa: BLE001  실패도 그대로 기록한다
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "verdict": None, "reason": "",
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "usage": None, "judge": "llm"}
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    text = (response.choices[0].message.content or "") if response.choices else ""
    usage = getattr(response, "usage", None)
    usage_d = {"prompt_tokens": getattr(usage, "prompt_tokens", None),
               "completion_tokens": getattr(usage, "completion_tokens", None),
               "total_tokens": getattr(usage, "total_tokens", None)} if usage else None

    verdict, reason = parse_verdict(text)
    if verdict is None:
        return {"ok": False, "error": "응답에서 VERDICT 를 읽지 못했다",
                "verdict": None, "reason": "", "latency_ms": latency_ms,
                "usage": usage_d, "judge": "llm", "raw_response": text[:400]}
    return {"ok": True, "error": None, "verdict": verdict, "reason": reason,
            "latency_ms": latency_ms, "usage": usage_d, "judge": "llm"}


def faers_for_event(drug: str, reaction: str, *, name_field: str = "generic",
                    use_cache: bool = True) -> dict[str, Any]:
    """기존 도구를 그대로 불러 한 건의 2x2 와 불균형 지표를 받는다.

    오프라인에서는 호출부가 ``cache_only_network`` 로 감싸므로 이 함수는 그대로 두고도
    네트워크로 나가지 않는다.
    """
    return ofda.faers_disproportionality(drug, reaction, name_field=name_field,
                                         use_cache=use_cache)


def run_rows(drug: str, events: list[dict[str, Any]], *, name_field: str = "generic",
             use_cache: bool = True, client: Any = None, model: str = "",
             timeout: float = 120.0, max_tokens: int = 256, sleep: float = 0.0,
             progress: bool = True) -> list[dict[str, Any]]:
    """이상사례 목록을 건별로 돌린다. ``client`` 가 없으면 고정 규칙으로 판정한다."""
    rows: list[dict[str, Any]] = []
    total = len(events)
    for i, event in enumerate(events, 1):
        faers = faers_for_event(drug, event["reaction"], name_field=name_field,
                                use_cache=use_cache)
        evidence = build_evidence(drug, event, faers)
        if client is None:
            result = rule_one(faers)
        else:
            result = judge_one(client, model, evidence, timeout=timeout, max_tokens=max_tokens)
        counts = faers.get("counts") or {}
        row = {
            "rank": event.get("rank", i),
            "reaction": event["reaction"],
            "faers_count": event.get("faers_count"),
            "counts_a": counts.get("a"),
            "prr": faers.get("prr"),
            "ror": faers.get("ror"),
            "chi2_yates": faers.get("chi2_yates"),
            "evans_signal": faers.get("evans_signal"),
            "ror_signal": faers.get("ror_signal"),
            "rule_verdict": rule_verdict(faers),
            "faers_errors": faers.get("errors", []),
            "evidence_chars": len(evidence),
        }
        row.update(result)
        rows.append(row)
        if progress:
            tok = (row.get("usage") or {}).get("total_tokens")
            print(f"  [{i:2d}/{total}] {row['reaction'][:34]:<34} "
                  f"판정 {str(row['verdict']):<4} 규칙 {str(row['rule_verdict']):<4} "
                  f"{row['latency_ms']:>9.1f} ms  토큰 {str(tok):>6}  "
                  f"{row['error'] or ''}", flush=True)
        if sleep and i < total:
            time.sleep(sleep)
    return rows


# ======================================================================================
# 요약
# ======================================================================================

def summarize(rows: list[dict[str, Any]], *, price_in: float | None = None,
              price_out: float | None = None, wall_clock_s: float | None = None) -> dict[str, Any]:
    """건수, 건당 토큰, 지연을 센다. 실패한 호출은 집계에서 빼고 따로 센다."""
    ok = [r for r in rows if r.get("ok")]
    failed = [r for r in rows if not r.get("ok")]
    n = len(ok)

    lat = [r["latency_ms"] for r in ok if r.get("latency_ms") is not None]
    p_tok = sum((r.get("usage") or {}).get("prompt_tokens") or 0 for r in ok)
    c_tok = sum((r.get("usage") or {}).get("completion_tokens") or 0 for r in ok)
    t_tok = p_tok + c_tok

    cost = None
    if price_in is not None and price_out is not None:
        cost = round(p_tok / 1_000_000 * price_in + c_tok / 1_000_000 * price_out, 6)

    verdicts = {"yes": sum(1 for r in ok if r.get("verdict") == "yes"),
                "no": sum(1 for r in ok if r.get("verdict") == "no")}

    comparable = [r for r in ok if r.get("rule_verdict") in ("yes", "no")]
    match = sum(1 for r in comparable if r.get("verdict") == r.get("rule_verdict"))

    per_event = {
        "prompt_tokens": round(p_tok / n, 1) if n else None,
        "completion_tokens": round(c_tok / n, 1) if n else None,
        "total_tokens": round(t_tok / n, 1) if n else None,
        "latency_ms_mean": round(statistics.fmean(lat), 1) if lat else None,
        "latency_ms_median": round(statistics.median(lat), 1) if lat else None,
        "cost_usd": round(cost / n, 8) if (cost is not None and n) else None,
    }

    # 건수가 늘 때의 값. 건당 값을 그대로 곱한 추정이며 병렬 실행과 캐시 효과는 넣지 않았다.
    projected = None
    if n:
        projected = {
            "basis": "건당 평균을 1,000건에 그대로 곱한 추정값이다. 실측이 아니다.",
            "events": 1000,
            "total_tokens": int(round(t_tok / n * 1000)),
            "hours_sequential": (round(per_event["latency_ms_mean"] * 1000 / 3_600_000, 2)
                                 if per_event["latency_ms_mean"] is not None else None),
            "cost_usd": round(cost / n * 1000, 4) if cost is not None else None,
        }

    return {
        "events": len(rows), "ok": n, "failed": len(failed),
        "failed_reactions": [r.get("reaction") for r in failed],
        "verdicts": verdicts,
        "rule_agreement": {"match": match, "of": len(comparable),
                           "rate": round(match / len(comparable), 4) if comparable else None},
        "latency_ms": {"mean": round(statistics.fmean(lat), 1) if lat else None,
                       "median": round(statistics.median(lat), 1) if lat else None,
                       "min": min(lat) if lat else None, "max": max(lat) if lat else None,
                       "total": round(sum(lat), 1) if lat else None},
        "tokens": {"prompt": p_tok, "completion": c_tok, "total": t_tok},
        "per_event": per_event,
        "cost_usd": cost,
        "wall_clock_s": None if wall_clock_s is None else round(wall_clock_s, 2),
        "projected_estimate": projected,
    }


def print_summary(label: str, s: dict[str, Any]) -> None:
    lat, pe, agr = s["latency_ms"], s["per_event"], s["rule_agreement"]
    print(f"\n[{label}]")
    print(f"  건수          {s['events']}건 (성공 {s['ok']}, 실패 {s['failed']})")
    print(f"  판정          yes {s['verdicts']['yes']} / no {s['verdicts']['no']}")
    print(f"  규칙과 일치    {agr['match']}/{agr['of']}")
    print(f"  지연 중앙값    {lat['median']} ms (평균 {lat['mean']} ms)")
    print(f"  건당 토큰      입력 {pe['prompt_tokens']} / 출력 {pe['completion_tokens']} "
          f"/ 합계 {pe['total_tokens']}")
    print(f"  토큰 합계      입력 {s['tokens']['prompt']:,} / 출력 {s['tokens']['completion']:,}")
    if s["cost_usd"] is not None:
        print(f"  비용          ${s['cost_usd']} (건당 ${pe['cost_usd']})")
    if s["wall_clock_s"] is not None:
        print(f"  벽시계        {s['wall_clock_s']} 초 (대기 시간 포함)")
    if s["projected_estimate"]:
        p = s["projected_estimate"]
        print(f"  1,000건 추정   토큰 {p['total_tokens']:,}, 순차 {p['hours_sequential']} 시간"
              + (f", ${p['cost_usd']}" if p["cost_usd"] is not None else ""))
    if s["failed_reactions"]:
        print(f"  실패한 건      {', '.join(str(x) for x in s['failed_reactions'])}")


# ======================================================================================
# 진입점
# ======================================================================================

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="이상사례 건별 선별 경로의 시간과 비용 측정")
    ap.add_argument("--drug", default=DEFAULT_DRUG, help=f"화합물 이름. 기본 {DEFAULT_DRUG}")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"돌릴 이상사례 건수. 기본 {DEFAULT_LIMIT}. 호출이 곧 비용이다")
    ap.add_argument("--label", default=None, help="이 실행의 이름. 산출 파일명에 들어간다")
    ap.add_argument("--name-field", default="generic",
                    help="약물명 매칭 필드. generic, brand, medicinalproduct 중 하나")
    ap.add_argument("--base-url", default=None, help=f"기본 {DEFAULT_BASE_URL}")
    ap.add_argument("--model", default=None, help=f"기본 {DEFAULT_MODEL}")
    ap.add_argument("--api-key-env", default="NVIDIA_API_KEY",
                    help="키를 담은 환경변수 이름. 기본 NVIDIA_API_KEY")
    ap.add_argument("--sleep", type=float, default=1.0, help="호출 사이 대기 초. 기본 1.0")
    ap.add_argument("--offline", action="store_true",
                    help="캐시만 쓰고 LLM 을 부르지 않는다. 판정은 고정 규칙이 낸다")
    ap.add_argument("--out", default=DEFAULT_OUT_DIR, help=f"산출 디렉터리. 기본 {DEFAULT_OUT_DIR}")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--price-in", type=float, default=None,
                    help="입력 백만 토큰당 달러. 주면 비용을 환산한다")
    ap.add_argument("--price-out", type=float, default=None, help="출력 백만 토큰당 달러")
    args = ap.parse_args(argv)

    if args.name_field not in ofda.NAME_FIELDS:
        print(f"--name-field 는 {sorted(ofda.NAME_FIELDS)} 중 하나여야 한다.", file=sys.stderr)
        return 2

    model = "" if args.offline else (args.model or os.environ.get("MODEL_PLANNER") or DEFAULT_MODEL)
    base_url = "" if args.offline else (args.base_url or os.environ.get("NVIDIA_BASE_URL") or DEFAULT_BASE_URL)
    label = args.label or ("offline" if args.offline else model.split("/")[-1])
    mode = "rule-offline" if args.offline else "llm"

    client = None
    if not args.offline:
        key = (os.environ.get(args.api_key_env) or "").strip()
        if not key:
            print(f"환경변수 {args.api_key_env} 가 비어 있다. 키를 넣거나 --offline 으로 돌려라.",
                  file=sys.stderr)
            return 2
        try:
            from openai import OpenAI
        except ImportError:
            print("openai 패키지가 없다.", file=sys.stderr)
            return 2
        client = OpenAI(base_url=base_url, api_key=key, timeout=args.timeout)

    started_all = time.perf_counter()
    if args.offline:
        with cache_only_network(ofda):
            listing = fetch_events(args.drug, limit=args.limit, name_field=args.name_field,
                                   offline=True)
            print(f"{args.drug} 이상사례 {len(listing['events'])}건 (캐시 전용, 고정 규칙 판정)")
            if listing["errors"]:
                print(f"  목록 오류: {'; '.join(listing['errors'])}")
            rows = run_rows(args.drug, listing["events"], name_field=args.name_field,
                            client=None, sleep=0.0)
    else:
        listing = fetch_events(args.drug, limit=args.limit, name_field=args.name_field)
        print(f"{args.drug} 이상사례 {len(listing['events'])}건, 모델 {model}, 엔드포인트 {base_url}")
        if listing["errors"]:
            print(f"  목록 오류: {'; '.join(listing['errors'])}")
        rows = run_rows(args.drug, listing["events"], name_field=args.name_field,
                        client=client, model=model, timeout=args.timeout,
                        max_tokens=args.max_tokens, sleep=args.sleep)
    wall_clock_s = time.perf_counter() - started_all

    summary = summarize(rows, price_in=args.price_in, price_out=args.price_out,
                        wall_clock_s=wall_clock_s)
    print_summary(label, summary)

    doc = {
        "label": label, "drug": args.drug, "mode": mode, "model": model, "base_url": base_url,
        "limit": args.limit, "name_field": args.name_field,
        "events_url": listing["url"], "events_total_terms": listing["total_terms"],
        "events_errors": listing["errors"],
        "prompt": SYSTEM_PROMPT if mode == "llm" else None,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "retrieved_at": now_iso(),
        "summary": summary, "rows": rows,
    }
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"triage_scale_{label}.json"
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(out_path)
    print(f"\n  {out_path} ({out_path.stat().st_size:,}바이트)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
