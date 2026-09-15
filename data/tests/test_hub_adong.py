"""[Page] 거점 ↔ 행정동 배정 규칙 회귀 테스트 (2026-09-15 신설).

## 무엇을 고정하나

`build_hub_adong` 은 카카오 `coord2regioncode` 로 건물 좌표를 역지오코딩했다.
불필요했다 — 행정동은 상가정보 응답에 `adongCd`(8자리)·`adongNm` 으로 **이미 들어
있었다**(증거: `data/logs/probe_d1_2026-07-07.log` 의 실측 샘플). 카카오는 응답 저장을
허용하지 않으므로 그 경로는 약관에도 저촉했다
(→ `docs/finding-map-provider-google-2026-09-15.md` §7-2).

이 파일이 고정하는 것:

  ① `adongCd` 가 8자리로 온다는 전제 — 커밋된 프로브 로그와 대조한다(§1)
  ② 좌표·라벨 배열 정렬 — 좌표가 깨진 행에서 어긋나면 **엉뚱한 동에 붙는다**(§2)
  ③ PNU 직접 조인이 kNN 근사보다 우선한다(§3)
  ④ 가중치 기준 폴백 — 면적이 0 이면 건물 수로 물러선다(§4)

실행: (레포 루트에서) python -m pytest data/tests -q
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data.pipelines.build_hub_adong import KNN_K, _centroid, adong_index

ROOT = Path(__file__).resolve().parents[2]
PROBE_LOG = ROOT / "data" / "logs" / "probe_d1_2026-07-07.log"


# ── 1. 전제 검증 — adongCd 는 8자리다 (커밋된 실측 로그와 대조) ──────────────
def test_probe_log_still_shows_8digit_adong_code():
    """상가정보가 8자리 행정동 코드를 준다는 전제를 실측 기록으로 확인한다.

    이 전제가 깨지면(필드명 변경·자릿수 변경) 카카오를 걷어낸 근거 자체가 무너지므로,
    기억이나 문서가 아니라 **저장소에 커밋된 프로브 응답**을 본다.
    `test_page_footfall_hourly::test_adong8_*` 가 요구하는 형식과 같아야 한다.
    """
    assert PROBE_LOG.exists(), "프로브 로그가 사라졌다 — 교체 근거의 원본이다"
    text = PROBE_LOG.read_text(encoding="utf-8", errors="replace")
    assert "'adongCd': '11680510'" in text, "8자리 adongCd 실측 샘플이 없다"
    assert "'adongNm': '신사동'" in text
    # 법정동은 10자리라 자리수로도 갈린다 — 둘을 혼동하면 조인이 조용히 빈다
    assert "'ldongCd': '1168010700'" in text


def test_knn_k_matches_validated_value():
    """k=9 는 build_district_zones 가 PNU 조인과 99.2% 일치를 확인한 값이다.

    두 파이프라인이 같은 규칙을 써야 건물→행정동 배정이 한 가지로 유지된다.
    """
    from data.pipelines.build_district_zones import KNN_K as ZONES_K

    assert KNN_K == ZONES_K == 9


# ── 2. 좌표·라벨 정렬 — 이게 어긋나면 엉뚱한 동에 붙는다 ────────────────────
def test_index_keeps_points_and_labels_aligned():
    """좌표가 깨진 행이 섞여도 pts[i] ↔ labels[i] 가 유지된다."""
    rows = [
        {"adongCd": "11680510", "adongNm": "신사동", "signguNm": "강남구",
         "lnoCd": "P1", "lon": 127.02, "lat": 37.52},
        # 좌표가 깨졌다 — kNN 표본에서는 빠져야 하고, 라벨도 같이 빠져야 한다
        {"adongCd": "11680521", "adongNm": "압구정동", "signguNm": "강남구",
         "lnoCd": "P2", "lon": "", "lat": 37.52},
        {"adongCd": "11680531", "adongNm": "청담동", "signguNm": "강남구",
         "lnoCd": "P3", "lon": 127.05, "lat": 37.52},
    ]
    pts, labels, by_pnu = adong_index(rows)

    assert len(pts) == len(labels) == 2, "좌표 결측 행이 라벨만 남겼다 — 배열이 어긋난다"
    assert labels[0][0] == "11680510" and labels[1][0] == "11680531"
    # 좌표가 없어도 PNU 조인에는 쓸 수 있다 — 버리지 않는다
    assert set(by_pnu) == {"P1", "P2", "P3"}
    assert by_pnu["P2"] == ("11680521", "압구정동", "강남구")


def test_index_drops_rows_without_adong_code():
    """코드가 없는 행은 버린다 — 이름만으로는 생활인구와 조인할 수 없다(동명이동)."""
    rows = [
        {"adongNm": "신사동", "lnoCd": "P1", "lon": 127.0, "lat": 37.5},   # 코드 없음
        {"adongCd": "", "adongNm": "신사동", "lon": 127.0, "lat": 37.5},   # 공란
        {"adongCd": "11680510", "adongNm": "신사동", "lon": 127.0, "lat": 37.5},
    ]
    pts, labels, by_pnu = adong_index(rows)
    assert len(pts) == len(labels) == 1
    assert by_pnu == {}, "코드 없는 행이 PNU 사전에 들어갔다"


# ── 3. 배정 우선순위 — 정확한 것(PNU) 먼저, 빈 자리만 근사(kNN) ──────────────
def test_pnu_join_wins_over_knn(tmp_path, monkeypatch):
    """PNU 로 붙는 건물은 kNN 이 다른 답을 내도 PNU 를 따른다."""
    from data.pipelines import build_hub_adong as m

    # 건물 1동: pnu=P1. 좌표는 '청담동' 점포들 한복판에 둬서 kNN 이 청담동을 고르게 한다.
    master = {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"pnu": "P1", "capacity": 4, "capacity_method": "floor_ouln"},
        "geometry": {"type": "Polygon", "coordinates": [[
            [127.05, 37.52], [127.0501, 37.52], [127.0501, 37.5201], [127.05, 37.52]]]},
    }]}
    gold = tmp_path / "gold" / "testhub"
    gold.mkdir(parents=True)
    (gold / "page_building_master.geojson").write_text(
        json.dumps(master, ensure_ascii=False), encoding="utf-8")

    stores = [
        # P1 의 대장상 행정동은 신사동이다(PNU 조인의 정답)
        {"adongCd": "11680510", "adongNm": "신사동", "signguNm": "강남구",
         "lnoCd": "P1", "lon": 127.02, "lat": 37.52},
    ] + [
        # 건물 좌표 주변은 청담동 점포로 채운다 — kNN 만 보면 청담동이 이긴다
        {"adongCd": "11680531", "adongNm": "청담동", "signguNm": "강남구",
         "lnoCd": f"Q{i}", "lon": 127.05 + i * 1e-5, "lat": 37.52}
        for i in range(KNN_K + 3)
    ]

    monkeypatch.setattr(m, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(m, "load_latest", lambda slug, name: stores)
    monkeypatch.setattr(m, "load_attrs", lambda slug: {"P1": {"com_area_flr": 500.0}})

    out, stat = m.build("testhub")
    assert stat == {"pnu": 1, "knn": 0, "missed": 0}
    assert list(out) == ["11680510"], f"PNU 조인이 kNN 에 밀렸다: {out}"
    assert out["11680510"]["adm_nm"] == "신사동"


def test_knn_fills_buildings_without_stores(tmp_path, monkeypatch):
    """점포가 없는 건물(PNU 미조인)은 최근접 점포 다수결로 채운다."""
    pytest.importorskip("scipy", reason="kNN 배정은 scipy 지연 임포트를 쓴다")
    from data.pipelines import build_hub_adong as m

    master = {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"pnu": "NO_STORE"},      # 점포가 없는 지번
        "geometry": {"type": "Polygon", "coordinates": [[
            [127.05, 37.52], [127.0501, 37.52], [127.0501, 37.5201], [127.05, 37.52]]]},
    }]}
    gold = tmp_path / "gold" / "testhub"
    gold.mkdir(parents=True)
    (gold / "page_building_master.geojson").write_text(
        json.dumps(master, ensure_ascii=False), encoding="utf-8")

    stores = [
        {"adongCd": "11680531", "adongNm": "청담동", "signguNm": "강남구",
         "lnoCd": f"Q{i}", "lon": 127.05 + i * 1e-5, "lat": 37.52}
        for i in range(KNN_K + 1)
    ] + [
        # 멀리 있는 소수파 — 다수결에서 져야 한다
        {"adongCd": "11680510", "adongNm": "신사동", "signguNm": "강남구",
         "lnoCd": "R1", "lon": 127.10, "lat": 37.52},
    ]

    monkeypatch.setattr(m, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(m, "load_latest", lambda slug, name: stores)
    monkeypatch.setattr(m, "load_attrs", lambda slug: {})

    out, stat = m.build("testhub")
    assert stat == {"pnu": 0, "knn": 1, "missed": 0}
    assert list(out) == ["11680531"]


# ── 4. 가중치 기준 폴백 ────────────────────────────────────────────────────
def test_weight_falls_back_to_building_count_without_area(tmp_path, monkeypatch):
    """상업 연면적이 0 이면(대장 미수집) 건물 수로 물러서고, 근거를 밝힌다.

    조용히 weight 0 을 주면 그 행정동이 지도에서 사라진다 — 근거를 바꿔서라도
    값을 남기는 것이 이 파이프라인의 규칙이다.
    """
    from data.pipelines import build_hub_adong as m

    feats = [{
        "type": "Feature", "properties": {"pnu": f"P{i}"},
        "geometry": {"type": "Point", "coordinates": [127.02, 37.52]},
    } for i in range(4)]
    gold = tmp_path / "gold" / "testhub"
    gold.mkdir(parents=True)
    (gold / "page_building_master.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
        encoding="utf-8")

    stores = [
        {"adongCd": "11680510", "adongNm": "신사동", "signguNm": "강남구",
         "lnoCd": "P0", "lon": 127.02, "lat": 37.52},
        {"adongCd": "11680510", "adongNm": "신사동", "signguNm": "강남구",
         "lnoCd": "P1", "lon": 127.02, "lat": 37.52},
        {"adongCd": "11680521", "adongNm": "압구정동", "signguNm": "강남구",
         "lnoCd": "P2", "lon": 127.03, "lat": 37.52},
        {"adongCd": "11680521", "adongNm": "압구정동", "signguNm": "강남구",
         "lnoCd": "P3", "lon": 127.03, "lat": 37.52},
    ]
    monkeypatch.setattr(m, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(m, "load_latest", lambda slug, name: stores)
    monkeypatch.setattr(m, "load_attrs", lambda slug: {})   # 면적 0

    out, stat = m.build("testhub")
    assert stat["pnu"] == 4
    assert {v["weight_basis"] for v in out.values()} == {"buildings"}
    assert sum(v["weight"] for v in out.values()) == pytest.approx(1.0)


def test_centroid_handles_polygon_and_point():
    assert _centroid({"type": "Point", "coordinates": [127.0, 37.5]}) == (127.0, 37.5)
    lon, lat = _centroid({"type": "Polygon", "coordinates": [[
        [127.0, 37.5], [127.2, 37.5], [127.2, 37.7], [127.0, 37.7]]]})
    assert lon == pytest.approx(127.1) and lat == pytest.approx(37.6)
    assert _centroid({"type": "Polygon", "coordinates": []}) is None


# ── 5. 약관 불변식 ────────────────────────────────────────────────────────
def test_hub_adong_makes_no_kakao_calls():
    """이 파이프라인은 카카오를 부르지 않는다(행정동은 상가정보에 있다)."""
    src = (ROOT / "data" / "pipelines" / "build_hub_adong.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines()
                     if not line.lstrip().startswith("#"))
    # 독스트링(경위 기록)은 남기되, 실제 호출 URL·헤더는 없어야 한다
    assert "dapi.kakao.com" not in code.split('"""')[-1], "카카오 엔드포인트가 살아 있다"
    assert "KakaoAK" not in src, "카카오 인증 헤더가 살아 있다"
    assert "KAKAO_REST_API_KEY" not in src, "카카오 키를 아직 읽는다"
