"""건별 선별 벤치마크의 계산부 테스트. 네트워크와 LLM 을 부르지 않는다.

실행: .venv/bin/python -m pytest tests/test_bench_triage_scale.py -q

여기서 보는 것은 셋이다. 요약 산식이 맞는지, 실패한 호출이 요약에서 빠지고 따로 세어지는지,
``--offline`` 이 네트워크와 LLM 없이 끝까지 돌아 산출 JSON 을 남기는지.
가짜 응답은 기존 도구가 쓰는 캐시에 직접 심어 주입한다.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from harness.tools import pharmasignal_openfda as ofda
from harness.tools.pharmasignal_common import ResponseCache

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    """스크립트는 패키지가 아니므로 파일 경로로 불러온다(test_make_figures 와 같은 방식)."""
    spec = importlib.util.spec_from_file_location(
        "bench_triage_scale", ROOT / "scripts" / "bench_triage_scale.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


bts = _load_module()

# (반응명, 이 약물에서의 보고 건수, a, n_drug, n_reaction, n_total)
# 앞의 건은 신호가 서고 뒤의 건은 서지 않는다.
SEED_EVENTS = [
    ("THROMBOCYTOPENIA", 400, 400, 1000, 20000, 1_000_000),
    ("HEADACHE", 5, 5, 1000, 200_000, 1_000_000),
]


def _seed_cache(drug: str, events, name_field: str = "generic") -> None:
    """반응 목록 응답과 건별 2x2 응답을 캐시에 심는다. 호출 전에 캐시 디렉터리를 바꿔 둔다."""
    listing = bts.count_cache(drug, name_field)
    listing.put(bts.count_url(drug, name_field),
                {"meta": {"last_updated": "20260901"},
                 "results": [{"term": t, "count": n} for t, n, *_ in events]})
    for term, _n, a, n_drug, n_reaction, n_total in events:
        cache = ResponseCache("openfda", f"{drug.strip().lower()}|{term.strip().upper()}|{name_field}")
        dc = ofda._drug_clause(drug, name_field)
        rc = ofda._reaction_clause(term)
        pairs = ((ofda._url(None), n_total), (ofda._url(dc), n_drug),
                 (ofda._url(rc), n_reaction), (ofda._url(f"{dc}+AND+{rc}"), a))
        for url, total in pairs:
            cache.put(url, {"meta": {"results": {"total": total}, "last_updated": "20260901"}})


def _row(reaction: str, *, ok: bool = True, verdict: str | None = "yes",
         rule: str | None = "yes", latency: float = 100.0,
         prompt: int | None = 200, completion: int = 20,
         error: str | None = None) -> dict:
    usage = None if prompt is None else {"prompt_tokens": prompt, "completion_tokens": completion,
                                        "total_tokens": prompt + completion}
    return {"reaction": reaction, "ok": ok, "verdict": verdict, "rule_verdict": rule,
            "latency_ms": latency, "usage": usage, "error": error}


# --------------------------------------------------------------------------------------
# 1. 요약 계산 (건수, 건당 토큰, 지연 중앙값)
# --------------------------------------------------------------------------------------

def test_summary_counts_tokens_and_median_latency():
    rows = [
        _row("A", verdict="yes", rule="yes", latency=100.0, prompt=100, completion=10),
        _row("B", verdict="no", rule="yes", latency=300.0, prompt=200, completion=20),
        _row("C", verdict="no", rule="no", latency=200.0, prompt=300, completion=30),
    ]
    s = bts.summarize(rows, price_in=1.0, price_out=2.0, wall_clock_s=1.234)

    assert s["events"] == 3 and s["ok"] == 3 and s["failed"] == 0
    assert s["tokens"] == {"prompt": 600, "completion": 60, "total": 660}
    assert s["per_event"]["total_tokens"] == pytest.approx(220.0)
    assert s["per_event"]["prompt_tokens"] == pytest.approx(200.0)
    assert s["per_event"]["completion_tokens"] == pytest.approx(20.0)
    # 지연 100, 200, 300 의 중앙값은 200, 평균도 200
    assert s["latency_ms"]["median"] == pytest.approx(200.0)
    assert s["latency_ms"]["mean"] == pytest.approx(200.0)
    assert s["latency_ms"]["min"] == 100.0 and s["latency_ms"]["max"] == 300.0
    assert s["latency_ms"]["total"] == pytest.approx(600.0)
    assert s["per_event"]["latency_ms_median"] == pytest.approx(200.0)
    # 판정 분포와 고정 규칙 일치. B 만 어긋난다
    assert s["verdicts"] == {"yes": 1, "no": 2}
    assert s["rule_agreement"] == {"match": 2, "of": 3, "rate": pytest.approx(0.6667, abs=1e-4)}
    # 비용은 입력 600 토큰과 출력 60 토큰에 단가를 곱한 값
    assert s["cost_usd"] == pytest.approx(600 / 1e6 * 1.0 + 60 / 1e6 * 2.0)
    assert s["wall_clock_s"] == pytest.approx(1.23)
    assert s["projected_estimate"]["events"] == 1000
    assert s["projected_estimate"]["total_tokens"] == 220_000


def test_summary_is_empty_but_safe_without_rows():
    s = bts.summarize([])
    assert s["events"] == 0 and s["ok"] == 0 and s["failed"] == 0
    assert s["per_event"]["total_tokens"] is None
    assert s["latency_ms"]["median"] is None
    assert s["cost_usd"] is None and s["projected_estimate"] is None
    assert s["rule_agreement"]["rate"] is None


# --------------------------------------------------------------------------------------
# 2. 실패한 호출은 요약에서 빠지고 따로 세어진다
# --------------------------------------------------------------------------------------

def test_failed_calls_are_excluded_and_counted_separately():
    rows = [
        _row("A", latency=100.0, prompt=100, completion=10),
        _row("B", latency=300.0, prompt=300, completion=30),
        _row("BOOM", ok=False, verdict=None, latency=99_000.0, prompt=9_999,
             completion=9_999, error="APITimeoutError: 503"),
    ]
    s = bts.summarize(rows)

    assert s["events"] == 3 and s["ok"] == 2 and s["failed"] == 1
    assert s["failed_reactions"] == ["BOOM"]
    # 실패 건의 지연과 토큰은 어느 집계에도 들어가지 않는다
    assert s["tokens"] == {"prompt": 400, "completion": 40, "total": 440}
    assert s["per_event"]["total_tokens"] == pytest.approx(220.0)
    assert s["latency_ms"]["max"] == 300.0
    assert s["latency_ms"]["median"] == pytest.approx(200.0)
    assert s["verdicts"] == {"yes": 2, "no": 0}
    assert s["rule_agreement"]["of"] == 2


# --------------------------------------------------------------------------------------
# 3. --offline 은 네트워크와 LLM 을 부르지 않고 끝까지 돈다
# --------------------------------------------------------------------------------------

@pytest.fixture()
def offline_run(tmp_path, monkeypatch):
    """캐시를 심고 오프라인으로 한 번 돌린 뒤 산출 JSON 을 돌려준다."""
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path / "cache"))
    _seed_cache("niraparib", SEED_EVENTS)

    def _no_network(*_args, **_kwargs):
        raise AssertionError("오프라인 경로가 네트워크를 불렀다")

    def _no_llm(*_args, **_kwargs):
        raise AssertionError("오프라인 경로가 LLM 을 불렀다")

    monkeypatch.setattr(bts, "http_get", _no_network)
    monkeypatch.setattr(ofda, "http_get", _no_network)
    monkeypatch.setattr(bts, "judge_one", _no_llm)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    out_dir = tmp_path / "out"
    code = bts.main(["--offline", "--drug", "niraparib", "--limit", "5", "--out", str(out_dir)])
    assert code == 0
    path = out_dir / "triage_scale_offline.json"
    assert path.exists()
    return json.loads(path.read_text(encoding="utf-8"))


def test_offline_runs_without_network_or_llm(offline_run):
    doc = offline_run
    assert doc["mode"] == "rule-offline"
    assert doc["model"] == "" and doc["base_url"] == ""
    assert doc["prompt"] is None
    assert [r["reaction"] for r in doc["rows"]] == ["THROMBOCYTOPENIA", "HEADACHE"]
    assert all(r["judge"] == "rule" for r in doc["rows"])
    assert all(r["usage"] is None for r in doc["rows"])
    # 심어 둔 숫자대로 앞의 건은 신호가 서고 뒤의 건은 서지 않는다
    assert doc["rows"][0]["verdict"] == "yes" and doc["rows"][0]["counts_a"] == 400
    assert doc["rows"][1]["verdict"] == "no"
    assert doc["summary"]["ok"] == 2 and doc["summary"]["failed"] == 0
    assert doc["summary"]["verdicts"] == {"yes": 1, "no": 1}
    assert doc["summary"]["rule_agreement"]["rate"] == 1.0
    assert doc["summary"]["tokens"]["total"] == 0


def test_offline_restores_the_tool_http_get_afterwards(monkeypatch):
    """with 블록을 빠져나오면 도구의 http_get 이 원래대로 돌아온다."""
    original = ofda.http_get
    with bts.cache_only_network(ofda) as stub:
        assert ofda.http_get is stub
    assert ofda.http_get is original


# --------------------------------------------------------------------------------------
# 4. 산출 JSON 의 필수 키
# --------------------------------------------------------------------------------------

DOC_KEYS = {"label", "drug", "mode", "model", "base_url", "limit", "name_field",
            "events_url", "events_total_terms", "events_errors", "prompt",
            "ran_at", "retrieved_at", "summary", "rows"}
SUMMARY_KEYS = {"events", "ok", "failed", "failed_reactions", "verdicts", "rule_agreement",
                "latency_ms", "tokens", "per_event", "cost_usd", "wall_clock_s",
                "projected_estimate"}
ROW_KEYS = {"rank", "reaction", "faers_count", "counts_a", "prr", "ror", "chi2_yates",
            "evans_signal", "ror_signal", "rule_verdict", "faers_errors", "evidence_chars",
            "ok", "error", "verdict", "reason", "latency_ms", "usage", "judge"}


def test_output_json_has_every_required_key(offline_run):
    doc = offline_run
    assert DOC_KEYS <= set(doc)
    assert SUMMARY_KEYS <= set(doc["summary"])
    assert {"prompt", "completion", "total"} <= set(doc["summary"]["tokens"])
    assert {"mean", "median", "min", "max", "total"} <= set(doc["summary"]["latency_ms"])
    assert {"prompt_tokens", "completion_tokens", "total_tokens",
            "latency_ms_mean", "latency_ms_median", "cost_usd"} <= set(doc["summary"]["per_event"])
    for row in doc["rows"]:
        assert ROW_KEYS <= set(row)


# --------------------------------------------------------------------------------------
# 목록 받기, 판정 파싱, 고정 규칙, 판정기 호출부
# --------------------------------------------------------------------------------------

def test_count_url_uses_the_existing_tool_constants():
    url = bts.count_url("Niraparib", "generic")
    assert url.startswith("https://api.fda.gov/drug/event.json?search=")
    assert 'patient.drug.openfda.generic_name:"niraparib"' in url
    assert url.endswith("&count=patient.reaction.reactionmeddrapt.exact")


def test_fetch_events_takes_the_top_n_by_count(monkeypatch):
    payload = {"meta": {}, "results": [{"term": f"PT{i}", "count": 100 - i} for i in range(20)]}
    monkeypatch.setattr(bts, "http_get", lambda url, **kw: payload)
    listing = bts.fetch_events("niraparib", limit=3, use_cache=False)
    assert [e["reaction"] for e in listing["events"]] == ["PT0", "PT1", "PT2"]
    assert [e["rank"] for e in listing["events"]] == [1, 2, 3]
    assert listing["events"][0]["faers_count"] == 100
    assert listing["total_terms"] == 20 and listing["errors"] == []


def test_fetch_events_reads_no_match_as_zero(monkeypatch):
    monkeypatch.setattr(bts, "http_get",
                        lambda url, **kw: {"__error__": 404, "body": '{"error":{"code":"NOT_FOUND"}}'})
    listing = bts.fetch_events("nosuchdrug", limit=5, use_cache=False)
    assert listing["events"] == [] and listing["errors"] == []


def test_fetch_events_records_a_cold_cache_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(bts, "http_get",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("네트워크 호출")))
    listing = bts.fetch_events("niraparib", limit=5, offline=True)
    assert listing["events"] == []
    assert listing["errors"] == ["events: http_error:offline_cache_miss"]


def test_fetch_events_rejects_a_bad_name_field():
    with pytest.raises(ValueError):
        bts.fetch_events("niraparib", limit=1, name_field="nope")


@pytest.mark.parametrize("text,expected", [
    ("VERDICT: YES\nREASON: 신호가 강하다", "yes"),
    ("VERDICT: no\nREASON: 기준 미달", "no"),
    ("verdict：YES", "yes"),
    ("VERDICT: **NO**", "no"),
    ("네, YES 입니다", "yes"),
    ("판정을 내리기 어렵다", None),
    ("", None),
])
def test_parse_verdict(text, expected):
    verdict, _reason = bts.parse_verdict(text)
    assert verdict == expected


def test_parse_verdict_keeps_the_reason_short():
    verdict, reason = bts.parse_verdict("VERDICT: YES\nREASON: " + "가" * 500)
    assert verdict == "yes" and len(reason) == 200


def test_rule_verdict_follows_the_signal_flags():
    assert bts.rule_verdict({"counts": {"a": 3}, "evans_signal": True, "ror_signal": False}) == "yes"
    assert bts.rule_verdict({"counts": {"a": 3}, "evans_signal": False, "ror_signal": True}) == "yes"
    assert bts.rule_verdict({"counts": {"a": 3}, "evans_signal": False, "ror_signal": False}) == "no"
    assert bts.rule_verdict({"counts": None}) is None


def test_rule_one_marks_a_missing_table_as_failed():
    row = bts.rule_one({"counts": None})
    assert row["ok"] is False and row["verdict"] is None and row["usage"] is None


def test_build_evidence_carries_the_numbers_only():
    faers = {"counts": {"a": 400, "b": 600, "c": 19600, "d": 979400},
             "prr": 20.39, "prr_ci95": [18.5, 22.4], "ror": 33.3, "ror_ci95": [29.0, 38.2],
             "chi2_yates": 7123.4, "evans_signal": True, "ror_signal": True}
    text = bts.build_evidence("niraparib", {"reaction": "THROMBOCYTOPENIA", "faers_count": 400}, faers)
    assert "niraparib" in text and "THROMBOCYTOPENIA" in text
    assert "a=400" in text and "d=979,400" in text
    assert "PRR: 20.39" in text and "Evans 신호: 예" in text
    # 근거는 짧게 둔다. 프롬프트가 길면 재는 대상이 흐려진다
    assert len(text.splitlines()) == 9


def test_build_evidence_says_nothing_when_the_table_is_missing():
    text = bts.build_evidence("x", {"reaction": "PT", "faers_count": None}, {"counts": None})
    assert "a=없음" in text and "PRR: 없음" in text


class _FakeUsage:
    prompt_tokens = 321
    completion_tokens = 17
    total_tokens = 338


class _FakeClient:
    """OpenAI 호환 클라이언트 자리에 끼우는 가짜. 네트워크를 쓰지 않는다."""

    def __init__(self, content: str | None = "VERDICT: YES\nREASON: 신호가 강하다",
                 raise_exc: Exception | None = None):
        self._content = content
        self._raise = raise_exc
        self.calls: list[dict] = []
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                if outer._raise is not None:
                    raise outer._raise
                message = type("M", (), {"content": outer._content})()
                choice = type("C", (), {"message": message})()
                return type("R", (), {"choices": [choice], "usage": _FakeUsage()})()

        self.chat = type("Chat", (), {"completions": _Completions()})()


def test_judge_one_records_the_verdict_and_tokens():
    client = _FakeClient()
    row = bts.judge_one(client, "some/model", "근거", timeout=5.0, max_tokens=64)
    assert row["ok"] is True and row["verdict"] == "yes"
    assert row["reason"] == "신호가 강하다"
    assert row["usage"]["total_tokens"] == 338 and row["judge"] == "llm"
    assert row["latency_ms"] >= 0
    sent = client.calls[0]
    assert sent["model"] == "some/model" and sent["max_tokens"] == 64
    assert sent["messages"][0]["content"] == bts.SYSTEM_PROMPT
    assert sent["messages"][1]["content"] == "근거"


def test_judge_one_records_an_unparsable_answer_as_failed():
    row = bts.judge_one(_FakeClient(content="잘 모르겠습니다"), "m", "근거",
                        timeout=5.0, max_tokens=64)
    assert row["ok"] is False and row["verdict"] is None
    assert "VERDICT" in row["error"] and row["usage"]["total_tokens"] == 338


def test_judge_one_records_an_exception_as_failed():
    row = bts.judge_one(_FakeClient(raise_exc=RuntimeError("503 Service Unavailable")),
                        "m", "근거", timeout=5.0, max_tokens=64)
    assert row["ok"] is False and row["verdict"] is None
    assert row["error"].startswith("RuntimeError") and row["usage"] is None


def test_run_rows_uses_the_injected_client_once_per_event(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    _seed_cache("niraparib", SEED_EVENTS)
    client = _FakeClient()
    with bts.cache_only_network(ofda):
        rows = bts.run_rows("niraparib",
                            [{"rank": 1, "reaction": t, "faers_count": n} for t, n, *_ in SEED_EVENTS],
                            client=client, model="m", progress=False)
    assert len(client.calls) == 2
    assert [r["verdict"] for r in rows] == ["yes", "yes"]
    # 고정 규칙은 뒤의 건을 흘려보낸다. 판정기와 어긋나는 자리가 기록으로 남는다
    assert [r["rule_verdict"] for r in rows] == ["yes", "no"]
    assert bts.summarize(rows)["rule_agreement"] == {"match": 1, "of": 2, "rate": 0.5}


def test_main_needs_a_key_when_it_is_not_offline(tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    code = bts.main(["--drug", "niraparib", "--limit", "1", "--out", str(tmp_path)])
    assert code == 2
