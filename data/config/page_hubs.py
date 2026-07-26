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

    # ── 확장 41거점 (54거점 완성) — 2026-07-26 추가, 수집 미착수 ──────────
    # radius_m 은 config/platform_places.DISTRICT_PLACES 의 검증 반경(SNS·업종·R-ONE
    # 3단 검증 통과값)을 그대로 쓴다. 위 13거점은 garosugil 을 뺀 12곳이 기본값 500 을
    # 그대로 둔 상태라 상권 크기와 무관하게 균일한데, 신규 41거점은 거점별 실제 크기를
    # 따른다(예: nokdu 200m ~ jamsil 800m). "크기보다 보행경로·정체성 우선" 원칙.
    "gangnam":         PageHub("gangnam",         "강남역·강남대로",    127.0268, 37.5004, 600, 800),
    "hapjeong":        PageHub("hapjeong",        "합정",          126.9118, 37.5502, 300, 500),
    "mangwon":         PageHub("mangwon",         "망원동·망리단길",    126.9093, 37.557, 500, 700),
    "samcheong":       PageHub("samcheong",       "삼청동·북촌",      126.9831, 37.5816, 400, 600),
    "gwangjang":       PageHub("gwangjang",       "광장시장·종로4가",   127.0003, 37.5713, 500, 700),
    "dongdaemun":      PageHub("dongdaemun",      "동대문·DDP",     127.0096, 37.5664, 700, 900),
    "jamsil":          PageHub("jamsil",          "잠실·롯데월드타워",   127.1014, 37.5143, 800, 1000),
    "konkuk":          PageHub("konkuk",          "건대입구·화양동",    127.0678, 37.5404, 400, 600),
    "yeouido":         PageHub("yeouido",         "여의도",         126.9242, 37.5249, 600, 800),
    "mullae":          PageHub("mullae",          "문래동 창작촌",     126.8942, 37.5153, 700, 900),
    "banpo":           PageHub("banpo",           "고속터미널·반포",    127.0066, 37.5044, 500, 700),
    "sinchon":         PageHub("sinchon",         "신촌·이대",       126.9391, 37.5572, 600, 800),
    "yeonhui":         PageHub("yeonhui",         "연희동",         126.932, 37.5672, 500, 700),
    "cheongnyangni":   PageHub("cheongnyangni",   "청량리·경동시장",    127.0434, 37.581, 600, 800),
    "sharosugil":      PageHub("sharosugil",      "샤로수길·서울대입구",  126.9549, 37.4789, 400, 600),
    "nokdu":           PageHub("nokdu",           "녹두거리",        126.937, 37.4703, 200, 400),
    "sillim":          PageHub("sillim",          "신림역·별빛거리",    126.9294, 37.4858, 500, 700),
    "noryangjin":      PageHub("noryangjin",      "노량진",         126.9393, 37.5126, 500, 700),
    "sungshin":        PageHub("sungshin",        "성신여대·돈암",     127.0181, 37.5937, 300, 500),
    "anam":            PageHub("anam",            "안암·고려대",      127.0251, 37.5858, 500, 700),
    "cheongdam":       PageHub("cheongdam",       "청담동 명품거리",    127.0483, 37.5248, 500, 700),
    "dosan":           PageHub("dosan",           "도산공원",        127.0334, 37.5223, 500, 700),
    "nonhyeon":        PageHub("nonhyeon",        "논현동",         127.0209, 37.5105, 500, 700),
    "teheran":         PageHub("teheran",         "역삼·테헤란로",     127.0358, 37.5011, 500, 700),
    "seolleung":       PageHub("seolleung",       "선릉",          127.049, 37.5046, 600, 800),
    "yongsan":         PageHub("yongsan",         "용산역",         126.9632, 37.5285, 500, 700),
    "namdaemun":       PageHub("namdaemun",       "남대문시장",       126.9785, 37.5585, 300, 500),
    "cityhall":        PageHub("cityhall",        "시청역",         126.9768, 37.5641, 500, 700),
    "jamsilsaenae":    PageHub("jamsilsaenae",    "잠실새내",        127.0832, 37.5101, 300, 500),
    "garak":           PageHub("garak",           "가락시장",        127.1117, 37.4935, 500, 700),
    "jangan":          PageHub("jangan",          "장안동",         127.0715, 37.5712, 300, 500),
    "gongdeok":        PageHub("gongdeok",        "공덕역",         126.951, 37.5421, 400, 600),
    "gunja":           PageHub("gunja",           "군자역",         127.0802, 37.5562, 400, 600),
    "chungmuro":       PageHub("chungmuro",       "충무로",         126.9943, 37.5615, 600, 800),
    "nambu":           PageHub("nambu",           "남부터미널",       127.0195, 37.4863, 500, 700),
    # kyunghee: platform_places 는 lon 127.0535 이나 SSOT(seoul_pages)의 127.0524 를 채택(97m 차)
    "kyunghee":        PageHub("kyunghee",        "경희대",         127.0524, 37.5937, 500, 700),
    "wangsimni":       PageHub("wangsimni",       "왕십리",         127.0359, 37.5611, 500, 700),
    "sadang":          PageHub("sadang",          "사당역",         126.983, 37.478, 300, 500),
    "sukmyung":        PageHub("sukmyung",        "숙대입구",        126.9711, 37.5448, 400, 600),
    "hyehwa":          PageHub("hyehwa",          "혜화·대학로",      127.0017, 37.5832, 500, 700),
    "dangsan":         PageHub("dangsan",         "당산",          126.902, 37.5346, 300, 500),
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
