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


def _load(path: Path) -> dict:
    """산출물 로드 — 스키마 v2(`lot-history/1`: lots + buildings 인덱스)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema") == "lot-history/1", f"{path}: 알 수 없는 스키마 {data.get('schema')!r}"
    return data


def _lot_counts(data: dict) -> dict[str, int]:
    """지번별 동 수 — 서비스가 lot_buildings 로 내려보내는 값과 같은 계산."""
    counts: dict[str, int] = {}
    for pnu in data["buildings"].values():
        counts[pnu] = counts.get(pnu, 0) + 1
    return counts


def _solo_lot_building_id() -> str:
    """동이 하나뿐인 지번의 건물 — 이력이 곧 그 건물의 것인 경우."""
    data = _load(GAROSU_HISTORY)
    counts = _lot_counts(data)
    for building_id, pnu in data["buildings"].items():
        if counts[pnu] == 1 and data["lots"].get(pnu):
            return building_id
    raise AssertionError("garosugil 에 단독 동 지번이 없다")


def _real_garosu_building_id() -> str:
    return _solo_lot_building_id()


def _open_business_building_id() -> str:
    data = _load(GAROSU_HISTORY)
    counts = _lot_counts(data)
    for building_id, pnu in data["buildings"].items():
        if counts[pnu] != 1:
            continue
        if any(row["end_date"] is None for row in data["lots"].get(pnu, [])):
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
        slug = master_path.parent.name
        licensing = list((ROOT / "data" / "bronze" / slug).glob("*/licensing_biz.json"))
        # 경기 인허가 원본이 없는 거점은 빈 이력이 정상이며 파일을 지어내지 않는다.
        if not licensing:
            assert not history_path.exists(), f"{history_path}: 원본 없이 이력을 만들었다"
            continue
        assert history_path.exists(), f"{history_path} missing"

        data = _load(history_path)
        assert data["lots"], f"{history_path} is empty"
        assert data["buildings"], f"{history_path} has no building index"
        assert any(
            DATE8.match(str(item.get("start_date") or ""))
            for rows in data["lots"].values()
            for item in rows
        ), f"{history_path} has no 8-digit start_date"

        # 인덱스가 실재하는 지번만 가리켜야 한다 — 끊어진 참조는 빈 이력으로 조용히 떨어진다.
        orphans = [b for b, pnu in data["buildings"].items() if pnu not in data["lots"]]
        assert not orphans, f"{history_path}: 이력 없는 지번을 가리키는 건물 {len(orphans)}개"


def test_lot_history_is_not_duplicated_per_building():
    """지번 이력은 지번에 한 번만 저장돼야 한다 — 동마다 복제하면 안 된다.

    v1 은 한 지번의 이력을 그 지번의 모든 동에 복사했다. 가락시장(폴리곤 225개가 한 지번)
    에서 225배로 불어나 거점 하나가 17.9MB 가 됐고, 무엇보다 **동마다 "이 건물에 344개
    업소가 있었다"고 주장**하게 됐다 — 원천(인허가 주소)은 지번까지만 안다.
    """
    for history_path in sorted((ROOT / "data" / "gold").glob("*/building_history.json")):
        data = _load(history_path)
        counts = _lot_counts(data)
        shared = [pnu for pnu, n in counts.items() if n > 1]
        if not shared:
            continue
        # 공유 지번의 이력이 lots 에 단 한 벌만 있는지는 구조가 보장한다(키가 지번이다).
        # 여기서 막는 것은 스키마가 건물 단위로 되돌아가는 회귀다.
        assert all(pnu in data["lots"] for pnu in shared), f"{history_path}: 공유 지번 이력 누락"
        worst = max(counts.values())
        assert worst > 1  # 이 거점에는 실제로 공유 지번이 있다


def test_shared_lot_history_is_labeled_lot_scope():
    """복수 동 지번의 이력은 건물 이력이라고 주장하면 안 된다.

    응답이 `localdata_lot` + 공유 동 수를 밝혀야 화면이 "이 건물"과 "이 지번"을 가른다.
    """
    checked = 0
    for history_path in sorted((ROOT / "data" / "gold").glob("*/building_history.json")):
        data = _load(history_path)
        counts = _lot_counts(data)
        for building_id, pnu in data["buildings"].items():
            if counts[pnu] <= 1 or not data["lots"].get(pnu):
                continue
            body = client.get(f"{V1}/buildings/{building_id}/history").json()
            assert body["history_source"] == "localdata_lot", building_id
            assert body["lot_buildings"] == counts[pnu], building_id
            checked += 1
            break
        if checked >= 3:
            break
    assert checked, "복수 동 지번이 하나도 없다 — 산출물 구조가 바뀌었는지 확인"
