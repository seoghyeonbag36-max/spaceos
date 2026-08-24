"""[Posting] 3-Tier 입력의 실데이터 서빙 — gold/platform_posting_inputs.json 로드.

`tier_scenarios()` 의 네 입력 중 실데이터가 있는 둘만 교체한다.

| 입력 | 소스 | 상태 |
|---|---|---|
| `rent` 월임대료 | R-ONE 소규모상가 임대료 × 면적 × **층 계수** | ✅ 실데이터 |
| `foot` 유동인구 등급 | 서울 상권분석 유동인구 3분위 + **최근접 상권 유동총량**(실측) | ✅ 실측 |
| `area` 면적 | 없음 — silver `com_area_flr` 은 건물 단위지 유닛 단위가 아니다 | ⬜ 시드 |
| `prem` 권리금 | 없음 — 공개 통계 부재(bronze 전수 확인) | ⬜ 시드 |

## 거점 단위 실데이터를 유닛에 내리는 두 가지 보정

R-ONE 임대료도 flpop 유동인구도 **거점 단위**라, 유닛에 그대로 내리면 거점 안의
구조가 뭉개진다. 둘 다 "실데이터가 절대 수준을, 계수가 거점 내 구조를" 맡는다.

- **rent — 층 계수**: R-ONE 소규모상가 임대료는 사실상 1층 기준이라 상층에 그대로
  곱하면 2~8배 과대계상된다. 근거는 `data/pipelines/build_posting_inputs.py` 참조.
- **foot — 거점 내 상대 위치**: flpop 을 그대로 내리면 한 거점의 모든 유닛이 같은
  등급이 돼 "메인로 vs 이면골목"이 사라진다(가로수길 고/고/중/저/중 → 전부 중).
  그래서 flpop 3분위로 **거점 기준 등급**을 정하고 거점 내에서 ±1칸 이동시킨다.

  그 ±1칸의 근거가 **2026-08-24 에 시드 → 실측으로 바뀌었다.** 거점당 상권이
  1~9곳(중앙 3곳)이라, 유닛 좌표에서 최근접 상권을 잡으면 거점 **내부에서도**
  유동총량이 갈린다. 실측 270유닛 중 **255개(94.4%)** 가 이 경로를 탄다
  (`"flpop+trdar"`) — 51/54거점.

  남은 3거점은 억지로 가르지 않고 시드로 물러난다(`"flpop+seed"`):
  `nokdu`·`garak` 은 상권이 1곳뿐이고, `euljiro` 는 유닛 5개가 300m 안에 몰려
  전부 같은 상권에 배정된다. **가를 수 없는 것을 갈라 놓으면 없는 구조를
  만들어 내는 것**이라 그대로 둔다.

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


# 유닛의 최근접 상권 유동총량이 거점 평균에서 이 비율만큼 벗어나야 ±1칸 움직인다.
# **실측이 아니라 계수다** — 이보다 작은 차이는 '어느 상권에 배정되나'의 경계 노이즈와
# 구분되지 않는다(거점당 상권 1~9곳, 중앙 3곳이라 경계가 굵다).
_TRDAR_EPS = 0.15


def _unit_trdar_flpop(district_id: str, units: list[dict]) -> list[float | None]:
    """유닛별 **최근접 상권의 유동총량**. 좌표나 상권이 없으면 None.

    왜 이걸로 거점 내 서열을 매기나: `foot` 의 거점 등급은 flpop 실측인데, 거점 안의
    유닛 서열은 **손으로 적은 시드**였다(`_blend_foot` 의 `seed_feet`). 그런데 거점당
    상권이 1~9곳(중앙 3곳)이라, 유닛 좌표에서 최근접 상권을 잡으면 **거점 내부에서도
    값이 갈린다** — 시드를 실측으로 바꿀 수 있다.

    ⚠ 상권이 1곳뿐인 거점에서는 모든 유닛이 같은 값이 되어 서열이 안 나온다. 그때는
      호출부가 시드로 물러난다(억지로 갈라 놓으면 없는 구조를 만들어 낸다).

    ⚠ import 를 함수 안에서 한다 — `footfall_layer` → `districts` → `posting_inputs`
      순환을 모듈 최상단 import 로 만들면 앱이 못 뜬다.
    """
    from app.services import footfall_layer

    trdars = footfall_layer.trdars_of(district_id)
    if not trdars:
        return [None] * len(units)

    out: list[float | None] = []
    for u in units:
        lat, lng = u.get("lat"), u.get("lng")
        if lat is None or lng is None:
            out.append(None)
            continue
        t = min(trdars, key=lambda t: (float(t["lat"]) - float(lat)) ** 2
                + (float(t["lng"]) - float(lng)) ** 2)
        v = t.get("flpop_tot")
        out.append(float(v) if v else None)
    return out


def _measured_offsets(vals: list[float | None]) -> list[int] | None:
    """최근접 상권 유동총량 → 거점 내 ±1칸 오프셋. 서열이 안 나오면 None.

    None 을 돌려주는 두 경우 모두 "실측으로 못 가른다" 는 뜻이라 시드로 물러나야 한다:
      - 값이 있는 유닛이 2개 미만
      - 값이 전부 같다(상권 1곳짜리 거점)
    """
    known = [v for v in vals if v is not None]
    if len(known) < 2 or len(set(known)) < 2:
        return None
    mean = sum(known) / len(known)
    if mean <= 0:
        return None
    return [0 if v is None else
            1 if v > mean * (1 + _TRDAR_EPS) else
            -1 if v < mean * (1 - _TRDAR_EPS) else 0
            for v in vals]


def _apply_offset(district_grade: str, offset: int) -> str:
    base = _GRADES.index(district_grade)
    return _GRADES[max(0, min(len(_GRADES) - 1, base + offset))]


def _blend_foot(district_grade: str, seed_foot: str, seed_feet: list[str]) -> str:
    """거점 flpop 등급 + **시드**의 거점 내 상대 위치 → 유닛 등급 (폴백 경로).

    ⚠ 이제 기본 경로가 아니다. 최근접 상권으로 서열을 낼 수 있으면
      `_measured_offsets` 쪽이 돌고, 못 낼 때만(상권 1곳짜리 거점 등) 여기로 온다.

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

    # 거점 내 서열을 **실측(최근접 상권 유동총량)** 으로 매길 수 있는지 먼저 본다.
    # 되면 시드 서열을 쓰지 않는다 — 되지 않을 때만(상권 1곳짜리 거점 등) 물러난다.
    offsets = _measured_offsets(_unit_trdar_flpop(district_id, units))

    out: list[dict] = []
    for i, unit in enumerate(units):
        resolved = {**unit, "inputs_source": dict(seed_src)}
        if rent_per_m2:
            factor = _floor_factor(unit.get("floor", "1F"), data.get("floor_factor"))
            # 시드 rent 와 같은 단위(만원/월): 천원/㎡ × ㎡ ÷ 10
            resolved["rent"] = max(
                1, round(rent_per_m2 * unit["area"] * _PYEONG_TO_M2 * factor / 10))
            resolved["inputs_source"]["rent"] = "rone"
        if district_grade:
            if offsets is not None:
                resolved["foot"] = _apply_offset(district_grade, offsets[i])
                resolved["inputs_source"]["foot"] = "flpop+trdar"
            else:
                resolved["foot"] = _blend_foot(
                    district_grade, unit.get("foot", ""), seed_feet)
                resolved["inputs_source"]["foot"] = "flpop+seed"
        out.append(resolved)
    return out
