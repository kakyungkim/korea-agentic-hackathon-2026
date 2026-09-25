# 팀원 제안 주제 실측: FDDD(초파리)와 Jev

2026-09-25 조사. 팀원이 제안한 두 주제의 실체를 직접 확인했다. `docs/notes/team.md:18-19`에
`[unverified]`로 남겨 둔 것을 메운다. 주제 선택 근거는 `docs/notes/topic-decision.md`에 있다.

## FDDD (초파리 뇌 아틀라스 기반 신약개발)

`drug.flybrain.kr`을 열고 정적 데이터 파일을 받아 확인했다. 이름은 **FDDD, Fly-driven drug
development**다. 사이트 메타 설명 원문은 아래와 같다.

> 20 fruit-fly brains (167,122 neurons each, MaleCNS) computed live in your browser, learning a
> preference over executed AutoDock Vina docking complexes. Real docking scores, real spikes,
> nothing faked.

### 규모

| 항목 | 값 |
|---|---|
| 도킹 타깃 | 3종. PARP1 촉매도메인(4R6E), 응고인자 Xa(2P16), 생쥐 COX-2(3LN1) |
| 화합물 | 6종. 15r, pamiparib, niraparib, rucaparib, celecoxib, apixaban |
| 도킹 조합 | 8건. 전부 `computed: true` |
| 도킹 도구 | AutoDock Vina 1.2.3, Webina/MolModa WASM, Node worker_threads |
| 재현 정보 | seed 20260914, exhaustiveness 4, cpu 1, num_modes 5, 박스 중심과 크기 명시 |
| 무결성 | 수용체, 입력, 포즈, 로그마다 SHA256. WASM 런타임 SHA256까지 |
| 참조 친화도 | BindingDB PARP1(UniProt P09874) 레코드 7,311건, 화합물 5,769종. Ki 1,194 / IC50 5,588 / Kd 214 / EC50 315 |
| 사람 PK | DailyMed 라벨. niraparib 반감기 50시간, 생체이용률 73퍼센트, 혈장단백결합 83퍼센트 |

데이터 경로는 `/data/docking/multi-target.json`, `/data/evidence/summary.json`,
`/data/malecns/*`다. `/api/docking/status`와 `/api/records`를 호출하는 코드가 있으나 전자는
404를 돌려준다. 도킹은 미리 계산해 정적 파일로 서빙한다.

### 도킹 점수 실측

| 타깃 | 화합물 | Vina (kcal/mol) | `role` 원문 |
|---|---|---|---|
| PARP1 (4R6E) | 15r | -13.093 | co-crystallized experimental PARP1 inhibitor |
| PARP1 (4R6E) | pamiparib | -11.085 | PARP inhibitor comparison |
| PARP1 (4R6E) | niraparib | -10.178 | co-crystal redocking control |
| PARP1 (4R6E) | rucaparib | -9.769 | PARP inhibitor comparison |
| COX-2 (3LN1) | celecoxib | -11.88 | Co-crystal ligand redocking control; crystal RMSD not calculated |
| COX-2 (3LN1) | niraparib | -6.605 | Exploratory cross-docking; no claim of validated binding |
| factor Xa (2P16) | apixaban | -10.248 | Co-crystal ligand redocking control; crystal RMSD not calculated |
| factor Xa (2P16) | niraparib | -7.967 | Exploratory cross-docking; no claim of validated binding |

### 가장 값어치 있는 것: 하지 말라고 적어 둔 해석

수치보다 이쪽이 중요하다. `multi-target.json`의 `notes` 배열에 데모가 스스로 금지한 해석이
8항목 있다. 원문을 옮긴다.

1. These are three DIFFERENT proteins, not three PARP1 structures. COX-2 structure 3LN1 is mouse,
   not human.
2. Raw Vina scores from different targets are NOT calibrated cross-target affinities. Do not
   globally rank targets or infer selectivity, Kd, Ki, IC50, efficacy, or fly response.
3. Niraparib on factor Xa and COX-2 is exploratory computational cross-docking, not evidence of
   experimentally confirmed binding.
4. Rigid published prepared receptors and ligands reused without local protonation changes.
   Single seed, exhaustiveness 4, no uncertainty/convergence analysis.
5. SMILES are molecular identity metadata, not the executed input. Connectivity SMILES can omit
   stereochemistry; preserved prepared PDBQT files define the exact executed structures.
6. Pose RMSD columns compare poses within each run, NOT to crystallographic ligand poses.
7. Use receptorPdbqt for the exact docking receptor; receptorPdb is the full original experimental
   entry and may contain additional chains, waters and co-crystal ligands.
8. All receptor/pose coordinates remain in their original Angstrom coordinate frame.

BindingDB 쪽에도 경고가 붙어 있다. "Ki, Kd, IC50 and EC50 are distinct endpoints and are NOT
pooled into one affinity score."

**이 목록이 크리틱 규칙과 부정 케이스를 동시에 준다.** 예를 들어 "niraparib은 PARP1에서 -10.178,
factor Xa에서 -7.967, COX-2에서 -6.605이므로 PARP1 선택성이 있다"는 주장은 숫자가 전부 맞고
근거 ID도 제대로 붙는다. 그런데 2번이 금지한 추론이고 두 건은 `role`에 "no claim of validated
binding"이라고 적혀 있다. **결정 규칙과 숫자 오라클을 모두 통과하고 LLM 크리틱만 잡을 수 있는
케이스다.** 지금 `eval/cases.jsonl`에 없는 바로 그 종류다.

### 두 주제가 이미 겹친다

FDDD가 **DailyMed 사람 라벨 PK를 이미 싣고 있다.** 화합물 6종 중 niraparib, rucaparib,
pamiparib, celecoxib, apixaban 다섯이 허가된 약이다. 즉 도킹 점수를 낸 그 화합물에 사람 라벨과
실제 이상사례 보고가 존재한다. 팀원이 구조에서 사람까지 잇는 쪽으로 이미 손을 뻗었고,
우리 약물감시 도구 3종이 거기에 그대로 들어간다. 억지 결합이 아니다.

## 초파리 접근법의 화제성과 한계

팀원이 공유한 링크 두 개와 도킹 쪽 독립 논평을 읽었다.

### 화제성

`aifficial.net`의 로봇과 게임 사례다. MaleCNS 수컷 중추신경계 뉴런 166,700개, 연결 2,500만 개를
써서 8족 로봇 보행, FPV 드론의 정면 장애물 회피, 카운터 스트라이크 2에서 11.4밀리초 반응 지연,
암호화폐 거래봇이 28시간에 55달러를 8,740달러로(15,800퍼센트), 블랙잭 6시간 연속 베팅이 있다.
마인크래프트 사례는 FlyWire 암컷 커넥톰(2024-10-02 Nature)으로 뉴런 139,255개, 시냅스 약
5,450만 개를 누출 적분 발화 모형으로 돌려 좀비를 피하고 발로 단맛을 느끼는 행동을 구현했다.

팀원이 "SNS에서 굉장히 화제가 많이 됐기 때문에 주목을 끌기에 좋다"고 한 근거가 실제로 확인된다.

### 한계

같은 글들이 한계도 분명히 적었다.

- 로봇 사례 편집장: "초파리가 인간의 의도를 이해하고 행동한다기보다는, 입력 신호와 모터 출력을
  엔지니어들이 영리하게 사상해 놓은 결과물에 가깝습니다."
- 마인크래프트 제작자: "게임에 연결된 것이 20퍼센트 남짓이고 나머지 80퍼센트는 무슨 일을 하는지
  모른 채 계속 신호를 주고받고 있다." 그리고 "배선도는 어디를 알려 주지만 언제는 알려 주지 않는다."

도킹 쪽 독립 논평은 Oxford Protein Informatics Group 블로그(2026-09)다. MaleCNS 중추뇌
38,128 뉴런, 시냅스 300만, 감각 뉴런 4,656개, 하행 뉴런 1,312개를 쓴다. 한 단계에 분자를 최대
0.5옹스트롱 옮기고 약 9도 돌리며 결정 구조에 2옹스트롱 안으로 들어오면 성공으로 본다.
저자는 staurosporine을 CDK2에 모든 시작 위치에서 도킹시켰다고 적으면서 동시에 "have we finally
solved drug discovery with a fly? Obviously not"이라고 못 박는다. 학습되지 않은 죽은 초파리의
뇌이고 하행 뉴런의 감각 의존 활동이 전체의 약 0.1퍼센트에 그친다고 했다.

### 판단

**초파리는 훅과 독창성에 강하고 실용성 단독으로는 약하다.** 커넥톰은 구조를 주고 동역학을 주지
않는다. 그래서 초파리를 결과의 권위로 세우지 않고 **여러 포즈 탐색 경로 중 하나로 두어
대조하는** 구성이 필요하다. 심사 2번 항목(실용성, 산업가치)은 초파리가 아니라 사람 근거 계층이
받는다.

### 뉴런 수가 자료마다 다르다

인용할 때 어느 커넥톰인지 함께 밝힌다. FDDD는 MaleCNS 167,122개, 로봇 사례는 MaleCNS
166,700개, 마인크래프트 사례는 FlyWire 암컷 139,255개, 도킹 논평은 MaleCNS 중추뇌 38,128개다.
같은 데이터의 다른 판본이거나 뇌 영역을 다르게 자른 것으로 보이나 확인하지 못했다 [unverified].

## Jev

실재하는 모델이다. `docs/notes/team.md:19`의 `[unverified]`를 아래로 대체한다.

### 실체

TypeSafe AI가 2026-09-15 얼리액세스로 냈다. 자기회귀 방식이 아니고 Transformer 기반이지만
자기회귀 생성 루프가 없다. 언어를 생성하는 대신 결정을 확률과 신뢰도로 직접 낸다.
RLCD는 Reinforcement Learning for Calibrated Decisions다.

### 성능 주장의 출처

공식 블로그 원문이 같은 수준의 프런티어 지능에서 "40x-200x faster"이고, 워크플로 평가에서
"193.6x faster, 444.6x cheaper"다. **저자들이 이 수치를 상단 추정치라고 스스로 밝혔다.**
비교 대상은 GPT-5.6 Terra, GPT-6 Astra, Fable 5.1이다.

팀원이 전한 "200배 빠르고 400배 저렴"은 이 상단 값에서 온 것으로 확인됐다. 문서에 인용할 때
출처와 상단 추정치임을 함께 적는다. **독립 검증 벤치마크는 찾지 못했고** 기술 세부 공개가
부족하다는 지적이 있다 [unverified].

### 접근 경로

가입이 불안정하다. 9/20에 전체 공개했다가 이틀 만에 수요로 가입을 멈췄다.

실측으로 우회 경로를 확인했다. **Vercel AI Gateway 공개 모델 목록에 `typesafe-ai/jev`가 있다.**
OpenRouter 목록에서는 찾지 못했다.

| 항목 | 값 |
|---|---|
| 모델 ID | `typesafe-ai/jev` |
| 소유 | typesafe-ai. 제공자에 digitalocean도 있음 |
| 형 | `evaluation` |
| 컨텍스트 | 32,000 |
| 가격 | 입력 백만 토큰당 0.042달러, 출력 0달러 |

### 중요한 제약: 채팅 모델이 아니다

게이트웨이가 돌려준 설명 원문이다.

> TypeSafe AI System One evaluation model. Accepts shared state and typed questions, returning
> choices, scores, and boolean probabilities. Limits: 64,000 tokens total per request; 32,000
> tokens for the state plus the longest question. No streaming or output-token limit.

`type`이 `evaluation`이다. **NAT의 `llms:` 자리에 넣을 수 없고 NAT 함수(도구)로 감싸야 한다.**
공유 상태와 타입 있는 질문을 주고 선택과 점수와 예/아니오 확률을 받는 형태다.

이 제약이 오히려 배치를 깔끔하게 만든다. Jev는 모델 교체가 아니라 판단 도구 한 개로 들어간다.

### 심사 불리 해소 방안

팀원이 걱정한 "다른 회사 모델을 핵심에 두면 불리"는 배치로 해소한다. 주 경로는 전부 NVIDIA로
두고 Jev를 **값비싼 NIM 호출 앞의 싼 분류기** 한 자리에 넣는다. 후보를 `screen`, `skip`,
`review`로 나누고 `review`만 Nemotron super로 넘긴다. 그리고 측정으로 정당화한다.

- 아낀 DiffDock 호출 수
- Jev 게이트의 지연과 Nemotron 단독 경로의 지연
- 두 경로의 판정 일치율
- Jev를 뺀 ablation에서 파이프라인이 그대로 도는지

빼도 도는 보조 부품이고 넣은 이유를 숫자로 대면 의존으로 읽히지 않는다. 못 쓰게 되어도
그 자리를 `nemotron-3.5-lightning`으로 채우고 "싼 모델이 1차 분류, 비싼 모델이 재검토"라는
같은 구조를 NVIDIA 안에서 보인다.

참고로 팀원이 Jev를 제안한 맥락은 팀장이 공유한 `architecture_pharmasignal.png`를 보고 그 구조에
얹는 안으로 낸 것이다. 즉 Jev는 처음부터 PharmaSignal 구조 위의 부품으로 제안됐다.

## 출처

- `drug.flybrain.kr`의 HTML 메타와 `/data/docking/multi-target.json`,
  `/data/evidence/summary.json` (직접 받아 확인, 2026-09-25)
- `aifficial.net/brain/posts/fly-brain-real-world-robot-hacking/`
- `aifficial.net/brain/posts/fly-brain-minecraft-connectome/`
- `blopig.com/blog/2026/09/finally-solving-drug-discovery-with-a-fly/`
- `typesafe.ai/blog/introducing-system-one-models-and-jev`
- `ai-gateway.vercel.sh/v1/models` (공개 목록, 직접 조회)
