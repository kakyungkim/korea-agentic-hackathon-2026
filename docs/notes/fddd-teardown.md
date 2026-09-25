# FDDD 기술 분해 (drug.flybrain.kr)

2026-09-25 조사. 자산과 엔진 코드를 직접 받아 읽었다. 데모의 성격과 규모를 파악하고,
우리가 무엇을 가져다 쓸 수 있는지 판단하기 위한 것이다.
데모의 과학적 내용과 도킹 수치는 `docs/notes/fddd-and-jev.md` 에 있다.

## 한 줄

**초파리 전뇌 커넥톰을 브라우저에서 LIF 로 실시간 시뮬레이션하고, 오프라인에서 미리 계산한
AutoDock Vina 점수를 보상 신호로 미각 뉴런에 넣어 움직임을 만드는 정적 웹앱**이다.
서버 연산이 없다. 전부 클라이언트에서 돈다.

## 자산 규모 (실측)

| 파일 | 크기 |
|---|---|
| `connectome.bin.gz` | 27,352,793 바이트 (27.4 MB) |
| `prism-models-*.js` | 806,297 바이트 |
| `display-points.json` | 2,657,020 바이트 |
| `root-ids.json` | 1,434,131 바이트 |
| `main-*.js` | 105,430 바이트 |
| `main-*.css` | 103,761 바이트 |
| `engine/malecns/core.js` | 13,755 바이트 |
| `engine/malecns/worker.js` | 1,717 바이트 |

**첫 로딩에 30 MB 가 넘는다.** 커넥톰이 대부분이다.

## 데이터 (가장 큰 일)

`manifest.json` 이 계보를 전부 적어 두었다.

| 항목 | 값 |
|---|---|
| 데이터셋 | `male-cns:v1.0` |
| 출처 | `male-cns.janelia.org/download/` |
| 라이선스 | **CC BY 4.0** |
| 원본 행 수 | 151,856,684 |
| 뉴런 | 167,122 |
| 전체 시냅스 | 124,162,779 |
| 유지 시냅스 | 89,851,287 |
| 엣지 (시냅스 5 이상) | 6,241,236 |
| 제외된 약한 엣지 | 19,337,579 |
| 렌더링 대상 | 28,195 (전체의 17퍼센트) |
| 좌표 | 141,001 |
| 그룹 | 27종 |

선택 기준도 적혀 있다. `status=Traced` 165,122 행에 주석이 붙은 `status=null` 2,000 행을 더했고,
아교세포와 고아와 앵커를 뺐다. **"Runtime is a selected, edge-thresholded CNS model, not the full
unfiltered neuron graph"** 라고 스스로 못 박았다. `annotations`, `weights`, `neurotransmitters`
세 파일의 SHA256 도 들어 있다.

### 바이너리 포맷

`core.js` 주석에 규격이 적혀 있다. 리틀엔디언이다.

```
Header    uint32 × 2                                  neuron_count, edge_count
Edges     edge_count × (uint32 pre, uint32 post, float32 weight)   pre 로 정렬
Metadata  neuron_count × (uint8 region_type, uint16 group_id)
```

계산이 맞는다. 엣지 6,241,236 × 12바이트 = 74.9 MB, 메타 167,122 × 3바이트 = 0.5 MB.
합쳐 75.4 MB 가 gzip 으로 27.4 MB 가 된다. 압축률 36퍼센트다.

## 시뮬레이션 엔진

`engine/malecns/core.js` 에 있다. 상류가 MIT 라이선스이고
**"Modified FDDD research engine. Upstream MIT notice: LICENSE-MIT.txt"** 로 밝혔다.
원 저작권자는 Seth Miller(2017)다.

### 모델

누출 적분 발화(leaky integrate-and-fire)다. 파라미터가 코드에 그대로 있다.

| 상수 | 값 | 뜻 |
|---|---|---|
| `DEFAULT_LEAK_RATE` | 0.95 | 매 틱 막전위 감쇠 |
| `DEFAULT_THRESHOLD` | 1.0 | 발화 문턱 |
| `DEFAULT_REFRACTORY_PERIOD` | 3 | 불응기 틱 수 |
| `WEIGHT_SCALE` | 0.15 | 시냅스 가중치 배율 |
| `TARGET_TICK_RATE` | 10 | 초당 틱. 렌더러가 사이를 보간한다 |

부호는 예측 신경전달물질로 정한다. GABA 와 글루탐산은 음, 나머지와 미상은 양이다.
manifest 의 `dynamics` 필드가 **"not physiological validation"** 이라고 스스로 적었다.

### 자료구조와 최적화

값어치 있는 부분이다.

- **CSR 희소행렬.** `rowPtr`(Uint32Array[N+1]), `colIdx`(Uint32Array[edges]),
  `values`(Float32Array[edges]). 발화한 뉴런의 행만 훑어 후시냅스 전위를 더한다
- **구조체 배열이 아니라 배열의 구조체**(struct-of-arrays). `V`, `fired`, `refractory` 를
  각각 타입드 배열로 둔다
- **뉴런을 그룹 순으로 물리적으로 재정렬**해 각 그룹이 연속 구간을 차지하게 하고 CSR 도 같이
  재매핑했다. 지역성 때문이다
- 주석에 neuropil 게이팅(활성 그룹만 틱)이 적혀 있으나 **지금 `stepEngine` 은 매 틱 전체 뉴런을
  계산한다.** 주석과 코드가 어긋난 자리다
- Web Worker 에서 돌고 결과를 **전송 가능 객체**(transferable)로 넘겨 복사를 피한다

### 한 틱에 하는 일

```
1. 불응기 감소, 아니면 V *= leak
2. baseline 모드면 발화한 뉴런의 CSR 행을 훑어 후시냅스에 가중치 누적
3. 감각 입력 8채널을 감각 세포에 주입 (bias + gain × value)
4. 보상 채널(인덱스 8)을 미각 세포 1,428개에 주입   ← 도킹 점수가 들어오는 자리
5. V >= threshold 인 뉴런 발화, V=0, 불응기 3
6. 운동 세포 발화를 6개 빈으로 모아 지수이동평균(0.72/0.28)
7. tanh 로 3개 출력 산출 (좌우, 상하, 추력)
8. 렌더링용 activity 배열 반환
```

### 대조군이 코드에 있다

`mode` 가 `baseline`, `disconnected`, `silenced` 셋이다. `silenced` 는 재귀 전달까지 포함해
모든 구동을 없앤다. **대조군을 코드에 넣어 둔 것이 이 데모의 신뢰도를 올린다.**
우리 과잉해석 규칙과 같은 정신이다.

## 도킹이 들어오는 방식

manifest 의 `rewardChannel` 필드가 정확히 적어 두었다.

> Authored input mapping of a reward signal (Vina-derived, learned-preference-weighted) into
> annotated gustatory receptor neurons; not a physiological feeding model.

즉 **Vina 점수를 정규화해 미각 수용체 뉴런 1,428개의 입력으로 넣고**, 그 결과로 나온 운동
출력이 움직임을 만든다. "먹이에 초파리가 꼬이듯 결합력 높은 후보에 꼬인다" 가 이렇게 구현됐다.
`gustatory.json` 에 대상 뉴런 인덱스가 있다.

**도킹 자체는 브라우저에서 돌지 않는다.** AutoDock Vina 1.2.3 을 Webina/MolModa WASM 으로
Node `worker_threads` 에서 미리 돌려 정적 JSON 으로 서빙한다. `/api/docking/status` 를 부르는
코드가 있으나 404 를 돌려준다.

## 프런트엔드

- **Vite** 빌드, ES 모듈, 정적 배포. 응답 헤더로 보아 Vercel 서울 리전이다
- **Three.js** WebGL2. `WebGLRenderer`, `InstancedMesh`, `Points`, `ShaderMaterial`,
  `BufferGeometry` 가 번들에 있다
- **React**
- **Web Worker + OffscreenCanvas**
- 167,122개를 다 그리지 않는다. **28,195개만 그린다.** 나머지는 계산만 하고 화면에 없다

## 필요 조건

일곱 덩어리다. 난이도와 분량 순으로 적는다.

### 1. 커넥톰 데이터 파이프라인 (가장 큼)

1억 5천만 행을 받아 거르고 묶어 바이너리로 싸는 일이다.
Traced 필터, 시냅스 5 이상 임계, 신경전달물질 예측으로 부호 정하기, 뉴런을 그룹 순으로 재정렬,
CSR 재매핑, gzip, SHA256. **여기가 전체 작업의 절반 이상**으로 보인다.

필요한 것은 대용량 테이블 처리(pandas 나 polars 또는 DuckDB), 희소행렬(scipy.sparse),
그리고 커넥톰 데이터 구조에 대한 이해다.

### 2. LIF 시뮬레이터

신경과학 모델 자체는 교과서 수준이라 어렵지 않다. 어려운 것은 **브라우저에서 6백만 엣지를
초당 10회 훑는 것**이다. CSR, 타입드 배열, 구조체 배열 회피, 캐시 지역성, 전송 가능 객체.
수치 최적화 감각이 필요하다.

### 3. 3D 렌더링

Three.js 로 수만 개 점을 인스턴싱해 그리고 셰이더로 밝기를 칠한다.
매 틱이 아니라 프레임마다 보간한다. WebGL 셰이더를 직접 쓸 줄 알아야 한다.

### 4. 도킹 파이프라인

AutoDock Vina 를 WASM 으로 Node 에서 돌린다(Webina 또는 MolModa).
수용체 준비(PDBQT), 도킹 박스 좌표 설정, 시드와 exhaustiveness 고정, 포즈와 로그 저장.
**계산화학 지식이 필요한 자리다.** 박스를 잘못 잡으면 결과가 의미 없다.

### 5. 두 세계를 잇는 설계

도킹 점수를 어떤 뉴런에 어떤 스케일로 넣을지 정하는 일이다.
FDDD 는 미각 수용체 뉴런에 넣었다. 여기는 코드보다 **발상**이다.

### 6. 정적 배포

Vite 빌드에 CDN 이면 된다. 서버 연산이 없어 운영 비용이 거의 없다.
다만 첫 로딩 30 MB 를 어떻게 다룰지는 고민거리다.

### 7. 증거와 정직성 설계

기술은 아니지만 이 데모를 믿게 만드는 것이 이 부분이다.
manifest 에 계보와 개수와 SHA256 과 라이선스를 적고, `dynamics` 에 생리학적 검증이 아니라고
밝히고, `selectionAudit` 으로 무엇을 넣고 뺐는지 적고, 대조군을 코드에 넣고,
`notes` 에 하지 말아야 할 해석을 8항목 적었다.

**이것이 우리 프로젝트와 같은 정신이다.** 그래서 두 주제가 붙는다.

## 분량 감각

혼자 만든다면 주 단위가 아니라 **달 단위**로 보인다. 데이터 파이프라인과 엔진 최적화가
각각 독립적으로 시간을 먹는다. 상류 MIT 엔진을 받아 고친 것이 시간을 크게 줄였을 것이다.

## 활용 가능 자산

해커톤 관점에서 실용적인 판단이다.

| 자산 | 쓸 수 있나 |
|---|---|
| 도킹 결과 8건과 SHA256 | **그대로 쓴다.** 공개 정적 파일이고 재현 정보가 붙어 있다 |
| `notes` 8항목 | **그대로 쓴다.** 우리 크리틱 규칙의 뼈대다 |
| BindingDB 와 DailyMed 참조 | 그대로 쓴다 |
| 시뮬레이션 엔진 | 3일 안에 우리 쪽에 이식하는 것은 무리다. **화면 녹화나 링크로 인용**한다 |
| 커넥톰 바이너리 | 27 MB 를 우리 저장소에 넣지 않는다. 출처만 밝힌다 |
| 렌더링 | 쓰지 않는다 |

**초파리 경로는 팀원 A 가 자기 데모로 보여 주고, 우리는 그 출력을 도구로 받는 구성이 현실적이다.**
`flybrain_pose` 도구는 실시간 시뮬레이션이 아니라 **그분이 낸 결과를 조회하는 형태**로 만든다.

## 라이선스 주의

| 대상 | 라이선스 | 우리 의무 |
|---|---|---|
| MaleCNS 커넥톰 | CC BY 4.0 | **출처 표기 필수** |
| 상류 엔진 | MIT (Seth Miller, 2017) | 저작권 고지 유지 |
| FDDD 자체 | 미확인 [unverified] | 팀원 A 에게 확인 |
| Webina, MolModa | 각 저장소 표기 | 표기 |

`docs/notes/credits.md` 의 외부 자산 표에 반영한다.
