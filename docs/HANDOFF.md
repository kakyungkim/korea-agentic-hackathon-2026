# 진행 상황 (2026-09-25 갱신)

마감 **2026-09-28(월) 23:59**. 목표 제출 시각은 그날 18:00으로 잡아 여유를 둔다.

## 지금 상태를 한 줄로

약물감시 시그널 트리아지 에이전트(PharmaSignal)의 도구와 크리틱이 동작하나
**도메인 도구가 NAT 에이전트에 연결돼 있지 않다.** 주제도 아직 확정되지 않았다.
남은 큰 일은 주제 확정, 도구 등록, 데모 영상, 신청서 제출 넷이다.

## 정정 (2026-09-25 오후 확인)

아래 두 항목은 이 문서의 이전 판과 `README.md`가 사실과 다르게 적고 있던 것이다.

**1. ~~도메인 도구 3종은 NAT에 등록돼 있지 않다~~ 2026-09-25 해소했다.** 아래는 그전 상태의 기록이다.
`openfda_faers`, `dailymed_label`, `pubmed_search` 가 등록됐고 `tool_names` 에 실렸다.
`diffdock_nim` 도 배선을 마쳤다.

이전 상태: "도구 3종이 공개 API로 실제 동작한다"는 맞지만
에이전트가 그것을 부를 수는 없다. `grep -rn "register_function" src/harness/tools/` 결과가 0건이고
`src/harness/register.py:152-156`의 도메인 도구 import 네 줄이 전부 주석이다.
`configs/author.yml`의 `tool_names`는 `[echo_tool, prr_calculator]`다. FAERS와 DailyMed와 PubMed는
`pharmasignal_cases.py` CLI로만 돈다.

심사 첫 항목이 "NVIDIA Agent 기술 활용 심도"이므로 **이것이 지금 가장 큰 구멍이다.**
주제와 무관하게 먼저 메운다. 기존 코드에 `@register_function` 래퍼를 씌우는 일이고 참조 구현은
`src/harness/register.py:126-147`, 절차는 `docs/notes/nat-harness.md:244-253`에 있다.

**2. `README.md`가 OpenShell 실행을 아직 못 한 일로 적고 있다.** 실제로는 완료했다(아래 "샌드박스
증거"). README가 낡았으니 제출물 작성 전에 고친다.

## 검증된 수치

| 항목 | 값 | 어디서 |
|---|---|---|
| 오프라인 테스트 | **214개 통과** (2026-09-25 갱신, 이전 128) | `pytest -q -m "not network"` |
| 도구 NAT 등록 | openfda_faers, dailymed_label, pubmed_search, diffdock_nim **4종 배선 완료** | `configs/author.yml` tool_names |
| 설정 검증 | 4종 전부 유효 | `nat validate` |
| 에이전트 도구 호출 | 도구 3종 연속 호출 확인, 근거 ID 붙은 JSON | `nat run` 실행 로그 |
| **케이스 시연 E2E** | niraparib 두 경로, 7단계 전부 수집, 3단 크리틱 통과와 반려 | `eval/results/case_niraparib_brief.md` |
| 크리틱 3단 분리 | 1단과 2단은 양쪽 통과, **3단만 과잉해석 7건을 전부 반려** | `eval/results/case_niraparib.json` |
| DiffDock NIM 호출 | HTTP 200, 4.0초, 포즈 3개 | `eval/results/diffdock_smoke.txt`, `diffdock_client_run.txt` |
| 크리틱 적발률 | 1.0 | `eval/results/critic_verdict_output.json` |
| 케이스 3건 | PRR 72.8 / 7.2 / 0.87 | `eval/results/pharmasignal_cases.json` |
| **샌드박스 스모크(신규 정책)** | **18건 전부 통과** | `eval/results/openshell_smoke_flydock.txt` |
| 샌드박스 안 파이썬 TLS | **통과.** `health.api.nvidia.com` GET 405 | 같은 파일 |
| 샌드박스 스모크(약물감시) | 9건 전부 통과, `process` 보강 후 10건 | `eval/results/openshell_smoke.txt` |

## 샌드박스 증거 (제출물의 핵심)

Colima VM 안에서 OpenShell 0.0.116을 설치하고 `policies/pharmasignal.yaml`을 적용해 실제로 강제되는
것을 확인했다. 허용 도메인 4곳은 200으로 응답하고, 허용 목록 밖인 example.com과 github.com은
프록시에서 403으로 끊긴다. `/etc`와 `/sandbox` 쓰기는 거부되고 `/work/out`만 열린다.

차단 로그 원문이 `eval/results/openshell_smoke.txt`에 있다.
```
NET:OPEN [MED] DENIED /usr/bin/curl -> example.com:443 [reason:endpoint example.com:443 is not allowed by any policy]
NET:OPEN [MED] DENIED /usr/bin/curl -> github.com:443 [reason:endpoint github.com:443 is not allowed by any policy]
Applying Landlock filesystem sandbox [abi:V2 compat:BestEffort ro:12 rw:3]
```
파일시스템 거부는 커널이 EPERM으로 끊어 DENIED 줄이 남지 않으므로 Landlock 적용 기록을 함께 저장했다.

추론 자격증명이 정책 파일이 아니라 provider가 들고 있다는 점도 확인했다. 샌드박스 안에서
`printenv NVIDIA_API_KEY`는 자리표시자를 돌려주는데 `integrate.api.nvidia.com` 호출은 200이 온다.

## 동작하는 것

- 도구 3종이 공개 API로 실제 동작한다. openFDA FAERS 집계와 불균형 지표, DailyMed 라벨 섹션 검색,
  PubMed 문헌 조회다. 응답은 캐시되어 재실행이 빠르다.
- NeMo Agent Toolkit 워크플로 둘이 돈다. 작성자가 도구를 호출해 근거 ID가 붙은 JSON을 내고,
  크리틱이 근거 없는 주장을 반려한다. 크리틱에는 쓰기 도구가 없다.
- v0에서 ROR 오라클과 검증 지표를 가져왔다. Evans 기준의 카이제곱이 Yates 보정이어야 한다는 것을
  원 논문에서 확인해 고쳤고, 분할표에 0이 들어가 버려지던 신호도 살렸다.
- 제출용 그림 2종이 있다. 아키텍처 도식과 케이스 3건 포레스트 플롯이며 결과 파일에서 수치를 읽는다.
- 영상과 슬라이드 제작 도구가 `assets/`에 있다. v0에서 가져왔고 원고와 내용만 갈면 된다.

## 아직 못 한 것

1. **팀 확정.** 폼의 "팀 구성 인원"이 2명부터라 최소 1명 합류가 사실상 필수다. 9/27(일)까지 합류해야
   각자 폼을 낼 수 있다. 연락 현황은 `docs/notes/recruiting.md`.
2. **데모 영상.** 2~3분. 도구는 준비돼 있고 원고 작성부터 하면 된다.
3. **신청서 제출.** 문안 초안은 `docs/submission-draft.md`에 있고 글자 수도 맞춰 두었다.
   `[측정필요]` 표에 제출 전 갱신할 자리가 모여 있다.
4. ~~OpenShell 실행~~ **완료했다.** 아래 "샌드박스 증거" 참고.
5. **DLI 강좌.** 레슨 1a와 1b를 들었다. 모듈 3과 4는 Brev 인스턴스를 띄워야 진도가 오른다.
   원격 진도 기록은 기본으로 꺼져 있으니 도구 모음의 Activity에서 켠다.

## 다음 세션에서 먼저 볼 것

- `README.md` 현재 상태와 실행 방법
- `docs/TROUBLESHOOTING.md` 겪은 문제 11건. 같은 자리에서 시간을 쓰지 않게 한다
- `docs/submission-draft.md`의 `[측정필요]` 표
- `docs/notes/recruiting.md` 연락 현황
- `docs/notes/topic-decision.md` **주제 후보 비교와 권고, 게이트와 일정. 주제 논의 전에 먼저**
- `docs/notes/fddd-and-jev.md` 팀원 제안 주제 두 개의 실측 내용
- `docs/notes/bionemo-nim.md` NVIDIA 생물학 NIM 접근 확인과 호출 규격
- `docs/notes/post-hackathon.md` 제출 후 세 갈래(심사, 스타, 논문)와 순서
- `docs/notes/paper-plan.md` 논문 계획과 확장 요건
- `docs/notes/credits.md` 기여 표기. README 와 신청서가 이것을 따른다
- 새로 합류한 분에게는 `docs/ONBOARDING.md` 링크만 주면 된다

## 결정된 사항

- 이름은 **PharmaSignal**. 선행 프로젝트는 `kakyungkim/pharmasignal-v0`으로 바꿨고 로컬 폴더는
  `hackthon/AgentForgeAI` 그대로다. 새 저장소 생성과 폴더 이름 변경은 팀 확정 후로 미뤘다
  (`docs/notes/repo-naming-plan.md`).
- 계보는 숨기지 않고 밝힌다. README에 문단이 들어가 있다.
- 되지 않는 것을 되는 것처럼 쓰지 않는다. NemoGuard 판정 모델은 호스팅 쪽 오류로 시연하지 못했고
  문안에도 그렇게 적었다.
- 커밋은 아직 하지 않았다. 사용자 지시가 있을 때 한다.

## 새로 확인한 것 (2026-09-25 오후)

**DiffDock 은 호출마다 결과가 다르다.** 같은 입력으로 두 번 불러 `position_confidence` 가
`[0.798, 0.751, 0.725]` 와 `[0.761, 0.693, 0.515]` 로 갈렸다. 확산모델이고 호스팅 API 에
시드 파라미터가 없다. 세 가지가 따라온다.

- 신청서와 영상에 "이 값이 나온다" 가 아니라 "이 호출에서 이 값이 나왔다" 로 적는다.
  요청과 응답의 SHA256 을 함께 남긴다
- 과잉해석 규칙이 하나 늘어 13종이 됐다. 단일 호출에 재현성을 주장하면 반려한다.
  **우리가 실측으로 보인 규칙이라 발표에서 값이 크다**
- 응답 캐시가 필수다. 캐시 적중은 0.01초이고 네트워크를 타지 않는다

**작업 하네스를 만들었다.** `.claude/` 에 에이전트 5명과 스킬 4개가 있다.
다음 세션에서 "이어서 해줘" 라고 하면 `hackathon-ship` 이 상태를 읽고 이어간다.
기여 표기는 `docs/notes/credits.md` 를 따른다.

## 주제 현황 (2026-09-25)

**Night Shift는 후보에서 뺐다.** 개발자 도메인과 커뮤니티 섭외를 겨냥한 후보였는데 확정 3명이
전부 바이오와 제약 쪽이고 자율 코딩을 관심으로 꼽은 사람이 없다. 구성요소(실행기, 규칙 크리틱 9종,
아침 보고서)는 동작하고 부정 패치 2건 반려도 확인했으므로 자산으로 남겨 다음 기회에 쓴다.
단 NAT 워크플로가 없어 되살리려면 배선이 새 작업이다.

남은 후보는 **PharmaSignal**과 **초파리 뇌 아틀라스 기반 신약개발(팀원의 FDDD 데모)** 둘이고
Jev는 독립 주제가 아니라 어느 쪽에든 얹는 부품이다.

**권고는 두 주제를 하나의 파이프라인으로 이어 붙이는 것이다.** 도킹을 앞단에 약물감시 도구를
뒷단에 두고, 도킹 점수에서 나올 수 없는 주장을 크리틱이 반려한다. 근거와 게이트와 일정은
`docs/notes/topic-decision.md`에 있다.

전제가 하나 있다. `health.api.nvidia.com`의 DiffDock 호출이 이 계정에서 인가되는지 먼저 확인해야
한다. 막히면 PharmaSignal 단독으로 되돌린다.

공통 하네스와 샌드박스 정책은 어느 쪽이든 그대로 쓴다.

## 중단한 작업 (2026-09-25 새벽, 이어서 할 것)

사용자가 외출해 두 작업을 중간에 멈췄다. 파일은 그대로 남아 있고 다시 실행해도 안전하다.

1. **데모 영상 대본과 슬라이드.** 시작 직후 멈춰 산출물이 없다. `docs/video/` 와
   `assets/video/02_나레이션.txt`, `08_timeline.txt` 새 버전, 슬라이드 내용을 만들면 된다.
   구간 배분은 문제 25초, 계보 20초, 흐름 60초, 결과 30초, 안전 25초, 마무리 15초로 잡았다.
2. **남은 정책 검증.** 진행 중 발견한 것이 하나 있다. **nightshift 정책에서 `pypi` 블록의
   `binaries` 목록이 python 과 pip 만 허용해 `curl` 로는 접속이 막힌다.** 스모크 스크립트가
   `curl` 로 확인하려 해서 실패했다. 정책이 의도대로 동작하는 증거이지 결함이 아니다.
   스모크를 고칠 때 정책이 허용한 바이너리로 확인하도록 바꿔야 한다.
   그 밖에 확인할 것은 github.com 차단, `/work/repo` 쓰기, `run_as_user` 적용,
   그리고 ~~샌드박스 안 파이썬 인증서 검증~~ **2026-09-25 해소했다.** OpenShell 이 자기 CA 를
   `/etc/openshell-tls/ca-bundle.pem` 에 넣고 `SSL_CERT_FILE` 등을 그 경로로 설정해 둔다.
   우리 도구 3종이 전부 `urllib` 을 쓰므로 그대로 돌아간다. certifi 번들을 강제하면 실패하니
   나중에 `httpx` 를 도입하면 `verify=` 에 OpenShell 번들 경로를 넘겨야 한다.

VM 상태는 그대로다. Colima 실행 중이고 샌드박스 `pharmasignal` 이 Ready 이며 제출 증거인
`eval/results/openshell_smoke.txt` 는 손대지 않았다.
