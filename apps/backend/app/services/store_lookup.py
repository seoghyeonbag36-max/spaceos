"""가게 반자동 조회 — Program 입력을 공식 API 로 미리 채운다 (2026-08-03).

네이버 플레이스의 방문자 리뷰·사진·메뉴에는 공식 API 가 없다(docs/feature-program.md §0).
그래서 **공식 API 로 얻을 수 있는 것만** 대신 채운다:

  카카오 로컬 키워드 검색 → 상호·카테고리·주소·좌표 (가게 특정)
  네이버 블로그 검색     → 리뷰성 텍스트 스니펫

리뷰라고 부르지 않는다. 블로그 스니펫은 광고 글이 섞이고 방문자 평점도 없다 —
`source` 로 출처를 밝혀 화면이 실제 무엇인지 말하게 한다.

**동명이지(同名異地) 방어가 이 모듈의 핵심이다.** 상호만으로 블로그를 질의하면 다른 시도의
같은 이름 가게 글이 섞인다(2026-08-01 실사: 54거점 코퍼스의 7.3%가 타 지역, 가로수길은
'창원'이 2번째 키워드였다). 여기서는 두 겹으로 막는다:
  1) 가게를 **후보 목록에서 사람이 고른다** → 주소가 확정된다
  2) 그 주소의 동(洞)을 질의에 붙인다 → "연남동 맡기다"

의존성은 표준 라이브러리만 쓴다. 배포(Vercel) 서버리스 의존성이 fastapi/pydantic 뿐이라
requests·httpx 를 쓰면 프로덕션에서만 죽는다.
"""
from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import settings
from app.data.seoul_pages import DISTRICTS_BY_ID

_KAKAO_KEYWORD = "https://dapi.kakao.com/v2/local/search/keyword.json"
_NAVER_BLOG = "https://openapi.naver.com/v1/search/blog.json"
_TIMEOUT_S = 8

# 거점을 지정했을 때 후보를 좁히는 반경. 거점 상권 하나가 대략 이 정도 크기다.
_DISTRICT_RADIUS_M = 1500

# 블로그 스니펫에서 걷어낼 것들
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# 주소에서 동(洞)을 뽑는다 — "서울 마포구 연남동 227-15" → "연남동".
# 가(街)·로(路) 주소도 상권 이름으로 그대로 쓸 수 있어 함께 받는다. 중간 숫자를 허용해야
# "을지로3가"가 잡힌다 — [가-힣]+ 만으로는 '3'에서 끊겨 통째로 놓쳤다(2026-08-03 실측).
_DONG_RE = re.compile(r"([가-힣]+[0-9]*(?:동|가|로))\s")


def _get_json(url: str, params: dict[str, object], headers: dict[str, str]) -> dict:
    """GET → JSON. 실패는 예외로 올린다(호출부가 source="unavailable" 로 바꾼다)."""
    qs = urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(f"{url}?{qs}", headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _clean(text: str) -> str:
    """검색 API 가 붙여주는 <b> 강조 태그와 HTML 엔티티를 걷어낸다."""
    t = _TAG_RE.sub("", text or "")
    for src, dst in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                     ("&#39;", "'"), ("&nbsp;", " ")):
        t = t.replace(src, dst)
    return _WS_RE.sub(" ", t).strip()


def dong_of(address: str | None) -> str | None:
    """주소에서 동(洞) 토큰. 없으면 None — 없으면 질의를 '서울'로만 좁힌다."""
    if not address:
        return None
    m = _DONG_RE.search(address + " ")
    return m.group(1) if m else None


def _leaf_category(category_name: str) -> str:
    """카카오 category_name("음식점 > 술집 > 이자카야")의 말단만 쓴다."""
    return (category_name or "").split(">")[-1].strip()


def find_places(query: str, district_id: str | None = None, limit: int = 10) -> dict:
    """카카오 로컬 키워드 검색 — 상호로 가게 후보를 찾는다.

    district_id 를 주면 그 거점 중심 반경으로 좁히고 거리(distance_m)를 함께 준다.
    거점 밖 가게도 다루므로 반경은 **정렬 힌트이지 필터가 아니다** — 카카오가 반경 안에서
    아무것도 못 찾으면 반경 없이 한 번 더 친다.
    """
    if not settings.kakao_rest_api_key:
        return {"query": query, "places": [], "source": "unavailable",
                "note": "KAKAO_REST_API_KEY 미설정 — data/.env 를 확인하라"}

    headers = {"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"}
    base: dict[str, object] = {"query": query, "size": min(max(limit, 1), 15)}

    d = DISTRICTS_BY_ID.get(district_id or "")
    attempts: list[dict[str, object]] = []
    if d and d.get("center"):
        lat, lng = d["center"]
        attempts.append({**base, "y": lat, "x": lng, "radius": _DISTRICT_RADIUS_M, "sort": "distance"})
    attempts.append(base)

    docs: list[dict] = []
    try:
        for params in attempts:
            docs = _get_json(_KAKAO_KEYWORD, params, headers).get("documents", [])
            if docs:
                break
    except (urllib.error.URLError, socket.timeout, ValueError, KeyError) as exc:
        return {"query": query, "places": [], "source": "unavailable",
                "note": f"카카오 로컬 조회 실패: {exc}"}

    places = []
    for doc in docs[:limit]:
        dist = doc.get("distance")
        places.append({
            "name": doc.get("place_name", ""),
            "category": _leaf_category(doc.get("category_name", "")),
            "address": doc.get("address_name") or None,
            "road_address": doc.get("road_address_name") or None,
            "phone": doc.get("phone") or None,
            "lat": float(doc["y"]) if doc.get("y") else None,
            "lng": float(doc["x"]) if doc.get("x") else None,
            "place_url": doc.get("place_url") or None,
            "distance_m": int(dist) if dist not in (None, "") else None,
        })
    return {"query": query, "places": places, "source": "kakao-local",
            "note": None if places else "검색 결과 없음 — 상호를 지도에 표기된 그대로 넣어보라"}


def find_reviews(name: str, address: str | None = None, limit: int = 15) -> dict:
    """네이버 블로그 검색 — 그 가게를 언급한 글의 스니펫을 모은다.

    질의는 `{동} {상호}` 로 좁힌다(동을 못 뽑으면 `서울 {상호}`). 그래도 남는 오염은
    **상호가 실제로 본문에 있는 글만** 남겨 거른다 — 상호가 안 나오는 글은 그 가게 얘기가
    아니거나 목록형 광고다.
    """
    if not (settings.naver_client_id and settings.naver_client_secret):
        return {"query": name, "reviews": [], "source": "unavailable",
                "note": "NAVER_CLIENT_ID/SECRET 미설정 — data/.env 를 확인하라"}

    region = dong_of(address) or "서울"
    query = f"{region} {name}"
    headers = {"X-Naver-Client-Id": settings.naver_client_id,
               "X-Naver-Client-Secret": settings.naver_client_secret}
    # 상호 필터로 걸러낼 몫을 감안해 넉넉히 받는다(상한 100).
    params = {"query": query, "display": min(limit * 4, 100), "sort": "sim"}

    try:
        items = _get_json(_NAVER_BLOG, params, headers).get("items", [])
    except (urllib.error.URLError, socket.timeout, ValueError, KeyError) as exc:
        return {"query": query, "reviews": [], "source": "unavailable",
                "note": f"네이버 블로그 조회 실패: {exc}"}

    # 공백을 지운 상호로 비교한다 — "연남 맡기다"/"연남맡기다" 표기 흔들림을 흡수한다.
    needle = name.replace(" ", "")
    seen: set[str] = set()
    reviews: list[str] = []
    dropped = 0
    for it in items:
        text = _clean(f"{it.get('title', '')} {it.get('description', '')}")
        if needle and needle not in text.replace(" ", ""):
            dropped += 1
            continue
        if text in seen or len(text) < 20:
            continue
        seen.add(text)
        reviews.append(text)
        if len(reviews) >= limit:
            break

    note = "블로그 검색 스니펫이다 — 방문자 리뷰가 아니고 광고 글이 섞일 수 있다."
    if dropped:
        note += f" 상호가 본문에 없는 {dropped}건은 제외했다."
    if not reviews:
        note = (f"'{query}' 로 검색된 글이 없다. 상호를 바꾸거나 리뷰를 직접 붙여넣어라. "
                + note)
    return {"query": query, "reviews": reviews, "source": "naver-blog", "note": note}
