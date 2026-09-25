# 이상사례 건별 선별의 시간과 비용 측정

2026-09-26 작성. 건수가 많은 경로를 따로 만들고 그 경로를 프런티어 모델로 돌릴 때의
지연과 토큰을 쟀다. 만든 것은 `scripts/bench_triage_scale.py` 와
`tests/test_bench_triage_scale.py` 두 개다. 기존 도구와 설정은 손대지 않았고
NAT 함수로 등록하지도 않았다.

## 규모와 비용

지금 파이프라인은 화합물 하나를 깊게 따라간다. 그 구조에서는 앞단에 싼 분류기를 두는
이점이 드러나지 않는다. 한 건을 처리하는 비용이 애초에 작기 때문이다. 이점은 건수가
많을 때 드러나므로, 한 화합물의 이상사례를 여러 건 받아 건별로 판정하는 경로를 만들고
건당 값을 재기로 했다.

재려는 것은 하나다. 예아니오 한 글자를 받자고 모델이 토큰을 얼마나 쓰는가.
그래서 프롬프트를 짧고 정형화된 두 줄 응답으로 묶었다. 긴 설명을 요구하면 재는 대상이
프롬프트 설계로 옮겨가 버린다.

```
VERDICT: YES 또는 NO
REASON: 한 문장, 60자 이내
```

## 동작 방식

1. openFDA 집계 쿼리(`count=patient.reaction.reactionmeddrapt.exact`)로 한 화합물의
   반응별 보고 건수를 받아 많은 순으로 앞의 N 건을 잡는다
2. 건마다 기존 도구 `pharmasignal_openfda.faers_disproportionality` 를 그대로 불러
   2x2 집계와 PRR, ROR, Yates 보정 카이제곱, Evans 신호, ROR 신호를 붙인다
3. 그 숫자만 근거로 주고 "사람이 먼저 봐야 하는가" 를 한 번 묻는다
4. 건마다 판정, 지연, 토큰을 기록하고 합계와 건당 값을 요약한다

기존 도구는 import 해서 쓰기만 했다. 상수(`BASE`, `REACTION_FIELD`)와 절 생성기도
빌려 써서 쿼리 문법을 두 군데에 두지 않았다.

### 비교 대상으로 둔 고정 규칙

LLM 없이 도는 판정을 나란히 둔다. Evans 신호나 ROR 신호가 서면 `yes`, 아니면 `no`다.
이미 계산된 값을 읽기만 하므로 추가 비용이 없다. 요약의 `rule_agreement` 가 두 판정이
얼마나 같은 답을 내는지 센다. 이 규칙은 정답이 아니라 비용이 0 인 대조군이다.

### 오프라인 경로

`--offline` 은 캐시만 읽고 LLM 을 부르지 않는다. 판정은 고정 규칙이 낸다.
구현은 with 블록 안에서만 도구 모듈의 `http_get` 을 캐시 전용 대체물로 바꾸는 방식이다.
도구 파일은 고치지 않고, 블록을 빠져나올 때 원래 함수를 되돌린다. 캐시에 없는 URL 은
네트워크로 나가지 않고 `offline_cache_miss` 로 돌아와 그 건이 실패로 잡힌다.
키 없는 환경에서 경로 전체를 확인할 수 있게 하려고 둔 장치다.

## 돌리는 법

```bash
# 캐시만 쓰는 경로. 키가 없어도 끝까지 돈다
env -u NVIDIA_API_KEY .venv/bin/python scripts/bench_triage_scale.py \
    --offline --drug niraparib --limit 10

# 판정기를 붙인다. 호출이 곧 비용이므로 --limit 을 작게 둔다
set -a; source .env; set +a
.venv/bin/python scripts/bench_triage_scale.py --drug niraparib --limit 10

# 판정기를 바꾼다
.venv/bin/python scripts/bench_triage_scale.py --label jev \
    --base-url https://<배포주소>/v1 --model typesafe-ai/jev --api-key-env JEV_API_KEY
```

주요 인자는 `--drug`(기본 niraparib), `--limit`(기본 10), `--sleep`(기본 1.0),
`--base-url`, `--model`, `--api-key-env`, `--offline`, `--out`(기본 `eval/results`)이다.
단가를 아는 판정기라면 `--price-in` 과 `--price-out` 으로 달러 환산까지 받을 수 있다.

산출물은 `eval/results/triage_scale_<label>.json` 이고 건별 기록과 요약이 함께 들어간다.
라벨을 주지 않으면 모델 이름의 끝 조각을, 오프라인에서는 `offline` 을 쓴다.

## 실측값

2026-09-26 실행. 모델은 `nvidia/nemotron-3-super-120b-a12b`,
엔드포인트는 `https://integrate.api.nvidia.com/v1`. niraparib 의 반응 100종 가운데
보고 건수 상위 10건을 돌렸다. 아래 숫자는 모두 그 실행 출력에서 가져왔다.

| 항목 | 판정기 호출 | 고정 규칙(오프라인) |
|---|---|---|
| 건수 | 10건 (성공 10, 실패 0) | 10건 (성공 10, 실패 0) |
| 판정 | yes 10 / no 0 | yes 10 / no 0 |
| 지연 중앙값 | 1,671.7 ms | 0.0 ms |
| 지연 평균 | 1,818.0 ms | 0.0 ms |
| 지연 최소에서 최대 | 635.6 ms 에서 3,177.5 ms | |
| 토큰 합계 | 입력 3,219 / 출력 466 | 0 |
| 건당 토큰 | 입력 321.9 / 출력 46.6 / 합계 368.5 | 0 |
| 벽시계 | 87.67 초 (호출 간 1초 대기 9회 포함) | 0.01 초 |

세 가지가 눈에 걸린다.

**입력이 출력의 일곱 배다.** 건당 입력 321.9 토큰에 출력 46.6 토큰이다. 예아니오 한 줄을
받는 값보다 그것을 묻는 값이 훨씬 크다. 건수가 늘 때 먼저 불어나는 쪽은 프롬프트다.

**두 판정이 10건 모두 같았다.** `rule_agreement` 가 10/10 이다. 상위 10건은 전부
Evans 신호와 ROR 신호가 함께 서는 강한 신호여서, 공짜로 도는 규칙이 이미 같은 답을 낸다.
같은 답을 받는 데 3,685 토큰과 18.2 초를 썼다.

**건당 지연이 다섯 배까지 벌어졌다.** 같은 길이의 프롬프트인데 635.6 ms 와 3,177.5 ms 가
같은 실행 안에 있다. 건별로 예산을 잡으려면 중앙값 하나로는 부족하다.

산출 JSON 의 `projected_estimate` 는 건당 값을 1,000건에 그대로 곱한 값이다.
토큰 368,500 과 순차 실행 0.51 시간이 나오나 **실측이 아니라 추정이고**, 병렬 실행과
캐시 효과를 넣지 않았다.

### 실제로 돌린 명령과 결과

```
env -u NVIDIA_API_KEY .venv/bin/python -m pytest -q -m "not network"
  358 passed, 6 deselected, 28 warnings in 55.75s      (이전 330건 + 신규 28건)

env -u NVIDIA_API_KEY .venv/bin/python scripts/bench_triage_scale.py --offline --drug niraparib --limit 10
  eval/results/triage_scale_offline.json (6,006바이트)

.venv/bin/python scripts/bench_triage_scale.py --drug niraparib --limit 10
  eval/results/triage_scale_nemotron-3-super-120b-a12b.json (8,285바이트)
```

온라인 실행은 한 번만 했다. `build.nvidia.com` 이 간헐적으로 내는 503 은 이번 실행에서
나오지 않았고, 10건 모두 응답을 받았다.

### 테스트

`tests/test_bench_triage_scale.py` 는 28건이며 `@pytest.mark.network` 없이 기본 실행에
들어간다. 가짜 응답은 기존 도구가 쓰는 파일 캐시에 직접 심어 주입한다. 확인하는 것은
요약 산식(건수, 건당 토큰, 지연 중앙값), 실패한 호출의 분리 집계, `--offline` 이
네트워크와 LLM 없이 완주하는지, 산출 JSON 의 필수 키다. 오프라인 확인은 도구와 스크립트
양쪽의 `http_get` 과 `judge_one` 을 예외를 던지는 함수로 바꿔 놓고 완주를 보는 방식이라,
한 번이라도 밖으로 나가면 테스트가 깨진다.

## 확인하지 못한 것

- **판정이 갈리는 자리를 보지 못했다.** 10건 모두 판정과 규칙이 `yes` 였다. 보고 건수
  상위권은 신호가 강한 자리라서 두 판정이 어긋날 구간이 표본에 들어오지 않았다.
  꼬리 쪽 반응이나 신호가 약한 구간을 섞어야 비교에 뜻이 생긴다
- **달러 비용을 재지 못했다.** 이 모델의 확인된 단가가 없어 `--price-in` 과 `--price-out`
  을 주지 않았고, 요약의 `cost_usd` 는 `null` 이다. 토큰까지만 실측이다 [unverified]
- **1,000건 추정은 곱셈이다.** 병렬 실행, 배치, 프롬프트 캐시를 넣지 않았다. 실제로
  1,000건을 돌려 본 적이 없다
- **고정 규칙은 정답이 아니다.** 10/10 일치는 둘이 같은 답을 냈다는 뜻일 뿐,
  어느 쪽이 맞았는지는 말해 주지 않는다. 사람 검토 라벨이 없다
- **한 화합물, 한 모델, 한 번의 실행이다.** 다른 화합물이나 다른 판정기와 비교하지 않았고
  같은 조건을 반복 실행하지 않아 실행 간 지연 분산을 모른다
- **오프라인 지연을 속도 비교로 쓸 수 없다.** 0.0 ms 는 이미 캐시에 있는 숫자로 산술만 한
  시간이다. openFDA 조회 시간이 빠져 있으므로 판정기 지연과 나란히 놓고 배수를 말하면
  틀린다
- **NAT 함수로 등록하지 않았다.** `configs/` 와 `src/harness/register.py` 를 건드리지
  않았으므로 워크플로에서 이 경로를 부를 수는 없다. 등록은 제출 뒤에 한다
