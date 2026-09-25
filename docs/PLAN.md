# Korea Agentic AI Hackathon(NVIDIA x 패스트캠퍼스) 지원 계획

작성일 2026-09-24(목) 밤. 온라인 사전 챌린지 마감 **2026-09-28(월) 23:59**. 남은 시간 4일(추석 연휴 9/24~9/28).

## Context

사용자는 NVIDIA Korea Agentic AI Hackathon 온라인 사전 챌린지에 지원하려 한다. 심사는 제출한 데모 프로젝트로 하며, 항목은 (1) NVIDIA Agent 기술 활용 심도, (2) 실용성·산업가치·혁신성, (3) 완성도, (4) 커스터마이징·독창성이다. 본선 10팀이 10/7 오프라인 해커톤에 진출하고, 상위 5팀은 11/10 AI Day Seoul 무대에 선다. 우승팀은 DGX Spark와 NVIDIA 기술 블로그 소개를 받는다.

사용자 확인 사항(2026-09-24):
- 후보 두 개를 나란히 둔다. **후보 1 PharmaSignal**(약물감시 시그널 트리아지, 사용자 도메인), **후보 2 Night Shift**(밤새 스스로 실험하는 자율 코딩 에이전트, 개발자 커뮤니티 섭외용). 팀 구성 결과에 따라 하나를 고른다.
- 팀원을 구해야 하며, 못 구하면 개인으로 지원한다. 개발자 커뮤니티에 홍보한다.
- 시간은 최대한 쓰되 풀타임은 아니다.
- NVIDIA developer 계정과 build.nvidia.com API 키가 모두 없다.

조사로 확인한 기술 조건(미확인은 [unverified]):
- **교육 미션**: NVIDIA DLI 무료 과정 "Securing Agents with OpenShell and NemoClaw"(S-FX-43). 브라우저 기반, GPU 불필요, 4모듈 약 4시간. Brev 계정과 build.nvidia.com API 키 필요. 수료 증빙 방식 [unverified]. https://learn.nvidia.com/courses/course-detail?course_id=course-v1:DLI+S-FX-43+V1
- **"Skill API"**라는 엔드포인트는 없다. build.nvidia.com/skills는 SKILL.md 형식 에이전트 스킬 카탈로그(`npx skills add nvidia/skills`), 모델 호출은 NIM API(`https://integrate.api.nvidia.com/v1`, OpenAI 호환). 둘 다 사용해 어느 해석에도 맞춘다.
- **Nemotron 3** 호스팅 모델: `nvidia/nemotron-3-nano-30b-a3b`(tools, JSON schema), `nvidia/nemotron-3-super-120b-a12b`(tools, `enable_thinking` 토글), `nvidia/nemotron-3-ultra-550b-a55b`(코딩 하네스에 맞춰 후훈련). 가입 시 1,000 크레딧, 40 RPM 제한이 통설이나 상충 정보 있음. 개발 중 잔량 확인.
- **NVIDIA Agent Toolkit**은 (a) Nemotron, NIM, 스킬, NemoClaw, OpenShell을 묶은 우산 브랜드, (b) NeMo Agent Toolkit(NAT, `pip install nvidia-nat`, `nat run/serve/eval/mcp`, v1.8부터 Guardrails 미들웨어) 두 뜻. 둘 다 쓴다.
- **OpenShell**: deny-by-default 샌드박스 런타임. 파일시스템, 네트워크, 프로세스, 추론 라우팅을 YAML 정책으로 통제. Linux, macOS(Apple Silicon), WSL2 지원. **NemoClaw**는 그 위의 참조 스택(검증 플랫폼 DGX/WSL). NVIDIA 소개 블로그 제목은 "Run autonomous self-evolving agents more safely with NVIDIA OpenShell".
- 로컬은 **Intel Mac(i5, 16GB, GPU 없음)**, Docker 27, Python 3.12(openai 1.59), Node. 모델 추론은 전부 클라우드 NIM, OpenShell은 Linux VM(Multipass)이나 팀원 서버가 필요.
- 과거 수상작: NAT를 다른 NVIDIA 기술과 결합하고 에이전틱 동작을 시연한 팀이 상위. UCSC NemoClaw 해커톤은 "NVIDIA 도구 활용", "Nemotron 활용"을 별도 항목으로 채점.

기존 자산(팀장의 연구 자동화 작업물 autobiox): LLM 호출 코드는 없다. 재활용할 것은 `BioProject02/agents/critic/scripts/verify_citations.py`(Crossref·PubMed, urllib), `check_number_drift.py`, 그리고 "작성자와 검토자 분리" 크리틱 게이트 설계 패턴. BP02 데이터(TCGA/CPTAC)는 통제 접근이라 쓰지 않는다.

## 공통 하네스 (두 후보가 공유, 9/24~9/25에 먼저 만든다)

두 후보는 "Nemotron 작성자 워크플로 + 독립 크리틱 워크플로 + OpenShell 정책 + nat eval"이라는 뼈대가 같다. 도메인 도구만 다르다. 따라서 팀 결정 전에 뼈대를 먼저 만들어 어느 쪽으로 가도 첫 이틀이 버려지지 않게 한다.

- NAT 워크플로 2개: `author.yml`(계획과 실행), `critic.yml`(검증 전용, 쓰기 도구 없음). 도구는 NAT function으로 등록.
- 모델: 개발 루프와 반복 작업자는 `nemotron-3-nano-30b-a3b`, 계획과 크리틱은 `nemotron-3-super-120b-a12b`(thinking on). 구조화 출력은 JSON schema.
- OpenShell 정책 템플릿 `policies/base.yaml`: 쓰기는 `/work/out`만, 네트워크는 후보별 허용 도메인 목록 + `integrate.api.nvidia.com`. 차단 시도는 감사 로그로 남겨 README와 데모에 표시.
- 평가: `eval/cases.jsonl`에 정상 케이스와 "심어 둔 부정 케이스"를 섞고 `nat eval`로 크리틱 적발률을 숫자로 낸다.
- 가드레일: NemoGuard 토픽 제어를 NAT Guardrails 미들웨어로 연결(후보별 차단 주제 다름).
- 스킬: build.nvidia.com 스킬 카탈로그에서 OpenShell 스킬과 `nemo-retriever` 스킬을 설치해 사용했음을 README에 명시.

## 후보 1. PharmaSignal: 약물감시 시그널 트리아지 에이전트

**문제.** 약물감시(pharmacovigilance, PV) 담당자는 이상사례 자발보고 데이터(FDA FAERS), 허가 라벨(DailyMed SPL), 문헌(PubMed)을 수작업으로 대조해 "이 약물과 이 이상사례 조합이 새 시그널인가, 이미 라벨에 있는가"를 1차 판정한다. 조합 하나에 수 시간이 들고 근거 누락과 판단 편차가 잦다.

**흐름.** 약물명과 이상사례 입력 → Nemotron 계획 → 도구 호출(FAERS 집계, 라벨 검색, 문헌 검색) → 라벨 기재 여부, 불균형 지표(PRR, ROR은 Python이 계산), 문헌 근거를 담은 트리아지 메모 → 크리틱이 모든 주장에 레코드 ID가 붙었는지, 라벨 인용이 실제 라벨 텍스트에 있는지 검증 → 통과분만 사람에게, 실패분은 사유와 함께 반려.

**도메인 도구.** `openfda_faers`(api.fda.gov 카운트, 2x2표 PRR/ROR), `dailymed_label`(SPL 섹션 분할), `pubmed_search`(E-utilities, `verify_citations.py` 로직 재사용), `label_rag`(NeMo Retriever `llama-nemotron-embed-1b-v2` + `llama-nemotron-rerank-1b-v2`).
**정책 허용 도메인.** `api.fda.gov`, `dailymed.nlm.nih.gov`, `eutils.ncbi.nlm.nih.gov`, `integrate.api.nvidia.com`.
**가드레일.** 환자 개별 복약 조언 요청 차단.
**데모 케이스.** 라벨 기재됨, 라벨 미기재 시그널, 근거 불충분 각 1건 + 근거 없는 주장을 심은 조작 케이스 1건(크리틱 반려 시연).
**강점.** 산업가치가 분명하고 공개 API라 4일 안에 E2E가 된다. 사용자의 QA/RA 경험이 피칭 신뢰도를 높인다. **약점.** 개발자 섭외 훅이 약하다.

## 후보 2. Night Shift: 퇴근 후 내 저장소에서 밤새 스스로 실험하는 자율 코딩 에이전트

**문제.** 개발자는 코딩 에이전트를 밤새 돌려 두고 싶지만, 아침에 무엇을 지웠을지, 어디로 코드를 보냈을지 몰라 못 한다. 자율 에이전트의 가치는 무인 장시간 실행에 있는데, 그 장시간 실행을 안전하게 가두는 장치가 없다.

**흐름.** 저장소, 목표 묶음(테스트 커버리지 올리기, 느린 함수 개선, 타입 힌트 보강, 문서화), 시간·크레딧 예산, 금지 사항 입력 → 계획자(Nemotron super)가 실험 하나를 고름 → 작업자(Nemotron nano)가 OpenShell 샌드박스 안 저장소 사본의 실험 브랜치에서 패치 작성, 테스트와 벤치마크 실행 → 크리틱(별도 워크플로, 읽기 전용)이 검증: 테스트를 지우거나 skip으로 우회했는가, 커버리지가 떨어졌는가, 성능 개선은 3회 재측정에서도 유지되는가, diff 범위가 목표 안인가 → 통과 실험은 "아침 보고서"에 증거와 함께, 반려 실험은 사유와 함께 기록 → 예산 소진까지 반복.
**아침 보고서.** 실험별 카드(목표, diff 요약, 전후 수치, 크리틱 판정, 적용 명령 `git am`). 하단에 정책 감사 요약(차단된 네트워크·쓰기 시도 건수).
**정책 허용.** 쓰기는 `/work/repo`(사본)와 `/work/out`만. 네트워크는 패키지 레지스트리(`pypi.org`, `files.pythonhosted.org`)와 `integrate.api.nvidia.com`만. `github.com`을 허용 목록에서 빼서 원본 push가 구조적으로 불가능함을 보여 준다.
**가드레일.** 비밀 파일 접근, 외부 전송, 파괴적 명령을 요구하는 목표 입력 차단.
**데모.** 공개 Python 소형 라이브러리(테스트 있는 것) 1개를 골라 30~60분 실행을 영상에 타임랩스로 압축. 실험 10건 이상, 크리틱 반려 1건 이상(테스트 삭제 시도를 고의로 유도한 케이스 포함)을 보여 준다.
**NVIDIA 활용 심도.** Nemotron super/nano 역할 분담, NAT 워크플로와 `nat eval`(크리틱 적발률), OpenShell 정책과 감사 로그, NemoGuard, 스킬 카탈로그. NVIDIA가 OpenShell을 소개한 문구("자율 진화 에이전트를 더 안전하게")와 정확히 겹친다.
**강점.** 개발자 훅이 한 문장으로 서고 커뮤니티 섭외 효과가 가장 크다. 실용성과 독창성이 모두 높다. **약점.** 크레딧 소모가 큼(실험 1건당 모델 호출 6~10회, 1,000 크레딧이면 실험 100건 안팎). 장시간 실행을 3분 영상으로 압축해야 한다. OpenShell 실행 환경(Linux) 확보가 필수다.

## 후보 결정 기준

- **9/25(금) 밤까지 결정.** 개발자 팀원이 1명 이상 합류하고 Linux 서버 또는 VM에서 OpenShell이 동작하면 Night Shift. 합류자가 없거나 AutoBioX 멤버 위주면 PharmaSignal. OpenShell을 9/26 정오까지 어디서도 못 돌리면 Night Shift는 포기한다(정책이 핵심인 주제라 캡처 대체가 안 된다).
- 후보 2로 결정해도 PharmaSignal의 문제 정의는 신청서 "기타 URL"이나 README의 "다음 적용 도메인"으로 한 줄 남겨 사용자의 도메인 강점을 심사위원에게 보인다.

## 개발자 커뮤니티 홍보문 초안 (사용자 발신 글 규율 적용, 자판 밖 기호 없음)

> [팀원 모집] NVIDIA x 패스트캠퍼스 Korea Agentic AI Hackathon, 9/28 마감
>
> 추석 연휴에 Nemotron, NVIDIA NeMo Agent Toolkit, OpenShell로 에이전트 데모를 만들어 지원하려 합니다. 상위 5팀은 11월 NVIDIA AI Day Seoul 무대에서 발표하고, 우승팀은 DGX Spark를 받습니다.
>
> 주제는 둘 중 하나로 팀 구성에 맞춰 정합니다.
> 1. Night Shift: 퇴근 후 내 저장소에서 밤새 스스로 리팩터와 테스트 보강 실험을 하고, 아침에 증거를 붙인 PR 후보를 올리는 자율 에이전트입니다. OpenShell 샌드박스가 우리 역할을 해서 원본 브랜치와 외부 네트워크에는 손도 못 댑니다. 도메인 지식 없이 바로 기여할 수 있습니다.
> 2. PharmaSignal: 공개 데이터(FDA FAERS, DailyMed, PubMed)로 약물 이상사례 시그널을 1차 판정하는 에이전트입니다. 제약 현업 문제이고 제가 도메인을 맡습니다.
>
> 저는 바이오, 제약 데이터 분석 20년 경력이고 에이전트 하네스 설계 경험이 있습니다. 파이썬 개발자 1~2명을 찾습니다. LLM 도구 호출 경험이 있거나 리눅스 서버를 갖고 있으면 더 좋습니다. 각자 구글 폼을 제출해야 하니 9/27까지 합류해 주시면 됩니다. 관심 있으시면 DM 주세요.

게시 채널: 가짜연구소 디스코드, AutoBioX 스터디(지용기, 류재면은 Linux GPU 서버 보유), 사용자가 활동하는 개발자 커뮤니티. 게시는 사용자가 직접 한다.

## 일정

| 날짜 | 할 일 | 산출물 |
|---|---|---|
| 9/24(목) 밤 | developer.nvidia.com 계정을 **kakyung.kim@gmail.com**으로 생성(신청서 이메일과 일치 필수). build.nvidia.com API 키 발급, 크레딧 잔량 확인. Brev 계정 생성 후 DLI S-FX-43 등록. 홍보문 게시. 저장소 초기화, `pip install nvidia-nat[langchain]`, Nemotron nano 호출 1회 | API 키(.env, 커밋 금지), 홍보문 게시, hello-nemotron 실행 |
| 9/25(금) | DLI 4모듈 수강(약 4시간), 수료증 또는 완료 화면 캡처. 공통 하네스: author/critic 워크플로 뼈대, 정책 템플릿, eval 골격. Multipass Ubuntu VM에 OpenShell 설치 시도(팀원 서버 있으면 그쪽). **밤에 후보 결정** | 교육 미션 증빙, 하네스 뼈대 동작, OpenShell 설치 결과, 후보 확정 |
| 9/26(토) | 도메인 도구 구현. PharmaSignal이면 도구 3종 + 라벨 RAG, Night Shift면 실험 루프 + 테스트·벤치마크 실행기 + 크리틱 규칙. 케이스 E2E | E2E 결과 JSON, 크리틱 반려 예시 1건 |
| 9/27(일) | OpenShell 정책 적용과 차단 로그 확보. NemoGuard 연결. `nat eval` 수치. 아키텍처 그림(matplotlib, Pretendard, 뮤트 팔레트, PNG 직접 확인). 데모 영상 2~3분 | 정책 YAML, 평가 수치, architecture.png, 영상 URL |
| 9/28(월) | README 완성. 신청서 문안(문제 300자, 솔루션 500자, 기술 스택). PDF, 파일명 `[NVIDIA 해커톤_팀명_프로젝트명]`. 팀원 각자 폼 제출 확인. **18:00까지 제출** | 제출 완료 캡처 |

시간이 모자랄 때 줄이는 순서: 라벨 RAG 또는 벤치마크 재측정 → NemoGuard → UI(`nat run` CLI 출력으로 대체). **줄이지 않는 것**: Nemotron 도구 호출, 크리틱 검증, OpenShell 정책과 차단 로그, 교육 미션, 영상.

## 저장소 구조

```
<project>/
  src/<pkg>/tools/          도메인 도구
  src/<pkg>/{register.py, critic.py, schemas.py}
  configs/{author.yml, critic.yml, guardrails/}
  policies/{base.yaml, <candidate>.yaml}
  eval/{cases.jsonl, results/}
  scripts/{run_demo.py, hello_nemotron.py}
  docs/{architecture.png, submission.pdf}
  README.md
```

## 신청서 문안 방향 (최종 문구는 9/28 실측 수치로, kr-style-polish 후 확정)

- 서비스 명: 확정 후보 이름(팀 합류 후 변경 가능).
- 문제 300자: 현업 불편을 구체 장면으로. 수치는 출처 있는 것만.
- 솔루션 500자: 입력 → 계획 → 도구 → 계산은 코드가, 해석은 모델이 → 크리틱 검증 → 사람은 판단만. 정책으로 허용 도메인을 명시.
- 기술 스택: Nemotron 3 Super/Nano(NIM API), NeMo Agent Toolkit(워크플로, eval, Guardrails 미들웨어), OpenShell 정책, NemoGuard, build.nvidia.com 스킬, (PharmaSignal이면) NeMo Retriever 임베딩/리랭커. 그 외 Python 3.12와 데이터 소스.
- 추가 URL: 데모 영상.

## 검증

- 실행 결과는 `eval/results/*.json`에 남기고 README 수치는 그 파일에서만 가져온다.
- E2E: `nat run --config_file configs/author.yml --input ...`가 스키마에 맞는 산출물을 내고, 크리틱이 심어 둔 부정 케이스(근거 없는 주장 또는 테스트 삭제)를 반려하는지 확인.
- 샌드박스: 정책 밖 도메인(예: github.com push, example.com) 호출이 차단된 로그를 캡처해 README에 넣는다.
- 제출 전: 파일명 규칙, 팀명 띄어쓰기 일치, 이메일이 NVIDIA 계정과 일치, 팀원 수만큼 폼 제출, 개인정보 동의.

## 리스크와 공백

- [Gap:Procedural] 신청폼 "팀 구성 인원"은 2명부터 선택 가능. 1명이면 기입 방법이 불명확해 **최소 1명 합류가 사실상 필수**. 연휴라 고객센터 문의 불가. 못 구하면 2명 선택 후 비고에 개인 지원임을 적는 방안 검토.
- [Gap:Assumption] "Skill API"는 스킬 카탈로그와 NIM API를 뭉뚱그린 표현으로 추정. 둘 다 써서 대응.
- [Gap:Procedural] 교육 미션 완료 증빙 방식 미확인. 수료증과 캡처 모두 보관해 PDF에 첨부.
- Intel Mac에서 OpenShell 미지원. 팀원 서버 → Multipass VM → DLI 환경 순. Night Shift는 정책이 핵심이라 대체 불가, PharmaSignal은 캡처 대체 가능.
- NIM 크레딧과 RPM 제한. 작업자는 nano, 응답 캐시, eval 반복 제한. Night Shift는 실험 수 상한을 설정에 둔다.
- PharmaSignal의 의료 정보 오용 인식: "규제 제출용 판단이 아닌 1차 트리아지 보조" 명시.

## 승인 후 첫 실행 항목

1. 프로젝트 메모리에 결정 기록(후보 2개, 결정 기준과 시점, 마감, 계정 이메일 일치 규칙). 사용자 피드백 메모리: 선택형 팝업보다 텍스트로 후보를 제시하고 대화로 정하는 방식을 선호(2026-09-24, 세 차례 팝업 거절).
2. 홍보문을 kr-style-polish로 윤문해 전달. 게시는 사용자가 한다.
3. 저장소 초기화와 `hello_nemotron.py` 작성. API 키는 사용자가 발급해 `.env`에 넣는다(계정 생성은 사용자가 직접).

## 실행 중 확인된 사실 (계획 원본은 아래 그대로 둠)

계획 원본은 기록으로 남기고, 실행하며 달라진 것만 여기에 적는다. 2026-09-25 기준.

- **모델 ID.** 계획의 `nemotron-3-nano-30b-a3b` 는 2026-09-01 종료(410)다. 이름을 뒤집은
  `nemotron-nano-3-30b-a3b` 는 이 계정에서 404다. 실제로 쓰는 것은 작업자
  `nvidia/nemotron-3.5-lightning-30b-a3b`, 계획과 크리틱 `nvidia/nemotron-3-super-120b-a12b` 다.
- **NeMo Retriever 리랭커는 없다.** 이 계정의 모델 목록 82개에 rerank 계열이 하나도 없어
  신청서 기술 스택에서 뺐다. 임베딩은 `nvidia/nemotron-3-embed-1b`(차원 2048)가 동작한다.
- **NemoGuard 판정 모델은 시연하지 못했다.** 토픽 제어 모델은 HTTP 500(3회 동일),
  content-safety 계열은 타임아웃이다. `nvidia/nemotron-3.5-content-safety` 만 응답하나
  출력 형식이 레일 파서와 맞는지 미확인이다. 가드레일 계층 배선과 차단 주제 정의까지는 했다.
- **크리틱 적발률 1.0.** 구조화 출력을 `guided_json` 대신 `response_format` json_schema 로
  바꿔 LLM 경로가 동작한다. 정상 2건 pass, 심어 둔 부정 1건 reject.
- **선행 프로젝트 계보.** 2026-08 PharmaSignal v0(`github.com/kakyungkim/pharmasignal-v0`,
  미수상)의 후속임을 README 와 신청서에 밝힌다. v0 에서 ROR 오라클과 검증 지표, 영상과
  슬라이드 파이프라인을 가져왔다. 자세한 것은 `docs/notes/reuse-from-v1.md`.
- **카이제곱 정정.** Evans 등 2001 관례는 Yates 보정이다. 보정 없는 Pearson 을 쓰던 것을
  고쳤고 케이스 3건에서 판정이 뒤집힌 것은 없다.
