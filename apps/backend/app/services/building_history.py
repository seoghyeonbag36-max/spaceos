"""Building business history service backed by Gold LocalData output."""
from __future__ import annotations

import json
from pathlib import Path

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"
_cache: dict[Path, dict] = {}


def _load_history(path: Path) -> dict:
    mtime = path.stat().st_mtime
    hit = _cache.get(path)
    if not hit or hit["mtime"] != mtime:
        hit = {"mtime": mtime, "data": json.loads(path.read_text(encoding="utf-8"))}
        _cache[path] = hit
    return hit["data"]


def get_history(building_id: str) -> tuple[list[dict], str]:
    """Return (history, history_source) for a page-master building id."""
    if not building_id:
        return [], "none"

    for path in _GOLD_DIR.glob("*/building_history.json"):
        rows = _load_history(path).get(building_id, [])
        if rows:
            return rows, "localdata"
    return [], "none"
