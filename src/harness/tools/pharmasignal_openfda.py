"""openFDA FAERS 불균형 분석 도구 (LLM 없이 동작).

엔드포인트: https://api.fda.gov/drug/event.json
문법(공식 문서 https://open.fda.gov/apis/query-syntax/ 확인, 2026-09-24):
- ``search=field:"term"`` , 결합은 ``+AND+``. 공백 포함 구는 따옴표로 묶는다.
- ``.exact`` 접미 필드는 구 전체를 한 값으로 취급한다. 반응명(MedDRA PT)은 정확 일치가
  필요하므로 ``patient.reaction.reactionmeddrapt.exact``를 대문자 PT로 검색한다.
- 약물명은 토큰 일치(``patient.drug.openfda.generic_name:"metformin"``)를 기본으로 해서
  "METFORMIN HYDROCHLORIDE", 복합제 등을 함께 잡는다. ``name_field``로 brand/medicinalproduct 선택.
- 결과 없음은 HTTP 404 ``{"error": {"code": "NOT_FOUND"}}`` 로 온다 → 0건으로 해석.
- 총건수는 ``limit=1`` 조회의 ``meta.results.total``에서 읽는다.

2x2표
- a: 약물+반응, b: 약물+기타반응, c: 기타약물+반응, d: 기타+기타.
- 카운트 쿼리 4개(N, n_drug, n_reaction, a)에서 b=n_drug-a, c=n_reaction-a, d=N-a-b-c.
  FAERS 한 보고에는 여러 약물·반응이 들어가므로 "보고 건수" 기준 표이다.
- PRR = (a/(a+b)) / (c/(c+d)), ROR = (a*d)/(b*c). 95% CI는 로그 스케일 정규근사.
- 카이제곱은 두 가지를 함께 낸다. ``chi2`` 는 보정 없는 Pearson, ``chi2_yates`` 는 Yates
  연속성 보정판이다. Evans 판정(``evans_signal``)은 원 논문 관례대로 Yates 쪽을 쓴다.
- ROR 쪽 판정(``ror_signal``)은 ``pharmasignal_ror`` 오라클이 낸다. 0 셀은 Haldane 0.5
  보정으로 살리고 그 값을 ``ror_haldane`` 에 따로 담는다.

제한(공식 문서 https://open.fda.gov/apis/authentication/): 키 없이 분당 240회, 일 1,000회(IP당).
그래서 (약물, 반응) 쌍별로 원응답을 ``eval/results/pharmasignal_cache_openfda_<hash>.json``에
캐시하고 재실행 시 재사용한다.
"""

from __future__ import annotations

import math
from typing import Any

try:
    from .pharmasignal_common import ResponseCache, http_get, is_error, now_iso, quote
    from .pharmasignal_ror import ror_2x2
except ImportError:  # 스크립트/테스트에서 sys.path로 직접 임포트할 때
    from pharmasignal_common import ResponseCache, http_get, is_error, now_iso, quote
    from pharmasignal_ror import ror_2x2

BASE = "https://api.fda.gov/drug/event.json"
REACTION_FIELD = "patient.reaction.reactionmeddrapt.exact"
NAME_FIELDS = {
    "generic": "patient.drug.openfda.generic_name",
    "brand": "patient.drug.openfda.brand_name",
    "medicinalproduct": "patient.drug.medicinalproduct",
}


def _url(search: str | None) -> str:
    if search:
        return f"{BASE}?search={search}&limit=1"
    return f"{BASE}?limit=1"


def _drug_clause(drug: str, name_field: str) -> str:
    field = NAME_FIELDS[name_field]
    return f'{field}:"{quote(drug.strip().lower())}"'


def _reaction_clause(reaction: str) -> str:
    return f'{REACTION_FIELD}:"{quote(reaction.strip().upper())}"'


def _meta_only(payload: Any) -> Any:
    """limit=1 조회에서 필요한 것은 meta 만이다. 레코드 본문은 캐시에 남기지 않는다."""
    if isinstance(payload, dict) and "meta" in payload:
        return {"meta": payload["meta"]}
    return payload


def _total(payload: Any) -> tuple[int | None, str | None]:
    """meta.results.total 을 읽는다. 404 NOT_FOUND는 0건. 그 외 오류는 (None, 사유)."""
    if isinstance(payload, dict) and "__error__" in payload:
        if payload["__error__"] == 404 and "NOT_FOUND" in str(payload.get("body", "")):
            return 0, None
        return None, f"http_error:{payload['__error__']}"
    if isinstance(payload, dict) and "error" in payload:
        if payload["error"].get("code") == "NOT_FOUND":
            return 0, None
        return None, f"api_error:{payload['error']}"
    try:
        return int(payload["meta"]["results"]["total"]), None
    except (KeyError, TypeError, ValueError):
        return None, "unexpected_payload"


def disproportionality(a: int, b: int, c: int, d: int) -> dict[str, Any]:
    """2x2표에서 PRR, ROR, 카이제곱과 95% CI를 계산한다.

    분모가 0이면 해당 지표는 None. 순수 산술이므로 네트워크가 필요 없다.

    [2026-09-25 선행 프로젝트 대조 후 보강] AgentForgeAI 의 `signal.py` 와 같은 입력으로
    맞춰 보니 **네 칸이 모두 0보다 클 때는 ROR 과 신뢰구간이 소수점 아래 아홉 자리까지
    같았다.** 어긋나는 곳은 두 군데였고 둘 다 여기를 보강해 메웠다.

    1. **0 셀.** 이 함수는 칸이 0이면 ROR 을 None 으로 두고 끝냈다. 그런데 b=0(이 약물의
       보고가 전부 이 반응)이나 c=0(다른 약물에서는 한 건도 없음)은 신호가 가장 강한
       자리다. 그 자리를 통째로 떨어뜨리는 것은 신호 탐지 도구로서 결함이다. 약물감시
       관례대로 네 칸에 0.5 를 더한 Haldane-Anscombe 보정값을 `ror_haldane` 로 따로
       내놓는다. `ror` 자체는 보정 없는 값(0 셀이면 None)으로 그대로 둬서, 보정한 값과
       보정하지 않은 값을 섞어 읽는 일이 없게 한다. v1 은 보정을 적용하고도 그 사실을
       남기지 않았는데 여기서는 `haldane_applied` 로 드러낸다.
    2. **카이제곱.** Evans, Waller, Davis(2001)가 제시한 관례는 a>=3, PRR>=2,
       **Yates 연속성 보정을 한** 카이제곱 >= 4 이다. 이 함수는 보정 없는 Pearson 을 써서
       원 논문보다 살짝 느슨했다(보정을 하면 카이제곱이 작아져 기준이 엄해진다).
       `chi2_yates` 를 더하고 `evans_signal` 의 근거를 그쪽으로 옮겼다. `chi2` 는 보정 없는
       Pearson 그대로 남겨 기존 결과 파일과 이어 읽을 수 있게 했다.
       (실측: 이미 받아 둔 FAERS 케이스 3건에서 Pearson 533148.68 -> Yates 533120.23,
        6823.09 -> 6816.99, 0.6951 -> 0.5755 로 판정은 하나도 뒤집히지 않았다.)
    3. **ROR 신호 기준.** 이 함수에는 ROR 기반 판정이 아예 없었다. ROR 쪽 관례인
       "a>=3 이고 95% CI 하한 > 1"을 `ror_signal` 로 더했다. PRR 계열(Evans)과 ROR 계열은
       서로 다른 관례라 둘 다 내놓고 어긋나는 경우를 사람이 보게 한다.
    """
    out: dict[str, Any] = {"prr": None, "prr_ci95": None, "ror": None, "ror_ci95": None,
                           "chi2": None, "chi2_yates": None}
    if a + b > 0 and c + d > 0 and c > 0:
        prr = (a / (a + b)) / (c / (c + d))
        out["prr"] = prr
        if a > 0:
            se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
            out["prr_ci95"] = [math.exp(math.log(prr) - 1.96 * se), math.exp(math.log(prr) + 1.96 * se)]
    if b > 0 and c > 0 and a > 0 and d > 0:
        ror = (a * d) / (b * c)
        out["ror"] = ror
        se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        out["ror_ci95"] = [math.exp(math.log(ror) - 1.96 * se), math.exp(math.log(ror) + 1.96 * se)]
    n = a + b + c + d
    r1, r2, c1, c2 = a + b, c + d, a + c, b + d
    if n > 0 and r1 and r2 and c1 and c2:
        out["chi2"] = n * (a * d - b * c) ** 2 / (r1 * r2 * c1 * c2)
        # Yates 연속성 보정. |ad-bc| 에서 n/2 를 빼고 음수면 0으로 막는다.
        yates_num = max(abs(a * d - b * c) - n / 2, 0.0)
        out["chi2_yates"] = n * yates_num ** 2 / (r1 * r2 * c1 * c2)

    # Evans, Waller, Davis(2001) 관례: a>=3, PRR>=2, Yates 보정 카이제곱 >=4
    out["evans_signal"] = bool(
        a >= 3 and (out["prr"] or 0) >= 2 and (out["chi2_yates"] or 0) >= 4)

    # ROR 계열 관례: a>=3 이고 95% CI 하한 > 1. 0 셀은 Haldane 0.5 보정으로 살린다.
    corrected = ror_2x2(a, b, c, d, haldane=True)
    out["ror_haldane"] = corrected["ror"]
    out["ror_ci95_haldane"] = (None if corrected["ror"] is None
                               else [corrected["ci_low"], corrected["ci_high"]])
    out["haldane_applied"] = corrected["haldane_applied"]
    out["ror_signal"] = corrected["is_signal"]
    return out


def faers_disproportionality(drug: str, reaction: str, name_field: str = "generic",
                             use_cache: bool = True) -> dict[str, Any]:
    """약물명과 MedDRA PT를 받아 FAERS 2x2표와 PRR/ROR/카이제곱을 돌려준다.

    반환(JSON 직렬화 가능):
      drug, reaction, name_field, counts{a,b,c,d,n_drug,n_reaction,n_total},
      prr, prr_ci95, ror, ror_ci95, chi2, chi2_yates, evans_signal,
      ror_haldane, ror_ci95_haldane, haldane_applied, ror_signal,
      query_urls{a,n_drug,n_reaction,n_total}, evidence_ids(=쿼리 URL 목록),
      errors[], data_last_updated, retrieved_at, cache{path,hits,misses}
    """
    if name_field not in NAME_FIELDS:
        raise ValueError(f"name_field must be one of {sorted(NAME_FIELDS)}")
    cache = ResponseCache("openfda", f"{drug.strip().lower()}|{reaction.strip().upper()}|{name_field}",
                          enabled=use_cache)
    dc, rc = _drug_clause(drug, name_field), _reaction_clause(reaction)
    urls = {
        "n_total": _url(None),
        "n_drug": _url(dc),
        "n_reaction": _url(rc),
        "a": _url(f"{dc}+AND+{rc}"),
    }
    totals: dict[str, int | None] = {}
    errors: list[str] = []
    last_updated = None
    for key, url in urls.items():
        payload = http_get(url, cache=cache, is_json=True, reduce=_meta_only)
        if isinstance(payload, dict) and isinstance(payload.get("meta"), dict):
            last_updated = payload["meta"].get("last_updated", last_updated)
        total, err = _total(payload)
        totals[key] = total
        if err:
            errors.append(f"{key}: {err}")
    result: dict[str, Any] = {
        "tool": "openfda_faers",
        "drug": drug, "reaction": reaction, "name_field": name_field,
        "counts": None, "prr": None, "prr_ci95": None, "ror": None, "ror_ci95": None,
        "chi2": None, "chi2_yates": None, "evans_signal": None,
        "ror_haldane": None, "ror_ci95_haldane": None, "haldane_applied": None,
        "ror_signal": None,
        "query_urls": urls, "evidence_ids": list(urls.values()),
        "errors": errors, "data_last_updated": last_updated, "retrieved_at": now_iso(),
        "cache": {"path": str(cache.path), "hits": cache.hits, "misses": cache.misses},
    }
    if any(v is None for v in totals.values()):
        return result
    a = totals["a"]
    b = totals["n_drug"] - a
    c = totals["n_reaction"] - a
    d = totals["n_total"] - a - b - c
    result["counts"] = {"a": a, "b": b, "c": c, "d": d, "n_drug": totals["n_drug"],
                        "n_reaction": totals["n_reaction"], "n_total": totals["n_total"]}
    result.update(disproportionality(a, b, c, d))
    return result


# ======================================================================================
# NAT 등록 래퍼 (openfda_faers). 위 계산 로직과 기존 함수는 그대로 두고 감싸기만 한다.
#
# 패턴은 src/harness/register.py 의 prr_calculator 를 그대로 따른다.
#   FunctionBaseConfig(name=...)  -> YAML 의 _type 값
#   @register_function            -> NAT 레지스트리 등록 (import 시점에 발동)
#   FunctionInfo.from_fn(fn, description=..., converters=[모델 -> str])
# register.py 하단의 "도메인 도구 import" 블록이 이 모듈을 import 해야 등록이 실린다.
# ======================================================================================
import asyncio  # noqa: E402
import os  # noqa: E402

from pydantic import BaseModel  # noqa: E402
from pydantic import ConfigDict  # noqa: E402
from pydantic import Field  # noqa: E402

from nat.builder.builder import Builder  # noqa: E402
from nat.builder.function_info import FunctionInfo  # noqa: E402
from nat.cli.register_workflow import register_function  # noqa: E402
from nat.data_models.function import FunctionBaseConfig  # noqa: E402


class FaersReport(BaseModel):
    """openfda_faers 의 출력 스키마. `faers_disproportionality` 반환 dict 를 그대로 담는다.

    지표가 늘어도 도구가 깨지지 않게 extra 필드를 허용한다.
    """

    model_config = ConfigDict(extra="allow")

    tool: str = "openfda_faers"
    drug: str
    reaction: str
    name_field: str
    counts: dict[str, int] | None = Field(
        default=None, description="2x2 table cells a,b,c,d plus n_drug, n_reaction, n_total")
    prr: float | None = Field(default=None, description="Proportional Reporting Ratio")
    prr_ci95: list[float] | None = None
    ror: float | None = Field(default=None, description="Reporting Odds Ratio, uncorrected")
    ror_ci95: list[float] | None = None
    chi2: float | None = Field(default=None, description="Pearson chi-square, no continuity correction")
    chi2_yates: float | None = Field(default=None, description="Yates corrected chi-square, used by the Evans rule")
    evans_signal: bool | None = Field(default=None, description="Evans 2001 rule: a>=3, PRR>=2, Yates chi-square>=4")
    ror_haldane: float | None = Field(default=None, description="ROR with Haldane-Anscombe 0.5 correction")
    ror_ci95_haldane: list[float] | None = None
    haldane_applied: bool | None = None
    ror_signal: bool | None = Field(default=None, description="ROR rule: a>=3 and lower 95% CI bound > 1")
    query_urls: dict[str, str] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list,
                                   description="openFDA query URLs. Cite one of these for every claim.")
    errors: list[str] = Field(default_factory=list)
    data_last_updated: str | None = None
    retrieved_at: str | None = None
    cache: dict[str, Any] | None = None


class OpenFdaFaersConfig(FunctionBaseConfig, name="openfda_faers"):
    """openFDA FAERS 불균형 분석 도구. 설정값은 약물명 매칭 필드와 캐시뿐이다."""

    name_field: str = Field(default="generic",
                            description="약물명 매칭 필드. generic, brand, medicinalproduct 중 하나.")
    use_cache: bool = Field(default=True,
                            description="원응답 파일 캐시 사용 여부. 키 없이 분당 240회, 일 1,000회 제한을 아낀다.")
    cache_dir: str | None = Field(default=None, description="캐시 디렉터리. 비우면 eval/results 를 쓴다.")


@register_function(config_type=OpenFdaFaersConfig)
async def openfda_faers(config: OpenFdaFaersConfig, _builder: Builder):
    if config.name_field not in NAME_FIELDS:
        raise ValueError(f"name_field 는 {sorted(NAME_FIELDS)} 중 하나여야 합니다: {config.name_field!r}")
    if config.cache_dir:
        os.environ["PHARMASIGNAL_CACHE_DIR"] = config.cache_dir

    async def _faers(drug: str, reaction: str) -> FaersReport:
        """Query openFDA FAERS for one drug and one adverse event and return signal statistics.

        drug: ingredient or product name, for example "metformin".
        reaction: MedDRA preferred term, for example "Lactic acidosis".
        Returns the 2x2 report counts (a, b, c, d), PRR and ROR with 95% confidence intervals,
        Pearson and Yates chi-square, the Evans signal rule, the Haldane corrected ROR, and
        evidence_ids holding the exact openFDA query URLs. Cite one of those URLs in every claim
        built from these numbers. No matching report is returned as a zero count, not as an error;
        when errors is non-empty the counts are missing and no claim may be made.
        """
        raw = await asyncio.to_thread(faers_disproportionality, drug, reaction,
                                      config.name_field, config.use_cache)
        return FaersReport.model_validate(raw)

    def _report_to_str(report: FaersReport) -> str:
        """도구 출력이 문자열을 요구하는 경로(콘솔, 일부 도구 래퍼)용 변환기."""
        return report.model_dump_json()

    yield FunctionInfo.from_fn(_faers, description=_faers.__doc__, converters=[_report_to_str])


if __name__ == "__main__":  # 수동 점검용
    import json
    import sys

    drug_arg = sys.argv[1] if len(sys.argv) > 1 else "metformin"
    reaction_arg = sys.argv[2] if len(sys.argv) > 2 else "Lactic acidosis"
    print(json.dumps(faers_disproportionality(drug_arg, reaction_arg), indent=1, ensure_ascii=False))
