# 주제 결정: 후보 정리와 권고

2026-09-25 작성. 마감 2026-09-28(월) 23:59, 목표 제출 9/28 18:00. 남은 시간 3일.

`docs/notes/team.md:21`에서 팀장이 별도 세션에서 초파리와 Jev 두 주제의 계획을 먼저 짜기로 했다.
이 문서가 그 산출물이고, 다섯 명 의견을 모으는 자리에 가져갈 판단 재료다.

실측 근거는 두 문서에 나눠 적었다. NVIDIA 생물학 NIM 쪽은 `docs/notes/bionemo-nim.md`,
팀원 제안 주제 쪽은 `docs/notes/fddd-and-jev.md`다.

## 결론 먼저

**권고는 이어 붙이기다.** 초파리 도킹을 앞단에, 약물감시 도구 3종을 뒷단에 두어 **하나의
파이프라인**으로 만들고, 각 단계에서 나올 수 없는 주장을 크리틱이 반려한다. 초파리는 훅과
세 번째 포즈 탐색 경로로 쓰고 결과의 권위로 세우지 않는다.

전제가 하나 있다. 생물학 NIM 권한 확인(아래 G1)이 9/25 밤에 통과해야 한다. 막히면 PharmaSignal
단독으로 되돌린다.

## Night Shift를 후보에서 뺀 경위

`docs/PLAN.md:49-59`의 후보 2였다. 밤새 저장소에서 스스로 실험하고 아침에 증거를 붙인 PR 후보를
올리는 자율 코딩 에이전트다. **개발자 도메인을 겨냥한 후보였고 개발자 커뮤니티 섭외용이었다**
(`docs/PLAN.md:10`, `docs/notes/recruiting.md:28-31`).

팀이 확정되면서 전제가 사라졌다. 확정 3명이 전부 바이오와 제약 쪽이다. 혈액 내 암세포 데이터
분석, 면역학 박사이자 AI 신약개발 저자, 약사이자 AI 프로덕트 개발자다. 팀원 두 분이 밝힌 관심도
약물감시와 신약개발이고 자율 코딩은 아무도 꼽지 않았다. 개발자 섭외 훅이 필요해서 준비한
후보인데 정작 모인 팀이 그 훅의 대상이 아니다.

그래서 **2026-09-25에 후보에서 뺀다.** 남은 선택은 PharmaSignal과 초파리 둘이고 Jev는 독립
주제가 아니라 어느 쪽에든 얹는 부품이다.

버리는 것은 아니다. 구성요소가 실제로 동작하므로 자산으로 남긴다.

- 실행기, 규칙 크리틱 9종, 아침 보고서가 동작한다. boltons 저장소 실험 3건을 65.4초에 돌려
  정직한 패치 1건 통과, 테스트 삭제와 skip 마커 패치 2건 반려를 확인했다
- **부정 패치 둘 다 pytest는 rc=0으로 통과했고 규칙 크리틱만 잡았다.** 이 대비가 구성요소의
  존재 이유이고, 발표에서 "샌드박스는 호스트를 지키지 결과의 정확성을 지키지 않는다"는 논거의
  실례로 쓸 수 있다
- `policies/nightshift.yaml`은 OpenShell에 실제로 적용해 github.com 차단과 `run_as_user=1500`
  적용까지 확인했다. 정책 작성 지식이 그대로 남는다
- 다만 NAT 워크플로가 없다. 계획자와 작업자가 미구현이라 주제로 되살리려면 배선이 새 작업이다

다음 해커톤이나 개발자 대상 자리에 쓴다. 자세한 것은 `docs/notes/nightshift-components.md`에 있다.

## 먼저 알아야 할 사실: 하네스에 도메인 도구가 등록돼 있지 않다

주제를 정하기 전에 확인할 것이다. `docs/HANDOFF.md`와 `README.md`가 "도구 3종이 동작한다"고
적고 있으나 그 도구는 **NAT에 등록되어 있지 않다.** 2026-09-25에 직접 확인했다.

```
$ grep -rn "register_function" src/harness/tools/ | wc -l
0
```

- NAT에 실린 것은 `echo_tool`, `prr_calculator`, `critic_judge`, 평가기 `critic_verdict` 넷뿐이다
- `src/harness/register.py:152-156`의 도메인 도구 import 네 줄이 **전부 주석**이다
- `configs/author.yml`의 `functions`가 `echo_tool`과 `prr_calculator` 둘이고
  `tool_names: [echo_tool, prr_calculator]`다
- FAERS, DailyMed, PubMed 도구는 `pharmasignal_cases.py`라는 별도 CLI로만 돌고 에이전트 루프
  밖에 있다

**심사 첫 항목이 "NVIDIA Agent 기술 활용 심도"인데 에이전트가 도메인 도구를 부르는 장면이 없다.**
지금 상태로 데모를 보이면 작성자 에이전트가 부를 수 있는 도구는 에코와 PRR 계산기다.

이것이 PharmaSignal의 가장 큰 구멍이고 **어느 주제로 가든 맨 먼저 메운다.** 기존 도구는 코드가
이미 동작하므로 `@register_function` 래퍼를 얇게 씌우는 일이다. 참조 구현은
`src/harness/register.py:126-147` 하나뿐이고 절차는 `docs/notes/nat-harness.md:244-253`에 있다.

## 두 후보 비교

### 채점 항목 (공고 문구 그대로)

> [온라인 사전 챌린지] 프로젝트 채점 항목
> - NVIDIA Agent 기술 활용 심도
> - 실용성, 산업가치, 혁신성
> - 완성도
> - 기타 - 커스터마이징 수준, 독창성 등

**배점은 공개되지 않았다.** `docs/PLAN.md:7`에 적힌 요약보다 이 원문이 정확하다.

네 번째 항목의 성격을 눈여겨본다. **"기타" 로 열려 있고 "등" 으로 끝난다.** 커스터마이징과
독창성이 예시일 뿐 목록이 닫히지 않았다는 뜻이다. 그러면 다음도 여기서 점수를 받을 수 있다.

- 문서의 질과 재현 절차. 우리는 실행 명령과 결과 파일 경로를 전부 적어 두었다
- 정직한 한계 기술. 시연하지 못한 것을 시연한 것처럼 쓰지 않는 규율이 자산이 된다
- 하네스 자체. 도메인을 갈아 끼우는 구조와 작성자와 크리틱 분리
- 영상과 발표의 완성도
- 팀 구성의 다학제성. 면역학 박사, 약사, 데이터 분석, 개발이 모여 있다

**즉 우리가 공들인 증거 규율이 버려지는 항목이 아니다.** 1번과 3번뿐 아니라 4번에서도 값을 한다.

| 항목 | PharmaSignal 단독 | 초파리 단독 | 이어 붙이기 |
|---|---|---|---|
| NVIDIA 심도 | 약함. Nemotron, NAT, OpenShell 셋 | 강함. DiffDock, Boltz-2, GenMol, MSA-Search 더함 | 강함. 일곱 장 |
| 실용성 | 강함. 현업 문제이고 팀장 도메인 | 약함. 커넥톰은 구조를 주고 동역학을 주지 않음 | 강함. 사람 근거 계층이 받음 |
| 완성도 | 강함. 테스트 128개, 케이스 3건, 샌드박스 증거 | 약함. 3일에 새로 만듦 | 중간. 기존 자산을 살림 |
| 독창성 | 약함 | 강함. SNS 화제성 | 강함 |
| 팀 적합 | 두 사람 관심 | 한 사람 관심 | 세 사람 관심 전부 |
| 위험 | 낮음 | 높음 | 중간 |

핵심 변수는 둘이다.

**첫째, 초파리 주제가 NVIDIA 심사에서 유리하다.** 팀원의 걱정과 반대 방향이다. NVIDIA가 도킹과
신약개발 NIM을 호스팅한다. 계정 키로 다섯 경로에 GET을 보내 전부 405를 받아 경로 존재를
확인했다. 걱정해야 할 것은 Jev 하나뿐이고 그것도 배치로 해소된다.

**둘째, 두 주제가 이미 겹친다.** FDDD가 BindingDB 친화도와 DailyMed 사람 라벨 PK를 함께 싣고
있다. 화합물 6종 중 다섯이 허가된 약이다. 즉 도킹 점수를 낸 그 화합물에 사람 라벨과 실제
이상사례 보고가 존재한다. 약물감시 도구 3종을 버릴 필요가 없다.

## 권고안: 구조에서 사람까지, 과잉해석을 잡는 후보 검증 에이전트

### 한 문장

초파리 커넥톰과 NVIDIA 도킹 NIM으로 후보의 결합을 보고, 그 후보가 사람에게서 실제로 어땠는지
공개 데이터로 잇고, **각 단계에서 나올 수 없는 주장을 크리틱이 반려한다.**

### 파이프라인

두 주제를 나란히 두는 것이 아니다. 하나의 흐름이고 약물감시 도구가 뒷단에 들어간다.

```
구조     타깃 수용체와 후보 화합물
  ↓
결합     DiffDock NIM · AutoDock Vina 실측 · 초파리 커넥톰 포즈 탐색   (세 경로 대조)
  ↓
참조     BindingDB 실험 친화도 (종점 4종 분리 유지)
  ↓
사람     DailyMed 라벨 PK와 기재 여부 · openFDA FAERS 불균형 지표 · PubMed 문헌
  ↓
검증     근거 ID 결정 규칙 → 숫자 오라클 → 과잉해석 LLM 판정
```

### 이렇게 두면 풀리는 것

- **팀원 세 사람의 관심이 전부 들어간다.** 초파리와 도킹은 면역학 박사이자 AI 신약개발 저자인
  팀원, 라벨과 약 정보는 약사인 팀원, 약물감시 지표와 검증 규율은 팀장이 맡는다
- **버리는 것이 거의 없다.** 약물감시 도구 3종을 그대로 쓴다. 테스트 131개 중 도메인 종속
  87퍼센트를 살린다
- **초파리의 실용성 약점을 사람 근거 계층이 받는다**
- **심사 1번 항목이 세 장에서 일곱 장으로 늘어난다**
- **팀원의 데모가 이미 이 방향이다.** 억지 결합이 아니다

### 분량 걱정에 대한 답

이어 붙이기가 초파리 단독보다 훨씬 더 큰 일로 보이지만 실제 차이는 작다. 추가되는 것은
**이미 동작하는 도구 3종에 `@register_function` 래퍼를 씌우는 일**뿐이다. 계산 로직은 손대지
않는다. 그리고 그 작업은 어느 주제로 가든 해야 하는 일이다.

## 이번 기여: 과잉해석 크리틱

가장 값어치 있는 부분이다. 우리 평가의 약점을 메우면서 동시에 새 기여가 된다.

지금 적발률 1.0은 의미가 얇다. `eval/cases.jsonl`이 3건이고 부정 케이스 1건은 `evidence_ids`가
빈 배열이라 LLM 없이 결정 규칙만으로 잡힌다. `configs/eval.yml:8` 주석이 스스로 "키 없이 결정
규칙만 1/3, LLM 붙으면 3/3"이라고 적었다. **LLM의 의미 판단으로만 잡히는 케이스가 데이터셋에
없다.**

과잉해석이 바로 그런 케이스다. 근거 ID가 제대로 붙고 숫자도 로그와 일치하는데 추론이 틀린
주장을 만들 수 있다. FDDD의 `notes` 8항목과 NVIDIA 문서가 규칙 목록과 부정 케이스 생성기를
동시에 준다.

| 규칙 | 반려 대상 주장의 예 |
|---|---|
| 교차 타깃 순위 금지 | 서로 다른 타깃의 Vina 점수를 비교해 선택성을 말한다 |
| 친화도 환산 금지 | 도킹 점수에서 Kd, Ki, IC50, EC50을 추론한다 |
| 교차 도킹 해석 금지 | 교차 도킹 결과를 실험으로 확인된 결합이라고 말한다 |
| 종 차이 명시 | 생쥐 COX-2 구조(3LN1) 결과를 사람 결과처럼 말한다 |
| 수렴 주장 금지 | 단일 seed, exhaustiveness 4 결과에 재현성이나 수렴을 말한다 |
| RMSD 기준 명시 | 실행 내 포즈 RMSD를 결정 구조와의 일치로 말한다 |
| 종점 혼합 규칙 | BindingDB의 Ki, Kd, IC50, EC50을 **보정과 불확실성 표기 없이** 단일 친화도로 합친다. 문헌상 대규모 활용에서는 혼합이 수용되므로 '혼합 금지'가 아니라 이렇게 좁혀 적는다 |
| 입력 동일성 | SMILES를 실행된 입력이라고 말한다. 실행 입력은 PDBQT다 |
| 초파리 결과 해석 | 초파리 포즈 탐색 성공을 효능이나 약효의 근거로 말한다 |
| DiffDock 신뢰도 환산 금지 | `position_confidence`를 결합 친화도로 환산한다. NVIDIA가 금지 문장을 적었고 원 논문에서 이 값이 RMSD 2옹스트롱 이진 분류기 출력임이 확인된다. **규칙 중 문헌 뒷받침이 가장 강하다** |
| 도구 간 점수 혼용 금지 | Vina의 kcal/mol과 DiffDock의 confidence를 같은 척도로 비교한다 |
| DiffDock 재현성 주장 금지 | 시드 없는 단일 호출의 confidence 를 재현되는 값처럼 말한다. **같은 입력 두 번에 0.725와 0.515로 갈린 것을 실측했다** |
| DiffDock 음수 신뢰도 해석 금지 | `position_confidence` 가 음수인 것을 결합하지 않는다는 증거로 읽는다. **실측에서 교차 도킹 경로가 -0.172 에서 -0.665 로 나왔다.** 이 값은 확률이 아니라 로짓으로 보인다 |
| 라벨 기재와 인과 구분 | FAERS 불균형 지표를 인과 관계로 말한다. 기존 약물감시 규율 |

부정 케이스 하나가 데이터에 이미 준비돼 있다. niraparib이 세 타깃에 모두 도킹돼 있고 점수가
PARP1 -10.178, factor Xa -7.967, COX-2 -6.605다. "그러므로 PARP1 선택성이 있다"는 주장은
숫자가 전부 맞고 근거 ID도 제대로 붙는데 2번 규칙이 금지한 추론이다. 결정 규칙과 숫자 오라클을
모두 통과하고 **LLM 크리틱만 잡는다.**

적발률이 처음으로 LLM의 의미 판단을 재는 숫자가 된다. 그리고 이 규율은 팀장의 QA/RA 경험과
팀원의 신약개발 전문성이 함께 만든 것이라 발표에서 설득력이 있다.

## 도구 구성

```
[게이트]  jev_triage       Jev로 후보를 screen/skip/review 분류 (보조, 생략 가능)
                            또는 nemotron-3.5-lightning 으로 대체
  ↓
[작성자]  계획 nemotron-3-super-120b-a12b, 반복 nemotron-3.5-lightning-30b-a3b
  신규
   diffdock_nim      NVIDIA DiffDock으로 포즈와 confidence
   vina_reference    FDDD 도킹 8건 조회와 SHA256 대조
   flybrain_pose     초파리 커넥톰 포즈 탐색 (팀원 모듈)
   bindingdb_ref     BindingDB 참조 친화도, 종점 4종 분리 유지
   rcsb_structure    RCSB에서 수용체 받고 SHA256 기록
   genmol_nim        후보 생성 (여유 있으면)
  기존 코드에 등록만
   openfda_faers     FAERS 집계와 PRR, ROR
   dailymed_label    라벨 섹션 검색과 PK
   pubmed_search     문헌 근거
  ↓
근거 ID 붙은 주장 JSON
  dock:diffdock:<id>, dock:vina:<sha256>, bindingdb:<id>,
  dailymed:setid:<id>:section:12.3, faers:2x2:<drug>-<event>, pubmed:<PMID>, fly:pose:<run>
  ↓
[크리틱 · 쓰기 도구 없음]
  1단 결정 규칙    주장 존재, 근거 ID 유무, 빈 문자열            ← 기존 그대로, 0줄 수정
  2단 숫자 오라클  포즈 점수가 로그와 일치, SHA256 대조, PRR 재계산  ← verify 골격 재사용
  3단 LLM 판정     위 규칙 14종으로 과잉해석 반려                ← 신규, 이번 기여
  ↓
[평가]  nat eval 적발률. 정상 케이스 + 과잉해석 부정 케이스
  ↓
[정책]  health.api.nvidia.com, integrate.api.nvidia.com, rcsb.org, bindingdb.org,
        api.fda.gov, dailymed.nlm.nih.gov, eutils.ncbi.nlm.nih.gov 만 허용
```

## 게이트 (9/25 밤에 순서대로)

하나라도 막히면 대체 경로로 간다. 게이트를 통과하지 못한 채 코드를 쓰지 않는다.

| 게이트 | 확인 방법 | 막히면 |
|---|---|---|
| ~~**G1 생물학 NIM 권한**~~ | **2026-09-25 통과.** HTTP 200, 4.1초, `Nvcf-Status: fulfilled`, `position_confidence` 3개. 기록은 `eval/results/diffdock_smoke.txt` | 해당 없음 |
| **G2 FDDD 코드 접근** | 팀원에게 저장소 접근과 라이선스, 맡을 범위 확인 | 공개 데이터만 인용하고 초파리 포즈 탐색은 화면 녹화로 대체 |
| **G3 Jev 접근** | Vercel 계정으로 `typesafe-ai/jev` 호출 1회 | Jev 제외, `nemotron-3.5-lightning`으로 같은 구조 |
| **G4 레이트리밋** | 429가 얼마나 빨리 오는지 확인. 크레딧이 아니라 레이트리밋으로 관리한다 | 요청 간 1.5초, 지수 백오프, `Retry-After` 존중, 응답 캐시 |
| **G5 오프라인 본선** | 패스트캠퍼스에 전원 참석 필요 여부 문의(평일 10~18시) | 10/2 발표 전까지 확인. 참석 가능한 인원으로 역할 배치 |

**G1이 가장 중요했고 통과했다.** 초파리 주제의 심사 1번 항목 유불리가 이것으로 정해졌다.
NVIDIA 도킹 NIM을 실제로 부를 수 있으므로 권고안의 전제가 성립한다. 최후 대체(PharmaSignal 단독)로
되돌릴 이유가 사라졌다.

G2는 사실상 해소된 것으로 보인다. 팀원이 데모 주소를 먼저 공유하고 "해커톤 출품까지 하려면
조금 더 디벨럽을 하면 좋을 것 같다"고 했으므로 사용 자체에 동의가 있다. 남은 것은 코드 저장소
접근과 라이선스 확인이다.

## 일정

| 날짜 | 할 일 | 산출물 |
|---|---|---|
| 9/25 밤 | 게이트 G1~G5. 팀에 이 문서 공유하고 주제 확정. 이름 결정 | 게이트 결과, 주제 확정 |
| 9/26 오전 | **도메인 도구를 NAT 함수로 등록하는 선례 만들기.** 기존 `openfda_faers`, `dailymed_label`, `pubmed_search` 셋에 래퍼 씌워 배선 확인 | `nat validate` 통과, `nat run`으로 도구 호출 확인 |
| 9/26 오후 | `bionemo_client.py`를 먼저 만들고 `diffdock_nim`, `vina_reference`, `bindingdb_ref` 작성과 등록. `author.yml`과 `author_guarded.yml` 동시 수정 | 도킹 1건 E2E 결과 JSON |
| 9/26 밤 | `jev_triage` 또는 대체. 초파리 경로 연결 또는 기존 결과 인용 | 후보 여러 건 분류 결과 |
| 9/27 오전 | 크리틱 3단 과잉해석 규칙 14종. `eval/cases.jsonl` 재작성(정상 + 부정 최소 3건). `nat eval` | 적발률 수치, 반려 사유 원문 |
| 9/27 오후 | OpenShell 정책 신규 작성, 스모크로 차단 로그. 아키텍처 그림과 결과 그림 | 정책 YAML, 차단 로그, PNG 2장 |
| 9/27 밤 | 영상 원고와 슬라이드, `assets/video/build.sh`로 렌더 | mp4와 SRT |
| 9/28 오전 | README, 신청서 문안(문제 300자, 솔루션 500자 각 ±10퍼센트), PDF | 제출물 일체 |
| 9/28 18:00 | 팀원 각자 폼 제출 확인 후 제출 | 제출 완료 캡처 |

팀원이 보스턴이라 한국시간 평일 오전이나 밤 10시 이후에만 겹친다. **9/26 밤 10시 이후와 9/27
오전을 팀원 담당 구간(초파리 경로, 도킹 해석 검토)으로 잡는다.**

### 줄이는 순서

1. `genmol_nim` 후보 생성
2. 초파리 포즈 탐색 실행. 팀원의 기존 결과 인용과 화면 녹화로 대체
3. `jev_triage`. `nemotron-3.5-lightning`으로 대체
4. `rcsb_structure`와 구조 예측. FDDD의 준비된 PDBQT를 그대로 사용
5. 그림 2장 중 결과 그림

### 줄이지 않는 것

- **도메인 도구가 NAT 함수로 등록되어 에이전트가 실제로 부르는 것.** 심사 1번 항목의 핵심이고
  지금 비어 있다
- DiffDock NIM 호출 1건 이상. NVIDIA 생물학 스택을 썼다는 유일한 증거
- 과잉해석 부정 케이스 최소 3건과 적발률 수치
- OpenShell 차단 로그
- 영상

### 최후 대체

9/27 정오까지 G1이 막히고 과잉해석 규칙이 서지 않으면 **PharmaSignal로 제출한다.** 이미 테스트
128개와 케이스 3건과 샌드박스 증거가 있다. 그 경우에도 9/26 오전의 도구 등록 작업은 그대로
값을 한다. PharmaSignal의 가장 큰 구멍이 바로 그것이기 때문이다.

## 고칠 파일

### 그대로 두는 것

`src/harness/schemas.py`, `src/harness/critic.py`, `src/harness/evaluators.py`,
`configs/critic.yml`, `configs/eval.yml`, `policies/base.yaml`,
`policies/nvidia-provider-profile.yaml`, `scripts/openshell_vm_up.sh`, `scripts/hello_nemotron.py`.

도메인 중립 코어가 약 500줄이다. 크리틱은 근거 ID의 **내용을 보지 않고 존재 여부만** 보게
설계돼 있어 도메인이 바뀌어도 그대로 돈다. 프롬프트의 약물감시 예시 열거(`critic.py:47`)는
코드를 고치지 않고 `CriticJudgeConfig.system_prompt` 필드로 YAML에서 덮어쓴다.

### 신규

| 파일 | 내용 |
|---|---|
| `src/harness/tools/bionemo_client.py` | **먼저 만든다.** 프레임워크 무관 HTTP 계층. 429 지수 백오프와 `Retry-After` 존중, 202 폴링 분기, 요청 간 1.5초, 응답 캐시 |
| `src/harness/tools/dock_diffdock.py` | DiffDock NAT 래퍼 |
| `src/harness/tools/dock_vina_reference.py` | FDDD 도킹 8건 조회와 SHA256 대조 |
| `src/harness/tools/dock_bindingdb.py` | BindingDB 참조. 종점 4종 분리 유지 |
| `src/harness/tools/dock_rcsb.py` | RCSB 구조 받기 |
| `src/harness/tools/flybrain_pose.py` | 초파리 포즈 탐색 연결. G2 결과에 따라 |
| `src/harness/tools/jev_triage.py` | Vercel AI Gateway `typesafe-ai/jev`. G3 결과에 따라 |
| `src/harness/tools/overclaim_rules.py` | 과잉해석 규칙 14종. 크리틱 3단이 참조 |
| `policies/<주제>.yaml` | `base.yaml` 복사 후 호스트 7곳 추가 |
| `tests/test_dock_*.py` | 순수 계산부 단위 테스트. 네트워크는 `@pytest.mark.network` |

`src/harness/tools/pharmasignal_common.py`(140줄)의 HTTP GET 재시도, 429 대기, 파일 캐시,
레이트리밋은 이름만 바꿔 그대로 쓴다. 새 도구 전부가 이것을 쓴다.

### 수정

| 파일 | 고칠 것 |
|---|---|
| `src/harness/register.py` | 152-156행 import 블록 해제와 신규 모듈 추가. `prr_calculator`와 `compute_prr_ror`는 `tools/`로 이동 |
| `src/harness/tools/pharmasignal_{openfda,dailymed,pubmed}.py` | `@register_function` 래퍼 추가. 계산 로직은 손대지 않는다 |
| `configs/author.yml` | `functions`, `tool_names`, `system_prompt` |
| `configs/guardrails/author_guarded.yml` | **위와 같은 내용을 중복으로.** 동기화가 수동이라 빠뜨리기 쉽다 |
| `configs/guardrails/rails/prompts.yml` | 13-21행의 후보별 허용과 거부 문장 재작성 |
| `eval/cases.jsonl` | 케이스 교체. 부정 케이스를 LLM만 잡는 종류로 |
| `tests/test_harness_configs.py` | 34, 36행의 `functions`와 `tool_names` 하드코딩 단정이 깨진다 |
| `tests/test_harness_register.py` | cases.jsonl 정합 단정 갱신 |
| `scripts/make_figures.py` | `make_architecture()`는 새로 쓴다. `load_cases()`는 키 계약 교체. 드로잉 프리미티브 유지 |
| `scripts/openshell_smoke.sh` | 38행 정책 화이트리스트와 73-103행 호스트 목록에 분기 추가 |
| `assets/video/02_나레이션.txt`, `08_timeline.txt`, `slides.py` | 원고와 슬라이드 내용 |

### 정책 보강

DLI 강좌 기준선 대조에서 나온 것이고 주제와 무관하게 고칠 값어치가 있다.

1. 추론 엔드포인트에 `/usr/bin/curl`을 허용한 것은 강좌가 적색으로 분류한 경우다.
   제출본에서 빼거나 `enforcement: audit`으로 분리한다
2. `base.yaml`과 `pharmasignal.yaml`에 `process` 블록이 없다. 이미지 `USER`가 바뀌면 조용히
   root로 돈다. `nightshift.yaml`처럼 명시한다
3. `access: read-write`는 경로를 가리지 않는다. `rules`로 `POST /v1/chat/completions`와
   `GET /v1/models`만 여는 예시가 `docs/notes/nat-harness.md:528-540`에 있다

## 확인해 주실 것

1. **주제 확정.** 이어 붙이기, 초파리 단독, PharmaSignal 단독 중 어느 쪽인지. 권고는 이어 붙이기다
2. **FDDD 코드 접근.** 저장소 접근 권한과 라이선스, 팀원이 직접 맡을 범위
3. **Vercel 계정.** Jev를 쓰려면 AI Gateway 계정과 결제 수단이 필요하다
4. ~~이름~~ **FlyGate 로 확정(2026-09-25).** 팀장이 정했고 팀원 의견을 받아 바꿀 수 있게 열어 둔다.
   초파리라는 훅과 검증 관문을 한 단어에 담고, PharmaSignal 과 같은 조어 규칙이라 계보가 이어지며,
   생물정보 도구와 이름이 겹치지 않는다. 한글로 "플라이게이트" 로 읽는다.
   바꾸기 쉽게 두 곳에만 박아 두었다. `scripts/make_figures.py` 의 `PROJECT_NAME` 상수와
   `policies/flydock.yaml` 파일명이다. FDDD 는 팀원 A 의 저작물이라 그대로 쓰지 않는다.
5. **DLI 수료 범위.** 팀원 전원인지 대표 1명인지. 전원이면 강좌 안내 공유가 급하다

## 남은 공백

- ~~생물학 NIM POST 권한~~ **확인 완료. 통과.** `eval/results/diffdock_smoke.txt`
- ~~`steps`인지 `num_steps`인지~~ **`steps`다.**
- [Gap:Assumption] `health.api`의 요청 본문 상한. 222KB는 통과했고 그 위는 모른다
- [Gap:Procedural] FDDD 코드 접근 권한과 라이선스
- [Gap:Procedural] 오프라인 본선 전원 참석 필요 여부. 10/2 발표 전에 문의
- [Gap:Procedural] DLI 수료가 전원인지 대표 1명인지
- [Gap:Consideration] 파이프라인이 길어 3일에 담기 어렵다. 줄이는 순서를 미리 합의해 둔다
- [unverified] Jev의 200배와 400배는 공급사 자체 측정의 상단 값이다. 독립 벤치마크는 없다
- [unverified] 초파리 뉴런 수가 자료마다 다르다. 인용할 때 어느 커넥톰인지 밝힌다
