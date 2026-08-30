"""도시 레지스트리 — 거점이 어느 시(市)에 속하는지, 그 시에 어떤 소스가 서는지.

## 왜 필요한가

54거점은 전부 서울이라 지금까지 도시가 **암묵**이었다(`seoul_pages.py`라는 파일명이
곧 도시였다). 고양·파주를 붙이려면 그 암묵을 필드로 끌어내야 한다 —
`city` 가 없으면 프론트가 거점 목록에서 서울과 경기를 구분할 수 없고, 백엔드는
"이 거점에 TRDAR 이 서는가"를 물을 방법이 없다.

## 두 축을 한 곳에서 정한다

1. **소속** — `gu`(자치구·일반구) → 도시. 거점 시드가 이미 `gu` 를 갖고 있으므로
   54개 항목을 건드리지 않고 도시를 유도할 수 있다.
2. **소스 세트** — 그 도시에 서울 전용 소스(TRDAR·서울 생활인구·서울 문화행사)가
   서는가. 서지 않으면 그 자리는 **비워 두고 화면이 그 사실을 밝힌다**(경기 대체
   소스 배선은 docs/plan-gyeonggi-expansion-2026-08-29.md Phase 3).

⚠ 도시를 늘릴 때는 `data/config/page_hubs.PageHub.city` 도 같이 늘린다. 두 곳이
   어긋나면 수집은 되는데 API 가 그 거점을 다른 도시로 부르게 된다 —
   `tests/test_city_registry.py` 가 이 어긋남을 고정한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class City:
    id: str                      # 도시 슬러그 (page_hubs.PageHub.city 와 같은 값)
    name: str                    # 정식 명칭
    short: str                   # 화면 표기 (칩·필터)
    sido: str                    # 시도명
    sgg_codes: frozenset[str]    # 법정 시군구 코드 5자리 — PNU 앞 5자리와 대조한다
    gus: frozenset[str]          # 이 도시에 속한 구(자치구·일반구) 또는 시 이름
    # 서울 전용 소스가 서는가. False 면 그 축은 **비어 있는 것이 정상**이다.
    has_trdar: bool = False          # 상권분석(추정매출·유동·연령·성별)
    has_living_pop: bool = False     # 생활인구(행정동·집계구 24시간)
    has_city_events: bool = False    # 문화행사 실데이터
    note: str = ""


_SEOUL_GUS = frozenset({
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구",
    "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구",
    "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구",
    "강동구",
})
# 서울 25 자치구 코드 11110~11740 (10 단위). 전부 적지 않고 접두로 판정한다.
_SEOUL_SGG = frozenset({f"111{n:02d}" for n in range(10, 100)} |
                       {f"112{n:02d}" for n in range(10, 100)} |
                       {f"113{n:02d}" for n in range(10, 100)} |
                       {f"114{n:02d}" for n in range(10, 100)} |
                       {f"115{n:02d}" for n in range(10, 100)} |
                       {f"116{n:02d}" for n in range(10, 100)} |
                       {f"117{n:02d}" for n in range(10, 100)})

CITIES: dict[str, City] = {
    "seoul": City(
        id="seoul", name="서울특별시", short="서울", sido="서울특별시",
        sgg_codes=_SEOUL_SGG, gus=_SEOUL_GUS,
        has_trdar=True, has_living_pop=True, has_city_events=True,
        note="원년 도시 — 54거점. 서울 전용 소스 3종이 전부 선다",
    ),
    "goyang": City(
        id="goyang", name="고양특례시", short="고양", sido="경기도",
        # 41281 덕양구 · 41285 일산동구 · 41287 일산서구
        sgg_codes=frozenset({"41281", "41285", "41287"}),
        gus=frozenset({"덕양구", "일산동구", "일산서구"}),
        note="R-ONE 표본 2곳(고양시청·탄현역). 계획상가 밀집 주의 → plan §3-B",
    ),
    "paju": City(
        id="paju", name="파주시", short="파주", sido="경기도",
        sgg_codes=frozenset({"41480"}),
        gus=frozenset({"파주시"}),
        note="R-ONE 표본 1곳(파주시청). 운정은 공유 매핑 대상",
    ),
}

DEFAULT_CITY = "seoul"


def by_id(city_id: str | None) -> City:
    """도시 슬러그 → City. 모르는 값은 서울로 눕히지 않고 KeyError 를 낸다 —
    조용히 서울이 되면 경기 거점이 서울 소스를 가진 것처럼 응답한다."""
    return CITIES[city_id or DEFAULT_CITY]


def of_gu(gu: str | None) -> City:
    """거점의 `gu` 로 도시를 판정. 어느 도시에도 안 걸리면 서울(원년 기본값).

    ⚠ 새 도시를 넣을 때 `gus` 를 채우지 않으면 그 거점이 **조용히 서울이 된다**.
       `tests/test_city_registry.py::test_every_hub_city_is_registered` 가 막는다.
    """
    for city in CITIES.values():
        if gu in city.gus:
            return city
    return CITIES[DEFAULT_CITY]


def of_pnu(pnu: str | None) -> City | None:
    """PNU 19자리 앞 5자리(법정 시군구 코드) → City. 미등록 지역이면 None.

    수집 산출물이 **정말 그 도시 것인지** 좌표가 아니라 코드로 검증하는 자리다
    (좌표는 경계에서 흔들리지만 PNU 는 안 흔들린다).
    """
    if not pnu or len(pnu) < 5:
        return None
    sgg = pnu[:5]
    for city in CITIES.values():
        if sgg in city.sgg_codes:
            return city
    return None
