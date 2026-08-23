"""Page 유동·밀도 레이어 (services/footfall_layer + /heatmap/footfall·/density).

## 무엇을 고친 것인가

`MapShell` 의 유동인구 히트맵은 `Math.random()` 으로 만든 점 120개였고, 시간
슬라이더는 그 난수를 건드리지도 않아 **장식**이었다. 밀도 레이어는 엔드포인트조차
없었다. 재료(TRDAR 상권 190곳)는 이미 저장소 안에 있었다 — 배선이 없던 것이다.

## 이 스위트가 지키는 것

1. **슬라이더가 실제로 입력을 바꾼다** — 시간대를 바꾸면 값이 바뀌어야 한다.
   안 바뀌면 예전 상태(장식)로 되돌아간 것이다.
2. **격자가 다른 레이어와 같다** — 공실·임대와 같은 셀이어야 네 레이어가 겹쳐 읽힌다.
3. **해상도를 숨기지 않는다** — 값은 상권 단위 집계다. `resolution`·`trdar_count`·
   `note` 가 응답에 없으면 화면이 격자 실측처럼 보여준다.
4. **없을 때 0 으로 채우지 않는다** — 0 은 "사람이 없다"는 거짓이다. None → 404.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import districts as svc
from app.services import footfall_layer as F

client = TestClient(app)
V1 = "/api/v1"
_D = "garosugil"


# ── 시간대가 값을 바꾼다 ────────────────────────────────────────────────────

def test_hour_changes_the_values():
    """이게 이 변경의 핵심이다 — 예전에는 슬라이더가 아무것도 바꾸지 않았다."""
    morning = F.footfall_heatmap(_D, 8)
    night = F.footfall_heatmap(_D, 22)
    assert morning and night
    assert morning["band"] != night["band"]
    assert [c["v"] for c in morning["cells"]] != [c["v"] for c in night["cells"]]


def test_all_six_bands_are_reachable():
    bands = {F.band_of_hour(h) for h in range(24)}
    assert bands == set(F.TMZONS)


def test_out_of_range_hour_does_not_crash():
    assert F.band_of_hour(-1) == F.band_of_hour(99) == "11_14"


# ── 격자는 공실·임대와 같다 ─────────────────────────────────────────────────

def test_grid_matches_vacancy_layer():
    vac = svc.get_vacancy_heatmap(_D)
    foot = F.footfall_heatmap(_D, 12)
    assert vac and foot
    assert [(c["i"], c["j"]) for c in foot["cells"]] == [(c["i"], c["j"]) for c in vac["cells"]]


# ── 해상도를 밝힌다 ─────────────────────────────────────────────────────────

def test_response_discloses_trdar_resolution():
    hm = F.footfall_heatmap(_D, 12)
    assert hm["resolution"] == "trdar"
    assert hm["trdar_count"] >= 1
    assert "상권 단위" in hm["note"]
    # 셀마다 어느 상권에서 온 값인지 밝힌다
    assert all(c["trdar"] for c in hm["cells"])


def test_density_is_flpop_not_resident_population():
    """화면 라벨이 '인구밀도'였지만 우리가 가진 것은 **유동인구** 밀도다."""
    hm = F.density_heatmap(_D)
    assert hm["metric"] == "flpop"
    assert hm["label"] == "유동인구 밀도"
    assert "유동인구" in hm["note"]


def test_density_stor_metric():
    hm = F.density_heatmap(_D, "stor")
    assert hm and hm["metric"] == "stor" and "점포" in hm["unit"]


# ── 없으면 없다고 한다 (0 으로 채우지 않는다) ───────────────────────────────

def test_unknown_district_returns_none_not_zeros():
    assert F.footfall_heatmap("no-such-district", 12) is None
    assert F.density_heatmap("no-such-district") is None


def test_missing_artifact_disables_layer(monkeypatch, tmp_path):
    """산출물이 빠지면 레이어를 통째로 내린다 — 0 으로 채우면 거짓이 화면에 나간다."""
    monkeypatch.setattr(F, "_SRC", tmp_path / "absent.json")
    F.clear_cache()
    try:
        assert F.trdars_of(_D) == []
        assert F.footfall_heatmap(_D, 12) is None
    finally:
        F.clear_cache()


# ── 라우터 ──────────────────────────────────────────────────────────────────

def test_footfall_endpoint():
    r = client.get(f"{V1}/heatmap/footfall", params={"district": _D, "hour": 8})
    assert r.status_code == 200
    b = r.json()
    assert b["footfall_source"] == "trdar" and b["hour"] == 8 and b["cells"]


def test_density_endpoint():
    r = client.get(f"{V1}/heatmap/density", params={"district": _D})
    assert r.status_code == 200
    assert r.json()["density_source"] == "trdar"


def test_endpoints_404_on_unknown_district():
    for path in ("footfall", "density"):
        r = client.get(f"{V1}/heatmap/{path}", params={"district": "no-such-district"})
        assert r.status_code == 404, path


# ── 산출물 자체 ─────────────────────────────────────────────────────────────

def test_artifact_covers_all_districts():
    """54거점 전부 상권이 붙어야 한다 — 빠진 거점은 화면에서 레이어가 통째로 빈다."""
    doc = F._load()
    assert doc, "gold/platform_page_footfall.json 없음 — build_page_footfall.py 실행 필요"
    covered = set(doc["districts"])
    missing = [d["id"] for d in svc.DISTRICTS if d["id"] not in covered]
    assert not missing, f"상권이 없는 거점: {missing}"
