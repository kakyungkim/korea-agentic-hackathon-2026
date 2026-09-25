"""NVIDIA 생물학 NIM(health.api.nvidia.com) 공통 호출 계층. 프레임워크 무관 순수 파이썬.

NAT 를 import 하지 않는다. DiffDock, Boltz-2, MolMIM, GenMol, MSA-Search, OpenFold2 도구가
이 모듈 하나를 공유한다. 표준 라이브러리만 쓰고(urllib, json, hashlib) 캐시와 해시는
``pharmasignal_common`` 의 것을 재사용한다.

규격 근거
- 사양: ``docs/notes/bionemo-nim.md``
- 실측: ``eval/results/diffdock_smoke.txt`` (2026-09-25, HTTP 200, 4.1초, Nvcf-Status: fulfilled)

설계 요약
- 단일 진입점 ``_post(path, payload, timeout)`` 하나에 self-throttle, 응답 캐시, 429/5xx
  지수 백오프, 202 폴링 분기를 모두 담는다. 공개 별칭은 ``post_json`` 이다.
- 429 와 5xx(500, 502, 503, 504)만 재시도한다. 그 밖의 HTTPError(예: 422)는 즉시 올려서
  호출 측이 필드명 폴백 같은 판단을 하게 한다.
- 백오프는 NVIDIA 워크플로 스크립트와 같은 값을 쓴다. 재시도 5회, 기본 10초, 상한 120초.
  ``Retry-After`` 헤더가 오면 그 값을 우선한다.
- 요청 간 최소 간격 1.5초를 둔다(서드파티 구현의 40 RPM 기준). 레이트리밋 값은 비공개다.
- 기본 경로는 동기 200 이다. 202 는 어떤 조건에서 오는지 문서에 없어 방어로만 둔다 [unverified].
- ``NVIDIA_API_KEY`` 는 import 시점이 아니라 호출 시점에 읽는다. 키가 없어도 import 와
  오프라인 단위 테스트가 통과해야 한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    from .pharmasignal_common import ResponseCache, now_iso
except ImportError:  # 스크립트/테스트에서 sys.path 로 직접 임포트할 때
    from pharmasignal_common import ResponseCache, now_iso

# --------------------------------------------------------------------------------------
# 상수. 전부 docs/notes/bionemo-nim.md 와 diffdock_smoke.txt 에서 온 값이다.
# --------------------------------------------------------------------------------------
HEALTH_BASE = "https://health.api.nvidia.com"
STATUS_PATH = "/v1/status"
DIFFDOCK_URL = f"{HEALTH_BASE}/v1/biology/mit/diffdock"

DEFAULT_TIMEOUT = 900          # NVIDIA 워크플로 스크립트가 900초와 1200초를 쓴다
POLL_SECONDS = 300             # NVCF-POLL-SECONDS 헤더 최대값
MIN_REQUEST_INTERVAL = 1.5     # 40 RPM 기준 self-throttle
MAX_RETRIES = 5
BASE_DELAY = 10.0
MAX_DELAY = 120.0
STATUS_POLL_INTERVAL = 5.0
RETRY_STATUS = (429, 500, 502, 503, 504)

USER_AGENT = "BioNeMoClient/0.1 (Korea Agentic AI Hackathon; stdlib urllib)"

# 요청 사이 간격을 재는 단일 시계. 모듈 전역이라 도구 여섯 개가 같은 간격을 공유한다.
_LAST_CALL: list[float] = []


# --------------------------------------------------------------------------------------
# 예외
# --------------------------------------------------------------------------------------
class NimError(RuntimeError):
    """생물학 NIM 호출 계층의 공통 예외."""


class NimAuthError(NimError):
    """``NVIDIA_API_KEY`` 가 없다."""


class NimHTTPError(NimError):
    """재시도 대상이 아닌 HTTP 오류. 상태코드와 응답 본문을 함께 담는다."""

    def __init__(self, status: int, body: str, url: str = "", headers: dict[str, str] | None = None):
        super().__init__(f"HTTP {status} from {url}: {body[:500]}")
        self.status = status
        self.body = body
        self.url = url
        self.headers = headers or {}


# --------------------------------------------------------------------------------------
# 인증과 헤더
# --------------------------------------------------------------------------------------
def api_key() -> str:
    """호출 시점에 ``NVIDIA_API_KEY`` 를 읽는다. 없으면 무엇을 해야 하는지 밝혀 예외를 낸다."""
    key = (os.environ.get("NVIDIA_API_KEY") or "").strip()
    if not key:
        raise NimAuthError(
            "NVIDIA_API_KEY 가 없습니다. build.nvidia.com 키를 .env 에 넣고 "
            "`set -a; source .env; set +a` 로 불러오세요. "
            "(오프라인 테스트는 이 함수를 부르지 않습니다.)"
        )
    return key


def default_headers(poll_seconds: int = POLL_SECONDS) -> dict[str, str]:
    """실측으로 통과한 헤더 세 개. 로컬 Docker NIM 에는 Authorization 을 보내지 않는다."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key()}",
        "NVCF-POLL-SECONDS": str(poll_seconds),
        "User-Agent": USER_AGENT,
    }


# --------------------------------------------------------------------------------------
# 해시와 무결성 기록. 이 프로젝트는 근거 ID 와 무결성 대조를 핵심으로 쓴다.
# --------------------------------------------------------------------------------------
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(payload: Any) -> str:
    """해시 입력용 정규화 JSON. 키 순서와 구분자를 고정해 같은 페이로드가 같은 해시를 낸다."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_sha256(payload: Any) -> str:
    """요청 페이로드의 SHA256. 근거 ID 와 캐시 키가 이 값을 쓴다."""
    return sha256_text(canonical_json(payload))


def integrity_record(payload: Any, response: Any) -> dict[str, Any]:
    """재현성 기록 한 덩어리. 요청과 응답의 SHA256, 바이트 수, 시각을 함께 남긴다."""
    req = canonical_json(payload)
    resp = response if isinstance(response, str) else canonical_json(response)
    return {
        "request_sha256": sha256_text(req),
        "response_sha256": sha256_text(resp),
        "request_bytes": len(req.encode("utf-8")),
        "response_bytes": len(resp.encode("utf-8")),
        "recorded_at": now_iso(),
    }


# --------------------------------------------------------------------------------------
# PDB 전처리. DiffDock 은 ATOM 레코드만 받는다.
# --------------------------------------------------------------------------------------
def extract_atom_records(pdb_text: str, chains: str | list[str] | None = None) -> str:
    """PDB 텍스트에서 ATOM 레코드만 남긴다. ``chains`` 를 주면 그 체인만 고른다.

    HETATM, TER, 헤더, ANISOU 는 모두 버린다. 체인 식별자는 PDB 규격의 22번째 칼럼
    (0-based 21)이다. 4R6E 는 체인이 A, B, C, D 이고 FDDD 는 chain A 만 쓴다.
    ATOM 이 하나도 남지 않으면 그대로 보내면 422 가 나므로 여기서 ValueError 를 낸다.
    """
    wanted: set[str] | None = None
    if chains is not None:
        wanted = {c.strip() for c in ([chains] if isinstance(chains, str) else chains) if c.strip()}
        if not wanted:
            wanted = None

    kept: list[str] = []
    for line in pdb_text.splitlines():
        if not line.startswith("ATOM"):
            continue
        if wanted is not None:
            chain_id = line[21] if len(line) > 21 else " "
            if chain_id.strip() not in wanted:
                continue
        kept.append(line.rstrip("\r"))

    if not kept:
        raise ValueError(
            "ATOM 레코드가 없습니다. 체인 선택이 맞는지 확인하세요"
            f"(요청 체인: {sorted(wanted) if wanted else '전체'}). "
            "ATOM 없이 보내면 DiffDock 이 422 를 돌려줍니다."
        )
    return "\n".join(kept)


def count_atom_records(protein_text: str) -> int:
    """ATOM 줄 수. 스모크 기록과 대조할 때 쓴다(4R6E chain A 는 2,752줄)."""
    return sum(1 for line in protein_text.splitlines() if line.startswith("ATOM"))


def pdb_chains(pdb_text: str) -> list[str]:
    """PDB 텍스트에 들어 있는 체인 식별자를 등장 순서대로 돌려준다."""
    seen: list[str] = []
    for line in pdb_text.splitlines():
        if line.startswith("ATOM") and len(line) > 21:
            chain_id = line[21].strip()
            if chain_id and chain_id not in seen:
                seen.append(chain_id)
    return seen


# --------------------------------------------------------------------------------------
# 레이트리밋 계산. 순수 함수로 두어 오프라인에서 검증한다.
# --------------------------------------------------------------------------------------
def backoff_delay(attempt: int, retry_after: str | float | None = None,
                  base_delay: float = BASE_DELAY, cap: float = MAX_DELAY) -> float:
    """재시도 대기 시간. ``Retry-After`` 가 오면 그 값을 쓰고, 없으면 지수 백오프를 쓴다.

    attempt 는 0부터 센다. base_delay * 2**attempt 를 cap 으로 자른다(10, 20, 40, 80, 120).
    Retry-After 는 초 단위 정수만 해석하고 HTTP-date 형식은 무시한다(값이 잘못되면 지수 백오프).
    """
    if retry_after is not None:
        try:
            seconds = float(str(retry_after).strip())
            if seconds >= 0:
                return min(cap, seconds)
        except (TypeError, ValueError):
            pass
    return min(cap, base_delay * (2 ** max(0, attempt)))


def throttle_seconds(last_call: float | None, now: float,
                     min_interval: float = MIN_REQUEST_INTERVAL) -> float:
    """직전 호출과의 간격을 채우기 위해 더 기다려야 할 초. 첫 호출이면 0 이다."""
    if last_call is None or min_interval <= 0:
        return 0.0
    return max(0.0, min_interval - (now - last_call))


# --------------------------------------------------------------------------------------
# 응답 캐시. pharmasignal_common.ResponseCache 를 그대로 쓴다.
# --------------------------------------------------------------------------------------
# 파일명은 부모 규약을 따라 ``eval/results/pharmasignal_cache_<source>_<sha1(key)[:12]>.json``
# 이 된다(source 는 bionemo_diffdock 처럼 모델 이름을 담는다). 접두어를 바꾸지 않은 이유는
# .gitignore 가 이미 ``eval/results/pharmasignal_cache_*.json`` 으로 캐시를 제외하고 있어서다.
# 도킹 응답은 단백질을 그대로 되돌려 주므로 한 건이 수백 KB 다. 저장소에 들어가면 안 된다.


@dataclass
class NimResponse:
    """NIM 한 번의 호출 결과. 본문과 헤더와 무결성 정보를 함께 담는다."""

    status: int
    body: Any
    headers: dict[str, str] = field(default_factory=dict)
    url: str = ""
    request_sha256: str = ""
    response_sha256: str = ""
    elapsed_s: float = 0.0
    attempts: int = 1
    from_cache: bool = False
    cache_path: str | None = None

    @property
    def reqid(self) -> str | None:
        return self.headers.get("nvcf-reqid")

    @property
    def nvcf_status(self) -> str | None:
        return self.headers.get("nvcf-status")


def _lower_headers(raw: Any) -> dict[str, str]:
    try:
        return {str(k).lower(): str(v) for k, v in raw.items()}
    except AttributeError:
        return {}


def _full_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{HEALTH_BASE}/{path.lstrip('/')}"


def _raw_post(url: str, data: bytes, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
    """urllib 로 POST 한 번. HTTPError 는 그대로 올린다(재시도 판단은 _post 가 한다)."""
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
        return int(getattr(resp, "status", 200) or 200), raw, _lower_headers(resp.headers)


def _raw_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
        return int(getattr(resp, "status", 200) or 200), raw, _lower_headers(resp.headers)


def _poll_status(reqid: str, headers: dict[str, str], timeout: float,
                 poll_interval: float = STATUS_POLL_INTERVAL,
                 sleep: Callable[[float], None] = time.sleep,
                 getter: Callable[..., tuple[int, str, dict[str, str]]] | None = None,
                 ) -> tuple[int, str, dict[str, str]]:
    """202 방어 분기. ``GET /v1/status/{reqid}`` 를 poll_interval 간격으로 200 이 올 때까지 부른다.

    기본 경로는 동기 200 이므로 여기까지 오는 일은 없어야 한다. DiffDock 호스팅이 202 를
    반환하는 조건은 어느 문서에도 없다 [unverified].
    """
    do_get = getter or _raw_get
    url = f"{HEALTH_BASE}{STATUS_PATH}/{reqid}"
    deadline = time.monotonic() + timeout
    last: tuple[int, str, dict[str, str]] = (202, "", {})
    while True:
        status, raw, resp_headers = do_get(url, headers, timeout)
        last = (status, raw, resp_headers)
        if status != 202:
            return last
        if time.monotonic() >= deadline:
            raise NimError(f"202 폴링이 {timeout:.0f}초 안에 끝나지 않았습니다. reqid={reqid}")
        sleep(poll_interval)


def _post(path: str, payload: Any, timeout: float = DEFAULT_TIMEOUT, *,
          cache_source: str | None = None, use_cache: bool = True,
          max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY,
          min_interval: float = MIN_REQUEST_INTERVAL, poll_seconds: int = POLL_SECONDS,
          headers: dict[str, str] | None = None,
          sleep: Callable[[float], None] = time.sleep,
          poster: Callable[..., tuple[int, str, dict[str, str]]] | None = None,
          getter: Callable[..., tuple[int, str, dict[str, str]]] | None = None,
          ) -> NimResponse:
    """생물학 NIM POST 단일 진입점. 도구 여섯 개가 이 함수만 부른다.

    순서는 캐시 조회, self-throttle, POST, 재시도 판단, 202 분기, 캐시 저장이다.
    429 와 5xx 는 backoff_delay 만큼 기다려 최대 max_retries 회 다시 부르고, 그 밖의
    HTTP 오류는 NimHTTPError 로 즉시 올린다(422 폴백 판단은 호출 측의 일이다).
    ``poster`` 와 ``getter`` 와 ``sleep`` 은 테스트에서 주입한다.
    """
    url = _full_url(path)
    req_json = canonical_json(payload)
    req_sha = sha256_text(req_json)

    cache: ResponseCache | None = None
    cache_key = f"{url}#{req_sha}"
    if cache_source and use_cache:
        cache = ResponseCache(cache_source, req_sha)
        hit = cache.get(cache_key)
        if isinstance(hit, dict) and "body" in hit:
            cache.hits += 1
            body = hit["body"]
            return NimResponse(
                status=int(hit.get("status", 200)), body=body,
                headers=_lower_headers(hit.get("headers") or {}), url=url,
                request_sha256=req_sha,
                response_sha256=sha256_text(canonical_json(body)),
                elapsed_s=0.0, attempts=0, from_cache=True, cache_path=str(cache.path),
            )
        cache.misses += 1

    do_post = poster or _raw_post
    req_headers = dict(headers) if headers is not None else default_headers(poll_seconds)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    started = time.monotonic()

    status = 0
    raw = ""
    resp_headers: dict[str, str] = {}
    for attempt in range(max_retries + 1):
        wait = throttle_seconds(_LAST_CALL[0] if _LAST_CALL else None, time.monotonic(), min_interval)
        if wait > 0:
            sleep(wait)
        _LAST_CALL[:] = [time.monotonic()]
        try:
            status, raw, resp_headers = do_post(url, data, req_headers, timeout)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001  본문을 못 읽어도 상태코드는 쓴다
                pass
            err_headers = _lower_headers(getattr(exc, "headers", None) or {})
            if exc.code in RETRY_STATUS and attempt < max_retries:
                sleep(backoff_delay(attempt, err_headers.get("retry-after"), base_delay))
                continue
            raise NimHTTPError(exc.code, body, url, err_headers) from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries:
                sleep(backoff_delay(attempt, None, base_delay))
                continue
            raise NimError(f"네트워크 오류로 {max_retries + 1}회 모두 실패했습니다: {exc}") from exc

        if status in RETRY_STATUS and attempt < max_retries:
            sleep(backoff_delay(attempt, resp_headers.get("retry-after"), base_delay))
            continue
        break
    else:  # pragma: no cover  for 문이 break 없이 끝나는 경로
        raise NimError(f"재시도 {max_retries}회를 모두 소진했습니다: {url}")

    attempts = attempt + 1
    if status == 202:
        reqid = resp_headers.get("nvcf-reqid")
        if not reqid:
            raise NimError("202 를 받았는데 nvcf-reqid 헤더가 없어 폴링할 수 없습니다.")
        status, raw, resp_headers = _poll_status(
            reqid, req_headers, timeout, sleep=sleep, getter=getter)

    if status >= 400:
        raise NimHTTPError(status, raw, url, resp_headers)

    try:
        body = json.loads(raw) if raw else {}
    except ValueError as exc:
        raise NimError(f"JSON 이 아닌 응답을 받았습니다({len(raw)}바이트): {raw[:300]}") from exc

    result = NimResponse(
        status=status, body=body, headers=resp_headers, url=url,
        request_sha256=req_sha, response_sha256=sha256_text(canonical_json(body)),
        elapsed_s=time.monotonic() - started, attempts=attempts,
        cache_path=str(cache.path) if cache else None,
    )
    if cache is not None:
        keep = {k: v for k, v in resp_headers.items()
                if k in ("nvcf-status", "nvcf-reqid", "content-type")}
        cache.put(cache_key, {"status": status, "headers": keep, "body": body})
    return result


# 공개 별칭. 다른 도구는 이 이름으로 부른다.
post_json = _post
