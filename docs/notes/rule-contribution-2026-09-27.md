# 규칙 15종이 일반 LLM 판단에 무엇을 더하는가

2026-09-27 측정. 논문 Rao 2026 의 대조군 설계를 우리 구조에 맞게 옮긴 것이다.

## 왜 쟀나

Rao 등이 "LiverTox 를 참조하라" 는 프롬프트만 준 조건과 아무 제약 없는 조건을 견주어
세 영역 모두 차이가 없음을 보였다(Hepatol Commun 2026;10:e0895). 프롬프트로 주의를 주는
것만으로는 듣지 않는다는 실측이다.

같은 질문이 우리에게도 온다. **규칙 15종을 주는 것이 그냥 "과잉해석을 판정하라" 고 시키는
것과 다른가.** 다르지 않다면 규칙 목록은 장식이다.

우리 `nat eval` 은 `eval/cases.jsonl` 의 고정 텍스트를 크리틱이 판정하는 구조라 작성자
프롬프트를 바꾸는 조건은 넣을 자리가 없다. 대신 **3단 판정 프롬프트에서 규칙 목록만 빼고**
나머지를 같게 둔 대조를 만들었다.

## 세 조건

| 조건 | 적발률 | 거짓 양성 | 출처 |
|---|---|---|---|
| 고정 규칙만 (모델 없음) | 1/16 | | `critic_verdict_output_deterministic.json` |
| **규칙 없이 LLM 일반 판정** | **13/16** | **1/17** | `bench_generic-arm.json` |
| 규칙 15종 + LLM | **16/16** | **0/17** | `bench_rules-arm.json` |

같은 모델, 같은 케이스 33건, 같은 온도와 상위확률이다. 프롬프트에서 규칙 목록만 뺐다.

## 읽는 법

**LLM 판단만으로 13건이 잡힌다.** 규칙 없이도 상당수가 걸러진다는 뜻이고, 이것을 숨기면
과장이 된다.

**규칙이 더한 것은 세 건과 거짓 양성 하나다.** 규칙 조건이 16/16 에 오탐 0/17 이고,
일반 조건이 13/16 에 오탐 1/17 이다.

일반 조건이 놓친 것이 무엇인지가 중요하다.

| 케이스 | 기대 | 규칙 | 일반 |
|---|---|---|---|
| `convergence_claim_reject` | reject | reject | **pass** |
| `executed_input_reject` | reject | reject | **pass** |
| `diffdock_reproducibility_reject` | reject | reject | **pass** |
| `executed_input_pass` | pass | pass | **reject** (거짓 양성) |

셋 다 **도구의 실행 조건을 알아야 판정되는 것**이다. 단일 시드와 exhaustiveness 4 로 돌린
결과에 재현성을 주장하는 것, SMILES 를 실행 입력이라고 말하는 것(실제 입력은 PDBQT),
DiffDock 호스팅 API 에 시드가 없다는 사실. 일반적인 과학 상식으로는 닿지 않고 도구 문서를
읽어야 안다.

이것이 규칙을 도구 문서에서 옮긴 이유를 뒷받침한다. **분야 상식으로 풀리는 것은 LLM 이
이미 풀고, 도구 문서에만 적힌 것은 그 문서를 줘야 풀린다.**

## 비용

| 조건 | 입력 토큰 | 출력 토큰 | 지연 중앙값 |
|---|---|---|---|
| 규칙 15종 | 58,538 | 8,027 | 1,667.9 ms |
| 규칙 없음 | 11,748 | 1,736 | 835.8 ms |

규칙 목록이 입력 토큰을 다섯 배로 늘린다. 세 건을 더 잡고 오탐 하나를 없애는 대가다.

## 실행 실패 한 건

일반 조건에서 `species_mismatch_pass` 한 건이 실패했다(33건 중 32건 성공). 판정이 아니라
호출 또는 파싱 실패다. 그래서 일반 조건의 분모가 규칙 조건과 정확히 같지 않다.
다시 돌려 확인해야 한다.

## 재현

```bash
set -a; source .env; set +a
.venv/bin/python scripts/bench_critic_judge.py --label rules-arm   --prompt rules   --sleep 0.4
.venv/bin/python scripts/bench_critic_judge.py --label generic-arm --prompt generic --sleep 0.4
.venv/bin/python scripts/bench_critic_judge.py --compare eval/results/bench_rules-arm.json eval/results/bench_generic-arm.json
```

`--prompt` 옵션은 2026-09-27 에 `scripts/bench_critic_judge.py` 에 넣었다.
`generic` 은 규칙 목록을 뺀 것 말고는 같은 문장을 쓴다.

## 미확인 사항

- 실패한 한 건을 다시 돌리지 않았다
- 한 번씩만 돌렸다. 같은 조건을 여러 번 돌렸을 때의 편차를 모른다
- 규칙을 하나씩 빼 보는 절제 실험은 하지 않았다. 15종 가운데 어느 것이 세 건을 담당하는지는
  위 케이스 이름으로 짐작할 뿐이다
