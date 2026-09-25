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

지어내지 않는다. `source` 는 `SOURCES` 의 셋 중 하나이고, 원문이나 경로를 `source_quote` 에 남긴다.

| 출처 | 원본 |
|---|---|
| FDDD notes 원문 | `drug.flybrain.kr/data/docking/multi-target.json` 의 `notes` 8항목. 사본은 `eval/results/case_niraparib.json` 의 `fddd_notes` |
| NVIDIA DiffDock 문서 | `nim-skills/diffdock-nim/references/validation.md:31` 의 "Do not convert confidence directly into binding affinity." 인용 경위는 `docs/notes/bionemo-nim.md:205-215` |
| 기존 약물감시 규율 | 불균형 지표를 인과로 말하지 않는다. PharmaSignal 케이스 3건이 따르던 규율 |

## 문헌 이중 귀속

FDDD 는 팀원의 별도 저작물이라 팀에서 빠질 수 있다. 그런데 notes 8항목은 도킹 분야에서 널리 알려진
한계를 다시 적은 것이고 같은 내용이 동료심사 문헌에 있다. 그래서 `literature_source` 와
`literature_quote` 로 출처를 둘로 달았다. 문헌은 `docs/notes/paper-plan.md` 의 선행연구 표에 있는
것만 쓰고 `LITERATURE_SOURCES` 로 값을 제한한다. 뒷받침이 없으면 `None` 으로 두고 사유를
`strength_note` 에 적는다. 억지로 붙이지 않는다.

`FDDD_INDEPENDENT_RULE_IDS` 는 FDDD 가 빠져도 문헌이나 NVIDIA 문서로 서는 규칙 12종이다.
남은 3종(`species_mismatch`, `executed_input`, `evidence_scope`)이 FDDD 단독 의존이고,
셋 다 도구 문서 수준의 사실이라 대체 경로를 `strength_note` 에 적어 두었다.

문헌 필드는 기록용이고 **3단 프롬프트에 싣지 않는다.** `prompt_line()` 의 출력은 이 작업 전과
한 글자도 다르지 않다.

## 강도

`strength` 는 `docs/notes/paper-plan.md` 의 "규칙별 문헌 뒷받침 강도" 표를 따른다. 그 표를 15종
전부로 늘리면서 문헌 뒷받침이 없는 4종은 **없음**으로 적었다. 등급을 임의로 올리지 않는다.
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

# --------------------------------------------------------------------------------------
# 문헌 귀속의 허용 값
#
# `docs/notes/paper-plan.md` 의 선행연구 표와 그 절이 인용한 도구 공식 문서에서만 가져온다.
# 여기 없는 문헌을 `literature_source` 에 넣으면 테스트가 막는다.
# --------------------------------------------------------------------------------------
LIT_WARREN = "Warren 등 2006, J Med Chem 49(20):5912, 10.1021/jm050362n"
LIT_PANTSAR = "Pantsar와 Poso 2018, Molecules 23(8):1899, 10.3390/molecules23081899"
LIT_KALLIOKOSKI = "Kalliokoski 등 2013, PLoS ONE 8(4):e61007, 10.1371/journal.pone.0061007"
LIT_POSEBUSTERS = "PoseBusters (Buttenschoen 등) 2024, Chem Sci 15(9):3130, 10.1039/d3sc04185a"
LIT_WIERBOWSKI = "Wierbowski 등 2020, Protein Sci 29(1):298, 10.1002/pro.3784"
LIT_CORSO = "Corso 등 2023, DiffDock, ICLR, arXiv:2210.01776"
LIT_DIFFDOCK_FAQ = "DiffDock 공식 저장소 FAQ (github.com/gcorso/DiffDock, 접속 2026-09-25)"
LIT_VINA_FAQ = "AutoDock Vina 공식 FAQ (접속 2026-09-25)"
LIT_OPIG = ("Oxford Protein Informatics Group 블로그 2026-09 "
            "(blopig.com/blog/2026/09/finally-solving-drug-discovery-with-a-fly/)")

LITERATURE_SOURCES: tuple[str, ...] = (
    LIT_WARREN, LIT_PANTSAR, LIT_KALLIOKOSKI, LIT_POSEBUSTERS, LIT_WIERBOWSKI,
    LIT_CORSO, LIT_DIFFDOCK_FAQ, LIT_VINA_FAQ, LIT_OPIG,
)

# 한 규칙에 문헌이 둘 이상 붙을 때의 구분자. 테스트가 이 기준으로 쪼개어 값을 검사한다.
LITERATURE_JOIN = " + "

STRENGTH_VERY_STRONG = "매우 강함"
STRENGTH_STRONG = "강함"
STRENGTH_MEDIUM = "중간"
STRENGTH_WEAK = "약함"
STRENGTH_NONE = "없음"
# 15종 전부에 등급이 붙어 더 쓰이지 않는다. 새 규칙이 들어올 자리로 남겨 둔다.
STRENGTH_UNGRADED = "등급 미정"

STRENGTHS: tuple[str, ...] = (STRENGTH_VERY_STRONG, STRENGTH_STRONG, STRENGTH_MEDIUM,
                              STRENGTH_WEAK, STRENGTH_NONE, STRENGTH_UNGRADED)


@dataclass(frozen=True)
class Rule:
    """과잉해석 규칙 하나.

    - ``id``: 짧은 식별자. 3단 판정의 check 이름과 케이스 id 접두사로 쓴다
    - ``name``: 한국어 규칙 이름. `docs/notes/topic-decision.md` 표의 이름을 따른다
    - ``reject_when``: LLM 이 읽고 판단할 반려 조건. "주의하라" 가 아니라 무엇을 하면
      반려인지 구체적으로 적는다
    - ``source``: `SOURCES` 중 하나
    - ``source_quote``: 그 출처의 원문 인용 또는 경로
    - ``literature_source``: 문헌 귀속. `LITERATURE_SOURCES` 의 값이고 둘 이상이면
      `LITERATURE_JOIN` 으로 잇는다. 뒷받침하는 문헌이 없으면 `None`
    - ``literature_quote``: 그 문헌의 원문 인용 한 문장 또는 확인한 내용. 문헌이 없으면 `None`
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
    literature_source: str | None = None
    literature_quote: str | None = None

    def stands_without_fddd(self) -> bool:
        """FDDD 가 빠져도 이 규칙이 서는가. 문헌이 있거나 출처가 FDDD 가 아니면 선다."""
        return self.source != SOURCE_FDDD or self.literature_source is not None

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
        strength_note=("paper-plan.md \"규칙별 문헌 뒷받침 강도\" 표. 1차 근거가 Warren 등 [2] 이라 FDDD 가 빠져도 "
                       "문헌만으로 선다."),
        literature_source=LIT_WARREN,
        literature_quote=("\"For prediction of compound affinity, none of the docking programs or scoring functions "
                          "made a useful prediction of ligand binding affinity\". 도킹 10종과 scoring function 37종을 "
                          "8개 단백질에서 평가한 결과이고, 최대 상관은 Chk1 의 한 계열에서 r = -0.57 이며 같은 표적의 "
                          "다른 계열에서는 r = 0.0 이었다."),
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
        strength=STRENGTH_STRONG,
        strength_note=("문헌 두 편이 직접 받친다. Pantsar와 Poso [3] 가 부적합을 명시하고 Warren 등 [2] 이 수치로 "
                       "보였다. confidence 환산 쪽은 diffdock_confidence_affinity 에서 매우 강함으로 따로 등급이 "
                       "붙어 있다."),
        literature_source=LIT_PANTSAR + LITERATURE_JOIN + LIT_WARREN,
        literature_quote=("Pantsar와 Poso: 도킹이 친화도 추정에 맞는 도구인지 물은 뒤 \"The short answer is no, and "
                          "this has been concluded in several comprehensive analyses\" 라고 적었다. Warren 등도 "
                          "8개 표적에서 쓸 만한 친화도 예측이 없었다고 보고했다."),
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
                       "문헌 귀속을 달았으나 Wierbowski 등의 본문을 읽지 못해 수치가 미확인이다 [unverified]."),
        literature_source=LIT_WIERBOWSKI + LITERATURE_JOIN + LIT_POSEBUSTERS,
        literature_quote=("교차 도킹 벤치마크 문헌이다. **본문 접근이 막혀 자가 도킹 대비 성공률 하락 수치를 확인하지 "
                          "못했다 [unverified].** 포즈 타당성 기준 쪽은 PoseBusters [1] 가 받친다."),
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
        strength=STRENGTH_NONE,
        strength_note=("문헌 뒷받침 없음. 구조 항목 수준의 사실이라 문헌을 억지로 붙이지 않았다. FDDD 원문이 종을 "
                       "단정하므로 확인은 명확하고, FDDD 가 빠지면 PDB 3LN1 항목의 생물종 필드로 직접 확인한다."),
        literature_source=None,
        literature_quote=None,
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
        literature_source=LIT_VINA_FAQ,
        literature_quote=("AutoDock Vina 공식 FAQ 가 같은 시드를 줘야 같은 결과가 나온다고 조건을 밝혀 두었다"
                          "(paper-plan.md \"빈 자리\" 5번). **FAQ 원문 문장을 직접 대조하지 못했다 [unverified].** "
                          "호출 간 변동은 우리 실측이 받친다."),
    ),
    Rule(
        id="rmsd_reference",
        name="RMSD 기준 명시",
        reject_when=(
            "FDDD 포즈 표의 rmsdLowerBoundFromBest, rmsdUpperBoundFromBest 를 결정 구조의 리간드 포즈와의 "
            "일치로 말하면 반려한다. 그 값은 같은 실행 안의 1순위 포즈를 기준으로 잰 것이다."),
        source=SOURCE_FDDD,
        source_quote="\"Pose RMSD columns compare poses within each run, NOT to crystallographic ligand poses.\"",
        strength=STRENGTH_MEDIUM,
        strength_note=("문헌이 RMSD 의 기준을 결정 구조로 정해 두었고, FDDD 열이 같은 실행 안의 1순위 포즈를 기준으로 "
                       "삼는다는 사실은 데모 원문에서 온다. 기준은 문헌, 열 정의는 도구 쪽이라 중간으로 둔다. "
                       "PoseBusters 를 점수 해석 한계 문헌으로 인용하면 안 된다(원문에 그 논의가 없다)."),
        literature_source=LIT_POSEBUSTERS,
        literature_quote=("PoseBusters 는 포즈 타당성을 물리적 타당성과 결정 구조 리간드 대비 RMSD 2옹스트롱 미만을 "
                          "동시에 만족하는지로 판정한다. 결론 문장은 \"no DL-based method yet outperforms standard "
                          "docking methods when both physical plausibility and binding mode RMSD is taken into "
                          "account\" 다. RMSD 의 기준은 결정 구조이고 같은 실행 안의 다른 포즈가 아니다."),
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
                       "반대라 규칙 문구를 금지에서 표기 조건으로 좁혔다."),
        literature_source=LIT_KALLIOKOSKI,
        literature_quote=("서로 다른 assay 의 IC50 을 섞으면 표준편차가 0.68 log 단위(선형으로 약 4.8배)이고 같은 "
                          "실험실 반복 측정은 0.22 와 0.17 이었다. 다만 대규모 활용에서는 혼합이 수용되고 pKi 는 "
                          "offset 보정으로 pIC50 을 보강할 수 있다고 보고되었으므로, 이 문헌은 금지가 아니라 보정과 "
                          "불확실성 표기를 요구하는 근거다."),
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
        strength=STRENGTH_NONE,
        strength_note=("문헌 뒷받침 없음. 도구 문서 수준이다. 연결성 SMILES 가 입체화학을 빠뜨릴 수 있다는 것과 실행 "
                       "입력이 준비된 PDBQT 라는 것은 FDDD 원문과 AutoDock 입력 규격에서 온다. FDDD 가 빠지면 "
                       "우리 실행 기록의 입력 파일과 SHA256 으로 대체한다."),
        literature_source=None,
        literature_quote=None,
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
        strength=STRENGTH_WEAK,
        strength_note=("동료심사 문헌이 아니라 Oxford Protein Informatics Group 블로그 논평이라 약함으로 둔다. "
                       "초파리 경로 자체도 아직 우리 실행 결과로 뒷받침되지 않았다."),
        literature_source=LIT_OPIG,
        literature_quote=("\"have we finally solved drug discovery with a fly? Obviously not\". 같은 글이 학습되지 "
                          "않은 죽은 초파리의 뇌이고 하행 뉴런의 감각 의존 활동이 전체의 약 0.1퍼센트에 그친다고 "
                          "적었다(docs/notes/fddd-and-jev.md 의 도킹 논평 절)."),
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
        strength_note=("paper-plan.md 표 \"confidence 를 친화도로 환산\" 행. DiffDock 원문 [4], 저장소 FAQ [5], "
                       "NVIDIA 문서가 함께 받쳐 FDDD 와 무관하게 선다."),
        literature_source=LIT_CORSO + LITERATURE_JOIN + LIT_DIFFDOCK_FAQ,
        literature_quote=("저장소 FAQ: \"No, DiffDock does not predict the binding affinity of the ligand to the "
                          "protein. ... it is not a direct measure of it.\" 원 논문의 confidence model 은 포즈 RMSD "
                          "2옹스트롱 미만 여부를 라벨로 삼아 교차엔트로피로 학습된 이진 분류기이고, 1위 예측이 "
                          "2옹스트롱 미만인 비율은 38퍼센트였다."),
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
        strength=STRENGTH_MEDIUM,
        strength_note=("원 논문 [4] 이 confidence 의 학습 목표를 정의하므로 단위와 축이 다르다는 결론이 문헌으로 선다. "
                       "두 도구의 점수를 직접 견준 문헌은 확인하지 못해 중간으로 둔다."),
        literature_source=LIT_CORSO,
        literature_quote=("원 논문의 confidence model 은 포즈 RMSD 2옹스트롱 미만 여부를 라벨로 학습한 이진 분류기다. "
                          "기하학적 적중 확률이고 kcal/mol 자유에너지 축이 아니므로 Vina 점수와 같은 척도에 둘 수 없다."),
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
        strength_note=("paper-plan.md 표 \"시드 없는 단일 호출에 재현성 주장\" 행. 우리 측정이 핵심 근거이고 문헌은 "
                       "생성모델이라는 성격만 받친다."),
        literature_source=LIT_CORSO,
        literature_quote=("DiffDock 은 포즈 분포에서 표본을 뽑는 확산 생성모델이라 호출마다 표본이 달라진다"
                          "(원 논문 요지, docs/notes/bionemo-nim.md:205-215). **원문 문장을 직접 대조하지 못했다 "
                          "[unverified].** 시드 필드 부재와 0.725 대 0.515 변동은 우리 실측이다."),
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
        strength=STRENGTH_MEDIUM,
        strength_note=("값의 관측은 우리 실측이고 \"결합하지 않음의 증거가 아니다\" 라는 결론은 원 논문 [4] 의 학습 "
                       "목표 정의에서 나온다. 로짓 해석이 미확인이라 중간으로 둔다."),
        literature_source=LIT_CORSO,
        literature_quote=("confidence model 이 포즈 RMSD 2옹스트롱 미만 여부만 라벨로 학습했으므로 값이 낮거나 음수인 "
                          "것은 포즈가 기하학적으로 맞을 자신이 낮다는 뜻이고 결합 여부를 판정하지 않는다. "
                          "시그모이드 이전 로짓이라는 해석은 학습 절차에서 추론한 것이다 [unverified]."),
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
        strength=STRENGTH_NONE,
        strength_note=("문헌 뒷받침 없음. paper-plan.md 선행연구 표에 약물감시 문헌이 없어 억지로 붙이지 않았다. "
                       "약물감시 실무에서 굳어진 규율이고 출처가 FDDD 가 아니라 FDDD 가 빠져도 그대로 선다."),
        literature_source=None,
        literature_quote=None,
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
        strength=STRENGTH_NONE,
        strength_note=("문헌 뒷받침 없음. 근거 범위를 지키라는 규율이라 문헌을 붙이지 않았다. topic-decision.md 규칙 "
                       "표에도 없고 case_runner 3단 프롬프트가 먼저 쓰고 있던 규칙이다. FDDD 가 빠지면 참조 집합의 "
                       "UniProt 범위를 우리 실행 기록으로 대체한다."),
        literature_source=None,
        literature_quote=None,
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

# --------------------------------------------------------------------------------------
# FDDD 가 빠져도 서는 규칙
#
# FDDD 는 팀원의 별도 저작물이다. 그 자산을 못 쓰게 되면 아래 12종은 문헌이나 NVIDIA 문서로
# 그대로 서고, 나머지 3종(`species_mismatch`, `executed_input`, `evidence_scope`)은 출처를 잃는다.
# 목록을 직접 적어 두고 테스트가 `stands_without_fddd()` 파생과 대조한다.
# --------------------------------------------------------------------------------------
FDDD_INDEPENDENT_RULE_IDS: tuple[str, ...] = (
    "cross_target_ranking", "affinity_conversion", "cross_docking_binding", "convergence_claim",
    "rmsd_reference", "endpoint_merge", "fly_response", "diffdock_confidence_affinity",
    "cross_tool_scale", "diffdock_reproducibility", "diffdock_negative_confidence",
    "disproportionality_causality",
)

FDDD_ONLY_RULE_IDS: tuple[str, ...] = tuple(
    r.id for r in RULES if not r.stands_without_fddd())


def rule_ids() -> list[str]:
    """정의 순서대로의 규칙 id 목록."""
    return [r.id for r in RULES]


def get_rule(rule_id: str) -> Rule:
    """id 로 규칙 하나를 찾는다. 없으면 KeyError."""
    return RULES_BY_ID[rule_id]


def fddd_independent_rules() -> list[Rule]:
    """FDDD 없이도 서는 규칙. 문헌 귀속이 있거나 출처가 FDDD 가 아닌 것들이다."""
    return [r for r in RULES if r.stands_without_fddd()]


def fddd_only_rules() -> list[Rule]:
    """FDDD 단독 의존 규칙. FDDD 가 빠지면 출처를 잃는다."""
    return [r for r in RULES if not r.stands_without_fddd()]


def literature_backed_rules() -> list[Rule]:
    """문헌 귀속이 붙은 규칙."""
    return [r for r in RULES if r.literature_source is not None]


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
