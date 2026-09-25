# 촬영 목록

작성 2026-09-25. 대본은 `docs/video/script.md`, 문장과 슬라이드 매핑은
`assets/video/08_timeline.txt`에 있다. 문장 번호는 그 두 문서와 같은 번호다.

## 쓸 수 있는 자산

아래는 저장소에 **실제로 있는 파일**만 적었다. 없는 화면은 목록에 넣지 않았다.

| 자산 | 경로 | 상태 |
|---|---|---|
| 아키텍처 도식 | `docs/figures/architecture_pharmasignal.png` | 2400x1500, 있음 |
| 케이스 포레스트 플롯 | `docs/figures/results_pharmasignal.png` | 2400x1320, 있음 |
| 케이스 결과 JSON | `eval/results/pharmasignal_cases.json` | 3건, 있음 |
| 크리틱 평가 결과 | `eval/results/critic_verdict_output.json` | `average_score` 1.0, 있음 |
| 크리틱 판정 원문 | `eval/results/workflow_output.json` | `checks` 배열, 있음 |
| 샌드박스 스모크 로그 | `eval/results/openshell_smoke.txt` | pass=9 fail=0, 있음 |
| 도구 응답 캐시 | `eval/results/pharmasignal_cache_*.json` | 13개, 있음 |
| 워크플로 설정 | `configs/author.yml`, `configs/critic.yml`, `configs/eval.yml` | 있음 |
| 샌드박스 정책 | `policies/pharmasignal.yaml` | 있음 |
| 지표 계산 코드 | `src/harness/tools/pharmasignal_openfda.py` | `disproportionality()` |
| 영상 슬라이드 생성기 | `assets/video/slides.py` | 문구가 앞 버전 그대로다. 교체 후 렌더 |
| 터미널 화면 렌더러 | `assets/scripts/record_demo.py` | 실행 명령을 이 저장소 진입점으로 바꿔야 함 |

**아직 없는 것.** 영상 슬라이드 PNG(`assets/video/slides/s01.png` 등)는 `slides.py`를 이번 문구로
바꿔 렌더해야 생긴다. 터미널 녹화 mp4도 `record_demo.py`를 고쳐 돌려야 생긴다. 둘 다 이 작업 범위 밖이다.

## 실행 화면에 쓸 명령

터미널 장면은 꾸며 내지 않고 아래 명령의 실제 출력을 쓴다. 넷 모두 이 저장소에서 돌아간 적이 있다.

```bash
.venv/bin/python src/harness/tools/pharmasignal_cases.py     # 케이스 3건, JSON 저장
.venv/bin/python -m pytest -q -m "not network"               # 128 passed
.venv/bin/nat eval --config_file configs/eval.yml            # 크리틱 적발률
scripts/openshell_smoke.sh pharmasignal                      # 허용/차단/쓰기 검증
```

샌드박스 안 로그를 직접 띄우려면 VM에서 `openshell logs pharmasignal --since 15m`을 쓴다.
VM 기동 절차는 `docs/notes/openshell-setup.md`에 있다.

---

## 구간별 화면

### 1. 문제 (문장 1~5, 약 25초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 1-1 | 1 | 슬라이드 1 표지 | `slides.py` s01 |
| 1-2 | 2~3 | 슬라이드 2. 20,692,690과 440,270을 큰 숫자로 | `slides.py` s02. 값은 `pharmasignal_cases.json`의 `counts` |
| 1-3 | 4~5 | 슬라이드 3. FAERS, 라벨, 문헌 세 갈래 도식 | `slides.py` s03 |

수치 자막 아래에 출처 한 줄을 작게 깐다. `openFDA drug/event, 데이터 기준일 2026-07-30`.

### 2. 앞 버전과 한계 (문장 6~9, 약 20초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 2-1 | 6 | 슬라이드 4. 앞 버전 저장소 주소 `github.com/kakyungkim/pharmasignal-v0` | `slides.py` s04 |
| 2-2 | 7~8 | 같은 슬라이드에 못 본 것 세 줄(FAERS 미호출, 라벨 대조 없음, 문헌은 제목만) | 근거는 `README.md`의 "배경과 계보" |
| 2-3 | 9 | 못 본 것에서 이번 도구 3종으로 이어지는 화살표 | 슬라이드 안 애니메이션 없이 정적 도식 |

앞 버전 저장소 화면을 실제로 띄울지는 정하지 않았다 [unverified]. 공개 저장소이지만 캡처를
아직 뜨지 않았으므로, 뜨지 못하면 슬라이드의 주소 텍스트로 대신한다.

### 3. 이번 판 (문장 10~20, 약 60초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 3-1 | 10~11 | 터미널. `pharmasignal_cases.py` 실행과 첫 줄 출력 | `record_demo.py`로 렌더하거나 실제 터미널 녹화 |
| 3-2 | 12 | `docs/figures/architecture_pharmasignal.png`의 도구 3종 구간을 확대 | 원본 PNG를 크롭해 쓴다 |
| 3-3 | 13 | `eval/results/` 파일 목록에서 `pharmasignal_cache_*.json` 13개 | `ls eval/results/` 출력 |
| 3-4 | 14~15 | 슬라이드 6. 두 물음을 나란히 | `slides.py` s06 |
| 3-5 | 16~17 | `src/harness/tools/pharmasignal_openfda.py`의 `disproportionality()` 본문 | 에디터 화면 캡처. PRR, ROR, 카이제곱 계산부만 |
| 3-6 | 16~17 | 아키텍처 그림의 계산 상자 배지("파이썬이 계산, 모델은 계산하지 않음") 확대 | 같은 PNG 크롭 |
| 3-7 | 18~19 | `configs/author.yml`과 `configs/critic.yml`을 좌우로 | 두 파일을 나란히 연 에디터 |
| 3-8 | 20 | `eval/results/workflow_output.json`의 `checks` 배열 | JSON 뷰어나 `jq` 출력 |

컷 3-5와 3-7은 코드와 설정을 그대로 보여 주는 자리다. 글자가 작아지지 않게 필요한 블록만 잘라 확대한다.

### 4. 실제 결과 (문장 21~25, 약 30초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 4-1 | 21 | `docs/figures/results_pharmasignal.png` 전체 | 원본 그대로 |
| 4-2 | 22 | 첫째 행(metformin, PRR 72.83, 19,411건, 박스 경고) 강조 | 같은 PNG에 강조 상자를 얹는다 |
| 4-3 | 23 | 둘째 행(semaglutide, PRR 7.22) 강조 | 같은 방식 |
| 4-4 | 24 | 셋째 행(amoxicillin, PRR 0.87, 39건, 라벨 미기재)과 PRR = 1 기준선 | 같은 방식 |
| 4-5 | 25 | 슬라이드 9. 세 케이스 요약표 | `slides.py` s09. 값은 `pharmasignal_cases.json` |

강조 상자는 PNG 위에 영상 편집으로 얹고 원본 그림은 고치지 않는다. 그림을 고치려면
`scripts/make_figures.py`를 다시 돌려야 한다.

### 5. 안전 (문장 26~30, 약 25초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 5-1 | 26 | `policies/pharmasignal.yaml`의 `filesystem_policy`와 `network_policies` | 에디터 캡처 |
| 5-2 | 27 | 허용 도메인 네 줄 | `openshell_smoke.txt`의 "허용 도메인" 절 4줄 |
| 5-3 | 28 | 차단 로그 두 줄을 한 줄씩 띄움 | `openshell_smoke.txt`의 `NET:OPEN [MED] DENIED ... example.com:443`과 `github.com:443` |
| 5-4 | 29 | 파일시스템 결과 세 줄과 `summary: pass=9 fail=0` | 같은 파일 |
| 5-5 | 30 | `eval/results/critic_verdict_output.json` 전체 | 파일이 짧아 한 화면에 들어간다 |

컷 5-3이 이 영상에서 가장 값어치 있는 증거다. 로그 원문을 그대로 띄우고 `reason:endpoint
github.com:443 is not allowed by any policy`까지 읽히게 글자를 키운다.

### 6. 한계와 마무리 (문장 31~33, 약 17초)

| 컷 | 문장 | 화면 | 만드는 법 |
|---|---|---|---|
| 6-1 | 31 | 슬라이드 12 아래쪽. NemoGuard 차단 시연을 못 했다는 한 줄 | `slides.py` s12 |
| 6-2 | 32~33 | 슬라이드 13 마무리 | `slides.py` s13 |

## 배경음악

`assets/video/bgm_pick.sh set <테마>`로 고르고 `bgm_themes.tsv`의 후보를 쓴다. macOS 기본
Apple Loops라 라이선스 문제가 없다. `build.sh`가 앞 13초와 뒤 17초에만 깔고 본문은 나레이션만 둔다.

## 렌더 뒤 점검

1. `assets/video/10_overlap_check.py`로 자막이 슬라이드를 침범했는지 본다. 문장 12와 20이 가장 길다.
2. 최종 mp4 길이가 2분 30초에서 3분 사이인지 확인한다. 추정은 2분 55초이고 실측은 다를 수 있다.
3. 화면에 띄운 수치를 `eval/results/*.json`과 한 번 더 대조한다.
4. 자막에 앞 버전 고유명(Bright Data, Qwen, Daytona, Nosana)이 남아 있지 않은지 본다.
