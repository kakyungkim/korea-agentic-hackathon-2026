# 작업 노트 색인

주제별 폴더 여섯 개로 나눠 두었다. **처음 읽는다면 `06-project/topic-decision.md` 부터
본다.** 무엇을 왜 만들기로 했는지가 거기 있다.

| 폴더 | 무엇 | 파일 |
|---|---|---|
| `01-domain/` | 약물감시 도메인 | 5 |
| `02-judging/` | 판정 모델과 트리아지 | 5 |
| `03-structure/` | 시판 전 구조 예측과 도킹 | 6 |
| `04-platform/` | NVIDIA 스택과 에이전트 껍데기 | 8 |
| `05-research/` | 논문화와 문헌 | 4 |
| `06-project/` | 팀, 일정, 제출 | 12 |
| `dli-course/` | NVIDIA DLI 강좌 수강 정리 | 별도 |

## 01-domain: 약물감시 도메인

| 파일 | 무엇 |
|---|---|
| `causality-assessment.md` | WHO-UMC, Naranjo, 한국형 알고리즘. 인과성 평가 체계 비교 |
| `pv-datasets.md` | FAERS, DailyMed, PubMed, 참조 세트. 접근 경로와 실측 응답 |
| `real-world-cases.md` | 현장에서 실제로 일어난 과잉해석. 초파리 커넥톰과 아두카누맙 |
| `report-form-mapping.md` | 국내 이상사례 보고 서식과 데이터 필드 대응 |
| `case-drug-review-2026-09-27.md` | 사례 약물 선정. 바이옥스 0건 대 44,279건 문제 |

## 02-judging: 판정 모델과 트리아지

| 파일 | 무엇 |
|---|---|
| `jev-primer.md` | Jev 개념과 규격. 공급사 주장과 회의적 시각을 나눠 적었다 |
| `jev-triage-2026-09-27.md` | Jev 첫 실측. 10건 벤치마크와 Nemotron 비교 |
| `triage-scale.md` | 트리아지 확장 측정과 결정 정책 |
| `measurement-2026-09-27.md` | 측정 설계 전반. 가림, 기준선, 시점 고정 |
| `evidence-grade-2026-09-28.md` | 근거 등급 A~D 시제품. 두 번 틀린 기록과 약사 지적 |

## 03-structure: 시판 전 구조 예측과 도킹

| 파일 | 무엇 |
|---|---|
| `bionemo-nim.md` | NIM 네 종의 호출 규격과 함정. 인자 이름 차이 목록 |
| `openfold3-2026-09-27.md` | 구조 예측 실측 |
| `structure-rules-2026-09-27.md` | 구조 예측 해석 규칙 2종 |
| `fddd-and-jev.md` | 도킹 서비스와 판정 모델의 배치 판단 |
| `fddd-teardown.md` | 도킹 서비스 응답 분해와 주의 8항목 |
| `rule-contribution-2026-09-27.md` | 규칙 기여 경위와 출처 귀속 |

## 04-platform: NVIDIA 스택과 에이전트 껍데기

| 파일 | 무엇 |
|---|---|
| `nvidia-skills.md` | 스킬 규격 기초 |
| `nvidia-skills-catalog.md` | 카탈로그 382개 중 고른 것과 그 사유 |
| `openshell-setup.md` | 샌드박스 설치와 정책. 스모크 테스트 9항목 실측 |
| `nat-harness.md` | NeMo Agent Toolkit 워크플로 구성 |
| `skill-packaging.md` | 우리 기능을 스킬 규격으로 포장하기 |
| `pharmasignal-tools.md` | 약물감시 도구 모듈 목록 |
| `nightshift-components.md` | 후보에서 뺀 주제의 부품 기록 |
| `reuse-from-v1.md` | 앞 버전에서 가져올 것 검토 |

## 05-research: 논문화와 문헌

| 파일 | 무엇 |
|---|---|
| `paper-plan-pv.md` | **약물감시 본편 계획.** 논지, 실험 6종, 투고처와 비용 |
| `paper-plan.md` | **도킹 과잉해석 편 계획.** 본편과 합치지 않는다. 독자와 투고처가 다르다 |
| `lit-survey-2026-09-29.md` | 선행연구 조사. 카파 0.22 정정과 선점 위험 셋 |
| `lessons-2026-09-28.md` | 프로젝트에서 배운 것 6부. AI 전달이 무너지는 지점 포함 |

## 06-project: 팀, 일정, 제출

| 파일 | 무엇 |
|---|---|
| `topic-decision.md` | **결정 근거와 게이트와 일정의 원본** |
| `credits.md` | 사람 기여 표기 |
| `team-repo-conventions.md` | 팀 저장소에 기여할 때의 규약 |
| `figures.md` | 그림 목록과 생성 방법 |
| `flyvigilante-review-2026-09-28.md` | 팀 데모 검토 |

## 이 폴더의 규약

- **문서 한 편은 주제 하나.** 여러 주제가 섞이면 나눈다
- **날짜가 붙은 이름은 그날의 측정 기록이다.** 날짜 없는 이름은 계속 갱신하는 문서다
- **수치는 실행 출력에서만 가져온다.** 확인 못 한 것은 `[unverified]` 로 표시한다
- **못 한 것과 실패도 적는다.** 지우면 다음 사람이 같은 실수를 한다
- 파일을 옮기면 참조도 함께 고친다. 이 저장소에 `docs/notes/` 참조가 224건 있다
