"""[Page] 건물 단위 공실 확장 거점 레지스트리 — 핵심 13거점.

garosugil PoC 파이프라인(config/garosugil.py)을 다거점으로 일반화한 단일 출처(SSOT).
각 거점은 수집기(vworld_bldg·building_vacancy)와 Gold 빌더(build_page_master)가
공유하는 **최소 상수**만 갖는다: 중심좌표(cx/cy)·수집 반경·표시명·거점 id.

시군구/법정동/본번/부번은 거점 상수가 아니라 점포·폴리곤의 PNU(lnoCd) 19자리에서
건별로 파생하므로(수집기 _jibun 참조) 레지스트리에 둘 필요가 없다. 즉 신규 거점을
추가할 때 필요한 것은 중심좌표와 반경뿐이다.

중심좌표 출처: apps/backend/app/data/seoul_pages.py DISTRICTS[*].center([lat, lng]).
  → cx=경도=center[1], cy=위도=center[0].
garosugil 은 2026-07-19 지상검증(정확도 75%)을 통과한 산출물이므로 원
config/garosugil.py 의 검증된 반경(400/600)을 그대로 보존한다 (재수집 대상 아님).

거점 id 는 seoul_pages.py DISTRICTS id 와 동일. 프론트가 heatmap ?district= 로 넘기는 값.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageHub:
    slug: str                  # bronze/gold 하위 폴더명 (= 거점 id)
    name: str                  # 표시명 (프론트 패널 제목)
    cx: float                  # 중심 경도(lon)
    cy: float                  # 중심 위도(lat)
    radius_m: int = 500        # V-World 폴리곤 수집 bbox 반경(±m). 대각 코너는 ≈radius×√2 까지 커버
    stores_radius_m: int = 700 # 점포 수집 반경 — 폴리곤 커버리지 ⊇ 원칙(경계 건물 empty 오판 방지)


# 핵심 13거점 (platform13 원년 거점 집합). garosugil 은 검증 반경 유지.
HUBS: dict[str, PageHub] = {
    "garosugil":       PageHub("garosugil",       "신사동 가로수길", 127.0230, 37.5205, 400, 600),
    "apgujeong-rodeo": PageHub("apgujeong-rodeo", "압구정로데오",   127.0385, 37.5273),
    "hongdae":         PageHub("hongdae",         "홍대",          126.9235, 37.5551),
    "yeonnam":         PageHub("yeonnam",         "연남동",         126.9245, 37.5615),
    "ikseon":          PageHub("ikseon",          "익선동",         126.9900, 37.5740),
    "seochon":         PageHub("seochon",         "서촌",          126.9705, 37.5790),
    "myeongdong":      PageHub("myeongdong",      "명동",          126.9855, 37.5630),
    "euljiro":         PageHub("euljiro",         "을지로(힙지로)", 126.9915, 37.5663),
    "seongsu":         PageHub("seongsu",         "성수동 카페거리", 127.0559, 37.5445),
    "seoulsup":        PageHub("seoulsup",        "서울숲 아틀리에길", 127.0430, 37.5462),
    "itaewon":         PageHub("itaewon",         "이태원",         126.9946, 37.5346),
    "hannam":          PageHub("hannam",          "한남동·용리단길", 127.0005, 37.5352),
    "songridan":       PageHub("songridan",       "송리단길",       127.1055, 37.5087),
}

# 거점 id 별칭 → 정규 slug (프론트/레거시 경로 호환).
ALIASES: dict[str, str] = {
    "gangnam-garosugil": "garosugil",
    "sinsa": "garosugil",
}


def resolve(district: str) -> str | None:
    """거점 id/별칭 → 정규 slug. 미지원이면 None."""
    if district in HUBS:
        return district
    return ALIASES.get(district)


def get_hub(district: str) -> PageHub | None:
    slug = resolve(district)
    return HUBS.get(slug) if slug else None
