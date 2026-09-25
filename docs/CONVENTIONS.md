# 저장소 규약

팀원이 함께 지키는 규칙이다. 환경 준비는 `docs/ONBOARDING.md`, 진행 상황은 `docs/HANDOFF.md`,
주제 결정 근거는 `docs/notes/topic-decision.md` 를 본다.

## 환경

- Python 3.12, 가상환경 `.venv`. 시스템 파이썬에 설치하지 않는다
- 모델 호출은 build.nvidia.com NIM API(OpenAI 호환). 키는 각자 보관하고 `.env` 에 둔다.
  **`.env` 는 커밋하지 않는다**
- 로컬은 GPU 없음. OpenShell 은 리눅스 VM 에서 돈다
- 외부 유료 API 호출 금지. 공개 API 는 호출 횟수를 아낀다. PubMed 는 초당 3회 이하

## 구조

```
src/harness/            공통 하네스 (register.py, critic.py, schemas.py)
src/harness/tools/      도메인 도구
configs/                NAT 워크플로 YAML
policies/               OpenShell 정책
eval/                   cases.jsonl, results/
scripts/                실행 스크립트
tests/                  pytest
docs/                   계획, 설정 안내, 그림, 제출물
```

## 커밋 범위

**공개 저장소다. 처음부터 공개 기준으로 커밋한다.** 커밋 전에 셋을 확인한다.

1. **저작권이 있는 외부 원문을 담고 있는가.** 강좌 본문, 유료 자료, 남의 문서 전재는 두지
   않는다. 요약과 우리 해석만 둔다
2. **빼라고 지시받은 경로인가.** 한 번이라도 지시가 있었으면 지킨다
3. **공개됐을 때 곤란한가.** 곤란하면 지금도 커밋하지 않는다

개인 경로, 작업 도구 설정, 팀원 실명, 키는 올리지 않는다.

## 저작 표기 (예외 없음)

커밋 저작자는 각자 본인 GitHub 신원이다. **AI 도구를 공동저자나 생성자로 적지 않는다.**
트레일러와 꼬리말을 넣지 않고 커밋 메시지 본문에도 언급하지 않는다.

커밋 이력은 본인 이름으로 남는 작업 기록이고 대외 공개 저장소에서도 읽힌다.

사람 기여 표기는 `docs/notes/credits.md` 를 따른다.

## 작업 규율

- 각자 담당 경로만 고친다. 담당은 `docs/notes/work-assignment.md` 에 있다.
  **`configs/` 와 `src/harness/register.py` 는 팀장만 고친다**
- 파일을 고치는 스크립트는 읽고 나서 쓰고, 다건 수정은 드라이런 후 적용한다
- **모든 수치는 방금 실행한 출력에서만 가져온다.** 추정은 추정이라 적고 확인 못 한 것은
  `[unverified]` 로 표시한다
- 테스트는 `tests/` 에 pytest 로. 네트워크가 필요하면 `@pytest.mark.network` 로 표시한다
- 문서는 한국어. em-dash 금지, 가운뎃점 절제, 번역투 회피
- 완료 보고에 만든 파일, 실행한 명령과 결과, 확인하지 못한 것을 적는다

## 되지 않는 것을 되는 것처럼 쓰지 않는다

이 저장소의 핵심 규율이다. 시연하지 못한 것은 시연하지 못했다고 적는다.
현재 상태는 `README.md` 의 "아직 하지 않은 것" 표에 있다.
