import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
V1 = "/api/v1"
ROOT = Path(__file__).resolve().parents[3]
GAROSU_HISTORY = ROOT / "data" / "gold" / "garosugil" / "building_history.json"
GAROSU_MASTER = ROOT / "data" / "gold" / "garosugil" / "page_building_master.geojson"
DATE8 = re.compile(r"^\d{8}$")


def _real_garosu_building_id() -> str:
    histories = json.loads(GAROSU_HISTORY.read_text(encoding="utf-8"))
    return next(iter(histories))


def _open_business_building_id() -> str:
    histories = json.loads(GAROSU_HISTORY.read_text(encoding="utf-8"))
    for building_id, rows in histories.items():
        if any(row["end_date"] is None for row in rows):
            return building_id
    raise AssertionError("open LocalData business not found in garosugil history")


def _absent_building_id() -> str:
    for master_path in sorted((ROOT / "data" / "gold").glob("*/page_building_master.geojson")):
        if (master_path.parent / "building_history.json").exists():
            continue
        master = json.loads(master_path.read_text(encoding="utf-8"))
        if master["features"]:
            return master["features"][0]["properties"]["id"]
    return "no-such-building"


def test_history_returns_real_licensing_records():
    building_id = _real_garosu_building_id()
    r = client.get(f"{V1}/buildings/{building_id}/history")
    assert r.status_code == 200
    body = r.json()
    assert body["history_source"] == "localdata"
    assert body["history"]
    assert all(item["business_name"] != "예시 카페" for item in body["history"])
    assert all(DATE8.match(item["start_date"]) for item in body["history"])


def test_history_absent_returns_empty_not_dummy():
    building_id = _absent_building_id()
    r = client.get(f"{V1}/buildings/{building_id}/history")
    assert r.status_code == 200
    body = r.json()
    assert body["history"] == []
    assert body["history_source"] == "none"


def test_closure_reason_is_null_not_fabricated():
    building_id = _real_garosu_building_id()
    r = client.get(f"{V1}/buildings/{building_id}/history")
    assert r.status_code == 200
    assert all(item["closure_reason_summary"] is None for item in r.json()["history"])


def test_open_business_has_null_end_date():
    building_id = _open_business_building_id()
    r = client.get(f"{V1}/buildings/{building_id}/history")
    assert r.status_code == 200
    assert any(item["end_date"] is None for item in r.json()["history"])


def test_history_covers_all_page_master_districts():
    master_paths = sorted((ROOT / "data" / "gold").glob("*/page_building_master.geojson"))
    assert master_paths

    for master_path in master_paths:
        history_path = master_path.parent / "building_history.json"
        assert history_path.exists(), f"{history_path} missing"

        histories = json.loads(history_path.read_text(encoding="utf-8"))
        assert histories, f"{history_path} is empty"
        assert any(
            DATE8.match(str(item.get("start_date") or ""))
            for rows in histories.values()
            for item in rows
        ), f"{history_path} has no 8-digit start_date"
