"""configs/*.yml 이 NAT 1.9.0 스키마로 로드되는지 확인한다 (`nat validate` 와 같은 경로: nat.runtime.loader.load_config).

모델 호출은 없다. NVIDIA_API_KEY 가 없어도 ${NVIDIA_API_KEY} 는 빈 문자열로 치환되어 로드가 된다.
guardrails 설정은 nvidia-nat-security(nemoguardrails) 가 설치돼 있어야 한다.
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture(autouse=True)
def _chdir_repo_root(monkeypatch):
    # guardrails_root, dataset file_path 가 저장소 루트 기준 상대경로다.
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("NVIDIA_API_KEY", os.environ.get("NVIDIA_API_KEY", "nvapi-dummy-for-schema-load"))


def _load(path: str):
    from nat.runtime.loader import load_config
    return load_config(ROOT / path)


TOOL_NAMES = ["echo_tool", "prr_calculator", "openfda_faers", "dailymed_label",
              "pubmed_search", "diffdock_nim"]


def test_author_config_loads_with_two_nim_llms_and_five_tools():
    cfg = _load("configs/author.yml")
    assert set(cfg.llms) == {"planner", "worker"}
    assert cfg.llms["planner"].model_name == "nvidia/nemotron-3-super-120b-a12b"
    # nano(nvidia/nemotron-3-nano-30b-a3b)는 2026-09-01 종료(410)라 lightning 으로 바꿨다. docs/notes/nat-harness.md 참고.
    assert cfg.llms["worker"].model_name == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert cfg.llms["planner"].base_url == "https://integrate.api.nvidia.com/v1"
    assert set(cfg.functions) == set(TOOL_NAMES)
    # 별명과 _type 을 같게 두었다. 별명이 그대로 LLM 에게 보이는 도구 이름이 된다.
    assert {k: v.type for k, v in cfg.functions.items()} == {n: n for n in TOOL_NAMES}
    assert cfg.workflow.type == "tool_calling_agent"
    assert [str(t) for t in cfg.workflow.tool_names] == TOOL_NAMES


def test_author_config_domain_tool_settings():
    """도메인 도구의 설정값이 YAML 에서 Config 필드로 들어오는지."""
    fns = _load("configs/author.yml").functions
    assert fns["openfda_faers"].name_field == "generic" and fns["openfda_faers"].use_cache is True
    assert fns["dailymed_label"].max_labels == 1 and fns["dailymed_label"].name_type == "both"
    assert fns["pubmed_search"].retmax == 5 and fns["pubmed_search"].min_interval_seconds == 0.34
    assert fns["diffdock_nim"].num_poses == 3 and fns["diffdock_nim"].steps == 18


def test_author_system_prompt_requires_evidence_and_bans_self_computed_stats():
    prompt = _load("configs/author.yml").workflow.system_prompt
    assert "Never compute statistics yourself" in prompt
    assert "prr_calculator" in prompt
    for tool in ("openfda_faers", "dailymed_label", "pubmed_search"):
        assert tool in prompt
    assert "evidence_id" in prompt


def test_critic_config_has_no_tools_and_uses_planner():
    cfg = _load("configs/critic.yml")
    assert cfg.functions == {}
    assert cfg.workflow.type == "critic_judge"
    assert str(cfg.workflow.llm_name) == "planner"
    assert cfg.workflow.deterministic_only is False


def test_critic_deterministic_flag_from_env(monkeypatch):
    monkeypatch.setenv("CRITIC_DETERMINISTIC_ONLY", "true")
    cfg = _load("configs/critic.yml")
    assert cfg.workflow.deterministic_only is True


def test_eval_config_points_to_cases_and_custom_evaluator():
    cfg = _load("configs/eval.yml")
    ds = cfg.eval.general.dataset
    assert ds.type == "jsonl"
    assert Path(ds.file_path) == Path("eval/cases.jsonl")
    assert ds.structure.question_key == "input"
    assert ds.structure.answer_key == "expected_verdict"
    assert set(cfg.eval.evaluators) == {"critic_verdict"}
    assert cfg.eval.evaluators["critic_verdict"].type == "critic_verdict"


def test_guardrails_config_duplicates_author_tools_and_prompt():
    """author.yml 과 author_guarded.yml 은 llms/functions/tool_names/system_prompt 를 손으로 복제한다.

    동기화가 수동이라 한쪽만 고치면 가드레일 경로에서 도구가 사라진다. 여기서 대조한다.
    """
    pytest.importorskip("nemoguardrails")
    author = _load("configs/author.yml")
    guarded = _load("configs/guardrails/author_guarded.yml")
    assert set(guarded.functions) == set(author.functions)
    assert {k: v.type for k, v in guarded.functions.items()} == {k: v.type for k, v in author.functions.items()}
    assert [str(t) for t in guarded.workflow.tool_names] == [str(t) for t in author.workflow.tool_names]
    assert guarded.workflow.system_prompt == author.workflow.system_prompt
    assert {k: v.model_name for k, v in guarded.llms.items()} == {k: v.model_name for k, v in author.llms.items()}


def test_guardrails_config_loads_rails_policy():
    pytest.importorskip("nemoguardrails")
    cfg = _load("configs/guardrails/author_guarded.yml")
    mw = cfg.middleware["topic_guard"]
    assert mw.type == "guardrails"
    # 검증기가 guardrails_root 를 RailsConfig 로 읽어 guardrails 필드에 채운다.
    assert mw.guardrails is not None and mw.guardrails.colang_version == "1.0"
    assert [m.type for m in mw.guardrails.models] == ["main", "topic_control"]
    assert cfg.workflow.middleware == ["topic_guard"]
