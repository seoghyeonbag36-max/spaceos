"""[B단계·Program/Posting] 카카오 로컬 수집기 — 장소·카테고리 크로스체크 (docs §8-E).

`KAKAO_REST_API_KEY`(developers.kakao.com 즉시발급)로 거점 반경의 현존 점포를
카테고리별로 수집한다. 용도: 상가정보 API(§1-A)의 폐업 반영 지연 보완 + 업종
카테고리·place_url(리뷰 크롤링 시드) 확보.

⚠️ 카카오 로컬은 쿼리당 최대 45건(15건×3페이지)만 노출 — 반경·카테고리를 잘게
쪼개서 45건 미만이 되도록 분할 수집해야 전수에 가깝다(TODO: 격자 분할).

실행: python -m data.collectors.kakao_local
"""
from __future__ import annotations

import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import load_env, save_json
from data.config.garosugil import CX, CY, RADIUS_M, SLUG

_URL = "https://dapi.kakao.com/v2/local/search/category.json"

# 상권 분석에 쓰는 카테고리 그룹 코드
CATEGORY_GROUPS: dict[str, str] = {
    "FD6": "음식점",
    "CE7": "카페",
    "CS2": "편의점",
    "HP8": "병원",
    "PM9": "약국",
    "AD5": "숙박",
    "CT1": "문화시설",
}


def _search_category(key: str, group: str) -> list[dict]:
    """카테고리 1개를 페이징 수집 (최대 45건 제한)."""
    docs: list[dict] = []
    for page in range(1, 4):  # size 15 × 3페이지 = 노출 상한 45건
        resp = requests.get(
            _URL,
            headers={"Authorization": f"KakaoAK {key}"},
            params={
                "category_group_code": group,
                "x": CX, "y": CY, "radius": RADIUS_M,
                "page": page, "size": 15, "sort": "distance",
            },
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        docs.extend(body.get("documents", []))
        if body.get("meta", {}).get("is_end", True):
            break
    return docs


def collect() -> list[dict]:
    """카테고리별 반경 수집 → 중복(장소 id) 제거 → Bronze 저장."""
    key = os.getenv("KAKAO_REST_API_KEY")
    if not key or requests is None:
        print("[kakao_local] KAKAO_REST_API_KEY 미설정(또는 requests 없음) — 건너뜀")
        return []

    seen: dict[str, dict] = {}
    for group, label in CATEGORY_GROUPS.items():
        try:
            docs = _search_category(key, group)
        except Exception as exc:
            print(f"  {group}({label}): 실패 — {exc}")
            continue
        capped = " ★45건 상한 — 분할 필요" if len(docs) >= 45 else ""
        print(f"  {group}({label}): {len(docs)}건{capped}")
        for d in docs:
            seen[d.get("id", d.get("place_url", ""))] = d

    places = list(seen.values())
    save_json(places, SLUG, "kakao_places.json")
    return places


if __name__ == "__main__":
    load_env()
    collect()
