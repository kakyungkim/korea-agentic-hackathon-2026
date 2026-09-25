# 온라인 사전 챌린지 신청서 문안 초안

작성 2026-09-24. 마감 2026-09-28(월) 23:59. 신청서 Section 02의 네 항목을 후보별로 준비해 둔 초안이다.
후보는 9/25(금) 밤에 하나로 정하고, 정해진 쪽의 문안만 폼에 옮긴다.

글자 수는 각 문안 끝에 `(현재 N자)`로 적었고 공백 포함 기준과 미포함 기준을 함께 표기했다.
기준은 문제 300자, 솔루션 500자이며 ±10%(문제 270~330자, 솔루션 450~550자) 안에 맞췄다.
세는 방법은 파이썬 `len()`이고, 폼이 공백을 어떻게 세는지 모르므로 두 기준 모두 남겼다.

2026-09-25 재측정. 아래 표가 현재 문안의 글자 수이고, 각 문안 끝의 `(현재 N자)`와 같은 값이다.

| 후보 | 문항 | 공백 포함 | 공백 미포함 | 기준 | 판정 |
|---|---|---|---|---|---|
| PharmaSignal | 문제 | 293 | 227 | 270~330 | 충족 |
| PharmaSignal | 솔루션 | 542 | 430 | 450~550 | 충족 |
| PharmaSignal | 기술 스택 | 1,254 | 1,079 | 상한 미고지 | 해당 없음 |
| Night Shift | 문제 | 288 | 218 | 270~330 | 충족 |
| Night Shift | 솔루션 | 468 | 364 | 450~550 | 충족 |
| Night Shift | 기술 스택 | 1,263 | 1,079 | 상한 미고지 | 해당 없음 |

이번에 고친 곳은 두 기술 스택 문단의 NemoGuard 서술과 Night Shift 솔루션의 모델명이다. 솔루션 문안은
Night Shift 쪽만 "Nano"를 실측으로 살아 있는 "3.5 Lightning"으로 바꿔 9자 늘었고, 두 후보 모두 500자
±10% 안에 그대로 있다. 기술 스택은 폼이 상한을 밝히지 않아 기준 판정에서 뺐다.

문체는 합니다체로 썼다. 폼이 평서체를 요구하거나 분량을 더 줄여야 하면 종결만 "~한다"로 바꾸면
공백 포함 기준으로 문항당 20자 안팎이 줄어든다.

---

## 확정 전 실측으로 갱신할 자리

아래 항목은 2026-09-24 기준으로 **아직 실행하지 못했다.** 9/28 최종 제출 전에 실측으로 갱신하고,
끝내 못 돌린 항목은 문안에서 빼거나 "설계까지 마쳤고 실행은 남았다"로 정직하게 적는다.
현재 문안에는 이 항목들이 이미 된 것처럼 적힌 표현이 없다.

| 번호 | 항목 | 지금 상태 | 갱신할 곳 |
|---|---|---|---|
| 1 | LLM 경로 **실측 완료** | 키를 발급받아 모델을 직접 호출했다. `nat eval`이 크리틱 워크플로를 끝까지 돌렸고 결과가 `eval/results/critic_verdict_output.json`에 남았다(2026-09-24 실행) | 두 후보 솔루션 문안의 Nemotron 관련 서술 |
| 2 | 크리틱 적발률 **실측 완료** | `eval/results/critic_verdict_output.json` 평균 1.0. 정상 2건 pass, 심어 둔 부정 1건 reject로 3건 모두 기대와 일치한다 | 솔루션 문안에 "평가 3건에서 적발률은 1.0"으로 반영했다 |
| 3 | Nemotron 3 모델 ID **실측 완료** | `nvidia/nemotron-3-super-120b-a12b`(계획과 크리틱)와 `nvidia/nemotron-3.5-lightning-30b-a3b`(작업자)는 호출된다. 계획서의 `nvidia/nemotron-3-nano-30b-a3b`는 2026-09-01 종료로 410을 돌려준다(`docs/notes/nat-harness.md`) | 기술 스택의 모델명을 실측 ID로 바꿨다 |
| 4 | `[측정필요]` OpenShell 실제 실행 | 정책 YAML 3종과 설치 스크립트를 쓰고 `bash -n` 문법 검사까지만 했다. Multipass VM을 아직 만들지 않았다 | 솔루션 문안의 샌드박스 서술, 기술 스택의 OpenShell 항목 |
| 5 | `[측정필요]` 정책 차단 로그 건수 | Night Shift 아침 보고서의 정책 감사 요약은 0으로 채운 자리표시다 | 솔루션 문안에 차단 건수를 넣을지 여부 |
| 6 | NemoGuard **실측 완료(부정 결과)** | `nvidia/llama-3.1-nemoguard-8b-topic-control`은 3회 모두 HTTP 500(서버 쪽 TensorRT-LLM CUDA 오류), `nvidia/llama-3.1-nemoguard-8b-content-safety`는 25초와 90초 모두 타임아웃이다. 응답하는 것은 `nvidia/nemotron-3.5-content-safety` 하나뿐인데 출력이 NemoGuard JSON이 아니라 `User Safety: unsafe` 한 줄이라 레일 파서와 맞는지는 미확인이다(`docs/notes/nat-harness.md`). 차단 시연을 하지 못했다 | 두 기술 스택 문단을 "배선까지 했고 차단 시연은 남았다"로 고쳤다. 그림의 `NemoGuard 토픽 제어` 라벨도 `NeMo Guardrails 정책`으로 바꿨다 |
| 7 | `[측정필요]` NeMo Retriever 라벨 RAG | PharmaSignal의 `label_rag`는 계획만 있고 구현하지 않았다. 리랭커는 이 계정의 모델 목록에 하나도 없어 문안에서 뺐고, 임베딩 `nvidia/nemotron-3-embed-1b`(차원 2048)는 동작을 확인했다 | PharmaSignal 기술 스택. 못 만들면 목록에서 뺀다 |
| 8 | `[측정필요]` 크레딧 소모 | 실험 1건당 모델 호출 3~5회는 설계상 추정이고 실측이 아니다 | 문안에는 넣지 않는다. 심사 질의 대비용 |
| 9 | `[측정필요]` DLI S-FX-43 수료 | 등록과 수강을 아직 하지 않았다. 증빙 방식도 미확인 | 제출 PDF 첨부 |
| 10 | `[측정필요]` 팀명, 팀원 수, 영상 URL | 미정 | 서비스 명, 파일명, 추가 URL |
| 11 | `[측정필요]` 선행 프로젝트 계보 기재 위치 확인 | README의 "배경과 계보" 절에는 적었다. 신청서 폼과 제출 PDF 중 어디에 어떤 분량으로 넣을지 미정 | 솔루션 문안, 추가 URL, 제출 PDF |

---

## PharmaSignal 버전

후보 1로 확정했을 때 쓴다.

### 서비스 명

```
PharmaSignal
```

부제가 필요하면 `PharmaSignal: 근거를 검증하는 약물감시 시그널 트리아지 에이전트`로 쓴다.

### 해결하고자 했던 문제 (Problem Definition)

```
의약품 이상사례 자발보고는 규모가 사람 손을 넘어섰습니다. openFDA FAERS 전체 보고는 2,069만 건이고(2026년 7월 30일 갱신) metformin 한 성분에만 44만 건이 걸립니다. 약물감시 담당자는 조합 하나를 판정하려고 이 보고와 허가 라벨, 문헌을 각각 검색해 교차 확인합니다. 새로 나타난 시그널인지 이미 라벨에 적힌 반응인지 1차로 가리는 일인데, 대조 경로가 담당자마다 달라 근거가 빠지거나 판정이 갈립니다. 자동화하려 해도 모델이 근거 없이 결론을 적어 버리면 규제 업무에서는 쓸 수 없습니다.
```

(현재 293자, 공백 미포함 227자)

인용한 수치의 출처는 `eval/results/pharmasignal_cases.json`이다. 전체 보고 건수 `n_total` 20,692,690,
metformin `n_drug` 440,270, 데이터 갱신일은 openFDA 응답의 `meta.last_updated` 2026-07-30이다.
"수 시간이 걸린다" 같은 소요 시간은 출처가 없어 넣지 않았다.

### 서비스 소개 및 주요 기능 (Solution)

```
PharmaSignal은 약물명과 이상사례를 받아 근거가 붙은 트리아지 메모를 만듭니다. 8월 해커톤에 낸 앞 버전은 임상시험 자료만 봤고, 이번 판은 FAERS와 허가 라벨, 문헌을 도구로 채웠습니다. Nemotron 3 Super가 계획을 세우고 도구를 부릅니다. openFDA FAERS에서 2x2표를 만들고, DailyMed SPL 라벨을 섹션으로 나눠 해당 반응 기재를 찾고, PubMed에서 문헌을 모읍니다. PRR, ROR, 카이제곱은 모델에 맡기지 않고 파이썬 코드가 계산합니다. 쓰기 권한이 없는 별도 크리틱 워크플로가 모든 주장에 FAERS 쿼리 URL, DailyMed setid, PMID가 붙었는지 검사하고, 근거 없는 주장은 사유와 함께 반려합니다. 평가 3건에서 적발률은 1.0이었습니다. 실제 실행에서 metformin과 유산산증은 PRR 72.8로 박스 경고 기재, amoxicillin과 망막박리는 PRR 0.87로 라벨 미기재에 문헌 8건이 나왔습니다. 규제 제출용 판단이 아닌 1차 트리아지 보조로 쓰며, 최종 판단은 사람이 합니다.
```

(현재 542자, 공백 미포함 430자)

의료 오용 방지 문구는 마지막 문장에 넣었다. 두 번째 문장이 선행 프로젝트 계보를 담는 자리다.
분량을 줄여야 하면 케이스 수치 문장을 먼저 뺀다. 그 문장을 통째로 빼면 공백 포함 96자가 줄어 446자가 된다.

### 활용한 핵심 기술 및 AI 모델 (Tech Stack)

```
[NVIDIA] Nemotron 3 Super 120B A12B(`nvidia/nemotron-3-super-120b-a12b`, 계획과 크리틱), Nemotron 3.5 Lightning 30B A3B(`nvidia/nemotron-3.5-lightning-30b-a3b`, 반복 작업)를 NIM API(integrate.api.nvidia.com, OpenAI 호환)로 호출합니다. NVIDIA NeMo Agent Toolkit 1.9.0(nvidia-nat)으로 작성자 워크플로와 크리틱 워크플로를 나눠 구성했습니다. 도메인 도구는 NAT function으로 등록했고(entry point 그룹 nat.components), 크리틱 적발률은 자체 평가기 critic_verdict를 nat eval에 붙여 잽니다. 안전 계층은 nvidia-nat-security 1.9.0의 Guardrails 미들웨어와 NeMo Guardrails 0.21.0(Colang 1.0) 정책으로 올렸고, 환자 개별 복약 조언을 차단 주제로 정의했습니다. 레일의 판정 모델로 지정한 NemoGuard 토픽 제어(`nvidia/llama-3.1-nemoguard-8b-topic-control`)는 레일이 호출하는 데까지 배선했으나 호스팅 쪽 서버 오류로 응답하지 않아 차단 시연은 남겨 뒀습니다. 실행 격리는 NVIDIA OpenShell 정책으로 합니다. deny-by-default로 쓰기는 /work/out만 허용하고, 네트워크는 api.fda.gov, dailymed.nlm.nih.gov, eutils.ncbi.nlm.nih.gov, integrate.api.nvidia.com만 열며 이 네 곳도 REST read-only로 제한해 POST를 L7에서 막습니다. 추론 자격증명은 정책 파일이 아니라 OpenShell provider profile이 들고 있어 샌드박스 환경변수에는 자리표시자만 들어갑니다. build.nvidia.com 스킬 카탈로그의 OpenShell 스킬을 함께 씁니다.

[그 밖] Python 3.12, 표준 라이브러리만 쓰는 도구 3종(urllib, xml.etree), pytest 9.1.1과 coverage 7.16.1, Docker 28 이상, Multipass Ubuntu 24.04 VM. 데이터 출처는 openFDA drug/event API, DailyMed SPL REST v2, PubMed E-utilities입니다. 오프라인 테스트 128개와 NAT 설정 4종 nat validate가 통과합니다.
```

`[측정필요] 4, 7`이 걸린 문단이다. 모델 ID는 실측값으로 맞췄고, 6번 NemoGuard는 실측 결과대로 "배선까지 했고 차단 시연은 남았다"로 적었다.
**리랭커는 적지 않는다.** 이 계정의 모델 목록 82개에 rerank 계열이 하나도 없다(`docs/notes/nat-harness.md`).
NeMo Retriever 라벨 RAG를 9/27까지 만들면 임베딩 `nvidia/nemotron-3-embed-1b`(차원 2048, 호출 확인)만
NVIDIA 문단 끝에 더하고, 만들지 못하면 지금처럼 빼 둔다.

### 추가 URL (선택)

- 데모 영상 `[측정필요]`
- GitHub 저장소 (공개 전환 시점을 제출 직전으로 잡는다)

---

## Night Shift 버전

후보 2로 확정했을 때 쓴다.

### 서비스 명

```
Night Shift
```

부제가 필요하면 `Night Shift: 밤새 실험하고 아침에 증거를 내미는 자율 코딩 에이전트`로 쓴다.

### 해결하고자 했던 문제 (Problem Definition)

```
개발자는 코딩 에이전트를 밤새 돌려 두고 싶지만 아침에 무엇이 지워졌을지 몰라 못 합니다. 자율 에이전트의 값어치는 무인 장시간 실행에 있는데, 그 실행을 안전하게 가두는 장치가 없습니다. 테스트 통과 여부만으로는 걸러지지도 않습니다. 실제로 테스트 하나를 지우고 검증 대상 함수의 동작을 바꾼 패치, 그리고 실패하는 테스트에 skip 마커를 붙인 패치를 돌려 보니 둘 다 테스트 실행이 정상 종료했습니다. 실행 결과만 보면 성공으로 읽히는 변경이 밤새 쌓이고, 아침에 사람이 diff를 하나씩 다시 읽어야 합니다.
```

(현재 288자, 공백 미포함 218자)

뒤쪽 두 문장의 근거는 `eval/results/nightshift_demo.json`과 `docs/notes/nightshift-components.md`의
데모 실행 결과다. 부정 패치 `fraud_delete_test`와 `fraud_skip_marker` 모두 테스트 실행이 rc=0으로 끝났다.

### 서비스 소개 및 주요 기능 (Solution)

```
Night Shift는 저장소 사본과 목표, 예산을 받아 밤새 실험을 반복하고 아침 보고서를 냅니다. Nemotron 3 Super가 실험을 고르고 3.5 Lightning이 패치를 씁니다. 패치는 OpenShell 샌드박스 안 실험 브랜치에서만 적용됩니다. 정책에서 github.com을 허용 목록에 넣지 않아 원본 저장소로 나갈 경로가 없고, git 래퍼가 push, pull, fetch, remote를 낱말 단위로 막습니다. 규칙 크리틱 아홉 가지가 테스트 삭제, skip 마커 추가, 검증문 감소, 커버리지 하락, 범위 밖 파일 수정, 비밀값 유입을 코드로 판정합니다. boltons 저장소 실험 3건을 65.4초에 돌려 정직한 패치는 통과시키고 테스트 삭제와 skip 마커 패치 2건은 반려했습니다. 아침 보고서에는 실험별 전후 수치, 규칙 판정, git am 적용 명령, 정책 감사 요약이 담겨 사람은 적용 여부만 고릅니다.
```

(현재 468자, 공백 미포함 364자)

"OpenShell 샌드박스 안"이라는 구절은 `[측정필요] 4`에 걸린다. 9/27까지 VM에서 실제로 돌리지 못하면
"OpenShell 정책으로 가두고, 지금 데모는 로컬 저장소 사본에서 돌립니다"로 정확히 낮춰 적는다.

### 활용한 핵심 기술 및 AI 모델 (Tech Stack)

```
[NVIDIA] Nemotron 3 Super 120B A12B(`nvidia/nemotron-3-super-120b-a12b`, 실험 선택과 최종 판정), Nemotron 3.5 Lightning 30B A3B(`nvidia/nemotron-3.5-lightning-30b-a3b`, 패치 작성)를 NIM API(integrate.api.nvidia.com, OpenAI 호환)로 호출합니다. NVIDIA NeMo Agent Toolkit 1.9.0(nvidia-nat)으로 작성자 워크플로와 크리틱 워크플로를 나눠 구성했습니다. 실행기, 규칙 크리틱, 보고서 생성기는 NAT function으로 등록했고(entry point 그룹 nat.components), 크리틱 적발률은 자체 평가기 critic_verdict를 nat eval에 붙여 잽니다. 안전 계층은 nvidia-nat-security 1.9.0의 Guardrails 미들웨어와 NeMo Guardrails 0.21.0(Colang 1.0) 정책으로 올렸고, 비밀 파일 접근과 외부 전송, 파괴적 명령을 요구하는 목표 입력을 차단 주제로 정의했습니다. 레일의 판정 모델로 지정한 NemoGuard 토픽 제어(`nvidia/llama-3.1-nemoguard-8b-topic-control`)는 레일이 호출하는 데까지 배선했으나 호스팅 쪽 서버 오류로 응답하지 않아 차단 시연은 남겨 뒀습니다. 실행 격리는 NVIDIA OpenShell 정책으로 합니다. deny-by-default로 쓰기는 /work/repo와 /work/out만 허용하고, 네트워크는 pypi.org, files.pythonhosted.org, integrate.api.nvidia.com만 엽니다. github.com은 의도적으로 빼서 원본 저장소로 나갈 길을 구조적으로 없앴습니다. 추론 자격증명은 OpenShell provider profile이 들고 있어 샌드박스 환경변수에는 자리표시자만 들어갑니다. build.nvidia.com 스킬 카탈로그의 OpenShell 스킬을 함께 씁니다.

[그 밖] Python 3.12, 표준 라이브러리 기반 실행기와 AST 규칙 크리틱, git, pytest 9.1.1, coverage 7.16.1, 외부 자원 없는 단일 파일 HTML 보고서, Docker 28 이상, Multipass Ubuntu 24.04 VM. 표적 저장소는 mahmoud/boltons(BSD-3-Clause)입니다. 오프라인 테스트 128개와 NAT 설정 4종 nat validate가 통과합니다.
```

`[측정필요] 4`가 걸린 문단이다. 3번 모델 ID와 6번 NemoGuard는 실측 결과를 반영했다.

### 추가 URL (선택)

- 데모 영상(30~60분 실행을 타임랩스로 압축) `[측정필요]`
- 아침 보고서 샘플 HTML
- GitHub 저장소

---

## 공통 기술 스택 문안

두 후보가 나눠 쓰는 뼈대는 같다. 아래 표를 손에 쥐고 있다가 확정된 후보 쪽 문안에 붙인다.

### 두 후보가 함께 쓰는 NVIDIA 기술

| 기술 | 쓰는 방식 | 확인 상태 |
|---|---|---|
| Nemotron 3 Super 120B A12B (`nvidia/nemotron-3-super-120b-a12b`) | 계획자와 LLM 크리틱 | 호출 확인 |
| Nemotron 3.5 Lightning 30B A3B (`nvidia/nemotron-3.5-lightning-30b-a3b`) | 반복 작업자. 종료된 nano 를 대신한다 | 호출 확인 |
| NIM API (`integrate.api.nvidia.com/v1`) | OpenAI 호환 엔드포인트로 호출 | 호출 확인 |
| NeMo Agent Toolkit 1.9.0 | `author.yml`, `critic.yml`, `eval.yml` 세 워크플로. `tool_calling_agent` | 설정 4종 `nat validate` 통과 |
| NAT function 등록 | `pyproject.toml`의 `nat.components` entry point로 도구 등록 | `nat info components`로 확인 |
| NAT 평가기 `critic_verdict` | `nat eval`로 크리틱 적발률 측정 | 평균 1.0. 정상 2건 pass, 부정 1건 reject |
| nvidia-nat-security 1.9.0 Guardrails 미들웨어 | 워크플로에 `middleware:`로 부착 | 로드와 `nat validate` 통과 |
| NeMo Guardrails 0.21.0 (Colang 1.0) | 후보별 차단 주제 정의 | 정책 폴더 문법 검증 통과 |
| NemoGuard 토픽 제어 (`nvidia/llama-3.1-nemoguard-8b-topic-control`) | 레일의 판정 모델로 지정. 레일이 호출하는 데까지 배선 | 호출 시 HTTP 500(서버 쪽 CUDA 오류), 3회 동일. 차단 시연 못 함 |
| NemoGuard content safety (`nvidia/llama-3.1-nemoguard-8b-content-safety`) | 레일의 보조 판정 후보 | 25초, 90초 모두 타임아웃. 쓰지 않는다 |
| `nvidia/nemotron-3.5-content-safety` | 살아 있는 대체 판정 모델 후보 | 호출 확인. 다만 출력이 `User Safety: unsafe` 한 줄이라 레일 파서와 맞는지 `[측정필요]` |
| OpenShell 정책 | `filesystem_policy`, `landlock`, `process`, `network_policies` 네 구역. deny-by-default | `[측정필요]` 실제 실행 |
| OpenShell provider profile | 추론 자격증명을 정책 밖에 두고 프록시가 주입 | `[측정필요]` 동일 |
| build.nvidia.com 스킬 카탈로그 | OpenShell 스킬 설치 | `[측정필요]` |

NemoClaw는 쓰지 않는다. 참조 스택이 요구하는 리소스와 검증 플랫폼이 이번 환경과 맞지 않고,
NemoClaw 문서 자체가 커스텀 이미지 워크로드는 OpenShell 단독 경로로 안내한다.
제출문에는 "OpenShell 정책을 직접 작성했고 NemoClaw는 참조 스택으로 검토했다"로 적는다.

### 후보별 추가분

| 후보 | 더해지는 NVIDIA 기술 | 더해지는 그 밖의 기술 |
|---|---|---|
| PharmaSignal | NeMo Retriever 임베딩 `nvidia/nemotron-3-embed-1b`(차원 2048)로 라벨 RAG. 리랭커는 이 계정 목록에 없어 뺐다. `[측정필요] 7` 미구현 | openFDA drug/event, DailyMed SPL REST v2, PubMed E-utilities. urllib와 xml.etree만 쓰는 도구 3종, 응답 파일 캐시 |
| Night Shift | 없음. 대신 OpenShell 정책의 쓰기 경로와 허용 도메인이 다르다 | git 실행기(브랜치, `git apply`, `format-patch`), AST 기반 규칙 크리틱 9종, coverage, 단일 파일 HTML 아침 보고서, 표적 저장소 boltons |

### 공통 비-NVIDIA 스택

Python 3.12, pytest 9.1.1, coverage 7.16.1, Docker 28 이상, Multipass Ubuntu 24.04 VM,
matplotlib(아키텍처 그림). 오프라인 테스트 128개가 통과하고 네트워크 테스트 3건은 별도 마커로 분리했다.

---

## 파일명 규칙과 제출 체크리스트

### 파일명 규칙

형식은 `[NVIDIA 해커톤_팀명_프로젝트명]`이다. 대괄호를 포함해 그대로 쓰고, 팀명은 폼에 적은 철자와
띄어쓰기를 글자 하나까지 맞춘다.

```
[NVIDIA 해커톤_<팀명>_PharmaSignal].pdf
[NVIDIA 해커톤_<팀명>_Night Shift].pdf
```

`[측정필요] 10` 팀명이 정해지면 `<팀명>` 자리를 채우고 이 줄을 확정한다.
프로젝트명에 띄어쓰기가 들어가는 Night Shift는 파일명에도 띄어쓰기를 그대로 둘지,
`NightShift`로 붙일지 제출 직전에 정해 폼 기재와 일치시킨다.

### 제출 전 점검

- [ ] 파일명이 `[NVIDIA 해커톤_팀명_프로젝트명]` 형식과 일치한다
- [ ] 파일명의 팀명 철자와 띄어쓰기가 폼에 적은 팀명과 글자 단위로 같다
- [ ] 신청서 이메일이 developer.nvidia.com 계정 이메일(kakyung.kim@gmail.com)과 같다
- [ ] 팀원 수만큼 구글 폼을 각자 제출했다(한 명이 몰아서 내지 않는다)
- [ ] 팀 구성 인원 항목을 폼 선택지에 맞춰 기입했다(1명일 때 기입 방법은 `[측정필요]`, PLAN의 미해결 항목)
- [ ] 개인정보 수집과 이용 동의 항목에 체크했다
- [ ] 문제 문안이 300자 ±10% 안에 있다
- [ ] 솔루션 문안이 500자 ±10% 안에 있다
- [ ] 기술 스택 문안에 NVIDIA 기술을 모델명, 라이브러리, 프레임워크 단위로 적었다
- [ ] 추가 URL의 데모 영상 링크가 외부에서 열린다(시크릿 창으로 확인)
- [ ] GitHub 저장소를 공개로 돌렸고 `.env`와 API 키가 이력에 없다
- [ ] 제출물의 모든 수치를 `eval/results/*.json`에서 다시 대조했다
- [ ] `[측정필요]` 항목 중 실행하지 못한 것을 "했다"로 적은 문장이 없다
- [ ] DLI S-FX-43 수료 증빙(수료증 또는 완료 화면 캡처)을 PDF에 넣었다
- [ ] 정책 밖 도메인 차단 로그 캡처를 제출물에 넣었다(못 얻었으면 그 사실을 적었다)
- [ ] 한국어 문안을 kr-style-polish로 한 번 더 윤문했다
- [ ] 9/28 18:00까지 제출을 마쳤다(마감 23:59 대비 여유)

### 제출물 구성

| 항목 | 내용 | 상태 |
|---|---|---|
| 구글 폼 Section 02 | 위 네 항목 | 이 문서의 확정 후보 문안 |
| PDF | README 요약, 아키텍처 그림, 실행 결과 수치, 정책과 차단 로그, DLI 수료 증빙 | 미작성 |
| 데모 영상 | 2~3분 | `[측정필요]` |
| GitHub 저장소 | 공개 전환 | 미전환 |
