"""과잉해석 규칙 모듈. 크리틱 3단(LLM 의미 판정)이 읽는 규칙의 단일 원본이다.

## 이 모듈이 재는 것

1단 결정 규칙은 근거 ID 의 존재를, 2단 숫자 오라클은 문면 수치와 로그의 일치를 본다.
둘 다 통과한 뒤에 남는 것이 **근거가 전부 맞을 때의 추론 타당성**이다. 도킹 도구의 출력에는
문서화된 해석 한계가 있고, 그 한계를 넘는 문장은 근거 ID 가 붙고 숫자가 맞아도 틀린다.
이 모듈의 규칙이 그 경계를 적는다.

## 규칙 수

- `TABLE_RULE_IDS` 14종은 `docs/notes/topic-decision.md` 의 규칙 표를 그대로 옮긴 것이다.
- 여기에 `evidence_scope` 1종을 더해 `RULES` 는 15종이다. 이 규칙은 표에 적히기 전부터
  `case_runner` 3단 프롬프트가 쓰고 있었고, 출처도 FDDD 원문과 약물감시 규율에 있다.

## 출처

지어내지 않는다. `SOURCES` 의 셋 중 하나이고, 원문이나 경로를 `source_quote` 에 남긴다.

| 출처 | 원본 |
|---|---|
| FDDD notes 원문 | `drug.flybrain.kr/data/docking/multi-target.json` 의 `notes` 8항목. 사본은 `eval/results/case_niraparib.json` 의 `fddd_notes` |
| NVIDIA DiffDock 문서 | `nim-skills/diffdock-nim/references/validation.md:31` 의 "Do not convert confidence directly into binding affinity." 인용 경위는 `docs/notes/bionemo-nim.md:205-215` |
| 기존 약물감시 규율 | 불균형 지표를 인과로 말하지 않는다. PharmaSignal 케이스 3건이 따르던 규율 |

## 강도

`strength` 는 `docs/notes/paper-plan.md` 의 "규칙별 문헌 뒷받침 강도" 표를 따른다. 그 표가 등급을
매긴 것은 5줄이고, 나머지는 **등급 미정**으로 둔다. 등급을 임의로 채우지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------------------
# 출처와 강도의 허용 값
# --------------------------------------------------------------------------------------
SOURCE_FDDD = "FDDD notes 원문"
SOURCE_NVIDIA = "NVIDIA DiffDock 문서 (nim-skills/diffdock-nim/references/validation.md:31)"
SOURCE_PV = "기존 약물감시 규율"

SOURCES: tuple[str, ...] = (SOURCE_FDDD, SOURCE_NVIDIA, SOURCE_PV)

STRENGTH_VERY_STRONG = "매우 강함"
STRENGTH_STRONG = "강함"
STRENGTH_MEDIUM = "중간"
STRENGTH_WEAK = "약함"
STRENGTH_UNGRADED = "등급 미정"

STRENGTHS: tuple[str, ...] = (STRENGTH_VERY_STRONG, STRENGTH_STRONG, STRENGTH_MEDIUM,
                              STRENGTH_WEAK, STRENGTH_UNGRADED)


@dataclass(frozen=True)
class Rule:
    """과잉해석 규칙 하나.

    - ``id``: 짧은 식별자. 3단 판정의 check 이름과 케이스 id 접두사로 쓴다
    - ``name``: 한국어 규칙 이름. `docs/notes/topic-decision.md` 표의 이름을 따른다
    - ``reject_when``: LLM 이 읽고 판단할 반려 조건. "주의하라" 가 아니라 무엇을 하면
      반려인지 구체적으로 적는다
    - ``source``: `SOURCES` 중 하나
    - ``source_quote``: 그 출처의 원문 인용 또는 경로
    - ``strength``: `STRENGTHS` 중 하나. `docs/notes/paper-plan.md` 표를 따른다
    - ``strength_note``: 등급의 근거나 유보 사항
    """

    id: str
    name: str
    reject_when: str
    source: str
    source_quote: str
    strength: str
    strength_note: str = ""

    def prompt_line(self) -> str:
        """3단 프롬프트에 실리는 한 줄. `이름. 반려 조건` 형식이다."""
        return f"{self.name}. {self.reject_when}"


# --------------------------------------------------------------------------------------
# 규칙 15종
# --------------------------------------------------------------------------------------
RULES: tuple[Rule, ...] = (
    Rule(
        id="cross_target_ranking",
        name="교차 타깃 순위 금지",
        reject_when=(
            "서로 다른 targetId 에서 나온 Vina 점수를 견주어 선택성, 상대적 결합 세기, 타깃 우선순위, "
            "Kd, Ki, IC50, EC50, 효능을 추론하면 반려한다. 점수차(예: 2.211 kcal/mol)를 결합 세기 차이로 "
            "옮기는 것도 같다."),
        source=SOURCE_FDDD,
        source_quote=("\"Raw Vina scores from different targets are NOT calibrated cross-target affinities. "
                      "Do not globally rank targets or infer selectivity, Kd, Ki, IC50, efficacy, or fly response.\""),
        strength=STRENGTH_STRONG,
        strength_note="paper-plan.md 표 \"교차 타깃 점수 비교로 선택성 주장\" 행. 1차 근거는 Warren 등 [2].",
    ),
    Rule(
        id="affinity_conversion",
        name="친화도 환산 금지",
        reject_when=(
            "Vina 점수(kcal/mol)나 DiffDock position_confidence 에서 Kd, Ki, IC50, EC50, 나노몰 수준 같은 "
            "실험 친화도나 효능을 환산하면 반려한다."),
        source=SOURCE_FDDD,
        source_quote=("FDDD notes: \"Do not globally rank targets or infer selectivity, Kd, Ki, IC50, efficacy\". "
                      "DiffDock 쪽 금지 문장은 diffdock_confidence_affinity 규칙에 따로 적었다."),
        strength=STRENGTH_UNGRADED,
        strength_note="confidence 환산 부분은 diffdock_confidence_affinity 에서 매우 강함으로 등급이 붙어 있다.",
    ),
    Rule(
        id="cross_docking_binding",
        name="교차 도킹 해석 금지",
        reject_when=(
            "role 이 \"Exploratory cross-docking; no claim of validated binding\" 인 조합(niraparib 대 "
            "응고인자 Xa 2P16, niraparib 대 COX-2 3LN1)의 점수를 실험으로 확인된 결합, 오프타깃 작용, "
            "병용 주의나 임상 주의사항으로 말하면 반려한다."),
        source=SOURCE_FDDD,
        source_quote=("\"Niraparib on factor Xa and COX-2 is exploratory computational cross-docking, "
                      "not evidence of experimentally confirmed binding.\""),
        strength=STRENGTH_WEAK,
        strength_note=("paper-plan.md 표 \"교차 도킹을 실험 확인 결합으로 서술\" 행이 약함, 보강 필요로 적혀 있다. "
                       "자가 도킹 대비 교차 도킹 성공률 하락의 1차 수치를 확보하지 못했다."),
    ),
    Rule(
        id="species_mismatch",
        name="종 차이 명시",
        reject_when=(
            "생쥐 COX-2 구조(PDB 3LN1)에서 나온 결과를 사람 COX-2 결과로 말하거나, 종을 밝히지 않고 "
            "사람에서의 함의로 옮기면 반려한다."),
        source=SOURCE_FDDD,
        source_quote=("\"These are three DIFFERENT proteins, not three PARP1 structures. "
                      "COX-2 structure 3LN1 is mouse, not human.\""),
        strength=STRENGTH_UNGRADED,
        strength_note="paper-plan.md 표에 행이 없다. 출처 원문이 종을 단정하므로 사실 확인은 명확하다.",
    ),
    Rule(
        id="convergence_claim",
        name="수렴 주장 금지",
        reject_when=(
            "단일 seed 20260914, exhaustiveness 4, num_modes 5 로 한 번 돌린 Vina 결과에 수렴, 재현성, "
            "\"다시 돌려도 같다\" 를 말하면 반려한다. FDDD 가 불확실성과 수렴 분석을 하지 않았다."),
        source=SOURCE_FDDD,
        source_quote=("\"Rigid published prepared receptors and ligands reused without local protonation changes. "
                      "Single seed, exhaustiveness 4, no uncertainty/convergence analysis.\""),
        strength=STRENGTH_MEDIUM,
        strength_note=("paper-plan.md 표 \"시드 없는 단일 호출에 재현성 주장\" 행(중간)이 Vina FAQ 와 우리 실측을 "
                       "근거로 든다. 그 행은 diffdock_reproducibility 와 함께 걸린다."),
    ),
    Rule(
        id="rmsd_reference",
        name="RMSD 기준 명시",
        reject_when=(
            "FDDD 포즈 표의 rmsdLowerBoundFromBest, rmsdUpperBoundFromBest 를 결정 구조의 리간드 포즈와의 "
            "일치로 말하면 반려한다. 그 값은 같은 실행 안의 1순위 포즈를 기준으로 잰 것이다."),
        source=SOURCE_FDDD,
        source_quote="\"Pose RMSD columns compare poses within each run, NOT to crystallographic ligand poses.\"",
        strength=STRENGTH_UNGRADED,
        strength_note="paper-plan.md 표에 행이 없다. 출처가 열의 정의를 직접 적고 있다.",
    ),
    Rule(
        id="endpoint_merge",
        name="종점 혼합 규칙",
        reject_when=(
            "BindingDB 참조 집합의 Ki 1,194건, IC50 5,588건, Kd 214건, EC50 315건을 보정과 불확실성 표기 "
            "없이 7,311건의 단일 친화도 근거로 합치면 반려한다. 종점을 나누어 적거나 보정과 불확실성을 "
            "함께 밝히면 반려하지 않는다."),
        source=SOURCE_FDDD,
        source_quote=("FDDD evidence/summary.json 의 BindingDB 블록이 종점별 건수를 나누어 싣는다. "
                      "문헌상 대규모 활용에서는 혼합이 수용되므로 금지가 아니라 표기 조건으로 좁혔다."),
        strength=STRENGTH_MEDIUM,
        strength_note=("paper-plan.md 표 \"종점 단일 병합\" 행. 1차 근거는 Kalliokoski 등 [6] 이고 방향이 일부 "
                       "반대라 문구를 수정했다."),
    ),
    Rule(
        id="executed_input",
        name="입력 동일성",
        reject_when=(
            "SMILES 를 실행된 입력이라고 말하면 반려한다. 실행 입력은 준비된 PDBQT 파일"
            "(/data/docking/inputs/4R6E_ligand_niraparib.pdbqt)이고 연결성 SMILES 는 입체화학을 빠뜨릴 수 있다. "
            "실행 입력이 준비된 PDBQT 라고 밝힌 문장은 규칙을 지킨 것이므로 반려하지 않는다."),
        source=SOURCE_FDDD,
        source_quote=("\"SMILES are molecular identity metadata, not the executed input. Connectivity SMILES can "
                      "omit stereochemistry; preserved prepared PDBQT files define the exact executed structures.\""),
        strength=STRENGTH_UNGRADED,
        strength_note="paper-plan.md 표에 행이 없다. 출처가 실행 입력을 명시한다.",
    ),
    Rule(
        id="fly_response",
        name="초파리 결과 해석",
        reject_when=(
            "도킹 점수나 초파리 커넥톰 포즈 탐색 결과를 초파리나 사람의 반응, 효능, 약효의 근거로 말하면 "
            "반려한다. 포즈 탐색이 성공한 것은 기하학적 배치일 뿐이다."),
        source=SOURCE_FDDD,
        source_quote=("\"Do not globally rank targets or infer selectivity, Kd, Ki, IC50, efficacy, or fly response.\" "
                      "금지 목록의 마지막 항목이 fly response 다."),
        strength=STRENGTH_UNGRADED,
        strength_note="paper-plan.md 표에 행이 없다. 초파리 경로 자체가 아직 실행 결과로 뒷받침되지 않았다.",
    ),
    Rule(
        id="diffdock_confidence_affinity",
        name="DiffDock 신뢰도 환산 금지",
        reject_when=(
            "position_confidence(경로 A 의 0.761, 0.693, 0.515 등)를 결합 친화도로 환산하거나 친화도의 "
            "뒷받침으로 쓰면 반려한다. 그 값은 포즈 RMSD 2옹스트롱 미만 여부를 라벨로 학습한 이진 분류기의 "
            "출력이다."),
        source=SOURCE_NVIDIA,
        source_quote="\"Do not convert confidence directly into binding affinity.\"",
        strength=STRENGTH_VERY_STRONG,
        strength_note=("paper-plan.md 표 \"confidence 를 친화도로 환산\" 행. DiffDock 원문 [4], FAQ [5], "
                       "NVIDIA 문서가 함께 받친다."),
    ),
    Rule(
        id="cross_tool_scale",
        name="도구 간 점수 혼용 금지",
        reject_when=(
            "Vina 의 kcal/mol 과 DiffDock 의 position_confidence 를 같은 척도에 두고 비교하거나, 한쪽이 "
            "다른 쪽을 수치로 확증한다고 말하면 반려한다."),
        source=SOURCE_NVIDIA,
        source_quote=("NVIDIA DiffDock 문서가 confidence 를 친화도로 바꾸지 말라고 적었고, 응답에 점수 필드는 "
                      "position_confidence 하나뿐이다(docs/notes/bionemo-nim.md:205)."),
        strength=STRENGTH_UNGRADED,
        strength_note="paper-plan.md 표에 행이 없다. 단위와 축이 다르다는 점에서 파생된 규칙이다.",
    ),
    Rule(
        id="diffdock_reproducibility",
        name="DiffDock 재현성 주장 금지",
        reject_when=(
            "시드가 없는 단일 DiffDock 호출의 position_confidence 를 재현되는 값이나 고정된 값처럼 말하면 "
            "반려한다. 같은 입력 두 번에 3순위 포즈가 0.725 와 0.515 로 갈린 것을 실측했다. "
            "\"이 호출에서 이 값이 나왔다\" 로 적으면 반려하지 않는다."),
        source=SOURCE_NVIDIA,
        source_quote=("호스팅 API 요청 스키마에 시드 필드가 없다(docs/notes/bionemo-nim.md:172-190). "
                      "호출 간 변동은 2026-09-25 실측(docs/notes/bionemo-nim.md:145-150)."),
        strength=STRENGTH_MEDIUM,
        strength_note="paper-plan.md 표 \"시드 없는 단일 호출에 재현성 주장\" 행. 우리 측정이 핵심 근거다.",
    ),
    Rule(
        id="diffdock_negative_confidence",
        name="DiffDock 음수 신뢰도 해석 금지",
        reject_when=(
            "position_confidence 가 음수인 것(경로 B 의 -0.172, -0.205, -0.665)을 결합하지 않는다는 증거나 "
            "오프타깃 배제의 근거로 읽으면 반려한다. 포즈가 기하학적으로 맞을 자신이 낮다는 뜻이고 결합 여부를 "
            "판정하지 않는다."),
        source=SOURCE_NVIDIA,
        source_quote=("음수 값은 2026-09-25 케이스 시연 실측(docs/notes/bionemo-nim.md:115-135). "
                      "로짓 해석은 학습 절차에서 추론한 것이고 NVIDIA 문서가 명시하지 않았다 [unverified]."),
        strength=STRENGTH_UNGRADED,
        strength_note="paper-plan.md 표에 행이 없다. 값의 관측은 실측이고 로짓 해석은 미확인이다.",
    ),
    Rule(
        id="disproportionality_causality",
        name="라벨 기재와 인과 구분",
        reject_when=(
            "FAERS 불균형 지표(PRR 9.13, ROR 9.55, 카이제곱 7672.29 등)를 인과 관계의 확증이나 "
            "\"약물이 이상사례를 일으킨다\" 로 말하면 반려한다. 보고가 많다는 서술, 시그널 탐지 기준(PRR>=2, a>=3, 카이제곱>=4 같은 Evans 기준) 충족 여부, 다음 확인 단계 제안은 "
            "반려하지 않는다."),
        source=SOURCE_PV,
        source_quote=("불균형 지표는 보고 편향, 적응증 교란, 노출 규모 차이를 통제하지 않는다. "
                      "eval/results/case_niraparib.json 의 cannot_say 6번 항목."),
        strength=STRENGTH_UNGRADED,
        strength_note="paper-plan.md 표에 행이 없다. 약물감시 실무에서 굳어진 규율이다.",
    ),
    Rule(
        id="evidence_scope",
        name="근거 범위 준수",
        reject_when=(
            "화합물 단위 사람 근거(DailyMed 라벨, FAERS 2x2, PubMed 문헌)를 특정 타깃 결합의 확증으로 쓰면 "
            "반려한다. 이 셋은 niraparib 이라는 화합물에 붙은 근거이고 어느 타깃에 결합하는지를 가리지 않는다. "
            "참조 친화도 집합이 없는 경로에 참조가 있다고 말하는 것도 같다."),
        source=SOURCE_FDDD,
        source_quote=("FDDD 가 응고인자 Xa 조합에 \"no claim of validated binding\" 을 적었고, 이 실행에 붙은 "
                      "참조 집합은 사람 PARP1(UniProt P09874) 하나뿐이다. "
                      "eval/results/case_niraparib.json 의 cannot_say 7번과 10번 항목."),
        strength=STRENGTH_UNGRADED,
        strength_note=("paper-plan.md 표에 행이 없다. topic-decision.md 규칙 표에도 없고, case_runner 3단 "
                       "프롬프트가 먼저 쓰고 있던 규칙이다."),
    ),
)

# `docs/notes/topic-decision.md` 규칙 표 14종. evidence_scope 는 표에 없다.
TABLE_RULE_IDS: tuple[str, ...] = (
    "cross_target_ranking", "affinity_conversion", "cross_docking_binding", "species_mismatch",
    "convergence_claim", "rmsd_reference", "endpoint_merge", "executed_input", "fly_response",
    "diffdock_confidence_affinity", "cross_tool_scale", "diffdock_reproducibility",
    "diffdock_negative_confidence", "disproportionality_causality",
)

RULES_BY_ID: dict[str, Rule] = {r.id: r for r in RULES}


def rule_ids() -> list[str]:
    """정의 순서대로의 규칙 id 목록."""
    return [r.id for r in RULES]


def get_rule(rule_id: str) -> Rule:
    """id 로 규칙 하나를 찾는다. 없으면 KeyError."""
    return RULES_BY_ID[rule_id]


def rule_lines() -> list[str]:
    """3단 프롬프트에 실을 규칙 줄 목록."""
    return [r.prompt_line() for r in RULES]


def numbered_rules_block() -> str:
    """번호를 붙인 규칙 블록."""
    return "\n".join(f"{i}. {line}" for i, line in enumerate(rule_lines(), 1))


_JSON_CONTRACT = (
    "Answer with a single JSON object and nothing else, no markdown fence and no commentary:\n"
    '{"verdict": "pass|reject|needs_human", "checks": [{"name": "...", "passed": true, '
    '"reason": "..."}], "required_followups": ["..."]}')

_JUDGE_CONTRACT = (
    "A claim that states a limit, or that explicitly declines an inference, OBEYS the rule it "
    "mentions: never reject a claim for naming the boundary it is respecting.\n"
    "Set verdict `reject` when one or more claims or the summary break a rule, `pass` when none "
    "do, and `needs_human` only when you genuinely cannot decide. Emit one check per rule you "
    "found broken, named after the rule, with the offending claim quoted in `reason`. Write every "
    "`reason` and `required_followups` entry in Korean.\n")


def stage3_prompt(*, numbers_verified: bool = True) -> str:
    """3단 과잉해석 판정 시스템 프롬프트.

    `numbers_verified=True` 는 케이스 러너 경로다. 2단 숫자 오라클이 앞에서 돌았다.
    `False` 는 `nat eval` 경로다. 그쪽은 1단 결정 규칙만 앞에 있고 숫자 오라클이 없으므로
    산술을 다시 재지 말라고만 일러 둔다.
    """
    if numbers_verified:
        intro = (
            "You are the third stage of a critic inside a drug-candidate evidence pipeline. Two earlier "
            "stages already passed: every claim carries a non-empty evidence id, and every number in the "
            "text was recomputed and matched. Do NOT re-check ids or arithmetic.\n")
    else:
        intro = (
            "You are the overclaim stage of a critic inside a drug-candidate evidence pipeline. A "
            "deterministic stage already checked that every claim carries a non-empty evidence id, and a "
            "separate numeric oracle owns the arithmetic. Do NOT re-check ids or arithmetic, and do not "
            "judge whether an evidence id looks real: treat every non-empty id as valid provenance.\n")
    return (
        intro
        + "Judge ONE thing: does any claim or the summary draw an inference that the cited evidence "
        "cannot support? Apply these rules, which come from the docking demo's own published "
        "restrictions, from the NVIDIA DiffDock documentation and from pharmacovigilance practice:\n"
        + numbered_rules_block()
        + "\n" + _JUDGE_CONTRACT
        + _JSON_CONTRACT)
