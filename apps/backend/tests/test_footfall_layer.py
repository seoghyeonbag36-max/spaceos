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

import json

import pytest
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

def test_response_discloses_trdar_resolution(monkeypatch, tmp_path):
    """상권 경로로 물러났을 때의 공시. 집계구가 있으면 그쪽이 쓰이므로 꺼 두고 본다."""
    _disable_jipgyegu(monkeypatch, tmp_path)
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
    _disable_jipgyegu(monkeypatch, tmp_path)
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
    # 기본 경로는 2026-08-26 부터 집계구다. 둘 중 무엇이 돌았든 **밝히고는 있어야**
    # 하므로 source 를 열거로 받는다 — 리터럴 하나로 박으면 폴백이 도는 환경
    # (산출물 미보유)에서 스위트가 깨진다.
    assert b["footfall_source"] in ("flpop_jipgyegu", "trdar")
    assert b["hour"] == 8 and b["cells"]


def test_density_endpoint():
    r = client.get(f"{V1}/heatmap/density", params={"district": _D})
    assert r.status_code == 200
    assert r.json()["density_source"] in ("flpop_jipgyegu", "trdar")


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


# ── 시간 축: 6구간 → 24시간 (생활인구, 2026-08-24) ──────────────────────────
#
# 공간은 TRDAR, 시간은 생활인구로 갈랐다. 이 묶음이 지키는 것:
#   1. 산출물이 거점을 담으면 24시간 눈금을 쓴다(접지 않는다).
#   2. 없으면 **조용히 0 이 되지 않고** TRDAR 6구간으로 물러난다.
#   3. 어느 쪽이 돌았는지 응답이 밝힌다 — 안 밝히면 두 눈금의 값이 섞여 비교된다.

def _disable_jipgyegu(monkeypatch, tmp_path):
    """집계구 산출물을 치워 **상권 경로**를 강제한다.

    2026-08-26 에 집계구가 기본 경로가 됐다. 상권·행정동 폴백을 검증하는 테스트는
    집계구를 끈 상태에서 돌아야 자기가 주장하는 것을 실제로 검증한다 — 안 끄면
    통과해도 폴백이 살아 있다는 증거가 못 된다.
    """
    monkeypatch.setattr(F, "_JIPGYEGU_SRC", tmp_path / "absent-jipgyegu.json")
    F.clear_cache()


def _install_hourly(monkeypatch, tmp_path, *, weekday, weekend=None):
    """합성 24시간 산출물을 깔고 캐시를 비운다. weekday/weekend 는 시각→구성비.

    행정동(24시간) 축을 검증하는 헬퍼이므로 **집계구는 함께 끈다** — 집계구가 켜져
    있으면 이 산출물이 아예 안 읽힌다.
    """
    src = tmp_path / "page_footfall_hourly.json"
    prof = {"weekday": {"hour_share": weekday},
            "weekend": {"hour_share": weekend or {}}}
    src.write_text(json.dumps({"resolution": "adong", "districts": {_D: prof}}),
                   encoding="utf-8")
    monkeypatch.setattr(F, "_HOURLY_SRC", src)
    _disable_jipgyegu(monkeypatch, tmp_path)


@pytest.fixture(autouse=True)
def _reset_layer_cache():
    """캐시가 테스트 사이로 새면 앞 테스트의 합성 산출물이 뒤에 붙는다."""
    F.clear_cache()
    yield
    F.clear_cache()


def test_hourly_artifact_replaces_the_six_band_axis(monkeypatch, tmp_path):
    _install_hourly(monkeypatch, tmp_path,
                    weekday={f"{h:02d}": 0.04 for h in range(24)} | {"15": 0.20})
    hm = F.footfall_heatmap(_D, 15)
    assert hm["time_source"] == "adong_hourly"
    assert hm["share_basis"] == "hour24"
    assert hm["hour_share"] == 0.2
    # 공간 해상도는 여전히 상권이다 — 프론트 TS 가 리터럴로 받는 필드를 바꾸지 않는다.
    assert hm["resolution"] == "trdar" and hm["footfall_source"] == "trdar"


def test_all_24_hours_are_distinguishable(monkeypatch, tmp_path):
    """이게 이 변경의 핵심이다 — 6구간에서는 08 시와 10 시가 같은 값이었다."""
    _install_hourly(monkeypatch, tmp_path,
                    weekday={f"{h:02d}": (h + 1) / 300 for h in range(24)})
    tops = [F.footfall_heatmap(_D, h)["cells"][0]["v"] for h in range(24)]
    assert len(set(tops)) == 24, "24시간이 서로 다른 값을 내지 못한다 — 축이 접혔다"

    # 6구간이던 시절에는 같은 구간 안의 두 시각이 반드시 같았다.
    assert F.band_of_hour(8) == F.band_of_hour(10)
    assert tops[8] != tops[10]


def test_weekday_and_weekend_differ(monkeypatch, tmp_path):
    """업무지구와 상업지구는 이 축에서 갈린다 — 한 벌로 평균하면 서로를 지운다."""
    _install_hourly(
        monkeypatch, tmp_path,
        weekday={f"{h:02d}": 0.04 for h in range(24)} | {"12": 0.30},
        weekend={f"{h:02d}": 0.04 for h in range(24)} | {"12": 0.01})
    wd = F.footfall_heatmap(_D, 12, "weekday")
    we = F.footfall_heatmap(_D, 12, "weekend")
    assert wd["daytype"] == "weekday" and we["daytype"] == "weekend"
    assert wd["hour_share"] != we["hour_share"]
    assert [c["v"] for c in wd["cells"]] != [c["v"] for c in we["cells"]]


def test_absent_daytype_profile_falls_back_not_zeroes(monkeypatch, tmp_path):
    """주말 표본이 아직 없으면(실제 08-24 상태) 0 이 아니라 6구간으로 물러난다."""
    _install_hourly(monkeypatch, tmp_path,
                    weekday={f"{h:02d}": 0.04 for h in range(24)}, weekend={})
    we = F.footfall_heatmap(_D, 12, "weekend")
    assert we["time_source"] == "trdar_band"
    assert we["share_basis"] == "band6"
    assert we["hour_share"] is None
    assert max(c["v"] for c in we["cells"]) > 0, "0 은 '사람이 없다'는 거짓이다"


def test_missing_hourly_artifact_keeps_previous_behaviour(monkeypatch, tmp_path):
    """산출물이 아예 없으면 종전 동작 그대로 — 이 배선은 레이어를 내리지 않는다."""
    monkeypatch.setattr(F, "_HOURLY_SRC", tmp_path / "nope.json")
    _disable_jipgyegu(monkeypatch, tmp_path)
    hm = F.footfall_heatmap(_D, 12)
    assert hm is not None
    assert hm["time_source"] == "trdar_band"
    assert "TRDAR 6구간" in hm["note"]


def test_note_discloses_which_time_axis_ran(monkeypatch, tmp_path):
    _install_hourly(monkeypatch, tmp_path,
                    weekday={f"{h:02d}": 0.04 for h in range(24)})
    assert "생활인구" in F.footfall_heatmap(_D, 12)["note"]


def test_hourly_share_rejects_bad_hour(monkeypatch, tmp_path):
    _install_hourly(monkeypatch, tmp_path,
                    weekday={f"{h:02d}": 0.04 for h in range(24)})
    assert F.hourly_share(_D, 24) is None
    assert F.hourly_share(_D, -1) is None
    assert F.hourly_share("no-such-district", 12) is None


def test_endpoint_accepts_daytype(monkeypatch, tmp_path):
    _install_hourly(
        monkeypatch, tmp_path,
        weekday={f"{h:02d}": 0.04 for h in range(24)} | {"12": 0.30},
        weekend={f"{h:02d}": 0.04 for h in range(24)} | {"12": 0.01})
    a = client.get(f"{V1}/heatmap/footfall",
                   params={"district": _D, "hour": 12, "daytype": "weekend"})
    assert a.status_code == 200
    assert a.json()["daytype"] == "weekend"
    assert a.json()["time_source"] == "adong_hourly"


# ── 집계구 승격 (2026-08-26) ────────────────────────────────────────────────
#
# 종전 경로의 셀 값은 `(최근접 상권 총량) × (거점 공통 시간구성비)` 였다. 시각을
# 바꾸면 **모든 셀에 같은 상수가 곱해지므로** 거점 안의 셀 서열이 구조적으로 보존된다
# — 슬라이더는 밝기만 바꾸고 "어디가 더 붐비나"는 하루 종일 같았다. 집계구는 공간과
# 시간이 한 표에서 나오므로 그 제약이 사라진다. 아래 테스트가 그 차이를 고정한다.

def _rho(a: list[float], b: list[float]) -> float:
    """스피어만 순위상관 (동점은 등장순 — 여기선 대소 판정에만 쓴다)."""
    def rank(vs: list[float]) -> list[int]:
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        r = [0] * len(vs)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    if n < 2:
        return 1.0
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da * db else 1.0


def test_jipgyegu_is_the_default_path():
    """산출물이 있으면 공간 축이 상권이 아니라 집계구다."""
    hm = F.footfall_heatmap(_D, 12)
    assert hm["resolution"] == "jipgyegu"
    assert hm["footfall_source"] == "flpop_jipgyegu"
    assert hm["time_source"] == "jipgyegu_hourly"
    assert hm["oa_count"] >= 2
    # 셀마다 어느 집계구에서 온 값인지 밝힌다 — 상권 경로의 `trdar` 와 같은 역할
    assert all(c["oa"] for c in hm["cells"])


def test_jipgyegu_response_still_says_it_is_not_grid_truth():
    """입도가 올라가도 격자 실측은 아니다 — 그 사실이 응답에서 사라지면 안 된다."""
    hm = F.footfall_heatmap(_D, 12)
    assert "격자 실측은 아니다" in hm["note"]
    assert hm["resolution"] == "jipgyegu"


def test_jipgyegu_does_not_multiply_a_share():
    """구성비 곱셈이 없다는 것을 타입으로 드러낸다.

    `share_basis` 가 남아 있으면 프론트가 두 경로의 값을 같은 눈금으로 오해한다.
    """
    hm = F.footfall_heatmap(_D, 12)
    assert hm["share_basis"] is None
    assert hm["hour_share"] is None
    assert "명(시각" in hm["unit"]


def test_hour_reorders_cells_within_a_district():
    """이 배선의 핵심 — 시각이 셀 **서열**을 바꾼다.

    상권 경로에서는 이 rho 가 정의상 1.0 이었다(모든 셀에 같은 상수를 곱하므로
    순위가 보존된다). 실측 54거점 중 **52곳**에서 서열이 바뀌고 중앙 rho 는 0.812,
    최소는 kyunghee 0.498 이다. 여기서는 대표 거점 하나만 고정한다.
    """
    day = F.footfall_heatmap(_D, 14)
    night = F.footfall_heatmap(_D, 3)
    assert day["resolution"] == night["resolution"] == "jipgyegu"
    rho = _rho([c["v"] for c in day["cells"]], [c["v"] for c in night["cells"]])
    assert rho < 0.99, f"셀 서열이 시각에 불변이다(rho={rho:.3f}) — 상권 경로로 되돌아갔나"


def test_trdar_path_cannot_reorder_cells(monkeypatch, tmp_path):
    """대조군 — 상권 경로에서는 서열이 시각에 **불변**이다.

    이 테스트가 깨지는 날은 상권 경로가 바뀐 것이고, 그러면 위 테스트가 무엇을
    개선했다고 주장하는지도 다시 봐야 한다.
    """
    _disable_jipgyegu(monkeypatch, tmp_path)
    day = F.footfall_heatmap(_D, 14)
    night = F.footfall_heatmap(_D, 3)
    assert day["resolution"] == "trdar"
    rho = _rho([c["v"] for c in day["cells"]], [c["v"] for c in night["cells"]])
    assert rho == pytest.approx(1.0), "상권 경로는 셀 서열을 못 바꾼다"


def test_jipgyegu_density_declares_a_different_basis():
    """밀도의 **분자 정의**가 상권판과 다르다 — 안 밝히면 값이 비교 가능해 보인다."""
    hm = F.density_heatmap(_D)
    assert hm["resolution"] == "jipgyegu"
    assert hm["density_basis"] == "flpop_mean24_per_1k_m2"
    assert "24시간 평균" in hm["unit"]
    assert all(c["v"] > 0 for c in hm["cells"])


def test_store_density_stays_on_trdar():
    """점포 밀도는 집계구 원천이 없다 — 조용히 올리면 없는 실측을 주장하게 된다."""
    hm = F.density_heatmap(_D, "stor")
    assert hm["resolution"] == "trdar"
    assert hm["metric"] == "stor"


def test_missing_jipgyegu_artifact_falls_back_not_down(monkeypatch, tmp_path):
    """집계구 산출물이 없으면 상권으로 물러난다 — 레이어를 내리지는 않는다."""
    _disable_jipgyegu(monkeypatch, tmp_path)
    hm = F.footfall_heatmap(_D, 12)
    assert hm is not None and hm["resolution"] == "trdar"


def test_jipgyegu_artifact_covers_every_district():
    """부분 커버 거점은 산출물이 애초에 안 싣는다 — 한 화면에 두 눈금이 섞이면 안 된다."""
    doc = F._load_jipgyegu()
    assert doc, "집계구 산출물이 없다 — build_page_footfall_jipgyegu 먼저"
    assert doc["stats"]["districts_partial"] == {}
    covered = set(doc["districts"])
    assert covered >= set(svc.DISTRICTS_BY_ID), (
        f"안 덮인 거점: {sorted(set(svc.DISTRICTS_BY_ID) - covered)}")
