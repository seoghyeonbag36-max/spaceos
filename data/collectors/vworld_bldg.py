"""[Page] V-World GIS건물통합정보 수집기 — 건물 footprint 폴리곤 (Bronze).

`VWORLD_API_KEY`(vworld.kr 즉시발급)로 가로수길 코어 축 bbox의 건물 폴리곤을
WFS(getBldgisSpceWFS, 레이어 dt_d010)로 수집한다. 2026-07-08 실호출 검증 완료:
PNU·층수·연면적·높이(hg)·용도코드 + gml 좌표 수신 확인.

- PNU(19자리) → 시군구(5)+법정동(5)+산여부(1)+본번(4)+부번(4) 파생 → 건축물대장 조인.
- 원본 XML 은 무가공 저장(Bronze 규칙), 파싱 GeoJSON 은 편의 산출물로 병행 저장.
- 서버 maxFeatures 상한 1000 → 상한 도달 시 bbox 4분할 재귀 타일링, PNU+fid 로 중복 제거.
- bbox 축 순서는 lon,lat (소량 bbox 실호출로 검증됨).

실행: python -m data.collectors.vworld_bldg
"""
from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import bronze_dir, load_env, save_json
from data.config.garosugil import CX, CY, RADIUS_M, SLUG

_URL = "https://api.vworld.kr/ned/wfs/getBldgisSpceWFS"
_TYPENAME = "dt_d010"
_DOMAIN = "http://localhost:5173"   # 키 발급 시 등록한 도메인
_MAX_FEATURES = 1000   # 서버 상한 1000 (초과 시 INVALID_RANGE 예외)

_NS = {
    "wfs": "http://www.opengis.net/wfs",
    "gml": "http://www.opengis.net/gml",
    "sop": "https://www.vworld.kr",
}

# 속성 태그 → GeoJSON properties 키 (실호출 검증된 필드만)
_FIELDS = (
    "pnu", "gis_idntfc_no", "buld_idntfc_no", "buld_prpos_code",
    "ground_floor_co", "undgrnd_floor_co", "hg", "totar", "plot_ar",
    "regstr_se_code", "strct_code", "use_confm_de", "last_updt_dt",
)


def _bbox(cx: float, cy: float, radius_m: int) -> tuple[float, float, float, float]:
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * math.cos(math.radians(cy)))
    return (cx - dlon, cy - dlat, cx + dlon, cy + dlat)


def _fetch(key: str, bbox_str: str) -> str | None:
    params = {
        "key": key, "domain": _DOMAIN, "typename": _TYPENAME,
        "bbox": bbox_str, "srsName": "EPSG:4326",
        "maxFeatures": _MAX_FEATURES,
        "output": "text/xml; subtype=gml/2.1.2",
    }
    try:
        r = requests.get(_URL, params=params, timeout=60)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        print(f"[vworld] WFS 실패 — {exc}")
        return None


def _pnu_to_jibun(pnu: str) -> dict:
    """PNU 19자리 → 건축물대장 조회 파라미터(sigunguCd/bjdongCd/platGbCd/bun/ji)."""
    if not pnu or len(pnu) != 19:
        return {}
    return {
        "sigunguCd": pnu[0:5], "bjdongCd": pnu[5:10],
        "platGbCd": str(int(pnu[10]) - 1),  # PNU 산구분 1=대지/2=산 → 대장 0/1
        "bun": pnu[11:15], "ji": pnu[15:19],
    }


def _parse(xml_text: str) -> list[dict]:
    """WFS FeatureCollection → GeoJSON Feature 목록 (외곽 링 기준)."""
    root = ET.fromstring(xml_text)
    feats: list[dict] = []
    for member in root.findall("gml:featureMember", _NS):
        el = member.find(f"sop:{_TYPENAME}", _NS)
        if el is None:
            continue
        props = {}
        for f in _FIELDS:
            v = el.findtext(f"sop:{f}", default=None, namespaces=_NS)
            if v is not None:
                props[f] = v.strip()
        props.update(_pnu_to_jibun(props.get("pnu", "")))

        rings = []
        for coords in el.findall(".//gml:coordinates", _NS):
            pts = []
            for pair in (coords.text or "").split():
                xy = pair.split(",")
                if len(xy) >= 2:
                    pts.append([float(xy[0]), float(xy[1])])
            if len(pts) >= 4:
                rings.append(pts)
        if not rings:
            continue
        feats.append({
            "type": "Feature",
            "properties": props,
            # TODO: 내부 링(중정) 구분 — 현재는 첫 링=외곽만 신뢰, 나머지는 보류
            "geometry": {"type": "Polygon", "coordinates": rings[:1]},
        })
    return feats


def _collect(key: str, box: tuple[float, float, float, float],
             raws: list[str], depth: int = 0) -> list[dict]:
    """bbox 수집 — 상한(1000) 도달 시 4분할 재귀."""
    x1, y1, x2, y2 = box
    xml_text = _fetch(key, f"{x1},{y1},{x2},{y2}")
    feats = _parse(xml_text) if xml_text else []
    if len(feats) >= _MAX_FEATURES and depth < 5:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        out: list[dict] = []
        for sub in ((x1, y1, mx, my), (mx, y1, x2, my),
                    (x1, my, mx, y2), (mx, my, x2, y2)):
            out += _collect(key, sub, raws, depth + 1)
        return out
    if xml_text:
        raws.append(xml_text)
    print(f"[vworld] tile d{depth}: {len(feats)}동")
    return feats


def main() -> None:
    load_env()
    key = os.getenv("VWORLD_API_KEY")
    if not key or requests is None:
        print("[vworld] VWORLD_API_KEY 미설정(또는 requests 없음) — 건너뜀")
        return

    raws: list[str] = []
    feats = _collect(key, _bbox(CX, CY, RADIUS_M), raws)
    if not feats:
        print("[vworld] 수집 실패 — 응답 XML/키/도메인 확인 필요")
        return

    # 타일 경계 중복 제거 (PNU + GIS식별번호)
    seen: set[tuple] = set()
    uniq: list[dict] = []
    for f in feats:
        k = (f["properties"].get("pnu"), f["properties"].get("gis_idntfc_no"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)

    raw_path = bronze_dir(SLUG) / "vworld_bldg_raw.xml"
    raw_path.write_text("\n<!-- TILE -->\n".join(raws), encoding="utf-8")
    print(f"[bronze] {raw_path.name} (원본 XML {len(raws)}타일)")
    save_json({"type": "FeatureCollection", "features": uniq}, SLUG, "bldg_polygons.geojson")

    sample = uniq[0]["properties"]
    print(f"[vworld] 총 {len(uniq)}동(중복 제거 전 {len(feats)}) · 샘플 PNU {sample.get('pnu')} "
          f"(지상 {sample.get('ground_floor_co')}층)")


if __name__ == "__main__":
    main()
