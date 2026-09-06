"""상가정보 `flrNo` 로 유닛별 실면적을 특정할 수 있는가 — 재측정 스크립트.

`유닛 면적 입도` 게이트(2026-09-05 폐기·관측 50%)가 "다음 레버"로 지목했던 길을 잰다.
결론은 기각이고 경위는 `docs/finding-posting-unit-area-flrno-2026-09-06.md`,
절 서술은 `docs/feature-posting.md` §0-W 다.

수집하지 않는다 — 이미 있는 gold/silver 산출물만 읽는다(네트워크 없음).
다음 사람이 이 결론을 반박하려면 이 스크립트를 다시 돌려 수를 대면 된다:

    python -m data.validation.posting_unit_area_flrno

핵심 판정: **단일 층으로 확정되는 유닛 ⟺ `capacity == 1`** 이고, 그 경우 현재 식
(`com_area / capacity`)이 이미 그 한 층의 면적이라 델타가 0평이다. 즉 적용 가능한
곳에서는 값이 안 바뀌고, 바뀔 곳에는 적용할 수 없다.
"""
from __future__ import annotations

import json
import os
import statistics as st
from typing import Any

from data.config.page_hubs import ACTIVE_HUBS, get_hub

# SERVED_CITIES={"seoul"} — apps/backend/tests/test_city_registry.py 가 고정한다.
# 서빙 밖 거점(고양·파주)은 게이트가 세지 않으므로 여기서도 뺀다.
SERVED_CITIES = frozenset({"seoul"})

M2_PER_PYEONG = 3.3058
GOLD = "data/gold"
SILVER = "data/silver"


def served_hubs() -> set[str]:
    out = set()
    for slug in ACTIVE_HUBS:
        try:
            if get_hub(slug).city in SERVED_CITIES:
                out.add(slug)
        except Exception:
            continue
    return out


def _rows(path: str) -> list[dict]:
    """gold 산출물은 list 이거나 list 를 품은 dict 다 — 둘 다 받는다."""
    if not os.path.exists(path):
        return []
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, list):
        return d
    return next((v for v in d.values() if isinstance(v, list)), [])


def measure() -> dict[str, Any]:
    hubs = served_hubs()
    floor_dist: dict[int, int] = {}
    cap_dist: dict[int, int] = {}
    single_caps: dict[int, int] = {}
    deltas: list[int] = []
    ratios: list[float] = []
    units = no_mix = single = 0

    for slug in sorted(hubs):
        attrs_p = os.path.join(SILVER, slug, "building_attrs.json")
        attrs = json.load(open(attrs_p, encoding="utf-8")) if os.path.exists(attrs_p) else {}

        for u in _rows(os.path.join(GOLD, slug, "vacant_units.json")):
            units += 1
            mix = u.get("vac_floor_mix") or u.get("floor_mix") or {}
            if not mix:
                no_mix += 1
                continue
            k = len(mix)
            cap = u.get("capacity") or 0
            floor_dist[k] = floor_dist.get(k, 0) + 1
            cap_dist[cap] = cap_dist.get(cap, 0) + 1
            if k != 1:
                continue
            single += 1
            single_caps[cap] = single_caps.get(cap, 0) + 1
            # 단일 층이면 그 층의 면적 비중이 곧 이 유닛의 몫이다.
            uid = str(u.get("id") or "")
            pnu = uid.split("-")[1] if "-" in uid else None
            com_area = attrs.get(pnu, {}).get("com_area_flr") if pnu else None
            cur = u.get("area")
            if com_area and cur:
                new = round(com_area * list(mix.values())[0] / M2_PER_PYEONG)
                deltas.append(new - cur)
                ratios.append(new / cur if cur else 1.0)

    # 균등분할이 뭉개는 입도의 크기 — 건물 내 층 면적 최대/최소 비
    spread: list[float] = []
    for slug in sorted(hubs):
        by_bld: dict[str, list[float]] = {}
        for r in _rows(os.path.join(GOLD, slug, "vacant_floor_units.json")):
            by_bld.setdefault(str(r.get("building_id")), []).append(r.get("area_m2") or 0.0)
        for areas in by_bld.values():
            a = [x for x in areas if x]
            if len(a) >= 2:
                spread.append(max(a) / min(a))

    out: dict[str, Any] = {
        "probe": "posting-unit-area-flrno",
        "date": "2026-09-06",
        "served_hubs": len(hubs),
        "units_total": units,
        "no_floor_mix": no_mix,
        "floor_count_dist": dict(sorted(floor_dist.items())),
        "capacity_dist": dict(sorted(cap_dist.items())),
        "single_floor_units": single,
        "single_floor_pct": round(100 * single / units, 1) if units else 0.0,
        "multi_floor_units": units - single,
        # 이 줄이 판정의 핵심이다 — 단일층이 곧 capacity 1 인가
        "single_floor_capacity_dist": dict(sorted(single_caps.items())),
    }
    if deltas:
        out["delta_pyeong_on_single"] = {
            "n": len(deltas), "min": min(deltas), "max": max(deltas),
            "median": st.median(deltas), "changed_gt_1py": sum(1 for x in deltas if abs(x) > 1),
        }
    if ratios:
        out["ratio_new_over_cur_median"] = round(st.median(ratios), 4)
    if spread:
        s = sorted(spread)
        out["forgone_granularity"] = {
            "multi_floor_buildings": len(s),
            "ratio_median": round(st.median(s), 3),
            "ratio_p90": round(s[int(0.9 * len(s))], 3),
            "ratio_max": round(max(s), 1),
            "pct_over_1_2x": round(100 * sum(1 for r in s if r > 1.2) / len(s), 1),
        }
    return out


def main() -> None:
    r = measure()
    os.makedirs("reports", exist_ok=True)
    dest = "reports/posting_unit_area_flrno_probe_2026-09-06.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print(f"\n저장: {dest}")


if __name__ == "__main__":
    main()
