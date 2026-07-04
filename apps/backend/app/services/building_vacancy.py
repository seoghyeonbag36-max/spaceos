"""건물 단위 공실 GeoJSON 서비스 (Page 공실 레이어) — PoC: 강남구 신사동 가로수길.

건물 footprint 폴리곤 + 추정 공실률을 GeoJSON FeatureCollection 으로 제공한다.
프론트(MapShell)가 naver.maps.Polygon 으로 색칠 렌더한다.

TODO(실데이터): docs/poc-building-vacancy.md 파이프라인 —
  GIS건물통합정보 footprint ⊕ (소상공인 상가정보 활성점포 / 건축물대장 상업 호수)
  로 산출한 Gold `building_vacancy` 테이블로 아래 _GAROSU 샘플을 대체.
"""
from __future__ import annotations

# 가로수길 코어 샘플 건물 (추정 공실). status: full/partial/high/empty
_GAROSU = [
    {"id": "b1", "name": "가로수길 A빌딩", "lat": 37.5219, "lng": 127.0222, "status": "empty", "capacity": 12, "active": 1, "industry": "의류"},
    {"id": "b2", "name": "세로수길 B타워", "lat": 37.5211, "lng": 127.0231, "status": "high", "capacity": 10, "active": 4, "industry": "카페"},
    {"id": "b3", "name": "신사 C스퀘어", "lat": 37.5203, "lng": 127.0226, "status": "partial", "capacity": 8, "active": 6, "industry": "화장품"},
    {"id": "b4", "name": "가로수 D플라자", "lat": 37.5198, "lng": 127.0236, "status": "full", "capacity": 6, "active": 6, "industry": "F&B"},
    {"id": "b5", "name": "도산 E빌딩", "lat": 37.5226, "lng": 127.0238, "status": "empty", "capacity": 9, "active": 0, "industry": "편집숍"},
    {"id": "b6", "name": "신사 F빌딩", "lat": 37.5190, "lng": 127.0221, "status": "partial", "capacity": 7, "active": 5, "industry": "뷰티"},
    {"id": "b7", "name": "가로수 G동", "lat": 37.5215, "lng": 127.0245, "status": "high", "capacity": 11, "active": 3, "industry": "패션"},
    {"id": "b8", "name": "신사 H타워", "lat": 37.5207, "lng": 127.0213, "status": "full", "capacity": 5, "active": 5, "industry": "오피스"},
]

# footprint 근사 사각형 반경(도 단위) ≈ 위도 15m / 경도 15m
_D_LAT = 0.00013
_D_LNG = 0.00017

_ALIASES = {"gangnam-garosugil", "garosugil", "sinsa"}


def _ring(lat: float, lng: float) -> list[list[float]]:
    """[lng, lat] 순서(GeoJSON)의 닫힌 사각 링."""
    return [
        [lng - _D_LNG, lat - _D_LAT],
        [lng + _D_LNG, lat - _D_LAT],
        [lng + _D_LNG, lat + _D_LAT],
        [lng - _D_LNG, lat + _D_LAT],
        [lng - _D_LNG, lat - _D_LAT],
    ]


def building_vacancy_geojson(district: str) -> dict | None:
    """건물 공실 GeoJSON FeatureCollection. 미지원 거점이면 None."""
    if district not in _ALIASES:
        return None
    features = []
    for b in _GAROSU:
        vac = round((1 - b["active"] / b["capacity"]) * 100, 1)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(b["lat"], b["lng"])]},
            "properties": {
                "id": b["id"], "name": b["name"], "status": b["status"],
                "capacity": b["capacity"], "active": b["active"],
                "industry": b["industry"], "vacancy_rate": vac,
            },
        })
    return {"type": "FeatureCollection", "district": district, "features": features}
