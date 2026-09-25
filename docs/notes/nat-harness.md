# NAT 공통 하네스 노트 (NeMo Agent Toolkit 1.9.0)

작성 2026-09-24. 여기 적은 문법은 모두 `.venv`에 설치된 `nvidia-nat 1.9.0` 소스에서 직접 확인한 것이다. 문서나 기억이 아니라 설치본이 기준이며, 확인하지 못한 항목은 마지막 절에 [unverified]로 모았다.

## 구성 요소와 파일

| 경로 | 역할 |
|---|---|
| `pyproject.toml` | `harness` 패키지 정의와 NAT entry point 등록 (`nat.components` 그룹) |
| `src/harness/register.py` | 함수 등록. 예시 도구 `echo_tool`, `prr_calculator`. 도메인 도구 import 자리 |
| `src/harness/schemas.py` | `AuthorOutput`(claims, summary), `CriticReport`(verdict, checks, required_followups) |
| `src/harness/critic.py` | 크리틱 함수 `critic_judge`. 결정 규칙(순수 파이썬) 뒤에 LLM 의미 판단 |
| `src/harness/evaluators.py` | `nat eval` 평가기 `critic_verdict` (verdict 일치율 = 적발률) |
| `configs/author.yml` | NIM LLM 2개(planner, worker) + tool_calling_agent 워크플로 |
| `configs/critic.yml` | 도구 없는 크리틱 워크플로 |
| `configs/eval.yml` | 크리틱 워크플로에 `eval/cases.jsonl`을 넣고 적발률을 재는 설정 |
| `configs/guardrails/author_guarded.yml` | author + NeMo Guardrails 미들웨어 부착 |
| `configs/guardrails/rails/{config,prompts}.yml` | Colang 1.0 정책 디렉터리 (토픽 제어) |
| `eval/cases.jsonl` | 정상 2건, 근거 없는 주장을 심은 부정 1건 |
| `tests/test_harness_register.py`, `tests/test_harness_configs.py` | 수치, 스키마, 결정 규칙, 설정 로딩 테스트 |

## 설치와 등록 방식

NAT는 설치된 파이썬 패키지의 entry point 그룹 `nat.components`(구형 `nat.plugins`도 인식)를 스캔해 컴포넌트를 찾는다(`nat/runtime/loader.py: discover_entrypoints`). 저장소 안 모듈을 그냥 두면 `nat validate`가 `_type`을 해석하지 못하므로, 루트 `pyproject.toml`에 한 줄을 두고 개발 설치했다.

```toml
[project.entry-points.'nat.components']
harness = "harness.register"
```

```bash
.venv/bin/pip install -e . --no-deps
.venv/bin/nat info components -q harness -f package   # function 3개, evaluator 1개가 hackathon-harness 패키지로 보여야 한다
```

가드레일 미들웨어는 코어에 없고 `nvidia-nat-security[guardrails]==1.9.0`에 들어 있다. `.venv/bin/pip install "nvidia-nat[guardrails]==1.9.0"`으로 설치했고 `nemoguardrails 0.21.0`이 함께 들어온다.

## 확인한 문법

### 함수 등록 (nat/tool/datetime_tools.py, 워크플로 템플릿 workflow.py.j2)

```python
from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

class EchoToolConfig(FunctionBaseConfig, name="echo_tool"):   # name 이 YAML 의 _type
    prefix: str = ""

@register_function(config_type=EchoToolConfig)
async def echo_tool(config: EchoToolConfig, builder: Builder):
    async def _echo(text: str) -> str: ...
    yield FunctionInfo.from_fn(_echo, description="...", converters=[...])
```

- 인자가 하나면 그 타입이 입력 스키마, 여러 개면 `create_model`로 pydantic 모델을 자동 생성한다(`nat/builder/function_info.py`). `prr_calculator`는 `a, b, c, d: int` 네 인자를 그대로 받는다.
- 반환 타입이 pydantic 모델이면 콘솔 프런트엔드가 `str`로 바꾸지 못해 `Cannot convert type ... to <class 'str'>` 오류가 난다. `FunctionInfo.from_fn(..., converters=[fn])`에 `def fn(x: Model) -> str` 변환기를 넣으면 해결된다(실측).
- 공개 import 경로로 `nat.plugin_api`(Builder, FunctionInfo, register_function, LLMFrameworkEnum, HumanPrompt 등)도 있다.
- LLM은 `await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)`으로 받는다. 돌아오는 것은 맨 `ChatNVIDIA`가 아니라 그것을 `configurable_fields`로 감싼 `RunnableConfigurableFields`다. 구조화 출력은 `.with_structured_output()` 대신 `.bind(response_format=...)`을 쓴다(아래 "구조화 출력은 response_format 으로" 절).

### 평가기 등록 (nat/plugins/langchain/eval/trajectory_evaluator.py)

```python
from nat.builder.builder import EvalBuilder
from nat.builder.evaluator import EvaluatorInfo
from nat.cli.register_workflow import register_evaluator
from nat.data_models.evaluator import EvalInput, EvalInputItem, EvaluatorBaseConfig
from nat.plugins.eval.data_models.evaluator_io import EvalOutput, EvalOutputItem

class CriticVerdictEvaluatorConfig(EvaluatorBaseConfig, name="critic_verdict"): ...

@register_evaluator(config_type=CriticVerdictEvaluatorConfig)
async def critic_verdict_evaluator(config, builder: EvalBuilder):
    async def _evaluate(eval_input: EvalInput) -> EvalOutput: ...
    yield EvaluatorInfo(config=config, evaluate_fn=_evaluate, description="...")
```

`EvalInputItem`은 `id, input_obj, expected_output_obj, output_obj, trajectory, full_dataset_entry`를 가진다.

### 설정 파일 최상위 키 (nat/data_models/config.py)

`general, functions, function_groups, middleware, llms, embedders, memory, object_stores, retrievers, ttc_strategies, workflow, authentication, eval, trainers, ...`. 환경변수는 `${VAR}` 또는 `${VAR:-default}`로 치환된다(`nat/utils/io/yaml_tools.py`). 값이 없으면 빈 문자열이라 `nat validate`는 키 없이도 통과한다.

### NIM LLM (nat/llm/nim_llm.py)

```yaml
llms:
  planner:
    _type: nim
    model_name: nvidia/nemotron-3-super-120b-a12b     # model 도 alias 로 허용
    base_url: https://integrate.api.nvidia.com/v1
    api_key: ${NVIDIA_API_KEY}
    temperature: 0.2
    top_p: 0.95
    max_tokens: 2048                                  # ChatNVIDIA 에는 max_completion_tokens 로 전달
    chat_template_kwargs:
      enable_thinking: true
```

- `thinking: true` 키(ThinkingMixin)는 정규식 `^nvidia/(llama|nvidia).*nemotron`에 맞는 모델만 받는다. `nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3.5-lightning-30b-a3b`는 여기에 걸려 **validate 단계에서 거부된다**(실측: "thinking is not supported for model_name"). NAT 자체 템플릿(`config.yml.j2`)도 `chat_template_kwargs.enable_thinking`을 쓰므로 같은 방식으로 바꿨다. `NIMModelConfig`가 `extra="allow"`이고 `ChatNVIDIA.build_extra`가 미지 키를 `model_kwargs`로 접어 요청 본문에 싣는다. `scripts/hello_nemotron.py`의 `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`와 같은 경로다.
- 재시도(`RetryMixin`), SSL(`verify_ssl`) 옵션도 같은 블록에 둘 수 있다.

### 에이전트 워크플로 (nat/plugins/langchain/agent/*/register.py)

- `tool_calling_agent`: `llm_name, tool_names, description, verbose, handle_tool_errors, max_iterations, max_history, system_prompt, additional_instructions, return_direct, truncation_retry`.
- `react_agent`: `llm_name, tool_names, description, verbose, max_tool_calls, retry_agent_response_parsing_errors, parse_agent_response_max_retries, tool_call_max_retries, pass_tool_call_errors_to_agent, use_native_tool_calling, system_prompt, additional_instructions, max_history`.
- 그 밖에 `reasoning_agent, rewoo_agent, router_agent, sequential_executor, parallel_executor, chat_completion(도구 없는 단발 LLM)`이 등록돼 있다.
- 모든 함수 설정은 `middleware: [이름]` 리스트를 받는다(`FunctionBaseConfig`).

### nat eval (nat/data_models/evaluate_config.py, dataset_handler.py)

```yaml
eval:
  general:
    max_concurrency: 2
    output_dir: eval/results
    dataset:
      _type: jsonl                     # json, jsonl, csv, parquet, xls, custom, langsmith
      file_path: eval/cases.jsonl
      id_key: id
      structure:
        question_key: input            # 워크플로 입력
        answer_key: expected_verdict   # 평가기의 expected_output_obj
  evaluators:
    critic_verdict:
      _type: critic_verdict
```

결과는 `output_dir/workflow_output.json`과 `output_dir/<평가기>_output.json`으로 떨어진다. 설치본에 있는 평가기는 `trajectory, tunable_rag_evaluator, langsmith*`(langchain 플러그인)이고, `rag_accuracy, ragas` 계열은 `nvidia-nat[ragas]` 추가 설치가 필요하다(미설치).

### 미들웨어 (nat/middleware, nvidia-nat-security)

등록된 `_type`: 코어 `cache, circuit_breaker, dynamic_middleware, logging_middleware, timeout`; security `guardrails, content_safety_guard, output_verifier, pii_defense, pre_tool_verifier, red_teaming`.

- `circuit_breaker`(v1.9): `failure_threshold, cooldown_period, half_open_success_threshold, probe_timeout, circuit_breaker_message` + DynamicMiddleware 공통 키(`llms, workflow_functions, register_workflow_functions, enabled ...`).
- HITL(v1.9): `nat.middleware.hitl.HITLMiddleware`는 `_on_pre_invoke_response / _on_post_invoke_response`를 구현해야 하는 추상 클래스이고 `HITLMiddlewareConfig(pre_invoke_prompt, post_invoke_prompt)`도 `name=`이 없어 **YAML `_type`으로 바로 쓸 수 없다.** 서브클래스를 만들어 `@register_middleware`로 등록해야 한다. 이번 뼈대에는 넣지 않았다.
- `guardrails`(`nemo_guardrails_middleware_config.py`):

```yaml
middleware:
  topic_guard:
    _type: guardrails
    guardrails_root: configs/guardrails/rails    # 또는 guardrails: {RailsConfig 인라인}. 둘 중 하나만
    llm_bindings: {main: planner}                # rail 모델 타입 -> NAT llms 키. main/default 는 주 LLM, 그 외는 "<type>_llm"
    workflow_functions: [...]                    # 선택. 생략하면 함수 설정의 middleware: 로 부착
    stream_output_rails: false
workflow:
  middleware: [topic_guard]
```

로드 시 `RailsConfig.from_path`로 정책을 읽고 Colang 1.0이 아니면 거부하므로, `nat validate`가 정책 폴더의 문법 오류까지 잡는다(실측 통과).

## 실측한 모델 ID와 가용성 (2026-09-24, 이 계정의 키로 직접 호출)

`GET /v1/models`에는 82개가 올라온다. 목록에 있다고 호출이 되는 것은 아니어서, 쓸 모델은 모두 최소 호출로 직접 확인했다. 아래 표는 이 저장소의 키로 실제 요청을 보내 받은 응답이다.

| 모델 ID | 결과 | 비고 |
|---|---|---|
| `nvidia/nemotron-3-super-120b-a12b` | OK | planner, 크리틱 의미 판단 |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | OK | worker. 종료된 nano 를 대신한다 |
| `nvidia/nemotron-3-ultra-550b-a55b` | OK | |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | OK | |
| `nvidia/nemotron-3-embed-1b` | OK | 임베딩 차원 2048 (`/v1/embeddings`, `input_type` 필요) |
| `nvidia/nemotron-3.5-content-safety` | OK | 개별 복약 조언 질문에 `User Safety: unsafe` 를 반환 |
| `nvidia/nemotron-3-nano-30b-a3b` | **410 Gone** | 2026-09-01 종료. `docs/PLAN.md`에 적힌 ID다 |
| `nvidia/nemotron-nano-3-30b-a3b` | **404** | 목록에는 있으나 호출되지 않는다 |
| `nvidia/llama-3.1-nemotron-70b-instruct` | **404** | 목록에는 있으나 호출되지 않는다 |
| `nvidia/llama-3.1-nemotron-51b-instruct` | **404** | |
| `nvidia/llama-3.1-nemoguard-8b-topic-control` | **500** | 서버 쪽 TensorRT-LLM CUDA 오류. 3회 모두 같다 |
| `nvidia/llama-3.1-nemoguard-8b-content-safety` | **타임아웃** | 25초, 90초 모두 응답 없음 |
| `nvidia/llama-3.1-nemotron-safety-guard-8b-v3` | **타임아웃** | |

계획서의 모델 ID 두 개가 모두 죽어 있어 `.env`, `.env.example`, `configs/author.yml`, `configs/guardrails/author_guarded.yml`의 worker 를 `nvidia/nemotron-3.5-lightning-30b-a3b`로 바꿨다. `tests/test_harness_configs.py`와 `scripts/hello_nemotron.py`의 기본값도 같이 맞췄다.

**리랭커는 이 계정의 목록에 하나도 없다.** `nv-rerankqa` 계열이나 그 밖의 rerank 모델이 82개 안에 없으므로, 신청서 기술 스택에서 리랭커를 빼야 한다. 임베딩은 `nvidia/nemotron-3-embed-1b` 외에 `nvidia/llama-3.2-nv-embedqa-1b-v1`, `nvidia/nv-embedqa-mistral-7b-v2`, `nvidia/embed-qa-4`, `snowflake/arctic-embed-l`이 목록에 있다.

### 구조화 출력은 response_format 으로 (guided_json 금지)

크리틱의 `llm.with_structured_output(CriticReport)`는 쓰지 않는다. LangChain `ChatNVIDIA`는 구조화 출력을 세 형식으로 차례로 시도하는데(`chat_models.py`의 `_FallbackRunnable`), 앞 형식이 실패하면 `nvext.guided_json`으로 넘어가고 Nemotron 3 엔드포인트는 그 필드를 거부한다.

```
400 unknown field `guided_json`, expected one of `greed_sampling`, `use_raw_prompt`, ... `router`
```

폴백이 마지막 예외만 올리는 구조라, 앞 단계에서 무슨 일이 났든 화면에는 이 `guided_json` 오류만 보인다. 네 가지를 같은 프롬프트로 재 보고 다음을 골랐다.

| 방법 | 결과 |
|---|---|
| `response_format: {"type": "json_schema", ...}` | **OK.** 스키마에 맞는 JSON 만 돌아온다 |
| `response_format: {"type": "json_object"}` | OK. 다만 스키마를 강제하지 않아 필드가 제멋대로다 |
| 프롬프트로만 JSON 요청 | OK. 모델이 자기 마음대로 필드를 지어낸다 |
| `nvext: {"guided_json": ...}` | 400 거부 |
| `guided_json` 최상위 | 거부 |
| `with_structured_output(..., method=...)` | `method` 인자를 ChatNVIDIA 가 경고와 함께 무시한다. 선택지가 아니다 |

그래서 `src/harness/critic.py`는 이렇게 부른다.

1. `llm.bind(response_format=_RESPONSE_FORMAT).ainvoke(...)`로 OpenAI 호환 json_schema 를 직접 싣는다. 스키마는 `CriticReport.model_json_schema()`에서 만든다.
2. 응답 본문을 `extract_json_object()`로 훑는다. `</think>` 뒤만 남기고, 중괄호 균형을 세어(문자열 안의 괄호는 빼고) 최상위 JSON 객체를 모은 뒤 `verdict` 키를 가진 것을 고른다. 마크다운 펜스와 앞뒤 서술, `{"critic_report": {...}}` 처럼 한 겹 감싼 응답까지 걷어낸다.
3. `CriticReport.model_validate`로 검증한다. 형식이 어긋나면 "JSON 만 출력하라"는 지시를 붙여 한 번 더 요청한다(이때는 `response_format` 없이).
4. 그래도 안 되면 예외를 삼키고 `verdict`를 `needs_human`으로 두며 사유를 `required_followups`에 남긴다. 결정 규칙이 이미 `reject`를 낸 입력은 LLM 을 부르지 않는다.

프롬프트도 함께 고쳤다. 크리틱은 근거 ID 의 내용을 열어 볼 수 없으므로, ID 가 진짜인지 그럴듯한지 판단하지 말라고 못 박고 두 가지만 보게 했다. 요약이 주장 범위를 넘는지(`summary_within_claims`), 주장이 근거로 확인 가능할 만큼 구체적인지(`claims_are_checkable`). 고치기 전에는 모델이 "근거 내용을 못 봤으니 검증할 수 없다"며 정상 케이스까지 반려했다.

### 가드레일 미들웨어의 실행 시점 결함 두 가지

`nat validate`는 통과하지만 `nat run`에서 연달아 막혔다. 둘 다 고쳐서 레일이 실제로 토픽 제어 모델을 부르는 데까지는 갔다.

1. `ValueError: LLM 'planner' not found`. 미들웨어의 `llm_bindings`는 평범한 문자열 맵이라 의존 그래프에 잡히지 않고, 미들웨어가 LLM 보다 먼저 만들어진다. `DynamicMiddlewareConfig`의 `llms: [planner]`(이쪽은 `LLMRef`)를 함께 적어 순서를 잡았다.
2. `TypeError: llm_bindings['planner'] must resolve to a LangChain BaseLanguageModel ...; got RunnableConfigurableFields`. NAT 가 `nat/plugins/langchain/llm.py`에서 ChatNVIDIA 를 `configurable_fields`로 감싸는데 NeMo Guardrails 는 맨 모델을 요구한다. NAT 1.9.0 에서는 우회할 설정이 없어 `llm_bindings`를 주석 처리하고, 레일이 `configs/guardrails/rails/config.yml`의 `models:` 정의로 스스로 모델을 만들게 두었다.

그 뒤 `nat run --config_file configs/guardrails/author_guarded.yml --input "이 약을 제가 하루 두 번 먹어도 될까요?"`는 토픽 제어 모델까지 요청을 보냈고, 모델이 500 을 돌려주며 워크플로가 멈췄다. **차단 시연은 하지 못했다.** 배선은 맞고 호스팅된 NemoGuard 모델이 죽어 있다는 뜻이다. 시연이 필요하면 `nvidia/nemotron-3.5-content-safety`가 살아 있으니 이쪽으로 바꿔 보는 방법이 있다. 다만 출력이 NemoGuard 형식(JSON)이 아니라 `User Safety: unsafe` 한 줄이라 레일의 파서와 맞는지는 따로 확인해야 한다.

## 실행 명령

```bash
# 문법과 등록 검증 (키 불필요, 4개 모두 통과)
.venv/bin/nat validate --config_file configs/author.yml
.venv/bin/nat validate --config_file configs/critic.yml
.venv/bin/nat validate --config_file configs/eval.yml
.venv/bin/nat validate --config_file configs/guardrails/author_guarded.yml

# 단위 테스트
.venv/bin/python -m pytest tests -q

# 크리틱 드라이런 (키 없이, 결정 규칙만)
CRITIC_DETERMINISTIC_ONLY=true .venv/bin/nat run --config_file configs/critic.yml \
  --input '{"claims":[{"text":"PRR 19.8","evidence_ids":[]}],"summary":"라벨 개정 권고"}'
# -> verdict reject, all_claims_have_evidence 실패

# 적발률 드라이런 (키 없이): 부정 1건 reject, 정상 2건 needs_human -> 평균 0.3333
CRITIC_DETERMINISTIC_ONLY=true .venv/bin/nat eval --config_file configs/eval.yml

# 키를 넣고 (set -a; source .env; set +a)
.venv/bin/nat run --config_file configs/author.yml --input "a=40, b=960, c=200, d=98800 의 PRR 을 계산해 근거 ID 와 함께 JSON 으로 보고해."
.venv/bin/nat serve --config_file configs/author.yml         # FastAPI, POST http://localhost:8000/generate
.venv/bin/nat eval --config_file configs/eval.yml            # 적발률 1.0 (정상 2건 pass, 부정 1건 reject)
.venv/bin/nat run --config_file configs/guardrails/author_guarded.yml --input "이 약을 제가 하루 두 번 먹어도 될까요?"
```

`nat run`에 `--override llms.planner.temperature 0.0`처럼 점 표기 덮어쓰기가 된다. `nat eval`은 `--dataset`, `--reps`, `--skip_workflow`(이미 생성된 출력만 재평가), `--endpoint`(서빙 중인 워크플로 대상)를 받는다.

## 도메인 도구 추가 절차

1. `src/harness/tools/<domain>_<tool>.py`에 `FunctionBaseConfig` 서브클래스(`name="..."`)와 `@register_function` async generator를 쓴다. 순수 계산 부분은 별도 함수로 빼서 테스트한다.
2. `src/harness/register.py` 하단 "도메인 도구 import" 블록에 `from harness.tools import <module>  # noqa: F401` 한 줄을 추가한다. entry point는 `harness.register` 하나만 스캔하므로 import 되지 않은 모듈은 등록되지 않는다.
3. `configs/author.yml`의 `functions:`에 `별명: {_type: <name>, ...}`을 넣고 `workflow.tool_names`에 별명을 추가한다.
4. 출력이 pydantic 모델이면 `converters=[모델 -> str]`을 함께 준다.
5. `tests/test_<domain>_<tool>.py`를 두고, 네트워크가 필요한 테스트는 `@pytest.mark.network`.
6. `.venv/bin/nat validate --config_file configs/author.yml`과 `nat info components -q <name>`으로 등록을 확인한다.

현재 `src/harness/tools/`에 pharmasignal_*, nightshift_* 모듈이 들어와 있으나 register.py의 import 블록은 아직 주석 상태다. 해당 모듈이 `@register_function`을 갖추면 담당자가 주석을 해제한다.

## 실측 결과 (2026-09-24)

키 없이 확인한 것.

- `nat --version` 1.9.0. `nat validate` 4개 설정 모두 "Configuration file is valid!".
- `nat info components`: `hackathon-harness 0.1.0` 패키지로 function `echo_tool, prr_calculator, critic_judge`, evaluator `critic_verdict` 등록 확인.
- `pytest -q -m "not network"`: **128 passed, 3 deselected**(2026-09-25 재측정). 크리틱 응답 파싱 테스트
  4건을 이번에 추가해 이 절을 쓸 당시에는 96개였고, 그 뒤 ROR 오라클과 대조 검증 테스트가 들어오며 128개가 됐다.
- 키 없는 `nat run`(critic, deterministic)과 `nat eval`(평균 0.3333, 부정 케이스 적발 1/1) 정상 종료.

키를 넣고 확인한 것.

- `nat eval --config_file configs/eval.yml`: `critic_verdict` 평균 **1.0**. 정상 2건이 `pass`, 부정 1건이 `reject`. 전체 28.15초. 고치기 전에는 LLM 경로가 매번 실패해 0.3333이었다.
- `nat run --config_file configs/author.yml`: 작성자 에이전트가 `prr_calculator`를 호출해 PRR 19.8 을 받고, `claims`와 `summary`를 가진 JSON 하나로 답했다. 근거 ID `calc:prr:40-960-200-98800`이 주장에 붙어 나왔다. `tool_calling_agent`와 Nemotron 3 super 의 네이티브 tool calling 이 맞물린다.
- 크리틱의 구조화 출력이 `response_format` json_schema 로 동작한다(위 절 참고).

## 확인하지 못한 것

- [unverified] NemoGuard 토픽 제어가 실제로 요청을 차단하는 모습. `nvidia/llama-3.1-nemoguard-8b-topic-control`이 500(서버 쪽 CUDA 오류)을 돌려줘 시연하지 못했다. 배선은 레일이 그 모델을 호출하는 데까지 확인했다.
- [unverified] `nvidia/nemotron-3.5-content-safety`의 출력(`User Safety: unsafe` 한 줄)이 NeMo Guardrails 의 content safety 파서와 맞는지.
- [unverified] jailbreak 탐지 `/v1/security/nvidia/nemoguard-jailbreak-detect` 엔드포인트. 호출해 보지 않았다.
- [unverified] `chat_template_kwargs.enable_thinking`이 Nemotron 3 의 채팅 템플릿에서 생각 과정을 실제로 켜고 끄는지. 요청은 통과하고 super 가 `reasoning_content`를 돌려주는 것까지만 봤다.
- [unverified] 남은 크레딧 잔량. 확인 방법을 찾지 못했다.
- 문서(docs.nvidia.com/nemo/agent-toolkit)와의 대조는 하지 않았다. 설치본과 문서가 다르면 설치본이 맞다.
