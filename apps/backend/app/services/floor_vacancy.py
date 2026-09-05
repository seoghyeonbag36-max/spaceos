"""층 단위 공실 매물 목록 로더 — `gold/{거점}/vacant_floor_units.json` 한 벌.

## `vacant_inventory` 와 무엇이 다른가

이름이 비슷하지만 **다른 것을 센다.** 한쪽만 보고 다른 쪽을 짐작하면 안 된다.

| | `vacant_inventory` | 여기 |
|---|---|---|
| 파일 | `vacant_units.json` | `vacant_floor_units.json` |
| 단위 | 건물 1동 = 유닛 1개 | **(지번, 층)** = 유닛 1개 |
| 대상 | 통째로 빈 건물(`empty`·`high`) | 빈 층이 있는 모든 건물 — **`partial` 포함** |
| 쓰임 | 3-Tier ROI 시뮬레이션의 **표본** | 화면에 거는 **매물 목록** |
| 규모 | 66거점 679유닛 | 66거점 12,497유닛 |

**이 목록을 ROI 표본으로 쓰지 말 것.** 층마다 유닛을 내면 중앙값 유닛이 상층부로
올라가 프라임 프리미엄 트립와이어가 부호를 넘는다 — 2026-08-26 에 실측하고 되돌린
자리다(docs/feature-posting.md §0-Q·§0-T). 그래서 `/postings` 는 종전대로
`vacant_inventory` 를 본다.

## 확정과 추정

`certainty` 가 둘을 가른다. 상가정보 `flrNo` 공란(약 30%)에서 오는 괄호이고,
한 값으로 뭉개면 "실측처럼 보이는 추정치"가 된다.

- `confirmed` — 층 미상 점포를 낮은 층부터 다 앉히고도 남은 층. 비었음이 확정이다.
- `probable` — 그 배정에 먹힌 층. 층 미상 점포가 다른 층에 있으면 이쪽이 빈다.

기본 조회는 **둘 다** 준다. 화면이 섞어 그리지 않도록 필드로 드러낼 뿐이고,
`certainty=confirmed` 로 좁힐 수 있다.

## 슬러그 규칙은 빌려 쓴다

`vacant_inventory.slug_of` 를 그대로 쓴다 — 거점 id 별칭과 경로 조작 차단 규칙이
두 벌이 되면 같은 요청이 서비스마다 다른 거점을 가리킨다.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.services import vacant_inventory

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"

_CERTAINTIES = ("confirmed", "probable")

_cache: dict[str, dict | None] = {}


def path(slug: str) -> Path:
    return _GOLD_DIR / slug / "vacant_floor_units.json"


def clear_cache() -> None:
    """테스트·재적재용. 프로세스 전역 캐시를 비운다."""
    _cache.clear()


def load(district_id: str | None) -> dict | None:
    """파일 통째로. 없거나 깨졌으면 None.

    파일이 없는 것은 **정상 상태**다(거점에 빈 층이 없거나 아직 안 돌렸거나).
    예외를 올리지 않고 None 을 주어 호출부가 "아직 없다"고 말하게 한다.
    """
    slug = vacant_inventory.slug_of(district_id)
    if slug is None:
        return None
    if slug in _cache:
        return _cache[slug]
    p = path(slug)
    data: dict | None = None
    if p.exists():
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("units"), list):
                data = loaded
        except (OSError, ValueError):
            data = None
    _cache[slug] = data
    return data


def listing(district_id: str | None, *, certainty: str | None = None,
            floor: int | None = None, min_area: int | None = None,
            max_area: int | None = None, limit: int = 200,
            offset: int = 0) -> dict | None:
    """거점의 층 단위 매물 목록 + 집계. 산출물이 없으면 None.

    `total`/`counts` 는 **필터를 적용한 뒤**의 수다. 필터 전 전체는 산출물의
    `counts` 에 있고 `counts_all` 로 같이 내려보낸다 — 화면이 "12,497 중 316" 처럼
    분모를 밝힐 수 있어야 목록이 잘린 것인지 원래 없는 것인지 구분된다.
    """
    d = load(district_id)
    if d is None:
        return None

    units = list(d["units"])
    if certainty in _CERTAINTIES:
        units = [u for u in units if u.get("certainty") == certainty]
    if floor is not None:
        units = [u for u in units if u.get("floor") == floor]
    if min_area is not None:
        units = [u for u in units if (u.get("area") or 0) >= min_area]
    if max_area is not None:
        units = [u for u in units if (u.get("area") or 0) <= max_area]

    conf = sum(1 for u in units if u.get("certainty") == "confirmed")
    # 층 히스토그램 — 필터 적용 뒤 기준. 화면의 층 선택기가 이 값으로 그려진다.
    by_floor: dict[int, int] = {}
    for u in units:
        f = u.get("floor")
        if isinstance(f, int):
            by_floor[f] = by_floor.get(f, 0) + 1

    page = units[offset:offset + limit] if limit > 0 else units[offset:]
    return {
        "district_id": district_id,
        "total": len(units),
        "counts": {"confirmed": conf, "probable": len(units) - conf},
        "counts_all": d.get("counts") or {},
        "by_floor": {str(k): by_floor[k] for k in sorted(by_floor)},
        "built_at": d.get("built_at"),
        "source": d.get("source"),
        "note": d.get("note"),
        "units": page,
    }
