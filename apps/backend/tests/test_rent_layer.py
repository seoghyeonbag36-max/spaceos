from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
V1 = "/api/v1"


def test_rent_layer_uses_rone_source():
    r = client.get(f"{V1}/heatmap/rent", params={"district": "garosugil"})
    assert r.status_code == 200
    body = r.json()
    assert body["rent_source"] == "rone"
    assert body["unit"] == "만원/평"
    assert body["cells"]
    assert all(c["v"] > 0 for c in body["cells"])


def test_rent_layer_omits_districts_without_rone(monkeypatch):
    from app.services import rent_layer

    monkeypatch.setattr(rent_layer.posting_inputs, "for_district", lambda district_id: None)
    r = client.get(f"{V1}/heatmap/rent", params={"district": "garosugil"})
    assert r.status_code == 404
    assert "cells" not in r.json()


def test_rent_cells_match_vacancy_grid():
    rent = client.get(f"{V1}/heatmap/rent", params={"district": "garosugil"})
    vacancy = client.get(f"{V1}/heatmap/vacancy", params={"district": "garosugil"})
    assert rent.status_code == 200
    assert vacancy.status_code == 200

    rent_cells = rent.json()["cells"]
    vacancy_cells = vacancy.json()["cells"]
    assert len(rent_cells) == len(vacancy_cells)
    for rc, vc in zip(rent_cells, vacancy_cells):
        assert {k: rc[k] for k in ("i", "j", "lat", "lng", "c_lat", "c_lng", "dlat", "dlng")} == {
            k: vc[k] for k in ("i", "j", "lat", "lng", "c_lat", "c_lng", "dlat", "dlng")
        }
