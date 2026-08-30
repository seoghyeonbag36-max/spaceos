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
    # 도시 슬러그 — apps/backend/app/data/cities.CITIES 의 키와 같은 값.
    # 54거점이 전부 서울이던 동안은 암묵이었다. 경기 거점이 붙으면서 필드가 됐다.
    # ⚠ 여기와 백엔드 레지스트리가 어긋나면 수집은 되는데 API 가 다른 도시로 부른다
    #   → apps/backend/tests/test_city_registry.py 가 고정한다.
    city: str = "seoul"
    # 예외 표시 — 이 거점의 수치를 **다른 거점과 나란히 놓으면 안 되는 이유**를 적는다.
    # 비어 있으면 예외가 아니다. 채워져 있으면 API 응답(`caveat`)에 그대로 실려
    # 화면이 그 문구를 보여준다. 거점을 빼는 대신 **왜 다른지 밝힌 채로 넣기 위한** 자리다.
    # ⚠ 여기에 적은 문구가 곧 사용자에게 보이는 경고다. 추측이 아니라 실측을 적는다.
    caveat: str = ""


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

# ── 경기 확장 후보 (2026-08-29 등재) ─────────────────────────────────────────
# **수집 대상 등록일 뿐 화면 노출이 아니다.** Gold 산출물이 서기 전에는 API 거점 목록
# (app/data/seoul_pages.DISTRICTS)에 오르지 않는다 — 시드 zones/units 를 지어내지 않기
# 위해서다. 좌표·반경 근거와 선정 기준은 docs/plan-gyeonggi-expansion-2026-08-29.md.
#
# ⚠ 라페스타·웨스턴돔은 계획상가 밀집으로 일반 채택 기준(건물당 점포 10개 이하)을
#   넘지만, 2026-08-30 제품 판단으로 **예외 서빙**한다. 예외는 caveat 로 응답에 밝히며
#   두 상권은 합치지 않고 각각의 중심·반경과 Gold 산출물을 갖는다.
GYEONGGI_HUBS: dict[str, PageHub] = {
    "hwajeong":  PageHub("hwajeong",  "화정",       126.8330, 37.6350, 500, 700, city="goyang",
                          caveat="대표값 한계 — 집합 호실 비중이 80%를 넘는다. 공실률은 "
                                 "일반건축물 표본에 근거한다."),
    # 좌표는 카카오 로컬에서 공식 도로명주소를 대조했다(라페스타 중앙로 1305-56,
    # 웨스턴돔 정발산로 24). 350m 점포 프로브의 건물 id 중복은 2동뿐이라 별도 판정한다.
    "ilsan":     PageHub("ilsan",     "일산 라페스타", 126.768308, 37.661029, 250, 350,
                          city="goyang",
                          caveat="예외 서빙 — 계획상가 밀집으로 일반 채택 기준을 넘는다. "
                                 "공실률은 일반건축물 표본에만 근거하므로 다른 거점과 직접 "
                                 "비교하지 말 것."),
    "westerndom": PageHub("westerndom", "일산 웨스턴돔", 126.772184, 37.655885, 250, 350,
                          city="goyang",
                          caveat="예외 서빙 — 계획상가 밀집으로 일반 채택 기준을 넘는다. "
                                 "공실률은 일반건축물 표본에만 근거하므로 다른 거점과 직접 "
                                 "비교하지 말 것."),
    "geumchon":  PageHub("geumchon",  "금촌",       126.7740, 37.7600, 500, 700, city="paju"),
    "unjeong":   PageHub("unjeong",   "운정",       126.7660, 37.7220, 500, 700, city="paju"),
    # 야당역 경의중앙선(소리천로 10) 중심 — 파주 주요 상권 판정 대상이며 운정과 합치지 않는다.
    "yadang":    PageHub("yadang",    "야당",       126.761454, 37.712611, 500, 700, city="paju"),
    # 탄현 — R-ONE `경기>탄현역` **정확 매핑** 후보(좌표는 카카오 로컬 실측:
    # 37.6940,126.7611 = 고양 일산서구. 파주 탄현면과는 12km 떨어져 있다).
    # 라페스타(ilsan)가 탄현역 앵커를 4.07km 공유로 빌려 쓰는 문제의 대안으로 등재.
    "tanhyeon":  PageHub("tanhyeon",  "탄현",       126.7611, 37.6940, 500, 700, city="goyang",
                          caveat="대표값 한계 — 집합 호실 비중이 80%를 넘는다. 공실률은 "
                                 "일반건축물 표본에 근거한다."),

    # ── 2026-08-30 2차 확장 13거점 ────────────────────────────────────────────
    # 좌표는 전부 카카오 로컬 실측. 등록 전에 1차 프로브(상가정보만, 건축HUB 콜 0)로
    # 지표를 재고 넣었다 → docs/finding-goyang-paju-candidates-2026-08-30.md
    #
    # ⚠ 반경은 **이격 실측으로 정했다.** 겹치면 같은 점포를 두 번 센다(라페스타·웨스턴돔
    #   666m 에서 겪은 문제). 1.0km 미만 쌍만 반경을 줄였다:
    #     마두역 ↔ 웨스턴돔 629m · 대화역 ↔ 킨텍스 825m · 스타필드 ↔ 삼송역 690m
    # ⚠ 운정역은 **넣지 않았다** — 기존 `unjeong` 과 414m 라 이미 그 수집 반경 안이다.

    # 판정 통과 — 예외 표기 없이 서울과 같은 자격으로 선다
    "bamgasi":   PageHub("bamgasi",   "밤가시마을",   126.7778, 37.6743, 500, 700, city="goyang"),
    "wondang":   PageHub("wondang",   "원당역",      126.8429, 37.6531, 500, 700, city="goyang"),

    # 주의 구간 — 건물당 점포는 낮고 집중도만 높다. 대장으로 집합 비중을 확인한다
    "baekseok":  PageHub("baekseok",  "백석역",      126.7881, 37.6430, 500, 700, city="goyang"),
    "daehwa":    PageHub("daehwa",    "대화역",      126.7475, 37.6762, 350, 450, city="goyang"),
    "haengsin":  PageHub("haengsin",  "행신역",      126.8341, 37.6119, 500, 700, city="goyang"),
    "munsan":    PageHub("munsan",    "문산역",      126.7874, 37.8546, 500, 700, city="paju"),

    # 예외 채택(계획상가 밀집) — 라페스타와 같은 처리. 건물당 점포가 기준(10)을 넘는다
    "madu":      PageHub("madu",      "마두역",      126.7776, 37.6522, 250, 350, city="goyang",
                          caveat="계획상가 밀집 — 건물당 점포 17.1개(기준 10 초과). 공실률은 "
                                 "일반건축물만 세므로 이 거점 상업 재고의 일부에만 근거한다. "
                                 "다른 거점과 공실률을 직접 비교하지 말 것."),
    "juyeop":    PageHub("juyeop",    "주엽역",      126.7613, 37.6701, 500, 700, city="goyang",
                          caveat="계획상가 밀집 — 건물당 점포 22.4개(기준 10 초과). 공실률은 "
                                 "일반건축물만 세므로 이 거점 상업 재고의 일부에만 근거한다. "
                                 "다른 거점과 공실률을 직접 비교하지 말 것."),
    "mokdong":   PageHub("mokdong",   "운정 목동",    126.7330, 37.7331, 500, 700, city="paju",
                          caveat="계획상가 밀집 — 건물당 점포 10.2개(기준 10 초과). 공실률은 "
                                 "일반건축물만 세므로 이 거점 상업 재고의 일부에만 근거한다. "
                                 "다른 거점과 공실률을 직접 비교하지 말 것."),

    # 단일시설 — '상권'이 아니라 '건물'이다. 점포 대부분이 몰 한 채 안에 있어
    # (top10 지번 집중도 64~82% · 라페스타 40% 보다 높다) 거점 공실률이 건물 하나에 좌우된다.
    # 계획상가 밀집과는 **다른 종류의 예외**라 문구를 따로 쓴다.
    "kintex":    PageHub("kintex",    "킨텍스",      126.7458, 37.6689, 350, 450, city="goyang",
                          caveat="단일시설 상권 — 점포의 69.6%가 상위 10개 지번에 몰려 있다. "
                                 "공실률이 시설 한 채에 좌우되므로 가두 상권과 같은 축에 "
                                 "놓고 비교하지 말 것."),
    "starfield": PageHub("starfield", "스타필드 고양",  126.8954, 37.6471, 300, 400, city="goyang",
                          caveat="단일시설 상권 — 점포의 79.9%가 상위 10개 지번에 몰려 있다. "
                                 "공실률이 시설 한 채에 좌우되므로 가두 상권과 같은 축에 "
                                 "놓고 비교하지 말 것."),
    "samsong":   PageHub("samsong",   "삼송역",      126.8957, 37.6533, 300, 400, city="goyang",
                          caveat="단일시설 상권 — 점포의 63.9%가 상위 10개 지번에 몰려 있다. "
                                 "공실률이 시설 한 채에 좌우되므로 가두 상권과 같은 축에 "
                                 "놓고 비교하지 말 것."),
    "pajuoutlet": PageHub("pajuoutlet", "파주 프리미엄아울렛", 126.6963, 37.7695, 500, 700, city="paju",
                          caveat="단일시설 상권 — 점포의 82.0%가 상위 10개 지번에 몰려 있다. "
                                 "R-ONE 앵커(파주시청)와도 6.9km 떨어져 임대 대조가 약하다. "
                                 "가두 상권과 같은 축에 놓고 비교하지 말 것."),
}

# 거점 id 별칭 → 정규 slug (프론트/레거시 경로 호환).
ALIASES: dict[str, str] = {
    "gangnam-garosugil": "garosugil",
    "sinsa": "garosugil",
}


# 명시 지정용 통합 레지스트리 — **순회 대상이 아니다.**
#
# `HUBS`(서울 54)는 인자 없이 실행했을 때의 기본 순회 집합으로 그대로 둔다. 경기 거점은
# 아직 수집 전이라, 전 거점 루프에 섞이면 산출물 없는 거점이 매 실행마다 실패로 찍히고
# 거점 수를 세는 곳(coverage tier · Dockerfile 가드 · pppp_status)의 분모가 흔들린다.
# 그래서 **이름을 대고 부를 때만** 잡히게 한다.
ALL_HUBS: dict[str, PageHub] = {**HUBS, **GYEONGGI_HUBS}


def resolve(district: str) -> str | None:
    """거점 id/별칭 → 정규 slug. 미지원이면 None. 경기 거점도 여기서 잡힌다."""
    if district in ALL_HUBS:
        return district
    return ALIASES.get(district)


def get_hub(district: str) -> PageHub | None:
    """거점 id/별칭 → PageHub. 수집기·파이프라인의 CLI 진입점이 쓰는 조회구다.

    ⚠ 여기서 None 이 나오면 **조용히 건너뛰지 말 것.** 사람이 이름을 대고 부른 경우이므로
      오타이거나 미등록이다. 2026-08-30 에 `hwajeong` 을 수집하려 했을 때 수집기가
      `HUBS` 만 보고 건너뛴 뒤 exit 0 으로 끝나, 체인이 "수집 완료"로 읽었다.
    """
    slug = resolve(district)
    return ALL_HUBS.get(slug) if slug else None
