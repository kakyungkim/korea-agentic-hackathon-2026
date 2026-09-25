# niraparib 한 후보의 두 경로 대조: 도킹에서 사람 근거까지

생성 2026-09-25T07:58:04+00:00, 실행 모드 온라인, DiffDock 캐시 재생, 화합물 Niraparib, 이상사례 Thrombocytopenia

같은 화합물, 같은 도구, 같은 단계다. 점수 차이는 2.211 kcal/mol 인데 한쪽은 말할 수 있고 한쪽은 말할 수 없다.

## 단계별 근거

| 단계 | 경로 A: PARP1 촉매도메인 (4R6E chain A) | 경로 B: 응고인자 Xa (2P16 chain A) |
|---|---|---|
| 구조 | RCSB 4R6E 원본 1,879,848바이트, 체인 A/B/C/D<br>보낸 것은 chain A ATOM 2,752줄, 222,911바이트<br>SHA256 290872054fd93e02...<br>`rcsb:4R6E:chainA:29087205` | RCSB 2P16 원본 231,984바이트, 체인 A/L<br>보낸 것은 chain A ATOM 1,853줄, 150,092바이트<br>SHA256 533a3c5b605f97dd...<br>`rcsb:2P16:chainA:533a3c5b` |
| 결합 1 (Vina 실측) | **-10.178 kcal/mol**<br>role 원문: "co-crystal redocking control"<br>AutoDock Vina 1.2.3, seed 20260914, exhaustiveness 4, num_modes 5<br>박스 중심 [-39, 5, -8], 크기 [15, 20, 14]<br>로그 SHA256 3fe4e8bb90aaf7c0...<br>`dock:vina:3fe4e8bb` | **-7.967 kcal/mol**<br>role 원문: "Exploratory cross-docking; no claim of validated binding"<br>AutoDock Vina 1.2.3, seed 20260914, exhaustiveness 4, num_modes 5<br>박스 중심 [7.48497143, 43.97488571, 62.17711429], 크기 [20, 20, 20]<br>로그 SHA256 e3970b3cf97bc8ac...<br>`dock:vina:e3970b3c` |
| 결합 2 (DiffDock NIM) | 포즈 3개, position_confidence 0.761, 0.693, 0.515<br>요청 SHA256 f31b513b3d160866...<br>응답 SHA256 a3f5fdbd1bb3ee98...<br>캐시 재생<br>시드가 없어 호출마다 값이 다르다. 친화도로 환산하지 않는다.<br>`dock:diffdock:f31b513b:pose1` `dock:diffdock:f31b513b:pose2` `dock:diffdock:f31b513b:pose3` | 포즈 3개, position_confidence -0.172, -0.205, -0.665<br>요청 SHA256 91b182ea53cf0965...<br>응답 SHA256 6b9c88eeb2a5ebf4...<br>캐시 재생<br>시드가 없어 호출마다 값이 다르다. 친화도로 환산하지 않는다.<br>`dock:diffdock:91b182ea:pose1` `dock:diffdock:91b182ea:pose2` `dock:diffdock:91b182ea:pose3` |
| 참조 (BindingDB) | Human PARP1 / UniProt P09874, 레코드 7,311건, 화합물 5,769종<br>종점별로 Ki 1,194, IC50 5,588, Kd 214, EC50 315<br>네 종점을 하나의 친화도로 합치지 않는다.<br>`bindingdb:P09874` | **참조 집합 없음**<br>이 실행에 붙은 참조 친화도 집합은 Human PARP1 / UniProt P09874 하나뿐이다. 응고인자 Xa(2P16) 에 대응하는 참조 집합은 없다.<br>`bindingdb:P09874` |
| 사람 1 (DailyMed 라벨) | ZEJULA(niraparib) 라벨, Thrombocytopenia 기재 **있음**<br>기재 절: 5절 경고와 주의사항, 6절 이상반응, 본문 6곳<br>12.3 절 PK: 반감기 50시간, 생체이용률 73퍼센트, 혈장단백결합 83퍼센트<br>`dailymed:setid:b7f675e2-159c-490c-b6f4-3f16d9492b7d:section:12.3` `dailymed:setid:b7f675e2-159c-490c-b6f4-3f16d9492b7d:section:6` `dailymed:setid:b7f675e2-159c-490c-b6f4-3f16d9492b7d:section:5` | ZEJULA(niraparib) 라벨, Thrombocytopenia 기재 **있음**<br>기재 절: 5절 경고와 주의사항, 6절 이상반응, 본문 6곳<br>12.3 절 PK: 반감기 50시간, 생체이용률 73퍼센트, 혈장단백결합 83퍼센트<br>`dailymed:setid:b7f675e2-159c-490c-b6f4-3f16d9492b7d:section:12.3` `dailymed:setid:b7f675e2-159c-490c-b6f4-3f16d9492b7d:section:6` `dailymed:setid:b7f675e2-159c-490c-b6f4-3f16d9492b7d:section:5` |
| 사람 2 (FAERS) | 2x2: a 1,065, b 21,051, c 108,978, d 20,561,596<br>PRR 9.13 (95% CI 8.61 ~ 9.69)<br>ROR 9.55 (95% CI 8.97 ~ 10.15)<br>Yates 보정 카이제곱 7672.29, Evans 기준 충족<br>데이터 최종 갱신 2026-07-30<br>`faers:2x2:niraparib-thrombocytopenia` | 2x2: a 1,065, b 21,051, c 108,978, d 20,561,596<br>PRR 9.13 (95% CI 8.61 ~ 9.69)<br>ROR 9.55 (95% CI 8.97 ~ 10.15)<br>Yates 보정 카이제곱 7672.29, Evans 기준 충족<br>데이터 최종 갱신 2026-07-30<br>`faers:2x2:niraparib-thrombocytopenia` |
| 사람 3 (PubMed) | 검색어 niraparib AND "Thrombocytopenia", 총 92건<br>대표 PMID 40687421: Severe thrombocytopenia induced by niraparib in ovarian cancer patients: a case report and literature review.<br>`pubmed:40687421` | 검색어 niraparib AND "Thrombocytopenia", 총 92건<br>대표 PMID 40687421: Severe thrombocytopenia induced by niraparib in ovarian cancer patients: a case report and literature review.<br>`pubmed:40687421` |

경로 B 의 체인 선택은 우리 판단이다. 2P16 은 chain A(1,853 ATOM)와 chain L(385 ATOM)로 되어 있다. 촉매도메인인 chain A 를 고른 것은 우리 선택이고 FDDD 의 준비된 PDBQT 와 같은 파일이 아니다.

사람 근거 세 줄은 두 경로에 같은 값이 들어간다. 그 셋이 화합물에 붙은 근거이고 타깃을 가리지 않기 때문이고, 경로 B 의 공백이 바로 여기서 드러난다.

## 크리틱 판정 두 벌

같은 근거로 요약을 두 벌 만들었다. (가)는 주장 14건, (나)는 주장 7건이고 근거 ID 와 숫자는 양쪽이 같다. (나)에는 과잉해석 7건을 심었다.

**(가) 뒷받침되는 요약: pass** (판정 주체: 3단 과잉해석 LLM 판정)
- 1단 결정 규칙: 통과 (점검 5건)
- 2단 숫자 오라클: 통과. 5/5 일치, 커버리지 83%
- 3단 과잉해석 판정(nvidia/nemotron-3-super-120b-a12b): pass

**(나) 과잉해석을 심은 요약: reject** (판정 주체: 3단 과잉해석 LLM 판정)
- 1단 결정 규칙: 통과 (점검 5건)
- 2단 숫자 오라클: 통과. 5/5 일치, 커버리지 83%
- 3단 과잉해석 판정(nvidia/nemotron-3-super-120b-a12b): reject
  - 반려 사유 원문: 교차 타깃 순위 금지: PARP1 에서 -10.178 kcal/mol 이고 응고인자 Xa 에서 -7.967 kcal/mol 이므로, niraparib 은 응고인자 Xa 보다 2.211 kcal/mol 만큼 PARP1 에 더 강하게 결합하고 PARP1 선택성을 갖는다.
  - 반려 사유 원문: 친화도 환산 금지: Vina -10.178 kcal/mol 을 환산하면 Kd 는 나노몰 수준이고 IC50 도 같은 자리에 온다. DiffDock 1순위 position_confidence 0.761 이 그 친화도를 같은 척도에서 뒷받침한다.
  - 반려 사유 원문: 수렴 주장 금지: seed 20260914 를 고정하고 exhaustiveness 4 로 돌렸으므로 이 점수는 수렴한 재현값이고 다시 돌려도 같게 나온다.
  - 반려 사유 원문: 교차 도킹 해석 금지: 응고인자 Xa 에서 -7.967 kcal/mol 로 결합하므로, niraparib 을 쓸 때 항응고 작용을 함께 고려해야 한다.
  - 반려 사유 원문: 종점 혼합 규칙: BindingDB 참조 집합의 Ki 1,194건과 IC50 5,588건과 Kd 214건과 EC50 315건을 합친 7,311건이 하나의 친화도 근거가 되어 위 도킹 점수를 실험으로 검증한다.
  - 반려 사유 원문: 라벨 기재와 인과 구분: PRR 9.13, ROR 9.55(신뢰구간 하한 8.97, 상한 10.15), Yates 보정 카이제곱 7672.29 는 niraparib 이 혈소판감소증을 일으킨다는 것을 통계적으로 확증한다.
  - 반려 사유 원문: 라벨 기재와 인과 구분: 혈소판감소증이 라벨 경고와 이상반응 절에 기재된 것은 위 응고인자 Xa 결합의 사람 쪽 확증이다.
  - 후속 조치 원문: 교차 타깃 순위 금지 위반: 서로 다른 타깃의 Vina 점수를 비교해 선택성 또는 상대적 결합 세기를 주장할 수 없음
  - 후속 조치 원문: 친화도 환산 금지 위반: 도킹 점수에서 Kd, Ki, IC50 등을 추론할 수 없음
  - 후속 조치 원문: 수렴 주장 금지 위반: 단일 seed와 exhaustiveness 4 결과에 재현성 또는 수렴을 주장할 수 없음
  - 후속 조치 원문: 교차 도킹 해석 금지 위반: 탐색적 교차 도킹 결과를 실험으로 확인된 결합이나 임상 주의사항으로 해석할 수 없음
  - 후속 조치 원문: 종점 혼합 규칙 위반: BindingDB의 Ki, Kd, IC50, EC50을 보정과 불확실성 표기 없이 단일 친화도로 합칠 수 없음
  - 후속 조치 원문: 라벨 기재와 인과 구분 위반: FAERS 불균형 지표를 인과 관계로 해석할 수 없음
  - 후속 조치 원문: 라벨 기재와 인과 구분 위반: 라벨 기재만을 근거로 인과 관계를 주장할 수 없음

심은 과잉해석 목록: 교차 타깃 순위와 선택성 추론, 도킹 점수와 DiffDock 신뢰도의 친화도 환산, 단일 seed 결과의 수렴과 재현성 주장, 교차 도킹을 확인된 결합으로 해석, 종점 4종을 보정 없이 단일 친화도로 합침, 불균형 지표를 인과로 해석, 화합물 단위 사람 근거를 특정 타깃 결합의 확증으로 사용.

## 근거 안의 진술

- 경로 A 에서 niraparib 이 PARP1 4R6E chain A 에 대해 Vina -10.178 kcal/mol 을 받았다는 사실. 단 이 값은 같은 실행 안의 다른 포즈와만 비교한다.
- 그 실행의 프로토콜(seed 20260914, exhaustiveness 4, 박스 좌표)과 로그 SHA256 으로 어느 실행의 값인지 대조할 수 있다는 사실.
- DiffDock 호출 1회에서 나온 1순위 포즈 신뢰도 0.761. 요청 SHA256 으로 지정되는 이 호출의 결과라는 한정과 함께 쓴다.
- 경로 A 에는 사람 PARP1 참조 친화도 집합이 붙어 있고 종점이 Ki, IC50, Kd, EC50 넷으로 나뉘어 있다는 사실.
- 혈소판감소증이 ZEJULA 라벨에 이미 기재된 알려진 위험이라는 사실과 라벨 12.3 절의 사람 PK 값.
- FAERS 2x2 표와 PRR 9.13, ROR 9.55 수치. 그리고 라벨 기재 반응이라 새 신호로 올릴 대상이 아니라는 판정.
- PubMed 문헌 92건이 있고 그중 제목에 이 이상사례가 들어간 보고가 있다는 사실.
- 경로 B 의 Vina 점수 -7.967 kcal/mol 자체와, FDDD 가 그 조합에 적어 둔 역할이 "Exploratory cross-docking; no claim of validated binding" 이라는 사실.

## 근거 밖의 진술

- 두 점수(-10.178, -7.967)를 견주어 PARP1 선택성을 말하는 것. 서로 다른 단백질이고 교차 타깃으로 보정되지 않았다.
- Vina 점수나 DiffDock 신뢰도를 Kd, Ki, IC50, EC50 으로 환산하는 것. NVIDIA 문서 원문이 "Do not convert confidence directly into binding affinity" 다.
- 경로 B 를 실제 결합으로 말하는 것. FDDD 가 그 조합에 적어 둔 역할은 "Exploratory cross-docking; no claim of validated binding" 이다.
- BindingDB 의 Ki, Kd, IC50, EC50 을 보정과 불확실성 표기 없이 합쳐 단일 친화도로 쓰는 것.
- 단일 seed 와 exhaustiveness 4 로 나온 점수에 수렴이나 재현성을 말하는 것. DiffDock 은 호스팅 API 에 시드가 아예 없어 더 강하게 금지된다.
- FAERS 불균형 지표를 인과로 말하는 것. 보고 편향과 적응증 교란과 노출 규모 차이가 남는다.
- 라벨과 FAERS 와 문헌을 경로 B 결합의 사람 쪽 확증으로 쓰는 것. 이 셋은 화합물 단위 근거이고 타깃을 가리지 않는다.
- SMILES 를 실행된 입력이라고 말하는 것. FDDD 의 실행 입력은 준비된 PDBQT 파일이다.
- 포즈 사이 RMSD 를 결정 구조와의 일치로 말하는 것. FDDD 의 RMSD 열은 같은 실행 안의 포즈끼리 잰 값이다.
- 경로 B 에 참조 친화도 집합이 있다고 말하는 것. 이 실행에 붙은 참조 집합은 사람 PARP1 하나뿐이다.
- DiffDock 신뢰도가 음수로 나온 것을 결합하지 않는다는 증거로 읽는 것. 이 값은 포즈가 기하학적으로 맞을 확률에 대한 이진 분류기의 출력이라 낮게 나왔다는 뜻이고, 결합 여부를 판정하지 않는다.

## 시사점

같은 화합물을 같은 도구로 두 번 돌렸는데, PARP1 경로에서는 계산값과 참조 친화도 집합과 사람 라벨과 이상사례 보고가 같은 대상을 가리켰고 응고인자 Xa 경로에는 Vina 점수 하나만 남았다. 두 경로를 가르는 것은 점수 차이 2.211 kcal/mol 이 아니라 그 점수를 받쳐 줄 실험 근거가 있는지다. 그 경계를 사람이 매번 기억하지 않아도 되게 근거 ID 로 붙여 두고, 경계를 넘는 주장을 크리틱 3단이 반려하게 만든 것이 이 파이프라인의 기여다.
