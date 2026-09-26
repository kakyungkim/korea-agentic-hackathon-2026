# 논문 계획: 도킹 출력의 과잉해석을 걸러내는 크리틱

2026-09-25 작성. 해커톤 제출과는 별개 갈래다. 순서와 시간 창은 `docs/notes/post-hackathon.md`에 있다.

> 선행연구와 발표 자리는 조사 중이다. 아래 해당 절에 결과를 채운다.

## 기여 한 문장

LLM 에이전트가 분자 도킹 도구에 붙어 후보물질을 요약할 때, **근거가 전부 맞는데도 추론이
도구의 문서화된 해석 한계를 넘는** 실패가 생긴다. 그 실패를 재는 벤치마크와 그 실패를 걸러내는
3단 크리틱을 낸다.

## 왜 새로운가

기존 환각 평가는 **근거의 사실성**을 잰다. 인용이 실재하는가, 숫자가 원문과 맞는가,
출처에 귀속되는가다. 우리가 재는 것은 다르다. **근거가 전부 맞을 때의 추론 타당성**이다.

부정 케이스가 이 차이를 보여 준다. niraparib 의 AutoDock Vina 점수가 PARP1 에서 -10.178,
factor Xa 에서 -7.967, COX-2 에서 -6.605 다. 전부 실측이고 근거 ID 도 제대로 붙는다.
그것으로 "PARP1 선택성이 있다" 고 주장하면 **숫자와 출처는 100퍼센트 맞고 추론만 틀린다.**
결정 규칙과 숫자 오라클을 모두 통과하고 LLM 판정만 이 주장을 반려한다.

두 번째 강점은 정답 라벨의 객관성이다. 계산화학에서는 해석 한계가 **도구 문서와 데이터 제공자
경고에 문장으로 적혀 있다.** 그래서 "이 주장은 넘었다" 는 판정이 주관적 취향이 아니다.

근거의 출처는 셋이다.

| 출처 | 내용 |
|---|---|
| FDDD 데모의 `notes` 배열 8항목 | 교차 타깃 순위 금지, 친화도 환산 금지, 교차 도킹 해석 금지 등 |
| NVIDIA DiffDock 문서 | "Do not convert confidence directly into binding affinity." |
| BindingDB 경고 | "Ki, Kd, IC50 and EC50 are distinct endpoints and are NOT pooled into one affinity score." |

원문은 `docs/notes/fddd-and-jev.md` 와 `docs/notes/bionemo-nim.md` 에 인용해 두었다.

## 우리가 실측으로 보탠 규칙

문서에서 옮긴 것만이 아니라 **직접 재서 추가한 규칙이 하나 있다.**

DiffDock 호스팅 API 에는 시드 파라미터가 없다. 같은 수용체와 리간드로 두 번 불러
`position_confidence` 가 `[0.798, 0.751, 0.725]` 와 `[0.761, 0.693, 0.515]` 로 갈렸다.
3순위 포즈에서 0.725 와 0.515 다. 그래서 "시드 없는 단일 호출에 재현성을 주장하면 반려" 를
규칙에 넣었다. 기록은 `eval/results/diffdock_smoke.txt` 와 `diffdock_client_run.txt` 에 있다.

이 항목이 논문에서 값이 크다. 남의 문서를 정리한 것이 아니라 우리가 측정한 것이다.

## 방법: 3단 크리틱

| 단 | 무엇을 보는가 | 성격 |
|---|---|---|
| 1단 결정 규칙 | 주장 존재, 근거 ID 유무와 빈 문자열 | 순수 파이썬. LLM 없음 |
| 2단 숫자 오라클 | 문면의 수치가 로그와 일치, SHA256 대조 | 순수 파이썬 |
| 3단 LLM 판정 | 추론이 도구 한계를 넘었는지 | 규칙 15종을 프롬프트에 실음 |

**1단과 2단을 먼저 걸고 통과한 것만 3단 LLM 에 넘긴다.** 두 경로 중 하나를 비-LLM 으로 고정해
상관 실패를 끊는다는 것이 설계 의도다. "같은 일을 두 번 하는 것 아닌가" 라는 질문의 답이기도 하다.

## 해커톤 규모에서 논문 규모로

지금 상태를 정직하게 적는다. **이대로는 논문이 안 된다.**

| 항목 | 지금 | 필요 |
|---|---|---|
| 평가 케이스 | 열 쌍 남짓 | 수백 쌍. 규칙 15종 × 타깃 여럿 × 화합물 여럿 |
| 도킹 데이터 | 타깃 3종, 화합물 6종, 조합 8건 | 표준 세트로 확장. 타깃 수십 |
| 모델 | Nemotron 하나 | 여럿. 모델 특성인지 문제 특성인지 갈라야 한다 |
| 정답 라벨 | 우리 판단 | **도메인 전문가 2명 이상의 일치도(kappa).** 팀에 박사급 두 분이 있어 강점이다 |
| 베이스라인 | 없음 | 셋. 크리틱 없는 LLM, "주의하라" 만 넣은 프롬프트, 결정 규칙만 |
| 거짓 양성 | 안 쟀다 | 통과 케이스를 반려한 비율을 함께 낸다 |
| 판정 이유 | 안 봤다 | **맞는 판정을 틀린 이유로 낸 것은 통과로 치지 않는다** |

### 베이스라인이 특히 중요하다

심사자가 가장 먼저 물을 것은 "프롬프트에 '조심해라' 한 줄 넣으면 되는 것 아닌가" 다.
그 베이스라인을 반드시 넣고, 우리 규칙 목록이 그보다 나은지 수치로 보여야 한다.
나아지지 않으면 그 사실을 적는다.

### 규칙 목록의 일반성

지금 규칙은 도킹과 약물감시에 특화돼 있다. 논문에서는 **규칙을 어떻게 얻는지의 절차**를
기여로 세우는 편이 낫다. 도구 문서와 데이터 제공자 경고에서 금지 추론을 추출하는 절차라면
다른 도구에도 적용된다. 그러면 사례가 하나여도 방법이 일반화된다.

## 선행연구

2026-09-25 조사. 원문에서 확인한 것과 초록만 본 것을 구분해 적는다.

### 먼저 읽을 것: 선점 위험 네 건

**1. SciRigor (arXiv:2609.06192, 2026-09-05). 가장 위험하다.**
과학 분석 에이전트의 주장이 자기 계산 결과로 뒷받침되는지를 typed evidence graph 로 재구성해
검사하고, 최종 정답 일치가 아니라 claim-support path 의 완결성을 점수로 매긴다고 보고되었다.
원문 문장을 그대로 옮긴다.

> On full-benchmark runs, agents' claims agree with their own results at nearly the same rate
> whether those results are faithful to the scientific target or not (91.8% versus 91.0%).

**우리 논지와 겹친다.** 내부 정합성만으로 과학적 정확성이 담보되지 않는다는 것이다.
검증 파이프라인도 프로그램 검사에 의미 매칭을 더한 혼합형이라 형태가 비슷하다.

갈라서는 지점은 셋이다. 도메인 여섯 가지에 **화학과 도킹과 신약개발이 없다**(경제와 정책,
컴퓨팅, 사회행동, 인지과학, 생명보건, 물리). 조작 방식이 결과 자체를 틀리게 만든 대비인데
우리 케이스는 **근거 ID 와 숫자가 전부 맞는 상태를 유지한다.** 그리고 그쪽은 주장이 산출물로
추적되는지를 보고 우리는 산출물이 완벽할 때 도구 문서가 허용한 해석 범위를 넘는지를 본다.

**2. TruthInsightBench (arXiv:2609.05079, 2026-09-04).**
정답과 기대값을 가린 blind task 40건에서 주장의 근거 성숙도를 6개 차원 29개 항목으로 LLM
심판이 채점한다고 보고되었다. 화학과 신약 도메인 포함 여부는 확인하지 못했다 [unverified].

**3. Granqvist, Mercado, Genheden (arXiv:2608.21057, 2026-08-21). 아키텍처가 걸린다.**
신약개발 에이전트 출력을 네 차원으로 LLM 심판이 채점하고 거기에 결정적 Tool Call Correctness
검사를 붙였으며, 심판을 조정해 인간 다수결과의 정렬을 0.80에서 0.86으로 올렸다고 보고되었다.
**"결정 규칙 다음에 LLM 판정" 이라는 구조 자체를 우리 신규성으로 주장하면 이 논문에 걸린다.**
다행히 채점 차원이 출력 품질이고 해석 한계 위반이 아니다.

**4. AgenticPosesRanker (arXiv:2605.03707, 2026-05-05).**
물리 기반 결정적 도구 여섯 종에 GPT-5 추론을 결합해 도킹 포즈를 순위 매기며, 162개 포즈
10개 시스템에서 best-pose 정확도 50퍼센트로 Smina 기준선과 같았다고 보고되었다.
재료가 우리와 같고 목적이 다르다. 이들은 포즈를 고르고 우리는 주장을 심사한다.

**인용 금지.** "Beyond SMILES: Evaluating Agentic Systems for Drug Discovery"(arXiv:2602.10163)는
arXiv 에서 철회되었다. 인용하지 않는다.

이름이 겹치지만 대상이 다른 것도 있다. Quantifying Overclaiming Propensity in Frontier LLM
Agents(arXiv:2609.20812)는 에이전트가 하지 않은 작업을 했다고 보고하는 빈도를 재는 것이고
과학적 추론 타당성이 아니다.

### 핵심 선행연구

| # | 문헌 | 연도 | 출처 | 우리와의 관계 |
|---|---|---|---|---|
| 1 | PoseBusters (Buttenschoen, Morris, Deane) | 2024 | Chem Sci 15(9):3130, 10.1039/d3sc04185a | **핵심 대비축.** 포즈 타당성 대 주장 타당성 |
| 2 | A Critical Assessment of Docking Programs and Scoring Functions (Warren 등) | 2006 | J Med Chem 49(20):5912, 10.1021/jm050362n | 교차 타깃 점수 비교 금지의 1차 근거 |
| 3 | Binding Affinity via Docking: Fact and Fiction (Pantsar, Poso) | 2018 | Molecules 23(8):1899, 10.3390/molecules23081899 | 친화도 환산 금지의 근거 |
| 4 | DiffDock (Corso 등) | 2023 | ICLR, arXiv:2210.01776 | confidence 의 정의를 원문으로 못 박음 |
| 5 | DiffDock 공식 저장소 FAQ | 접속 2026-09-25 | github.com/gcorso/DiffDock | 개발진이 친화도가 아니라고 명시 |
| 6 | Comparability of Mixed IC50 Data (Kalliokoski 등) | 2013 | PLoS ONE 8(4):e61007 | 종점 혼합 규칙. **방향이 일부 반대** |
| 7 | Cross-docking benchmark (Wierbowski 등) | 2020 | Protein Sci 29(1):298 | 교차 도킹 규칙. 본문 접근 실패 [unverified] |
| 8 | ChemCrow (Bran 등) | 2024 | Nat Mach Intell 6(5):525 | 에이전트 계보 + **LLM 심판 한계의 도메인 내 최강 근거** |
| 9 | Coscientist (Boiko 등) | 2023 | Nature 624:570 | 에이전트 계보 |
| 10 | BixBench (Mitchener 등) | 2025 | arXiv:2503.00096 | 인접 벤치마크. 과제 성공률 측정 |
| 11 | ALCE (Gao 등) | 2023 | EMNLP 2023 | 근거 사실성 계열 대표. 우리가 갈라서는 지점 |
| 12 | LLM-as-a-Judge, MT-Bench (Zheng 등) | 2023 | NeurIPS D&B, arXiv:2306.05685 | 3단 LLM 판정의 위험 문헌 |
| 13 | ROSCOE (Golovneva 등) | 2023 | ICLR, arXiv:2212.07919 | 도메인 무관 추론 타당성 평가 선례 |
| 14 | **A chemically-aware validation framework for benchmarking LLMs in materials synthesis planning** | 2026 | J Cheminform 18:100, 10.1186/s13321-026-01222-5 | **구조가 가장 가깝다. 반드시 읽을 것** |
| 15 | The limits of bio-molecular modeling with large language models | 2026 | Bioinformatics 42(8) btag550 | LLM 한계를 벤치마크로 드러내는 장르 선례 |

### 원문에서 확인한 수치

**PoseBusters [1].** 물리적 타당성과 RMSD 2옹스트롱 미만을 **동시에** 만족한 비율이다.

| 데이터셋 | DiffDock | AutoDock Vina | Gold |
|---|---|---|---|
| Astex Diverse (85 복합체) | 47% | 56% | 64% |
| PoseBusters Benchmark (308 복합체) | 12% | 58% | 55% |

결론 문장은 "no DL-based method yet outperforms standard docking methods when both physical
plausibility and binding mode RMSD is taken into account" 다.

**중요한 제약.** PoseBusters 원문에는 **점수와 친화도의 상관 논의가 없다.**
점수 해석 한계를 인용할 때 PoseBusters 를 쓰면 안 된다. [2]와 [3]으로 인용한다.

**Warren 등 [2].** 도킹 10종과 scoring function 37종을 8개 단백질에서 평가했다.
"For prediction of compound affinity, none of the docking programs or scoring functions made a
useful prediction of ligand binding affinity" 라고 보고되었다. 최대 상관은 Chk1 에서 r = -0.57
이었고 한 계열 안에서만 나타났으며 같은 표적의 다른 계열에서는 r = 0.0 이었다.

**Pantsar와 Poso [3].** 도킹이 친화도 추정에 맞는 도구인지 물은 뒤 "The short answer is no,
and this has been concluded in several comprehensive analyses" 라고 적었다.

**DiffDock [4][5].** confidence model 은 각 포즈의 RMSD 2옹스트롱 미만 여부를 라벨로 삼아
교차엔트로피로 학습된 이진 분류기다. 1위 예측이 RMSD 2옹스트롱 미만인 비율은 38퍼센트,
가장 확신한 3분의 1에서는 83퍼센트였다. 저장소 FAQ 원문은 "No, DiffDock does not predict the
binding affinity of the ligand to the protein. ... it is not a direct measure of it." 다.

**Kalliokoski 등 [6].** 서로 다른 assay 의 IC50 을 섞으면 표준편차가 0.68 log 단위(선형으로
약 4.8배)이고 같은 실험실 반복 측정은 0.22와 0.17이었다.

**ChemCrow [8].** 우리 3단에 직접 걸리는 경고다. "Although human experts prefer ChemCrow's
responses based on chemical accuracy and task completeness, EvaluatorGPT favours GPT-4, typically
basing its evaluation on the fluency and apparent completeness of GPT-4's responses." 저자들은
실제 지식이 필요한 과학 과제에서 LLM 평가가 전문가 평가를 대체할 수 없다고 덧붙였다.

### 남은 공백

1. **도구 문서가 명시한 해석 한계를 규칙으로 부호화한 평가가 없다.** 진술들이 문헌과 문서에
   흩어져 있고 에이전트 출력을 그것에 대고 기계적으로 검사하는 평가 집합은 확인되지 않았다
2. **근거가 전부 맞는 상태를 유지한 채 추론만 틀린 케이스가 도킹 도메인에 없다.**
   SciRigor 는 결과를 틀리게 만들어 대비했고 인용 검증 계열은 근거의 실재를 본다
3. **신뢰도의 의미 오용을 재는 항목이 없다.** confidence 의 학습 목표가 RMSD 이진 라벨임을
   명시한 원문과 실제 에이전트가 그것을 친화도로 환산하는 행동 사이의 간극이다
4. **과학 주장 평가가 생명화학 도구 생태계로 내려오지 않았다**
5. **도킹 호출의 시드 미지정 변동을 재현성 주장과 연결한 평가가 없다.** Vina 공식 FAQ 는
   같은 시드를 줘야 재현된다고 조건을 밝혀 두었으나 에이전트 행동을 규칙으로 잡은 평가는 없다

### 위치 설정

**새롭다고 말해도 되는 것**

- 도킹과 참조 데이터와 사람 라벨을 함께 쓰는 에이전트에서, **도구 제공자 문서와 평가 문헌이
  명시한 해석 한계를 규칙으로 부호화하고 위반을 측정한 것.** 이 형태의 규칙 집합은 확인되지 않았다
- **근거를 고정한 채 추론만 어긋뜨린 평가 케이스.** 근거 사실성 계열과 실제로 구분된다
- **같은 입력에 신뢰도가 0.725와 0.515로 갈린 실측.** confidence 가 RMSD 이진 분류라는 원문
  사실과 묶으면 임계값 기반 해석의 불안정을 보이는 구체 증거가 된다. **측정 조건(표본 수,
  시드 설정, NIM 버전)을 본문에 반드시 명시한다.** 지금 관측은 두 번뿐이다
- 대비축으로서 **포즈 타당성 대 주장 타당성은 성립한다**

**과대주장이 될 것**

- **"기존 환각 평가는 근거 사실성만 재고 우리가 처음 추론 타당성을 잰다" 는 이분법.**
  SciRigor 와 TruthInsightBench 가 2026년에 이미 주장의 정당성 축으로 옮겨 왔다.
  **도메인이 다르다는 점으로만 차별화하고 개념의 최초성은 주장하지 않는다**
- **결정 규칙 다음 LLM 판정이라는 구조의 신규성.** 이미 보고되었다. 구조가 아니라
  **판정 대상**(해석 한계 위반)으로 차별화한다
- **PoseBusters 를 점수 해석 한계 문헌으로 인용하는 것.** 원문에 그 논의가 없다
- **"Ki, Kd, IC50, EC50 을 합치면 안 된다" 는 강한 표현.** 대규모 활용에서는 혼합이 수용되고
  pKi 는 offset 보정으로 pIC50 을 보강할 수 있다고 보고되었다. 규칙을 **"보정과 불확실성
  0.68 log 표기 없이 단일 친화도로 합치는 것을 금지"** 로 좁혔다
- **규칙 15종을 "표준" 이라 부르는 것.** 뒷받침 강도가 규칙마다 다르다. 부록에 등급을 밝힌다
- **LLM 판정 단계의 신뢰도.** 같은 화학 도메인에서 LLM 평가자가 유창성에 끌린 보고가 있으므로
  사람 라벨과의 정렬 수치를 제시하지 않으면 3단 전체가 반박당한다. 기준선으로 0.86을 참고한다

### 규칙별 문헌 뒷받침 강도

2026-09-25 에 15종 전부로 늘렸다. 등급은 강함, 중간, 약함, 없음 넷이다. **없음은 규칙이 틀렸다는
뜻이 아니라 동료심사 문헌을 붙이지 않았다는 뜻이다.** 도구 문서와 구조 항목 수준의 사실에는
문헌을 억지로 붙이지 않았다. `confidence 를 친화도로 환산` 한 줄만 이전 표의 **매우 강함**을
그대로 남겼다. 원 논문, 개발진 FAQ, 벤더 문서가 같은 취지를 적어 둔 자리라 강함으로 내리면
사실과 어긋난다.

원본은 `src/harness/tools/overclaim_rules.py` 의 `literature_source` 와 `literature_quote` 이고,
이 표와 어긋나면 `tests/test_overclaim_rules.py` 가 잡는다.

| # | 규칙 (id) | 1차 근거 | 강도 |
|---|---|---|---|
| 1 | 교차 타깃 순위 금지 (`cross_target_ranking`) | Warren 등 [2] | 강함 |
| 2 | 친화도 환산 금지 (`affinity_conversion`) | Pantsar와 Poso [3], Warren 등 [2] | 강함 |
| 3 | 교차 도킹 해석 금지 (`cross_docking_binding`) | Wierbowski 등 [7], PoseBusters [1] | **약함.** 본문 미확인 [unverified] |
| 4 | 종 차이 명시 (`species_mismatch`) | 없음. 구조 항목 수준 | 없음 |
| 5 | 수렴 주장 금지 (`convergence_claim`) | AutoDock Vina 공식 FAQ, 우리 실측 | 중간. FAQ 원문 미대조 [unverified] |
| 6 | RMSD 기준 명시 (`rmsd_reference`) | PoseBusters [1] | 중간 |
| 7 | 종점 혼합 규칙 (`endpoint_merge`) | Kalliokoski 등 [6]. 방향 일부 반대 | 중간. 문구 수정 완료 |
| 8 | 입력 동일성 (`executed_input`) | 없음. 도구 문서 수준 | 없음 |
| 9 | 초파리 결과 해석 (`fly_response`) | OPIG 블로그 2026-09 | 약함. 동료심사 아님 |
| 10 | DiffDock 신뢰도 환산 금지 (`diffdock_confidence_affinity`) | Corso 등 [4], FAQ [5], NVIDIA 문서 | 매우 강함 |
| 11 | 도구 간 점수 혼용 금지 (`cross_tool_scale`) | Corso 등 [4] | 중간 |
| 12 | DiffDock 재현성 주장 금지 (`diffdock_reproducibility`) | Corso 등 [4], 우리 실측 | 중간. 우리 측정이 핵심 |
| 13 | DiffDock 음수 신뢰도 해석 금지 (`diffdock_negative_confidence`) | Corso 등 [4], 우리 실측 | 중간. 로짓 해석 [unverified] |
| 14 | 라벨 기재와 인과 구분 (`disproportionality_causality`) | 없음. 약물감시 실무 규율 | 없음 |
| 15 | 근거 범위 준수 (`evidence_scope`) | 없음. 근거 범위 규율 | 없음 |

강도별로는 강함 2종, 중간 6종, 약함 2종, 없음 4종이고 매우 강함이 1종이다.

**가장 약한 곳은 여전히 교차 도킹 규칙이다.** 자가 도킹 대비 교차 도킹의 성공률 하락을 수치로
밝힌 1차 문헌을 확보해야 한다. Wierbowski 등의 본문은 접근이 막혀 수치를 확인하지 못했다.
AutoDock Vina 공식 FAQ 도 같은 취지의 문장이 있다고 적어 두었으나 원문을 직접 대조하지 못했다.
둘 다 [unverified] 로 표시해 두었고 원문 확보가 다음 할 일이다.

### FDDD 가 빠져도 서는 규칙

FDDD 는 팀원 A 의 별도 저작물이라 팀 구성이 바뀌면 쓰지 못하게 된다. 그때 무엇이 남는지를
미리 갈라 두었다. 판단 기준은 하나다. 출처가 FDDD 가 아니거나 문헌 귀속이 붙어 있으면 선다.

| 상태 | 규칙 수 | 목록 |
|---|---|---|
| 문헌이나 NVIDIA 문서로 서는 규칙 | 12 | 위 표의 1, 2, 3, 5, 6, 7, 9, 10, 11, 12, 13, 14 |
| FDDD 단독 의존 | 3 | 종 차이 명시, 입력 동일성, 근거 범위 준수 |

이중 귀속 전에는 FDDD `notes` 를 출처로 둔 규칙이 10종이었고 그 10종이 모두 단독 의존이었다.
문헌을 함께 달아 **단독 의존이 10종에서 3종으로 줄었다.** 남은 3종은 종 차이, 실행 입력, 근거 범위를 다룬다.
문헌이 아니라 PDB 항목, 도구 입력 규격, 우리 실행 기록으로 대체한다.
대체 경로는 각 규칙의 `strength_note` 에 적어 두었다.

코드에서는 `FDDD_INDEPENDENT_RULE_IDS` 상수와 `fddd_independent_rules()` 로 꺼낸다.
FDDD 를 실제로 빼야 할 때는 그 목록만 쓰면 된다.

### 용어 통일 (원고 작업 전에)

단계 수를 **3단**으로 통일했다. 1단 결정 규칙, 2단 숫자 오라클, 3단 LLM 판정이다.
예전 메모에 "2단 크리틱" 이라 적힌 곳이 있으면 이 표기로 고친다.

## 발표 자리

2026-09-25 조사. **마감이 임박한 것부터 적는다.** 공식 페이지에서 확인한 것만 절대 날짜로 쓰고
나머지는 통상 시기로 적는다.

### 지금 결정할 것 (해커톤과 겹친다)

| 자리 | 마감 | 내는 것 | 판단 |
|---|---|---|---|
| **ACS Spring 2027 CINF 초록** | **2026-09-28 23:59 EST** | 초록만 | 심포지엄 "Rebuilding Public Trust in Chemistry: Information Validation, Addressing AI-Related Concerns" 가 우리 주제와 정면으로 맞는다. **다만 개최가 2027년 3월인데 마감이 지금이라 이례적으로 빠르다. 의존하기 전에 공식 페이지를 직접 확인한다** |
| **BIOINFO/GIW ISCB-Asia 2026 late-breaking 포스터** | **2026-09-30** | 초록만 | **서울 연세대 11/17~20 개최.** 기조강연 제목이 "Agentic AI for Drug Discovery with Physical and Biological Priors" 이고 튜토리얼에 "Agentic AI for In Silico Team Science" 가 있다. 청중이 정확히 겹치고 이동 부담이 없다 |
| AgenticLS @ NeurIPS 2026 | 2026-09-26 AoE | 정식 9p 또는 확장초록 4p | 주제는 맞지만 **내일이라 무리다** |
| KIPS ACK 2026 | 2026-09-30 | 2~4p | 원고를 써야 해서 이번 주에는 무리다 |

**초록만 내는 두 건은 원고를 새로 쓰지 않아도 되므로 해커톤과 병행할 수 있다.**

### 본선 직후

| 순위 | 자리 | 마감 | 분량 |
|---|---|---|---|
| 1 | **KIISE KSC 2026** (경주 12/21~23) | **2026-10-12** | 2~3p |
| 2 | **NVIDIA GTC 2027 포스터** (산호세 2027-03) | **2026-11-10 17:00 PT** | 포스터 |
| 3 | AAAI-27 워크숍 | CFP 가 2026-10-02까지 공개. 논문 마감은 11월 중순에서 12월 초 추정 [unverified] | 4~8p |
| 4 | **Journal of Cheminformatics** "AI and XAI in Drug Discovery" 컬렉션 | **2027-01-13 또는 2026-12-31** | 정식 논문 |
| 5 | ICLR 2027 워크숍 | 권장 **2027-02-01**. 워크숍 목록은 2026-11-29 확정 | 4~9p |

KSC 2026 이 일정상 가장 자연스럽다. **본선 5일 뒤 마감이라 본선에서 받은 지적을 반영할 시간이
있고 국내 프로시딩 실적이 남는다.**

GTC 2027 포스터는 마감이 **AI Day Seoul 무대 당일**이다. 심사 기준에 "NVIDIA 기술 적용" 과
"벤치마킹 방법론" 이 명시돼 있어 DiffDock 을 쓰는 이 연구가 요건을 그대로 충족한다.
하루 이틀 앞서 끝내 둔다.

### 닫힌 것

NeurIPS 2026 워크숍 라운드가 이미 닫혔다. 주제가 가장 잘 맞는 자리들이 여기 몰려 있었다.
ML4Molecules(Agentic Systems for Molecular Sciences) 8/29, AI for Science(Verification in the
Age of AI Scientists) 9/8, AI4DD 9/5, JUDGe(Can We Trust the Judge?) 8/29 다.
주최측 필수 통보일이 9/29라 재개방 여지가 없다.

**2027 회차를 노린다.** ML4Molecules 는 "부정 결과와 세심한 베이스라인과 엄밀한 대조를 특히
환영" 한다고 적어 두었다. 우리 성격과 맞는다. 마감은 8월 말 추정이다 [unverified].

### 학술지 비교

2026-09-25 심층 조사. 게재 실적을 Crossref 로 검증했다.

| 저널 | 맞는 유형 | 게재료 | 1차 결정 | 분량 | 적합도 |
|---|---|---|---|---|---|
| **Journal of Cheminformatics** | **Software**, Research, Methodology | £1,690 / $2,390 | **중앙값 9일** | Software 제한 없음 | **높음. 1순위** |
| **Digital Discovery** (RSC) | Full paper | £2,200 | 37일 | **제한 없음** | **높음. 2순위** |
| PLOS Computational Biology | **Research Article** (Benchmarking 아님) | $3,165 | 중앙값 41일 | 제한 없음 | 높음 |
| Patterns (Cell Press) | Resource | $4,900 | 회부 5일 | 느슨함 | 높음 |
| MLST (IOP) | **Benchmarks 전용 유형** | £2,500 | [unverified] | 8,500단어 | 높음 |
| JCIM (ACS) | Application Note, Article | [unverified] | [unverified] | App Note 5,000단어 | 중간. **스코프 조항 주의** |
| Bioinformatics (OUP) | Application Note 4쪽 | $3,625 | 중앙값 23일 | 약 2,600단어 | 중간. 분량이 빡빡하다 |
| JCAMD (Springer) | Original Paper | **구독 경로 $0** | [unverified] | [unverified] | 중간 |
| TMLR | regular submission | **무료** | 목표 9주 | 제한 없음 | 중간. 도메인 심사자 부재 위험 |

#### 1순위 근거: Journal of Cheminformatics

**거의 같은 구조의 논문을 2026년 5월에 실었다.** "A chemically-aware validation framework for
benchmarking large language models in materials synthesis planning", J Cheminform 18:100,
2026-05-24, `10.1186/s13321-026-01222-5` 다. 화학 지식을 아는 검증 틀로 LLM 을 벤치마킹한다는
구조가 우리와 겹친다. **선행연구로도 반드시 읽어야 한다.**

요건이 까다롭지만 우리에게는 부담이 아니다. 제3자가 완전히 재현할 수 있어야 하고, 소스를 OSI
승인 라이선스로 공개하고, 심사자가 익명으로 테스트할 수 있어야 한다. GPU 가 필요 없는 크리틱
모듈이라 맞춘다. 초록에 **"Scientific Contribution"** 절을 3문장 이내로 넣어야 한다.

문턱이 하나 있다. "기존 소프트웨어 대비 상당한 진전을 보여야 하고 보통 직접 비교로 입증한다."
그래서 베이스라인 셋이 필수다.

#### 2순위 근거: Digital Discovery

**분량 제한이 없어 수백 쌍 벤치마크를 온전히 담을 수 있다.** 게재료가 £2,200 이고, 코드와
데이터를 심사 중 심사자가 접근할 수 있게 하고 승인 시 Zenodo 에 영구 예치해 DOI 를 받는
요건이 우리 성격과 맞아떨어진다.

#### JCIM 은 사전 문의가 필요하다

공식 저자안내에 이런 조항이 있다.

> JCIM will not consider straightforward applications of molecular docking methods to a single
> target system without adequate experimental validation.

우리는 도킹 응용이 아니라 LLM 주장 검증이라 직접 저촉은 아니다. 다만 실험 검증을 중시하는 편집
기조와 부딪힐 여지가 있어 **투고 전 편집장 사전 문의를 권한다.** LLM 에이전트 신약탐색 논문의
중심지인 것은 맞다.

#### PLOS 는 유형 선택에 함정이 있다

Benchmarking 유형이 "저자가 벤치마크와 병행해 만든 신규 도구를 논문에 포함하지 말 것" 이라고
못 박는다. **크리틱 모듈과 벤치마크를 한 편에 담으려면 Benchmarking 이 아니라 Research Article
로 가야 한다.** Software 유형도 "이미 널리 채택되었거나 채택 전망" 을 요구해 신규 모듈로는 어렵다.

#### 장르 선례 하나 더

Bioinformatics 가 "The limits of bio-molecular modeling with large language models: a cross-scale
evaluation"(42(8) btag550, 2026-07-23)을 실었다. **LLM 의 한계를 벤치마크로 드러내는 장르를
이미 싣는다**는 증거다. 선행연구로 확인할 값이 있다.

#### 비용 현실

**한국은 Springer Nature, ACS, IOP 의 국가 기반 게재료 면제 대상이 아니다.** 공식 목록에서
직접 확인했다. 비용을 0원으로 하려면 TMLR(무료) 이나 JCAMD 구독 경로($0, 오픈액세스 아님)다.

**소속 기관이 전환계약(Read and Publish)에 포함되는지 도서관에 확인한다.** 포함되면 게재료가
0원이 되어 순위가 완전히 달라진다.

### arXiv 선공개

**시점은 본선(10/7) 직후, 늦어도 GTC 포스터 제출(11/10) 전이다.** 지금 후보 가운데 arXiv
선공개가 걸림돌이 되는 곳은 없다. NeurIPS 는 선공개를 공식 허용하고 ARR 은 2024-02-15부터
금지 기간을 없앴다.

카테고리는 **primary 를 cs.AI 또는 cs.LG 로 두고 q-bio.BM 하나만 교차 등록**한다.
arXiv 공식 안내가 과도한 교차 등록을 결례로 못 박았다. 유사 논문들도 한두 개만 쓴다.
도킹 해석 자체가 무게중심이면 physics.chem-ph 를 primary 로 돌린다. cs.CL 은 쓰지 않는다.
이 연구가 언어 처리 자체를 다루지 않는다.

### 주의할 점

- **국내 중복투고 제약.** ACK 2026 과 KSC 2026 에 같은 내용을 낼 수 없다. 하나만 고른다
- **J Cheminform 컬렉션 마감이 두 곳에서 다르다.** Springer 페이지는 2027-01-13,
  연계 워크숍 페이지는 2026-12-31 이다. **보수적으로 12-31 로 잡고 편집진에 확인한다**
- ICML 2027 과 NeurIPS 2027 은 공식 정보가 없다. 제3자 집계 날짜를 계획에 넣지 않는다
- ACS 초록의 단어 수 상한과 비회원 제출 가능 여부를 확인하지 못했다 [unverified]

### 팀이 정할 것

우선순위가 갈린다. **국내 프로시딩 실적인지, 국제 워크숍 노출인지, 피인용 가능한 학술지
논문인지**에 따라 1순위가 달라진다. 그리고 게재료 예산 상한이 완전 OA 를 감당할 수 있는지에
따라 학술지 후보가 절반으로 줄어든다. 코드와 벤치마크 데이터 공개 여부도 정해야 한다.
PLOS Software 는 OSI 라이선스를, Bioinformatics Application Note 는 2년간 무상 접근을 요구한다.

## 2026-09-26 재검토: 새 재료 둘과 선점 위험 하나

계획을 쓴 뒤에 재료가 둘 생겼고, 그것을 반영하려다 선점 위험을 하나 더 찾았다.

### 새 재료 1. 현장에서 실제로 일어난 과잉해석 사례

> 사례 목록과 확인 결과는 `docs/notes/real-world-cases.md` 로 옮겼다. 초파리 외에
> 아두카누맙 사례를 더했다. 약물감시 쪽 독자에게는 그쪽이 더 잘 닿는다.

지금 계획의 부정 케이스는 전부 우리가 만든 것이다. 심사자는 "이 실패가 실제로 일어나는가"를
묻는다. 그 답이 생겼다.

2026-09-12 에 올라와 12만 회 넘게 읽힌 게시물이 초파리 뇌를 훈련시켜 3상 약물을 합성하게
했다고 적었다. 그런데 그 데모가 쓰는 커넥톰 매니페스트를 직접 받아 보면 노드가 80개이고
엣지가 1,296개이며, 매니페스트 본문에 `"Not a physiological or whole-brain model."` 이라고
적혀 있다. 사이트 홍보 문구의 167,122 뉴런과 실제로 반응하는 그래프가 다르다.

**우리 주제와 구조가 같다.** 수치는 실재하고 데이터도 진짜인데 결론이 데이터가 받쳐 주는
범위를 넘는다. 그리고 그 범위를 **데이터 제공자가 스스로 문서에 적어 두었다.**

다만 도입 방식에 주의가 필요하다. 원문은 농담조이고 실명이 붙은 게시물이다. 이것을 논문의
중심 사례로 세워 특정인의 발언을 표적으로 삼으면 반발을 부르고 기여와도 어긋난다.
**동기 부여 절에서 중립적으로 한 문단만 쓰고, 측정은 도킹 벤치마크로 유지한다.**

값어치는 일반화에 있다. 기여가 도킹에만 걸린 이야기가 아니라 "산출물의 해석 한계가 문서에
적혀 있는 모든 계산 도구"로 넓어진다.

### 새 재료 2. 비용과 지연이라는 평가 차원

크리틱을 실제로 돌릴 수 있는지가 실용성 문제인데 지금까지 재지 않았다.
`scripts/bench_critic_judge.py` 를 만들어 케이스마다 판정과 지연과 토큰을 기록하게 했다.
기준선 측정을 2026-09-26 에 돌렸다.

이 축이 생기면 "판정 품질이 같다면 얼마나 싸게 돌릴 수 있는가" 를 물을 수 있다. 감시 대상이
많아질수록 이 질문이 커진다. 우리 데이터에서 니라파립과 혈소판감소증 조합 하나에 보고가
1,065건이고 같은 기간 전체 보고가 2천만 건대다.

### 선점 위험. 기권과 보정을 앞세우지 말 것

확률을 내는 분류기를 3단에 놓으면 임계값으로 기권 구간을 만들 수 있다. 매력적인 방향이라
기여로 삼고 싶어지는데, **2026년 기준으로 이미 붐비는 주제다.**

| 문헌 | 무엇 |
|---|---|
| Judge, Retrieve, or Abstain (COLM 2026, arXiv:2608.17994) | LLM 판정에 위험 보장을 붙이고 기권 대신 검색을 붙임 |
| SCOPE (arXiv:2602.13110) | 쌍 비교 판정에 conformal 선택 적용 |
| I-CALM (arXiv:2604.03904) | 신뢰도 기반 기권을 보상으로 유도 |
| SelectLLM (OpenReview) | 커버리지와 위험의 균형 보정 |
| Overconfidence in LLM-as-a-Judge (arXiv:2508.06225) | 판정자의 과신 진단과 해법 |

그래서 **기권 구간과 위험 커버리지 곡선은 기여가 아니라 방법의 한 부품으로만 쓴다.**
헤드라인으로 올리면 "이미 나온 것"이라는 지적을 받는다.

### 그래서 남는 우리 것

세 가지다. 이것이 계획의 기여 문장과 달라지지 않는다는 점이 오히려 좋다.

1. **정답 라벨이 주관이 아니다.** 무엇이 과잉해석인지를 도구 문서와 데이터 제공자 경고가
   문장으로 적어 두었다. 사람 주석자의 취향이 아니다. 이것이 방어선이다
2. **쌍으로 설계한 케이스.** 통과와 반려가 같은 근거 ID 와 같은 수치를 쓴다. 그래서 차이가
   오직 추론에서만 난다
3. **우리가 직접 잰 규칙 하나.** 시드 없는 DiffDock 의 호출 간 편차를 실측해 재현성 주장
   금지 규칙을 넣었다

여기에 이번 측정이 더해진다. 고정 규칙만으로는 16건 중 1건을 잡고 의미 판단을 붙이면 16건을
잡는다. **그 간격이 이 논문이 재는 대상 그 자체다.**

### 미확인 사항

- 보정된 확률을 내는 분류기를 3단에 실제로 붙여 보지 않았다. 접근이 아직 막혀 있다
- 위 선점 문헌 다섯 편의 본문을 읽지 않았다. 제목과 초록 수준에서만 확인했다
- 커넥톰 사례를 논문에 쓰려면 게시물 원문 인용 가능 여부와 표기 방식을 정해야 한다

## 정직한 한계 (논문에 그대로 적을 것)

- **사례가 하나의 도메인이다.** 도킹과 약물감시다. 다른 도구로 일반화했다는 증거가 없다
- **규칙의 출처가 좁다.** 2026-09-25 에 15종 중 11종에 문헌 귀속을 함께 달아 FDDD 단독 의존을
  10종에서 3종으로 줄였다. 남은 3종은 도구 문서 수준의 사실이라 문헌을 붙이지 않았고,
  교차 도킹과 Vina FAQ 두 자리는 원문을 확인하지 못해 [unverified] 로 남아 있다
- **정답 라벨을 저자들이 만들었다.** 일치도를 재야 하고, 규칙을 만든 사람이 케이스도 만들면
  순환이다. 규칙 작성자와 케이스 작성자를 갈라야 한다
- **LLM 판정의 신뢰도 자체가 문제다.** 3단이 LLM 이므로 그 한계가 우리 한계다
- **초파리 커넥톰 경로는 이 논문의 주장이 아니다.** 도킹 경로 하나로 취급하고
  효능이나 성능의 근거로 쓰지 않는다

## 저자와 기여

`docs/notes/credits.md` 의 층 구분을 따른다. 주제와 도킹 자산과 해석 한계 목록은 팀원 A,
하네스와 검증 체계와 약물감시 도구는 팀장이다. 저자 순서는 논문 착수 시점에 팀에서 정한다.

FDDD 는 팀원 A 의 별도 저작물이다. 논문에서도 복제하지 않고 인용하며, 데이터 출처와 SHA256 을
그대로 밝힌다.

## 다음 행동

1. ~~선행연구 조사 결과를 채운다~~ **완료.** 선점 위험 네 건을 위에 적었다
2. ~~발표 자리 후보와 마감일~~ **완료.** 단 아래 두 건은 원문 확인이 필요하다
   - J Cheminform 18:100(2026-05)을 읽는다. **구조가 가장 가까운 논문이다**
   - Bioinformatics btag550(2026-07)을 읽는다
3. ACS Spring 2027 초록 마감(9/28)이 해커톤 마감과 겹친다. **공식 페이지로 날짜를 먼저 확인한다**
4. 소속 기관 전환계약 포함 여부를 도서관에 확인한다. 게재료가 0원이 될 수 있다
3. 해커톤 제출과 본선을 마친 뒤(10/8 이후) 케이스 확장에 착수한다
4. 규칙 작성자와 케이스 작성자를 갈라 순환을 끊는다
