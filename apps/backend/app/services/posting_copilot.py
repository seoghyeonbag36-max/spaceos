"""외부 AI 창업 코파일럿 어댑터 — 계약(contract)과 정규화 (2026-08-23).

## 왜 우리가 명세를 쓰는가

이 자리는 2026-07-18 부터 "외부 코파일럿의 입출력 명세 확보"를 기다리며 비어 있었다.
공급자가 정해지지 않았으므로 기다리는 한 영원히 비어 있다. 그래서 **방향을 뒤집는다 —
SpaceOS 가 계약을 발행하고 공급자가 여기에 맞춘다.** 어댑터는 오늘 구현되고, 계약을
그대로 흉내내는 가짜 서버로 오늘 검증된다. 공급자가 정해지면 URL 만 채우면 된다.

계약이 우리 것이라 얻는 더 중요한 것: **무엇을 공급자에게 맡기고 무엇을 안 맡길지**를
우리가 정한다. 아래 표가 그 경계다.

## 계약 v1

요청 — ``POST {posting_copilot_url}/simulate``, ``Authorization: Bearer {key}``

    {"contract": "spaceos.posting/1",
     "district_id": "garosugil",
     "industry_type": "cafe" | null,
     "unit": {"id": "...", "area": 60, "rent": 850, "prem": 3000,
              "floor": "1F", "foot": "고"},
     "units": {"area": "m2", "rent": "manwon_per_month", "prem": "manwon",
               "invest_mn": "million_krw", "month_cost": "manwon_per_month",
               "month_rev": "manwon_per_month"}}

응답

    {"contract": "spaceos.posting/1",
     "scenarios": [{"tier": "premium", "invest_mn": 37.0, "month_cost": 1288.0,
                    "month_rev": 4225.0, "basis": "rent+fitout+cogs+labor"}, ...]}

``units`` 를 요청에 실어 보내는 것은 예의가 아니라 **방어**다. 이 코드베이스는 단위
때문에 이미 틀린 적이 있다(회수기간 100배 축소 — districts.tier_scenarios 참조).

## 경계 — 공급자가 주는 것 / 우리가 정하는 것

| 필드 | 누가 | 왜 |
|---|---|---|
| `invest_mn`·`month_cost`·`month_rev` | **공급자** | 이걸 받으려고 붙이는 것이다 |
| `basis` | **공급자** | 어떤 비용 항목까지 넣었는지 안 밝히면, 그 값이 우리 미보정 계산보다 나은지 판단할 방법이 없다 |
| `month_net`·`roi_months`·`viable` | **우리** | 파생값이다. 공급자가 준 것을 믿으면 단위 실수와 '회수 불가' 표식(99.0)의 정의가 공급자마다 갈린다 |
| `recommended` | **우리** | 추천 기준(회수 최단)은 **제품 정의**다(districts.recommend_tier). 공급자가 바꿀 수 있으면 그건 우리 제품이 아니다 |
| `name`·`sub` | **우리** | 화면에 나가는 우리 라벨이다 |

## 부분 채용은 하지 않는다

세 tier 중 하나라도 계약을 어기면 **응답 전체를 버리고 폴백**한다. 둘은 코파일럿,
하나는 폴백인 시나리오 표는 비교표가 아니다 — 같은 자를 안 쓴 값을 나란히 놓으면
읽는 사람이 그걸 비교로 오독한다.

의존성은 표준 라이브러리만 쓴다 — Vercel 서버리스 의존성이 fastapi/pydantic 뿐이라
httpx 를 쓰면 프로덕션에서만 죽는다(services/store_lookup 과 같은 이유).
"""
from __future__ import annotations

import json
import math
import socket
import urllib.error
import urllib.request

from app.core.config import settings

CONTRACT = "spaceos.posting/1"
_TIMEOUT_S = 8

# 요청에 실어 보내는 단위표. 공급자가 이걸 무시하고 틀리면 아래 상한에 걸린다.
UNITS = {
    "area": "m2",
    "rent": "manwon_per_month",
    "prem": "manwon",
    "invest_mn": "million_krw",
    "month_cost": "manwon_per_month",
    "month_rev": "manwon_per_month",
}

# 단위 착오 탐지용 상한. 값의 타당성을 재는 게 아니라 **자릿수 사고**를 잡는 것이다.
# 상가 한 칸의 시뮬레이션이므로 투자 1,000억·월매출 100억은 단위가 틀린 것이다.
_MAX_INVEST_MN = 100_000       # 백만원 → 1,000억
_MAX_MANWON_MONTH = 1_000_000  # 만원/월 → 100억/월

_REQUIRED = ("invest_mn", "month_cost", "month_rev")

# 공급자가 basis 를 안 밝혔을 때 채우는 값. 숨기지 않고 모른다고 적는다.
BASIS_UNKNOWN = "unknown(copilot)"


class ContractError(ValueError):
    """코파일럿 응답이 계약 v1 을 어겼다. 메시지가 그대로 `source_note` 로 나간다."""


def _fail(msg: str) -> None:
    raise ContractError(msg)


def request_body(district_id: str, unit: dict, industry_type: str | None) -> dict:
    """계약 v1 요청 바디. 유닛에서 **시뮬레이션 입력만** 뽑는다.

    시드 서술 필드(`rec`·`was`·`n`)는 보내지 않는다 — `rec` 은 기준이 정의된 적 없는
    손으로 적은 값이었고(districts.recommend_tier), 실제 건물에서 뽑은 유닛에는 아예
    없다. 공급자가 그걸 읽고 답을 바꾸면 배선이 다시 시드에 묶인다.
    """
    return {
        "contract": CONTRACT,
        "district_id": district_id,
        "industry_type": industry_type,
        "unit": {
            "id": unit["id"],
            "area": unit["area"],
            "rent": unit["rent"],
            "prem": unit["prem"],
            "floor": unit.get("floor"),
            "foot": unit.get("foot"),
        },
        "units": UNITS,
    }


def _number(raw: object, field: str, tier: str, cap: float) -> float:
    """수치 하나를 검증해 float 로. bool 은 int 의 하위형이라 명시적으로 막는다."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        _fail(f"{tier}.{field} 가 수치가 아니다: {raw!r}")
    val = float(raw)
    if not math.isfinite(val):
        _fail(f"{tier}.{field} 가 유한값이 아니다: {val!r}")
    if val < 0:
        _fail(f"{tier}.{field} 가 음수다: {val}")
    if val > cap:
        _fail(f"{tier}.{field}={val:g} 가 상한 {cap:g} 초과 — 단위 착오로 본다"
              f" ({UNITS[field]} 기준)")
    return val


def normalize(payload: object, tiers: dict) -> dict:
    """코파일럿 응답 → tier_scenarios 와 같은 모양의 dict.

    `tiers` 는 districts.TIER (우리 라벨). 파생값은 여기서 계산하고, `_raw` 에 반올림
    전 원값을 실어 recommend_tier 가 반올림 동률에 걸리지 않게 한다 — 폴백 쪽에서
    실 유닛 270건 중 14건을 뒤집던 함정이라 어댑터도 같은 방어를 한다.
    계약 위반은 ContractError 로 올린다(호출부가 폴백으로 떨어뜨린다).
    """
    if not isinstance(payload, dict):
        _fail(f"응답이 객체가 아니다: {type(payload).__name__}")
    got = payload.get("contract")
    if got != CONTRACT:
        _fail(f"contract 불일치 — 기대 {CONTRACT!r}, 받음 {got!r}")

    rows = payload.get("scenarios")
    if not isinstance(rows, list):
        _fail(f"scenarios 가 배열이 아니다: {type(rows).__name__}")

    by_tier: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            _fail(f"scenarios 원소가 객체가 아니다: {type(row).__name__}")
        tier = row.get("tier")
        if tier not in tiers:
            _fail(f"모르는 tier: {tier!r} (허용: {', '.join(tiers)})")
        if tier in by_tier:
            _fail(f"tier 중복: {tier}")
        by_tier[tier] = row

    missing = [t for t in tiers if t not in by_tier]
    if missing:
        # 부분 채용 금지 — 모듈 docstring 참조.
        _fail(f"tier 누락: {', '.join(missing)} — 3전략이 모두 있어야 비교가 성립한다")

    out: dict[str, dict] = {}
    for tier in tiers:
        row = by_tier[tier]
        for f in _REQUIRED:
            if f not in row:
                _fail(f"{tier}.{f} 없음")
        inv = _number(row["invest_mn"], "invest_mn", tier, _MAX_INVEST_MN)
        cost = _number(row["month_cost"], "month_cost", tier, _MAX_MANWON_MONTH)
        rev = _number(row["month_rev"], "month_rev", tier, _MAX_MANWON_MONTH)

        # 파생값은 우리가 계산한다 — 공급자가 준 net/roi 는 읽지도 않는다.
        # 단위 정합(투자=백만원, 순익=만원/월)은 tier_scenarios 와 동일하게 ×100.
        net = rev - cost
        roi = float("inf") if net <= 0 else inv * 100 / net

        basis = row.get("basis")
        if not isinstance(basis, str) or not basis.strip():
            basis = BASIS_UNKNOWN
        out[tier] = {
            "tier": tier, "name": tiers[tier]["nm"], "sub": tiers[tier]["sub"],
            "invest_mn": round(inv), "month_cost": round(cost), "month_rev": round(rev),
            "month_net": round(net), "roi_months": 99.0 if net <= 0 else round(roi, 1),
            "viable": net > 0,
            "basis": basis.strip(),
            "_raw": {"invest_mn": inv, "cost": cost, "rev": rev, "net": net, "roi": roi},
        }
    return out


def fetch(district_id: str, unit: dict, industry_type: str | None) -> dict:
    """코파일럿 호출 → 원시 JSON. 실패는 ContractError 로 올린다(호출부가 폴백)."""
    base = settings.posting_copilot_url.rstrip("/")
    body = json.dumps(request_body(district_id, unit, industry_type)).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.posting_copilot_key:
        headers["Authorization"] = f"Bearer {settings.posting_copilot_key}"
    req = urllib.request.Request(f"{base}/simulate", data=body, headers=headers,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        _fail(f"코파일럿 HTTP {exc.code}")
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        _fail(f"코파일럿 연결 실패: {exc}")
    except (ValueError, UnicodeDecodeError) as exc:
        _fail(f"코파일럿 응답이 JSON 이 아니다: {exc}")
    return {}  # 도달 불가 — _fail 이 항상 올린다. 타입체커용.
