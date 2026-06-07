"""SNS 업로드(SNS) 수집기 — 인스타 해시태그/위치태그 + 네이버 리뷰 언급량.

'SNS에 업로드가 많이 되는 정도'의 프록시로, 구별 대표 상권 해시태그 게시물 수와
네이버 블로그/플레이스 리뷰 언급량을 합산한다.

출처:
- 인스타그램 Graph API(hashtag search → recent_media): 게시물 수/좋아요/댓글
  https://developers.facebook.com/docs/instagram-api/guides/hashtag-search
  (비즈니스 계정 필요. 대안: 자체 Playwright 크롤링 또는 수집 대행)
- 썸트렌드(some.co.kr) 언급량: 블로그/인스타/뉴스/커뮤니티 통합 언급량 (보조)
- 네이버 블로그 검색 OpenAPI: 키워드별 블로그 문서 수 (total)
  https://developers.naver.com/docs/serviceapi/search/blog/blog.md

환경변수:
- INSTAGRAM_ACCESS_TOKEN / IG_USER_ID: 인스타 Graph API.
- NAVER_CLIENT_ID / NAVER_CLIENT_SECRET: 네이버 블로그 검색(보조 신호).
- 모두 없으면 프록시(base) 폴백.
"""
from __future__ import annotations

import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.config.seoul_districts import DISTRICTS

_IG_GRAPH = "https://graph.facebook.com/v19.0"
_NAVER_BLOG = "https://openapi.naver.com/v1/search/blog.json"


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    if not raw:
        return {}
    lo, hi = min(raw.values()), max(raw.values())
    span = (hi - lo) or 1.0
    return {gu: round((v - lo) / span * 100, 1) for gu, v in raw.items()}


def _ig_hashtag_count(tag: str, token: str, ig_user: str) -> int:
    """해시태그 검색 → recent_media 게시물 수(근사). 실패 시 0."""
    try:
        s = requests.get(f"{_IG_GRAPH}/ig_hashtag_search",
                         params={"user_id": ig_user, "q": tag, "access_token": token}, timeout=20)
        hid = s.json()["data"][0]["id"]
        m = requests.get(f"{_IG_GRAPH}/{hid}/recent_media",
                        params={"user_id": ig_user, "fields": "id,like_count,comments_count",
                                "access_token": token}, timeout=20)
        return len(m.json().get("data", []))
    except Exception:
        return 0


def _naver_blog_total(query: str, cid: str, secret: str) -> int:
    """네이버 블로그 검색 결과 총건수(보조 SNS 신호). 실패 시 0."""
    try:
        r = requests.get(_NAVER_BLOG, headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret},
                        params={"query": query, "display": 1}, timeout=20)
        return int(r.json().get("total", 0))
    except Exception:
        return 0


def fetch_sns_mentions() -> dict[str, float]:
    """구별 SNS 업로드 강도(해시태그 게시물 + 블로그 언급)를 0~100 정규화 반환."""
    token, ig_user = os.getenv("INSTAGRAM_ACCESS_TOKEN"), os.getenv("IG_USER_ID")
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if requests is None or not ((token and ig_user) or (cid and secret)):
        return _proxy_fallback()

    raw: dict[str, float] = {}
    try:
        for gu, meta in DISTRICTS.items():
            score = 0.0
            for kw in meta["keywords"][:3]:
                if token and ig_user:
                    score += _ig_hashtag_count(kw, token, ig_user) * 10  # 게시물 수 가중
                if cid and secret:
                    score += _naver_blog_total(kw, cid, secret) / 1000.0  # 블로그 총건수 스케일다운
            raw[gu] = score
        return _normalize(raw) if any(raw.values()) else _proxy_fallback()
    except Exception as exc:
        print(f"[sns_mentions] 실측 실패 → 프록시 폴백: {exc}")
        return _proxy_fallback()


def _proxy_fallback() -> dict[str, float]:
    return {gu: float(m["base"]["SNS"]) for gu, m in DISTRICTS.items()}


if __name__ == "__main__":
    data = fetch_sns_mentions()
    for gu, v in sorted(data.items(), key=lambda x: -x[1])[:5]:
        print(f"{gu:6} SNS={v}")
