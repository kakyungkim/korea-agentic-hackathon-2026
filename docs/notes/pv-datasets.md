# 약물감시 공개 데이터셋 조사

조사일 2026-09-26. 조사자 researcher 서브에이전트. 이 문서는 조사 기록이며 결정 문서가 아니다.

## 조사 질문

접근 가능한 공개 약물감시 데이터셋에는 무엇이 있고, 그 안의 주장을 사람이 처리할 때 드는
시간과 비용을 출처 있는 수치로 잡을 수 있는가. 잡을 수 있다면 우리 크리틱 실측치와 어떤
비교가 정직하게 성립하는가.

## 요약

**확인한 것.** 지금 바로 받을 수 있는 대량 데이터는 openFDA FAERS, FAERS 분기 전체 파일,
DailyMed SPL, SIDER 4.1, OFFSIDES와 TWOSIDES, OnSIDES, VAERS, Canada Vigilance 추출물,
일본 JADER, ClinicalTrials.gov 열 가지다. 응답 코드와 규모를 직접 확인했다.

**신청이나 유료 계약이 필요한 것.** WHO VigiBase는 회원국 무료, 연구기관과 대학은 유료다.
EMA EudraVigilance 상세 데이터는 EMA에 요청해야 하고 2025년 한 해 승인 건이 25건에 그쳤다.
한국 KAERS 원시자료는 월 단위 일괄 심의에 최대 30일이 걸리고 공표 전 사전 통지 의무가 붙는다.
MedDRA는 구독이 필요하되 비영리와 비상업은 무료다. 셋 다 해커톤 일정 안에 붙일 수 없다.

**찾지 못한 것.** ICSR 한 건을 처음부터 끝까지 처리하는 데 드는 시간을 잰 동료심사 수치와
건당 인건비를 찾지 못했다. "한 건에 한두 시간", "외주 단가 200달러에서 600달러"라는 말은
벤더 블로그와 시장조사 보고서에만 있었고 측정 방법이 적혀 있지 않았다. 대신 쓸 수 있는
동료심사 수치로는 신호 평가 안에서 ICSR 내러티브를 검토한 시간 하나만 남았다(Warner 등 2026,
건당 5.56분). 이 수치는 전체 케이스 처리 시간이 아니다.

**결론 성격의 제안.** 팀원이 말한 "그 안의 주장들을 기존 방식으로 처리할 때"를 사람의 케이스
처리 시간으로 잡으면 비교가 서지 않는다. 우리가 이미 잰 고정 규칙 1/16 대 모델 포함 16/16이
같은 입력과 같은 라벨을 쓰는 유일한 실측 비교다. 이것을 주 비교로 두고, 사람과의 시간 비교는
같은 33건에 전문가를 붙여 새로 재는 것만 인정하는 편이 낫다.

## 데이터셋 목록

규모와 날짜는 조사 당일(2026-09-26)에 직접 조회한 값이다. 본문은 받지 않고 응답 코드와
메타데이터만 확인했다. 빈 곳은 확인 못 함으로 남겼다.

### 지금 바로 받을 수 있는 것

| 이름과 제공 기관 | 규모 | 접근 방법 | 라이선스와 제약 | 실제 확인 결과 |
|---|---|---|---|---|
| openFDA FAERS (미국 FDA) | 레코드 20,692,690건, last_updated 2026-07-30 | REST API. 키 없이 분당 240회, 일 1,000회. 키 발급 시 분당 240회, 일 120,000회 | CC0 1.0 공개도메인. 상업 이용과 재배포 가능. 인과관계 단정 금지 고지 | `api.fda.gov/drug/event.json?limit=1` HEAD 200, meta.results.total로 건수 확인 |
| FAERS 분기 전체 파일 (미국 FDA, fis.fda.gov) | 2004년부터 2026년 2분기. 분기당 ASCII 8MB에서 70MB, XML 9MB에서 144MB. 누적본 아님 | 전체 다운로드(zip). 관계형 DB 구축 전제. 요약 자료는 FOIA 요청 안내 | 확인 못 함. FDA 원자료라는 표기만 확인 | `faers_ascii_2025q1.zip` GET 200, 17,640,928바이트 수신 후 본문 폐기 |
| DailyMed SPL (미국 NLM) | API 기준 라벨 159,383건, db_published_date 2026-09-24. 전체 다운로드는 처방 54,939파일 16.71GB, OTC 68,509파일 32.77GB, 동종요법 16,058파일 5.53GB, 동물 3,613파일 1.18GB, 잔여 2,528파일 636.86MB | REST API v2와 전체 zip. 월간, 주간, 일간 증분 제공 | 확인 못 함. 페이지에 이용조건 문구가 없었다 | `services/v2/spls.json?pagesize=1` HEAD 200, metadata.total_elements 확인. 전체 다운로드 페이지 GET 200 |
| SIDER 4.1 (EMBL) | 약물 1,430종, 부작용 5,868종, 약물과 부작용 쌍 139,756건. 그중 39.9%에 빈도 정보. MedDRA 16.1 사용. 릴리스 2015-10-21 | 전체 파일 직접 다운로드. `meddra_all_se.tsv.gz` 2.3MB 등 | CC BY-SA 4.0. 교육과 연구 목적 고지 | `/download/` GET 200으로 통계와 파일 목록 확인, `meddra_all_se.tsv.gz` HEAD 200. 홈페이지에 "데이터가 2015년이라 낡았다"는 자체 경고와 EBI 후속 데이터베이스 착수 예정 공지 |
| OFFSIDES, TWOSIDES (Tatonetti Lab, nsides.io) | 약물 3,300종 이상, 조합 63,000건. 파일명 기준 2019-11-13 | S3 직접 다운로드 | 확인 못 함. 라이선스 표기를 찾지 못했다 | `OFFSIDES.csv.gz` GET 200, 68,762,346바이트. `TWOSIDES.csv.gz` GET 200, 223,164,756바이트. 둘 다 본문 폐기. 예전 경로 `tatonettilab.org/resources/nsides/OFFSIDES.csv.gz`는 404 |
| OnSIDES (Tatonetti Lab) | DailyMed 라벨 46,686건에서 추출. 성분 2,793종, 약물과 이상반응 쌍 360만건 초과. 2023년 11월 DailyMed 기준 | CSV 플랫파일과 SQL 스키마. GitHub 릴리스 | 확인 못 함 | nsides.io GET 200으로 수치와 성능 확인. ADVERSE REACTIONS 절 추출 F1 0.90, BOXED WARNINGS F1 0.71, TAC 2017 기준 Micro-F1 0.87. 실제 CSV URL은 확인 못 함 |
| VAERS (미국 CDC와 FDA) | 1990년부터 2026년까지 연도별. 국외 보고는 별도 분류. 총 건수는 확인 못 함 | 연도별 CSV 세 종류(VAERSDATA, VAERSVAX, VAERSSYMPTOMS) 다운로드 | Data Use Guide 열람을 요구. 2025년 5월부터 추가된 2차 보고는 신규 이상사례가 아니라는 고지 | `vaers.hhs.gov/data/datasets.html` GET 200 |
| Canada Vigilance 추출물 (Health Canada) | 1965년부터 2026-05-31까지. ZIP 341MB. 월간 갱신. 보고 건수는 페이지에 없었다 | 전체 다운로드(`extract_extrait.zip`). 사용자가 직접 DB에 적재하는 전제 | 확인 못 함 | 데이터 추출 안내 페이지 GET 200. open.canada.ca의 데이터셋 페이지는 404 |
| JADER (일본 PMDA) | 기업과 의료기관 보고는 2004년도 이후, 예방접종 관련은 2013년도 이후. 공개 4개월 전까지 접수분 포함. 총 건수는 확인 못 함 | 전체 CSV 네 표(demo, drug, reac, hist). 매 공개 때 전체 갱신 | 인과관계 미평가, 중복 가능, 단순 안전성 비교 불가 고지. 재배포 조항은 확인 못 함 | 안내 페이지 GET 200. CSV 직접 URL은 확인 못 함. 시험한 예시 URL 하나는 404 |
| ClinicalTrials.gov (미국 NLM) | 등록 연구 604,566건, 2026-09-26 조회 | 공개 REST API v2와 대량 다운로드 | 확인 못 함. 이용조건 페이지가 애플리케이션 응답으로 와서 본문을 읽지 못했다 | `api/v2/studies?pageSize=1&countTotal=true` 200, totalCount 확인 |

### 신청이나 계약이 필요한 것

| 이름과 제공 기관 | 규모 | 접근 방법 | 라이선스와 제약 | 실제 확인 결과 |
|---|---|---|---|---|
| VigiBase (WHO, Uppsala Monitoring Centre) | 보고 40,000,000건 초과, WHO PIDM 회원 180곳 이상. 2025년 2월 기준 | 회원 기관은 무료. 그 밖은 유료. 검색 서비스, 승인된 소프트웨어 제공사를 통한 케이스 단위 추출본, VigiAccess 웹 조회와 API | 회원 무료, 허가권자와 소프트웨어 제공사, 연구기관, 대학은 유료. 데이터 릴리스에 한계를 적은 caveat 문서가 따라붙는다. 재배포 조항은 확인 못 함 | `who-umc.org/vigibase/` HEAD 405, GET 200으로 규모 확인. 데이터 접근 페이지에서 유료 문구 확인. VigiAccess는 HEAD 404, GET 200이나 본문이 757바이트 자바스크립트 애플리케이션이어서 실제 데이터 응답은 확인 못 함 |
| EudraVigilance와 adrreports.eu (EMA) | ICSR 31.2백만건, 케이스 약 17.9백만건(2025년 말). 2025년 허가 후 신규 ICSR 약 1.8백만건으로 2024년 대비 0.5% 증가 | 공개분은 adrreports.eu 웹 조회. 라인 리스팅과 ICSR 양식 제공. 대량 다운로드나 공개 API는 확인 못 함. 상세 검색은 EMA에 개별 요청 | 접근정책 5판(2025-04-16). 학계 접근에 Annex D 개인정보와 기밀 서약 필요. 2025년 데이터 요청 25건에 응답했고 그중 학계가 8건 | adrreports.eu HEAD 200. EMA 2025년 연차보고서 PDF 원문에서 수치 확인 |
| KAERS와 의약품안전나라 (한국 식약처, 한국의약품안전관리원) | 이상사례 보고 2025년 277,279건, 2024년 253,486건, 2023년 268,148건, 2022년 315,867건 | 집계 통계는 공공데이터포털 CSV로 로그인 없이 다운로드. 원시자료는 신청 후 심의 | 매월 접수분을 익월 초 일괄 심의하고 신청일로부터 30일 내 통보. 대상은 대학과 연구기관, 의료기관, 정부와 공공기관, 제조수입사. 공표 7일 전 사전 통지 의무. 결과 등록 의무는 논문 게재 후 90일, 학회 발표 후 30일. 재배포 조항은 확인 못 함 | 원시자료 이용안내 페이지 GET 200으로 절차 확인. 공공데이터포털 파일데이터 페이지 GET 200. 연도별 건수는 "2025년 의약품등 안전성정보 보고동향"을 인용한 약사공론 보도에서 확인했고 원문 게시물 본문은 확인 못 함 |
| MedDRA (ICH MSSO, 일본은 JMO) | 용어 표준. 연 2회 갱신 | 구독 신청. 네 유형은 규제기관, 비영리와 비상업, 상업, 시스템 개발자 | 규제기관과 비영리 및 비상업은 무료. 상업은 연매출 연동 슬라이딩, 시스템 개발자는 정액. 기업은 전사 한 건으로 충분. 재배포 조항 원문은 확인 못 함 | meddra.org GET 200이나 본문이 자바스크립트라 텍스트 추출 실패. ICH MedDRA 팩트시트 PDF(2026년 7월 8일판) 원문에서 구독 유형과 무료 대상 확인 |

## 기존 방식 수치

출처 있는 시간 수치는 하나 찾았다. Warner 등 2026(Clin Pharmacol Ther, DOI 10.1002/cpt.70409,
PMID 42522449)은 Eli Lilly의 후향적 실현가능성 연구로, 과거 신호 평가 다섯 건에 쓰인 ICSR
1,115건(주제당 69건에서 697건)을 대상으로 GPT-4o 기반 플랫폼과 사람 검토를 견줬다. 이 가운데
Product C 발성장애 주제의 ICSR 69건에서 사람의 수동 검토가 395분, 건당 약 5.56분이었고,
플랫폼을 붙였을 때 145분, 건당 약 2.05분으로 약 63.1% 줄었다. **이 5.56분은 ICSR 한 건의 전체
처리 시간이 아니다.** 이미 접수되어 데이터베이스에 들어간 내러티브에서 위험인자와
dechallenge 및 rechallenge 반응 같은 특정 요소를 뽑아 읽는 시간만 잰 값이고, 접수와 중복 확인,
MedDRA 코딩, 내러티브 작성, 의사의 인과성 검토, 규제기관 제출은 빠져 있다. 추출 성능도 주제에
따라 위험인자 F1 0.444에서 1.000, dechallenge와 rechallenge 반응 F1 0.429에서 0.909로 넓게
흩어졌고, 저자들이 직접 "방법론적 약점 때문에 시간 절감 수치는 예비적이고 탐색적으로만 보아야
한다"고 적었다. 따라서 이 값은 상한도 하한도 아닌 단일 사례의 참고치로만 쓸 수 있다.

벤더 자료에 흔한 "케이스 한 건에 한두 시간", "외주 단가 건당 200달러에서 600달러" 같은 수치는
측정 방법과 표본이 적혀 있지 않고 판매 목적 문서에만 나와 이 문서에서 뺐다.

## 인용 확인

Warner 등 2026 은 PubMed E-utilities 로 직접 대조했다(2026-09-26). 제목
"Intelligent Automation Improved Efficiency in Pharmacovigilance Safety Signal Assessment",
Clinical Pharmacology and Therapeutics, 2026-07-29, DOI 10.1002/cpt.70409, PMID 42522449.
제목과 저널과 저자와 DOI 가 모두 맞았다. 다만 본문 전문을 열어 5.56분이라는 수치를
직접 확인하지는 못했다.

## 출처

실제로 열어 응답을 받은 URL만 적는다. PubMed 문헌은 E-utilities efetch로 초록 원문을 받아 읽었다.

- https://api.fda.gov/drug/event.json?limit=1
- https://api.fda.gov/drug/label.json?limit=1
- https://open.fda.gov/apis/drug/event/
- https://open.fda.gov/apis/authentication/
- https://open.fda.gov/license/
- https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html
- https://fis.fda.gov/content/Exports/faers_ascii_2025q1.zip
- https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?pagesize=1
- https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm
- https://sideeffects.embl.de/
- https://sideeffects.embl.de/download/
- https://sideeffects.embl.de/media/download/meddra_all_se.tsv.gz
- https://nsides.io/
- https://tatonettilab.org/offsides/
- https://tatonettilab-resources.s3.us-west-1.amazonaws.com/nsides/OFFSIDES.csv.gz
- https://tatonettilab-resources.s3.us-west-1.amazonaws.com/nsides/TWOSIDES.csv.gz
- https://vaers.hhs.gov/data/datasets.html
- https://www.canada.ca/en/health-canada/services/drugs-health-products/medeffect-canada/adverse-reaction-database/canada-vigilance-online-database-data-extract.html
- https://www.pmda.go.jp/safety/info-services/drugs/adr-info/suspected-adr/0004.html
- https://clinicaltrials.gov/api/v2/studies?pageSize=1&countTotal=true
- https://who-umc.org/vigibase/
- https://who-umc.org/vigibase-data-access/
- https://www.vigiaccess.org/
- https://www.adrreports.eu/en/index.html
- https://www.ema.europa.eu/en/documents/report/2025-annual-report-eudravigilance-european-parliament-council-commission_en.pdf
- https://www.meddra.org/
- https://files.meddra.org/www/Website%20Files/Fact%20Sheets/meddra_factsheet1_accessing_meddra-8%20July%202026-A4.pdf
- https://open.drugsafe.or.kr/original/invitation.jsp
- https://www.data.go.kr/data/15117015/fileData.do
- https://nedrug.mfds.go.kr/bbs/2
- https://www.kpanews.co.kr/news/articleView.html?idxno=530630
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13416901/ (Warner 등 2026, Clin Pharmacol Ther, DOI 10.1002/cpt.70409)
- https://pubmed.ncbi.nlm.nih.gov/42522449/

응답을 받지 못한 URL도 적어 둔다. Wiley의 Schmider 등 2019 PDF는 403, open.canada.ca 데이터셋
페이지와 PMDA 예시 CSV와 예전 OFFSIDES 경로는 404, meddra.org 본문은 텍스트 추출 실패였다.
