# PharmaSignal 도메인 도구 3종 메모

작성 2026-09-24. 담당 경로: `src/harness/tools/pharmasignal_*.py`, `tests/test_pharmasignal_*.py`,
`eval/results/pharmasignal_*.json`. LLM을 부르지 않는 순수 파이썬(표준 라이브러리 urllib, json, xml.etree)이다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `src/harness/tools/pharmasignal_common.py` | HTTP GET(재시도, 429 대기), 파일 캐시(`ResponseCache`), 해시, UTC 타임스탬프 |
| `src/harness/tools/pharmasignal_openfda.py` | `faers_disproportionality(drug, reaction, name_field="generic")`: FAERS 2x2표, PRR, ROR, 카이제곱(Pearson과 Yates 보정), Evans와 ROR 두 계열 판정. `disproportionality(a,b,c,d)`는 순수 산술 |
| `src/harness/tools/pharmasignal_ror.py` | ROR 오라클 `ror_2x2(a,b,c,d)`: ROR, 95% CI, Haldane 0.5 보정, "CI 하한 > 1이면 신호 후보" 판정 |
| `src/harness/tools/pharmasignal_verify.py` | 불일치율과 검증 커버리지 지표, 원장 덧붙이기 |
| `src/harness/tools/pharmasignal_dailymed.py` | `search_setids(drug_name)`, `fetch_label_sections(setid)`, `find_label_mentions(drug_name, reaction)` |
| `src/harness/tools/pharmasignal_pubmed.py` | `search_pubmed(drug, reaction, retmax=10)`: esearch 후 efetch XML 파싱 |
| `src/harness/tools/pharmasignal_cases.py` | 세 도구를 한 조합에 대해 실행하는 `run_case`, 데모 3건을 저장하는 `run_cases` |
| `tests/test_pharmasignal_{openfda,dailymed,pubmed}.py` | 오프라인 단위 테스트 13개, `@pytest.mark.network` 라이브 테스트 3개 |
| `eval/results/pharmasignal_cases.json` | 데모 3건 실행 결과(커밋 안 함, `.gitignore`의 `eval/results/*.json`에 해당) |
| `eval/results/pharmasignal_cache_<source>_<hash>.json` | API 원응답 캐시. `<source>`는 openfda, dailymed, pubmed |

모든 반환값은 JSON 직렬화 가능한 dict이고 `evidence_ids`를 포함한다. FAERS는 카운트 쿼리 URL 4개,
DailyMed는 setid, PubMed는 PMID를 넣어 크리틱이 근거를 따라갈 수 있게 했다. 인자는 문자열과 정수만
받으므로 NAT 함수 도구로 그대로 등록할 수 있다.

## API별 확인 사항

### openFDA drug/event
- 엔드포인트 `https://api.fda.gov/drug/event.json`. 공식 문법 페이지(open.fda.gov/apis/query-syntax)에서
  `search=field:"term"`, 결합 `+AND+`, `count=field`, `.exact` 접미를 확인했다. 필드 정의는
  `https://open.fda.gov/fields/drugevent.yaml`에서 읽었다. `reactionmeddrapt`, `medicinalproduct`,
  `openfda.generic_name`, `openfda.brand_name` 모두 `is_exact: true`이고, MedDRA 용어는 영국식 철자
  (예: `DIARRHOEA`)라는 주석이 있다.
- 사용 필드: 반응은 `patient.reaction.reactionmeddrapt.exact`에 대문자 PT를 넣어 구 전체 일치로 검색한다.
  약물은 기본 `patient.drug.openfda.generic_name`을 토큰 일치로 검색한다. 실측으로 `generic_name.exact:"METFORMIN"`은
  17,143건, 토큰 일치 `generic_name:"metformin"`은 19,411건(metformin과 lactic acidosis 동반)이었다.
  복합제와 염 표기("METFORMIN HYDROCHLORIDE")를 포함하려면 토큰 일치가 맞다. `name_field="brand"`,
  `"medicinalproduct"`로 바꿀 수 있다.
- 2x2표는 `limit=1` 조회 4개의 `meta.results.total`로 만든다(전체 N, 약물 n, 반응 n, 약물 AND 반응 a).
  b, c, d는 뺄셈으로 얻는다. 결과가 없으면 HTTP 404에 `{"error":{"code":"NOT_FOUND"}}`가 오고 이를 0건으로 읽는다.
- 제한: 공식 인증 페이지(open.fda.gov/apis/authentication)에는 **키 없이 분당 240회, 일 1,000회(IP당)**,
  키 있으면 분당 240회, 일 120,000회로 적혀 있다. 과제 지시문의 "분당 40회"는 문서와 다르다. 일 1,000회
  제약이 더 빡빡하므로 (약물, 반응, 필드) 쌍별로 원응답을 캐시하고 재실행 때 재사용한다. 캐시에는 `meta`만 남겨
  파일이 약 2.6KB다. 응답 헤더에 rate-limit 정보는 없었다.
- 지표: PRR = (a/(a+b)) / (c/(c+d)), ROR = ad/bc, 95% CI는 로그 스케일 정규근사.
  데이터 갱신일은 응답 `meta.last_updated`(2026-07-30)를 `data_last_updated`로 넘긴다.
- 카이제곱은 두 가지를 함께 낸다. `chi2`는 연속성 보정 없는 Pearson이고, `chi2_yates`는 Yates 연속성 보정을
  한 값이다. 보정은 |ad-bc|에서 N/2를 빼고 음수면 0으로 막는 방식이라 카이제곱이 늘 작아지고, 그만큼 판정이
  엄해진다. **[2026-09-25 정정] `evans_signal`은 이제 `chi2_yates`로 판정한다.** Evans, Waller, Davis(2001)가
  제시한 관례가 a≥3, PRR≥2, **Yates 보정** χ²≥4이기 때문이다. 그 전에는 보정 없는 Pearson을 써서 원 논문보다
  느슨했다. `chi2`는 기존 결과 파일과 이어 읽으라고 그대로 남겼다.
- ROR 계열 판정은 `ror_signal`이다. 기준은 a≥3이고 ROR 95% CI 하한이 1을 넘는 것이며, 계산은
  `src/harness/tools/pharmasignal_ror.py`의 `ror_2x2()`가 맡는다. PRR 계열(Evans)과 ROR 계열은 서로 다른
  관례라 둘을 함께 내놓고 어긋나는 자리를 사람이 보게 했다.
- 0 셀 처리. 네 칸 중 하나라도 0이면 비가 정의되지 않으므로 네 칸에 0.5를 더한다(Haldane-Anscombe 보정).
  보정한 값은 `ror_haldane`와 `ror_ci95_haldane`로 따로 내고, 보정을 적용했는지는 `haldane_applied`로 드러낸다.
  `ror`과 `ror_ci95`는 보정하지 않은 값(0 셀이면 None)으로 그대로 둬서 보정값과 섞여 읽히지 않게 했다.
  b=0(이 약물의 보고가 전부 이 반응)이나 c=0(다른 약물에서는 한 건도 없음)은 신호가 가장 강한 자리라
  통째로 떨어뜨리지 않는다.

### DailyMed REST v2
- 기본 URI `https://dailymed.nlm.nih.gov/dailymed/services/v2`. `/spls.json?drug_name=<이름>&name_type=<generic|brand|both>&pagesize=<=100&page=N`
  으로 setid 목록을 받고, `/spls/<SETID>.xml`로 HL7 SPL XML을 받는다. 공식 파라미터 목록은
  `/dailymed/webservices-help/v2/spls_api.cfm`에서 확인했다(pagesize 기본 100, 최대 100).
- 섹션 분리는 `<section><code code="LOINC">`로 한다. metformin 라벨(setid 1200ea71-8a9e-4e49-bb77-7d9fe0d84ae7) 실측 코드:
  34066-1 Boxed Warning, 34070-3 Contraindications, 43685-7 Warnings and Precautions, 34084-4 Adverse Reactions.
  구형 라벨용 34071-1 Warnings, 42232-9 Precautions도 매핑에 넣었다(이번 케이스에서는 등장하지 않아 실측은 아님).
  하위 절(예: 5.1 Lactic Acidosis)은 상위 섹션 텍스트에 함께 들어간다.
- `find_label_mentions`는 검색 결과 상위 `max_labels`개(기본 1)만 읽는다. 첫 결과가 재포장업체나 복합제
  라벨일 수 있다. amoxicillin 케이스에서는 "AMOXICILLIN AND CLAVULANATE" 라벨이 잡혔다. 특정 라벨을 보려면
  `setids=[...]`를 넘긴다. 반응명 매칭은 대소문자 무시 부분 문자열이며, 라벨을 하나도 못 받으면 `labeled=None`으로
  "근거 없음"과 구분한다.
- 문서에 호출 제한 수치는 없었다. 라벨 XML은 190~410KB라 setid별로 캐시한다.

### PubMed E-utilities
- `esearch.fcgi?db=pubmed&retmode=json&retmax=N&sort=relevance&term=<약물> AND "<반응>"` 후
  `efetch.fcgi?db=pubmed&retmode=xml&rettype=abstract&id=<PMID,...>`. XML에서 ArticleTitle, Journal/Title,
  PubDate/Year(없으면 MedlineDate의 연도), AbstractText를 읽고 초록은 앞 300자만 남긴다.
  참고 구현 `autobiox/BioProject02/agents/critic/scripts/verify_citations.py`의 esearch 후 efetch 흐름을 따랐다.
- 호출 간 최소 0.34초를 보장해 초당 3회 제한을 지킨다. `NCBI_API_KEY`, `NCBI_EMAIL` 환경변수가 있으면
  `api_key`, `email`을 붙이고 `tool=pharmasignal`은 항상 붙인다.
- [unverified] NCBI 이용 지침 페이지(NBK25497, NBK25499)는 이번 세션에서 reCAPTCHA로 막혀 "키 없이 초당 3회"
  문구를 원문으로 재확인하지 못했다. 코드의 간격 제한은 그 관례를 따른다.

## 실행 결과 (`eval/results/pharmasignal_cases.json`, `generated_at` 2026-09-24T15:35:03+00:00 재실행)

FAERS 전체 보고 건수 N = 20,692,690 (`meta.last_updated` 2026-07-30).
재실행은 캐시만 읽었다. openFDA 쿼리 12건이 모두 캐시 적중(`hits` 4씩, `misses` 0)이고 소켓 연결을 막고
돌려도 세 케이스가 `errors: []`로 끝났다.

| 케이스 | a / b / c / d | PRR (95% CI) | ROR (95% CI) | χ² Pearson | χ² Yates | Evans | ROR 판정 | 라벨 등장 섹션 | PubMed 건수(반환) |
|---|---|---|---|---|---|---|---|---|---|
| (a) metformin + Lactic acidosis | 19,411 / 420,859 / 12,260 / 20,240,160 | 72.83 (71.22~74.48) | 76.14 (74.43~77.90) | 533,148.68 | 533,120.23 | 시그널 | 시그널 | boxed_warning, warnings_and_precautions, adverse_reactions | 1,139 (10) |
| (b) semaglutide + Pancreatitis | 1,302 / 71,699 / 50,919 / 20,568,770 | 7.22 (6.84~7.63) | 7.34 (6.94~7.75) | 6,823.09 | 6,816.99 | 시그널 | 시그널 | warnings_and_precautions, adverse_reactions | 119 (10) |
| (c) amoxicillin + Retinal detachment | 39 / 101,509 / 9,039 / 20,582,103 | 0.87 (0.64~1.20) | 0.87 (0.64~1.20) | 0.6951 | 0.5755 | 아님 | 아님 | 없음(labeled=false) | 8 (8) |

Yates 보정으로 카이제곱이 세 케이스 모두 작아졌으나 판정은 하나도 뒤집히지 않았다. (c)가 기준선에 가장
가깝지만 0.5755도 4에 한참 못 미치고, PRR 0.87이 이미 2를 밑돌아 `evans_signal`은 어느 쪽 카이제곱으로도
거짓이다. ROR 계열 판정(`ror_signal`)은 세 건 모두 Evans 계열과 같았고, 0 셀이 없어
`haldane_applied`는 세 건 다 거짓이다.

- (a) 라벨 setid 014f2a32-8440-4d0c-8f5d-c4b3a49e0dec(METFORMIN HYDROCHLORIDE ER, 검색 559건 중 첫 결과).
  박스 경고 "WARNING: LACTIC ACIDOSIS"에서 매칭 7건. PubMed 상위: 26773926, 34244196, 31372935.
- (b) 라벨 setid 27f15fac-7d98-4114-a2ec-92494a91da98(RYBELSUS/OZEMPIC 정제, 검색 9건 중 첫 결과).
  "Acute Pancreatitis" 경고 등 매칭 6건. PubMed 상위: 38774967, 40196933, 36578889.
- (c) 라벨 setid 5200ae31-8a79-45f9-84fc-98f8448483a7(AMOXICILLIN AND CLAVULANATE, 검색 634건 중 첫 결과).
  네 섹션 모두 "retinal detachment" 없음. PubMed 8건은 대부분 플루오로퀴놀론 비교 연구여서 amoxicillin이
  대조군으로 등장하는 문헌이다. 케이스 (c)는 "FAERS 소수, 불균형 없음, 라벨 미기재, 문헌 희박"의 근거 부족 예시로 쓸 수 있다.
- 세 케이스 모두 `errors: []`. 오류나 429는 한 번도 나지 않았다.

## 테스트

```
.venv/bin/pytest tests/test_pharmasignal_*.py -m "not network"   # 13 passed, 3 deselected (0.1초)
.venv/bin/pytest tests/test_pharmasignal_*.py -m network          # 3 passed (12초, 라이브)
.venv/bin/python src/harness/tools/pharmasignal_cases.py          # 데모 3건 실행, JSON 저장
.venv/bin/python -m pytest -q -m "not network"                    # 저장소 전체 128 passed, 3 deselected
```

ROR 오라클(`pharmasignal_ror.py`)과 대조 검증(`pharmasignal_verify.py`)은 `tests/test_signal_oracle.py`
32개가 맡는다(2026-09-25 실측). 저장소 전체 오프라인 테스트는 128개다.

PRR 단위 테스트: a=40, b=960, c=200, d=98800 → PRR 19.8 통과. `network` 마커는 pytest 설정에 등록되어
있지 않아 `PytestUnknownMarkWarning`이 뜬다. 오케스트레이터가 `pyproject.toml` 또는 `pytest.ini`에
`markers = network: 외부 API 호출` 을 추가하면 사라진다.

## 추가 패키지

- `pytest 9.1.1` (`.venv/bin/pip install pytest`, `pytest-cov 7.1.0`이 함께 설치됨). `requirements.txt`는 건드리지 않았다.
- 도구 본체는 표준 라이브러리만 쓴다. `httpx`는 이미 `.venv`에 있지만 사용하지 않았다.

## 남은 일과 한계

- 라벨 선택 규칙이 "검색 첫 결과"라 재포장업체나 복합제가 잡힐 수 있다. 원개발사 라벨을 우선하는 규칙
  (제목에 " AND "가 없는 것, 또는 `labeler` 파라미터)을 붙이면 좋다.
- 반응명 매칭은 단순 부분 문자열이다. 동의어(예: MedDRA LLT, 영국식 철자)는 아직 다루지 않는다.
- FAERS 2x2표는 보고 건수 기준이며, 한 보고에 여러 약물·반응이 있어 셀이 중복 계산된다. 통상의 FAERS 불균형
  분석도 같은 전제라 그대로 두었다.
- [unverified] E-utilities 이용 지침 원문 재확인(위 참조).
