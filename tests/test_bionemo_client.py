"""bionemo_client 오프라인 테스트. 네트워크도 API 키도 쓰지 않는다.

실행: .venv/bin/python -m pytest tests/test_bionemo_client.py -q -m "not network"

검증 대상은 백오프 계산, self-throttle 계산, ATOM 추출, SHA256, 캐시, 그리고 _post 의
재시도와 202 분기다. HTTP 는 poster/getter/sleep 주입으로 대신한다.
"""

from __future__ import annotations

import email.message
import io
import json
import urllib.error

import pytest

from harness.tools import bionemo_client as bc


# --------------------------------------------------------------------------------------
# 키 없이도 import 와 단위 테스트가 통과해야 한다
# --------------------------------------------------------------------------------------
def test_api_key_missing_raises_clear_error(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(bc.NimAuthError) as exc:
        bc.api_key()
    assert "NVIDIA_API_KEY" in str(exc.value)


def test_api_key_read_at_call_time(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    headers = bc.default_headers()
    assert headers["Authorization"] == "Bearer nvapi-test"
    assert headers["Content-Type"] == "application/json"
    assert headers["NVCF-POLL-SECONDS"] == "300"


# --------------------------------------------------------------------------------------
# 백오프와 self-throttle
# --------------------------------------------------------------------------------------
def test_backoff_is_exponential_and_capped():
    assert bc.backoff_delay(0) == 10.0
    assert bc.backoff_delay(1) == 20.0
    assert bc.backoff_delay(2) == 40.0
    assert bc.backoff_delay(3) == 80.0
    assert bc.backoff_delay(4) == 120.0   # 160 이 아니라 상한 120
    assert bc.backoff_delay(9) == 120.0


def test_backoff_respects_retry_after_header():
    assert bc.backoff_delay(0, "7") == 7.0
    assert bc.backoff_delay(3, 5) == 5.0            # 지수값 80 보다 헤더가 우선
    assert bc.backoff_delay(0, "999") == 120.0      # 헤더도 상한을 넘지 않는다
    assert bc.backoff_delay(1, "Wed, 25 Sep 2026 00:00:00 GMT") == 20.0  # HTTP-date 는 무시


def test_throttle_interval():
    assert bc.throttle_seconds(None, 100.0) == 0.0
    assert bc.throttle_seconds(100.0, 100.0) == pytest.approx(1.5)
    assert bc.throttle_seconds(100.0, 101.0) == pytest.approx(0.5)
    assert bc.throttle_seconds(100.0, 102.0) == 0.0
    assert bc.MIN_REQUEST_INTERVAL == 1.5


# --------------------------------------------------------------------------------------
# ATOM 추출
# --------------------------------------------------------------------------------------
PDB_SAMPLE = "\n".join([
    "HEADER    HYDROLASE                               01-JAN-00   4R6E",
    "ATOM      1  N   SER A 662      10.000  20.000  30.000  1.00 20.00           N",
    "ATOM      2  CA  SER A 662      11.000  21.000  31.000  1.00 20.00           C",
    "ANISOU    2  CA  SER A 662     1000   1000   1000      0      0      0       C",
    "ATOM      3  N   GLY B   1      12.000  22.000  32.000  1.00 20.00           N",
    "TER       4      GLY B   1",
    "HETATM    5  O   HOH A 900      13.000  23.000  33.000  1.00 30.00           O",
    "ATOM      6  N   ALA C   1      14.000  24.000  34.000  1.00 20.00           N",
    "ATOM      7  N   ALA D   1      15.000  25.000  35.000  1.00 20.00           N",
    "END",
])


def test_extract_atom_keeps_only_atom_records():
    out = bc.extract_atom_records(PDB_SAMPLE)
    lines = out.splitlines()
    assert len(lines) == 5
    assert all(line.startswith("ATOM") for line in lines)
    assert "HETATM" not in out and "ANISOU" not in out and "TER" not in out


def test_extract_atom_chain_selection():
    # 4R6E 는 체인이 A B C D 이고 FDDD 는 chain A 만 쓴다.
    assert bc.pdb_chains(PDB_SAMPLE) == ["A", "B", "C", "D"]
    only_a = bc.extract_atom_records(PDB_SAMPLE, "A")
    assert bc.count_atom_records(only_a) == 2
    assert all(line[21] == "A" for line in only_a.splitlines())
    two = bc.extract_atom_records(PDB_SAMPLE, ["C", "D"])
    assert bc.count_atom_records(two) == 2


def test_extract_atom_empty_raises():
    with pytest.raises(ValueError) as exc:
        bc.extract_atom_records(PDB_SAMPLE, "Z")
    assert "422" in str(exc.value)
    with pytest.raises(ValueError):
        bc.extract_atom_records("HETATM    5  O   HOH A 900")


# --------------------------------------------------------------------------------------
# SHA256 과 무결성 기록
# --------------------------------------------------------------------------------------
def test_payload_sha256_is_key_order_independent():
    a = {"protein": "ATOM x", "ligand": "C1CC", "steps": 18}
    b = {"steps": 18, "ligand": "C1CC", "protein": "ATOM x"}
    assert bc.payload_sha256(a) == bc.payload_sha256(b)
    assert len(bc.payload_sha256(a)) == 64
    assert bc.payload_sha256({"steps": 18}) != bc.payload_sha256({"num_steps": 18})


def test_sha256_text_known_value():
    # 빈 문자열의 SHA256 은 고정값이라 구현이 바뀌면 바로 드러난다.
    assert bc.sha256_text("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


def test_integrity_record_shape():
    rec = bc.integrity_record({"a": 1}, {"b": 2})
    assert set(rec) == {"request_sha256", "response_sha256", "request_bytes",
                        "response_bytes", "recorded_at"}
    assert rec["request_sha256"] == bc.sha256_text('{"a":1}')
    assert rec["request_bytes"] == 7


# --------------------------------------------------------------------------------------
# _post: 성공, 재시도, 즉시 예외, 202 분기, 캐시
# --------------------------------------------------------------------------------------
def _ok(body: dict, headers: dict | None = None):
    return 200, json.dumps(body), dict(headers or {"nvcf-status": "fulfilled"})


def test_post_sync_200(monkeypatch, tmp_path):
    calls = []

    def poster(url, data, headers, timeout):
        calls.append((url, json.loads(data.decode()), timeout))
        return _ok({"status": "success", "position_confidence": [0.79]})

    resp = bc._post("/v1/biology/mit/diffdock", {"steps": 18}, 900,
                    headers={}, poster=poster, sleep=lambda s: None, use_cache=False)
    assert resp.status == 200
    assert resp.body["status"] == "success"
    assert resp.nvcf_status == "fulfilled"
    assert resp.attempts == 1
    assert resp.request_sha256 == bc.payload_sha256({"steps": 18})
    assert calls[0][0] == bc.DIFFDOCK_URL
    assert calls[0][2] == 900


def test_post_retries_429_then_succeeds():
    slept: list[float] = []
    seq = [(429, "", {"retry-after": "3"}), (503, "", {}), _ok({"status": "success"})]

    def poster(url, data, headers, timeout):
        return seq.pop(0)

    resp = bc._post(bc.DIFFDOCK_URL, {"x": 1}, 60, headers={}, poster=poster,
                    sleep=slept.append, use_cache=False, min_interval=0.0)
    assert resp.status == 200
    assert resp.attempts == 3
    assert slept == [3.0, 20.0]  # 429 는 Retry-After 3초, 그다음 5xx 는 지수 백오프 20초


def test_post_gives_up_after_max_retries():
    def poster(url, data, headers, timeout):
        return (503, "busy", {})

    with pytest.raises(bc.NimHTTPError) as exc:
        bc._post(bc.DIFFDOCK_URL, {"x": 1}, 60, headers={}, poster=poster,
                 sleep=lambda s: None, use_cache=False, max_retries=2, min_interval=0.0)
    assert exc.value.status == 503


def test_post_422_raises_immediately_without_retry():
    calls = []

    def poster(url, data, headers, timeout):
        calls.append(1)
        hdrs = email.message.Message()
        raise urllib.error.HTTPError(
            url, 422, "Unprocessable Entity", hdrs,
            io.BytesIO(b'{"error": "unknown field num_steps"}'))

    with pytest.raises(bc.NimHTTPError) as exc:
        bc._post(bc.DIFFDOCK_URL, {"num_steps": 18}, 60, headers={}, poster=poster,
                 sleep=lambda s: None, use_cache=False, min_interval=0.0)
    assert exc.value.status == 422
    assert "num_steps" in exc.value.body
    assert len(calls) == 1  # 422 는 재시도하지 않는다


def test_post_202_polls_status_endpoint():
    def poster(url, data, headers, timeout):
        return 202, "", {"nvcf-reqid": "3b6e93b3-d0e1-4edd-9581-aeff11686a34"}

    polled: list[str] = []
    replies = [(202, "", {}), _ok({"status": "success", "ligand_positions": ["sdf"]})]

    def getter(url, headers, timeout):
        polled.append(url)
        return replies.pop(0)

    slept: list[float] = []
    resp = bc._post(bc.DIFFDOCK_URL, {"x": 1}, 60, headers={}, poster=poster, getter=getter,
                    sleep=slept.append, use_cache=False, min_interval=0.0)
    assert resp.status == 200
    assert resp.body["ligand_positions"] == ["sdf"]
    assert polled == [
        "https://health.api.nvidia.com/v1/status/3b6e93b3-d0e1-4edd-9581-aeff11686a34"] * 2
    assert slept == [bc.STATUS_POLL_INTERVAL]


def test_post_202_without_reqid_raises():
    def poster(url, data, headers, timeout):
        return 202, "", {}

    with pytest.raises(bc.NimError) as exc:
        bc._post(bc.DIFFDOCK_URL, {"x": 1}, 60, headers={}, poster=poster,
                 sleep=lambda s: None, use_cache=False, min_interval=0.0)
    assert "nvcf-reqid" in str(exc.value)


def test_post_cache_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("PHARMASIGNAL_CACHE_DIR", str(tmp_path))
    calls = []

    def poster(url, data, headers, timeout):
        calls.append(1)
        return _ok({"status": "success", "position_confidence": [0.7979534864425659]})

    payload = {"protein": "ATOM x", "steps": 18}
    first = bc._post(bc.DIFFDOCK_URL, payload, 60, headers={}, poster=poster,
                     sleep=lambda s: None, cache_source="bionemo_diffdock", min_interval=0.0)
    second = bc._post(bc.DIFFDOCK_URL, payload, 60, headers={}, poster=poster,
                      sleep=lambda s: None, cache_source="bionemo_diffdock", min_interval=0.0)
    assert len(calls) == 1              # 두 번째는 네트워크를 타지 않는다
    assert second.from_cache is True
    assert second.body == first.body
    assert second.request_sha256 == first.request_sha256
    assert second.response_sha256 == first.response_sha256
    files = list(tmp_path.glob("pharmasignal_cache_bionemo_diffdock_*.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text(encoding="utf-8"))
    assert saved["responses"][f"{bc.DIFFDOCK_URL}#{first.request_sha256}"]["body"] == first.body


def test_post_non_json_body_raises():
    def poster(url, data, headers, timeout):
        return 200, "<html>gateway</html>", {}

    with pytest.raises(bc.NimError) as exc:
        bc._post(bc.DIFFDOCK_URL, {"x": 1}, 60, headers={}, poster=poster,
                 sleep=lambda s: None, use_cache=False, min_interval=0.0)
    assert "JSON" in str(exc.value)


def test_post_json_is_the_public_alias():
    assert bc.post_json is bc._post
