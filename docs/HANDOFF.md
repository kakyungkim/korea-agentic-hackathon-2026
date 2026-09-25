# 진행 상황 (2026-09-25 새벽 기준)

마감 **2026-09-28(월) 23:59**. 목표 제출 시각은 그날 18:00으로 잡아 여유를 둔다.

## 지금 상태를 한 줄로

약물감시 시그널 트리아지 에이전트(PharmaSignal)가 도구부터 크리틱까지 동작한다.
남은 큰 일은 팀 확정, 데모 영상, 신청서 제출 셋이다.

## 검증된 수치

| 항목 | 값 | 어디서 |
|---|---|---|
| 오프라인 테스트 | 128개 통과 | `pytest -q -m "not network"` |
| NAT 설정 검증 | 4종 통과 | `nat validate` |
| 크리틱 적발률 | 1.0 | `eval/results/critic_verdict_output.json` |
| 케이스 3건 | PRR 72.8 / 7.2 / 0.87 | `eval/results/pharmasignal_cases.json` |
| 샌드박스 스모크 | 9건 전부 통과 | `eval/results/openshell_smoke.txt` |

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
- 새로 합류한 분에게는 `docs/ONBOARDING.md` 링크만 주면 된다

## 결정된 사항

- 이름은 **PharmaSignal**. 선행 프로젝트는 `kakyungkim/pharmasignal-v0`으로 바꿨고 로컬 폴더는
  `hackthon/AgentForgeAI` 그대로다. 새 저장소 생성과 폴더 이름 변경은 팀 확정 후로 미뤘다
  (`docs/notes/repo-naming-plan.md`).
- 계보는 숨기지 않고 밝힌다. README에 문단이 들어가 있다.
- 되지 않는 것을 되는 것처럼 쓰지 않는다. NemoGuard 판정 모델은 호스팅 쪽 오류로 시연하지 못했고
  문안에도 그렇게 적었다.
- 커밋은 아직 하지 않았다. 사용자 지시가 있을 때 한다.

## 주제가 바뀔 가능성

팀 구성에 따라 Night Shift(밤새 저장소에서 스스로 실험하는 자율 코딩 에이전트)로 갈 수 있다.
그쪽 구성요소도 이미 동작한다. 실행기, 규칙 크리틱, 아침 보고서가 있고 데모에서 부정 패치 2건을
반려하는 것을 확인했다. 공통 하네스와 샌드박스 정책은 어느 쪽이든 그대로 쓴다.

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
   그리고 **샌드박스 안에서 파이썬 클라이언트가 `integrate.api.nvidia.com` 인증서 검증을
   통과하는지**다. 마지막 항목이 중요하다. 우리 도구 3종이 파이썬이라 이것이 되어야
   샌드박스 안에서 실제 파이프라인을 돌릴 수 있다.

VM 상태는 그대로다. Colima 실행 중이고 샌드박스 `pharmasignal` 이 Ready 이며 제출 증거인
`eval/results/openshell_smoke.txt` 는 손대지 않았다.
