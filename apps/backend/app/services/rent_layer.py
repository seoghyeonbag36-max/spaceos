"""[Page] 임대시세 레이어 — **격자 색이 아니라 "이 빈 층이 월 얼마인가"** 를 낸다.

## 왜 바꿨나 (2026-09-13)

종전 응답은 공실 히트맵과 같은 100m 격자에 **최근접 공실 유닛의 평당 임대료**를 칠한
셀 목록이었다. 문제가 둘이었다.

1. **숫자가 안 보였다.** 화면은 셀을 5단계 초록으로 칠했을 뿐이라 사용자는 "진한 곳이
   비싸다"만 알고 "그래서 얼마냐"는 알 수 없었다.
2. **격자가 없는 구조를 그렸다.** R-ONE 소규모상가 임대료는 **거점(상권) 단위 값 하나**다.
   셀마다 달라 보이던 차이는 최근접 유닛의 층 계수 차이였을 뿐, 공간 구조가 아니었다.

그래서 값이 실제로 갈리는 축 — **층과 면적** — 으로 내려간다:

- `floors`   거점의 층별 평당 월임대료 표 (R-ONE 1층 기준 × 층 계수)
- `listings` 층 단위 공실 매물(`vacant_floor_units.json`)마다 **추정 월임대료(만원/월)**

## 식

    월임대료(만원) = R-ONE 임대료(천원/㎡·월) × 그 층의 대장 면적(㎡) × 층 계수 ÷ 10

`posting_inputs.resolve_units` 의 `rent` 와 **같은 식**이다(거기는 호실당 평균 면적,
여기는 그 층 전체 면적). 두 화면이 같은 자리에 다른 금액을 내면 안 된다.

## 이 값이 아닌 것

- **호가·실거래가가 아니다.** R-ONE 표본 평균에 층 계수를 곱한 추정이다. 층 계수는
  실측이 아니라 계수다(`posting_inputs` 독스트링 참조).
- **보증금·권리금·관리비가 없다.** R-ONE 소규모상가 임대료는 월 임대료만 준다.
- **한 층에 호실이 여럿이면 그 층 전체 금액이다** — 층별개요 면적이 층 단위라 호실로
  못 내려간다(`floor_vacancy` 독스트링 · docs/feature-posting.md §0-R·§0-S).

R-ONE 이 없는 거점은 None(→ 404) — 이웃 거점 값이나 0 으로 채우지 않는다.
"""
from __future__ import annotations

from app.services import floor_vacancy, posting_inputs

_PYEONG_TO_M2 = 3.3058

# 층 표에 싣는 줄. 매물이 없는 층이라도 기준표로는 보여 준다 — "2층이면 평당 얼마"는
# 매물 유무와 무관하게 입점 기업이 먼저 묻는 값이다.
_FLOOR_ROWS = ("B1", "1F", "2F", "3F", "4F+")


def _per_pyeong(rent_per_m2: float, factor: float) -> float:
    """천원/㎡·월 × 계수 → 만원/평·월 (소수 첫째 자리)."""
    return round(rent_per_m2 * _PYEONG_TO_M2 * factor / 10, 1)


def _monthly(rent_per_m2: float, area_m2: float, factor: float) -> int:
    """천원/㎡·월 × ㎡ × 계수 → 만원/월 (정수). 1만원 미만으로 떨어뜨리지 않는다."""
    return max(1, round(rent_per_m2 * area_m2 * factor / 10))


def rent_heatmap(district_id: str) -> dict | None:
    """거점의 층별 평당 임대료 표 + 층 단위 공실 매물의 추정 월임대료.

    엔드포인트 이름(`/heatmap/rent`)은 프론트 계약이라 그대로 두었다. 응답에 더 이상
    격자(`cells`)는 없다 — 위 독스트링의 "왜 바꿨나" 참조.
    """
    row = posting_inputs.for_district(district_id)
    rent_per_m2 = (row or {}).get("rent_per_m2_krw_thousand")
    if not rent_per_m2:
        return None

    shared = posting_inputs.is_shared_rone(district_id)
    floors = [
        {
            "floor": label,
            "factor": posting_inputs.floor_factor(label),
            "rent_per_pyeong": _per_pyeong(rent_per_m2, posting_inputs.floor_factor(label)),
        }
        for label in _FLOOR_ROWS
    ]

    inventory = floor_vacancy.load(district_id)
    listings: list[dict] = []
    for u in (inventory or {}).get("units") or []:
        area_m2 = u.get("area_m2")
        lat, lng = u.get("lat"), u.get("lng")
        if not area_m2 or lat is None or lng is None:
            # 면적이 없으면 금액이 성립하지 않는다 — 평당 값으로 대신 채우지 않는다.
            continue
        label = u.get("floor_label") or ""
        factor = posting_inputs.floor_factor(label)
        listings.append({
            "id": u.get("id"),
            "building_id": u.get("building_id"),
            "name": u.get("n"),
            "lat": lat, "lng": lng,
            "floor": u.get("floor"),
            "floor_label": label,
            "certainty": u.get("certainty"),
            "area_py": u.get("area"),
            "area_m2": area_m2,
            "factor": factor,
            "rent_per_pyeong": _per_pyeong(rent_per_m2, factor),
            "monthly_rent": _monthly(rent_per_m2, area_m2, factor),
        })

    monthly = [x["monthly_rent"] for x in listings]
    return {
        "district": district_id,
        # 인접·포괄 상권의 표본을 빌려 쓰는 거점은 라벨로 가른다 — 빌린 값을 실측처럼
        # 보이게 하지 않는다(posting_inputs 와 같은 규칙).
        "rent_source": "rone-shared" if shared else "rone",
        "quarter": posting_inputs.quarter(),
        "unit": "만원/평",
        "monthly_unit": "만원/월",
        "base_rent_per_m2_krw_thousand": rent_per_m2,
        "base_rent_per_pyeong": _per_pyeong(rent_per_m2, 1.0),
        "floors": floors,
        "listings": listings,
        "listing_count": len(listings),
        "monthly_min": min(monthly) if monthly else None,
        "monthly_max": max(monthly) if monthly else None,
        "basis": "R-ONE 소규모상가 임대료(1층 기준) × 층 계수 × 건축물대장 층별개요 면적",
        "excludes": ["보증금", "권리금", "관리비"],
        "note": "호가·실거래가가 아니라 R-ONE 표본 평균에 층 계수를 곱한 추정이다. "
                "한 층에 호실이 여럿이면 그 층 전체 면적의 금액이다.",
    }
