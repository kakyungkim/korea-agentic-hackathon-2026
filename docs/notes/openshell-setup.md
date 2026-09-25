# OpenShell 실행 환경 안내 (Intel Mac + Multipass Ubuntu 24.04 VM)

작성 2026-09-24, 실행 기록 추가 2026-09-25. 담당 경로 `policies/`, `scripts/openshell_*.sh`. 처음 작성할 때는 Multipass가 없어 `bash -n` 문법 검사까지만 했으나, 2026-09-25에 Colima VM에서 설치부터 정책 적용과 스모크 테스트까지 실제로 돌렸다. 실행으로 확인한 내용과 문서와 달랐던 자리는 아래 "실행 기록(Colima)" 절에 있고, 그 앞 절들은 Multipass 기준으로 쓴 처음 설계를 그대로 둔 것이다. 아래 수치 중 소요 시간과 리소스는 추정이며 그렇게 표시했다. 확인하지 못한 항목은 [unverified]로 적었다.

## 결론 요약

| 질문 | 판단 | 근거 |
|---|---|---|
| Intel Mac(macOS 14)에 OpenShell을 직접 설치 | **불가** | 지원 매트릭스의 macOS 항목은 Apple Silicon만이고, 설치 스크립트가 `x86_64` macOS에서 "Intel macOS is not supported because no x86_64-apple-darwin release assets are published"로 종료한다 |
| Multipass Ubuntu 24.04 VM 안에서 OpenShell 실행 | **조건부 가능** | Linux x86_64(Debian/Ubuntu) deb 패키지는 정식 지원. Ubuntu 24.04 커널 6.8이 Landlock ABI 3(6.2+) 요건을 충족한다. 다만 VM 커널의 Landlock LSM 활성 여부와 seccomp 프로브 통과는 첫 실행에서 확인해야 한다 [unverified]. Docker 28 이상이 필요하므로 VM에 Docker 공식 apt 저장소로 새로 설치한다 |
| GPU 없이 동작 | **가능** | OpenShell의 GPU 패스스루는 선택 기능(experimental). 추론은 전부 `integrate.api.nvidia.com`로 나간다 |
| NemoClaw를 이 환경에서 사용 | **권장하지 않음** | 검증 플랫폼이 DGX Spark/Station, Ubuntu 24.04 Linux, macOS Apple Silicon(제한), WSL2(제한)이고 RAM 최소 8GB, 권장 16GB, 디스크 20~40GB를 요구한다. 6GB VM에서는 빠듯하고, NemoClaw는 OpenClaw 등 "지원 에이전트"를 표준 구성으로 돌리는 참조 스택이라 우리처럼 NAT 워크플로를 직접 넣는 경우에는 OpenShell 단독이 맞다(NemoClaw 문서 자체가 "커스텀 이미지나 참조 스택 밖 워크로드면 OpenShell 단독"이라고 안내한다) |

## 환경 전제

- 호스트: Intel Mac(i5, 16GB), macOS 14, Docker 27 설치됨(호스트 Docker는 쓰지 않는다), GPU 없음.
- Multipass는 macOS 14 Sonoma 이상에서 Intel과 M 시리즈 모두 지원하고, 기본 백엔드는 QEMU(Apple Hypervisor.framework 위)다. HyperKit은 더 이상 기본이 아니다.
- OpenShell은 VM 안에서 Docker 컨테이너를 샌드박스로 쓴다(Docker compute driver). 중첩 가상화(KVM)는 필요 없다. MicroVM 드라이버는 쓰지 않는다.
- 최신 안정 릴리스는 `v0.0.116`(2026-08-28, GitHub Releases API 기준). README는 0.1.0 업그레이드 안내를 싣고 있어 설치 스크립트가 받는 "latest"가 달라질 수 있다. 설치 후 `openshell --version`으로 기록한다.

## 설치 절차

스크립트 한 번으로 8단계를 순서대로 진행한다. 각 단계는 이미 끝났으면 건너뛰고, 실패하면 그 자리에서 멈춘다.

```bash
# 0. (사용자가 직접) Multipass 설치
brew install --cask multipass

# 1. VM 생성부터 정책 적용까지 (기본 정책 pharmasignal)
scripts/openshell_vm_up.sh pharmasignal      # 또는 nightshift, base

# 2. 스모크 테스트 → eval/results/openshell_smoke.txt
scripts/openshell_smoke.sh pharmasignal
```

스크립트가 VM 안에서 실행하는 내용은 다음과 같다.

| 단계 | 내용 | idempotent 처리 |
|---|---|---|
| 1 | `multipass launch 24.04 --name openshell --cpus 2 --memory 6G --disk 30G` | `multipass info`로 존재 확인, 멈춰 있으면 start |
| 2 | 커널 점검: `uname -r`가 6.2 이상, `/sys/kernel/security/lsm`에 `landlock`, `/boot/config-*`에 `SECCOMP_FILTER`, `NET_NS`, `USER_NS` | 매번 실행(빠름) |
| 3 | Docker 공식 apt 저장소로 `docker-ce` 설치, `ubuntu`를 docker 그룹에 추가, `loginctl enable-linger`, 서버 버전 28 이상 확인 | `command -v docker` |
| 4 | `curl -LsSf .../install.sh \| sh` (deb 설치 + `systemctl --user` 서비스 `openshell-gateway` 기동 + 로컬 게이트웨이 `https://127.0.0.1:17670` 등록) | `command -v openshell` |
| 5 | `policies/`, `scripts/`를 tar 파이프로 `~/hackathon`에 복사, `docker build -t hackathon-sandbox:latest policies/sandbox-image` | `docker image inspect` |
| 6 | `openshell provider profile lint/import -f policies/nvidia-provider-profile.yaml`, `.env`의 `NVIDIA_API_KEY`가 있으면 `openshell provider create --name nvidia --type nvidia-hackathon --from-existing` | `profile export`, `provider list` |
| 7 | `openshell sandbox create --name <정책명> --from hackathon-sandbox:latest --policy policies/<정책>.yaml --cpu 2 --memory 3Gi [--provider nvidia] --detach -- sleep infinity` | `sandbox list` |
| 8 | `openshell policy set <정책명> --policy policies/<정책>.yaml --wait`, `openshell policy get <정책명> --full` | 매번 실행(전체 치환) |

키가 없으면 6단계는 건너뛰고 샌드박스를 `--no-auto-providers`로 만든다. 키를 `.env`에 넣고 다시 실행하면 provider가 만들어지지만, 이미 만든 샌드박스에는 `openshell sandbox provider attach <정책명> nvidia`로 따로 붙여야 한다(스크립트는 새로 만드는 경우만 처리한다).

### 게이트웨이가 사용자 서비스라는 점

deb 패키지는 게이트웨이를 `systemd --user` 서비스로 띄우고 Docker 소켓을 사용자 권한으로 연다. 그래서 (1) `ubuntu`가 docker 그룹에 있어야 하고, (2) 로그인 세션 없이도 사용자 매니저가 살아 있도록 `loginctl enable-linger`가 필요하다. 그룹을 바꾼 뒤에는 이미 떠 있던 사용자 매니저가 새 그룹을 모르므로 스크립트가 `systemctl restart user@1000.service`를 한 번 실행한다. 그래도 `docker version`이 권한 오류를 내면 `multipass restart openshell` 후 스크립트를 다시 돌린다.

## 예상 소요 시간 (추정)

각 단계의 다운로드 용량과 일반적인 Intel Mac QEMU 속도를 근거로 한 추정이며 실측값은 없다. 첫 실행 기준이며 재실행은 8단계만 돌아 1분 안쪽이다.

| 단계 | 추정 |
|---|---|
| Multipass 설치(brew cask) | 3~5분 |
| Ubuntu 24.04 이미지 다운로드와 VM 첫 부팅 | 5~10분(이미지 약 600MB급, 회선에 좌우) |
| Docker 설치 | 2~4분 |
| OpenShell deb 설치와 게이트웨이 기동 | 2~3분 |
| 샌드박스 이미지 빌드(ubuntu:24.04 + python3, git, curl) | 3~6분(QEMU x86 에뮬레이션이 아닌 HVF 가속이라 네이티브의 절반 안쪽 속도로 예상) |
| 샌드박스 생성(런타임 이미지 pull 포함)과 정책 적용 | 2~5분 |
| 합계 | 약 20~35분. 한 단계라도 막히면(커널 프로브 실패 등) 트러블슈팅 시간이 별도로 든다 |

## VM 리소스 권장

호스트 16GB 기준. macOS 자체와 브라우저, 에디터가 6~8GB를 쓴다고 보고 VM에 4~6GB를 배정한다.

| 항목 | 기본값(스크립트) | 비고 |
|---|---|---|
| vCPU | 2 | `VM_CPUS`로 변경. i5 4코어면 2가 안전 |
| 메모리 | 6G | `VM_MEM`. 게이트웨이 + Docker + 샌드박스 1개면 4G에서도 도나 pip 설치가 겹치면 여유가 없다. Night Shift 데모처럼 테스트와 벤치마크를 돌릴 때는 6G |
| 디스크 | 30G | `VM_DISK`. 런타임 이미지, 샌드박스 이미지, pip 캐시를 합쳐 10GB 안쪽으로 예상하지만 Multipass 디스크는 나중에 키우기 번거로워 넉넉히 잡는다 |
| 샌드박스 자체 제한 | `--cpu 2 --memory 3Gi` | `openshell sandbox create` 플래그로 건다(정책 파일에는 해당 키가 없다). Docker 드라이버가 런타임 제한으로 적용한다 |

## 정책 문법 요약

정책은 YAML 한 파일이고 최상위 키는 여섯 개다. 출처는 `docs/reference/policy-schema.mdx`(OpenShell 저장소)이며, 아래 표에 없는 키는 스키마에 없으므로 쓰면 로드 단계에서 거부된다.

| 키 | 구역 | 뜻 |
|---|---|---|
| `version` | 필수 | 현재 `1`만 허용 |
| `filesystem_policy` | static | `include_workdir`(작업 디렉터리를 read_write에 자동 추가), `read_only[]`, `read_write[]`. 목록에 없는 경로는 접근 불가. 절대경로, `..` 금지, `/` 단독 읽기쓰기 금지, 합계 256개 이하 |
| `landlock` | static | `compatibility: best_effort`(없는 경로는 건너뜀) 또는 `hard_requirement`(하나라도 못 열면 시작 실패) |
| `process` | static | `run_as_user`, `run_as_group`. `"sandbox"` 또는 1~4294967294의 숫자. 0(root) 거부 |
| `network_policies` | dynamic | 이름 → `{name, endpoints[], binaries[]}`. 나열된 실행 파일만 나열된 목적지에 접속 |
| `network_middlewares` | dynamic | 호스트별 미들웨어(토큰 마스킹 등). 이번 프로젝트에서는 쓰지 않는다 |

static 구역은 샌드박스 생성 시 고정되어 바꾸려면 삭제 후 재생성해야 하고, dynamic 구역은 `openshell policy set`(전체 치환)이나 `openshell policy update`(network_policies 증분 병합)로 실행 중 교체된다.

`endpoints[]` 항목에서 이번에 쓰는 필드는 다음과 같다.

| 필드 | 값 | 설명 |
|---|---|---|
| `host` | 호스트명 | 정확한 이름 권장. 와일드카드는 첫 라벨에만(`*.example.com`) |
| `port` | 정수 | 필수 |
| `protocol` | 생략, `rest`, `tcp`, `websocket`, `graphql`, `mcp`, `json-rpc` | 생략하면 프록시를 통한 L4 통과(호스트와 포트만 검사). `rest`면 TLS를 종단해 메서드와 경로를 검사하고 L7 로그가 남는다. `tcp`는 프록시 설정 없는 네이티브 TCP 클라이언트용 |
| `enforcement` | `enforce`, `audit` | `audit`는 기록만 하고 통과. 정책을 만들어 가는 단계에 유용 |
| `access` | `read-only`, `read-write`, `full` | `read-only`는 GET/HEAD/OPTIONS, `read-write`는 POST/PUT/PATCH 추가, `full`은 전부. `rules`와 동시 사용 불가 |
| `rules[]` | `{allow: {method, path, query}}` | 메서드와 경로 글롭으로 세밀 허용. `deny_rules[]`는 allow보다 우선 |

`binaries[]`는 `{path: /usr/bin/curl}` 형태이고 글롭(`/sandbox/.venv/**`)을 받는다. 이미지의 실제 경로와 다르면 정책이 있어도 전부 거부된다. Ubuntu 24.04에서 `python3`는 `/usr/bin/python3.12`로 해석되므로 두 경로를 모두 적었다.

정책에 없는 것: CPU, 메모리, 실행 시간, 프로세스 수 제한. CPU와 메모리는 `openshell sandbox create --cpu 2 --memory 4Gi`, 시간은 `openshell sandbox exec -n <name> --timeout 3600 -- <cmd>`로 건다. pids 제한은 게이트웨이 설정(`gateway.toml`)의 드라이버 항목에 `sandbox_pids_limit`이 보이지만 Docker 드라이버에서의 동작은 확인하지 않았다 [unverified].

### 세 정책의 차이

| 파일 | 쓰기 경로 | 허용 호스트 | 비고 |
|---|---|---|---|
| `base.yaml` | `/work/out`, `/tmp`, `/dev/null` | `integrate.api.nvidia.com:443` (rest, read-write, enforce) | `include_workdir: false`로 `/sandbox`는 읽기 전용 |
| `pharmasignal.yaml` | base와 같음 | base + `api.fda.gov`, `dailymed.nlm.nih.gov`, `eutils.ncbi.nlm.nih.gov` (모두 rest, read-only, enforce) | POST 시도는 L7에서 403 |
| `nightshift.yaml` | base + `/work/repo` | base + `pypi.org`, `files.pythonhosted.org` (L4 통과) | `github.com` 의도적 미허용, `process` 1500:1500 고정 |

추론 자격증명은 provider profile(`policies/nvidia-provider-profile.yaml`)이 맡고, 정책 파일에는 키가 들어가지 않는다. 프록시가 `integrate.api.nvidia.com`로 가는 요청에만 진짜 키를 넣고 샌드박스 환경변수에는 자리표시자만 들어간다. OpenShell 문서에서 "inference routing"은 이 provider 구조를 뜻하며, 모델을 고르거나 base URL을 바꾸는 별도 라우팅 키는 없다.

## 차단 로그 확인 방법

거부 이벤트는 세 곳에서 볼 수 있다. 모두 OpenShell 저장소 `docs/observability/accessing-logs.mdx`와 `examples/sandbox-policy-quickstart/README.md`에 나오는 방식이다.

```bash
# (VM 안) 게이트웨이가 모아 둔 최근 로그. 실시간은 --tail
openshell logs pharmasignal --since 10m
openshell logs pharmasignal --level warn --since 10m     # L7 거부만
openshell logs pharmasignal --tail --source sandbox

# (VM 안) 샌드박스 파일시스템의 전체 기록(gRPC로 유실될 수 있는 이벤트까지 남는다. 일 단위 회전, 3개 보관)
openshell sandbox exec -n pharmasignal -- sh -c 'grep -h "DENIED\|BLOCKED" /var/log/openshell.*.log'

# (VM 안) 실시간 대시보드
openshell term
```

로그 한 줄의 모양은 다음과 같다. 목적지, 호스트, 실행 파일, 사유가 함께 남아 README와 데모의 "정책 감사 요약"에 그대로 쓸 수 있다.

```
[ocsf] NET:OPEN [MED] DENIED /usr/bin/curl(64) -> example.com:443 [policy:- engine:opa]
l7_decision=deny dst_host=api.fda.gov l7_action=POST l7_target=/drug/event.json l7_deny_reason="POST /drug/event.json not permitted by policy"
```

거부 사유 문구는 `no matching policy`(허용 규칙 없음), `l7 deny`(메서드나 경로 위반), `resolves to always-blocked address`(루프백 등), `DNS resolution failed` 등이다. 샌드박스 안에서 curl은 `curl: (56) Received HTTP code 403 from proxy after CONNECT`로 실패하고, L7 거부는 `{"error":"policy_denied", ...}` JSON 본문을 받는다. `scripts/openshell_smoke.sh`가 이 로그 발췌를 `eval/results/openshell_smoke.txt` 끝에 붙인다.

## 실행 기록(Colima)

2026-09-25 실측 기록. Intel Mac에서 Multipass가 VM을 만들지 못해(qemu-img 세그멘테이션 오류,
`docs/TROUBLESHOOTING.md` 3번) Colima로 바꿔 설치부터 정책 적용과 스모크 테스트까지 끝냈다.
아래 수치는 모두 이 세션에서 실행한 명령의 출력이다. 앞 절들의 Multipass 기준 설명은 그대로 두고,
달랐던 자리만 여기에 적는다.

스크립트는 `VM_BACKEND=colima|multipass`로 백엔드를 고르도록 고쳤고 기본값은 colima다. VM 안에서
명령을 돌리는 함수 하나(`vm()`)만 백엔드마다 다르고 2단계부터 8단계까지는 공유한다. Colima는 VM이
이미 떠 있어야 하므로 1단계는 생성 대신 `colima status` 확인으로 바뀌었고, 꺼져 있으면 실행 방법을
안내하고 멈춘다.

### 실행 환경 (실측)

| 항목 | 값 |
|---|---|
| VM | Colima, macOS Virtualization.Framework, x86_64, runtime docker, mountType virtiofs |
| OS | Ubuntu 24.04.4 LTS, 커널 `6.8.0-117-generic`, glibc 2.39 |
| LSM | `lockdown,capability,landlock,yama,apparmor` (landlock 활성) |
| 커널 설정 | `CONFIG_SECURITY_LANDLOCK/SECCOMP/SECCOMP_FILTER/NET_NS/USER_NS` 다섯 개 모두 `=y` |
| Docker | 클라이언트와 서버 모두 29.5.2 |
| 메모리 | 총 4.8Gi, 가용 4.4Gi. 디스크는 루트 19G, `/var/lib/docker` 30G |
| VM 사용자 | uid 501, 홈 `/home/kkkim.guest`, docker 그룹(gid 991) 소속, 암호 없는 sudo |
| OpenShell | `0.0.116` (deb `openshell_0.0.116-1_amd64.deb`, 60.6MB). snap이 없어 deb 경로로 설치 |

### 단계별 결과

| 단계 | 결과 | 비고 |
|---|---|---|
| 1. OpenShell 설치 | 성공(수정 뒤) | 패키지 설치는 한 번에 됐으나 게이트웨이 기동에서 두 번 막혔다. 아래 "문서와 달랐던 점" 1번과 2번 |
| 2. 샌드박스 이미지 빌드 | 성공 | `hackathon-sandbox:latest`. Dockerfile 수정 없음 |
| 3. provider profile import와 provider 생성 | 성공 | 키는 stdin으로 넘기고 `--credential NVIDIA_API_KEY`로 환경변수 이름만 지정했다. 명령줄과 로그에 값이 남지 않는다 |
| 4. 샌드박스 생성과 정책 적용 | 성공 | `--cpu 2 --memory 3Gi --provider nvidia --detach -- sleep infinity`, 이어서 `policy set --wait` |
| 5. `policy get --full` | 성공 | version 1, Status `Effective`, Source `sandbox`, 정책 파일 내용 그대로 |

스크립트를 고친 뒤 `scripts/openshell_vm_up.sh pharmasignal`을 종료 코드 0으로 두 번 돌렸다. 두
번째는 샌드박스를 지우고 돌려 7단계 생성 경로까지 확인했다.

### 문서와 달랐던 점

1. **게이트웨이가 compute driver를 스스로 찾지 못한다.** 설치 직후
   `configuration error: no compute driver configured and auto-detection found no suitable installed driver`로
   죽는다. 자동 탐지 순서는 Kubernetes, Podman, Docker인데 Colima VM에서는 어느 것도 잡히지 않았다.
   `~/.config/openshell/gateway.env`에 `OPENSHELL_DRIVERS=docker`를 써서 못 박는다. 이 파일은 서비스
   유닛이 `EnvironmentFile=-%E/openshell/gateway.env`로 읽는다. 설치 스크립트가 기동까지 맡으므로
   설치 전에 미리 써 두어야 한 번에 끝난다.
2. **사용자 systemd 매니저가 docker 그룹을 모른다.** driver를 지정한 뒤에도
   `failed to query Docker daemon version: Error in the hyper legacy client: client error (Connect)`로
   죽었다. 셸의 `id -G`에는 docker gid 991이 있는데 매니저 프로세스의 `/proc/<pid>/status`에는
   `Groups: 999 1000`뿐이었다. 부팅 순서 때문에 그룹이 붙기 전에 매니저가 떴다.
   `sudo systemctl restart user@$(id -u).service`로 다시 띄우면 `Groups: 991 999 1000`이 되고
   게이트웨이가 바로 올라온다. 스크립트에 3b 단계로 넣어 매번 점검한다.
3. **게이트웨이 등록이 남는다.** 설치 스크립트가 2번 때문에 중간에 죽으면 CLI에 게이트웨이가
   등록되지 않는다. `openshell gateway add https://127.0.0.1:17670 --local --name openshell`로
   따로 붙이면 `openshell status`가 Connected, Authenticated(mTLS)로 바뀐다.
4. **`provider profile lint`는 이미 import된 id를 오류로 잡는다.**
   `field=id custom provider profile 'nvidia-hackathon' already exists`로 종료 코드 1이다. 그래서
   스크립트를 다시 돌리면 6단계에서 멈췄다. `openshell provider list-profiles`로 존재를 먼저 확인하고,
   없을 때만 lint와 import를 하도록 순서를 바꿨다.
5. **`openshell sandbox exec`에 `--no-login-shell` 플래그가 없다.** 옛 스모크 스크립트가 쓰던
   플래그다. 실제 플래그는 `-n/--name`, `--workdir`, `--timeout`, `--tty/--no-tty`, `--env`이므로
   `--no-tty`로 바꿨다.
6. **`sandbox exec`는 stdin을 샌드박스로 그대로 흘린다.** 터미널이 아닌 곳에서 돌리면 EOF를 기다리며
   멈춘다. 백그라운드로 돌린 스모크 테스트가 첫 요청에서 10분 넘게 걸려 있었다. 스모크 스크립트의
   `vm()`에 `</dev/null`을 붙여 막았다.
7. **목록과 삭제 명령의 모양.** `openshell sandbox list --names`가 이름만 한 줄씩 출력하므로 JSON을
   grep할 필요가 없다. 삭제는 `openshell sandbox delete <NAME>`이고 `--yes` 같은 확인 플래그는 없다.
8. **로그 줄 수 플래그는 `-n`이다.** `openshell logs <이름> --since 15m -n 500 --level debug` 형태로 쓴다.
9. **키 전달 방식.** `openshell provider create --credential KEY`는 값이 아니라 조회할 환경변수 이름을
   받는다(`KEY=VALUE` 형태도 되지만 값이 명령줄에 남는다). 이름만 넘기고 값은 stdin으로 환경변수에
   담는 쪽을 썼다.

### 정책이 실제로 강제되는지 (스모크 테스트)

`scripts/openshell_smoke.sh pharmasignal`을 돌려 종료 코드 0, `pass=9 fail=0`을 얻었다. 원문은
`eval/results/openshell_smoke.txt`에 있다.

| 구분 | 대상 | 결과 |
|---|---|---|
| 허용 | `api.fda.gov` | `http=200 rc=0` |
| 허용 | `dailymed.nlm.nih.gov` | `http=200 rc=0` |
| 허용 | `eutils.ncbi.nlm.nih.gov` | `http=200 rc=0` |
| 허용 | `integrate.api.nvidia.com` | `http=200 rc=0` |
| 차단 | `example.com` | `curl: (56) CONNECT tunnel failed, response 403`, `http=000 rc=56` |
| 차단 | `github.com` | `curl: (56) CONNECT tunnel failed, response 403`, `http=000 rc=56` |
| 쓰기 거부 | `/etc` | `cannot create /etc/openshell_smoke_probe: Permission denied`, `rc=2` |
| 쓰기 허용 | `/work/out` | 파일을 쓰고 다시 읽은 뒤 삭제까지 `rc=0` |
| 쓰기 거부 | `/sandbox` | `cannot create /sandbox/openshell_smoke_probe: Permission denied`, `rc=2` |

`integrate.api.nvidia.com`이 401이 아니라 200을 돌려준 것은 프록시가 진짜 키를 끼워 넣었다는 뜻이다.
샌드박스 안에서 `printenv NVIDIA_API_KEY`를 하면 값이 아니라 자리표시자
`openshell:resolve:env:v<숫자>_NVIDIA_API_KEY`가 나온다. provider 구조가 설명대로 동작한다.

### 차단 로그 원문

네트워크 거부는 게이트웨이 로그에 그대로 남는다. 아래는 `openshell logs pharmasignal --since 15m`
출력에서 뽑은 것이다.

```
[1790272384.037] [sandbox] [OCSF ] [ocsf] NET:OPEN [MED] DENIED /usr/bin/curl(189) -> example.com:443 [policy:- engine:opa] [reason:endpoint example.com:443 is not allowed by any policy]
[1790272385.616] [sandbox] [OCSF ] [ocsf] NET:OPEN [MED] DENIED /usr/bin/curl(199) -> github.com:443 [policy:- engine:opa] [reason:endpoint github.com:443 is not allowed by any policy]
[1790272387.470] [sandbox] [INFO ] [openshell_sandbox] Flushed activity summary to gateway denied_action_count=2 network_activity_count=2 sandbox_name=pharmasignal
```

앞 절의 로그 예시와 견주면 실제 형식이 조금 다르다. 사유가 `l7_deny_reason=` 같은 별도 필드가 아니라
`[reason:...]` 괄호 안에 들어가고, 허용 목록에 없는 호스트는 L7까지 가지 않고 `is not allowed by any
policy`로 끊긴다.

**파일시스템 거부는 로그에 DENIED로 남지 않는다.** Landlock이 커널에서 EPERM으로 끊기 때문에
게이트웨이가 볼 이벤트가 없다. 대신 적용 기록이 남으므로 스모크 스크립트가 이 줄을 함께 저장한다.

```
[ocsf] CONFIG:APPLYING [INFO] Applying Landlock filesystem sandbox [abi:V2 compat:BestEffort ro:12 rw:3]
[ocsf] CONFIG:BUILT [INFO] Landlock ruleset built [rules_applied:14 skipped:1]
```

`skipped:1`은 이미지에 없는 `/app` 하나다(`read_only` 목록에는 있으나 이미지에 만들지 않았다).
`compatibility: best_effort`라 건너뛰고 넘어간다. `hard_requirement`로 바꾸려면 Dockerfile에
`/app`을 만들거나 정책에서 빼야 한다. `abi:V2`로 적용된 점도 기록해 둔다. 커널 6.8은 더 높은 ABI를
제공하지만 0.0.116은 V2로 걸었다.

### 이 세션에서 해소된 [unverified]

아래 절의 목록 중 1번(Landlock 활성), 2번(seccomp 프로브), 4번(이미지의 python3), 5번(`sandbox list`
필드 구조), 6번(`--version` 존재), 9번(설치되는 최신 버전)은 실행으로 확인했다. 설치된 버전은
`0.0.116`이다.

### 남은 [unverified]

- `protocol: rest` 엔드포인트에 Python 클라이언트(`requests`, `httpx`)가 인증서 검증을 통과하는지.
  이번 확인은 `curl`로만 했다. NAT 워크플로를 샌드박스 안에서 돌릴 때 다시 본다.
- `sandbox_pids_limit`이 Docker 드라이버에서 유효한지.
- Multipass 백엔드 경로. 스크립트에 그대로 남겼으나 이 환경에서는 VM을 못 만들어 실행 검증이 없다.
- `nightshift.yaml`과 `base.yaml`. 이번에는 `pharmasignal.yaml`만 적용했다.
- 소요 시간 표(추정). Colima에서는 VM 생성이 빠지고 설치와 이미지 빌드만 남아 훨씬 짧았지만
  단계별로 재보지는 않았다.

## NemoClaw 판단

NemoClaw는 OpenShell을 설치하고 그 위에 OpenClaw, Hermes, LangChain Deep Agents 같은 "지원 에이전트"를 표준 구성으로 올리는 참조 스택이다. 온보딩 한 줄(`curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash`)로 provider 생성, 추론 경로 설정, MCP 서버 수명주기, 스냅샷과 복구까지 맡아 준다.

이 프로젝트에는 맞지 않는다고 판단한다. 첫째, 우리는 NAT 워크플로와 자체 도구를 담은 커스텀 이미지를 돌리는데, NemoClaw 문서가 이 경우를 "OpenShell 단독" 경로로 안내한다. 둘째, 요구 리소스(RAM 최소 8GB, 권장 16GB, 디스크 20~40GB, Node.js 22.19 이상)가 6GB VM에 맞지 않는다. 셋째, 검증 플랫폼이 DGX와 Ubuntu 24.04 네이티브 Linux, Apple Silicon macOS, WSL2이고 Intel Mac 위의 QEMU VM은 언급이 없다. 다만 DLI 교육 미션(S-FX-43)에서 NemoClaw를 다루므로 개념과 명령은 교육 환경(Brev)에서 익히고, 제출물에는 "OpenShell 정책을 직접 작성했고 NemoClaw는 참조 스택으로 검토했다"고 적는 편이 정확하다.

## 안 되는 것

- Intel Mac 호스트에 OpenShell 설치. 설치 스크립트가 아키텍처 검사에서 종료한다. VM이 유일한 경로다.
- 호스트의 Docker 27을 게이트웨이 런타임으로 사용. 지원 매트릭스 최소 버전이 28.0이고, 어차피 macOS x86_64 게이트웨이 바이너리가 없다.
- 정책 파일 안에서 CPU, 메모리, 시간 제한. 스키마에 없다. 생성과 실행 플래그로 대신한다.
- 정책 파일 간 상속(include, extends). 없다. 후보별 파일은 base 내용을 그대로 담고 있다.
- `openshell sandbox upload`로 코드 넣기(base 정책 기준). `include_workdir: false`라 `/sandbox`가 읽기 전용이다. 코드는 이미지에 `COPY`한다. 업로드가 필요하면 `include_workdir: true`로 바꾸고 `/sandbox`를 `read_write`로 옮긴다(그러면 "쓰기는 /work/out만"이 깨진다).
- `nightshift.yaml`에서 git 소스 sdist를 빌드하는 pip 패키지 설치. `github.com`을 막았으므로 의도된 제약이다.
- 첫 TCP(`protocol: tcp`) 엔드포인트를 실행 중 추가. 샌드박스 재생성이 필요하다. 이번 정책은 tcp를 쓰지 않는다.

## [unverified] 목록

1. Multipass의 Ubuntu 24.04 x86_64 이미지 커널에서 Landlock LSM이 활성(`lsm=` 목록 포함)인지. Ubuntu 커널 설정 파일을 직접 받아 확인하지 못했다(launchpad 응답 실패). 스크립트 2단계가 `/sys/kernel/security/lsm`으로 실측하고, OpenShell 슈퍼바이저도 시작 시 Landlock ABI와 seccomp을 프로브해 실패하면 fail-closed로 멈춘다.
2. seccomp `SECCOMP_IOCTL_NOTIF_ADDFD`와 task-memory 접근 프로브가 QEMU VM 안의 Docker 컨테이너에서 통과하는지. 문서는 "컨테이너나 microVM 안에서도 필요"라고만 적고 있어 실행으로 확인해야 한다.
3. `protocol: rest`로 TLS를 종단하는 엔드포인트에 Python 클라이언트(`requests`, `httpx`의 certifi 번들)가 인증서 검증을 통과하는지. 공식 `local-inference` 예제가 `protocol: rest` 엔드포인트에 Python 바이너리를 허용하고 OpenAI 클라이언트로 호출하므로 통과할 것으로 보이지만, CA 주입 방식은 문서에서 찾지 못했다. pip는 이 위험을 피해 L4 통과로 두었다.
4. 기본 이미지 `nvcr.io/nvidia/base/ubuntu:24.04`에 python3가 있는지. 확인하지 않고 자체 이미지(`policies/sandbox-image/Dockerfile`)를 쓴다. 매니페스트는 익명으로 조회되어 pull 자체는 가능하다.
5. `openshell sandbox list -o json`의 정확한 필드 구조. 스크립트는 `"name": "<이름>"` 패턴과 텍스트 첫 열을 둘 다 검사한다.
6. `openshell --version` 옵션 존재 여부. 스크립트는 실패해도 넘어간다.
7. `sandbox_pids_limit`이 Docker 드라이버에서도 유효한지(Podman 드라이버 항목에서만 확인).
8. 소요 시간 표 전체(추정).
9. 설치 스크립트가 내려받는 "latest"가 `v0.0.116`인지 0.1.0 계열인지. README와 Releases API가 다르게 읽힌다. 설치 후 버전을 기록한다.

## 사용자가 직접 할 명령 (순서대로)

Colima 기준이다. 1번과 2번은 이미 끝나 있으면 건너뛴다.

```bash
brew install colima                                 # 1. Colima 설치
colima start --vm-type vz --cpu 2 --memory 5 --disk 30   # 2. VM 기동 (Apple 가상화 프레임워크, QEMU를 거치지 않는다)
cp .env.example .env && $EDITOR .env                # 3. NVIDIA_API_KEY 채우기 (없으면 provider 단계만 건너뜀)
scripts/openshell_vm_up.sh pharmasignal             # 4. Docker 점검 → OpenShell → 이미지 → provider → 샌드박스 → 정책
scripts/openshell_smoke.sh pharmasignal             # 5. 허용/차단/쓰기 검증, eval/results/openshell_smoke.txt
colima ssh                                          # 6. (선택) VM 접속 후 openshell logs pharmasignal --tail
SANDBOX_NAME=nightshift scripts/openshell_vm_up.sh nightshift   # 7. (후보 2 확정 시) 두 번째 샌드박스
```

Multipass를 쓰는 환경이면 백엔드만 바꾼다. Intel Mac에서는 VM 생성이 실패하므로 리눅스 호스트나
Apple Silicon Mac에서만 쓸 수 있다.

```bash
VM_BACKEND=multipass scripts/openshell_vm_up.sh pharmasignal
VM_BACKEND=multipass scripts/openshell_smoke.sh pharmasignal
```

## 출처

- OpenShell README: https://github.com/NVIDIA/OpenShell
- 정책 스키마: https://github.com/NVIDIA/OpenShell/blob/main/docs/reference/policy-schema.mdx
- 기본 정책: https://github.com/NVIDIA/OpenShell/blob/main/docs/reference/default-policy.mdx
- 지원 매트릭스(플랫폼, Docker 28, 커널 요건): https://github.com/NVIDIA/OpenShell/blob/main/docs/reference/support-matrix.mdx
- 설치 스크립트(Intel macOS 미지원 분기): https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh
- 빠른 시작 예제와 정책: https://github.com/NVIDIA/OpenShell/tree/main/examples/sandbox-policy-quickstart
- 추론 예제(provider profile, PyPI L4 정책): https://github.com/NVIDIA/OpenShell/tree/main/examples/local-inference
- BYOC 이미지 요건: https://github.com/NVIDIA/OpenShell/tree/main/examples/bring-your-own-container
- provider 예제(nvidia.yaml, pypi.yaml): https://github.com/NVIDIA/OpenShell/tree/main/providers
- 추론(provider) 문서: https://github.com/NVIDIA/OpenShell/blob/main/docs/sandboxes/inference-routing.mdx
- 정책 적용과 디버깅: https://github.com/NVIDIA/OpenShell/blob/main/docs/sandboxes/policies.mdx
- 샌드박스 관리(--cpu, --memory, exec --timeout, upload): https://github.com/NVIDIA/OpenShell/blob/main/docs/sandboxes/manage-sandboxes.mdx
- 로그 접근과 형식: https://github.com/NVIDIA/OpenShell/blob/main/docs/observability/accessing-logs.mdx , https://github.com/NVIDIA/OpenShell/blob/main/docs/observability/logging.mdx
- NemoClaw 문서: https://docs.nvidia.com/nemoclaw/latest/ , 전제조건 https://docs.nvidia.com/nemoclaw/latest/get-started/prerequisites.html , 생태계 https://docs.nvidia.com/nemoclaw/latest/about/ecosystem.html
- NVIDIA 블로그: https://developer.nvidia.com/blog/run-autonomous-self-evolving-agents-more-safely-with-nvidia-openshell/
- Multipass 설치(macOS 14+, Intel 지원, QEMU 기본): https://canonical.com/multipass/docs/en/latest/how-to-guides/install-multipass/
- Multipass launch 옵션: https://canonical.com/multipass/docs/en/latest/reference/command-line-interface/launch/
- Docker Engine Ubuntu 설치: https://docs.docker.com/engine/install/ubuntu/
- Ubuntu 24.04 커널 6.8: https://discourse.ubuntu.com/t/introducing-kernel-6-8-for-the-24-04-noble-numbat-release/41958
