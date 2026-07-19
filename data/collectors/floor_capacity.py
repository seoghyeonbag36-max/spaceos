"""[Page·분모 정밀화] 층별개요 기반 capacity 재산출 — poc §1-2 TODO 구현.

2026-07-19 지상검증 잔여 오차(영업→high 9동)의 원인: floor_approx 가
지상층 전체 × 2호를 분모로 잡아, 상층부가 사무실·주거·단일 임차인 건물의
상가 수용량을 과대추정한다.

교정: 건축HUB 층별개요(getBrFlrOulnInfo)로 각 층 용도를 받아
  상업 용도(근린생활·판매·위락·숙박·문화) 층 수 × 2호
만 분모로 삼는다. 대상은 gold/building_vacancy.json 중 capacity_method
== "floor_approx" 행 전부 (~560동, 건물당 1콜 — 쿼터 내).

산출: building_vacancy.json 의 capacity/capacity_method("floor_ouln") 갱신
      + bronze/{SLUG}/{날짜}/bldg_flr_raw.json
실행: python -m data.collectors.floor_capacity
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter

from data.collectors.common import GOLD, load_env, save_json
from data.config.garosugil import SLUG
from data.collectors.building_vacancy import (
    BASE_BLD, COMMERCIAL_PURPS, STORES_PER_FLOOR, _get_json, _items, _jibun, classify,
)

_SLEEP = 0.05


def _commercial_floors(rows: list[dict]) -> int:
    """층별개요 행에서 '지상' 상업 용도 층 수를 센다 (지하는 분모 제외 유지)."""
    floors = set()
    for r in rows:
        if str(r.get("flrGbCdNm", "")) not in ("지상", ""):
            continue
        purps = f"{r.get('mainPurpsCdNm', '')}{r.get('etcPurps', '')}"
        if any(p in purps for p in COMMERCIAL_PURPS):
            floors.add((r.get("flrGbCd", ""), r.get("flrNo", "")))
    return len(floors)


def main() -> None:
    load_env()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key:
        print("[flr-cap] DATA_GO_KR_SERVICE_KEY 미설정 — 건너뜀")
        return

    path = GOLD / SLUG / "building_vacancy.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    targets = [r for r in rows if r.get("capacity_method") == "floor_approx"]
    print(f"[flr-cap] 대상 {len(targets)}동 (floor_approx)")

    raw: dict[str, list] = {}
    updated = failed = 0
    for i, b in enumerate(targets, 1):
        jibun = _jibun(b.get("lnoCd", ""))
        if jibun is None:
            continue
        flr = _get_json(f"{BASE_BLD}/getBrFlrOulnInfo",
                        {"serviceKey": key, "_type": "json", "numOfRows": 200, **jibun})
        items = _items(flr)
        if not items:
            failed += 1
            continue
        raw[b["lnoCd"]] = items
        n_com = _commercial_floors(items)
        cap = max(n_com * STORES_PER_FLOOR, 1) if n_com else None
        if cap is None:
            # 상업 층 0 — 표제부에서 상업으로 본 건물이므로 최소 1층분은 남긴다
            cap = STORES_PER_FLOOR
        b["capacity"] = max(cap, b["active"])
        b["capacity_method"] = "floor_ouln"
        occ = min(b["active"] / b["capacity"], 1.0)
        b["occupancy"] = round(occ, 3)
        b["vacancy_bldg"] = round((1 - occ) * 100, 1)
        b["status"] = classify(occ, "floor_ouln")
        updated += 1
        if i % 50 == 0 or i == len(targets):
            print(f"[flr-cap] {i}/{len(targets)}동 (갱신 {updated}, 응답없음 {failed})")
        time.sleep(_SLEEP)

    save_json(raw, SLUG, "bldg_flr_raw.json")
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    cm = Counter(r.get("capacity_method") for r in rows)
    print(f"[flr-cap] building_vacancy.json 갱신 — capacity_method: {dict(cm)}")


if __name__ == "__main__":
    main()
