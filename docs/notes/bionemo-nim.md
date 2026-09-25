# NVIDIA 생물학 NIM 접근과 호출 규격

2026-09-25 조사. 신약개발 주제로 갈 때 쓸 NVIDIA 도킹과 구조 예측 NIM을 정리했다.
실측한 것과 문서에서만 확인한 것을 구분해 적는다.

## 왜 중요한가

심사 첫 항목이 "NVIDIA Agent 기술 활용 심도"다. PharmaSignal은 NVIDIA 기술이 Nemotron과
NeMo Agent Toolkit과 OpenShell 셋이다. 신약개발로 가면 DiffDock, Boltz-2, GenMol, MSA-Search가
더해져 일곱이 된다. 팀원이 걱정한 "다른 회사 모델을 핵심에 두면 불리하다"는 Jev에만 해당하고,
초파리와 도킹 주제 자체는 반대 방향으로 작용한다.

## 접근 경로 실측 (2026-09-25)

`integrate.api.nvidia.com`과 호스트가 다르다. 계정 목록에는 생물학 모델이 없다.

```
GET https://integrate.api.nvidia.com/v1/models  ->  200, 모델 82개, 생물학 모델 0개
GET https://health.api.nvidia.com/v1/models     ->  404
```

생물학 NIM은 `health.api.nvidia.com/v1/biology/...`에 이름 기반 경로로 있다. 계정 키로 GET을
보내 전부 **405 Method Not Allowed**를 받았다. 경로가 존재하고 POST만 받는다는 뜻이다.

| 엔드포인트 | GET 응답 |
|---|---|
| `health.api.nvidia.com/v1/biology/mit/diffdock` | 405 |
| `health.api.nvidia.com/v1/biology/mit/boltz2/predict` | 405 |
| `health.api.nvidia.com/v1/biology/nvidia/molmim/generate` | 405 |
| `health.api.nvidia.com/v1/biology/nvidia/genmol/generate` | 405 |
| `health.api.nvidia.com/v1/biology/openfold/openfold2/predict-structure-from-msa-and-template` | 405 |
| `integrate.api.nvidia.com/v1/biology/mit/diffdock` | 404 (경로 없음) |

**POST 인가는 2026-09-25에 실측으로 확인했다. 통과했다.** 4R6E chain A(2,752 ATOM, 222KB)와
niraparib SMILES로 DiffDock을 불러 **HTTP 200, 4.1초, `Nvcf-Status: fulfilled`**를 받았다.
`position_confidence`는 `[0.798, 0.751, 0.725]`이고 포즈 3개가 SDF로 왔다.
원문 기록은 `eval/results/diffdock_smoke.txt`에 있다.

이 한 번으로 아래 네 가지가 함께 풀렸다.

1. 계정에 생물학 NIM 권한이 있다
2. 호출은 동기다. 202 폴링 분기가 필요 없었다
3. 호스팅 필드 이름은 **`steps`**다. `num_steps`가 아니다
4. 222KB 인라인 본문이 통과한다. `is_staged`나 asset 업로드가 필요 없다

`build.nvidia.com`의 생물학 목록에 올라온 모델은 alphafold2, alphafold2-multimer, openfold2,
openfold3, diffdock, proteinmpnn, rfdiffusion, genmol, molmim, evo2 계열, msa-search, boltz-2다.

## 가장 큰 위험: 계정 권한

NVIDIA 포럼에 "Public API Endpoints permission missing, biology NIM always errors
(`Nvcf-Status: errored`)" 스레드가 있다. **권한이 없으면 생물학 NIM이 전부 에러난다.**
405는 경로가 있다는 것만 알려 주고 권한을 알려 주지 않는다.

그래서 작업 순서의 맨 앞에 DiffDock 스모크 1회를 둔다. 200과 `position_confidence`를 받고
응답 헤더 `Nvcf-Status`가 `fulfilled`인지 함께 본다.

## 크레딧이 아니라 레이트리밋

전제가 바뀌었다. NVIDIA 포럼 답변에 따르면 `build.nvidia.com`은 **더 이상 크레딧 기반이 아니고**
모델별 레이트리밋으로 관리하며 그 값은 공개하지 않는다. 초과하면 429다.

따라서 관리할 것은 잔량이 아니라 호출 간격과 캐시다. 서드파티 구현이 40 RPM 기준으로 요청 간
1.5초를 둔다. NVIDIA 자체 워크플로 스크립트에도 지수 백오프와 `Retry-After` 존중이 들어 있다.
생물학 NIM의 모델별 정확한 레이트리밋은 어디에도 없다 [unverified].

## BioNeMo Agent Toolkit에 대한 오해 정정

**이름과 달리 NeMo Agent Toolkit(`nvidia-nat`) 기반이 아니다.** 저장소
`github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit`를 확인한 결과다.

- `pyproject.toml` 주석 원문이 "This repository is a catalog of agent skills, **not an installable
  Python package**"다. `[tool.uv] package = false`이고 의존성은 biotite, numpy, pyyaml 셋이다
- **`nvidia-nat` 의존성이 없고 `[project.entry-points]` 섹션 자체가 없다.** `@register_function`도,
  NAT 워크플로 YAML도, `nat`을 import하는 파일도 없다
- 실제 형식은 `nim-skills/<모델>-nim/{SKILL.md, references/*.md}`이고 SKILL.md는 YAML
  frontmatter를 가진 에이전트 스킬 문서다. 설치는 pip이 아니라
  `npx skills add NVIDIA-BioNeMo/bionemo-agent-toolkit --skill boltz2-nim`이다
- 평가 하네스도 `nat eval`이 아니라 astra-skill-eval과 Harbor다

그래서 **"BioNeMo Agent Toolkit을 NAT에 붙였다"고 쓰지 않는다.** 대신 두 가지로 정직하게 쓴다.

1. `docs/PLAN.md:17`이 이미 정리해 둔 스킬 카탈로그 활용이다. NVIDIA의 BioNeMo 에이전트 스킬을
   설치해 참조 규격으로 썼다고 적으면 사실이고 신청서의 스킬 카탈로그 항목과 맞는다
2. NIM을 우리가 직접 NAT 함수로 감쌌다고 적는다. 이쪽이 오히려 기여로 읽힌다

부수 효과가 있다. 그 저장소의 `references/api.md` 6개가 **가장 정확한 HTTP 규격 문서**다.
프레임워크 중립 순수 HTTP라 NAT 도구로 감싸는 작업이 기계적이다. 스킬 문서는 CC-BY-4.0으로
출처 표기가 필요하고 코드는 Apache-2.0이다.

관련 참고물이 하나 더 있다. `NVIDIA-BioNeMo-blueprints/generative-virtual-screening`(Apache-2.0)이
MSA-Search에서 OpenFold2, GenMol, DiffDock V2 순서로 부르는 노트북을 담고 있다.

## 호출 방식: 동기 POST

NVIDIA 예제 전부가 폴링 없이 `timeout=300`으로 한 번 부른다. 서드파티 실측 보고도 호스팅이
항상 200과 완전한 본문을 주고 응답 헤더에 `Nvcf-Status: fulfilled`가 붙는다고 한다.
같은 보고에서 `/v2/nvcf/pexec/status/{id}`는 유효한 reqid든 랜덤 UUID든 전부 404다.

202가 올 경우를 대비한 분기는 `GET https://health.api.nvidia.com/v1/status/{reqid}`로 두는
구현이 있다. 요청에 `NVCF-POLL-SECONDS` 헤더(최대 300)를 주면 서버가 그만큼 동기 대기를 시도한다.

**동기 200을 기본으로 하고 202 분기를 방어로 얹는다.** DiffDock 호스팅이 어떤 조건에서 202를
반환하는지는 어느 문서에도 없다 [unverified].

공통 헤더는 아래와 같다. 로컬 Docker NIM은 readiness 이후 Authorization을 보내면 안 된다.

```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}",
}
```

## position_confidence 는 확률이 아니라 로짓이다 (실측)

2026-09-25 케이스 시연에서 새로 관측했다. **음수 값이 나온다.**

| 경로 | 타깃 | position_confidence |
|---|---|---|
| A | PARP1 4R6E chain A | 0.761, 0.693, 0.515 |
| B | 응고인자 Xa 2P16 chain A | **-0.172, -0.205, -0.665** |

확률이면 0 아래로 내려갈 수 없다. 원 논문의 학습 방식과 맞춰 보면 설명이 된다.
confidence model 은 포즈의 RMSD 2옹스트롱 미만 여부를 라벨로 삼아 교차엔트로피로 학습된
이진 분류기이고, **출력이 시그모이드를 지나기 전의 로짓**이다. 로짓 0.761 은 확률 약 0.68,
로짓 -0.172 는 확률 약 0.46 에 해당한다. 이 해석은 학습 절차에서 추론한 것이고 NVIDIA 문서가
명시한 것은 아니다 [unverified].

**세 가지가 따라온다.**

1. **임계값을 숫자 크기로 정하면 안 된다.** 0.5 를 기준으로 삼으면 확률 기준인지 로짓 기준인지에
   따라 뜻이 완전히 달라진다
2. **음수를 "결합하지 않는다" 의 증거로 읽으면 안 된다.** 포즈가 기하학적으로 맞을 자신이 낮다는
   뜻이고 결합 여부를 판정하지 않는다. 과잉해석 규칙에 이 항목을 넣었다
3. **친화도 환산 금지 규칙이 더 강해진다.** 로짓을 친화도로 환산한다는 것은 단위도 축도 맞지 않는
   변환이다

경로 B 가 교차 도킹이라 낮게 나왔을 가능성이 있으나 확인하지 않았다 [unverified].

## DiffDock 은 호출마다 결과가 다르다 (실측)

같은 입력으로 두 번 불러 신뢰도가 달랐다. 확산모델이고 **호스팅 API 에 시드 파라미터가 없다.**

| 호출 | 입력 | position_confidence |
|---|---|---|
| 2026-09-25 스모크 | 4R6E chain A 2,752 ATOM + niraparib | 0.798, 0.751, 0.725 |
| 2026-09-25 클라이언트 | 같은 입력 (ATOM 줄 수와 바이트 일치) | 0.761, 0.693, 0.515 |

3순위 포즈에서 0.725 와 0.515 로 차이가 크다. 이것이 세 가지를 뜻한다.

**첫째, 재현성을 주장할 수 없다.** 신청서와 영상에 DiffDock 수치를 적을 때 "이 값이 나온다"
가 아니라 "이 호출에서 이 값이 나왔다" 로 적는다. 요청과 응답의 SHA256 을 함께 남겨
어느 호출의 결과인지 대조할 수 있게 한다. `bionemo_client.py` 가 그렇게 기록한다.

**둘째, 과잉해석 규칙이 하나 늘었다.** 단일 호출 결과에 재현성이나 수렴을 주장하면 반려한다.
FDDD 의 Vina 쪽에도 같은 취지의 항목이 있다. 단일 seed, exhaustiveness 4, 불확실성 분석 없음.
이쪽은 시드조차 없으므로 더 강하다. **우리가 실측으로 보인 규칙이라 발표에서 값이 크다.**

**셋째, 캐시가 필수다.** 재실행마다 값이 달라지면 문서 수치와 결과 파일이 어긋난다.
응답 캐시로 같은 입력에 같은 값을 재생한다. 캐시 적중은 0.01초이고 네트워크를 타지 않는다.

## DiffDock (우선순위 1)

```
POST https://health.api.nvidia.com/v1/biology/mit/diffdock
```

### 요청

| 필드 | 형 | 필수 | 기본 | 제한 |
|---|---|---|---|---|
| `protein` | string | 예 | | PDB 텍스트, **ATOM 레코드만** |
| `ligand` | string | 예 | | 리간드 파일 내용, 줄바꿈은 `\n` |
| `ligand_file_type` | string | 예 | | `"mol2"`, `"sdf"`, `"txt"` |
| `num_poses` | int | 아니오 | 10 | 100 이하 |
| `time_divisions` | int | 아니오 | 20 | 20 이하 |
| `steps` | int | 아니오 | 18 | 18 이하 |
| `save_trajectory` | bool | 아니오 | false | |
| `skip_gen_conformer` | bool | 아니오 | false | |
| `is_staged` | bool | 아니오 | false | |

**SMILES를 넣을 때 `ligand_file_type`은 `"smiles"`가 아니라 `"txt"`다.** base64도 파일 업로드도
아니고 인라인 평문이다. 단백질은 ATOM 라인만 남긴다.

```python
protein = "\n".join(
    line for line in Path("protein.pdb").read_text().splitlines()
    if line.startswith("ATOM")
)
```

NVIDIA 문서가 "No string-typed numeric fields"라고 못 박는다. GenMol과 반대다.

### 응답

| 필드 | 형 | 설명 |
|---|---|---|
| `status`, `details` | string | |
| `protein`, `ligand` | string | 입력 에코 |
| `ligand_positions` | list[string] | 랭크순 SDF 포즈 문자열. `[0]`이 1순위 |
| `position_confidence` | list[float] | 신뢰도. `ligand_positions`와 평행 배열 |
| `trajectory` | list[string] | `save_trajectory=true`일 때만 |

**점수는 `position_confidence` 하나뿐이다.** 별도 도킹 점수 필드가 없다. 그리고 NVIDIA 문서가
직접 이렇게 적었다.

> Do not convert confidence directly into binding affinity.

**출처를 정확히 적는다.** 이 문장은 NVIDIA NIM for DiffDock 개요 페이지가 아니라
`nim-skills/diffdock-nim/references/validation.md:31` 에 있다.
개요 페이지에서는 같은 문장을 찾지 못했다. 논문과 제출물에 인용할 때 이 경로와 접속일을 함께 밝힌다.

같은 취지를 DiffDock 개발진도 공식 저장소 FAQ 에 적었고 그쪽이 인용하기 더 좋다.
"No, DiffDock does not predict the binding affinity of the ligand to the protein. ...
it is not a direct measure of it."(github.com/gcorso/DiffDock README FAQ)

근거가 더 강한 이유는 원 논문에 있다. confidence model 은 생성된 포즈의 RMSD 가 2옹스트롱
미만인지를 라벨로 삼아 교차엔트로피로 학습된 **이진 분류기**다(Corso 등, ICLR 2023,
arXiv:2210.01776). 즉 포즈가 기하학적으로 맞을 확률이고 에너지 축이 아니다.
원문 기준으로 1위 예측이 RMSD 2옹스트롱 미만인 비율은 38퍼센트였다.

이 문장을 과잉해석 크리틱 규칙에 넣는다. NVIDIA가 스스로 금지한 추론을 우리 크리틱이 잡는다.

`422`는 잘못된 `ligand_file_type`, 잘못된 SMILES나 SDF, 또는 ATOM 레코드 없음이다.

## Boltz-2 (우선순위 2)

```
POST https://health.api.nvidia.com/v1/biology/mit/boltz2/predict
```

최상위 필수는 `polymers`(1개에서 12개)뿐이다. `ligands`는 20개까지, `recycling_steps` 1~10(기본 3),
`sampling_steps` 10~1000(기본 50), `diffusion_samples` 1~25(기본 1), `sampling_steps_affinity`
10~1000(기본 200), `diffusion_samples_affinity` 1~10(기본 5, 속도 우선이면 1)이다.
`output_format`은 mmcif만 된다.

`Polymer`는 `molecule_type`("protein", "dna", "rna")과 `sequence`(최대 4096자)가 필수다.
`Ligand`는 `ccd`와 `smiles` 중 **정확히 하나**를 준다. 둘 다 주면 에러다. `predict_affinity`는
요청당 1개만 가능하다.

**MSA 중첩 구조에서 가장 많이 실패한다. 키는 `alignment`이고 `data`가 아니다.**

```json
{
  "msa_search": {
    "a3m": {
      "alignment": ">query\nMTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPT",
      "format": "a3m",
      "rank": 0
    }
  }
}
```

NVIDIA 원문이 "Older examples that use `data` fail with HTTP 422 on the validated Boltz2 NIM"이라고
적었다.

응답에서 친화도 점수 이름은 `affinities.<ligand_id>` 아래의 `affinity_pic50`,
`affinity_pred_value`, `affinity_probability_binary`(0에서 1)다. 전부 배열이고 `[0]`이 consensus다.
구조는 `structures[i]["structure"]`에 mmCIF로 들어온다.

**`pae`와 `pde`는 항상 null이다.** 파이썬 모델에서 Optional로 잡지 않으면 파싱이 전부 실패한다.
실제로 그 때문에 요청 100퍼센트 실패 사례가 보고됐다. 알 수 없는 필드를 보내면 422이고 에러
본문은 `{"error": "<message>"}` 형태다.

## MolMIM (우선순위 3)

```
POST https://health.api.nvidia.com/v1/biology/nvidia/molmim/generate
```

**시드 SMILES 키가 `smiles`가 아니라 `smi`다.** `algorithm`은 `"CMA-ES"`나 `"none"`,
`num_molecules` 1~100(기본 10), `iterations` 1~1000(기본 10), `property_name`은 `"QED"`나
`"plogP"`, `particles` 2~1000(호스팅 기본 20), `min_similarity` 0~1(기본 0.7),
`scaled_radius` 0~2(기본 1)이다.

**응답 파싱에 주의한다.** 호스팅은 `molecules`를 **JSON 문자열로** 돌려주므로 한 번 더 파싱해야
하고 SMILES 키는 `sample`, 점수는 `score`다. 로컬은 `generated` 배열을 주기도 한다. 양쪽을
방어하라고 NVIDIA 문서가 명시한다.

호스팅에는 `/embedding`, `/hidden`, `/decode`, `/sampling`이 **없다.** 로컬 전용이다.

## GenMol (우선순위 4)

```
POST https://health.api.nvidia.com/v1/biology/nvidia/genmol/generate
```

`smiles`가 필수인데 **이름과 달리 SAFE 표기를 받고** `[*{min-max}]` 마스크 프래그먼트를 쓴다.
De novo 생성은 `smiles: "[*{20-30}]"`이다. `num_molecules` 1~1000(기본 30)이고 무효 분자가
걸러지므로 실제 출력이 더 적을 수 있다.

**`temperature`와 `noise`를 문자열로 보내야 한다.** 각각 `"0.01"`에서 `"10"`, `"0"`에서 `"2"`다.
블루프린트 노트북이 로컬에 숫자로 보내지만 NVIDIA 스킬 문서는 호스팅에서 문자열을 요구한다.
호스팅 클라이언트는 `str()`로 변환해 보낸다.

응답은 `{"status": "success", "molecules": [{"smiles": ..., "score": ...}]}`이고 실패는
`{"status": "failed", "error": ...}`다.

## MSA-Search와 OpenFold2 (우선순위 5)

```
POST https://health.api.nvidia.com/v1/biology/colabfold/msa-search/predict
POST https://health.api.nvidia.com/v1/biology/colabfold/msa-search/paired/predict
POST https://health.api.nvidia.com/v1/biology/openfold/openfold2/predict-structure-from-msa-and-template
```

MSA-Search는 `sequence`(1~4096자)가 필수다. `databases`는 1~5개이고 **대소문자를 구분한다**
(`"Uniref30_2302"`, `"colabfold_envdb_202108"`, `"all"`). `search_type`은 `"colabfold"`(민감)나
`"alphafold2"`(단일 패스), `e_value` 기본 0.0001, `max_msa_sequences` 최대 500이다.
응답은 `alignments.<db>.<format>.alignment`다. structure-templates 경로는 호스팅에 없다(404).

OpenFold2는 `sequence`가 필수이고 **호스팅 문서상 1~1000 aa**다(로컬은 2048). monomer 전용이라
OpenFold3의 `inputs`나 `molecules` 필드를 쓰면 안 된다. 응답 스키마를 NVIDIA도 미확정으로
표기했다. 블루프린트 노트북에서 확인된 형태는
`structures_in_ranked_order[i]["structure"]`인데 이는 로컬에서 확인된 것이고 호스팅 동일 여부는
미확인이다 [unverified].

## 구현 함정 요약

| 대상 | 함정 |
|---|---|
| DiffDock | 블루프린트 노트북은 `num_steps`, 공식 예제는 `steps`다. alias를 두고 422면 폴백한다 |
| DiffDock | `is_staged`의 사용법이 어느 문서에도 없다. 건드리지 않는다 |
| DiffDock | `ligand_file_type`은 SMILES일 때 `"txt"`다 |
| Boltz-2 | MSA 키는 `alignment`이고 `data`가 아니다 |
| Boltz-2 | `pae`와 `pde`는 항상 null이다. Optional로 잡는다 |
| MolMIM | 시드 키가 `smi`다. 응답 `molecules`가 JSON 문자열이고 SMILES 키는 `sample`이다 |
| GenMol | `temperature`와 `noise`를 문자열로 보낸다. `smiles`가 SAFE 표기다 |
| 공통 | 429가 실재한다. 지수 백오프와 `Retry-After` 존중, 요청 간 1.5초 |
| 공통 | NVIDIA 워크플로 스크립트 타임아웃이 900초와 1200초다. 300초는 짧을 수 있다 |
| 공통 | 요청 본문 바이트 한도를 확인하지 못했다. 큰 PDB를 인라인으로 넣으면 413이 날 수 있다 |

## 구현 순서

**프레임워크 무관 `src/harness/tools/bionemo_client.py`를 먼저 만들고 그 위에 NAT 래퍼를 얇게
얹는다.** 단일 `_post()`에 429 백오프와 202 폴링 분기와 요청 간격과 응답 캐시를 담으면 도구
여섯 개가 그것을 공유한다. `pharmasignal_common.py`(140줄)의 HTTP GET 재시도와 429 대기와
파일 캐시가 이미 같은 일을 하므로 그것을 확장하는 편이 빠르다.

NAT 1.9.0에서는 `nat.plugin_api`에서 import한다. `register_function`, `FunctionBaseConfig`,
`FunctionInfo`, `Builder`가 모두 stable public으로 분류돼 있다. entry point 그룹은
`nat.components`다. 등록 절차는 `docs/notes/nat-harness.md:244-253`에 있다.

```python
from nat.plugin_api import register_function, FunctionBaseConfig, FunctionInfo, Builder

class DiffDockConfig(FunctionBaseConfig, name="diffdock_nim"):
    base_url: str = "https://health.api.nvidia.com/v1/biology/mit/diffdock"
    num_poses: int = 10

@register_function(config_type=DiffDockConfig)
async def diffdock_nim(config: DiffDockConfig, _builder: Builder):
    async def _dock(...):
        """Protein-ligand docking via NVIDIA DiffDock NIM. ..."""
        ...
    yield FunctionInfo.from_fn(_dock, description=_dock.__doc__, converters=[...])
```

## 확인하지 못한 것

~~1. 이 계정의 생물학 NIM POST 권한~~ **확인 완료. 통과.**
~~2. DiffDock 호스팅이 `steps`인지 `num_steps`인지~~ **`steps`다.**
~~3. `is_staged` 사용법~~ **필요하지 않다. 222KB 인라인이 통과했다.**
4. `health.api`의 요청 바이트 한도. 222KB는 되고 상한은 모른다
5. DiffDock 호스팅이 202를 반환하는 조건. 4.1초 작업은 동기 200이었다
6. 생물학 NIM의 모델별 레이트리밋과 호출당 소모량
7. OpenFold2 호스팅 응답의 정확한 필드명
8. GenMol 호스팅이 숫자형 `temperature`도 받아 주는지
9. MolMIM 호스팅 `molecules`가 항상 JSON 문자열인지

## 출처

- `github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit`의 `nim-skills/*/references/api.md`,
  `SKILL.md`, `examples.md`, `pyproject.toml`
- `github.com/NVIDIA-BioNeMo-blueprints/generative-virtual-screening`의
  `src/generative-virtual-screening.ipynb`
- `docs.nvidia.com/nim/bionemo/{diffdock,boltz2}` 문서
- `docs.nvidia.com/nvcf` 개요와 Generic HTTP Function Invocation
- NVIDIA 개발자 포럼의 Public API Endpoints 권한 스레드와 크레딧 문의 스레드
- NeMo Agent Toolkit v1.9.0 문서의 Plugin System, Public Plugin API, Custom Functions
- `build.nvidia.com` 생물학 모델 목록
- 계정 키로 직접 호출한 GET 결과 (2026-09-25)
