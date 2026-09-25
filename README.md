# Korea Agentic AI Hackathon 2026 (NVIDIA x 패스트캠퍼스)

온라인 사전 챌린지 제출 프로젝트. 마감 2026-09-28(월) 23:59. 계획 전체는 `docs/PLAN.md`.

후보 두 개를 공통 하네스 위에 올려 두고 팀 구성 결과에 따라 하나를 고른다.

| 후보 | 한 줄 | 상태 |
|---|---|---|
| PharmaSignal | 약물 이상사례 시그널을 공개 데이터로 1차 판정하는 트리아지 에이전트 | 도구 3종 실제 동작, 케이스 3건 수치 확보 |
| Night Shift | 밤새 저장소에서 스스로 실험하고 아침에 증거 붙인 PR 후보를 올리는 자율 에이전트. OpenShell이 울타리 | 실행기, 크리틱 규칙, 보고서 동작. 부정 패치 2건 반려 확인 |

## 배경과 계보

이 저장소는 2026-08-22 Agent Forge AI Hackathon Seoul에 낸 PharmaSignal v0의 후속이다. v0의 공개 저장소는 https://github.com/kakyungkim/pharmasignal-v0 이고 수상하지는 못했다. v0의 시그널 계산은 ClinicalTrials.gov의 이상사례만 보고 ROR을 냈다. 시판 후 자발보고 데이터베이스인 FAERS는 코드에서 한 번도 부르지 않았고, `code/src/pharmasignal/signal.py` 주석에도 "전체 시판 후 데이터베이스(FAERS 등)를 쓰는 정식 신호 탐지와는 규모가 다르다"고 한계로 적어 두었다. 허가 라벨 대조는 아예 없었고, 문헌은 검색 결과 제목만 긁는 수준이라 `research/01-novelty-assessment.md`의 4절과 5절에 미완 과제로 남겼다. 이번 PharmaSignal은 그 셋을 도구로 메운다. openFDA FAERS에서 2x2표를 만들고, DailyMed 라벨에서 기재 여부를 확인하고, PubMed에서 문헌을 모은다. 작성자와 독립 크리틱은 서로 다른 워크플로로 나누고, 실행은 OpenShell 정책 안에 둔다. v0이 쓴 Bright Data, Daytona, Nosana, Qwen은 이번에 하나도 쓰지 않아 스택이 전부 다르고, 지금 `src/harness/` 코드 중 v0에서 가져온 것도 사실상 없다. 물려받은 것은 문제 정의와 검증 설계다. v0도 생성 코드의 불일치율과 검증 커버리지를 직접 재서 `docs/11-measurement.md`에 남겼고, 그 측정 우선 원칙을 이번에도 이어 간다.

## 공통 하네스
- **Nemotron 3** (NIM API, `integrate.api.nvidia.com`): 계획자와 크리틱은 `nemotron-3-super-120b-a12b`, 작업자는 `nemotron-3.5-lightning-30b-a3b`
- **NeMo Agent Toolkit 1.9.0**: `configs/author.yml`(계획과 실행), `configs/critic.yml`(검증 전용), `configs/eval.yml`(적발률 평가기)
- **OpenShell**: `policies/`에 deny-by-default 정책 3종. 허용 도메인만 열고 차단 시도를 감사 로그로 남긴다
- **NeMo Guardrails**: NAT Guardrails 미들웨어로 정책을 올리고 차단 주제를 정의했다.
  판정 모델로 지정한 NemoGuard 토픽 제어는 호스팅 쪽 서버 오류로 응답하지 않아 차단 시연은 남아 있다

## 현재 확인된 것
- 오프라인 테스트 128개 통과 (`.venv/bin/python -m pytest -q -m "not network"`)
- NAT 설정 4종 `nat validate` 통과
- 크리틱 적발률 1.0 (`eval/results/critic_verdict_output.json`. 정상 2건 pass, 심어 둔 부정 1건 reject)
- Nemotron 3 모델 ID 실측. 계획서의 `nemotron-3-nano-30b-a3b`는 2026-09-01 종료라 작업자를 lightning으로 바꿨다
- PharmaSignal 케이스 3건: metformin과 유산산증 PRR 72.8 라벨 기재, semaglutide와 췌장염 PRR 7.2 라벨 기재, amoxicillin과 망막박리 PRR 0.87 라벨 미기재
- Night Shift 데모: 정직한 패치 1건 통과, 테스트 삭제와 skip 마커 패치 2건 반려

## 아직 못 한 것
- OpenShell 실제 실행 (Multipass VM 설치 필요, Intel Mac 호스트 직접 설치는 불가)

## 시작
```bash
cp .env.example .env            # build.nvidia.com 에서 발급한 키를 채운다
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e . --no-deps
.venv/bin/python scripts/hello_nemotron.py
.venv/bin/python -m pytest -q -m "not network"
```

키를 넣은 뒤 LLM 경로 확인:
```bash
set -a; source .env; set +a
.venv/bin/nat eval --config_file configs/eval.yml   # 적발률이 0.33 에서 1.0 이 되어야 한다
```

OpenShell 환경 준비는 `docs/notes/openshell-setup.md`.
설치와 실행에서 막히면 `docs/TROUBLESHOOTING.md` 에 겪은 문제와 해결책을 모아 두었다.
새로 합류하신 분은 `docs/ONBOARDING.md` 부터 보면 된다.
