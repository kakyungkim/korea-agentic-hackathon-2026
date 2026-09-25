# 합류하신 분께

읽는 데 5분, 환경 준비에 15분이면 됩니다. 마감은 2026-09-28(월) 23:59입니다.

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

## 지금까지 된 것

- 약물감시 도구 3종이 공개 데이터로 실제 동작합니다. openFDA FAERS 집계와 불균형 지표 계산,
  DailyMed 라벨 섹션 분할과 반응명 검색, PubMed 문헌 조회입니다.
- 케이스 3건을 실행해 결과를 `eval/results/pharmasignal_cases.json` 에 남겼습니다.
  metformin 과 유산산증은 PRR 72.8 에 라벨 박스 경고 기재, amoxicillin 과 망막박리는 PRR 0.87 에 라벨 미기재입니다.
- NeMo Agent Toolkit 워크플로 뼈대가 섰습니다. 작성자와 크리틱을 나눠 두었고, 크리틱은 쓰기 도구가 없습니다.
- OpenShell 정책 3종을 썼습니다. 허용 도메인만 열고 나머지는 막는 구조입니다.

## 남은 일 (고르실 수 있습니다)

| 일 | 필요한 것 | 예상 |
|---|---|---|
| 케이스 선정과 결과 검증 | 약물감시나 RA 실무 감각 | 도메인 |
| 데모 화면 (간단한 웹 UI 또는 CLI 출력 정리) | 파이썬, 프런트 조금 | 반나절 |
| OpenShell 샌드박스 실행과 차단 로그 확보 | 리눅스 환경 또는 VM | 두세 시간 |
| 라벨 검색 품질 개선 (임베딩 기반 검색) | 파이썬 | 반나절 |
| 데모 영상과 발표 자료 | 누구나 | 두세 시간 |

## 알아 두실 것

- 수치는 실행 결과에서만 가져옵니다. 문서에 적는 숫자는 방금 돌린 출력이나 결과 파일에서 나와야 합니다.
- 크리틱은 작성자와 분리합니다. 만든 사람이 자기 결과를 검증하지 않습니다.
- 이 도구는 규제 제출용 판단이 아니라 1차 트리아지를 돕는 보조입니다. 문서와 산출물에 그렇게 적습니다.
- **막히면 `docs/TROUBLESHOOTING.md` 를 먼저 보세요.** 제가 이미 겪고 푼 것을 그대로 적어 두었습니다.
  모델 ID 종료, 구조화 출력 400, Intel 맥에서 VM 생성 실패, 강좌 접속 오류가 들어 있습니다.
- 자세한 계획은 `docs/PLAN.md`, 현재 상태는 `README.md`, 기술 메모는 `docs/notes/` 에 있습니다.
