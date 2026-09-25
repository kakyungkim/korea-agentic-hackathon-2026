# 겪은 문제와 해결책

2026-09-24에서 25 사이에 직접 부딪쳐 푼 것만 적는다. 합류하신 분은 같은 자리에서 시간을 쓰지 않으셔도 된다.
추측은 넣지 않았고, 해결하지 못한 것은 그렇다고 적는다.

## 1. 모델 ID가 통하지 않는다

**증상.** `410 Gone ... has reached its end of life`, 또는 `404 Not Found ... Function '...': Not found for account`.

**원인.** 여기저기 문서에 적힌 `nvidia/nemotron-3-nano-30b-a3b`는 2026-09-01에 종료됐다.
이름을 뒤집은 `nvidia/nemotron-nano-3-30b-a3b`는 목록에는 있으나 신규 계정에서 404다.
**모델 목록에 있다고 호출되는 것이 아니다.**

**해결.** 실제로 응답하는 것만 쓴다. 실측으로 확인한 것은 다음과 같다.

| 쓰임 | 모델 ID | 상태 |
|---|---|---|
| 계획, 크리틱 | `nvidia/nemotron-3-super-120b-a12b` | 동작 |
| 반복 작업, 강좌 기본 | `nvidia/nemotron-3.5-lightning-30b-a3b` | 동작 |
| 임베딩 | `nvidia/nemotron-3-embed-1b` | 동작, 차원 2048 |
| 큰 모델 | `nvidia/nemotron-3-ultra-550b-a55b` | 동작 |

리랭커는 이 계정의 목록 82개에 **하나도 없다.** 기술 스택에 적지 않는다.

내 계정에서 무엇이 되는지 확인하려면 `/v1/models`를 부른 뒤, 후보마다 짧은 호출을 한 번씩 넣어 본다.

## 2. 구조화 출력이 400으로 거부된다

**증상.** `unknown field 'guided_json', expected one of 'greed_sampling', 'use_raw_prompt', ...`

**원인.** LangChain의 `ChatNVIDIA.with_structured_output()`이 요청을 `nvext.guided_json`으로 보내는데
Nemotron 3 엔드포인트가 그 필드를 받지 않는다. 더 헷갈리는 점은 내부적으로 세 형식을 차례로 시도하면서
**마지막 예외만 올린다**는 것이다. 그래서 화면에는 `guided_json` 오류만 보인다.

**해결.** `llm.bind(response_format=...)`으로 OpenAI 호환 `json_schema`를 직접 실어 보낸다.
`method=` 인자는 ChatNVIDIA가 경고와 함께 무시하므로 선택지가 아니다.
추론형 모델은 생각 과정이 섞여 나오므로, `</think>` 뒤만 남기고 중괄호 균형을 세어 JSON을 뽑는
추출 함수와 1회 재시도를 함께 둔다.

## 3. Multipass가 VM을 만들지 못한다 (Intel Mac)

**증상.** `launch failed: Failed to amend image to QCOW2 v3: qemu-img failed (Process crashed)`.
이미지는 100% 받고 해시 검증도 통과한 뒤 그 자리에서 멈춘다.

**원인.** Multipass 1.16.4에 딸려 온 `qemu-img`가 이 환경에서 죽는다. 다운로드 문제가 아니다.
`qemu-img create`만 따로 돌려도 세그멘테이션 오류(rc=139)가 난다.

**해결.** Colima로 바꾼다. Apple 가상화 프레임워크를 쓰므로 QEMU를 거치지 않는다.
```bash
brew install colima
colima start --vm-type vz --cpu 2 --memory 5 --disk 30
```
OpenShell은 호스트가 macOS Intel이면 설치 자체가 거부된다(설치 스크립트가 x86_64 Darwin을 막는다).
반드시 리눅스 VM 안에서 설치한다.

**결과(2026-09-25).** Colima VM(Ubuntu 24.04.4, 커널 6.8.0-117, Docker 29.5.2) 안에 OpenShell
0.0.116을 설치하고 샌드박스 생성과 정책 적용까지 마쳤다. 스모크 테스트는 허용 4건, 차단 2건,
쓰기 3건이 모두 통과했고(`pass=9 fail=0`) 차단 로그 원문까지 `eval/results/openshell_smoke.txt`에
남겼다. 게이트웨이 기동에서 두 군데가 막혔는데, compute driver 자동 탐지가 실패하므로
`~/.config/openshell/gateway.env`에 `OPENSHELL_DRIVERS=docker`를 넣어야 하고, 사용자 systemd
매니저가 docker 그룹 없이 떠 있으면 `sudo systemctl restart user@$(id -u).service`로 다시 띄워야
한다. 자세한 기록은 `docs/notes/openshell-setup.md`의 "실행 기록(Colima)" 절에 있다.

## 4. DLI 강좌에서 "Failed to fetch"가 뜬다

**증상.** 키를 넣고 Save & verify를 누르면
`Connection failed: Network or endpoint failure ... Failed to fetch`.
콘솔에는 `blocked by CORS policy: No 'Access-Control-Allow-Origin' header`.

**원인.** 키도 모델도 주소도 정상이다. 강좌는 NVIDIA API를 직접 부를 수 없어
`nvidia-api-cors-proxy.experiments.courses.nvidia.com` 릴레이를 거치는데, **그 릴레이가 간헐적으로
504를 낸다.** CloudFront 오류 페이지에는 허용 헤더가 붙지 않아 브라우저는 "헤더가 없다"고만 보고한다.
실측으로 네 번 중 세 번이 30초 만에 504였고 한 번만 1.7초에 성공했다.

**해결.** 설정의 **Request handling**에서 `Automatic retries`를 0에서 **3**으로 올린다.
대기 시간은 60초 그대로 두면 된다(실패는 30초에 나고 성공은 2초 안에 온다).
확장 프로그램이나 시크릿 창과는 무관하다. 콘솔의 `Could not establish connection`은 확장이 내는 잡음이다.

진단을 되풀이하지 않으려면 터미널에서 릴레이를 직접 찔러 본다.
```bash
curl -s -o /dev/null -m 120 -w "%{http_code} %{time_total}s\n" \
  -X POST "https://nvidia-api-cors-proxy.experiments.courses.nvidia.com/v1/chat/completions" \
  -H "Origin: https://nvdli.github.io" -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3.5-lightning-30b-a3b","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

## 5. 강좌 실습에서 "Incomplete model decision"

**증상.** 미로 실습을 Run하면 `Error: Incomplete model decision; no move was applied.`

**원인.** 설정 오류가 아니다. `nemotron-3.5-lightning`은 추론형이라 답하기 전에 생각 과정을 쓴다.
출력 예산이 모자라면 생각만 하다 끝나고 결정이 안 나온다. 코드 주석도
`no reasoning budget; compare with "reasoning" or "omni"`라고 적어 비교를 권한다.

**해결.** Debug info를 펼쳐 응답을 확인한 뒤 `model:`을 `reasoning`으로 바꿔 다시 돌린다.
그래도 안 되면 채팅 모델을 `nvidia/nemotron-3-super-120b-a12b`로 바꾼다(크레딧을 더 쓴다).
실패한 판도 레슨이 보여 주려는 비교의 일부라 진도에는 지장이 없다.

## 5-1. 강좌 채팅 실습에서 "No displayable answer arrived"

**증상.** 질문을 보내면 한참 기다린 뒤 `No displayable answer arrived. Inspect the tool trace and the
course home's request recovery guidance before retrying.` 가 뜬다. 응답 위에 `reasoning · ~2966 tok`
같은 배지가 남는다.

**원인.** `nemotron-3.5-lightning`은 추론형이라 답하기 전에 생각을 먼저 쓴다. 그 생각도 출력 예산을
쓰기 때문에, 질문이 어려우면 생각만 하다 한도에 닿아 정작 보여 줄 본문이 남지 않는다. 통신 오류나
키 문제가 아니다. 실측으로 같은 질문이 2,966 토큰을 생각에 쓰면 실패했고 1,455 토큰이면 본문까지 나왔다.

**해결.** 셋 중 하나를 쓴다.
1. 한 메시지에 여러 가지를 시키지 않는다. 규칙을 주는 메시지와 묻는 메시지를 나누고, 규칙 쪽에는
   `Reply "OK" only.` 처럼 짧게 답하라고 못 박는다.
2. 상단 **Model and context options**에서 추론 예산을 줄이거나 출력 길이를 늘린다.
3. 채팅 모델을 `nvidia/nemotron-3-super-120b-a12b`로 바꾼다. 크레딧을 더 쓴다.

**우리 코드와의 관계.** `src/harness/critic.py`가 응답에서 `</think>` 뒤만 남기고 중괄호 균형으로
JSON을 뽑은 뒤, 형식이 어긋나면 한 번 더 요청하는 경로를 둔 이유가 이것이다. 추론형 모델을 쓸 때
이 대비가 없으면 아무것도 돌려받지 못하는 일이 생긴다.

## 5-2. 기억을 꺼도 규칙이 지켜진다 (실험 설계 착각)

**증상.** 기억(memory)을 끄고 "규칙 + 질문"을 한 메시지로 보냈는데 모델이 규칙을 그대로 지켰다.
기억을 껐으니 규칙을 잊을 것이라 예상했다면 어긋난다.

**원인.** 기억 스위치가 정하는 것은 **이전 메시지를 다시 보낼지 말지**이지 지금 보낸 메시지의 내용이
아니다. 한 메시지 안에 규칙과 질문이 함께 있으면 기억과 무관하게 모델에게 그대로 전달된다.

**제대로 비교하려면.** 기억을 끈 채로 규칙만 담은 메시지를 먼저 보내고, 다음 메시지로 질문만 보낸다.
그러면 규칙이 전달되지 않아 모델이 규칙을 모른 채 답한다.

**우리 코드와의 관계.** 지켜야 할 규칙은 대화 기록에 기대지 말고 시스템 프롬프트에 두어 매 호출마다
함께 보낸다. `configs/author.yml`의 `Never compute statistics yourself: use prr_calculator and cite
its evidence_id.`가 그 자리다. 기록에 기대면 대화가 길어질 때 잃어버린다.

**실측 세 판(2026-09-25).** 같은 질문 "What is the PRR for metformin and lactic acidosis in FAERS?"로
비교했다.

| 보낸 방식 | 기억 | 결과 |
|---|---|---|
| 규칙과 질문을 한 메시지에 | 꺼짐 | 규칙 지킴. `[no source]`를 붙이고 숫자를 말하지 않음 |
| 규칙과 질문을 나눠서 | 꺼짐 | 규칙 사라짐. 출처 없이 "PRR 2.5~5.0 범위" 제시 |

두 번째 판이 위험을 그대로 보여 준다. 모델은 `[no source]`를 한 번도 쓰지 않고 구체적인 범위를
말했는데 출처가 없어 확인할 길이 없다. 같은 날 openFDA를 실제로 불러 계산한 값은 **72.8**로 자릿수가
다르다. 어느 쪽이 맞는지는 분모와 기간, 약물명 매칭 방식에 따라 갈리므로 단정하지 않는다. 확실한 것은
우리 수치는 쿼리 URL로 되짚을 수 있고 모델의 범위는 그럴 수 없다는 점이다. 도구 결과에 근거 ID를
붙이는 이유가 이것이다.

모델이 규칙을 받으면 스스로 조심하는 것은 좋은 신호이지만 매번 그러리라는 보장이 없으므로 크리틱이
따로 확인한다.

## 5-3. 본문이 나오다가 사라진다 (스트리밍 중 끊김)

**증상.** 답이 화면에 쌓이다가 갑자기 사라지고 오류로 바뀐다. 재시도를 3으로 올려 두어도 소용없다.

**원인 둘이 겹친다.** 하나는 4번의 릴레이 불안정이다. 스트리밍이 길수록 끊길 구간이 길어진다.
다른 하나는 **재시도가 스트리밍 시작 전에만 걸린다**는 점이다. 설정 화면도 그렇게 적어 두었다.
글자가 쌓이기 시작한 뒤 끊기면 자동으로 다시 시도하지 않는다.

**해결.** 질문을 짧게 나눠 생각과 출력을 줄인다. 끊기면 `rewind here`로 그 지점으로 되돌리거나
New chat으로 새로 시작해 다시 보낸다. 시간을 두고 재시도하면 통과할 때가 많다.

**실측 사례(레슨 2a 실습).** 이 증상의 표식은 `finish_reason: null`이다. `stop`도 `length`도 아니라
완결 신호 자체가 오지 않았다는 뜻이며, 예산이 모자라 멈춘 경우와 여기서 갈린다. 구조화 출력을 요구하는
단계에서 특히 잘 드러난다. 자유 텍스트는 앞부분이라도 남지만 미완성 JSON은 파싱이 안 되므로 바로
실패하기 때문이다. 레슨 2a의 ReWOO 플래너 노드에서
`✗ Error: Planner did not finish a JSON answer (finish_reason: null).`로 멈췄고, `max_tokens`를 손대지
않고 셀을 다시 돌리자 통과했다. `null`이 보이면 예산이 아니라 연결 쪽을 먼저 의심하고 재실행한다.
자세한 내용은 `docs/notes/dli-course/lessons/02a-workflow-agent.md` 3절에 적었다.

## 5-4. "이번만"과 "계속"을 한 문장에 섞지 않는다 (프롬프트 설계)

**증상.** 규칙을 주는 메시지에 `Reply "OK" only.`를 넣었더니, 기억이 켜진 상태에서 다음 질문에
모델이 갈등했다. 생각 과정에 "OK만 답하라고 했는데 지금은 질문이네, 헷갈린다"가 여러 번 되풀이되고
출력이 끝나지 않았다.

**원인.** 기억이 켜져 있으면 앞 메시지가 다음 요청에도 실린다. `Reply "OK" only.`가 그 턴에만
해당하는 지시였는데 계속 유효한 명령으로 읽혔다. 기억이 꺼진 판에서는 이 문장이 다음 턴에 실리지
않아 문제가 없었다.

**해결.** 적용 범위를 문장에 밝힌다.
```
Rule for the rest of this conversation: for every factual claim, add a source ID in brackets.
If you have no source, write "no source". Acknowledge with OK.
```

**우리 코드와의 관계.** 시스템 프롬프트를 쓸 때 한 번만 할 일과 늘 지킬 규칙을 섞지 않는다.
늘 지킬 규칙은 시스템 프롬프트에 두고, 이번 호출에만 필요한 지시는 사용자 메시지에 둔다.

## 5-5. 강좌 3a 에서 launchable 연결이 계속 실패한다 (미해결, 강좌 쪽 한계)

**증상.** 모듈 3a 의 `Connect NemoClaw` 에서 Base URL 을 넣어도 네 가지 점검(`/api/agent`,
`/cli/gateway`, `/ws/terminal`, `/healthz`)이 모두 `FAILED` 로 끝난다. 메시지는
`Connection failed`, 상세에는 `Failure: Failed to fetch` 와
`Credential: The saved access session is not copied into a direct browser request.` 가 나온다.

**원인.** 강좌 안내와 실제 인스턴스가 어긋난다. 세 가지가 겹친다.

1. **주소 형태가 다르다.** 강좌는 `apps.run.brev.nvidia.com` 또는 `brevtab.com` 만 다루는데
   실제로 받은 인스턴스는 `nemoclaw-<id>.gobrev.dev` 였다.
2. **쿠키 이름이 다르다.** 강좌는 `_powerfulm` 이나 `CF_Authorization` 을 찾으라고 하는데
   실제 쿠키는 `cf_clearance` 와 `__Host-skybridge-brev-prd` 둘뿐이었다. `cf_clearance` 는
   Cloudflare 봇 검사 통과 표시라 인증 토큰이 아니다.
3. **`__Host-` 쿠키는 교차 출처로 보낼 수 없다.** 규격상 그렇다. 값을 정확히 복사해 넣어도
   강좌 페이지(`nvdli.github.io`)에서 `gobrev.dev` 로 보내는 요청에는 실리지 않는다.
   화면의 "저장한 세션 값이 직접 요청에 실리지 않는다" 가 그 뜻이다.

**해결하지 못했다.** 두 쿠키를 모두 시도했고 launchable 탭을 열어 둔 채로도 실패했다.
사용자 설정 문제가 아니다.

**대신 이렇게 한다.**
- launchable 자체는 정상이므로 NemoClaw 화면의 `CHAT WITH AGENT` 로 들어가 에이전트를 직접 쓴다.
  샌드박스 경계를 확인하는 질문(작업 디렉터리와 사용자 신원, `/tmp` 와 `/etc` 쓰기, 허용 목록 밖
  도메인 접속, `NVIDIA_API_KEY` 값)을 던지면 모듈 3 과 4 가 가르치려는 것을 실물로 확인할 수 있다.
- 모듈 3 과 4 의 내용은 `docs/notes/dli-course/module3-4.md` 로 본다. OpenClaw 게이트웨이,
  예약 실행, OpenShell 정책 문법이 정리돼 있고 우리 `policies/` 와 대조한 표도 있다.
- **교육 미션 수행은 다른 증거로 설명한다.** 우리는 리눅스 VM 에서 OpenShell 0.0.116 을 설치해
  정책을 적용하고 허용 목록 밖 접속이 403 으로 끊기는 로그까지 확보했다
  (`eval/results/openshell_smoke.txt`). 강좌가 가르치려는 것을 실제로 해 본 기록이다.

**진도에 미치는 영향.** 이 연결이 안 되면 진도가 50% 에서 멈춘다. 모듈 3 과 4 의 체크포인트
다섯 개가 모두 살아 있는 launchable 연결을 요구하기 때문이다.

## 5-6. NemoClaw 인스턴스 다루기 (요금 주의)

**띄우기.** 강좌 첫 화면의 `Launch NemoClaw` 로 Brev launchable 을 배포한다. 배포가 끝나도
서비스가 바로 응답하지 않는다. 처음 3 분에서 5 분은 `404 route_not_found` 가 나오는데 컨테이너가
올라오는 중이라 그렇다. 기다렸다 새로고침하면 된다.

**설정.** 온보딩 1 단계에서 런타임은 `OPENCLAW`, 접근 방식은 **`NVIDIA CLOUD`** 를 고른다.
기본값인 `OPENROUTER` 는 `sk-or-v1-` 로 시작하는 별도 키를 요구하므로 쓸 수 없다.
제공자를 바꾸면 키 칸이 `nvapi-` 로 바뀌고 강좌에서 쓰던 키를 그대로 넣으면 된다.
모델은 `nemotron-3-super-120b-a12b` 가 균형이 맞다. Ultra 550B 는 느리고 크레딧을 많이 쓴다.

**요금.** 실행 중 시간당 0.25 달러, 정지 중 0.05 달러다. 신규 계정 잔액이 1 달러라
**실제 실습에 쓸 수 있는 시간은 네 시간 남짓이다.** 켜 두고 자리를 비우면 그대로 빠져나간다.

**정지.** `brev.nvidia.com` 의 Compute 탭에서 인스턴스 카드 제목을 클릭해 상세 페이지로 들어가면
오른쪽 위에 `Start`/`Stop` 과 `Delete` 가 있다. 목록 화면에는 점 세 개 메뉴가 없다.
**`Stop` 을 쓴다.** `Delete` 는 에이전트 설정과 샌드박스를 지워 처음부터 다시 만들어야 한다.

**대화가 실패할 때.** `The AI service is temporarily overloaded.` 는 NVIDIA 모델 서버가 붐비는
것이고 4 번, 5-3 번과 같은 뿌리다. 잠시 뒤 다시 보내거나 채팅 하단에서 모델을 바꾼다.

## 6. NAT 가드레일이 검증은 통과하는데 실행에서 죽는다

**증상 둘.** `ValueError: LLM 'planner' not found`,
`TypeError: llm_bindings['planner'] must resolve to a LangChain BaseLanguageModel; got RunnableConfigurableFields`.

**원인.** `llm_bindings`가 평범한 문자열 맵이라 의존 그래프에 잡히지 않아 미들웨어가 LLM보다 먼저 만들어진다.
그리고 NAT가 ChatNVIDIA를 `configurable_fields`로 감싸는데 NeMo Guardrails는 맨 모델을 요구한다.

**해결.** `llms: [planner]`를 함께 적어 생성 순서를 잡고, `llm_bindings`는 주석 처리해
레일이 자기 설정 파일의 `models:`로 스스로 모델을 만들게 둔다.

## 7. NemoGuard 판정 모델이 응답하지 않는다 (미해결)

`nvidia/llama-3.1-nemoguard-8b-topic-control`은 HTTP 500(서버 쪽 CUDA 오류, 3회 동일),
content-safety 계열은 타임아웃이다. `nvidia/nemotron-3.5-content-safety`만 응답하는데
출력이 NemoGuard JSON이 아니라 한 줄 텍스트라 레일 파서와 맞는지 확인하지 못했다.
**문서와 발표에서 "NemoGuard로 차단한다"고 쓰지 않는다.** 배선까지 했다는 사실만 적는다.

## 8. 도구 모듈을 두 번 import 하면 NAT 가 `_type` 을 해석하지 못한다

**증상.** `nat validate` 가 `union_tag_invalid` 로 실패한다. 기대 태그 목록에
`pharmasignal_openfda/openfda_faers` 와 `harness.tools/openfda_faers` 가 나란히 찍힌다.

**원인.** 테스트가 `sys.path.insert` 로 도구를 최상위 모듈(`pharmasignal_openfda`)로 불러오고
`harness.register` 는 같은 파일을 `harness.tools.pharmasignal_openfda` 로 불러왔다.
같은 파일이 서로 다른 모듈로 두 번 들어오면서 `@register_function` 이 두 번 돌고 짧은 이름
`openfda_faers` 가 둘이 됐다. **NAT 는 짧은 이름이 겹치면 판별 유니온에서 빼 버린다**
(`nat/cli/type_registry.py` 의 `_do_compute_annotation`). 그래서 YAML 의 `_type` 이 해석 불가가 된다.

**해결.** 도구 테스트는 반드시 패키지 경로로 import 한다. `from harness.tools import ...` 다.
회귀 방지로 `tests/test_harness_register.py` 에 `test_registered_tool_names_are_unique` 를 넣었다.

**교훈.** 등록 이름이 겹치면 에러가 등록 시점에 나지 않고 **설정 검증 시점에 엉뚱한 메시지로**
나타난다. 도구를 늘릴 때 짧은 이름 유일성을 테스트로 지킨다.

## 9. tool calling 요청이 간헐적으로 500 을 돌려준다 (서버 쪽)

**증상.** `nat run` 이 1초 만에 죽는다.
`LLM returned an empty response (no content, no tool calls). finish_reason=None, response_metadata={}`

**확인.** `integrate.api.nvidia.com` 에 같은 조건을 직접 반복해 보니 **500 이 무작위로 섞인다.**
같은 본문이 두 번 연속 500 이었다가 다음에는 성공했고, 짧은 프롬프트에서도 한 번은 성공 한 번은
500 이었다. 파라미터 조합이 원인이 아니다.

**해결.** 재시도하면 통한다. 2026-09-25 재측정에서 도구 8개로 늘린 뒤에도 같았다.
한 번 실패하고 다음 시도에서 바로 성공했다. 도구가 늘어 프롬프트가 커진 것 자체는 문제가 아니었다
(성공 호출의 input_tokens 1,583).

**교훈.** 빈 응답을 받으면 먼저 재시도한다. 프롬프트를 줄이거나 도구를 빼기 전에 서버 쪽
간헐 실패를 의심한다. 데모 녹화와 제출 직전 실행에는 재시도 여유를 둔다.

## 10. DiffDock 은 같은 입력에도 호출마다 결과가 다르다

**증상.** 같은 수용체와 리간드로 두 번 불러 `position_confidence` 가
`[0.798, 0.751, 0.725]` 와 `[0.761, 0.693, 0.515]` 로 갈렸다.

**원인.** 확산모델이고 **호스팅 API 에 시드 파라미터가 없다.** 입력 ATOM 줄 수와 바이트가
정확히 같아도 재현되지 않는다.

**해결.** 요청과 응답의 SHA256 을 함께 기록해 어느 호출의 결과인지 대조한다. 응답 캐시로 같은
입력에 같은 값을 재생한다(캐시 적중 0.01초, 네트워크 미사용).
문서에는 "이 값이 나온다" 가 아니라 "이 호출에서 이 값이 나왔다" 로 적는다.

**교훈.** 과잉해석 규칙에 "시드 없는 단일 호출에 재현성을 주장하면 반려" 를 넣었다.
우리가 실측으로 보인 규칙이다.

## 알아 두면 좋은 것

- **NAT의 `thinking:` 키는 Nemotron 3 ID를 거부한다.** 정규식이 맞지 않아 검증에서 실패한다.
  `chat_template_kwargs: {enable_thinking: true|false}`로 쓴다.
- **pydantic을 반환하는 NAT 함수는 콘솔 프런트엔드에서 문자열 변환에 실패한다.**
  `FunctionInfo.from_fn(..., converters=[...])`로 변환기를 등록한다.
- **openFDA는 키 없이 분당 240회, 일 1,000회다**(IP당). 결과가 없으면 404를 돌려주므로 0건으로 처리한다.
- **PubMed는 초당 3회**를 넘기지 않는다. 호출 사이에 0.34초를 둔다.
- **강좌 진도는 연속으로 달성한 가장 높은 지점으로 계산된다.** 중간을 건너뛰면 뒤를 채워도 오르지 않는다.
  모듈 1과 2를 마치면 50%이고 그 위는 Brev 인스턴스가 있어야 한다. 원격 기록은 기본으로 꺼져 있으니
  도구 모음의 Activity에서 켠다.
