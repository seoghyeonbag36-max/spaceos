"""13거점 장소·리뷰 수집 상수 — kakao_local/naver_blog 의 platform13 모드가 사용.

center 좌표는 백엔드 시드(apps/backend/app/data/seoul_pages.py)의 center 와 동일 축.
GNN 노드 확장(점포)·리뷰 유사도 엣지(블로그)의 원천 수집 범위를 정의한다.
"""
from __future__ import annotations

# district_id → (lat, lng, 반경 m, 블로그 검색 대표 명칭)
DISTRICT_PLACES: dict[str, tuple[float, float, int, str]] = {
    "garosugil": (37.5205, 127.0230, 400, "가로수길"),
    "apgujeong-rodeo": (37.5273, 127.0385, 400, "압구정로데오"),
    "hongdae": (37.5551, 126.9235, 500, "홍대"),
    "yeonnam": (37.5615, 126.9245, 400, "연남동"),
    "ikseon": (37.5740, 126.9900, 300, "익선동"),
    "seochon": (37.5790, 126.9705, 400, "서촌"),
    "myeongdong": (37.5630, 126.9855, 400, "명동"),
    "euljiro": (37.5663, 126.9915, 400, "을지로 힙지로"),
    "seongsu": (37.5445, 127.0559, 500, "성수동 카페거리"),
    "seoulsup": (37.5462, 127.0430, 400, "서울숲 아틀리에길"),
    "itaewon": (37.5346, 126.9946, 400, "이태원"),
    "hannam": (37.5352, 127.0005, 500, "한남동 용리단길"),
    "songridan": (37.5087, 127.1055, 400, "송리단길"),
}
