# 제출용 그림 2종

작성 2026-09-24. 담당 경로: `docs/figures/`, `scripts/make_figures.py`, 이 문서.
그림은 `scripts/make_figures.py` 하나로 다시 만든다. 손으로 고친 PNG는 두지 않는다.

| 파일 | 크기 | 말하는 것 |
|---|---|---|
| `docs/figures/architecture_pharmasignal.png` | 2400x1500, 300dpi | 지표는 파이썬이 계산하고 모델은 해석만 하며, 독립 크리틱과 OpenShell 샌드박스가 그 결과를 사람에게 넘기기 전에 가로막는다 |
| `docs/figures/results_pharmasignal.png` | 2400x1320, 300dpi | 케이스 3건에서 PRR과 95% 신뢰구간이 라벨 기재 여부, 문헌 건수와 함께 갈린다(metformin 72.83, semaglutide 7.22, amoxicillin 0.87) |

## 실행

```bash
.venv/bin/pip install matplotlib          # 최초 1회, 설치본은 3.11.2
.venv/bin/python scripts/make_figures.py
```

표준출력에 폰트 family, 저장 경로, 픽셀 크기, 케이스별 수치가 찍힌다. 두 PNG를 덮어쓰므로
재실행만으로 갱신된다.

## 폰트 설치 경로

Pretendard v1.3.9(OFL) 4종을 `docs/figures/fonts/`에 둔다. GitHub 릴리스 zip에서만 받아진다
(raw, jsdelivr, unpkg는 실패한다). ttf는 zip 안 `public/static/alternative/` 하위에 있다.

```bash
curl -sL -o /tmp/pretendard.zip \
  https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip
unzip -q /tmp/pretendard.zip -d /tmp/pretendard
find /tmp/pretendard -name '*.ttf'        # 실제 경로를 먼저 확인
cp /tmp/pretendard/public/static/alternative/Pretendard-{Regular,Medium,SemiBold,Bold}.ttf \
   docs/figures/fonts/
```

스크립트의 `register_fonts()`가 `docs/figures/fonts/Pretendard-*.ttf`를 모두
`font_manager.fontManager.addfont`로 등록하고 `rcParams["font.family"]`를 `Pretendard`로 둔다.
폰트가 없으면 어떤 그림도 그리지 않고 설치 절차를 가리키며 멈춘다.

팔레트는 차분한 Tableau 뮤트 톤을 상수로 모아 두었다(`BLUE`는 모델, `TEAL`은 도구, `GREEN`은
파이썬 계산, `PLUM`은 크리틱, `BRICK`은 차단). 원색과 컬러 이모지는 쓰지 않고, 아이콘은
막대, 문서, 돋보기, 2x2 표, 체크, 사람 모양을 도형으로 직접 그린다.

## 그림 1의 내용

왼쪽 사용자 입력에서 시작해 계획 수립(Nemotron 3 Super), 도구 3종(openFDA FAERS, DailyMed 라벨,
PubMed), 지표 계산(파이썬), 트리아지 메모(Nemotron 3.5 Lightning), 독립 크리틱(critic.yml, 쓰기 도구 없음)
순으로 흐르고, 크리틱에서 통과와 반려로 갈린다. 지표 계산 상자만 테두리를 굵게 하고
"파이썬이 계산, 모델은 계산하지 않음" 배지를 달아 핵심 메시지를 분리했다.

전체를 OpenShell 샌드박스 점선 상자로 감쌌고, 경계 위에 허용 도메인 4곳을 적었다. 사용자 입력과
사람 전달, 반려는 경계 밖에 두어 화살표가 경계를 넘는 지점이 보이게 했다. 도구 블록에서
경계 밖으로 나가려는 점선 화살표 하나는 경계에서 차단 표시로 끊고 "github.com, example.com 등은
차단되고 감사 로그에 남는다"를 붙였다.

NVIDIA 기술 라벨은 실제 저장소 상태에 맞춰 달았다. Nemotron 3 Super는 `configs/author.yml`과
`configs/critic.yml`의 `nvidia/nemotron-3-super-120b-a12b`, 작업자는 `nvidia/nemotron-3.5-lightning-30b-a3b`,
NeMo Agent Toolkit은 두 워크플로 YAML, NeMo Guardrails 정책은 `configs/guardrails/`,
OpenShell은 `policies/pharmasignal.yaml`에서 확인한 것이다. **NeMo Retriever만 구현되어 있지 않아
"라벨 RAG는 확장 계획"이라고 작은 글씨로 적었다.** 구현하면 이 문구를 도구 한 줄로 올린다.

## 그림 2의 내용

`eval/results/pharmasignal_cases.json`을 읽어 그린 포레스트 플롯이다. 하드코딩한 수치는 없고,
`load_cases()`가 케이스별로 `faers.prr`, `faers.prr_ci95`, `summary.faers_a`, `summary.labeled`,
`summary.label_sections`, `summary.pubmed_total`, `summary.evans_signal`, `summary.chi2_yates`,
`summary.ror_signal`을 꺼낸다. 케이스 수가 늘면 행이 따라 늘어난다.

가로축은 로그 눈금이고 PRR = 1 기준선(파선)과 Evans 기준 PRR ≥ 2(점선)를 함께 그렸다.
Evans 기준(a≥3, PRR≥2, Yates 보정 카이제곱≥4)을 충족한 케이스는 파랑, 미충족은 회색이다. 왼쪽에 약물명,
이상사례, FAERS 동반보고 건수를, 오른쪽에 PRR(95% CI), 라벨 기재 여부와 기재 섹션, PubMed 건수를
적었다. 아래 각주에 출처 파일과 실행일, openFDA 데이터 기준일을 남겼다.

## 그림에 쓴 수치 (2026-09-25 재실행분)

`eval/results/pharmasignal_cases.json`의 `generated_at`은 2026-09-24T15:35:03+00:00,
openFDA `data_last_updated`는 2026-07-30이다. 재실행은 캐시만 읽었고 아래 수치는 이전 실행과 같다.

| 케이스 | PRR (95% CI) | FAERS 동반보고 | 라벨 | PubMed |
|---|---|---|---|---|
| metformin, Lactic acidosis | 72.83 (71.22~74.48) | 19,411건 | 기재(이상반응, 박스 경고, 경고와 주의) | 1,139건 |
| semaglutide, Pancreatitis | 7.22 (6.84~7.63) | 1,302건 | 기재(이상반응, 경고와 주의) | 119건 |
| amoxicillin, Retinal detachment | 0.87 (0.64~1.20) | 39건 | 미기재 | 8건 |

## 점검 결과

두 PNG를 렌더 후 직접 열어 확인했다. tofu(□)는 한 곳도 없고, 글씨 잘림과 상자 밖 넘침도 없다.
1차 렌더에서 찾아 고친 것은 셋이다.

1. 허용 도메인 목록이 트리아지 메모 상자와 지표 계산 상자 위로 겹쳤다. 목록을 한 줄로 합쳐
   경계 바깥 위쪽으로 올리고, `/work/out` 쓰기 제한 설명은 경계 안쪽으로 내렸다.
2. 그림 2의 "PRR = 1 기준선" 글자를 기준선이 관통했다. 기준선 왼쪽으로 붙여 오른쪽 정렬했다.
3. 축 이름 "PRR (보고비 비례보고비...)"의 겹말과 부제의 축 설명 중복을 정리했고,
   PubMed 건수에 천 단위 쉼표를 넣어 FAERS 표기와 맞췄다.

### 2026-09-25 재렌더 점검

`disproportionality()`에 `chi2_yates`, `ror_signal`, `haldane_applied`가 생겨 두 그림을 다시 뽑고
PNG를 직접 열어 확인했다. 그림 2는 부제에 "Evans 기준의 카이제곱은 Yates 연속성 보정을 한 값이다"와
ROR 기준과의 일치 건수를 한 줄 더했고(일치 건수는 데이터에서 세므로 어긋나면 문구가 바뀐다),
범례를 "Yates 보정 카이제곱≥4"로 고쳤다. 부제가 두 줄이 되면서 세 축의 높이를 0.64에서 0.615로 줄였다.
ROR 값은 별도 행이나 열로 넣지 않았다. 세 케이스 모두 Evans 계열과 판정이 같아 표시가 겹치기만 한다.

그림 1에서는 `NemoGuard 토픽 제어` 배지를 `NeMo Guardrails 정책`으로 바꿨다. 판정 모델이 호스팅 쪽
오류로 응답하지 않아 차단을 시연하지 못했으므로, 배선이 확인된 계층만 남긴 것이다.
1차 렌더에서 배지 아래 설명 "환자 개별 복약 조언을 차단 주제로 정의"가 그림 왼쪽 경계 밖으로 잘렸다.
두 줄로 나눠 다시 뽑아 잘림이 사라진 것을 눈으로 확인했다. 두 그림 모두 tofu와 글씨 겹침은 없다.

## 미확인 사항

- [unverified] 제출 PDF와 README에 넣었을 때의 인쇄 품질. 300dpi로 뽑았으나 실제 배치 후
  축소 배율은 아직 정하지 않았다.
- [unverified] 그림 1의 흐름이 최종 데모 실행 경로와 끝까지 일치하는지. 워크플로 YAML과
  정책 파일 기준으로 그렸고, 키가 없어 전체 E2E를 돌려 대조하지는 못했다.
- `docs/figures/fonts/`가 약 10MB이고 현재 `.gitignore`에 걸리지 않는다. 저장소에 폰트를
  넣을지, 무시 목록에 넣고 이 문서의 설치 절차로 대신할지는 오케스트레이터가 정한다.
