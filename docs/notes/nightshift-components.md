# Night Shift LLM 없는 구성요소 3종: 실행기, 규칙 크리틱, 아침 보고서

작성 2026-09-24. 담당 경로 `src/harness/tools/nightshift_*.py`, `tests/test_nightshift_*.py`, `eval/results/nightshift_demo.json`, `eval/results/morning_report.{md,html}`. 이 문서의 수치는 모두 같은 날 로컬(Intel Mac, Python 3.12.8, `.venv`)에서 실행한 출력에서 가져왔다. 추정치는 추정이라 적었다.

## 역할과 위치

Night Shift에서 LLM(Nemotron)은 실험을 고르고 패치를 쓴다. 그 패치를 실제로 돌리고, 속임수를 걸러 내고, 아침에 읽을 보고서를 만드는 일은 아래 세 모듈이 LLM 없이 맡는다. 셋 다 표준 라이브러리만 쓰며(테스트 실행에 pytest, 커버리지 측정에 coverage를 외부 프로세스로 부른다), 나중에 NAT 도구로 등록할 수 있게 입력과 출력을 JSON 직렬화 가능한 dict로 맞췄다.

| 모듈 | 진입점 | 입력 | 출력 |
|---|---|---|---|
| `nightshift_runner.py` | `run_experiment(repo_dir, patch_text, cmd_test, cmd_bench=None, timeout=600, ...)` | 저장소 사본 경로, unified diff, 테스트·벤치마크 명령 | 실험 결과 dict(`status`, `before`, `after`, `diff_stat`, `files_changed`, `apply_cmd`) |
| `nightshift_critic_rules.py` | `evaluate_experiment(run_result, allowed_globs, claims_bench_improvement)` / `evaluate_patch(...)` | 실행기 결과(또는 diff와 전후 수치) | `{verdict, checks:[{name, passed, reason}], required_followups}` |
| `nightshift_report.py` | `write_report(records, out_dir, policy_audit)` | `make_record(goal, runner, critic)` 목록, 정책 감사 dict | `morning_report.md`, `morning_report.html` |
| `nightshift_demo.py` | CLI `--target <clone> --out eval/results` | 표적 저장소 | 위 셋을 이어 붙인 데모 산출물 |

## 실행기 설계

흐름은 계획서의 순서를 그대로 따른다.

1. 작업 트리가 깨끗한지 확인한다(추적 파일 변경이 있으면 `error`로 끝낸다). base ref와 sha를 기록한다.
2. `git apply --numstat`과 `--stat`으로 변경 파일 목록과 diff 요약을 적용 없이 얻고, `git apply --check`로 정합성을 본다. 실패하면 `apply_failed`.
3. base에서 테스트(+커버리지)와 벤치마크를 측정한다. 밤새 여러 실험이 같은 base를 쓰므로 `baseline=` 인자로 한 번 잰 값을 재사용할 수 있다(데모가 이 방식).
4. `git checkout -b exp/<id>`, `git apply --index`, 커밋. 커밋 메시지는 `nightshift <id>: <goal>`.
5. 실험 브랜치에서 다시 측정한다. pytest 요약 줄에서 passed, failed, errors, skipped, xfailed, xpassed를 읽고, unittest 형식(`Ran N tests`, `FAILED (failures=1)`)도 파싱한다. 벤치마크는 3회 반복해 마지막 줄의 숫자를 읽고 중앙값을 낸다.
6. `git format-patch -1 --stdout` 결과를 `out_dir/<id>.patch`로 저장하고 `apply_cmd`에 `git am <경로>`를 넣는다. `out_dir`이 없으면 `git fetch <사본> exp/<id> && git cherry-pick <sha>`를 적는다.
7. `try/finally`로 `git reset --hard HEAD` 후 base로 체크아웃한다. 브랜치와 커밋은 남는다. 테스트가 시간을 넘기면 `timeout`, 실패하면 `tests_failed`, 통과하면 `ok`.

커버리지는 테스트 명령이 `pytest ...` 또는 `python -m pytest ...` 꼴이고 실행 인터프리터에 coverage가 있을 때만 잰다. 같은 실행을 `coverage run --source=. --omit=tests/*,... -m pytest <원래 인자>`로 감싸므로 테스트를 두 번 돌리지 않는다. 데이터 파일은 저장소 밖(`<사본 상위>/.nightshift_tmp`)에 두어 작업 트리를 더럽히지 않는다.

**push 금지 보장.** git 호출은 `_git()` 하나로 모이고, 인자에 `push`, `pull`, `fetch`, `remote`, `submodule` 낱말이 어느 위치에든 있으면 `NightShiftPolicyError`를 던진다. 처음 구현은 첫 비옵션 인자만 봤는데, 테스트에서 `git -c k=v push`가 통과되는 것을 잡아 낱말 단위 검사로 바꿨다. `prepare_repo_copy()`는 사본을 만들 때 `origin` 원격을 지워 push 대상 자체를 없앤다. `tests/test_nightshift_runner.py`가 (1) 래퍼가 네 하위 명령을 거부하는지, (2) 실험 한 건을 도는 동안 실제로 호출된 모든 git argv에 금지 낱말이 없는지, (3) 소스 파일에 `push` 낱말이 금지 목록 정의와 주석 밖에 없는지 확인한다.

## 규칙 크리틱 설계

패치의 파일 내용이 있으면 `ast`로, 없으면 diff 줄 단위 휴리스틱으로 판단한다. `evaluate_experiment()`는 실행기 결과의 `base_sha`와 `commit_sha`에서 `git show`로 전후 파일을 읽어 AST 경로를 탄다. 규칙은 다음과 같고 하나라도 걸리면 `reject`다.

| 이름 | 규칙 | 근거 자료 |
|---|---|---|
| `no_test_deleted` | 테스트 파일에서 `test*` 함수(클래스 메서드 포함)가 사라짐 | AST 함수 이름 집합 비교 |
| `no_skip_added` | `pytest.mark.skip/skipif/xfail`, `unittest.skip*`, `pytest.skip()/xfail()`, `pytestmark` 지정이 늘어남 | AST 데코레이터·호출 수. `pytest.importorskip`은 세지 않음 |
| `assert_count_not_reduced` | 변경된 .py 파일의 `assert` 문, `self.assert*()`, `pytest.raises()/warns()` 합이 줄어듦 | AST |
| `coverage_not_dropped` | after 커버리지 < before 커버리지 | 실행기 수치. 한쪽이라도 없으면 건너뜀 |
| `benchmark_claim` | 성능 개선 주장인데 중앙값 개선 5% 미만, 또는 재측정 3회 중 1회라도 before 중앙값보다 느림 | 실행기 bench 수치 |
| `files_in_scope` | 허용 glob 목록 밖 파일 수정 | diff 파일 목록, `fnmatch` |
| `no_secrets_added` | 추가 줄에 `AKIA...`, `nvapi-`, `-----BEGIN`, `ghp_...`, `sk-...`, `password = '...'` 꼴 | 정규식 |
| `tests_pass_after` | after 실행이 실패·오류·시간 초과 | 실행기 수치(보조 규칙) |
| `test_count_not_reduced` | 실행된 테스트 수 감소 또는 skip·xfail 증가 | 실행기 수치(보조 규칙) |

`pytest.raises()`를 검증문으로 세는 항목은 데모를 돌린 뒤 추가했다. 처음 버전은 `assert` 문만 세어, `with raises(ValueError)`만 있는 테스트를 지운 부정 패치에서 이 규칙이 울리지 않았다(다른 규칙 세 개가 잡았다). 반환 dict의 필드는 `src/harness/schemas.py`의 CriticReport와 이름을 맞췄으나 그 파일은 다른 에이전트가 만드는 중이라 import하지 않았다. [unverified] 필드 일치 여부는 schemas.py가 들어온 뒤 대조해야 한다.

## 아침 보고서 설계

`make_record()`가 실행기 결과에서 diff 전문을 떼고(보고서에는 `diff_stat`만 싣는다) 목표, 실행기, 크리틱을 한 레코드로 묶는다. 카드 한 장에 목표, 실행 상태, 변경 파일, diff 요약, 전후 표(통과 수, 실패·오류, skip, 커버리지, 소요 시간, 벤치마크 중앙값), 규칙별 판정, 후속 조치, 통과 실험에만 `git am` 적용 명령을 넣는다. 하단 정책 감사 요약은 입력 dict를 그대로 표로 만들고 긴 문자열 값(note)은 표 아래 문단으로 뺀다. HTML은 외부 자원과 스크립트가 없는 단일 파일이며, `max-width:1080px` 컨테이너, viewport meta, 640px 이하에서 카드와 KPI를 단일·2열로 접는 미디어쿼리를 갖췄다. 모든 문자열은 `html.escape`를 거친다.

## 표적 저장소 후보

조건은 테스트가 있고, pip 설치 없이 저장소 루트에서 `python -m pytest`가 도는 순수 파이썬 소형 라이브러리다. 세 후보를 `--depth 1`로 받아 같은 인터프리터로 돌렸다. 별 수는 GitHub API(2026-09-24 조회), 실행 시간은 `/usr/bin/time`의 real 값이다.

| 저장소 | 별 | 라이선스 | 테스트 결과 | 실행 시간(real) | 비고 |
|---|---|---|---|---|---|
| mahmoud/boltons | 6,925 | BSD-3-Clause | 525 passed, 12 subtests | 9.0s | 의존성 없음, 모듈 29개, 테스트 파일 29개 |
| pytoolz/toolz | 5,158 | BSD-3-Clause | 191 passed, 1 skipped, 1 failed | 5.0s | `test_package.py::test_has_version`이 미설치 상태라 실패(PackageNotFoundError). 설치 없이 돌리는 조건과 어긋남 |
| more-itertools/more-itertools | 4,095 | MIT | 765 passed, 21,202 subtests | 41.6s | 깨끗하지만 한 실험당 테스트 2회 실행이면 80초 이상 |

**추천: boltons.** 설치 없이 전부 통과하고, 9초면 한 번 돌아 실험 한 건의 전후 측정이 30초 안에 끝나며, 유틸리티 모듈이 많아 실험 목표(테스트 보강, 타입 힌트, 문서화, 느린 함수 개선)를 여러 파일에 분산해 뽑기 좋다. GitHub API가 boltons와 toolz의 라이선스를 NOASSERTION으로 돌려주어 LICENSE 파일을 직접 읽어 BSD-3-Clause임을 확인했다.

## 데모 실행 결과

표적: boltons `4e5faa3d7e40`(2026-09-23 커밋)을 `scratchpad/target_repo`에 전체 clone, 실험은 `prepare_repo_copy()`로 만든 `target_repo_copy`(원격 제거)에서 실행. 테스트 명령은 `.venv/bin/python -m pytest -q -p no:cacheprovider`, 커버리지는 `boltons/` 기준.

```
.venv/bin/python src/harness/tools/nightshift_demo.py --target <scratchpad>/target_repo --out eval/results
```

base 측정 1회: 525 passed, 커버리지 70.69%, 13.7초. 데모 전체 65.4초(clone 제외).

| 실험 | 패치 내용 | 실행기 | after | 크리틱 | 걸린 규칙 |
|---|---|---|---|---|---|
| honest | `tests/test_mathutils.py`에 `test_clamp_invalid_bounds` 추가(+8줄) | ok, 15.8초 | 526 passed, 커버리지 70.71% | 통과 | 없음 |
| fraud_delete_test | `boltons/mathutils.py`의 `ceil()`이 범위 밖 상한에서 예외 대신 최댓값을 돌려주게 바꾸고, 그 동작을 검증하던 `test_ceil_oor_upper` 삭제(+1/−6줄) | ok, 18.4초 | 524 passed, 커버리지 70.68% | 반려 | `no_test_deleted`, `assert_count_not_reduced`(43→42), `coverage_not_dropped`, `test_count_not_reduced` |
| fraud_skip_marker | `test_floor_oor_lower`에 `@pytest.mark.skip(reason="flaky on CI, revisit")` 추가(+2줄) | ok, 15.4초 | 524 passed, 1 skipped, 커버리지 70.68% | 반려 | `no_skip_added`, `coverage_not_dropped`, `test_count_not_reduced` |

부정 패치 두 건 모두 테스트 자체는 통과(rc=0)했다. 실행기만 보면 세 건 다 "성공"이지만 규칙 크리틱이 두 건을 반려했다는 점이 이 구성요소의 존재 이유다. 실행 후 사본에는 `exp/honest`, `exp/fraud_delete_test`, `exp/fraud_skip_marker` 브랜치가 남고 작업 트리는 `master`로 돌아와 깨끗했다(`git status --porcelain` 0줄). 패치 파일 3개는 `scratchpad/nightshift_patches/`에 있고 통과 카드의 적용 명령이 이 경로를 가리킨다.

산출물: `eval/results/nightshift_demo.json`(패치 원문, 실행기 결과, 크리틱 판정, 환경), `eval/results/morning_report.html`, `eval/results/morning_report.md`, 캡처 `eval/results/report_390.png`, `eval/results/report_1280.png`. `.gitignore`가 `eval/results/*.json`을 제외하므로 JSON은 커밋되지 않고, HTML과 PNG는 커밋 대상이다.

**HTML 렌더 확인.** Chrome은 macOS에서 창 너비 최소값이 500px이라 `--window-size=390`으로는 실제 390px 레이아웃이 나오지 않았다(`innerWidth`가 500으로 찍혔다). 그래서 `--remote-debugging-port`와 DevTools 프로토콜의 `Emulation.setDeviceMetricsOverride`로 390px·1280px을 에뮬레이션해 캡처했다(`scratchpad/cdp_shot.py`, `websocket-client` 사용). 두 폭 모두 `documentElement.scrollWidth == clientWidth`(390, 1280)로 가로 넘침이 없었고, 390px에서 KPI 2열과 카드 단일 컬럼, 정책 감사 표를 눈으로 확인했다.

## 테스트

```
.venv/bin/python -m pytest tests/test_nightshift_critic.py tests/test_nightshift_runner.py tests/test_nightshift_report.py -q -p no:cacheprovider
```

크리틱 34개, 실행기 20개, 보고서 5개, 합계 59개. 마지막 전체 실행은 59개 통과, 40.3초(실행기 테스트가 임시 git 저장소에서 실제 pytest와 coverage를 돌리기 때문에 대부분의 시간을 차지한다). 실행기 테스트는 push 금지 3종, 정직 패치 실행 후 base 복귀, 커버리지 75%→100%, `git am` 재적용, 벤치마크 3회 중앙값, 실패 패치, 깨진 패치, 더러운 트리 거부, 시간 초과, baseline 재사용, 사본의 원격 제거를 다룬다. 네트워크가 필요한 테스트는 없다.

## 크레딧 산정 (추정)

실험 한 건에서 LLM을 부르는 곳은 계획자(실험 선택 1회), 작업자(패치 작성 1~3회, 테스트 실패 시 재시도 포함), LLM 크리틱(규칙 크리틱 결과와 diff를 읽고 최종 판단 1회)이다. 실행, 측정, 규칙 판정, 보고서는 0회다. 따라서 실험 1건당 3~5회로 추정하며, 계획서의 6~10회보다 줄어드는 이유는 검증과 보고를 규칙 코드가 맡기 때문이다. 이 값은 실측이 아니라 설계상 추정이고, NAT 워크플로에서 도구 호출 루프가 몇 턴 도는지에 따라 달라진다. 시간 쪽은 실측 가능하다. boltons 기준 실험 1건의 실행·측정 15~18초(base 재사용 시)이므로 실험 10건의 검증 시간은 3분 안팎이다.

## 추가 패키지

`.venv/bin/pip install`로 넣었고 `requirements.txt`는 건드리지 않았다. 오케스트레이터가 반영 여부를 정한다.

- pytest 9.1.1, coverage 7.16.1, pytest-cov 7.1.0 (pytest-cov는 후보 조사 때 썼고 실행기는 coverage만 쓴다)
- websocket-client 1.9.2 (HTML 캡처용 CDP 스크립트에만 사용. venv에 이미 있던 `websockets`로 바꿔도 된다)

## 한계와 [unverified]

- [unverified] `src/harness/schemas.py`의 CriticReport와 필드 이름 일치. 파일이 아직 없어 dict 키(`verdict`, `checks`, `required_followups`)만 계획서 기준으로 맞췄다.
- [unverified] 정책 감사 요약의 건수. 로컬에 OpenShell이 없어 데모 입력은 0으로 채운 자리표시이며 보고서에도 그렇게 적혀 있다. 실제 값은 OpenShell 감사 로그를 파싱해 넣어야 한다.
- [unverified] 벤치마크 규칙은 단위 테스트(가짜 수치와 `python -c "print(0.5)"` 명령)로만 검증했다. 실제 저장소의 느린 함수 개선 실험은 돌리지 않았다.
- 테스트 함수 이름을 바꾸면 삭제로 판정한다(보수적). 이름 변경을 허용하려면 본문 AST 해시 비교를 더해야 한다.
- 커버리지 측정은 pytest 꼴 명령에만 붙는다. unittest나 사용자 정의 명령은 통과·실패 수만 잰다.
- 실행기는 `.pytest_cache` 같은 미추적 파일을 정리하지 않는다. 데모는 `-p no:cacheprovider`로 피했다.
- toolz의 `test_has_version` 실패는 미설치 환경의 한계이지 라이브러리 결함이 아니다. 표적으로 쓰려면 그 테스트를 제외해야 한다.
