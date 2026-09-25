#!/usr/bin/env python
"""크리틱 3단 판정기를 바꿔 가며 같은 조건으로 재는 A/B 벤치마크.

왜 필요한가
-----------
3단 과잉해석 판정에 어떤 모델을 쓰든, 바꾸기 전과 바꾼 뒤를 같은 데이터와 같은 프롬프트로
재야 비교가 선다. 지금 ``eval/results/critic_verdict_output_*.json`` 에는 판정만 있고
지연과 토큰이 없어서 속도와 비용을 말할 근거가 없다. 이 스크립트가 그 빈자리를 메운다.

무엇을 재는가
-------------
``eval/cases.jsonl`` 33건(정상 17, 과잉해석 16)에 3단 프롬프트를 그대로 물리고 케이스마다
판정, 지연, 토큰을 기록한다. 지표는 넷이다.

- 적발률: 반려해야 할 16건 중 실제로 반려한 수
- 거짓 양성: 통과해야 할 17건 중 잘못 반려한 수
- 지연: 케이스당 밀리초. 평균과 중앙값을 함께 적는다
- 비용: 토큰 합계. 단가를 주면 달러로 환산한다

판정기는 OpenAI 호환 엔드포인트면 무엇이든 붙는다. ``--base-url`` 과 ``--model`` 과
``--api-key-env`` 셋만 바꾸면 되고, 키는 환경변수에서만 읽어 저장소에 남지 않는다.

사용
----
    # 기준선. 지금 쓰는 NVIDIA 모델
    .venv/bin/python scripts/bench_critic_judge.py --label nemotron-super

    # 바꾼 뒤. 다른 엔드포인트를 붙인다
    .venv/bin/python scripts/bench_critic_judge.py \\
        --label jev --base-url https://<배포주소>/v1 \\
        --model typesafe-ai/jev --api-key-env JEV_API_KEY

    # 두 결과를 나란히 본다
    .venv/bin/python scripts/bench_critic_judge.py --compare \\
        eval/results/bench_nemotron-super.json eval/results/bench_jev.json

주의
----
케이스마다 한 번씩 부르므로 한 번 돌리면 33회 호출한다. 레이트리밋을 만나면
``--sleep`` 으로 간격을 준다. ``--limit`` 으로 앞의 몇 건만 시험 삼아 돌릴 수 있다.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from harness.critic import parse_critic_report  # noqa: E402
from harness.tools import overclaim_rules as ocr  # noqa: E402

DEFAULT_CASES = "eval/cases.jsonl"
DEFAULT_OUT_DIR = "eval/results"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# nat eval 경로와 같은 프롬프트를 쓴다. 그쪽은 숫자 오라클이 앞에 없다.
SYSTEM_PROMPT = ocr.stage3_prompt(numbers_verified=False)


def load_cases(path: Path, limit: int | None) -> list[dict[str, Any]]:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return cases[:limit] if limit else cases


def judge_one(client: Any, model: str, case_input: str, *, timeout: float,
              max_tokens: int) -> dict[str, Any]:
    """한 케이스를 한 번 부르고 판정과 지연과 토큰을 돌려준다."""
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": case_input}],
            temperature=0.2, top_p=0.95, max_tokens=max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    except Exception as exc:  # noqa: BLE001  실패도 그대로 기록한다
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "verdict": None, "usage": None}
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    text = (response.choices[0].message.content or "") if response.choices else ""
    usage = getattr(response, "usage", None)
    usage_d = {"prompt_tokens": getattr(usage, "prompt_tokens", None),
               "completion_tokens": getattr(usage, "completion_tokens", None),
               "total_tokens": getattr(usage, "total_tokens", None)} if usage else None

    report = parse_critic_report(text)
    if report is None:
        return {"ok": False, "error": "응답이 CriticReport 형식이 아니다",
                "latency_ms": latency_ms, "verdict": None, "usage": usage_d,
                "raw_response": text[:600]}
    return {"ok": True, "error": None, "latency_ms": latency_ms,
            "verdict": report.verdict, "usage": usage_d}


def summarize(rows: list[dict[str, Any]], *, price_in: float | None,
              price_out: float | None) -> dict[str, Any]:
    """적발률, 거짓 양성, 지연, 토큰, 비용을 센다. 실패 건은 따로 센다."""
    ok = [r for r in rows if r["ok"]]
    failed = [r for r in rows if not r["ok"]]

    should_reject = [r for r in rows if r["expected_verdict"] == "reject"]
    should_pass = [r for r in rows if r["expected_verdict"] == "pass"]
    caught = [r for r in should_reject if r["verdict"] == "reject"]
    false_positive = [r for r in should_pass if r["verdict"] == "reject"]

    lat = [r["latency_ms"] for r in ok]
    p_tok = sum((r.get("usage") or {}).get("prompt_tokens") or 0 for r in ok)
    c_tok = sum((r.get("usage") or {}).get("completion_tokens") or 0 for r in ok)

    cost = None
    if price_in is not None and price_out is not None:
        cost = round(p_tok / 1_000_000 * price_in + c_tok / 1_000_000 * price_out, 6)

    return {
        "cases": len(rows), "ok": len(ok), "failed": len(failed),
        "detection": {"caught": len(caught), "of": len(should_reject),
                      "rate": round(len(caught) / len(should_reject), 4) if should_reject else None},
        "false_positive": {"count": len(false_positive), "of": len(should_pass),
                           "rate": round(len(false_positive) / len(should_pass), 4) if should_pass else None},
        "latency_ms": {"mean": round(statistics.fmean(lat), 1) if lat else None,
                       "median": round(statistics.median(lat), 1) if lat else None,
                       "min": min(lat) if lat else None, "max": max(lat) if lat else None},
        "tokens": {"prompt": p_tok, "completion": c_tok, "total": p_tok + c_tok},
        "cost_usd": cost,
        "failed_ids": [r["id"] for r in failed],
    }


def print_summary(label: str, s: dict[str, Any]) -> None:
    det, fp, lat = s["detection"], s["false_positive"], s["latency_ms"]
    print(f"\n[{label}]")
    print(f"  케이스        {s['cases']}건 (성공 {s['ok']}, 실패 {s['failed']})")
    print(f"  적발률        {det['caught']}/{det['of']}")
    print(f"  거짓 양성     {fp['count']}/{fp['of']}")
    print(f"  지연 평균     {lat['mean']} ms")
    print(f"  지연 중앙값   {lat['median']} ms")
    print(f"  토큰          입력 {s['tokens']['prompt']:,} / 출력 {s['tokens']['completion']:,}")
    if s["cost_usd"] is not None:
        print(f"  비용          ${s['cost_usd']}")
    if s["failed_ids"]:
        print(f"  실패한 케이스 {', '.join(s['failed_ids'])}")


def compare(paths: list[str]) -> int:
    """돌려 둔 결과 둘 이상을 한 표로 나란히 둔다."""
    docs = []
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        docs.append(d)
    head = ["지표"] + [d["label"] for d in docs]
    rows = [
        ["적발률"] + [f"{d['summary']['detection']['caught']}/{d['summary']['detection']['of']}" for d in docs],
        ["거짓 양성"] + [f"{d['summary']['false_positive']['count']}/{d['summary']['false_positive']['of']}" for d in docs],
        ["지연 중앙값 (ms)"] + [str(d["summary"]["latency_ms"]["median"]) for d in docs],
        ["지연 평균 (ms)"] + [str(d["summary"]["latency_ms"]["mean"]) for d in docs],
        ["총 토큰"] + [f"{d['summary']['tokens']['total']:,}" for d in docs],
        ["비용 (USD)"] + [("" if d["summary"]["cost_usd"] is None else f"${d['summary']['cost_usd']}") for d in docs],
        ["모델"] + [d["model"] for d in docs],
    ]
    width = [max(len(r[i]) for r in [head] + rows) for i in range(len(head))]
    def line(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(width[i]) for i, c in enumerate(cells)) + " |"
    print(line(head))
    print("|" + "|".join("-" * (w + 2) for w in width) + "|")
    for r in rows:
        print(line(r))

    base, *rest = docs
    for d in rest:
        bl, dl = base["summary"]["latency_ms"]["median"], d["summary"]["latency_ms"]["median"]
        bt, dt = base["summary"]["tokens"]["total"], d["summary"]["tokens"]["total"]
        if bl and dl:
            print(f"\n{d['label']} 는 {base['label']} 대비 지연 중앙값 {bl / dl:.2f}배, "
                  f"토큰 {bt / dt:.2f}배다.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="크리틱 3단 판정기 A/B 벤치마크")
    ap.add_argument("--compare", nargs="+", metavar="JSON",
                    help="돌려 둔 결과 파일들을 한 표로 비교하고 끝낸다")
    ap.add_argument("--label", default=None, help="이 실행의 이름. 산출 파일명에 들어간다")
    ap.add_argument("--cases", default=DEFAULT_CASES)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    ap.add_argument("--base-url", default=None, help=f"기본 {DEFAULT_BASE_URL}")
    ap.add_argument("--model", default=None, help=f"기본 {DEFAULT_MODEL}")
    ap.add_argument("--api-key-env", default="NVIDIA_API_KEY",
                    help="키를 담은 환경변수 이름. 기본 NVIDIA_API_KEY")
    ap.add_argument("--limit", type=int, default=None, help="앞의 N 건만 돌린다")
    ap.add_argument("--sleep", type=float, default=0.0, help="호출 사이 대기 초")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--price-in", type=float, default=None,
                    help="입력 백만 토큰당 달러. 주면 비용을 환산한다")
    ap.add_argument("--price-out", type=float, default=None, help="출력 백만 토큰당 달러")
    args = ap.parse_args(argv)

    if args.compare:
        return compare(args.compare)

    model = args.model or os.environ.get("MODEL_PLANNER") or DEFAULT_MODEL
    base_url = args.base_url or os.environ.get("NVIDIA_BASE_URL") or DEFAULT_BASE_URL
    label = args.label or model.split("/")[-1]

    key = (os.environ.get(args.api_key_env) or "").strip()
    if not key:
        print(f"환경변수 {args.api_key_env} 가 비어 있다. 키를 넣고 다시 돌려라.", file=sys.stderr)
        return 2

    try:
        from openai import OpenAI
    except ImportError:
        print("openai 패키지가 없다.", file=sys.stderr)
        return 2

    cases = load_cases(REPO_ROOT / args.cases, args.limit)
    print(f"케이스 {len(cases)}건, 모델 {model}, 엔드포인트 {base_url}")

    client = OpenAI(base_url=base_url, api_key=key, timeout=args.timeout)
    rows: list[dict[str, Any]] = []
    for i, case in enumerate(cases, 1):
        r = judge_one(client, model, case["input"],
                      timeout=args.timeout, max_tokens=args.max_tokens)
        r.update({"id": case["id"], "expected_verdict": case["expected_verdict"]})
        hit = "" if not r["ok"] else ("맞음" if r["verdict"] == case["expected_verdict"] else "틀림")
        print(f"  [{i:2d}/{len(cases)}] {case['id']:<34} "
              f"기대 {case['expected_verdict']:<6} 판정 {str(r['verdict']):<6} "
              f"{r['latency_ms']:>8.1f} ms  {hit or r['error']}", flush=True)
        rows.append(r)
        if args.sleep and i < len(cases):
            time.sleep(args.sleep)

    summary = summarize(rows, price_in=args.price_in, price_out=args.price_out)
    print_summary(label, summary)

    doc = {"label": label, "model": model, "base_url": base_url,
           "cases_file": args.cases, "prompt_sha256": ocr.stage3_prompt_sha256(numbers_verified=False)
           if hasattr(ocr, "stage3_prompt_sha256") else None,
           "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "summary": summary, "rows": rows}
    out_dir = REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"bench_{label}.json"
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(out_path)
    print(f"\n  {out_path} ({out_path.stat().st_size:,}바이트)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
