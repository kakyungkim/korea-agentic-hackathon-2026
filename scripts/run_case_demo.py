#!/usr/bin/env python
"""후보 하나를 도킹에서 사람 근거까지 이은 케이스 시연 실행기.

사용
    .venv/bin/python scripts/run_case_demo.py --out eval/results
    .venv/bin/python scripts/run_case_demo.py --out eval/results --offline

산출물
    <out>/case_niraparib.json        단계별 근거와 수치와 SHA256 전부, 주장 두 벌, 크리틱 판정
    <out>/case_niraparib_brief.md    사람이 읽는 한 장 브리프

``--offline`` 은 캐시에 있는 응답만 쓰고 네트워크를 타지 않는다. 캐시가 없는 단계는 무엇이
없었는지 그대로 적고 자리표시자를 채우지 않는다. DiffDock 은 경로당 1회, ``--num-poses``
기본 3 으로 아낀다. ``NVIDIA_API_KEY`` 가 없으면 DiffDock 단계와 크리틱 3단을 건너뛴다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from harness.tools import case_runner as cr  # noqa: E402


def write_atomic(path: Path, text: str) -> None:
    """임시 파일에 쓰고 원자적으로 교체한다. 실행 중 끊겨도 기존 파일이 비지 않는다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="niraparib 두 경로 케이스 시연")
    parser.add_argument("--out", default="eval/results", help="산출물 디렉터리 (기본 eval/results)")
    parser.add_argument("--offline", action="store_true",
                        help="캐시만으로 돌린다. 네트워크와 LLM 을 부르지 않는다.")
    parser.add_argument("--no-cache", action="store_true",
                        help="응답 캐시를 쓰지 않는다. DiffDock 을 다시 부르므로 주의.")
    parser.add_argument("--num-poses", type=int, default=cr.DIFFDOCK_NUM_POSES,
                        help=f"DiffDock 포즈 수 (기본 {cr.DIFFDOCK_NUM_POSES})")
    parser.add_argument("--model", default=None,
                        help="크리틱 3단 모델. 비우면 MODEL_PLANNER 환경변수를 쓴다.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    use_cache = not args.no_cache

    print(f"[1/4] 두 경로 실행 (offline={args.offline}, cache={use_cache}, "
          f"num_poses={args.num_poses})", flush=True)
    case = cr.run_case(offline=args.offline, use_cache=use_cache, num_poses=args.num_poses)
    for path in case["paths"]:
        skipped = [name for name, step in path["steps"].items() if step.get("skipped")]
        failed = sorted(path["errors"])
        print(f"      경로 {path['path']} {path['title']}: "
              f"Vina {path['steps']['vina']['score_kcal_mol']} kcal/mol, "
              f"건너뜀 {skipped or '없음'}, 오류 {failed or '없음'}", flush=True)

    print("[2/4] 주장 두 벌 조립", flush=True)
    supported = cr.build_supported_claims(case)
    overclaim = cr.build_overclaim_claims(case)
    print(f"      (가) 주장 {len(supported['claims'])}건, "
          f"(나) 주장 {len(overclaim['claims'])}건, "
          f"심은 과잉해석 {len(overclaim['planted_overclaims'])}건", flush=True)

    print("[3/4] 크리틱 3단 판정", flush=True)
    counts = (cr.path_by_key(case, "A")["steps"]["faers"] or {}).get("counts")
    verdicts = {
        "supported": cr.judge_claim_set(supported, counts, offline=args.offline, model=args.model),
        "overclaim": cr.judge_claim_set(overclaim, counts, offline=args.offline, model=args.model),
    }
    for name, verdict in verdicts.items():
        print(f"      {name}: {verdict['final_verdict']} ({verdict['decided_by']})", flush=True)

    print("[4/4] 산출물 쓰기", flush=True)
    document = {
        **case,
        "claim_sets": {"supported": supported, "overclaim": overclaim},
        "critic_verdicts": verdicts,
        "can_say": cr.can_say(case),
        "cannot_say": cr.cannot_say(case),
        "run": {"offline": args.offline, "use_cache": use_cache, "num_poses": args.num_poses,
                "nvidia_api_key_present": bool((os.environ.get("NVIDIA_API_KEY") or "").strip()),
                "argv": sys.argv[1:]},
    }
    json_path = out_dir / "case_niraparib.json"
    brief_path = out_dir / "case_niraparib_brief.md"
    write_atomic(json_path, json.dumps(document, ensure_ascii=False, indent=1))
    write_atomic(brief_path, cr.render_brief(case, supported, overclaim, verdicts))
    print(f"      {json_path} ({json_path.stat().st_size:,}바이트)")
    print(f"      {brief_path} ({brief_path.stat().st_size:,}바이트)")

    ok = (verdicts["supported"]["final_verdict"] == "pass"
          and verdicts["overclaim"]["final_verdict"] == "reject")
    if not ok:
        print("      주의: (가) 통과와 (나) 반려가 함께 나오지 않았다. 위 판정 사유를 확인하세요.",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
