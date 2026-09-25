#!/usr/bin/env bash
# 이식 출처: AgentForgeAI(2026-08 Agent Forge AI Hackathon) 의 scripts/gate.sh
# 이식 시각: 2026-09-25
# 바꾼 것: 그대로 가져왔다. 게이트 항목 G1~G4 가 v1 CLI 기준이라 이번 저장소 기준으로 다시 정해야 한다.
# 완료 게이트 자동 실행. 기준은 docs/03-gate.md.
# 하나가 실패해도 나머지를 계속 돌린다. 마지막에 통과 개수를 보고한다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
EVIDENCE="$ROOT/docs/evidence"
mkdir -p "$EVIDENCE"

PASS=0; TOTAL=0
declare -a RESULTS

gate() {  # gate <id> <설명> <명령>
  local id="$1" desc="$2"; shift 2
  TOTAL=$((TOTAL + 1))
  printf '\n\033[1m[%s] %s\033[0m\n' "$id" "$desc"
  if "$@" > "$EVIDENCE/$id.log" 2>&1; then
    PASS=$((PASS + 1)); RESULTS+=("$id PASS  $desc")
    printf '  \033[92mPASS\033[0m  → docs/evidence/%s.log\n' "$id"
  else
    RESULTS+=("$id FAIL  $desc")
    printf '  \033[91mFAIL\033[0m  → docs/evidence/%s.log\n' "$id"
    tail -5 "$EVIDENCE/$id.log" | sed 's/^/      /'
  fi
}

cd "$ROOT/code" || exit 1
export PYTHONPATH=src

gate G1 "파이프라인 완주" $PY -m pharmasignal.cli run GLP-1 --limit 15
gate G2 "플랫폼 실호출"   $PY -m pharmasignal.cli smoke
gate G3 "회귀 테스트"     $PY -m pytest -q

# G4 보안 — 키 문자열이 소스에 없어야 통과 (grep이 못 찾으면 통과)
printf '\n\033[1m[G4] 비밀 노출 검사\033[0m\n'
TOTAL=$((TOTAL + 1))
if grep -rnE '(sk-[A-Za-z0-9]{16}|Bearer [A-Za-z0-9]{20})' src ../docs 2>/dev/null; then
  RESULTS+=("G4 FAIL  비밀 노출 검사"); printf '  \033[91mFAIL\033[0m  위 위치에 키로 보이는 문자열 있음\n'
else
  PASS=$((PASS + 1)); RESULTS+=("G4 PASS  비밀 노출 검사")
  printf '  \033[92mPASS\033[0m  소스·문서에 키 문자열 없음\n'
fi

printf '\n%s\n' "──────────────────────────────────────────────"
for r in "${RESULTS[@]}"; do printf '  %s\n' "$r"; done
printf '\n  %d/%d 게이트 통과\n\n' "$PASS" "$TOTAL"
[ "$PASS" -eq "$TOTAL" ]
