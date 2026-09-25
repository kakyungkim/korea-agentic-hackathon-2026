# FlyGate 촬영 목록

작성 2026-09-25. 대본은 `docs/video/script_flygate.md`, 문장과 슬라이드 매핑은
`assets/video/08_timeline.txt`에 있다. 문장 번호는 그 두 문서와 같은 번호다.
앞 주제(PharmaSignal) 판은 `docs/video/shotlist.md`에 그대로 남겨 두었다.

## 쓸 수 있는 자산

아래는 저장소에 **실제로 있는 파일**만 적었다. 없는 화면은 목록에 넣지 않았다.

| 자산 | 경로 | 상태 |
|---|---|---|
| 파이프라인 도식 | `docs/figures/architecture_pipeline.png` | 2400x1560, 있음 |
| 케이스 대조 그림 | `docs/figures/results_case.png` | 2400x1860, 있음 |
| 영상 슬라이드 13장 | `assets/video/slides/s01.png` ~ `s13.png` | 2026-09-25 렌더해 육안 확인, 있음 |
| 슬라이드 생성기 | `assets/video/slides_flygate.py` | 이번 주제로 새로 씀 |
| 케이스 결과 JSON | `eval/results/case_niraparib.json` | 7단계 근거와 SHA256, 있음 |
| 케이스 브리프 | `eval/results/case_niraparib_brief.md` | 사람이 읽는 한 장, 있음 |
| 에이전트 실행 결과 | `eval/results/nat_run_author_flydock.json` | 주장 4건 전부 근거 ID, 있음 |
| 적발률(LLM 포함) | `eval/results/critic_verdict_output_llm.json` | `average_score` 0.9697, 있음 |
| 적발률(결정 규칙만) | `eval/results/critic_verdict_output_deterministic.json` | `average_score` 0.0303, 있음 |
| DiffDock 호출 기록 | `eval/results/diffdock_smoke.txt`, `diffdock_client_run.txt` | HTTP 200, 있음 |
| 샌드박스 스모크 로그 | `eval/results/openshell_smoke_flydock.txt` | `pass=18 fail=0`, 있음 |
| 샌드박스 정책 | `policies/flydock.yaml` | 있음 |
| 과잉해석 규칙 | `src/harness/tools/overclaim_rules.py` | `RULES` 15종 |
| 평가 케이스 | `eval/cases.jsonl` | 33건 |
| 워크플로 설정 | `configs/author.yml`, `configs/critic.yml`, `configs/eval.yml` | 있음 |

**아직 없는 것.** 터미널 녹화 mp4가 없다. `assets/scripts/record_demo.py`가 앞 버전 CLI를
가리키고 있어 이 저장소 진입점으로 고쳐야 돌아간다. 이 작업 범위 밖이므로 터미널 컷은
전부 선택 사항으로 적었고, 없으면 슬라이드로 대신한다.

## 실행 화면에 쓸 명령

터미널 장면은 꾸며 내지 않고 아래 명령의 실제 출력을 쓴다. 넷 모두 이 저장소에서 돌아간 적이 있다.

```bash
.venv/bin/python -m pytest -q -m "not network"          # 313 passed
.venv/bin/nat validate --config_file configs/author.yml # 설정 검증
.venv/bin/python scripts/run_case_demo.py --out eval/results --offline
scripts/openshell_smoke.sh flydock                      # 허용/차단/쓰기/TLS 검증
```

샌드박스 안 로그를 직접 띄우려면 VM에서 `openshell logs flydock --since 15m`을 쓴다.
VM 기동 절차는 `docs/notes/openshell-setup.md`에 있다.

---

## 구간별 화면

### 1. 문제 (문장 1~5, 약 28초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 1-1 | 1 | 슬라이드 1 표지 | `slides_flygate.py` s01 |
| 1-2 | 2 | 슬라이드 2. 두 경로 카드 | s02 |
| 1-3 | 3 | 슬라이드 2에서 -10.178과 -7.967에 강조 상자 | s02 위에 편집으로 얹는다 |
| 1-4 | 4 | 슬라이드 3. 반려된 주장 원문 | s03 |
| 1-5 | 5 | 슬라이드 3의 "판정" 줄만 확대 | s03 크롭 |

컷 1-4의 문구는 지어낸 것이 아니라 `eval/results/case_niraparib_brief.md`의 반려 사유 원문을
줄인 것이다. 원문을 띄우고 싶으면 브리프의 "교차 타깃 순위 금지" 항목을 그대로 캡처한다.

### 2. 계보와 팀 (문장 6~8, 약 22초) ★ 교체 구간

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 2-1 | 6~8 | 슬라이드 4 한 장 | s04 |

**이 구간은 통째로 팀원 A 녹화로 바꾼다.** 도메인 전문가가 직접 말하는 자리이고, 지금은
나레이션 세 문장으로 채워 두어 그대로도 렌더된다.

- 슬라이드 4가 문장 6~8에 **정확히 하나로** 대응한다. 그래서 교체할 때 잘라 낼 구간이
  슬라이드 경계와 일치하고 앞뒤 타이밍이 흔들리지 않는다.
- 녹화가 오면 `02_나레이션.txt`의 둘째 문단 세 줄을 지우고, `08_timeline.txt`에서 슬라이드 4
  줄을 지운 뒤 뒤 번호와 문장 범위를 3씩 당긴다. 절차는 대본의 "녹화가 오면 바꾸는 절차"에 있다.
- 클립 길이는 20초에서 30초 사이로 받는다. 지금 자리는 22.2초다.
- 화면 구성은 말하는 사람 얼굴을 기본으로 두고, `drug.flybrain.kr` 데모 화면을 작게 끼우는
  쪽을 권한다. 데모 캡처를 못 뜨면 슬라이드 4를 배경으로 깐다.
- 실명 자막을 넣지 않는다. 저장소를 공개로 돌리므로 역할로만 적는다(`docs/notes/credits.md`).

### 3. 흐름 (문장 9~19, 약 62초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 3-1 | 9 | 슬라이드 5. 도식 왼쪽 "입력" 상자로 천천히 들어간다 | `docs/figures/architecture_pipeline.png` 원본을 쓰고 s05는 예비 |
| 3-2 | 10 | 같은 도식의 "작성자 워크플로"와 "도구 층" | 원본 크롭 |
| 3-3 | 11 | 슬라이드 6 | s06 |
| 3-4 | 12 | 슬라이드 6의 `200` 배지. 또는 `diffdock_smoke.txt` 원문 | s06 크롭, 로그는 선택 |
| 3-5 | 13 | 슬라이드 6 아래 두 카드 | s06 |
| 3-6 | 14 | 슬라이드 7. 세 숫자 | s07 |
| 3-7 | 15 | `eval/results/nat_run_author_flydock.json`의 `claims` 배열 | `jq` 출력이나 에디터 캡처 |
| 3-8 | 16~19 | 슬라이드 8. 문장마다 카드 하나씩 켠다 | s08에 강조를 편집으로 얹는다 |

**컷 3-1과 3-2에서 주의할 것.** 도식에 `jev_triage`(점선 상자)와 `flybrain_pose`("계획, 아직
NAT에 등록 안 됨")가 들어 있다. 둘 다 아직 구현되지 않았고 나레이션도 언급하지 않는다.
크롭할 때 그 표시를 자르지 않는다. 자르면 동작하는 도구처럼 보인다.

컷 3-8은 한 슬라이드에 네 문장이 걸려 가장 길다(21.3초). 카드를 하나씩 밝히는 강조로 끌고
가고, 밋밋하면 문장 17 자리에 `configs/critic.yml`과 `configs/author.yml`을 좌우로 연 화면을
2초쯤 끼운다.

### 4. 결과 (문장 20~24, 약 32초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 4-1 | 20 | `docs/figures/results_case.png` 왼쪽 열(경로 A) | 원본을 쓰고 s09는 예비 |
| 4-2 | 21 | 같은 그림 오른쪽 열과 "참조 집합 없음" 점선 상자 | 원본 크롭 |
| 4-3 | 22 | 그림의 "참조" 행 전체를 한 화면에 | 원본 크롭 |
| 4-4 | 23 | 슬라이드 10. 16/16과 0/17 | s10 |
| 4-5 | 24 | 슬라이드 10의 1/16을 강조 | s10 위에 강조 |

강조 상자는 PNG 위에 영상 편집으로 얹고 원본 그림은 고치지 않는다. 그림을 고치려면
`scripts/make_figures.py`를 다시 돌려야 한다.

**컷 4-4와 4-5를 붙여 둔다.** 적발률은 두 수치를 함께 보여야 뜻이 산다. 컷을 나누더라도
16/16과 1/16이 같은 화면에 남아 있게 한다.

### 5. 안전 (문장 25~29, 약 24초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 5-1 | 25 | 슬라이드 11. 또는 `policies/flydock.yaml`의 `network_policies` | s11, 에디터 캡처는 선택 |
| 5-2 | 26 | 슬라이드 11의 세 숫자와 허용 호스트 태그 | s11 |
| 5-3 | 27 | 슬라이드 12의 첫 두 줄(github.com DENIED) | s12 |
| 5-4 | 28 | 슬라이드 12의 curl 줄과 L7 줄 | s12 |
| 5-5 | 29 | `openshell_smoke_flydock.txt`의 `summary: pass=18 fail=0` | 로그 원문 캡처 |

**컷 5-3이 이 영상에서 가장 값어치 있는 증거다.** 로그 원문을 그대로 띄우고
`reason:endpoint github.com:443 is not allowed by any policy`까지 읽히게 글자를 키운다.
슬라이드 12는 그 원문을 줄만 다듬어 옮긴 것이고, 원문 그대로를 띄우려면
`eval/results/openshell_smoke_flydock.txt`의 50~61행을 캡처한다.

### 6. 마무리 (문장 30~32, 약 18초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 6-1 | 30~32 | 슬라이드 13 | s13 |

한계 세 줄이 슬라이드에 이미 있다. 자막과 겹치지 않게 아래 여백을 확인한다.

## 배경음악

`assets/video/bgm_pick.sh set <테마>`로 고르고 `bgm_themes.tsv`의 후보를 쓴다. macOS 기본
Apple Loops라 라이선스 문제가 없다. `build.sh`가 앞 13초와 뒤 17초에만 깔고 본문은 나레이션만 둔다.

## 렌더 절차

1. `python assets/video/slides_flygate.py` 실행. `assets/video/slides/`에 13장이 생긴다.
2. `cd assets/video && for f in slides/s*.png; do cp "$f" "slide_${f##*/s}"; done`
   `build.sh` 4단계가 같은 폴더의 `slide_NN.png`를 열기 때문이다.
3. `assets/video/09_caption.py`의 `NUM`을 대본 끝의 제안표로 바꾼다.
4. `assets/video/build.sh` 실행.

## 렌더 뒤 점검

1. `assets/video/10_overlap_check.py`로 자막이 슬라이드를 침범했는지 본다. 문장 7과 20이 가장 길다.
2. 최종 mp4 길이가 2분 30초에서 3분 사이인지 확인한다. 추정은 3분 6초이고 `rate=+8%` 때문에
   실측은 더 짧게 나올 가능성이 크다. 3분을 넘으면 문장 7, 20, 23을 줄인다.
3. 화면에 띄운 수치를 `eval/results/*.json`과 한 번 더 대조한다.
4. 자막에 앞 주제 고유명(PharmaSignal 케이스 3건, metformin, semaglutide, amoxicillin)이나
   v0 스택 이름(Bright Data, Qwen, Daytona, Nosana)이 남아 있지 않은지 본다.
5. 문장 30의 자막이 "샌드박스 안에서 DiffDock을 부른 것은 아니고"로 정확히 나오는지 본다.
   이 한 줄이 시연 범위를 정직하게 가르는 자리다.
