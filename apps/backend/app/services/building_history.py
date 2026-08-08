"""건물 영업이력 서비스 — Gold LocalData 산출물(`building_history.json`) 서빙.

산출물 스키마는 **지번 단위**다(`lot-history/1`, data/pipelines/build_building_history.py).
인허가 주소가 가리키는 것이 지번이지 동이 아니라서, 한 지번에 여러 동이 올라가 있으면
"어느 동의 업소였는지"는 원천에 없다.

그래서 이 서비스는 이력을 돌려줄 때 **그 지번을 몇 개 동이 공유하는지**(`lot_buildings`)를
함께 내려보내고, 출처를 두 값으로 가른다:

    localdata      지번에 동이 하나뿐 — 이력이 곧 그 건물의 이력이다
    localdata_lot  동이 여럿 — **지번 단위** 이력이다. 이 건물의 것이라고 말할 수 없다

화면이 이 구분을 지우면 "이 건물에 344개 업소가 있었다"(가락시장 실제 사례)가 된다.
"""
from __future__ import annotations

import json
from pathlib import Path

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"
_cache: dict[Path, dict] = {}


def _load_history(path: Path) -> dict:
    """산출물 로드 + 지번별 동 수 파생. mtime 이 바뀌면 다시 읽는다."""
    mtime = path.stat().st_mtime
    hit = _cache.get(path)
    if not hit or hit["mtime"] != mtime:
        data = json.loads(path.read_text(encoding="utf-8"))
        lot_counts: dict[str, int] = {}
        for pnu in (data.get("buildings") or {}).values():
            lot_counts[pnu] = lot_counts.get(pnu, 0) + 1
        hit = {"mtime": mtime, "data": data, "lot_counts": lot_counts}
        _cache[path] = hit
    return hit


def get_history(building_id: str) -> tuple[list[dict], str, int | None]:
    """(history, history_source, lot_buildings) 반환.

    lot_buildings 는 같은 지번을 공유하는 동 수. 이력이 없으면 None.
    """
    if not building_id:
        return [], "none", None

    for path in _GOLD_DIR.glob("*/building_history.json"):
        hit = _load_history(path)
        data = hit["data"]
        pnu = (data.get("buildings") or {}).get(building_id)
        if not pnu:
            continue
        rows = (data.get("lots") or {}).get(pnu) or []
        if not rows:
            continue
        n = hit["lot_counts"].get(pnu, 1)
        return rows, ("localdata" if n <= 1 else "localdata_lot"), n
    return [], "none", None
