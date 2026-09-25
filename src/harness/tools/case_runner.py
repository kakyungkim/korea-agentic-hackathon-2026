"""후보 하나를 도킹에서 사람 근거까지 잇는 케이스 러너.

한 화합물(niraparib)을 두 타깃에 대고 같은 도구로 같은 단계를 밟은 뒤, **한쪽은 말할 수 있고
한쪽은 말할 수 없다**는 경계를 근거 ID 로 드러낸다. 프레임워크 무관 순수 파이썬이고 NAT 를
모듈 import 시점에 끌어오지 않는다(크리틱 판정 단계에서만 지연 import 한다).

구조는 ``pharmasignal_cases.py`` 를 따른다. LLM 은 3단 과잉해석 판정에서만 부르고, 그 단계는
키가 없거나 오프라인이면 건너뛰면서 건너뛴 사유를 결과에 남긴다.

경로 두 벌
| 경로 | 타깃 | FDDD Vina 실측 | FDDD role 원문 |
|---|---|---|---|
| A | PARP1 촉매도메인 4R6E chain A | -10.178 kcal/mol | co-crystal redocking control |
| B | 응고인자 Xa 2P16 | -7.967 kcal/mol | Exploratory cross-docking; no claim of validated binding |

단계와 출처
| 단계 | 출처 |
|---|---|
| 구조 | RCSB ``files.rcsb.org/download/<PDB>.pdb`` |
| 결합 1 | FDDD ``drug.flybrain.kr/data/docking/multi-target.json`` |
| 결합 2 | DiffDock NIM (``dock_diffdock.dock`` 경유) |
| 참조 | FDDD ``drug.flybrain.kr/data/evidence/summary.json`` 의 BindingDB 블록 |
| 사람 1 | DailyMed SPL 라벨 (``pharmasignal_dailymed``) |
| 사람 2 | openFDA FAERS 2x2 와 PRR, ROR (``pharmasignal_openfda``) |
| 사람 3 | PubMed E-utilities (``pharmasignal_pubmed``) |

근거 ID 형식
``rcsb:<PDB>:chain<X>:<sha8>``, ``dock:vina:<sha8>``, ``dock:diffdock:<sha8>:pose<순위>``,
``bindingdb:<UniProt>``, ``dailymed:setid:<id>:section:<번호>``, ``faers:2x2:<drug>-<event>``,
``pubmed:<PMID>``.

DiffDock 은 시드가 없어 호출마다 값이 다르다(``docs/notes/bionemo-nim.md``). 그래서 요청과
응답의 SHA256 을 함께 적고 "이 호출에서 이 값이 나왔다"로만 쓴다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from contextlib import contextmanager, nullcontext as _nullcontext
from typing import Any, Callable, Iterator

try:
    from . import pharmasignal_dailymed as _dailymed_mod
    from . import pharmasignal_openfda as _openfda_mod
    from . import pharmasignal_pubmed as _pubmed_mod
    from . import bionemo_client as bc
    from . import dock_diffdock as dd
    from . import overclaim_rules as _ocr
    from .pharmasignal_common import ResponseCache, http_get, is_error, now_iso
    from .pharmasignal_dailymed import find_label_mentions
    from .pharmasignal_openfda import faers_disproportionality
    from .pharmasignal_pubmed import search_pubmed
except ImportError:  # 스크립트/테스트에서 sys.path 로 직접 임포트할 때
    import pharmasignal_dailymed as _dailymed_mod  # type: ignore[no-redef]
    import pharmasignal_openfda as _openfda_mod  # type: ignore[no-redef]
    import pharmasignal_pubmed as _pubmed_mod  # type: ignore[no-redef]
    import bionemo_client as bc  # type: ignore[no-redef]
    import dock_diffdock as dd  # type: ignore[no-redef]
    import overclaim_rules as _ocr  # type: ignore[no-redef]
    from pharmasignal_common import ResponseCache, http_get, is_error, now_iso  # type: ignore[no-redef]
    from pharmasignal_dailymed import find_label_mentions  # type: ignore[no-redef]
    from pharmasignal_openfda import faers_disproportionality  # type: ignore[no-redef]
    from pharmasignal_pubmed import search_pubmed  # type: ignore[no-redef]

# --------------------------------------------------------------------------------------
# 상수. 전부 docs/notes/fddd-and-jev.md 와 실제 데이터 파일에서 온 값이다.
# --------------------------------------------------------------------------------------
FDDD_DOCKING_URL = "https://drug.flybrain.kr/data/docking/multi-target.json"
FDDD_EVIDENCE_URL = "https://drug.flybrain.kr/data/evidence/summary.json"
RCSB_TEMPLATE = "https://files.rcsb.org/download/{pdb}.pdb"

COMPOUND_ID = "niraparib"
COMPOUND_NAME = "Niraparib"
COMPOUND_SMILES = "C1CC(CNC1)C2=CC=C(C=C2)N3C=C4C=CC=C(C4=N3)C(=O)N"
ADVERSE_EVENT = "Thrombocytopenia"          # MedDRA PT. 라벨에 기재된 알려진 위험이다.
ADVERSE_EVENT_KO = "혈소판감소증"

# ZEJULA(niraparib) 라벨. setid 의 출처는 FDDD evidence/summary.json 의 pharmacokinetics 항목이다.
ZEJULA_SETID = "b7f675e2-159c-490c-b6f4-3f16d9492b7d"
PK_SECTION_CODE = "43682-4"                 # LOINC PHARMACOKINETICS SECTION
PK_SECTION_NUMBER = "12.3"
WARNINGS_SECTION_NUMBER = "5"               # 5 WARNINGS AND PRECAUTIONS
ADVERSE_SECTION_NUMBER = "6"                # 6 ADVERSE REACTIONS
SPL_XML_TEMPLATE = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"
SPL_NS = "{urn:hl7-org:v3}"

BINDINGDB_UNIPROT = "P09874"                # Human PARP1
PUBMED_RETMAX = 5
DIFFDOCK_NUM_POSES = 3                      # 레이트리밋을 아낀다. 경로당 1회 호출.

OFFLINE_MISS = "offline_cache_miss"


class PathSpec:
    """경로 하나의 고정 정보. 값은 FDDD 데이터에서 대조로 확인한다."""

    __slots__ = ("key", "title", "target_id", "pdb_id", "chain", "chain_note")

    def __init__(self, key: str, title: str, target_id: str, pdb_id: str, chain: str,
                 chain_note: str = ""):
        self.key = key
        self.title = title
        self.target_id = target_id
        self.pdb_id = pdb_id
        self.chain = chain
        self.chain_note = chain_note

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.key, "title": self.title, "target_id": self.target_id,
                "pdb_id": self.pdb_id, "chain": self.chain, "chain_note": self.chain_note}


PATH_A = PathSpec(
    "A", "PARP1 촉매도메인", "parp1-4r6e-chain-a", "4R6E", "A",
    "FDDD 가 chain A 만 쓴다. 우리도 같은 체인을 골랐다.")
PATH_B = PathSpec(
    "B", "응고인자 Xa", "factor-xa-2p16", "2P16", "A",
    "2P16 은 chain A(1,853 ATOM)와 chain L(385 ATOM)로 되어 있다. 촉매도메인인 chain A 를 "
    "고른 것은 우리 선택이고 FDDD 의 준비된 PDBQT 와 같은 파일이 아니다.")
PATHS = [PATH_A, PATH_B]


# --------------------------------------------------------------------------------------
# 근거 ID. 순수 함수라 오프라인에서 그대로 검증한다.
# --------------------------------------------------------------------------------------
def sha8(digest: str) -> str:
    """SHA256 16진 문자열의 앞 8자. 근거 ID 에 들어가는 조각이다."""
    if not isinstance(digest, str) or len(digest) < 8:
        raise ValueError(f"SHA256 16진 문자열이 아닙니다: {digest!r}")
    return digest[:8]


def rcsb_evidence_id(pdb_id: str, chain: str, digest: str) -> str:
    """``rcsb:<PDB>:chain<X>:<sha8>``. digest 는 보낸 ATOM 텍스트의 SHA256 이다."""
    return f"rcsb:{pdb_id.upper()}:chain{chain}:{sha8(digest)}"


def vina_evidence_id(digest: str) -> str:
    """``dock:vina:<sha8>``. digest 는 FDDD 가 공개한 Vina 로그의 SHA256 이다.

    점수가 적힌 파일을 가리켜야 대조가 되므로 수용체나 포즈 해시가 아니라 로그 해시를 쓴다.
    """
    return f"dock:vina:{sha8(digest)}"


def bindingdb_evidence_id(uniprot: str = BINDINGDB_UNIPROT) -> str:
    """``bindingdb:<UniProt>``."""
    return f"bindingdb:{uniprot.upper()}"


def dailymed_evidence_id(setid: str, section: str) -> str:
    """``dailymed:setid:<id>:section:<번호>``."""
    return f"dailymed:setid:{setid}:section:{section}"


def faers_evidence_id(drug: str = COMPOUND_ID, event: str = ADVERSE_EVENT) -> str:
    """``faers:2x2:<drug>-<event>``. 소문자로 맞추고 공백은 밑줄로 바꾼다."""
    return f"faers:2x2:{drug.strip().lower()}-{event.strip().lower().replace(' ', '_')}"


def pubmed_evidence_id(pmid: str | int) -> str:
    """``pubmed:<PMID>``."""
    return f"pubmed:{pmid}"


def diffdock_evidence_id(request_sha256: str, rank: int) -> str:
    """``dock:diffdock:<sha8>:pose<순위>``. dock_diffdock 의 형식을 그대로 쓴다."""
    return dd.evidence_id(request_sha256, rank)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_text(text: str) -> str:
    return bc.sha256_text(text)


# --------------------------------------------------------------------------------------
# 오프라인 경로. 캐시에 있는 응답만 쓰고 네트워크를 타지 않는다.
#
# 기존 도구 모듈을 고치지 않기 위해 모듈 속성 ``http_get`` 을 잠시 바꿔 끼운다. 도구가
# 넘겨 주는 ResponseCache 객체를 그대로 받아 쓰므로 URL 을 다시 만들 필요가 없다.
# 캐시에 없으면 ``{"__error__": "offline_cache_miss"}`` 를 돌려주고, 도구는 그것을
# errors 에 담는다. 자리표시자를 채우지 않는다.
# --------------------------------------------------------------------------------------
def cache_only_get(url: str, cache: ResponseCache | None = None, is_json: bool = True,
                   retries: int = 2, timeout: int = 30, min_interval: float = 0.0,
                   _last_call: list | None = None, reduce: Callable | None = None) -> Any:
    """``pharmasignal_common.http_get`` 과 같은 서명의 캐시 전용 GET."""
    if cache is not None:
        hit = cache.get(url)
        if hit is not None:
            cache.hits += 1
            return hit
        cache.misses += 1
    return {"__error__": OFFLINE_MISS, "body": url}


_PATCH_TARGETS = (_openfda_mod, _dailymed_mod, _pubmed_mod)


@contextmanager
def offline_http() -> Iterator[None]:
    """도구 3종의 HTTP GET 을 캐시 전용으로 바꿔 끼운다. 끝나면 되돌린다."""
    saved = [(mod, mod.http_get) for mod in _PATCH_TARGETS]
    try:
        for mod in _PATCH_TARGETS:
            mod.http_get = cache_only_get
        yield
    finally:
        for mod, original in saved:
            mod.http_get = original


def cache_only_post(url: str, payload: Any, timeout: float = 0.0, *,
                    cache_source: str | None = None, use_cache: bool = True,
                    **_ignored: Any) -> bc.NimResponse:
    """``bionemo_client.post_json`` 자리에 끼우는 캐시 전용 POST.

    캐시 키 규약은 ``bionemo_client._post`` 와 같다(``ResponseCache(source, req_sha)`` 와
    ``"<url>#<req_sha>"``). 캐시가 없으면 NimError 를 올려서 단계가 건너뛰어졌음을 드러낸다.
    """
    req_sha = bc.payload_sha256(payload)
    cache = ResponseCache(cache_source or dd.CACHE_SOURCE, req_sha)
    hit = cache.get(f"{url}#{req_sha}")
    if not isinstance(hit, dict) or "body" not in hit:
        raise bc.NimError(
            f"offline: DiffDock 응답 캐시가 없습니다(request_sha256={req_sha[:8]}). "
            f"캐시 파일 {cache.path} 를 확인하세요. 키를 넣고 온라인으로 1회 돌리면 채워집니다.")
    body = hit["body"]
    return bc.NimResponse(
        status=int(hit.get("status", 200)), body=body,
        headers={str(k).lower(): str(v) for k, v in (hit.get("headers") or {}).items()},
        url=url, request_sha256=req_sha,
        response_sha256=bc.sha256_text(bc.canonical_json(body)),
        elapsed_s=0.0, attempts=0, from_cache=True, cache_path=str(cache.path))


def _snippets(text: str, term: str, width: int = 130, max_hits: int = 1) -> list[str]:
    """용어 주변 원문 조각. 라벨 원문을 그대로 인용하기 위한 것이다."""
    hits: list[str] = []
    for m in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
        s, e = max(0, m.start() - width), min(len(text), m.end() + width)
        hits.append(("..." if s > 0 else "") + text[s:e] + ("..." if e < len(text) else ""))
        if len(hits) >= max_hits:
            break
    return hits


# --------------------------------------------------------------------------------------
# 단계 1. 구조. RCSB 에서 수용체를 받아 ATOM 줄 수와 SHA256 을 기록한다.
# --------------------------------------------------------------------------------------
def step_structure(spec: PathSpec, *, offline: bool = False, use_cache: bool = True) -> dict[str, Any]:
    """RCSB PDB 를 받아 체인 ATOM 만 추리고 무결성 값을 남긴다."""
    url = RCSB_TEMPLATE.format(pdb=spec.pdb_id.upper())
    out: dict[str, Any] = {
        "step": "structure", "source": "RCSB", "url": url, "pdb_id": spec.pdb_id,
        "chain": spec.chain, "chain_note": spec.chain_note, "ok": False,
        "pdb_bytes": None, "pdb_sha256": None, "atom_count_total": None,
        "chains_present": [], "atom_count_chain": None, "atom_text_sha256": None,
        "evidence_ids": [], "errors": [], "retrieved_at": now_iso(),
    }
    cache = ResponseCache("rcsb", spec.pdb_id.upper(), enabled=use_cache)
    getter = cache_only_get if offline else http_get
    payload = getter(url, cache=cache, is_json=False)
    if is_error(payload) or not isinstance(payload, str):
        code = payload.get("__error__") if isinstance(payload, dict) else "non_text"
        out["errors"].append(f"rcsb_fetch_failed:{code}")
        return out

    out["pdb_bytes"] = len(payload.encode("utf-8"))
    out["pdb_sha256"] = sha256_text(payload)
    out["atom_count_total"] = bc.count_atom_records(payload)
    out["chains_present"] = bc.pdb_chains(payload)
    try:
        atom_text = bc.extract_atom_records(payload, spec.chain)
    except ValueError as exc:
        out["errors"].append(f"atom_extract_failed:{exc}")
        return out
    out["atom_count_chain"] = bc.count_atom_records(atom_text)
    out["atom_text_bytes"] = len(atom_text.encode("utf-8"))
    out["atom_text_sha256"] = sha256_text(atom_text)
    out["evidence_ids"] = [rcsb_evidence_id(spec.pdb_id, spec.chain, out["atom_text_sha256"])]
    out["ok"] = True
    out["_atom_text"] = atom_text          # 다음 단계(DiffDock)로만 넘기고 JSON 에는 남기지 않는다
    return out


# --------------------------------------------------------------------------------------
# 단계 2. 결합 1. FDDD 가 실행한 AutoDock Vina 실측값과 프로토콜.
# --------------------------------------------------------------------------------------
def fetch_fddd_docking(*, offline: bool = False, use_cache: bool = True) -> dict[str, Any]:
    """FDDD multi-target.json 한 번 받기. 문서 자체의 SHA256 을 함께 남긴다."""
    cache = ResponseCache("fddd", "multi-target", enabled=use_cache)
    getter = cache_only_get if offline else http_get
    payload = getter(FDDD_DOCKING_URL, cache=cache, is_json=True)
    if is_error(payload) or not isinstance(payload, dict):
        code = payload.get("__error__") if isinstance(payload, dict) else "non_json"
        return {"ok": False, "errors": [f"fddd_docking_fetch_failed:{code}"], "doc": None,
                "url": FDDD_DOCKING_URL}
    return {"ok": True, "errors": [], "doc": payload, "url": FDDD_DOCKING_URL,
            "doc_sha256": sha256_text(bc.canonical_json(payload)),
            "generated_at": payload.get("generatedAt"), "notes": payload.get("notes") or []}


def step_vina(spec: PathSpec, docking: dict[str, Any]) -> dict[str, Any]:
    """FDDD 조합에서 Vina 점수와 프로토콜과 SHA256 을 뽑는다. 수치를 새로 만들지 않는다."""
    out: dict[str, Any] = {
        "step": "vina", "source": "FDDD AutoDock Vina 1.2.3", "url": FDDD_DOCKING_URL,
        "ok": False, "combination_id": None, "role": None, "score_kcal_mol": None,
        "units": None, "protocol": None, "poses": [], "sha256": {},
        "evidence_ids": [], "errors": [], "fddd_notes": [], "retrieved_at": now_iso(),
    }
    if not docking.get("ok"):
        out["errors"] = list(docking.get("errors") or ["fddd_docking_unavailable"])
        return out
    doc = docking["doc"]
    combos = [c for c in (doc.get("combinations") or [])
              if c.get("targetId") == spec.target_id and c.get("compoundId") == COMPOUND_ID]
    if not combos:
        out["errors"].append(
            f"combination_not_found:{spec.target_id}/{COMPOUND_ID}")
        return out
    combo = combos[0]
    protocols = {p.get("id"): p for p in (doc.get("protocols") or [])}
    targets = {t.get("id"): t for t in (doc.get("targets") or [])}
    proto = protocols.get(combo.get("protocolId")) or {}
    target = targets.get(spec.target_id) or {}

    log_sha = combo.get("logSha256") or ""
    out.update({
        "ok": bool(combo.get("computed")) and combo.get("score") is not None and bool(log_sha),
        "combination_id": combo.get("id"),
        "role": combo.get("role"),
        "score_kcal_mol": combo.get("scoreKcalMol", combo.get("score")),
        "units": proto.get("units"),
        "computed_at": combo.get("computedAt"),
        "smiles": combo.get("smiles"),
        "smiles_kind": combo.get("smilesKind"),
        "executed_input": combo.get("inputUrl"),
        "target_name": target.get("name"),
        "organism": target.get("organism"),
        "protocol": {
            "id": proto.get("id"), "tool": proto.get("tool"), "version": proto.get("version"),
            "runtime": proto.get("runtime"), "scoring_function": proto.get("scoringFunction"),
            "seed": proto.get("seed"), "exhaustiveness": proto.get("exhaustiveness"),
            "cpu": proto.get("cpu"), "num_modes": proto.get("numModes"),
            "box_center": (proto.get("box") or {}).get("center"),
            "box_size": (proto.get("box") or {}).get("size"),
            "parameter_note": proto.get("parameterNote"),
        },
        "poses": combo.get("poses") or [],
        "sha256": {
            "log": log_sha, "poses": combo.get("posesSha256"),
            "ligand_input_pdbqt": combo.get("inputSha256"),
            "receptor_pdbqt": target.get("receptorSha256"),
            "manifest_document": docking.get("doc_sha256"),
            "wasm_runtime": (doc.get("provenance") or {}).get("runtimeWasmSha256"),
        },
        "fddd_notes": list(doc.get("notes") or []),
    })
    if log_sha:
        out["evidence_ids"] = [vina_evidence_id(log_sha)]
    else:
        out["errors"].append("log_sha256_missing")
    return out


# --------------------------------------------------------------------------------------
# 단계 3. 결합 2. DiffDock NIM. 경로당 1회, num_poses=3.
# --------------------------------------------------------------------------------------
def step_diffdock(spec: PathSpec, structure: dict[str, Any], *, offline: bool = False,
                  use_cache: bool = True, num_poses: int = DIFFDOCK_NUM_POSES,
                  post: Callable[..., bc.NimResponse] | None = None) -> dict[str, Any]:
    """DiffDock 을 한 번 부른다. 키가 없거나 캐시가 없으면 건너뛰고 사유를 남긴다."""
    out: dict[str, Any] = {
        "step": "diffdock", "source": "NVIDIA DiffDock NIM", "endpoint": dd.DIFFDOCK_URL,
        "ok": False, "skipped": False, "skip_reason": None,
        "num_poses_requested": num_poses, "num_poses_returned": None,
        "position_confidence": [], "poses": [], "request_sha256": None,
        "response_sha256": None, "from_cache": None, "elapsed_s": None,
        "protein_atom_count": None, "evidence_ids": [], "errors": [],
        "confidence_warning": dd.CONFIDENCE_WARNING, "retrieved_at": now_iso(),
    }
    if not structure.get("ok") or not structure.get("_atom_text"):
        out["skipped"] = True
        out["skip_reason"] = "수용체 구조 단계가 실패해 도킹 입력을 만들 수 없었다."
        return out

    poster = post
    if poster is None:
        if offline:
            poster = cache_only_post
        elif not (os.environ.get("NVIDIA_API_KEY") or "").strip():
            out["skipped"] = True
            out["skip_reason"] = (
                "NVIDIA_API_KEY 가 없어 DiffDock 을 부르지 않았다. 이 단계의 수치는 결과에 없다.")
            return out

    try:
        result = dd.dock(
            structure["_atom_text"], COMPOUND_SMILES, chains=spec.chain,
            ligand_file_type="txt", num_poses=num_poses, use_cache=use_cache,
            post=poster)
    except bc.NimError as exc:
        out["skipped"] = True
        out["skip_reason"] = f"DiffDock 호출을 건너뛰었다: {exc}"
        out["errors"].append(f"{type(exc).__name__}: {exc}")
        return out
    except Exception as exc:  # noqa: BLE001  네트워크와 파싱 실패를 그대로 남긴다
        out["errors"].append(f"{type(exc).__name__}: {exc}")
        out["skip_reason"] = "DiffDock 호출이 실패했다. 이 단계의 수치는 결과에 없다."
        out["skipped"] = True
        return out

    out.update({
        "ok": result.num_poses_returned > 0,
        "status": result.status, "details": result.details,
        "field_name_used": result.field_name_used,
        "num_poses_returned": result.num_poses_returned,
        "position_confidence": list(result.position_confidence),
        "poses": [{"rank": p.rank, "position_confidence": p.position_confidence,
                   "evidence_id": p.evidence_id, "sdf_bytes": len(p.sdf.encode("utf-8"))}
                  for p in result.poses],
        "request_sha256": result.request_sha256,
        "response_sha256": result.response_sha256,
        "from_cache": result.from_cache,
        "elapsed_s": round(result.elapsed_s, 3),
        "protein_atom_count": result.protein_atom_count,
        "evidence_ids": list(result.evidence_ids),
        "reproducibility_note": (
            "DiffDock 호스팅 API 에 시드 파라미터가 없어 같은 입력에도 호출마다 값이 달라진다. "
            "이 값은 request_sha256 으로 지정되는 이 호출의 결과다."),
    })
    return out


# --------------------------------------------------------------------------------------
# 단계 4. 참조. BindingDB PARP1 참조 집합. 종점 4종을 합치지 않는다.
# --------------------------------------------------------------------------------------
def fetch_fddd_evidence(*, offline: bool = False, use_cache: bool = True) -> dict[str, Any]:
    """FDDD evidence/summary.json 한 번 받기."""
    cache = ResponseCache("fddd", "evidence-summary", enabled=use_cache)
    getter = cache_only_get if offline else http_get
    payload = getter(FDDD_EVIDENCE_URL, cache=cache, is_json=True)
    if is_error(payload) or not isinstance(payload, dict):
        code = payload.get("__error__") if isinstance(payload, dict) else "non_json"
        return {"ok": False, "errors": [f"fddd_evidence_fetch_failed:{code}"], "doc": None,
                "url": FDDD_EVIDENCE_URL}
    return {"ok": True, "errors": [], "doc": payload, "url": FDDD_EVIDENCE_URL,
            "doc_sha256": sha256_text(bc.canonical_json(payload)),
            "captured_at": payload.get("capturedAt")}


def step_bindingdb(spec: PathSpec, evidence: dict[str, Any]) -> dict[str, Any]:
    """이 타깃에 붙은 참조 친화도 집합이 있는지 본다. 없으면 없다고 적는다."""
    out: dict[str, Any] = {
        "step": "bindingdb_reference", "source": "FDDD evidence summary (BindingDB REST)",
        "url": FDDD_EVIDENCE_URL, "ok": False, "reference_set_present": None,
        "uniprot": None, "target": None, "record_count": None, "compound_count": None,
        "endpoint_counts": {}, "endpoint_warning": None, "filter": None,
        "evidence_ids": [], "errors": [], "retrieved_at": now_iso(),
    }
    if not evidence.get("ok"):
        out["errors"] = list(evidence.get("errors") or ["fddd_evidence_unavailable"])
        return out
    block = (evidence["doc"] or {}).get("bindingdb") or {}
    uniprot = ""
    match = re.search(r"uniprot=([A-Z0-9]+)", str(block.get("sourceUrl") or ""))
    if match:
        uniprot = match.group(1)

    # 참조 집합은 PARP1(P09874) 하나뿐이다. 경로 B(응고인자 Xa)에는 대응하는 집합이 없다.
    is_parp1 = spec.target_id == PATH_A.target_id
    out.update({
        "ok": True,
        "reference_set_present": bool(block) and is_parp1,
        "uniprot": uniprot or None,
        "target": block.get("target"),
        "record_count": block.get("recordCount") if is_parp1 else None,
        "compound_count": block.get("compoundCount") if is_parp1 else None,
        "endpoint_counts": dict(block.get("counts") or {}) if is_parp1 else {},
        "endpoint_warning": block.get("warning"),
        "filter": block.get("filter"),
        "absent_note": (None if is_parp1 else
                        f"이 실행에 붙은 참조 친화도 집합은 {block.get('target')} 하나뿐이다. "
                        f"{spec.title}({spec.pdb_id}) 에 대응하는 참조 집합은 없다."),
    })
    if uniprot:
        out["evidence_ids"] = [bindingdb_evidence_id(uniprot)]
    else:
        out["errors"].append("uniprot_not_found_in_source_url")
    return out


# --------------------------------------------------------------------------------------
# 단계 5. 사람 1. DailyMed 라벨. PK 절과 대상 이상사례 기재 여부.
# --------------------------------------------------------------------------------------
# 라벨 12.3 절 본문에서 읽는 PK 값. 정규식은 ZEJULA 라벨 문장 구조에 맞춘 것이고, 문장이
# 바뀌면 값이 None 이 된다. 없는 값을 추정해 채우지 않는다.
_PK_PATTERNS: dict[str, str] = {
    "half_life_hours": r"half-life\s*\(?\s*t\s*1\s*/\s*2\s*\)?\s*is\s*([\d.]+)",
    "bioavailability_percent": r"bioavailability of niraparib is approximately\s*([\d.]+)\s*%",
    "plasma_protein_binding_percent": r"is\s*([\d.]+)\s*% bound to human plasma proteins",
    "cmax_ng_ml": r"concentration\s*\(\s*Cmax\s*\)\s*is\s*([\d,]+)\s",
}


def parse_pk_values(text: str) -> dict[str, float | None]:
    """PK 절 본문에서 수치를 읽는다. 문장을 못 찾으면 그 값은 None 이다."""
    out: dict[str, float | None] = {}
    for key, pattern in _PK_PATTERNS.items():
        match = re.search(pattern, text, flags=re.I)
        out[key] = float(match.group(1).replace(",", "")) if match else None
    return out


def extract_pk_section(setid: str = ZEJULA_SETID, *, offline: bool = False,
                       use_cache: bool = True) -> dict[str, Any]:
    """SPL XML 에서 LOINC 43682-4(12.3 Pharmacokinetics) 절 본문을 뽑는다.

    ``pharmasignal_dailymed.fetch_label_sections`` 는 경고와 이상반응 절만 매핑한다. 그 모듈을
    고치지 않기 위해 여기서 같은 캐시 키(``label|<setid>``)로 같은 응답을 다시 읽는다.
    캐시 적중이므로 HTTP 호출이 늘지 않는다.
    """
    out: dict[str, Any] = {"setid": setid, "section_code": PK_SECTION_CODE,
                           "section_number": PK_SECTION_NUMBER, "ok": False,
                           "text_length": None, "values": {}, "snippets": {}, "errors": []}
    cache = ResponseCache("dailymed", f"label|{setid}", enabled=use_cache)
    getter = cache_only_get if offline else http_get
    payload = getter(SPL_XML_TEMPLATE.format(setid=setid), cache=cache, is_json=False)
    if is_error(payload) or not isinstance(payload, str):
        code = payload.get("__error__") if isinstance(payload, dict) else "non_text"
        out["errors"].append(f"spl_fetch_failed:{code}")
        return out
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        out["errors"].append(f"xml_parse_error:{exc}")
        return out
    for sec in root.iter(f"{SPL_NS}section"):
        code_el = sec.find(f"{SPL_NS}code")
        if code_el is None or code_el.get("code") != PK_SECTION_CODE:
            continue
        # 하위 태그(<sub> 등)로 "t1/2" 가 갈라지지 않게 먼저 이어 붙이고 공백만 접는다.
        text = re.sub(r"\s+", " ", "".join(sec.itertext())).strip()
        out["ok"] = bool(text)
        out["text_length"] = len(text)
        out["values"] = parse_pk_values(text)
        for term in ("half-life", "bioavailability", "plasma proteins", "Cmax"):
            hit = _snippets(text, term)
            if hit:
                out["snippets"][term] = hit[0]
        return out
    out["errors"].append(f"section_not_found:{PK_SECTION_CODE}")
    return out


def step_label(*, offline: bool = False, use_cache: bool = True) -> dict[str, Any]:
    """ZEJULA 라벨에서 이상사례 기재 여부와 12.3 절 PK 를 확인한다."""
    out: dict[str, Any] = {
        "step": "label", "source": "DailyMed SPL", "setid": ZEJULA_SETID,
        "setid_source": "FDDD evidence/summary.json 의 pharmacokinetics 항목",
        "drug": COMPOUND_ID, "event": ADVERSE_EVENT, "ok": False,
        "title": None, "labeled": None, "mentioned_sections": [], "mention_count": 0,
        "snippet": None, "pk": None, "evidence_ids": [], "pk_evidence_ids": [],
        "event_evidence_ids": [], "errors": [],
        "retrieved_at": now_iso(),
    }
    runner = offline_http() if offline else _nullcontext()
    with runner:
        mentions = find_label_mentions(
            COMPOUND_ID, ADVERSE_EVENT, setids=[ZEJULA_SETID], use_cache=use_cache)
    out["errors"].extend(mentions.get("errors") or [])
    out["labeled"] = mentions.get("labeled")
    out["mentioned_sections"] = list(mentions.get("mentioned_sections") or [])
    out["mention_count"] = len(mentions.get("label_mentions") or [])
    checked = mentions.get("labels_checked") or []
    if checked:
        out["title"] = checked[0].get("title")
        out["xml_url"] = checked[0].get("xml_url")
    if mentions.get("label_mentions"):
        out["snippet"] = mentions["label_mentions"][0]["snippet"]

    pk = extract_pk_section(ZEJULA_SETID, offline=offline, use_cache=use_cache)
    out["pk"] = pk
    out["errors"].extend(pk.get("errors") or [])

    # PK 근거와 이상사례 기재 근거를 나눈다. 12.3 절은 PK 주장에만 붙인다.
    pk_ids = [dailymed_evidence_id(ZEJULA_SETID, PK_SECTION_NUMBER)] if pk.get("ok") else []
    section_numbers = {"warnings_and_precautions": WARNINGS_SECTION_NUMBER,
                       "adverse_reactions": ADVERSE_SECTION_NUMBER,
                       "boxed_warning": "boxed"}
    event_ids = [dailymed_evidence_id(ZEJULA_SETID, section_numbers[name])
                 for name in out["mentioned_sections"] if name in section_numbers]
    out["pk_evidence_ids"] = pk_ids
    out["event_evidence_ids"] = event_ids
    out["evidence_ids"] = pk_ids + event_ids
    out["ok"] = bool(out["labeled"]) and pk.get("ok", False)
    return out


# --------------------------------------------------------------------------------------
# 단계 6. 사람 2. openFDA FAERS 2x2 와 PRR, ROR, 신뢰구간.
# --------------------------------------------------------------------------------------
def step_faers(*, offline: bool = False, use_cache: bool = True) -> dict[str, Any]:
    """FAERS 2x2 표와 불균형 지표. 계산은 기존 도구가 하고 여기서는 옮겨 담기만 한다."""
    out: dict[str, Any] = {
        "step": "faers", "source": "openFDA FAERS", "drug": COMPOUND_ID,
        "event": ADVERSE_EVENT, "ok": False, "counts": None, "prr": None, "prr_ci95": None,
        "ror": None, "ror_ci95": None, "chi2": None, "chi2_yates": None,
        "evans_signal": None, "ror_signal": None, "haldane_applied": None,
        "data_last_updated": None, "query_urls": {}, "evidence_ids": [], "errors": [],
        "retrieved_at": now_iso(),
        "causality_note": (
            "불균형 지표는 같이 자주 보고된다는 것만 말하고 인과를 말하지 않는다. "
            "보고 편향과 적응증 교란과 노출 규모 차이가 그대로 남는다."),
    }
    runner = offline_http() if offline else _nullcontext()
    with runner:
        raw = faers_disproportionality(COMPOUND_ID, ADVERSE_EVENT, use_cache=use_cache)
    for key in ("counts", "prr", "prr_ci95", "ror", "ror_ci95", "chi2", "chi2_yates",
                "evans_signal", "ror_signal", "haldane_applied", "data_last_updated",
                "query_urls"):
        out[key] = raw.get(key)
    out["errors"] = list(raw.get("errors") or [])
    out["openfda_query_urls"] = list(raw.get("evidence_ids") or [])
    out["ok"] = bool(out["counts"]) and out["prr"] is not None
    if out["ok"]:
        out["evidence_ids"] = [faers_evidence_id()]
    return out


# --------------------------------------------------------------------------------------
# 단계 7. 사람 3. PubMed 문헌 건수와 대표 PMID.
# --------------------------------------------------------------------------------------
def step_pubmed(*, offline: bool = False, use_cache: bool = True,
                retmax: int = PUBMED_RETMAX) -> dict[str, Any]:
    """PubMed 검색 결과. 대표 PMID 는 제목에 이상사례가 들어간 것을 먼저 고른다."""
    out: dict[str, Any] = {
        "step": "pubmed", "source": "PubMed E-utilities", "ok": False,
        "term": None, "total_count": None, "pmids": [], "articles": [],
        "representative_pmid": None, "representative_title": None,
        "evidence_ids": [], "errors": [], "retrieved_at": now_iso(),
    }
    runner = offline_http() if offline else _nullcontext()
    with runner:
        raw = search_pubmed(COMPOUND_ID, ADVERSE_EVENT, retmax=retmax, use_cache=use_cache)
    out["term"] = raw.get("term")
    out["total_count"] = raw.get("total_count")
    out["pmids"] = list(raw.get("pmids") or [])
    out["articles"] = [{k: a.get(k) for k in ("pmid", "year", "title", "journal")}
                       for a in (raw.get("articles") or [])]
    out["errors"] = list(raw.get("errors") or [])
    needle = ADVERSE_EVENT.lower()
    chosen = next((a for a in out["articles"] if needle in str(a.get("title", "")).lower()), None)
    chosen = chosen or (out["articles"][0] if out["articles"] else None)
    if chosen:
        out["representative_pmid"] = chosen.get("pmid")
        out["representative_title"] = chosen.get("title")
        out["evidence_ids"] = [pubmed_evidence_id(chosen["pmid"])]
    out["ok"] = bool(out["pmids"]) and out["total_count"] is not None
    return out


# --------------------------------------------------------------------------------------
# 한 경로 실행과 케이스 전체
# --------------------------------------------------------------------------------------
def run_path(spec: PathSpec, docking: dict[str, Any], evidence: dict[str, Any], *,
             offline: bool = False, use_cache: bool = True,
             num_poses: int = DIFFDOCK_NUM_POSES,
             use_vina: bool = True,
             diffdock_post: Callable[..., bc.NimResponse] | None = None) -> dict[str, Any]:
    """한 경로(화합물 + 타깃)의 일곱 단계를 모아 구조화한다.

    ``use_vina=False`` 면 FDDD 의 AutoDock Vina 실측 조회를 건너뛴다. 그 자산은 팀원의
    별도 저작물이므로 쓸 수 없게 되는 경우를 대비한 경로다. 결합 근거는 DiffDock NIM 하나로
    줄지만 케이스의 요지(같은 화합물, 두 경로, 한쪽만 실험 근거가 있다)는 그대로 선다.
    자세한 것은 ``docs/notes/contingency-roster.md``.
    """
    structure = step_structure(spec, offline=offline, use_cache=use_cache)
    if use_vina:
        vina = step_vina(spec, docking)
    else:
        vina = {"step": "vina", "ok": False, "skipped": True,
                "skip_reason": "--no-vina 로 FDDD Vina 실측 조회를 건너뛰었다. "
                               "결합 근거는 DiffDock NIM 만 쓴다.",
                "evidence_ids": [], "errors": []}
    diffdock = step_diffdock(spec, structure, offline=offline, use_cache=use_cache,
                             num_poses=num_poses, post=diffdock_post)
    bindingdb = step_bindingdb(spec, evidence)
    label = step_label(offline=offline, use_cache=use_cache)
    faers = step_faers(offline=offline, use_cache=use_cache)
    pubmed = step_pubmed(offline=offline, use_cache=use_cache)

    structure_public = {k: v for k, v in structure.items() if not k.startswith("_")}
    steps = {"structure": structure_public, "vina": vina, "diffdock": diffdock,
             "bindingdb": bindingdb, "label": label, "faers": faers, "pubmed": pubmed}
    evidence_ids: list[str] = []
    for step in steps.values():
        for eid in step.get("evidence_ids") or []:
            if eid not in evidence_ids:
                evidence_ids.append(eid)
    errors = {name: step["errors"] for name, step in steps.items() if step.get("errors")}
    return {
        **spec.as_dict(),
        "human_evidence_scope": (
            "라벨과 FAERS 와 문헌은 화합물 단위 근거다. 이 타깃에서의 결합을 뒷받침하지 않는다."),
        "steps": steps,
        "evidence_ids": evidence_ids,
        "errors": errors,
        "_atom_text_available": bool(structure.get("_atom_text")),
    }


def run_case(*, offline: bool = False, use_cache: bool = True,
             num_poses: int = DIFFDOCK_NUM_POSES,
             use_vina: bool = True,
             diffdock_post: Callable[..., bc.NimResponse] | None = None,
             paths: list[PathSpec] | None = None) -> dict[str, Any]:
    """두 경로를 돌려 케이스 한 벌을 만든다. 주장 조립과 크리틱은 부르는 쪽에서 한다.

    ``use_vina=False`` 면 FDDD 도킹 문서를 아예 받지 않는다. 결합 근거가 DiffDock 하나로
    줄어도 두 경로 대조는 성립한다. 경로 A 의 신뢰도는 양수이고 경로 B 는 음수이며,
    BindingDB 참조는 경로 A 에만 있다.
    """
    specs = paths or PATHS
    if use_vina:
        docking = fetch_fddd_docking(offline=offline, use_cache=use_cache)
    else:
        docking = {"combinations": [], "targets": [], "protocols": [], "notes": []}
    evidence = fetch_fddd_evidence(offline=offline, use_cache=use_cache)
    results = [run_path(spec, docking, evidence, offline=offline, use_cache=use_cache,
                        num_poses=num_poses, use_vina=use_vina, diffdock_post=diffdock_post)
               for spec in specs]
    return {
        "case_id": "case_niraparib",
        "generated_at": now_iso(),
        "offline": offline,
        "compound": {"id": COMPOUND_ID, "name": COMPOUND_NAME, "smiles": COMPOUND_SMILES,
                     "smiles_note": (
                         "SMILES 는 분자 식별 정보이고 FDDD 가 실행한 입력이 아니다. "
                         "실행 입력은 준비된 PDBQT 파일이다."),
                     "adverse_event": ADVERSE_EVENT, "adverse_event_ko": ADVERSE_EVENT_KO},
        "sources": {"fddd_docking": docking.get("url"),
                    "fddd_docking_sha256": docking.get("doc_sha256"),
                    "fddd_docking_generated_at": docking.get("generated_at"),
                    "fddd_evidence": evidence.get("url"),
                    "fddd_evidence_sha256": evidence.get("doc_sha256"),
                    "fddd_evidence_captured_at": evidence.get("captured_at"),
                    "diffdock_endpoint": dd.DIFFDOCK_URL},
        "fddd_notes": list(docking.get("notes") or []),
        "paths": [{k: v for k, v in r.items() if not k.startswith("_")} for r in results],
    }


def path_by_key(case: dict[str, Any], key: str) -> dict[str, Any]:
    """케이스에서 경로 하나를 꺼낸다. 없으면 KeyError."""
    for path in case.get("paths") or []:
        if path.get("path") == key:
            return path
    raise KeyError(f"경로 {key!r} 가 케이스에 없습니다.")


# ======================================================================================
# 주장 두 벌. 같은 근거 ID 와 같은 숫자를 쓰고 추론만 다르다.
#
# (가) 뒷받침되는 요약: 각 주장이 근거 ID 를 갖고 해석 한계를 지킨다.
# (나) 과잉해석을 심은 요약: 근거 ID 와 숫자를 전부 맞게 두고 추론만 어긋뜨린다.
#      1단 결정 규칙과 2단 숫자 오라클을 모두 통과해야 하므로 빈 근거 ID 와 틀린 숫자를
#      넣지 않는다. 3단 LLM 판정만 잡아야 시연 가치가 있다.
# ======================================================================================
def _fmt(value: Any, places: int = 2) -> str:
    """숫자를 자리수 고정 문자열로. None 이면 물음표 대신 빈 값을 드러낸다."""
    if value is None:
        return "[unverified]"
    if isinstance(value, float):
        return f"{value:.{places}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _first(ids: list[str] | None) -> list[str]:
    return list(ids or [])


def build_supported_claims(case: dict[str, Any]) -> dict[str, Any]:
    """(가) 뒷받침되는 요약. AuthorOutput 형식의 dict 를 돌려준다."""
    a = path_by_key(case, "A")
    b = path_by_key(case, "B")
    sa, sb = a["steps"], b["steps"]
    claims: list[dict[str, Any]] = []

    def add(text: str, ids: list[str]) -> None:
        ids = [i for i in ids if i]
        if ids:
            claims.append({"text": text, "evidence_ids": ids})

    # 경로 A. 결합
    if sa["vina"]["ok"]:
        proto = sa["vina"]["protocol"]
        add(f"niraparib 은 사람 PARP1 촉매도메인(PDB 4R6E chain A)에서 AutoDock Vina "
            f"{proto['version']} 으로 {sa['vina']['score_kcal_mol']} kcal/mol 을 받았다. "
            f"이 값은 같은 실행 안의 다른 포즈와만 비교할 수 있다.",
            _first(sa["vina"]["evidence_ids"]) + _first(sa["structure"]["evidence_ids"]))
        add(f"그 실행의 프로토콜은 seed {proto['seed']}, exhaustiveness {proto['exhaustiveness']}, "
            f"num_modes {proto['num_modes']}, 박스 중심 {proto['box_center']}, "
            f"크기 {proto['box_size']} 이고, FDDD 가 불확실성과 수렴 분석을 하지 않았다고 적었다.",
            _first(sa["vina"]["evidence_ids"]))
        add(f"FDDD 가 적어 둔 이 조합의 역할은 \"{sa['vina']['role']}\" 이고, 실행 입력은 "
            f"SMILES 가 아니라 준비된 PDBQT 파일 {sa['vina']['executed_input']} 이다.",
            _first(sa["vina"]["evidence_ids"]))
    if sa["diffdock"]["ok"] and sa["diffdock"]["position_confidence"]:
        conf = sa["diffdock"]["position_confidence"][0]
        add(f"같은 수용체 ATOM {sa['diffdock']['protein_atom_count']:,}줄과 같은 리간드로 "
            f"NVIDIA DiffDock NIM 을 1회 불러 1순위 포즈의 position_confidence "
            f"{conf:.3f} 을 받았다. 이 값은 포즈가 기하학적으로 맞을 확률이고 결합 친화도가 "
            f"아니며, 호스팅 API 에 시드가 없어 같은 입력에도 호출마다 달라진다.",
            _first(sa["diffdock"]["evidence_ids"][:1]) + _first(sa["structure"]["evidence_ids"]))
    # 경로 A. 참조
    if sa["bindingdb"]["reference_set_present"]:
        counts = sa["bindingdb"]["endpoint_counts"]
        add(f"BindingDB 의 사람 PARP1(UniProt {sa['bindingdb']['uniprot']}) 참조 집합에 레코드 "
            f"{sa['bindingdb']['record_count']:,}건과 화합물 {sa['bindingdb']['compound_count']:,}종이 "
            f"있고, 종점은 Ki {counts.get('Ki'):,}, IC50 {counts.get('IC50'):,}, "
            f"Kd {counts.get('Kd'):,}, EC50 {counts.get('EC50'):,}로 나뉘어 있다. "
            f"네 종점은 하나의 친화도 점수로 합치지 않는다.",
            _first(sa["bindingdb"]["evidence_ids"]))
    # 사람 근거
    pk = (sa["label"].get("pk") or {})
    values = pk.get("values") or {}
    if pk.get("ok") and values.get("half_life_hours"):
        add(f"ZEJULA(niraparib) 라벨 {PK_SECTION_NUMBER} 절에 평균 반감기 "
            f"{_fmt(values.get('half_life_hours'), 0)}시간, 절대 생체이용률 "
            f"{_fmt(values.get('bioavailability_percent'), 0)}퍼센트, 혈장단백결합 "
            f"{_fmt(values.get('plasma_protein_binding_percent'), 0)}퍼센트가 적혀 있다. "
            f"혈장단백결합은 PARP1 결합이 아니다.",
            _first(sa["label"]["pk_evidence_ids"]))
    if sa["label"]["labeled"]:
        add(f"{ADVERSE_EVENT_KO}(thrombocytopenia)은 같은 라벨의 "
            f"{', '.join(section_labels(sa['label']['mentioned_sections']))}에 기재되어 있고 본문에서 "
            f"{sa['label']['mention_count']}곳에 등장한다. 이미 알려진 위험이라는 뜻이다.",
            _first(sa["label"]["event_evidence_ids"]))
    if sa["faers"]["ok"]:
        c = sa["faers"]["counts"]
        add(f"openFDA FAERS 보고 건수로 짠 2x2 표(a={c['a']:,}, b={c['b']:,}, c={c['c']:,}, "
            f"d={c['d']:,})에서 PRR {_fmt(sa['faers']['prr'])}, "
            f"ROR {_fmt(sa['faers']['ror'])}(신뢰구간 하한 {_fmt(sa['faers']['ror_ci95'][0])}, "
            f"상한 {_fmt(sa['faers']['ror_ci95'][1])}), "
            f"Yates 보정 카이제곱 {_fmt(sa['faers']['chi2_yates'])} 가 나왔다. "
            f"데이터 최종 갱신은 {sa['faers']['data_last_updated']} 이다.",
            _first(sa["faers"]["evidence_ids"]))
        add("불균형 지표는 이 반응이 이 약물에서 유독 많이 보고된다는 것만 말한다. 라벨에 이미 "
            "기재된 위험이므로 새 신호가 아니고, 인과는 이 표로 판정하지 않는다.",
            _first(sa["faers"]["evidence_ids"]) + _first(sa["label"]["event_evidence_ids"]))
    if sa["pubmed"]["ok"] and sa["pubmed"]["representative_pmid"]:
        add(f"PubMed 에서 '{sa['pubmed']['term']}' 검색 결과가 {sa['pubmed']['total_count']:,}건이고, "
            f"대표 문헌은 PMID {sa['pubmed']['representative_pmid']} "
            f"\"{sa['pubmed']['representative_title']}\" 이다.",
            _first(sa["pubmed"]["evidence_ids"]))
    # 경로 B. 점수만 있고 실험 근거가 없다
    if sb["vina"]["ok"]:
        add(f"같은 화합물을 사람 응고인자 Xa(PDB 2P16)에 도킹한 FDDD 결과는 "
            f"{sb['vina']['score_kcal_mol']} kcal/mol 이고, FDDD 가 그 조합에 적어 둔 역할은 "
            f"\"{sb['vina']['role']}\" 이다.",
            _first(sb["vina"]["evidence_ids"]) + _first(sb["structure"]["evidence_ids"]))
        add("두 점수는 서로 다른 단백질에서 나왔고 교차 타깃으로 보정되지 않았다. FDDD 가 "
            "타깃을 전역으로 순위 매기거나 선택성과 Kd, Ki, IC50, 효능을 추론하지 말라고 적었다.",
            _first(sa["vina"]["evidence_ids"]) + _first(sb["vina"]["evidence_ids"]))
    if sb["bindingdb"]["ok"]:
        add(f"이 실행에 붙은 참조 친화도 집합은 {sa['bindingdb']['target']} 하나뿐이고, "
            f"응고인자 Xa 에 대응하는 참조 집합은 없다.",
            _first(sb["bindingdb"]["evidence_ids"]))
    add("라벨과 FAERS 와 문헌은 niraparib 이라는 화합물에 붙은 근거이고, 어느 타깃에 결합하는지를 "
        "가리지 않는다. 응고인자 Xa 경로를 뒷받침하는 사람 근거로 쓸 수 없다.",
        _first(sa["label"]["event_evidence_ids"]) + _first(sa["faers"]["evidence_ids"])
        + _first(sa["pubmed"]["evidence_ids"]))

    summary = (
        "같은 화합물을 두 타깃에 대고 같은 도구로 같은 단계를 밟았다. PARP1 경로에서는 "
        "co-crystal redocking 대조군으로 계산한 Vina 점수와 BindingDB 참조 친화도 집합과 사람 "
        "라벨과 이상사례 보고가 모두 같은 대상을 가리킨다. 응고인자 Xa 경로에는 Vina 점수 하나만 "
        "있고 참조 집합도 실험으로 확인된 결합 근거도 없다. 두 점수를 견주어 선택성을 말하지 "
        "않고, 도킹 점수와 포즈 신뢰도를 친화도로 환산하지 않는다.")
    return {"claims": claims, "summary": summary}


def build_overclaim_claims(case: dict[str, Any]) -> dict[str, Any]:
    """(나) 과잉해석을 심은 요약. 숫자와 근거 ID 는 (가)와 같고 추론만 어긋난다."""
    a = path_by_key(case, "A")
    b = path_by_key(case, "B")
    sa, sb = a["steps"], b["steps"]
    claims: list[dict[str, Any]] = []
    planted: list[str] = []

    def add(text: str, ids: list[str], rule: str) -> None:
        ids = [i for i in ids if i]
        if ids:
            claims.append({"text": text, "evidence_ids": ids})
            planted.append(rule)

    if sa["vina"]["ok"] and sb["vina"]["ok"]:
        score_a = float(sa["vina"]["score_kcal_mol"])
        score_b = float(sb["vina"]["score_kcal_mol"])
        add(f"PARP1 에서 {score_a} kcal/mol 이고 응고인자 Xa 에서 {score_b} kcal/mol 이므로, "
            f"niraparib 은 응고인자 Xa 보다 {abs(score_a - score_b):.3f} kcal/mol 만큼 PARP1 에 "
            f"더 강하게 결합하고 PARP1 선택성을 갖는다.",
            _first(sa["vina"]["evidence_ids"]) + _first(sb["vina"]["evidence_ids"]),
            "교차 타깃 순위와 선택성 추론")
    if sa["vina"]["ok"]:
        conf_ids = _first(sa["diffdock"]["evidence_ids"][:1])
        if conf_ids and sa["diffdock"]["position_confidence"]:
            conf = sa["diffdock"]["position_confidence"][0]
            add(f"Vina {sa['vina']['score_kcal_mol']} kcal/mol 을 환산하면 Kd 는 나노몰 수준이고 "
                f"IC50 도 같은 자리에 온다. DiffDock 1순위 position_confidence {conf:.3f} 이 그 "
                f"친화도를 같은 척도에서 뒷받침한다.",
                _first(sa["vina"]["evidence_ids"]) + conf_ids,
                "도킹 점수와 DiffDock 신뢰도의 친화도 환산")
        else:
            add(f"Vina {sa['vina']['score_kcal_mol']} kcal/mol 을 환산하면 Kd 는 나노몰 수준이고 "
                f"IC50 도 같은 자리에 온다.",
                _first(sa["vina"]["evidence_ids"]), "도킹 점수의 친화도 환산")
        proto = sa["vina"]["protocol"]
        add(f"seed {proto['seed']} 를 고정하고 exhaustiveness {proto['exhaustiveness']} 로 "
            f"돌렸으므로 이 점수는 수렴한 재현값이고 다시 돌려도 같게 나온다.",
            _first(sa["vina"]["evidence_ids"]), "단일 seed 결과의 수렴과 재현성 주장")
    if sb["vina"]["ok"]:
        add(f"응고인자 Xa 에서 {sb['vina']['score_kcal_mol']} kcal/mol 로 결합하므로, niraparib 을 "
            f"쓸 때 항응고 작용을 함께 고려해야 한다.",
            _first(sb["vina"]["evidence_ids"]), "교차 도킹을 확인된 결합으로 해석")
    if sa["bindingdb"]["reference_set_present"]:
        counts = sa["bindingdb"]["endpoint_counts"]
        add(f"BindingDB 참조 집합의 Ki {counts.get('Ki'):,}건과 IC50 {counts.get('IC50'):,}건과 "
            f"Kd {counts.get('Kd'):,}건과 EC50 {counts.get('EC50'):,}건을 합친 "
            f"{sa['bindingdb']['record_count']:,}건이 하나의 친화도 근거가 되어 위 도킹 점수를 "
            f"실험으로 검증한다.",
            _first(sa["bindingdb"]["evidence_ids"]), "종점 4종을 보정 없이 단일 친화도로 합침")
    if sa["faers"]["ok"]:
        add(f"PRR {_fmt(sa['faers']['prr'])}, ROR {_fmt(sa['faers']['ror'])}(신뢰구간 하한 "
            f"{_fmt(sa['faers']['ror_ci95'][0])}, 상한 {_fmt(sa['faers']['ror_ci95'][1])}), "
            f"Yates 보정 카이제곱 {_fmt(sa['faers']['chi2_yates'])} 는 niraparib 이 "
            f"{ADVERSE_EVENT_KO}을 일으킨다는 것을 통계적으로 확증한다.",
            _first(sa["faers"]["evidence_ids"]), "불균형 지표를 인과로 해석")
    if sa["label"]["labeled"] and sb["vina"]["ok"]:
        add(f"{ADVERSE_EVENT_KO}이 라벨 경고와 이상반응 절에 기재된 것은 위 응고인자 Xa 결합의 "
            f"사람 쪽 확증이다.",
            _first(sa["label"]["event_evidence_ids"]) + _first(sb["vina"]["evidence_ids"]),
            "화합물 단위 사람 근거를 특정 타깃 결합의 확증으로 사용")

    summary = (
        "niraparib 은 PARP1 선택적 억제제이고 나노몰 수준 친화도를 갖는다. 응고인자 Xa 결합도 "
        "사람 이상사례 보고로 확증되었으므로 항응고 병용 주의 문안을 즉시 추가할 것을 권고한다.")
    return {"claims": claims, "summary": summary, "planted_overclaims": planted}


def author_output_json(payload: dict[str, Any]) -> str:
    """AuthorOutput 스키마에 담기는 두 키만 남겨 JSON 문자열로 만든다."""
    return json.dumps({"claims": payload.get("claims") or [],
                       "summary": payload.get("summary") or ""},
                      ensure_ascii=False, indent=1)


# ======================================================================================
# 크리틱 3단. 1단과 2단은 (가)와 (나)를 가르지 못한다. 그것이 이 시연의 요지다.
# ======================================================================================
def critic_stage1(payload: dict[str, Any]) -> dict[str, Any]:
    """1단 결정 규칙. ``harness.critic.judge_offline`` 을 그대로 쓴다.

    NAT 를 모듈 import 시점에 끌어오지 않으려고 여기서 지연 import 한다.
    """
    try:
        from harness.critic import judge_offline
    except ImportError as exc:  # pragma: no cover  NAT 미설치 환경
        return {"stage": "decision_rules", "ran": False, "error": f"{type(exc).__name__}: {exc}"}
    report = judge_offline(author_output_json(payload))
    checks = [{"name": c.name, "passed": c.passed, "reason": c.reason} for c in report.checks]
    return {"stage": "decision_rules", "ran": True, "verdict": report.verdict,
            "rules_passed": all(c["passed"] for c in checks), "checks": checks,
            "required_followups": list(report.required_followups)}


def critic_stage2(payload: dict[str, Any], counts: dict[str, Any] | None) -> dict[str, Any]:
    """2단 숫자 오라클. 주장에 적힌 숫자를 고정 로직으로 다시 구해 대조한다."""
    if not counts:
        return {"stage": "numeric_oracle", "ran": False,
                "error": "FAERS 2x2 카운트가 없어 기준값을 만들 수 없었다."}
    try:
        from .pharmasignal_verify import crosscheck_author_output
    except ImportError:
        from pharmasignal_verify import crosscheck_author_output  # type: ignore[no-redef]
    result = crosscheck_author_output(author_output_json(payload), counts)
    out = {"stage": "numeric_oracle", "ran": True, **result.as_dict()}
    out["summary_line"] = result.summary()
    return out


# 3단 규칙은 overclaim_rules.py 가 단일 원본이다. 프롬프트 문장도 그 모듈이 만든다.
_STAGE3_RULES = _ocr.rule_lines()
_STAGE3_PROMPT = _ocr.stage3_prompt(numbers_verified=True)


def critic_stage3(payload: dict[str, Any], *, offline: bool = False,
                  model: str | None = None, base_url: str | None = None,
                  timeout: float = 120.0) -> dict[str, Any]:
    """3단 과잉해석 LLM 판정. 키가 없거나 오프라인이면 건너뛰고 사유를 남긴다."""
    out: dict[str, Any] = {"stage": "overclaim_llm", "ran": False, "skip_reason": None,
                           "model": None, "verdict": None, "checks": [],
                           "required_followups": [], "raw_response": None,
                           "rules": list(_STAGE3_RULES)}
    if offline:
        out["skip_reason"] = "오프라인 모드에서는 LLM 을 부르지 않는다."
        return out
    key = (os.environ.get("NVIDIA_API_KEY") or "").strip()
    if not key:
        out["skip_reason"] = (
            "NVIDIA_API_KEY 가 없어 3단 과잉해석 판정을 돌리지 않았다. 1단과 2단만으로는 "
            "(가)와 (나)가 갈리지 않는다.")
        return out
    model = model or os.environ.get("MODEL_PLANNER") or "nvidia/nemotron-3-super-120b-a12b"
    base_url = base_url or os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    out["model"] = model
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        out["skip_reason"] = f"openai 패키지가 없어 3단을 돌리지 않았다: {exc}"
        return out
    try:
        client = OpenAI(base_url=base_url, api_key=key, timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": _STAGE3_PROMPT},
                      {"role": "user", "content": author_output_json(payload)}],
            temperature=0.2, top_p=0.95, max_tokens=2048,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        text = response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001  네트워크와 인증 실패를 그대로 남긴다
        out["skip_reason"] = f"3단 호출이 실패했다: {type(exc).__name__}: {exc}"
        return out

    out["raw_response"] = text
    try:
        from harness.critic import parse_critic_report
    except ImportError as exc:  # pragma: no cover
        out["skip_reason"] = f"크리틱 파서를 불러오지 못했다: {exc}"
        return out
    report = parse_critic_report(text)
    if report is None:
        out["skip_reason"] = "3단 응답이 CriticReport 형식이 아니어서 판정을 읽지 못했다."
        return out
    out.update({
        "ran": True, "verdict": report.verdict,
        "checks": [{"name": c.name, "passed": c.passed, "reason": c.reason} for c in report.checks],
        "required_followups": list(report.required_followups),
    })
    return out


def judge_claim_set(payload: dict[str, Any], counts: dict[str, Any] | None, *,
                    offline: bool = False, model: str | None = None) -> dict[str, Any]:
    """한 주장 벌에 1단, 2단, 3단을 순서대로 적용하고 최종 판정을 합친다."""
    stage1 = critic_stage1(payload)
    stage2 = critic_stage2(payload, counts)
    stage3 = critic_stage3(payload, offline=offline, model=model)
    if stage1.get("ran") and not stage1.get("rules_passed"):
        final = "reject"
        decided_by = "1단 결정 규칙"
    elif stage2.get("ran") and not stage2.get("ok"):
        final = "reject"
        decided_by = "2단 숫자 오라클"
    elif stage3.get("ran"):
        final = stage3["verdict"]
        decided_by = "3단 과잉해석 LLM 판정"
    else:
        final = "needs_human"
        decided_by = "3단을 돌리지 못해 사람 판단으로 넘김"
    reasons: list[str] = []
    if stage1.get("ran"):
        reasons += [f"1단 {c['name']}: {c['reason']}" for c in stage1["checks"] if not c["passed"]]
    if stage2.get("ran"):
        reasons += [f"2단 {m}" for m in stage2.get("mismatches") or []]
    if stage3.get("ran"):
        reasons += [f"3단 {c['name']}: {c['reason']}" for c in stage3["checks"] if not c["passed"]]
        reasons += [f"3단 후속 조치: {f}" for f in stage3.get("required_followups") or []]
    return {"final_verdict": final, "decided_by": decided_by, "reject_reasons": reasons,
            "stage1": stage1, "stage2": stage2, "stage3": stage3}


# ======================================================================================
# 한 장 브리프. 사람이 읽는다. 표 하나 뒤에 말할 수 있는 것과 말할 수 없는 것을 둔다.
# ======================================================================================
def _cell(lines: list[str]) -> str:
    """표 한 칸. 줄바꿈은 <br> 로 넣고 파이프 문자는 빼서 표가 깨지지 않게 한다."""
    return "<br>".join(line.replace("|", "/") for line in lines if line)


def _code(ids: list[str]) -> str:
    return " ".join(f"`{i}`" for i in ids)


def _structure_cell(step: dict[str, Any]) -> str:
    if not step.get("ok"):
        return _cell([f"실패: {', '.join(step.get('errors') or ['사유 없음'])}"])
    return _cell([
        f"RCSB {step['pdb_id']} 원본 {step['pdb_bytes']:,}바이트, 체인 {'/'.join(step['chains_present'])}",
        f"보낸 것은 chain {step['chain']} ATOM {step['atom_count_chain']:,}줄, "
        f"{step.get('atom_text_bytes', 0):,}바이트",
        f"SHA256 {step['atom_text_sha256'][:16]}...",
        _code(step["evidence_ids"]),
    ])


def _vina_cell(step: dict[str, Any]) -> str:
    if not step.get("ok"):
        return _cell([f"실패: {', '.join(step.get('errors') or ['사유 없음'])}"])
    p = step["protocol"]
    return _cell([
        f"**{step['score_kcal_mol']} {step['units']}**",
        f"role 원문: \"{step['role']}\"",
        f"{p['tool']} {p['version']}, seed {p['seed']}, exhaustiveness {p['exhaustiveness']}, "
        f"num_modes {p['num_modes']}",
        f"박스 중심 {p['box_center']}, 크기 {p['box_size']}",
        f"로그 SHA256 {str(step['sha256'].get('log'))[:16]}...",
        _code(step["evidence_ids"]),
    ])


def _diffdock_cell(step: dict[str, Any]) -> str:
    if step.get("skipped") or not step.get("ok"):
        return _cell([f"건너뜀: {step.get('skip_reason') or '사유 없음'}"])
    conf = ", ".join(f"{c:.3f}" for c in step["position_confidence"])
    return _cell([
        f"포즈 {step['num_poses_returned']}개, position_confidence {conf}",
        f"요청 SHA256 {str(step['request_sha256'])[:16]}...",
        f"응답 SHA256 {str(step['response_sha256'])[:16]}...",
        ("캐시 재생" if step["from_cache"] else f"{step['elapsed_s']}초 실호출"),
        "시드가 없어 호출마다 값이 다르다. 친화도로 환산하지 않는다.",
        _code(step["evidence_ids"]),
    ])


def _bindingdb_cell(step: dict[str, Any]) -> str:
    if not step.get("ok"):
        return _cell([f"실패: {', '.join(step.get('errors') or ['사유 없음'])}"])
    if not step.get("reference_set_present"):
        return _cell(["**참조 집합 없음**", step.get("absent_note") or "",
                      _code(step["evidence_ids"])])
    counts = step["endpoint_counts"]
    return _cell([
        f"{step['target']}, 레코드 {step['record_count']:,}건, 화합물 {step['compound_count']:,}종",
        f"종점별로 Ki {counts.get('Ki'):,}, IC50 {counts.get('IC50'):,}, "
        f"Kd {counts.get('Kd'):,}, EC50 {counts.get('EC50'):,}",
        "네 종점을 하나의 친화도로 합치지 않는다.",
        _code(step["evidence_ids"]),
    ])


def _label_cell(step: dict[str, Any]) -> str:
    pk = step.get("pk") or {}
    values = pk.get("values") or {}
    lines = []
    if step.get("labeled") is None:
        lines.append(f"라벨을 읽지 못했다: {', '.join(step.get('errors') or ['사유 없음'])}")
    else:
        lines.append(f"ZEJULA(niraparib) 라벨, {ADVERSE_EVENT} 기재 "
                     f"**{'있음' if step['labeled'] else '없음'}**")
        lines.append(f"기재 절: {', '.join(section_labels(step['mentioned_sections'])) or '없음'}, "
                     f"본문 {step['mention_count']}곳")
    if pk.get("ok"):
        lines.append(f"{PK_SECTION_NUMBER} 절 PK: 반감기 {_fmt(values.get('half_life_hours'), 0)}시간, "
                     f"생체이용률 {_fmt(values.get('bioavailability_percent'), 0)}퍼센트, "
                     f"혈장단백결합 {_fmt(values.get('plasma_protein_binding_percent'), 0)}퍼센트")
    else:
        lines.append(f"{PK_SECTION_NUMBER} 절을 읽지 못했다: "
                     f"{', '.join(pk.get('errors') or ['사유 없음'])}")
    lines.append(_code(step["evidence_ids"]))
    return _cell(lines)


def _faers_cell(step: dict[str, Any]) -> str:
    if not step.get("ok"):
        return _cell([f"실패: {', '.join(step.get('errors') or ['사유 없음'])}"])
    c = step["counts"]
    return _cell([
        f"2x2: a {c['a']:,}, b {c['b']:,}, c {c['c']:,}, d {c['d']:,}",
        f"PRR {_fmt(step['prr'])} (95% CI {_fmt(step['prr_ci95'][0])} ~ {_fmt(step['prr_ci95'][1])})",
        f"ROR {_fmt(step['ror'])} (95% CI {_fmt(step['ror_ci95'][0])} ~ {_fmt(step['ror_ci95'][1])})",
        f"Yates 보정 카이제곱 {_fmt(step['chi2_yates'])}, Evans 기준 "
        f"{'충족' if step['evans_signal'] else '미충족'}",
        f"데이터 최종 갱신 {step['data_last_updated']}",
        _code(step["evidence_ids"]),
    ])


def _pubmed_cell(step: dict[str, Any]) -> str:
    if not step.get("ok"):
        return _cell([f"실패: {', '.join(step.get('errors') or ['사유 없음'])}"])
    return _cell([
        f"검색어 {step['term']}, 총 {step['total_count']:,}건",
        f"대표 PMID {step['representative_pmid']}: {step['representative_title']}",
        _code(step["evidence_ids"]),
    ])


# 라벨 절 표기. 숫자 순서를 고정해 5절이 6절보다 먼저 오게 한다.
_SECTION_LABELS: list[tuple[str, str]] = [
    ("boxed_warning", "박스 경고"),
    ("warnings_and_precautions", "5절 경고와 주의사항"),
    ("warnings", "경고"),
    ("precautions", "주의사항"),
    ("contraindications", "4절 금기"),
    ("adverse_reactions", "6절 이상반응"),
]


def section_labels(names: list[str]) -> list[str]:
    """라벨 절 이름을 사람이 읽는 표기로 바꾼다. 순서는 라벨 절 번호 순이다."""
    known = [ko for key, ko in _SECTION_LABELS if key in names]
    unknown = [n for n in names if n not in {k for k, _ in _SECTION_LABELS}]
    return known + unknown


_ROW_RENDERERS: list[tuple[str, str, Callable[[dict[str, Any]], str]]] = [
    ("구조", "structure", _structure_cell),
    ("결합 1 (Vina 실측)", "vina", _vina_cell),
    ("결합 2 (DiffDock NIM)", "diffdock", _diffdock_cell),
    ("참조 (BindingDB)", "bindingdb", _bindingdb_cell),
    ("사람 1 (DailyMed 라벨)", "label", _label_cell),
    ("사람 2 (FAERS)", "faers", _faers_cell),
    ("사람 3 (PubMed)", "pubmed", _pubmed_cell),
]


def can_say(case: dict[str, Any]) -> list[str]:
    """말할 수 있는 것. 실제로 값을 받은 단계만 넣는다."""
    a, b = path_by_key(case, "A"), path_by_key(case, "B")
    sa, sb = a["steps"], b["steps"]
    out: list[str] = []
    if sa["vina"]["ok"]:
        out.append(f"경로 A 에서 niraparib 이 PARP1 4R6E chain A 에 대해 Vina "
                   f"{sa['vina']['score_kcal_mol']} kcal/mol 을 받았다는 사실. 단 이 값은 같은 "
                   f"실행 안의 다른 포즈와만 비교한다.")
        out.append(f"그 실행의 프로토콜(seed {sa['vina']['protocol']['seed']}, exhaustiveness "
                   f"{sa['vina']['protocol']['exhaustiveness']}, 박스 좌표)과 로그 SHA256 으로 "
                   f"어느 실행의 값인지 대조할 수 있다는 사실.")
    if sa["diffdock"]["ok"]:
        out.append(f"DiffDock 호출 1회에서 나온 1순위 포즈 신뢰도 "
                   f"{sa['diffdock']['position_confidence'][0]:.3f}. 요청 SHA256 으로 "
                   f"지정되는 이 호출의 결과라는 한정과 함께 쓴다.")
    if sa["bindingdb"]["reference_set_present"]:
        out.append(f"경로 A 에는 사람 PARP1 참조 친화도 집합이 붙어 있고 종점이 Ki, IC50, Kd, "
                   f"EC50 넷으로 나뉘어 있다는 사실.")
    if sa["label"].get("labeled"):
        out.append(f"{ADVERSE_EVENT_KO}이 ZEJULA 라벨에 이미 기재된 알려진 위험이라는 사실과 "
                   f"라벨 {PK_SECTION_NUMBER} 절의 사람 PK 값.")
    if sa["faers"]["ok"]:
        out.append(f"FAERS 2x2 표와 PRR {_fmt(sa['faers']['prr'])}, ROR {_fmt(sa['faers']['ror'])} "
                   f"수치. 그리고 라벨 기재 반응이라 새 신호로 올릴 대상이 아니라는 판정.")
    if sa["pubmed"]["ok"]:
        out.append(f"PubMed 문헌 {sa['pubmed']['total_count']:,}건이 있고 그중 제목에 이 이상사례가 "
                   f"들어간 보고가 있다는 사실.")
    if sb["vina"]["ok"]:
        out.append(f"경로 B 의 Vina 점수 {sb['vina']['score_kcal_mol']} kcal/mol 자체와, FDDD 가 "
                   f"그 조합에 적어 둔 역할이 \"{sb['vina']['role']}\" 이라는 사실.")
    return out


def cannot_say(case: dict[str, Any]) -> list[str]:
    """말할 수 없는 것. 이 파이프라인의 기여가 여기 있다."""
    a, b = path_by_key(case, "A"), path_by_key(case, "B")
    sa, sb = a["steps"], b["steps"]
    score_a = sa["vina"].get("score_kcal_mol")
    score_b = sb["vina"].get("score_kcal_mol")
    out = [
        f"두 점수({score_a}, {score_b})를 견주어 PARP1 선택성을 말하는 것. 서로 다른 단백질이고 "
        f"교차 타깃으로 보정되지 않았다.",
        "Vina 점수나 DiffDock 신뢰도를 Kd, Ki, IC50, EC50 으로 환산하는 것. "
        "NVIDIA 문서 원문이 \"Do not convert confidence directly into binding affinity\" 다.",
        f"경로 B 를 실제 결합으로 말하는 것. FDDD 가 그 조합에 적어 둔 역할은 "
        f"\"{sb['vina'].get('role')}\" 이다.",
        "BindingDB 의 Ki, Kd, IC50, EC50 을 보정과 불확실성 표기 없이 합쳐 단일 친화도로 쓰는 것.",
        "단일 seed 와 exhaustiveness 4 로 나온 점수에 수렴이나 재현성을 말하는 것. DiffDock 은 "
        "호스팅 API 에 시드가 아예 없어 더 강하게 금지된다.",
        "FAERS 불균형 지표를 인과로 말하는 것. 보고 편향과 적응증 교란과 노출 규모 차이가 남는다.",
        "라벨과 FAERS 와 문헌을 경로 B 결합의 사람 쪽 확증으로 쓰는 것. 이 셋은 화합물 단위 "
        "근거이고 타깃을 가리지 않는다.",
        "SMILES 를 실행된 입력이라고 말하는 것. FDDD 의 실행 입력은 준비된 PDBQT 파일이다.",
        "포즈 사이 RMSD 를 결정 구조와의 일치로 말하는 것. FDDD 의 RMSD 열은 같은 실행 안의 포즈끼리 잰 값이다.",
    ]
    if not sb["bindingdb"].get("reference_set_present"):
        out.append("경로 B 에 참조 친화도 집합이 있다고 말하는 것. 이 실행에 붙은 참조 집합은 "
                   "사람 PARP1 하나뿐이다.")
    negative = [c for step in (sa["diffdock"], sb["diffdock"])
                for c in (step.get("position_confidence") or []) if c < 0]
    if negative:
        out.append("DiffDock 신뢰도가 음수로 나온 것을 결합하지 않는다는 증거로 읽는 것. 이 값은 "
                   "포즈가 기하학적으로 맞을 확률에 대한 이진 분류기의 출력이라 낮게 나왔다는 "
                   "뜻이고, 결합 여부를 판정하지 않는다.")
    return out


def _verdict_line(name: str, verdicts: dict[str, Any]) -> list[str]:
    """크리틱 판정 한 벌을 사람이 읽을 줄로 펼친다."""
    s1, s2, s3 = verdicts["stage1"], verdicts["stage2"], verdicts["stage3"]
    lines = [f"**{name}: {verdicts['final_verdict']}** (판정 주체: {verdicts['decided_by']})"]
    if s1.get("ran"):
        lines.append(f"- 1단 결정 규칙: {'통과' if s1['rules_passed'] else '반려'} "
                     f"(점검 {len(s1['checks'])}건)")
    else:
        lines.append(f"- 1단 결정 규칙: 돌리지 못했다. {s1.get('error')}")
    if s2.get("ran"):
        lines.append(f"- 2단 숫자 오라클: {'통과' if s2['ok'] else '반려'}. {s2['summary_line']}")
    else:
        lines.append(f"- 2단 숫자 오라클: 돌리지 못했다. {s2.get('error')}")
    if s3.get("ran"):
        lines.append(f"- 3단 과잉해석 판정({s3['model']}): {s3['verdict']}")
        for check in s3["checks"]:
            if not check["passed"]:
                lines.append(f"  - 반려 사유 원문: {check['name']}: {check['reason']}")
        for followup in s3.get("required_followups") or []:
            lines.append(f"  - 후속 조치 원문: {followup}")
    else:
        lines.append(f"- 3단 과잉해석 판정: 건너뜀. {s3.get('skip_reason')}")
    return lines


def render_brief(case: dict[str, Any], supported: dict[str, Any], overclaim: dict[str, Any],
                 verdicts: dict[str, dict[str, Any]]) -> str:
    """한 장 브리프를 마크다운으로 만든다. em-dash 를 쓰지 않는다."""
    a, b = path_by_key(case, "A"), path_by_key(case, "B")
    mode = "오프라인(캐시 재생)" if case.get("offline") else "온라인"
    diffdock_state = a["steps"]["diffdock"]
    if diffdock_state.get("ok"):
        dd_state = "DiffDock 실행" if not diffdock_state.get("from_cache") else "DiffDock 캐시 재생"
    else:
        dd_state = "DiffDock 건너뜀"

    lines: list[str] = []
    lines.append("# niraparib 한 후보의 두 경로 대조: 도킹에서 사람 근거까지")
    lines.append("")
    lines.append(f"생성 {case['generated_at']}, 실행 모드 {mode}, {dd_state}, "
                 f"화합물 {case['compound']['name']}, 이상사례 {case['compound']['adverse_event']}")
    lines.append("")
    lines.append(f"같은 화합물, 같은 도구, 같은 단계다. 점수 차이는 "
                 f"{abs(float(a['steps']['vina']['score_kcal_mol']) - float(b['steps']['vina']['score_kcal_mol'])):.3f} "
                 f"kcal/mol 인데 한쪽은 말할 수 있고 한쪽은 말할 수 없다.")
    lines.append("")

    lines.append("## 단계별 근거")
    lines.append("")
    lines.append(f"| 단계 | 경로 A: {a['title']} ({a['pdb_id']} chain {a['chain']}) "
                 f"| 경로 B: {b['title']} ({b['pdb_id']} chain {b['chain']}) |")
    lines.append("|---|---|---|")
    for title, key, renderer in _ROW_RENDERERS:
        lines.append(f"| {title} | {renderer(a['steps'][key])} | {renderer(b['steps'][key])} |")
    lines.append("")
    lines.append(f"경로 B 의 체인 선택은 우리 판단이다. {b['chain_note']}")
    lines.append("")
    lines.append("사람 근거 세 줄은 두 경로에 같은 값이 들어간다. 그 셋이 화합물에 붙은 근거이고 "
                 "타깃을 가리지 않기 때문이고, 경로 B 의 공백이 바로 여기서 드러난다.")
    lines.append("")

    lines.append("## 크리틱 판정 두 벌")
    lines.append("")
    lines.append(f"같은 근거로 요약을 두 벌 만들었다. (가)는 주장 {len(supported['claims'])}건, "
                 f"(나)는 주장 {len(overclaim['claims'])}건이고 근거 ID 와 숫자는 양쪽이 같다. "
                 f"(나)에는 과잉해석 {len(overclaim.get('planted_overclaims') or [])}건을 심었다.")
    lines.append("")
    for name, key in (("(가) 뒷받침되는 요약", "supported"), ("(나) 과잉해석을 심은 요약", "overclaim")):
        lines.extend(_verdict_line(name, verdicts[key]))
        lines.append("")
    lines.append("심은 과잉해석 목록: " + ", ".join(overclaim.get("planted_overclaims") or []) + ".")
    lines.append("")

    lines.append("## 말할 수 있는 것")
    lines.append("")
    for item in can_say(case):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 말할 수 없는 것")
    lines.append("")
    for item in cannot_say(case):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 그래서 무엇을 알게 됐는가")
    lines.append("")
    lines.append(
        f"같은 화합물을 같은 도구로 두 번 돌렸는데, PARP1 경로에서는 계산값과 참조 친화도 집합과 "
        f"사람 라벨과 이상사례 보고가 같은 대상을 가리켰고 응고인자 Xa 경로에는 Vina 점수 하나만 "
        f"남았다. 두 경로를 가르는 것은 점수 차이 "
        f"{abs(float(a['steps']['vina']['score_kcal_mol']) - float(b['steps']['vina']['score_kcal_mol'])):.3f} "
        f"kcal/mol 이 아니라 그 점수를 받쳐 줄 실험 근거가 있는지다. "
        f"그 경계를 사람이 매번 기억하지 않아도 되게 근거 ID 로 붙여 두고, 경계를 넘는 주장을 "
        f"크리틱 3단이 반려하게 만든 것이 이 파이프라인의 기여다.")
    lines.append("")
    return "\n".join(lines)
