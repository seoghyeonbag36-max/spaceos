"""[Posting] 3-Tier 입력의 실데이터 서빙 — gold/platform_posting_inputs.json 로드.

`tier_scenarios()` 의 네 입력 중 실데이터가 있는 둘만 교체한다.

| 입력 | 소스 | 상태 |
|---|---|---|
| `rent` 월임대료 | R-ONE 소규모상가 임대료 × 면적 × **층 계수** | ✅ 실데이터 |
| `foot` 유동인구 등급 | 서울 상권분석 유동인구 3분위 + **시드의 거점 내 상대 위치** | ◐ 혼합 |
| `area` 면적 | 없음 — silver `com_area_flr` 은 건물 단위지 유닛 단위가 아니다 | ⬜ 시드 |
| `prem` 권리금 | 없음 — 공개 통계 부재(bronze 전수 확인) | ⬜ 시드 |

## 거점 단위 실데이터를 유닛에 내리는 두 가지 보정

R-ONE 임대료도 flpop 유동인구도 **거점 단위**라, 유닛에 그대로 내리면 거점 안의
구조가 뭉개진다. 둘 다 "실데이터가 절대 수준을, 계수가 거점 내 구조를" 맡는다.

- **rent — 층 계수**: R-ONE 소규모상가 임대료는 사실상 1층 기준이라 상층에 그대로
  곱하면 2~8배 과대계상된다. 근거는 `data/pipelines/build_posting_inputs.py` 참조.
- **foot — 거점 내 상대 위치**: flpop 을 그대로 내리면 한 거점의 모든 유닛이 같은
  등급이 돼 "메인로 vs 이면골목"이 사라진다(가로수길 고/고/중/저/중 → 전부 중).
  그래서 flpop 3분위로 **거점 기준 등급**을 정하고, 시드가 그 유닛에 준 등급이
  거점 평균보다 높/낮은지로 ±1칸 이동시킨다. 절대 수준은 실데이터, 거점 내 서열은
  시드 — 그래서 이 필드는 `"flpop+seed"` 로 표기한다(순수 실측이 아니다).

**두 보정 모두 실측이 아니라 계수다.** 프록시를 실측으로 오독하면 안 되므로
`inputs_source` 로 필드별 출처를 항상 함께 내려보낸다.

파이프라인이 pandas 로 만든 결과를 여기서는 정적 JSON 으로만 읽는다
(Vercel 서버리스에 pandas 를 싣지 않는다 — vacancy_forecast 와 같은 이유).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# repo/data/gold  (services → app → backend → apps → repo)
_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_INPUTS_JSON = _GOLD / "platform_posting_inputs.json"
_TTL_SECONDS = 300.0

# 층 계수 — build_posting_inputs._FLOOR_FACTOR 와 동일하게 유지할 것.
# 산출 JSON 의 floor_factor 를 우선 쓰고, 없을 때만 이 값으로 떨어진다.
_FALLBACK_FLOOR_FACTOR: dict[str, float] = {
    "B2": 0.60, "B1": 0.75, "1F": 1.00, "2F": 0.45, "3F": 0.40,
}
_FALLBACK_HIGH = 0.30
_PYEONG_TO_M2 = 3.3058

_cache: dict[str, Any] = {}


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - _cache.get("at", 0.0) < _TTL_SECONDS:
        return _cache["data"]
    if not _INPUTS_JSON.exists():
        return None
    _cache["data"] = json.loads(_INPUTS_JSON.read_text(encoding="utf-8"))
    _cache["at"] = now
    return _cache["data"]


def is_available() -> bool:
    """Posting 실데이터 입력이 적재돼 있는가."""
    return _load() is not None


def quarter() -> str | None:
    """실데이터의 기준 분기 (예: "20261")."""
    data = _load()
    return data.get("quarter") if data else None


def _floor_factor(floor: str, table: dict[str, float] | None) -> float:
    """유닛 층 라벨 → 임대료 계수. 모르는 라벨은 1층으로 본다(과소계상보다 안전)."""
    f = (floor or "").strip().upper()
    tbl = table or _FALLBACK_FLOOR_FACTOR
    if f in tbl:
        return float(tbl[f])
    if f.endswith("F") and f[:-1].isdigit() and int(f[:-1]) >= 4:
        return float((table or {}).get("4F+", _FALLBACK_HIGH))
    return float(tbl.get("1F", 1.0))


def for_district(district_id: str) -> dict | None:
    """거점의 실데이터 입력. 미적재·미지원 거점이면 None(→ 시드 프록시 유지)."""
    data = _load()
    if not data:
        return None
    return (data.get("districts") or {}).get(district_id)


_GRADES = ("저", "중", "고")
# 시드 등급이 거점 평균에서 이만큼 떨어져야 ±1칸 움직인다. 0.25 는 5유닛 거점에서
# "한 유닛만 튀는" 정도를 잡되 반올림 노이즈로는 안 움직이는 폭이다.
_RANK_EPS = 0.25


def _blend_foot(district_grade: str, seed_foot: str, seed_feet: list[str]) -> str:
    """거점 flpop 등급(절대 수준) + 시드의 거점 내 상대 위치(메인/이면) → 유닛 등급.

    flpop 만 쓰면 한 거점의 모든 유닛이 같은 등급이 돼 거점 내 구조가 사라진다.
    시드만 쓰면 거점 간 수준이 손으로 적은 값이다. 둘을 합친다.
    """
    if district_grade not in _GRADES or seed_foot not in _GRADES:
        return seed_foot
    base = _GRADES.index(district_grade)
    seed_idx = _GRADES.index(seed_foot)
    mean_idx = sum(_GRADES.index(f) for f in seed_feet if f in _GRADES) / max(1, len(seed_feet))
    offset = 1 if seed_idx > mean_idx + _RANK_EPS else -1 if seed_idx < mean_idx - _RANK_EPS else 0
    return _GRADES[max(0, min(len(_GRADES) - 1, base + offset))]


def resolve_units(district_id: str, units: list[dict]) -> list[dict]:
    """거점 유닛들의 3-Tier 입력을 실데이터로 덮어쓴다. 미적재면 시드 그대로.

    **유닛 하나가 아니라 목록을 받는다** — `foot` 보정이 거점 내 상대 위치를 쓰므로
    같은 거점의 다른 유닛을 봐야 한다.

    반환은 `tier_scenarios()` 가 받는 것과 같은 모양의 **새 dict** 다(시드 원본은
    건드리지 않는다 — seoul_pages.DISTRICTS 는 프로세스 전역에서 공유된다).
    `inputs_source` 로 필드별 출처를 함께 싣는다: 프록시를 실측으로 오독하면 안 된다.
    """
    seed_src = {"area": "seed", "rent": "seed", "prem": "seed", "foot": "seed"}
    row = for_district(district_id)
    if not row:
        return [{**u, "inputs_source": dict(seed_src)} for u in units]

    data = _load() or {}
    rent_per_m2 = row.get("rent_per_m2_krw_thousand")
    district_grade = row.get("foot")
    seed_feet = [u.get("foot", "") for u in units]

    out: list[dict] = []
    for unit in units:
        resolved = {**unit, "inputs_source": dict(seed_src)}
        if rent_per_m2:
            factor = _floor_factor(unit.get("floor", "1F"), data.get("floor_factor"))
            # 시드 rent 와 같은 단위(만원/월): 천원/㎡ × ㎡ ÷ 10
            resolved["rent"] = max(
                1, round(rent_per_m2 * unit["area"] * _PYEONG_TO_M2 * factor / 10))
            resolved["inputs_source"]["rent"] = "rone"
        if district_grade:
            resolved["foot"] = _blend_foot(district_grade, unit.get("foot", ""), seed_feet)
            resolved["inputs_source"]["foot"] = "flpop+seed"
        out.append(resolved)
    return out
