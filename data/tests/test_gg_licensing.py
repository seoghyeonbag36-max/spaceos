"""경기 인허가 수집기 + 좌표계 분기 — 조용히 틀리는 두 자리를 고정한다.

이 두 가지는 **틀려도 예외가 안 나고 산출물이 그럴듯하게 만들어진다**:

1. 주소 파싱 — 고양은 구가 있고(`고양시 덕양구 화정동`) 파주는 없다(`파주시 금촌동`).
   한쪽 형식만 맞추면 다른 도시의 인허가가 통째로 0 건이 된다.
2. 좌표계 — 경기 응답은 이미 WGS84 인데 `_licensed_pip` 은 서울 TM 을 가정해
   `EPSG:2097 → 4326` 변환을 한다. 한 번 더 변환하면 좌표가 엉뚱한 곳으로 가고
   **PIP 가 아무 건물에도 안 걸려 분자 보강이 0 이 된다** — 정상처럼 보인다.

근거: docs/finding-gyeonggi-licensing-source-2026-08-30.md
"""
from data.collectors.gg_licensing import _norm, _place


def test_place_parses_goyang_and_paju_forms():
    """구가 있는 주소와 없는 주소, 읍면(리) 주소를 모두 뽑아야 한다."""
    assert _place("경기도 고양시 덕양구 화정동 946") == ("고양시", "덕양구", "화정동")
    assert _place("경기도 파주시 금촌동 544-6") == ("파주시", "", "금촌동")
    assert _place("경기도 파주시 월롱면 도내리 238-2") == ("파주시", "", "도내리")
    # 층·호가 붙어도 잎은 동이다
    assert _place("경기도 고양시 일산동구 백석동 1278-2 1층 전체") == (
        "고양시", "일산동구", "백석동")
    assert _place("") is None


def test_norm_maps_to_seoul_schema():
    """소비층(build_page_master·build_building_history)이 읽는 키를 전부 채운다."""
    row = _norm({
        "MANAGE_NO": "4128000-101-2026-00001",
        "BIZPLC_NM": "함경면옥 백석점",
        "BIZCOND_DIV_NM_INFO": "한식",
        "BSN_STATE_NM": "영업",
        "CLSBIZ_DE": None,
        "LICENSG_DE": "20260506",
        "REFINE_LOTNO_ADDR": "경기도 고양시 일산동구 백석동 1278-2 1층 전체",
        "REFINE_ROADNM_ADDR": "경기도 고양시 일산동구 중앙로 1275",
        "LOCPLC_AR_INFO": "110.14",
        "REFINE_WGS84_LAT": "37.6463787",
        "REFINE_WGS84_LOGT": "126.7858359",
    })
    for k in ("MGTNO", "BPLCNM", "UPTAENM", "TRDSTATEGBN", "TRDSTATENM",
              "DCBYMD", "APVPERMYMD", "SITEWHLADDR", "RDNWHLADDR",
              "SITEAREA", "X", "Y", "CRS"):
        assert k in row, f"소비층 계약 키 누락: {k}"
    assert row["TRDSTATEGBN"] == "01", "영업은 서울 코드 01 로 옮겨야 한다"
    # X=경도, Y=위도 (always_xy 관례) — 뒤집히면 PIP 가 전부 빗나간다
    assert float(row["X"]) > 126 and float(row["Y"]) > 37
    assert row["CRS"] == "EPSG:4326", "좌표계 표기가 빠지면 소비층이 다시 변환한다"


def test_closed_business_maps_to_non_open():
    row = _norm({"BSN_STATE_NM": "폐업", "CLSBIZ_DE": "20070208"})
    assert row["TRDSTATEGBN"] == "02"
    assert row["DCBYMD"] == "20070208"


def test_licensed_pip_skips_transform_for_wgs84_rows():
    """`CRS: EPSG:4326` 행은 좌표 변환을 타지 않아야 한다.

    변환을 타면 경도 126.78 이 TM 좌표로 해석돼 결과가 지구 반대편으로 간다.
    여기서는 `_lonlat` 이 없는 구현으로 되돌아갔는지를 소스로 확인한다 —
    실제 PIP 는 폴리곤·대장이 있어야 돌아서 단위 테스트로 고정하기 어렵다.
    """
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "pipelines" / "build_page_master.py"
    text = src.read_text(encoding="utf-8")
    assert "_lonlat" in text, "좌표계 분기가 사라졌다 — 경기 인허가가 조용히 0 건이 된다"
    assert 'str(r.get("CRS") or "") == "EPSG:4326"' in text, "CRS 표기를 읽지 않는다"
    # 변환 호출은 `_lonlat` 안의 **한 곳뿐**이어야 한다. 루프에서 직접 부르는 자리가
    # 남아 있으면 그 경로만 WGS84 행을 다시 변환한다.
    assert text.count("tr.transform(x, y)") == 1, "변환을 직접 부르는 자리가 남아 있다"
