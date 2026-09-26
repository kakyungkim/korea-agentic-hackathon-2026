# 규칙별 반려 분포와 표기 변동에 대한 판정 안정성

2026-09-27 측정. 논문 단계에 쓸 자료다. 제출물은 손대지 않았고 결과 파일은 새 이름으로 썼다.

측정 A는 기존 실행 결과를 다시 집계했고, 측정 B는 이 날 새로 호출해 얻었다.
모델은 `nvidia/nemotron-3-super-120b-a12b`, 온도 0.0, `enable_thinking` false이며 설정은
`configs/eval.yml` 그대로다. 측정 B는 데이터셋 경로와 출력 경로만 덮어써 돌렸다.

| 산출물 | 경로 |
|---|---|
| 측정 A 집계 | `eval/results/rule_attribution_2026-09-27.json` |
| 측정 B 집계 | `eval/results/notation_robustness_2026-09-27.json` |
| 측정 B 변형 데이터셋 | `eval/results/notation_robustness_cases_{original,brand,code}.jsonl` |

---

## 측정 A. 규칙별 반려 건수와 사유 대응

### 측정 배경

Aljamaan 등이 챗봇 다섯 종의 참고문헌 환각을 재면서, 기계로 대조되는 서지 항목 여섯 개는
카이제곱 199.9에서 341.1로 도구를 뚜렷하게 갈랐는데 판단이 필요한 유일한 항목인 주제 관련성만
10.77(p=0.03)로 구분력이 떨어진 것을 보고했다(JMIR Med Inform 2024;12:e54345, 표 원문 확인).
우리 규칙이 그 함정을 피했다고 말하려면 규칙별 분포가 있어야 한다. 특정 규칙 한둘이 16건을
다 잡고 나머지가 쉬고 있으면 "규칙 15종"이라는 표현이 과장이 된다.

### 집계 방법

`eval/results/workflow_output_llm.json`의 3단 응답에서 `passed=false`인 체크를 모두 뽑아
체크 이름을 `src/harness/tools/overclaim_rules.py`의 `RULES` 15종에 대응시켰다. 모델이 이름 앞에
번호를 붙이기도 하고 빼기도 해서 앞머리 번호를 지운 뒤 규칙 이름으로 맞췄다. 대응에 실패한
이름은 0건이었다. 판정 일치 여부는 `critic_verdict_output_llm.json`을 그대로 썼다.

### 규칙별 분포

| # | 규칙 ID | 부정 케이스 발동 | 자기 케이스 | 정상 케이스 오발 | 발동한 케이스 |
|---|---|---|---|---|---|
| 1 | `cross_target_ranking` | 2 | O | 0 | `cross_target_ranking_reject`, `cross_docking_binding_reject` |
| 2 | `affinity_conversion` | 2 | O | 0 | `affinity_conversion_reject`, `diffdock_confidence_affinity_reject` |
| 3 | `cross_docking_binding` | 1 | O | 0 | `cross_docking_binding_reject` |
| 4 | `species_mismatch` | 1 | O | 0 | `species_mismatch_reject` |
| 5 | `convergence_claim` | 1 | O | 0 | `convergence_claim_reject` |
| 6 | `rmsd_reference` | 1 | O | 0 | `rmsd_reference_reject` |
| 7 | `endpoint_merge` | 2 | O | 0 | `endpoint_merge_reject`, `cross_docking_binding_reject` |
| 8 | `executed_input` | 1 | O | 0 | `executed_input_reject` |
| 9 | `fly_response` | 1 | O | 0 | `fly_response_reject` |
| 10 | `diffdock_confidence_affinity` | **0** | **X** | 0 | 없음 |
| 11 | `cross_tool_scale` | 1 | O | 0 | `cross_tool_scale_reject` |
| 12 | `diffdock_reproducibility` | 1 | O | 0 | `diffdock_reproducibility_reject` |
| 13 | `diffdock_negative_confidence` | 1 | O | 0 | `diffdock_negative_confidence_reject` |
| 14 | `disproportionality_causality` | 2 | O | 0 | `disproportionality_causality_reject`, `evidence_scope_reject` |
| 15 | `evidence_scope` | 1 | O | 0 | `evidence_scope_reject` |

부정 케이스 16건에서 과잉해석 체크가 21건 발동했다. 케이스당으로는 13건이 규칙 하나,
1건이 두 종, 1건이 세 종이었고, 남은 1건인 `planted_unsupported_claim`은 과잉해석 규칙이 아니라
1단 결정 규칙 `all_claims_have_evidence`가 잡았다. 정상 17건에서 과잉해석 체크가 발동한 것은
0건이다.

판정 자체는 부정 16건 전부 reject이고, 정상 17건 중 16건이 pass에 1건이 needs_human이다.
needs_human이 난 것은 `diffdock_reproducibility_pass`다.

### 읽는 법

**규칙 한둘이 전부를 잡는 구도는 아니다.** 10종이 1건, 4종이 2건을 잡았고 최대가 2건이다.
Aljamaan 등이 보고한 "기계 항목은 선명하고 판단 항목은 흐려진다"는 구도와는 다른 모양이다.

**다만 이 분포는 케이스 설계에서 상당 부분 따라온다.** `eval/cases.jsonl`은 규칙 15종마다
반려 케이스를 하나씩 심어 둔 구조다. 그래서 규칙당 1건은 설계가 정해 놓은 하한이고, 2건이 된
4종은 규칙 하나가 다른 케이스에도 함께 걸렸다는 뜻이다. **규칙별 구분력을 독립으로 측정한
것이 아니다.** 규칙마다 케이스가 하나뿐이라 그 규칙이 없으면 놓치는지를 이 데이터로는 가릴 수
없고, 그것을 본 것은 별도 측정인 `docs/notes/rule-contribution-2026-09-27.md`의 규칙 제거
대조다.

### 반려 사유와 출처 문장의 대응

21건 중 17건은 규칙의 `source_quote`가 금지한 바로 그 추론을 인용했다. 남은 4건은 다음과 같다.

| 케이스 | 모델이 적은 규칙 | 인용한 문장 | 판단 |
|---|---|---|---|
| `cross_docking_binding_reject` | 교차 타깃 순위 금지 | "이 점수로 응고인자 Xa 결합이 확인되었으므로 ... 임상 주의사항으로 함께 고려해야 한다" | 오귀속. 이 문장에는 두 타깃 점수의 비교가 없다. 맞는 규칙은 같은 케이스에서 함께 발동한 교차 도킹 해석 금지다 |
| `cross_docking_binding_reject` | 종점 혼합 규칙 | "응고인자 Xa 결합이 확인되었으므로 항응고 병용 주의 문안을 즉시 추가할 것을 권고한다" | 오귀속. BindingDB 종점 병합이 문장에 없다 |
| `evidence_scope_reject` | 라벨 기재와 인과 구분 | "혈소판감소증은 ZEJULA(niraparib) 라벨 5절과 6절에 기재되어 있고 FAERS PRR 은 9.13 이다" | 오귀속. 규칙 14가 "보고가 많다는 서술은 반려하지 않는다"로 면제한 유형이다. 케이스의 최종 판정은 근거 범위 준수 위반으로 reject가 맞다 |
| `diffdock_confidence_affinity_reject` | 친화도 환산 금지 | "0.761 을 결합 친화도로 환산하면 강한 친화도에 해당하므로 ..." | 문면상 규칙 2가 `position_confidence` 환산을 포함하므로 틀리지 않으나, 더 좁은 규칙 10이 이름에 오르지 않았다 |

케이스 단위 판정은 16건 모두 맞았으니 적발률 수치는 흔들리지 않는다. 흔들리는 것은
**"어느 규칙이 잡았다"는 귀속**이다. 사유 원문은 위반 문장을 그대로 인용하는 형식이라
출처 문서 문장과 대조는 되지만, 규칙 이름은 인접 규칙으로 번진다.

### 한 번도 발동하지 않은 규칙

**`diffdock_confidence_affinity` 1종이다.** 자기 반려 케이스까지 있는데도 이름이 한 번도
오르지 않았고, 그 케이스는 `affinity_conversion`으로 귀속됐다. 발표에서 값이 큰 규칙이 바로
이것이라 그냥 넘길 수 없다. 이 규칙만 출처가 NVIDIA DiffDock 문서의 "Do not convert confidence
directly into binding affinity."이고 문헌 뒷받침 강도가 유일하게 **매우 강함**이다. 즉
**NVIDIA 문서를 출처로 둔 규칙이 실제 판정에서 이름으로 확인된 적이 없다.**

고칠 방향은 둘이다. 규칙 2의 `reject_when`에서 `position_confidence`를 빼서 규칙 10이 유일한
담당이 되게 하거나, 3단 프롬프트에 좁은 규칙을 먼저 적용하라는 우선순위를 넣는 것이다.
전자가 규칙 모듈만 고치면 되므로 위험이 작다.

---

## 측정 B. 표기 변동에 대한 3단 판정 안정성

### 측정 배경

Gallifant 등이 약물 이름을 브랜드명에서 성분명으로 바꾸기만 해도 LLM 판단이 흔들리는 것을
보고했다(JCO Clin Cancer Inform 2025;9:e2400257). GPT-3.5-turbo-0125가 브랜드명을 효과 있음에
연결하는 경향이 오즈비 1.43(95% CI 1.15-1.78, p<0.05)이었다(원문 확인).

우리 3단도 LLM이고 약물 이름을 읽는다. 적발률 16/16은 표기를 niraparib 하나로 고정한 수치다.

### 쓴 표기와 출처

없는 이름은 지어내지 않았고 실제로 존재하는 표기 둘만 썼다.

| 표기 | 종류 | 출처 (2026-09-27 조회) |
|---|---|---|
| niraparib | INN 성분명 | 원본 케이스 |
| Zejula | 상품명 | openFDA `drug/label.json`, `brand_name` ZEJULA, `generic_name` NIRAPARIB, `spl_set_id` b7f675e2-159c-490c-b6f4-3f16d9492b7d, UNII 195Q483UZD |
| MK-4827 | 개발 코드명 | PubMed PMID 24970803, Oncotarget 2014, 제목 "Niraparib (MK-4827), a novel poly(ADP-Ribose) polymerase inhibitor, radiosensitizes human lung and breast cancer cells". 코드명 원논문은 PMID 19873981, J Med Chem 2009;52:7170-85 |

### 변형 세트를 만든 방법

`eval/cases.jsonl` 33건 중 본문(claim text와 summary)에 niraparib 또는 ZEJULA가 실제로 나오는
**14건**을 골랐다. 기대 판정이 reject인 것이 8건, pass인 것이 6건이다. 나머지 19건은 약물명이
없거나(`약물 X` 자리표시자, 수치만 있는 케이스) 근거 ID에만 있어 본문이 바뀌지 않는다.

치환은 claim text와 summary에만 했다. **`evidence_ids`는 그대로 두어 근거 문자열을 고정했다.**
표기 하나만 움직이게 하려고 그렇게 두었다.

첫 시도에서 하나가 더 섞였다. `executed_input_pass` 본문에 실행 입력 파일 경로
`/data/docking/inputs/4R6E_ligand_niraparib.pdbqt`가 들어 있어 치환이 파일명까지 바꿨다.
약물명 변경이 아니므로 경로를 원래대로 되돌린 세트를 따로 만들었고, 아래 본 결과는 그
경로 보존 세트를 쓴다. 경로까지 바뀐 세트는 별도로 적었다.

조건마다 같은 데이터셋을 3회 반복 실행했다. 온도 0.0이어도 호스팅 API 판정이 고정되지 않아
실행 사이 잡음을 재려면 반복이 필요했다.

### 결과

| 조건 | 실행 | 판정 수 | 기대와 불일치 | 503 폴백 | 모델 판정 뒤집힘 |
|---|---|---|---|---|---|
| 원본 niraparib | 3회 | 42 | 1 | 1 | **0** |
| Zejula (경로 보존) | 3회 | 42 | 2 | 2 | **0** |
| MK-4827 (경로 보존) | 3회 | 42 | 1 | 1 | **0** |
| 합계 | 9회 | **126** | 4 | 4 | **0** |

**표기를 바꿔 뒤집힌 판정은 0건이다.** 기대와 어긋난 4건은 모두 같은 원인이다. build.nvidia.com이
503 Service temporarily overloaded를 돌려주자 `harness/critic.py`가 needs_human으로 떨어뜨렸다.
응답 JSON의 `required_followups`에 "LLM 판정 실패" 문장이 남아 판정 오류와 구분된다. 표기 조건이
아니라 원본 조건에서도 1건 났다.

| 조건 | 실행 | 케이스 | 기대 | 결과 | 원인 |
|---|---|---|---|---|---|
| 원본 | orig3 | `affinity_conversion_reject` | reject | needs_human | 503 폴백 |
| Zejula | brand_keep | `disproportionality_causality_reject` | reject | needs_human | 503 폴백 |
| Zejula | brand_keep3 | `cross_docking_binding_pass` | pass | needs_human | 503 폴백 |
| MK-4827 | code_keep | `cross_target_ranking_reject` | reject | needs_human | 503 폴백 |

503을 제외하면 세 조건 모두 42/42로 기대와 같다.

### 경로까지 바뀐 세트에서 난 한 건

파일 경로를 함께 치환한 Zejula 세트에서 모델 판정이 한 번 뒤집혔다.

- 케이스 `executed_input_pass`, 기대 pass, 결과 **reject**
- 발동 규칙 **`executed_input`(입력 동일성)**
- 사유 원문: "실행된 입력은 준비된 PDBQT 파일 /data/docking/inputs/4R6E_ligand_Zejula.pdbqt 다.
  연결성 SMILES 는 입체화학을 빠뜨릴 수 있어 실행 입력이 아니다."

인용된 문장은 규칙을 지킨 문장이다. 실행 입력이 준비된 PDBQT라고 밝혔으니 규칙 8이
"반려하지 않는다"고 적어 둔 유형인데도 반려됐다. 짚을 것이 둘이다.

첫째, **규칙 8의 프롬프트가 파일 경로를 문자열로 박아 두었다.** 케이스의 경로가
`4R6E_ligand_Zejula.pdbqt`로 달라지자 규칙에 적힌 경로와 어긋났고, 모델이 그 불일치를 위반으로
읽은 것으로 보인다. 경로를 원래대로 둔 세트에서는 세 번 모두 pass였다.

둘째, **같은 데이터셋을 다시 돌리면 pass가 나왔다.** 경로까지 치환한 Zejula 세트를 두 번 돌려
한 번은 reject, 한 번은 pass다. 재현되지 않으므로 표기 때문이라고 단정할 수 없고 실행 사이
잡음과 섞여 있다.

### 통계적 한계

0/126은 "뒤집히지 않는다"가 아니다. 뒤집힘이 0건일 때 95% 단측 상한은 조건별 42건에서 **6.88%**,
세 조건을 합친 126건에서 **2.35%**다. 즉 **판정 1건당 7% 수준의 표기 민감도는 이 표본으로 배제할
수 없다.** Gallifant 등의 설계가 약물 수백 종을 쓴 것과 달리 우리 표본은 화합물 하나에
케이스 14건이다.

호스팅 API 쪽 잡음도 기록해 둔다. 9회 실행 126건에서 `response_format` 구조 출력 호출이 503으로
실패해 프롬프트 경로로 재시도한 것이 18건이고, 재시도까지 실패해 needs_human으로 떨어진 것이
4건(3.2%)이다.
**실행마다 다른 케이스에서 난다.** 논문에서 적발률을 단일 수치로 적으려면 반복 실행 중위값이나
503 제외 기준을 함께 밝혀야 한다.

---

## 제출 문안에 반영할 것

제출 마감이 2026-09-28이고 제출물은 이 측정에서 손대지 않았다. 아래는 권고이며 반영은 사용자가
결정한다.

**1. "규칙 15종"은 그대로 쓸 수 있다.** 15종 중 14종이 판정에서 이름으로 확인됐고 규칙 하나가
전부를 잡는 구도가 아니다. 다만 `diffdock_confidence_affinity`가 한 번도 이름에 오르지 않았으므로,
NVIDIA DiffDock 문서를 규칙 출처로 앞세우는 문장이 있으면 "규칙으로 적혀 있다"까지만 말하고
"그 규칙이 반려했다"로 넘기지 않는 편이 안전하다. 확인은
`eval/results/rule_attribution_2026-09-27.json`이다.

**2. 적발률 16/16에 표기 조건을 덧붙일 여지가 있다.** 지금 문안은 표기를 고정한 수치다.
한 문장을 더할 수 있으면 "약물명을 상품명 Zejula와 개발 코드명 MK-4827로 바꿔 각각 3회 재실행해도
판정이 뒤집힌 건은 없었다(126건 중 0건)" 정도가 측정으로 받쳐진다.

**3. 제출물의 수치를 고쳐야 하는 것은 없다.** `docs/HANDOFF.md`의 16/16, 평균 0.9697,
거짓 양성 0/17은 이번 재집계와 어긋나지 않는다. 정상 17건 중 1건이 needs_human이라는 사실은
평균 0.9697에 이미 반영돼 있다.

**4. 논문 단계에서는 고칠 것이 둘이다.** 규칙 2에서 `position_confidence`를 빼 규칙 10에
넘기는 것, 그리고 규칙 8에서 파일 경로 문자열을 빼거나 "경로는 예시"라고 밝히는 것이다.
둘 다 제출 후에 한다.

## 확인하지 못한 것

- **규칙별 독립 구분력.** 케이스가 규칙당 하나뿐이라 이 데이터로는 가릴 수 없다. 규칙마다
  반려 케이스를 여럿 두고 규칙을 하나씩 빼는 설계가 필요하다
- **약물 하나를 넘는 표기 실험.** niraparib 한 화합물만 썼다. Gallifant 등처럼 여러 약물의
  브랜드명과 성분명 쌍으로 넓히지 못했다
- **`약물 X` 자리표시자 케이스 3건.** 실재하는 약물이 아니라 표기 치환 대상에서 뺐다
- **한국어 조사 처리.** "niraparib 은"을 "Zejula 은"으로 치환해 조사가 어색해진 곳이 있다.
  판정에 영향을 줬는지는 확인하지 못했다 [unverified]
- **503 발생률의 시간대 의존.** 이 날 이 시간대 실행에서만 관측한 것이고 재발 빈도는 모른다
