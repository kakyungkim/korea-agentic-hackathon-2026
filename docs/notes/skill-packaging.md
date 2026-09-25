# 우리 역량을 Agent Skill 로 패키징하는 법

2026-09-26 작성. 맡으실 분에게 그대로 넘기는 작업 안내다. 새 코드를 짜는 일이 아니라
**이미 있는 역량을 NVIDIA 가 쓰는 문서 규격으로 묶는 일**이다.

## 배경

해커톤이 요구하는 "Skill API" 는 별도 HTTP 엔드포인트가 아니다. `build.nvidia.com/skills` 는
**SKILL.md 형식의 에이전트 역량 카탈로그**이고 실제 계산은 NIM 이 맡는다.
`docs/PLAN.md:17` 에 이미 그렇게 적어 두었다.

지금 우리는 NVIDIA 스킬을 **참조로 쓰기만 했고 우리 역량을 스킬로 내놓지는 않았다.**
그 자리가 비어 있다.

## 규격 (추정 아님, 실물 확인)

NVIDIA 의 `bionemo-agent-toolkit` 에서 `nim-skills/diffdock-nim/SKILL.md` 를 직접 받아
확인했다. 머리말이 이렇게 생겼다.

```yaml
---
name: diffdock-nim
description: >
  Run DiffDock molecular docking via NVIDIA NIM to predict small-molecule binding poses
  against protein targets. Use for DiffDock, molecular docking, ligand docking, blind
  docking, SMILES or SDF ligands, ranked poses, confidence scores, hosted NVIDIA API,
  or local Docker deployment.
license: Apache-2.0 AND CC-BY-4.0
compatibility: "requests>=2.28"
allowed-tools: Bash, Read, Write, AskUserQuestion
---
```

`description` 이 두 가지를 한 문단에 담는다. 무엇을 하는지, 그리고 **어떤 말이 나오면 이
스킬을 꺼내야 하는지**다. 뒤쪽 키워드 나열이 트리거 역할을 한다.

본문은 짧게 쓰고 세부는 `references/` 로 미룬다. 실물의 첫 문단이 이렇다.

```markdown
# DiffDock NIM

Predict protein-ligand binding poses with blind docking. Use this `SKILL.md` for
first-pass hosted/local usage; load supplemental files only when needed:

- `references/api.md`: exact hosted/local endpoints, schemas, Docker flags.
- `references/science.md`: docking use cases, limits, and handoffs.
- `references/parameters.md`: ligand formats, pose counts, diffusion controls.
- `references/validation.md`: receptor, ligand, pose, and confidence checks.
- `references/examples.md`: compact hosted/local and pose-saving patterns.
```

설치는 pip 이 아니라 `npx skills add <owner>/<repo> --skill <이름>` 이다.

## 만들 것

`skills/pharmacovigilance-evidence/` 아래에 여섯 파일을 둔다.

| 파일 | 담을 것 | 내용을 가져올 곳 |
|---|---|---|
| `SKILL.md` | 머리말과 본문. 언제 쓰는지, 단계 순서, 한계 | `README.md`, `docs/notes/topic-decision.md` |
| `references/api.md` | openFDA, DailyMed, PubMed, BindingDB 호출 규격 | `src/harness/tools/` 의 각 도구 docstring |
| `references/evidence.md` | 근거 ID 체계와 각 ID 가 무엇을 가리키는지 | `eval/results/case_niraparib.json` |
| `references/limits.md` | 과잉해석 규칙 15종과 그 출처 | `src/harness/tools/overclaim_rules.py` |
| `references/validation.md` | 판정 전에 확인할 것. 근거 ID 유무, 숫자 대조 | `src/harness/tools/case_runner.py` 의 1단과 2단 |
| `references/examples.md` | 한 화합물을 끝까지 따라간 실제 실행 예 | `eval/results/case_niraparib_brief.md` |

전용 가드레일 정책도 함께 낸다. `policies/flydock.yaml` 을 본보기로 쓰고, 스킬이 여는
호스트만 남긴다.

## 채울 내용의 뼈대

`SKILL.md` 본문에 이 다섯 절을 둔다.

1. **언제 쓰는가.** 약물과 이상사례 쌍을 받아 사람 근거를 모아야 할 때
2. **단계.** 라벨 기재 확인, 이상사례 보고 집계와 불균형 지표, 문헌 검색, 근거 ID 부착
3. **호출 순서.** 어느 것을 먼저 부르고 무엇을 캐시하는지
4. **판정 전 확인.** 모든 주장에 근거 ID 가 붙었는지, 숫자가 원본과 맞는지
5. **하지 말 것.** 불균형 지표를 인과로 읽지 않는다, 라벨 기재 반응을 새 신호로 올리지
   않는다, 화합물 단위 근거를 특정 타깃 결합의 확증으로 쓰지 않는다

다섯 번째가 이 스킬의 값어치다. 다른 스킬은 무엇을 할 수 있는지만 적는데, 우리는
**무엇을 말하면 안 되는지를 함께 싣는다.** 규칙 15종이 그 근거이고 출처가 전부 문서에 있다.

## 지킬 것

- **없는 기능을 적지 않는다.** 스킬 문서는 에이전트가 읽고 그대로 따르는 지시다. 안 되는
  것을 적으면 에이전트가 그것을 시도한다
- **수치를 적을 때는 출처 파일을 함께 적는다.** 이 저장소의 규율이다
- **영어로 쓴다.** NVIDIA 카탈로그의 다른 스킬이 전부 영어이고 에이전트가 읽는 문서다
- **라이선스를 밝힌다.** 우리 문서는 우리 것이고, NVIDIA 스킬 문서를 인용하면 CC-BY-4.0
  출처 표기가 필요하다

## 확인하는 법

```bash
# 1. 머리말이 YAML 로 읽히는가
.venv/bin/python -c "
import sys, yaml, pathlib
t = pathlib.Path('skills/pharmacovigilance-evidence/SKILL.md').read_text()
fm = t.split('---')[1]
d = yaml.safe_load(fm)
need = {'name','description','license'}
missing = need - set(d)
print('빠진 항목:', missing or '없음')
print('description 길이:', len(d.get('description','')))
"

# 2. references 가 본문에 적은 것과 실제로 맞는가
ls skills/pharmacovigilance-evidence/references/

# 3. 본문이 가리키는 우리 파일이 실재하는가
```

## 넘기는 분께

**두세 시간 보시면 됩니다.** 새로 조사할 것이 없습니다. 위 표의 오른쪽 열에 적힌 파일을
열어 영어로 옮기고 규격에 맞춰 묶는 일입니다.

막히시면 `docs/notes/bionemo-nim.md` 에 NVIDIA 스킬 저장소 구조를 분해해 두었고,
`docs/notes/topic-decision.md` 에 규칙 15종의 출처가 정리돼 있습니다.

`configs/` 와 `src/harness/register.py` 는 팀장만 고칩니다. 이 작업은 그 둘을 건드리지
않으므로 겹치지 않습니다.
