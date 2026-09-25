#!/usr/bin/env bash
# OpenShell 샌드박스 정책 스모크 테스트. 제출물의 "정책이 실제로 강제된다"는 증거를 만든다.
#   (1) 허용 도메인 접속 성공(정책마다 목록이 다르다)
#   (2) 허용 목록 밖 도메인(example.com, github.com) 차단
#   (3) 정책의 read_write 경로는 쓰기 성공, 그 밖의 경로는 쓰기 차단
#   (4) process.run_as_user 가 있으면 샌드박스 안 uid 확인
#   (5) nightshift 는 pip 로 실제 패키지를 받아 pypi.org 와 files.pythonhosted.org 를 함께 확인
#   (6) 게이트웨이 감사 로그의 DENIED 줄을 원문 그대로 발췌
#   (7) protocol: rest 엔드포인트에 파이썬 클라이언트가 인증서 검증을 통과하는지(CERT_URL)
# 기대값은 정책 파일마다 다르므로 아래 "대상 목록" 블록에서 정책별로 정한다.
# 결과는 pharmasignal 이면 eval/results/openshell_smoke.txt, 그 밖의 정책이면
# eval/results/openshell_smoke_<정책>.txt 에 남긴다. 하나라도 실패하면 종료 코드 1.
#
# ★ 확인에 쓰는 클라이언트는 정책이 허용한 바이너리여야 한다(PROBE 변수).
#   flydock 은 추론과 데이터 소스 블록에서 /usr/bin/curl 을 빼고 파이썬만 올렸으므로 curl 로
#   확인하면 허용 호스트조차 전부 거부된다. nightshift 의 pypi 블록도 python 과 pip 만 허용해
#   같은 일이 있었다. 그때의 실패는 정책이 의도대로 동작한 증거였고 스모크 쪽 결함이었다.
#
# 사용:  scripts/openshell_smoke.sh [pharmasignal|nightshift|base|flydock]   (기본 pharmasignal)
# 환경변수(선택):
#   VM_BACKEND=colima|multipass   (기본 colima. VM 안에서 직접 돌리면 로컬 openshell 을 쓴다)
#   VM_NAME=openshell             (multipass 백엔드에서만)
#   SANDBOX_NAME=<정책명>
#   OUT=<결과 파일 경로>        (기본은 위 규칙)
#
# 실측(2026-09-25, Colima + OpenShell 0.0.116): 차단은 프록시가 CONNECT 에 403 을 돌려주고
# curl 이 종료 코드 56 으로 실패한다("curl: (56) CONNECT tunnel failed, response 403").
# 쓰기 차단은 Landlock 이 걸어 "Permission denied" 와 종료 코드 2 로 나온다.

set -uo pipefail

POLICY="${1:-pharmasignal}"
case "$POLICY" in pharmasignal|nightshift|base|flydock) ;; *) echo "정책은 pharmasignal | nightshift | base | flydock" >&2; exit 2;; esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VM_BACKEND="${VM_BACKEND:-colima}"
VM_NAME="${VM_NAME:-openshell}"
SANDBOX_NAME="${SANDBOX_NAME:-$POLICY}"
OUT_DIR="$REPO_ROOT/eval/results"
# 결과 파일은 정책마다 따로 남긴다. pharmasignal 은 기존 파일명을 그대로 두어 앞선 기록을
# 덮어쓰지 않는다. OUT 환경변수로 직접 지정할 수도 있다.
case "$POLICY" in
  pharmasignal) OUT="${OUT:-$OUT_DIR/openshell_smoke.txt}" ;;
  *)            OUT="${OUT:-$OUT_DIR/openshell_smoke_$POLICY.txt}" ;;
esac
mkdir -p "$OUT_DIR"

# ---------------------------------------------------------------- 실행 위치 결정
# VM 안(또는 openshell 이 깔린 리눅스)에서 직접 돌리면 로컬 바이너리를, macOS 에서 돌리면
# 고른 VM 백엔드를 거친다.
# stdin 은 반드시 /dev/null 로 막는다. `openshell sandbox exec` 는 stdin 을 샌드박스로
# 흘려보내므로, 터미널이 아닌 곳(백그라운드 실행, CI)에서 돌리면 EOF 를 기다리며 멈춘다. 실측 확인.
if command -v openshell >/dev/null 2>&1; then
  vm() { bash -lc "$*" </dev/null; }
  WHERE="local"
elif [ "$VM_BACKEND" = colima ] && command -v colima >/dev/null 2>&1; then
  vm() { colima ssh -- bash -lc "$*" </dev/null; }
  WHERE="colima"
elif [ "$VM_BACKEND" = multipass ] && command -v multipass >/dev/null 2>&1; then
  vm() { multipass exec "$VM_NAME" -- bash -lc "$*" </dev/null; }
  WHERE="multipass:$VM_NAME"
else
  echo "openshell 도 $VM_BACKEND 도 없다" >&2; exit 2
fi

# 샌드박스 안에서 sh 명령 실행. 따옴표가 층층이 겹치지 않도록 base64 로 감싸 넘긴다.
sb() {
  local b64; b64="$(printf '%s' "$1" | base64 | tr -d '\n')"
  vm "openshell sandbox exec -n $SANDBOX_NAME --no-tty --timeout 90 -- sh -c 'echo $b64 | base64 -d | sh'" 2>&1
}

# 샌드박스 안에서 파이썬 프로그램 실행. 따옴표가 겹치지 않게 sb 와 같은 방식으로 감싼다.
# 파일로 떨어뜨리는 자리는 /tmp 다(정책의 read_write 에 있다).
sbpy() {
  local b64; b64="$(printf '%s' "$1" | base64 | tr -d '\n')"
  sb "echo $b64 | base64 -d > /tmp/openshell_probe.py && python3 /tmp/openshell_probe.py; r=\$?; rm -f /tmp/openshell_probe.py; exit \$r"
}

# 표준 라이브러리만 쓰는 GET 프로버. requests 나 httpx 를 이미지에 넣지 않았고, pypi 를
# 허용하지 않는 정책에서는 설치할 수도 없다. urllib 는 http_proxy/https_proxy 환경변수를
# 스스로 읽으므로 프록시 설정을 따로 주지 않는다.
py_probe_src() {  # py_probe_src <url>  → "http=NNN rc=N" 한 줄을 출력하는 파이썬 소스
  cat <<PY
import urllib.request, urllib.error
req = urllib.request.Request("$1", method="GET",
                             headers={"User-Agent": "openshell-smoke/1.0"})
try:
    with urllib.request.urlopen(req, timeout=25) as r:
        print("http=%d rc=0" % r.status)
except urllib.error.HTTPError as e:
    # 원본 서버나 프록시가 HTTP 상태로 답했다는 뜻이다. TLS 는 통했다.
    print("http=%d rc=0" % e.code)
except Exception as e:
    print("http=000 rc=7 err=%s %s" % (type(e).__name__, str(e)[:140]))
PY
}

# ---------------------------------------------------------------- 대상 목록
# 정책 파일마다 허용 도메인, 쓰기 경로, 프로세스 신원이 다르다. 여기서 한 번에 정한다.
#   ALLOWED_URLS  : network_policies 에 있는 호스트 (접속되어야 한다)
#   WRITE_ALLOW   : filesystem_policy.read_write 에 있는 디렉터리 (써지고 지워져야 한다)
#   WRITE_DENY    : read_only 에 있거나 아예 빠진 디렉터리 (Landlock 이 EPERM 으로 끊는다)
#   EXPECT_UID    : process.run_as_user. 정책에 없으면 빈 값(이미지 USER 를 따른다)
#   PIP_PROBE     : pip 로 실제 패키지를 받아 pypi.org 와 files.pythonhosted.org 를 함께 확인
#   PROBE         : 확인에 쓸 클라이언트(curl | python). 정책의 binaries 에 있는 것을 고른다
#   CERT_URL      : protocol: rest 엔드포인트의 파이썬 인증서 검증 확인 대상(빈 값이면 생략)
#   CURL_DENY_URL : 허용 호스트인데 curl 은 binaries 에 없어 막혀야 하는 URL(빈 값이면 생략)
#   L7_DENY_URL   : 허용 호스트인데 rules 에 없는 경로라 L7 에서 막혀야 하는 URL(빈 값이면 생략)
case "$POLICY" in
  pharmasignal)
    ALLOWED_URLS=(
      "https://api.fda.gov/drug/event.json?limit=1"
      "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?pagesize=1"
      "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?retmode=json"
      "https://integrate.api.nvidia.com/v1/models"
    )
    WRITE_ALLOW=( /work/out )
    WRITE_DENY=( /etc /sandbox )
    # 2026-09-25 에 정책에 process 블록을 넣었다(1500:1500). 이미 만들어 둔 샌드박스는 static
    # 구역이 고정돼 있어 반영되지 않으므로, 지우고 다시 만든 뒤에만 이 기대값이 맞는다.
    EXPECT_UID="1500"
    PIP_PROBE=0
    PROBE=curl
    CERT_URL=""
    CURL_DENY_URL=""
    L7_DENY_URL=""
    ;;
  nightshift)
    ALLOWED_URLS=(
      "https://pypi.org/simple/pip/"
      "https://files.pythonhosted.org/"
      "https://integrate.api.nvidia.com/v1/models"
    )
    WRITE_ALLOW=( /work/repo /work/out )
    WRITE_DENY=( /etc /sandbox )
    EXPECT_UID="1500"
    PIP_PROBE=1
    # pypi 블록의 binaries 가 python 과 pip 만 허용하므로 curl 로는 확인할 수 없다.
    PROBE=python
    CERT_URL=""
    CURL_DENY_URL=""
    L7_DENY_URL=""
    ;;
  base)
    ALLOWED_URLS=( "https://integrate.api.nvidia.com/v1/models" )
    WRITE_ALLOW=( /work/out )
    WRITE_DENY=( /etc /sandbox )
    EXPECT_UID="1500"
    PIP_PROBE=0
    PROBE=curl
    CERT_URL=""
    CURL_DENY_URL=""
    L7_DENY_URL=""
    ;;
  flydock)
    # 허용 호스트 일곱. 경로는 정책의 rules 가 허용한 것만 고른다(엉뚱한 경로를 찌르면 L7 에서
    # 403 이 오고, 그것은 정책이 아니라 스모크 쪽 실수다).
    ALLOWED_URLS=(
      "https://health.api.nvidia.com/v1/biology/mit/diffdock"
      "https://integrate.api.nvidia.com/v1/models"
      "https://files.rcsb.org/download/1CRN.pdb"
      "https://drug.flybrain.kr/data/evidence/summary.json"
      "https://api.fda.gov/drug/event.json?limit=1"
      "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?pagesize=1"
      "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?retmode=json"
    )
    WRITE_ALLOW=( /work/out )
    WRITE_DENY=( /etc /sandbox /work )
    EXPECT_UID="1500"
    PIP_PROBE=0
    # 추론과 데이터 소스 블록에서 /usr/bin/curl 을 뺐다(DLI 강좌 대조 보강 1번).
    PROBE=python
    # DiffDock POST 는 크레딧을 쓰므로 GET 으로 405 를 받는 것까지만 확인한다.
    CERT_URL="https://health.api.nvidia.com/v1/biology/mit/diffdock"
    # 파이썬이 200 을 받는 URL 을 그대로 쓴다. 호스트가 아니라 바이너리 때문에 막힌다.
    CURL_DENY_URL="https://integrate.api.nvidia.com/v1/models"
    # 허용 호스트, 허용 바이너리인데 rules 에 없는 경로다. L7 에서 403 이 와야 한다.
    L7_DENY_URL="https://api.fda.gov/drug/label.json?limit=1"
    ;;
esac
BLOCKED_URLS=( "https://example.com/" "https://github.com/" )

PASS=0; FAIL=0
{
  echo "# OpenShell smoke test"
  echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "policy: $POLICY.yaml   sandbox: $SANDBOX_NAME   via: $WHERE"
  echo "openshell: $(vm 'openshell --version' 2>/dev/null | tr -d '\r')"
  echo
} > "$OUT"

record() {  # record <PASS|FAIL> <이름> <상세>
  printf '%-4s %-34s %s\n' "$1" "$2" "$3" | tee -a "$OUT"
  if [ "$1" = PASS ]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi
}

probe_url() {  # probe_url <url>  → "http=NNN rc=N" 한 줄
  case "${PROBE:-curl}" in
    python)
      sbpy "$(py_probe_src "$1")" | tr -d '\r' | tr '\n' ' ' | sed 's/  */ /g' ;;
    *)
      sb "curl -sS --max-time 25 -o /dev/null -w \"http=%{http_code}\" \"$1\" 2>&1; echo \" rc=\$?\"" | tr -d '\r' | tr '\n' ' ' | sed 's/  */ /g' ;;
  esac
}

# ---------------------------------------------------------------- 1. 허용 도메인
echo "## 허용 도메인 (클라이언트: $PROBE)" | tee -a "$OUT"
for u in "${ALLOWED_URLS[@]}"; do
  host="$(echo "$u" | cut -d/ -f3)"
  out="$(probe_url "$u")"
  # http=000 은 프록시가 CONNECT 를 막았다는 뜻이다. 2xx, 401(키 없음), 404(경로 없음),
  # 405(POST 전용 경로에 GET)는 모두 원본 서버가 응답했다는 증거라 "허용"으로 본다.
  # 403 은 제외한다. L7 거부(policy_denied)가 바로 그 코드로 온다.
  if echo "$out" | grep -q 'rc=0' && echo "$out" | grep -qE 'http=(2[0-9][0-9]|401|404|405)'; then
    record PASS "allowed $host" "$out"
  else
    record FAIL "allowed $host" "$out (정책 binaries 에 이 클라이언트가 있는지, 호스트와 경로가 endpoints 의 rules 에 있는지 확인)"
  fi
done

# ---------------------------------------------------------------- 2. 허용 목록 밖 차단
echo | tee -a "$OUT"; echo "## 허용 목록 밖(차단되어야 함)" | tee -a "$OUT"
for u in "${BLOCKED_URLS[@]}"; do
  host="$(echo "$u" | cut -d/ -f3)"
  out="$(probe_url "$u")"
  # 프록시가 CONNECT 에 403 을 돌려주면 curl 은 56 으로 끝나고 파이썬은 예외를 던진다(rc=7).
  if echo "$out" | grep -qE 'rc=(56|7|35|22)' || echo "$out" | grep -qi 'tunnel failed\|tunnel connection failed\|policy_denied\|http=403'; then
    record PASS "blocked $host" "$out"
  else
    record FAIL "blocked $host" "차단되지 않았다: $out"
  fi
done

# ---------------------------------------------------------------- 2b. 정책에서 뺀 바이너리
# 같은 호스트라도 어느 실행 파일이 접속하는지 커널이 본다. 파이썬이 200 을 받은 그 URL 을
# curl 로 다시 찔러 거부되는지 확인한다. DLI 강좌 대조 보강 1번이 실제로 걸리는지 보는 자리다.
if [ -n "${CURL_DENY_URL:-}" ]; then
  echo | tee -a "$OUT"; echo "## 허용 호스트, 정책에 없는 바이너리(curl)" | tee -a "$OUT"
  host="$(echo "$CURL_DENY_URL" | cut -d/ -f3)"
  out="$(sb "curl -sS --max-time 25 -o /dev/null -w \"http=%{http_code}\" \"$CURL_DENY_URL\" 2>&1; echo \" rc=\$?\"" | tr -d '\r' | tr '\n' ' ' | sed 's/  */ /g')"
  if echo "$out" | grep -qE 'rc=(56|7|35|22)' || echo "$out" | grep -qi 'tunnel failed\|policy_denied\|http=403'; then
    record PASS "curl denied $host" "$out"
  else
    record FAIL "curl denied $host" "curl 이 허용 호스트에 닿았다(정책 binaries 에 curl 이 남아 있는지 확인): $out"
  fi
fi

# ---------------------------------------------------------------- 2c. rules 에 없는 경로
# access 를 rules 로 바꾼 효과를 확인하는 자리다(DLI 강좌 대조 보강 3번). 호스트도 바이너리도
# 허용된 요청인데 경로가 rules 에 없으면 프록시가 L7 에서 끊고 policy_denied 를 돌려준다.
if [ -n "${L7_DENY_URL:-}" ]; then
  echo | tee -a "$OUT"; echo "## 허용 호스트, rules 에 없는 경로 (L7 거부)" | tee -a "$OUT"
  target="$(echo "$L7_DENY_URL" | cut -d/ -f3-)"
  out="$(probe_url "$L7_DENY_URL")"
  if echo "$out" | grep -qE 'http=403' || echo "$out" | grep -qi 'policy_denied'; then
    record PASS "l7 denied ${target%%\?*}" "$out"
  else
    record FAIL "l7 denied ${target%%\?*}" "경로 제한이 걸리지 않았다: $out"
  fi
fi

# ---------------------------------------------------------------- 3. 쓰기 제한
echo | tee -a "$OUT"; echo "## 파일시스템 쓰기" | tee -a "$OUT"
for d in "${WRITE_DENY[@]}"; do
  out="$(sb "echo probe > $d/openshell_smoke_probe 2>&1; echo \"rc=\$?\"" | tr '\n' ' ' | sed 's/  */ /g')"
  if echo "$out" | grep -qE 'rc=[1-9]'; then
    record PASS "denied write $d" "$out"
  else
    record FAIL "denied write $d" "쓰기가 성공했다(read_write 에 들어갔거나 Landlock 미적용): $out"
    sb "rm -f $d/openshell_smoke_probe" >/dev/null 2>&1
  fi
done

for d in "${WRITE_ALLOW[@]}"; do
  out="$(sb "echo probe > $d/openshell_smoke_probe 2>&1 && cat $d/openshell_smoke_probe && rm -f $d/openshell_smoke_probe; echo \"rc=\$?\"" | tr '\n' ' ' | sed 's/  */ /g')"
  if echo "$out" | grep -q 'rc=0'; then
    record PASS "allowed write $d" "$out"
  else
    record FAIL "allowed write $d" "$out (이미지에 $d 가 있고 소유자가 샌드박스 사용자인지 확인)"
  fi
done

# ---------------------------------------------------------------- 3b. 프로세스 신원
# process.run_as_user 가 정책에 있으면 샌드박스 안의 uid 가 그 값이어야 한다.
echo | tee -a "$OUT"; echo "## 프로세스 신원 (process.run_as_user)" | tee -a "$OUT"
idout="$(sb 'id' | tr '\n' ' ' | sed 's/  */ /g')"
if [ -n "$EXPECT_UID" ]; then
  if echo "$idout" | grep -q "uid=$EXPECT_UID("; then
    record PASS "run_as_user=$EXPECT_UID" "$idout"
  else
    record FAIL "run_as_user=$EXPECT_UID" "기대한 uid 가 아니다: $idout"
  fi
else
  printf '%-4s %-34s %s\n' "INFO" "run_as_user 미지정" "$idout" | tee -a "$OUT"
fi

# ---------------------------------------------------------------- 3c. pip 실제 설치 (선택)
# pypi.org 와 files.pythonhosted.org 두 호스트를 한 번에 쓰는 실제 작업이다.
# HOME 이 쓰기 불가라 --no-cache-dir 를 반드시 준다.
if [ "$PIP_PROBE" = 1 ]; then
  echo | tee -a "$OUT"; echo "## pip 다운로드 (pypi.org + files.pythonhosted.org)" | tee -a "$OUT"
  out="$(sb 'rm -rf /tmp/pipdl; pip3 download --no-deps --no-cache-dir --dest /tmp/pipdl six 2>&1 | tail -3; echo "rc=$?"; ls /tmp/pipdl 2>/dev/null' | tr '\n' ' ' | sed 's/  */ /g')"
  if echo "$out" | grep -q 'six.*\.whl'; then
    record PASS "pip download six" "$out"
  else
    record FAIL "pip download six" "$out"
  fi
  sb 'rm -rf /tmp/pipdl' >/dev/null 2>&1
fi

# ---------------------------------------------------------------- 3d. 파이썬 인증서 검증
# protocol: rest 엔드포인트는 프록시가 TLS 를 종단한다. 그래서 샌드박스 안의 클라이언트는
# 원본 서버 인증서가 아니라 프록시 인증서를 검증한다. 우리 도구가 전부 파이썬이라 파이썬이
# 이 검증을 통과해야 샌드박스 안에서 파이프라인을 돌릴 수 있다.
#
# 실측(2026-09-25): OpenShell 은 자기 CA 를 /etc/openshell-tls/ca-bundle.pem 에 넣고
# SSL_CERT_FILE, REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE, GIT_SSL_CAINFO, NODE_EXTRA_CA_CERTS 를
# 그 경로로 설정해 둔다. 그래서 세 가지를 나눠 확인한다.
#   default_ctx  : ssl.create_default_context(). SSL_CERT_FILE 을 읽으므로 통한다.
#                  우리 도구가 쓰는 urllib.request.urlopen 경로와 같다. 이것이 합격 기준이다.
#   openshell_ca : 번들 경로를 직접 지정. 경로가 유효한지 확인한다. 합격 기준에 포함한다.
#   certifi_ca   : certifi 번들을 강제 지정. httpx 의 기본값이 이쪽이라 실패가 예상되며,
#                  실패해도 정책이나 환경의 결함이 아니라 클라이언트 설정 문제다. 기록만 한다.
if [ -n "${CERT_URL:-}" ]; then
  echo | tee -a "$OUT"; echo "## 파이썬 인증서 검증 ($CERT_URL)" | tee -a "$OUT"
  printf '%-4s %-34s %s\n' "INFO" "프록시 환경변수" \
    "$(sb 'printenv | grep -i proxy | sort | tr "\n" " "' | tr '\n' ' ')" | tee -a "$OUT"
  certsrc="$(cat <<PY
import ssl, sys, urllib.request, urllib.error
URL = "$CERT_URL"
def probe(ctx, label):
    req = urllib.request.Request(URL, method="GET",
                                 headers={"User-Agent": "openshell-smoke/1.0"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    try:
        with opener.open(req, timeout=25) as r:
            print("%s http=%d rc=0" % (label, r.status))
    except urllib.error.HTTPError as e:
        print("%s http=%d rc=0" % (label, e.code))
    except Exception as e:
        print("%s http=000 rc=7 err=%s %s" % (label, type(e).__name__, str(e)[:140]))
import os
print("python=%s %s" % (sys.version.split()[0], ssl.OPENSSL_VERSION))
print("env_SSL_CERT_FILE=%s" % os.environ.get("SSL_CERT_FILE"))
print("env_REQUESTS_CA_BUNDLE=%s" % os.environ.get("REQUESTS_CA_BUNDLE"))
dvp = ssl.get_default_verify_paths()
print("default_verify cafile=%s capath=%s" % (dvp.cafile, dvp.capath))
probe(ssl.create_default_context(), "default_ctx")
bundle = os.environ.get("SSL_CERT_FILE") or "/etc/openshell-tls/ca-bundle.pem"
if os.path.exists(bundle):
    print("openshell_bundle=%s size=%d" % (bundle, os.path.getsize(bundle)))
    probe(ssl.create_default_context(cafile=bundle), "openshell_ca")
else:
    print("openshell_ca absent path=%s" % bundle)
where = None
for mod in ("certifi", "pip._vendor.certifi"):
    try:
        m = __import__(mod, fromlist=["where"])
        w = m.where()
        if w and w != bundle:
            where = w
            print("certifi_from=%s path=%s" % (mod, w))
            break
    except Exception:
        pass
if where:
    probe(ssl.create_default_context(cafile=where), "certifi_ca")
else:
    print("certifi_ca skipped (certifi 번들이 없거나 OpenShell 번들과 같은 경로다)")
PY
)"
  certout="$(sbpy "$certsrc" | tr -d '\r')"
  printf '%s\n' "$certout" | sed 's/^/     /' | tee -a "$OUT"
  # 405 는 POST 전용 경로에 GET 을 보냈다는 뜻이고, TLS 와 라우팅이 통했다는 증거다.
  for label in default_ctx openshell_ca; do
    line="$(printf '%s\n' "$certout" | grep "^$label" | head -1)"
    if [ -z "$line" ]; then
      record FAIL "python TLS ($label)" "확인 결과 줄이 없다"
    elif printf '%s' "$line" | grep -qE 'http=(2[0-9][0-9]|401|404|405)'; then
      record PASS "python TLS ($label)" "$line"
    else
      record FAIL "python TLS ($label)" "$line"
    fi
  done
  # certifi 강제 지정은 합격 기준이 아니다. httpx 처럼 번들을 못 박는 클라이언트를 쓸 때
  # verify 인자나 SSL_CERT_FILE 을 OpenShell 번들로 맞춰야 한다는 기록으로 남긴다.
  certline="$(printf '%s\n' "$certout" | grep '^certifi_ca' | head -1)"
  printf '%-4s %-34s %s\n' "INFO" "python TLS (certifi 강제)" "${certline:-확인 못 함}" | tee -a "$OUT"
fi

# ---------------------------------------------------------------- 4. 감사 로그 + 유효 정책
{
  echo
  echo "## 차단 로그 원문 (openshell logs $SANDBOX_NAME --since 15m, DENIED/BLOCKED 만)"
  vm "openshell logs $SANDBOX_NAME --since 15m -n 500" 2>/dev/null \
    | grep -aiE 'DENIED|BLOCKED' | tail -40 || echo "(로그 없음 또는 logs 명령 실패)"
  echo
  echo "## Landlock 적용 기록 (파일시스템 거부는 커널이 EPERM 으로 끊어 로그에 DENIED 가 남지 않는다)"
  vm "openshell logs $SANDBOX_NAME --since 15m -n 500 --level debug" 2>/dev/null \
    | grep -aE 'Landlock' | tail -4 || echo "(Landlock 로그 없음)"
  echo
  echo "## 유효 정책 (openshell policy get $SANDBOX_NAME --full)"
  vm "openshell policy get $SANDBOX_NAME --full" 2>/dev/null | head -120 || echo "(policy get 실패)"
  echo
  echo "summary: pass=$PASS fail=$FAIL"
} >> "$OUT"

echo
echo "결과 파일: $OUT   (pass=$PASS fail=$FAIL)"
[ "$FAIL" -eq 0 ]
