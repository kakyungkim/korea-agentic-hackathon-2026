"""PharmaSignal 도구 공통 유틸: HTTP GET, 파일 캐시, 해시, 타임스탬프.

표준 라이브러리만 사용한다(urllib, json, hashlib). LLM 호출은 없다.

캐시 규약
- 캐시 디렉터리: 환경변수 ``PHARMASIGNAL_CACHE_DIR``, 없으면 저장소의 ``eval/results``.
- 파일명: ``pharmasignal_cache_<source>_<sha1(key)[:12]>.json``. key는 호출자가 넘기는
  "약물|반응" 같은 식별 문자열이다. 파일 안에는 URL -> 원응답(dict 또는 str) 매핑을 둔다.
- 캐시는 원응답만 저장한다. 판정·지표는 항상 응답에서 다시 계산한다(verify_citations.py 규약).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_AGENT = "PharmaSignal-tools/0.1 (Korea Agentic AI Hackathon; stdlib urllib)"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_DIR = REPO_ROOT / "eval" / "results"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def short_hash(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def cache_dir() -> Path:
    d = Path(os.environ.get("PHARMASIGNAL_CACHE_DIR") or DEFAULT_CACHE_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


class ResponseCache:
    """URL -> 원응답 캐시. 파일 하나가 (source, key) 한 쌍을 담는다.

    읽고 나서 쓰고, 임시파일에 쓴 뒤 os.replace로 원자적 교체한다.
    """

    def __init__(self, source: str, key: str, enabled: bool = True):
        self.source = source
        self.key = key
        self.enabled = enabled
        self.path = cache_dir() / f"pharmasignal_cache_{source}_{short_hash(key)}.json"
        self.data: dict[str, Any] = {}
        self.hits = 0
        self.misses = 0
        if enabled and self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}

    def get(self, url: str):
        if not self.enabled:
            return None
        return self.data.get("responses", {}).get(url)

    def put(self, url: str, payload: Any) -> None:
        if not self.enabled:
            return
        self.data.setdefault("source", self.source)
        self.data.setdefault("key", self.key)
        self.data.setdefault("responses", {})[url] = payload
        self.data["updated_at"] = now_iso()
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)


def http_get(url: str, cache: ResponseCache | None = None, is_json: bool = True,
             retries: int = 2, timeout: int = 30, min_interval: float = 0.0,
             _last_call: list | None = None, reduce=None) -> Any:
    """GET 한 번. 성공 시 dict(JSON) 또는 str, HTTP 오류 시 {"__error__": code, "body": ...}.

    네트워크 예외는 retries 회까지 재시도한다. 캐시가 있으면 원응답(오류 포함)을 재사용한다.
    min_interval > 0 이면 직전 호출과의 간격을 그만큼 보장한다(PubMed 초당 3회 제한용).
    reduce 가 있으면 성공 응답을 reduce(payload)로 줄여서 반환·캐시한다(불필요한 레코드 본문 제거용).
    """
    if cache is not None:
        hit = cache.get(url)
        if hit is not None:
            cache.hits += 1
            return hit
        cache.misses += 1
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        if min_interval > 0 and _last_call:
            wait = min_interval - (time.monotonic() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            if _last_call is not None:
                _last_call[:] = [time.monotonic()]
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
            out = json.loads(raw) if is_json else raw
            if reduce is not None:
                out = reduce(out)
            if cache is not None:
                cache.put(url, out)
            return out
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")[:2000]
            except Exception:
                pass
            if exc.code == 429 and attempt < retries:
                time.sleep(2.0 * (attempt + 1))
                continue
            out = {"__error__": exc.code, "body": body}
            if cache is not None and exc.code == 404:
                cache.put(url, out)
            return out
        except Exception as exc:  # 네트워크 일시 오류
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    return {"__error__": f"network: {last_exc}"}


def is_error(payload: Any) -> bool:
    return not isinstance(payload, (dict, str)) or (
        isinstance(payload, dict) and "__error__" in payload
    )


def quote(s: str) -> str:
    return urllib.parse.quote(s, safe="")
