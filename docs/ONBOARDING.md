# 합류하신 분께

읽는 데 5분, 환경 준비에 15분이면 됩니다. 마감은 2026-09-28(월) 23:59이고 목표 제출은 18:00입니다.

## 무엇을 만드는가

**신약 후보물질을 검증하는 에이전트입니다.** 파이프라인이 구조에서 사람까지 이어집니다.

```
구조   타깃 단백질과 후보 화합물
  ↓
결합   NVIDIA DiffDock · AutoDock Vina 실측 · 초파리 커넥톰 포즈 탐색  (세 경로 대조)
  ↓
참조   BindingDB 실험 친화도
  ↓
사람   DailyMed 라벨 · FDA FAERS 이상사례 · PubMed 문헌
  ↓
검증   근거 ID 확인 → 숫자 대조 → 과잉해석 판정
```

**핵심 기여는 마지막 칸입니다.** 도킹 점수에는 문서화된 해석 한계가 있습니다. 서로 다른 타깃의
Vina 점수를 교차 비교할 수 없고, DiffDock 의 신뢰도는 친화도가 아니며, 교차 도킹은 결합의
증거가 아닙니다. LLM 에이전트는 이 한계를 자주 넘습니다. 근거 ID 도 붙고 숫자도 맞는데 결론만
틀린 요약을 냅니다. **그것을 잡는 크리틱**을 만듭니다.

규칙 13종은 지어낸 것이 아니라 도구 문서와 데이터 제공자 경고에서 옮겼습니다. 한 건은 우리가
직접 재서 넣었습니다. DiffDock 은 시드가 없어 같은 입력에도 신뢰도가 0.725 와 0.515 로 갈립니다.

배경과 결정 근거는 `docs/notes/topic-decision.md` 에 있습니다. 그 문서 하나면 맥락이 잡힙니다.

## 먼저 하실 일 세 가지

1. **구글 폼 제출.** 팀원도 각자 내야 합니다. 팀명은 띄어쓰기까지 똑같이 적어 주세요.
   폼에 적는 이메일은 **NVIDIA developer 계정 이메일과 같아야** 합니다. 계정이 없으면 먼저 만드세요.
   developer.nvidia.com 에서 My profile 의 Email 로 확인할 수 있습니다.
2. **build.nvidia.com 에서 API 키 발급.** 무료 크레딧으로 충분합니다. 키는 각자 보관하고 공유하지 않습니다.
3. **DLI 강좌 수강.** 사전 챌린지의 교육 미션입니다. 등록부터 진도 100%까지 필요한 것을
   `docs/COURSE-GUIDE.md` 에 모아 두었습니다. 그 문서 하나만 보시면 됩니다.

## 환경 준비

```bash
git clone <저장소 주소> && cd KoreaAgenticAIhackathon
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e . --no-deps
cp .env.example .env            # NVIDIA_API_KEY 를 채웁니다. .env 는 커밋되지 않습니다.
.venv/bin/python scripts/hello_nemotron.py     # 모델 연결과 도구 호출 확인
.venv/bin/python -m pytest -q -m "not network" # 오프라인 테스트
```

`hello_nemotron.py` 가 통과하면 준비가 끝난 것입니다.

## 지금까지 된 것 (2026-09-25 기준, 전부 실행으로 확인)

| 항목 | 값 |
|---|---|
| 오프라인 테스트 | 183개 통과 |
| NAT 에 등록된 도구 | 6개. `openfda_faers`, `dailymed_label`, `pubmed_search`, `diffdock_nim`, `prr_calculator`, `echo_tool` |
| 설정 검증 | 4종 전부 유효 |
| 에이전트 도구 호출 | 도구 3종 연속 호출, 근거 ID 붙은 JSON 산출 |
| DiffDock NIM | HTTP 200, 4초, 포즈 3개. `eval/results/diffdock_smoke.txt` |
| 샌드박스 | OpenShell 정책 적용과 차단 로그 9건 통과 |

- 약물감시 도구 3종이 공개 데이터로 동작하고 **에이전트가 실제로 부릅니다.**
  openFDA FAERS 집계와 불균형 지표, DailyMed 라벨 섹션 검색, PubMed 문헌 조회입니다.
- NVIDIA 생물학 NIM 호출 계층이 있습니다. 429 백오프와 응답 캐시가 들어 있어 재실행이 0.01초입니다.
- NeMo Agent Toolkit 워크플로 둘이 돕니다. 작성자와 크리틱을 나눴고 크리틱에는 쓰기 도구가 없습니다.
- OpenShell 정책을 리눅스 VM 에서 실제로 적용해 차단 로그를 받았습니다.

## 남은 일 (고르실 수 있습니다)

급한 순서입니다. 위쪽이 값어치가 큽니다.

| 일 | 필요한 것 | 예상 |
|---|---|---|
| **과잉해석 케이스 작성** | 도킹이나 약물 지식. 규칙 13종에 통과/반려 케이스를 한 쌍씩 | 반나절 |
| **남은 NIM 도구** `vina_reference`, `bindingdb_ref` | 파이썬. `bionemo_client.py` 를 그대로 씀 | 반나절 |
| **Jev 판정 게이트** | 파이썬. Vercel AI Gateway 계정 필요 | 두세 시간 |
| 데모 화면 또는 CLI 출력 정리 | 파이썬, 프런트 조금 | 반나절 |
| 데모 영상과 발표 자료 | 누구나. 제작 스크립트가 이미 있음 | 두세 시간 |
| 그림 2종 갱신 | 파이썬, matplotlib | 두세 시간 |

**리눅스 서버나 VM 이 있으면 알려 주세요.** 샌드박스 안에서 파이썬 도구가
`health.api.nvidia.com` 인증서 검증을 통과하는지가 아직 미확인입니다. 그것이 되면 샌드박스
안에서 파이프라인 전체를 돌린 증거를 낼 수 있습니다.

## 알아 두실 것

- 수치는 실행 결과에서만 가져옵니다. 문서에 적는 숫자는 방금 돌린 출력이나 결과 파일에서 나와야 합니다.
- 크리틱은 작성자와 분리합니다. 만든 사람이 자기 결과를 검증하지 않습니다.
- 이 도구는 규제 제출용 판단이 아니라 1차 트리아지를 돕는 보조입니다. 문서와 산출물에 그렇게 적습니다.
- **막히면 `docs/TROUBLESHOOTING.md` 를 먼저 보세요.** 제가 이미 겪고 푼 것을 그대로 적어 두었습니다.
  모델 ID 종료, 구조화 출력 400, Intel 맥에서 VM 생성 실패, 강좌 접속 오류가 들어 있습니다.
- **작업 하네스가 있습니다.** `.claude/` 에 에이전트 5명과 스킬 4개를 두었습니다.
  Claude Code 를 쓰시면 "이어서 해줘" 라고만 해도 지금 상태를 읽고 이어갑니다.
- **커밋에 AI 도구를 공동저자로 넣지 않습니다.** 각자 본인 GitHub 신원으로 커밋합니다.
- 저장소를 제출 직전 공개로 돌립니다. 팀원 실명과 키를 문서에 남기지 않습니다.
- 주제와 결정 근거는 `docs/notes/topic-decision.md`, 현재 상태는 `docs/HANDOFF.md`,
  기술 메모는 `docs/notes/` 에 있습니다. `docs/PLAN.md` 는 초기 계획 기록입니다.
