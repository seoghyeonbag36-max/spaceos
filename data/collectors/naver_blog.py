"""[B단계·Program] 네이버 검색(블로그) + 데이터랩 트렌드 수집기 (docs §5-B).

`NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`(developers.naver.com — 검색·데이터랩 사용
설정)으로 거점 키워드의 블로그 리뷰와 월별 검색 트렌드를 수집한다.
용도: Program 의 콘텐츠 컨텍스트(리뷰 키워드·감성 원문) + 상권 관심도 시계열.

실행: python -m data.collectors.naver_blog
"""
from __future__ import annotations

import datetime
import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import load_env, save_json
from data.config.garosugil import BLOG_KEYWORDS, SLUG, TREND_KEYWORD_GROUPS

_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"
_DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
_DISPLAY = 100          # 요청당 최대
_PAGES = 3              # 키워드당 300건 (start 상한 1000)


def _headers() -> dict[str, str] | None:
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        return None
    return {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}


def collect_blog() -> list[dict]:
    """키워드별 최신 블로그 글 수집 → link 기준 중복 제거 → Bronze 저장."""
    headers = _headers()
    if headers is None or requests is None:
        print("[naver_blog] NAVER_CLIENT_ID/SECRET 미설정(또는 requests 없음) — 건너뜀")
        return []

    seen: dict[str, dict] = {}
    for kw in BLOG_KEYWORDS:
        got = 0
        for page in range(_PAGES):
            try:
                resp = requests.get(
                    _BLOG_URL, headers=headers,
                    params={"query": kw, "display": _DISPLAY,
                            "start": page * _DISPLAY + 1, "sort": "date"},
                    timeout=15,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
            except Exception as exc:
                print(f"  '{kw}' p{page + 1}: 실패 — {exc}")
                break
            for it in items:
                it["_query"] = kw  # 어떤 키워드로 잡혔는지 보존 (원문 필드는 무가공)
                seen[it.get("link", "")] = it
            got += len(items)
            if len(items) < _DISPLAY:
                break
        print(f"  '{kw}': {got}건")

    posts = list(seen.values())
    save_json(posts, SLUG, "naver_blog.json")
    return posts


def collect_trend() -> dict:
    """데이터랩 검색어 트렌드(최근 24개월·월 단위) → Bronze 저장."""
    headers = _headers()
    if headers is None or requests is None:
        return {}

    end = datetime.date.today()
    start = end.replace(year=end.year - 2)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": "month",
        "keywordGroups": [
            {"groupName": name, "keywords": kws}
            for name, kws in TREND_KEYWORD_GROUPS.items()
        ][:5],  # API 제한: 그룹 최대 5개
    }
    try:
        resp = requests.post(
            _DATALAB_URL, headers={**headers, "Content-Type": "application/json"},
            json=body, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"[naver_blog] 데이터랩 실패 — {exc}")
        return {}

    save_json(data, SLUG, "naver_datalab_trend.json")
    return data


def collect_platform13_blog() -> list[dict]:
    """[Platform·GNN/Program] 27거점 블로그 리뷰 수집 — 리뷰 유사도 엣지·감성 피처 원천.

    거점당 '{명칭} 맛집'·'{명칭} 카페' 2키워드 × 2페이지(최대 400건). 행에 district_id 부가.
    Bronze: data/bronze/platform13/{날짜}/naver_blog.json
    """
    from data.config.platform_places import DISTRICT_PLACES

    headers = _headers()
    if headers is None or requests is None:
        print("[naver_blog] NAVER_CLIENT_ID/SECRET 미설정(또는 requests 없음) — 건너뜀")
        return []

    seen: dict[str, dict] = {}
    for did, (_lat, _lng, _radius, name) in DISTRICT_PLACES.items():
        got = 0
        for kw in (f"{name} 맛집", f"{name} 카페"):
            for page in range(2):
                try:
                    resp = requests.get(
                        _BLOG_URL, headers=headers,
                        params={"query": kw, "display": _DISPLAY,
                                "start": page * _DISPLAY + 1, "sort": "date"},
                        timeout=15,
                    )
                    resp.raise_for_status()
                    items = resp.json().get("items", [])
                except Exception as exc:
                    print(f"  {did} '{kw}' p{page + 1}: 실패 — {exc}")
                    break
                for it in items:
                    it["_query"] = kw
                    it["district_id"] = did
                    seen[it.get("link", "")] = it
                got += len(items)
                if len(items) < _DISPLAY:
                    break
        print(f"  {did}: {got}건")

    posts = list(seen.values())
    save_json(posts, "platform13", "naver_blog.json")
    return posts


if __name__ == "__main__":
    import sys

    load_env()
    if "--platform13" in sys.argv:
        collect_platform13_blog()
    else:
        collect_blog()
        collect_trend()
