# 기여 표기

저장소를 공개로 돌리므로 **실명을 쓰지 않는다.** 공개 산출물(README, 신청서 부속 문서, 발표)에는
역할과 GitHub 핸들로만 적는다. 실명이 필요한 곳은 각자 제출하는 신청 폼과 커밋 저작자 표기뿐이다.

층을 나눠 적는 것이 양쪽에 공정하다. 같은 일을 반으로 나눈 것이 아니라 서로 다른 층을 댔다.

## 층별 기여

| 층 | 내용 | 기여자 | 근거 |
|---|---|---|---|
| 주제와 훅 | 초파리 커넥톰을 신약개발에 붙이는 발상, 화제성 판단 | 팀원 A | 2026-09-25 팀 논의에서 제안 |
| 도킹 자산 | FDDD 데모. 타깃 3종, 화합물 6종, AutoDock Vina 1.2.3 실행 8건, 수용체와 포즈와 로그의 SHA256, BindingDB 참조, DailyMed PK | 팀원 A | `drug.flybrain.kr`, `docs/notes/fddd-and-jev.md` |
| 해석 한계 목록 | 하지 말아야 할 해석 8항목. 우리 크리틱 규칙의 뼈대가 됨 | 팀원 A | FDDD `multi-target.json` 의 `notes` 배열 |
| Jev 접목 제안 | 판단 전용 모델을 파이프라인에 얹는 구성 | 팀원 A | 공유된 아키텍처 도식을 보고 제안 |
| 약 도메인 검토 | 라벨 읽기, 약 정보 정합, 약사 관점 | 팀원 B | |
| NAT 하네스 | 작성자와 크리틱 분리, 근거 ID 검증 구조, 도메인 중립 코어 약 500줄 | 팀장 | `src/harness/` |
| 약물감시 도구 | openFDA FAERS 집계와 불균형 지표, DailyMed 라벨 섹션, PubMed 문헌, ROR 오라클 | 팀장 | `src/harness/tools/pharmasignal_*.py` |
| 샌드박스 | OpenShell 정책과 차단 로그, provider profile 자격증명 격리 | 팀장 | `policies/`, `eval/results/openshell_smoke*.txt` |
| 평가 체계 | `nat eval` 적발률, 크리틱 판정 평가기 | 팀장 | `src/harness/evaluators.py` |
| NIM 통합 | 생물학 NIM 접근 확인과 호출 계층, DiffDock 도구 | 팀장 | `docs/notes/bionemo-nim.md`, `eval/results/diffdock_smoke.txt` |
| 과잉해석 크리틱 | 규칙 15종과 부정 케이스, 3단 판정 | 팀장 설계, 팀원 A 의 목록을 출처로 | `docs/notes/topic-decision.md` 규칙 표 |
| 제작 파이프라인 | 영상 9단계, 이중언어 슬라이드, 그림 생성 | 팀장 | `assets/`, `scripts/make_figures.py` |

## 선행 프로젝트 계보

**계보를 숨기지 않는다.** 이 저장소의 결정 사항이다.

PharmaSignal v0(`github.com/kakyungkim/pharmasignal-v0`, 2026-08 Agent Forge AI Hackathon Seoul
제출, 미수상)의 후속이다. v0 에서 ROR 오라클과 검증 지표, 영상과 슬라이드 파이프라인을 가져왔다.
자세한 것은 `docs/notes/reuse-from-v1.md`.

FDDD 는 팀원 A 의 별도 저작물이다. 이 저장소가 그것을 복제하지 않고 **도구로 참조한다.**
데이터 출처와 SHA256 을 그대로 인용하고 원 저작물을 링크로 밝힌다.

## 외부 자산

| 자산 | 출처 | 라이선스 |
|---|---|---|
| AutoDock Vina 실행 결과와 준비된 수용체 | Durrant Lab webina, MolModa | 해당 저장소 표기를 따름 |
| 수용체 구조 4R6E, 2P16, 3LN1 | RCSB PDB | 공개 |
| BindingDB 참조 친화도 | BindingDB REST | 해당 사이트 표기를 따름 |
| NVIDIA BioNeMo 에이전트 스킬 문서 | NVIDIA-BioNeMo/bionemo-agent-toolkit | 문서 CC-BY-4.0, 코드 Apache-2.0. **출처 표기 필요** |
| Pretendard 폰트 | orioncactus/pretendard | OFL |
| 초파리 커넥톰 | MaleCNS, FlyWire | 각 배포처 표기를 따름 |

## 커밋 저작자

`kakyungkim <kakyung.kim@gmail.com>` 하나다. AI 도구를 공동저자나 생성자로 적지 않는다.
다른 팀원이 직접 커밋하면 각자의 GitHub 신원으로 남긴다.

## 신청서와 README 에 쓸 문장

> 주제와 초파리 도킹 경로는 팀원 제안이고, 에이전트 하네스와 검증 체계는 선행 프로젝트에서
> 이어 온 자산입니다. 두 층을 하나의 파이프라인으로 이었습니다.

이 문장을 `submission-writer` 가 문체에 맞춰 다듬어 쓴다.
