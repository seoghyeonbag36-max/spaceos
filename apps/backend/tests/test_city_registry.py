"""도시 레지스트리 교차 불변식 — 수집(page_hubs)과 서빙(app.data.cities)이 같은 도시를 말하는가.

도시 축은 **두 파일에 나뉘어 있다**: 수집기는 `data/config/page_hubs.PageHub.city` 를 보고,
API 는 `app/data/cities.CITIES` 를 본다. 둘이 어긋나면 수집은 되는데 API 가 그 거점을
다른 도시로 부른다 — 조용히 어긋나는 종류의 결함이라 테스트로 고정한다.

`data/` 는 백엔드 패키지 밖이라 import 경로가 없다. 그래서 파일을 **경로로 로드**한다
(tests 가 data/gold 산출물을 경로로 읽는 것과 같은 방식).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from app.data import cities

_REPO = Path(__file__).resolve().parents[3]
_PAGE_HUBS = _REPO / "data" / "config" / "page_hubs.py"


def _load_page_hubs():
    """data/config/page_hubs.py 를 경로로 로드 (백엔드에서 import 할 수 없는 패키지)."""
    spec = importlib.util.spec_from_file_location("_page_hubs_probe", _PAGE_HUBS)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_page_hubs_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_every_hub_city_is_registered():
    """수집 거점이 말하는 도시는 전부 서빙 레지스트리에 있어야 한다.

    없으면 `cities.of_gu` 가 그 거점을 **조용히 서울로 눕힌다** — 경기 거점이
    서울 전용 소스를 가진 것처럼 응답하게 된다.
    """
    ph = _load_page_hubs()
    hubs = {**ph.HUBS, **getattr(ph, "GYEONGGI_HUBS", {})}
    unknown = sorted({h.city for h in hubs.values()} - set(cities.CITIES))
    assert not unknown, f"page_hubs 가 모르는 도시를 가리킨다: {unknown}"


def test_seoul_hubs_stay_seoul():
    """원년 54거점의 도시는 서울이어야 한다 — 기본값이 바뀌면 전 거점이 흔들린다."""
    ph = _load_page_hubs()
    assert {h.city for h in ph.HUBS.values()} == {"seoul"}
    assert len(ph.HUBS) == 54


def test_gyeonggi_hubs_do_not_mutate_seoul_seed():
    """경기 후보는 서울 시드에 섞지 않고 Gold 유무로 별도 서빙해야 한다.

    Gold 전 후보와 Gold 후 실측 거점이 같은 레지스트리에 있으므로, 서울 시드와의 분리는
    `DISTRICTS`가 아니라 `PAGES` 조립 단계에서 유지돼야 한다.
    """
    ph = _load_page_hubs()
    from app.data.seoul_pages import DISTRICTS_BY_ID

    gg = set(getattr(ph, "GYEONGGI_HUBS", {}))
    assert gg, "경기 후보가 등재돼 있어야 한다"
    assert not (gg & set(DISTRICTS_BY_ID)), "경기 후보가 서울 시드를 변형했다"


def test_ilsan_exceptions_are_separate_served_pages():
    """라페스타·웨스턴돔은 예외 근거를 밝힌 서로 다른 Gold 거점이어야 한다."""
    ph = _load_page_hubs()
    from app.services import districts as svc

    # 거점 id는 계속 늘 수 있으므로 표시명과 예외 계약에서 의무 거점을 찾는다.
    exceptions = [h for h in ph.GYEONGGI_HUBS.values() if h.caveat]
    required = {
        label: next((h for h in exceptions if label in h.name), None)
        for label in ("라페스타", "웨스턴돔")
    }
    assert all(required.values()), required
    lafesta, westerndom = required.values()
    assert lafesta.slug != westerndom.slug
    assert (lafesta.cx, lafesta.cy) != (westerndom.cx, westerndom.cy)

    for hub in required.values():
        row = svc.get_summary(hub.slug)
        assert row is not None, f"{hub.name}: Gold가 없어 API 서빙 목록에서 빠졌다"
        assert row["measured_only"] is True
        assert row["vacancy_source"] == "gold"
        assert row["caveat"].startswith("예외 서빙")


@pytest.mark.parametrize("pnu,expected", [
    ("1168010700105340012", "seoul"),    # 강남구 신사동
    ("4128110300100010000", "goyang"),   # 고양 덕양구
    ("4128510300100010000", "goyang"),   # 고양 일산동구
    ("4148010300100010000", "paju"),     # 파주시
])
def test_pnu_resolves_to_city(pnu, expected):
    """PNU 앞 5자리(법정 시군구 코드)로 도시가 갈려야 한다.

    좌표는 경계에서 흔들리지만 PNU 는 안 흔들린다 — 산출물이 정말 그 도시 것인지
    검증하는 축이다. 2026-08-29 실측: 5거점 15,605건 전수 판정 일치 100%.
    """
    city = cities.of_pnu(pnu)
    assert city is not None and city.id == expected


def test_unknown_city_id_raises_instead_of_defaulting():
    """모르는 도시 슬러그는 서울로 눕히지 않고 터져야 한다.

    조용히 서울이 되면 경기 거점이 TRDAR·생활인구를 가진 것처럼 응답한다.
    """
    with pytest.raises(KeyError):
        cities.by_id("nowhere")


def test_seoul_only_sources_are_flagged_per_city():
    """서울 전용 소스 3종은 도시별로 갈려 있어야 한다 — 없는 축을 있는 척하지 않는다."""
    assert cities.by_id("seoul").has_trdar
    assert cities.by_id("seoul").has_living_pop
    for cid in ("goyang", "paju"):
        c = cities.by_id(cid)
        assert not c.has_trdar, f"{cid}: 경기에는 서울 상권분석(TRDAR)이 서지 않는다"
        assert not c.has_living_pop, f"{cid}: 경기에는 서울 생활인구가 서지 않는다"
        assert not c.has_city_events


def test_district_summary_carries_city():
    """API 응답에 도시가 실려야 프론트가 서울과 경기를 가른다."""
    from app.services import districts as svc

    rows = svc.list_summaries()
    assert rows
    assert len(rows) == len(svc.PAGES_BY_ID)
    assert {r["id"] for r in rows} == set(svc.PAGES_BY_ID)
    for row in rows:
        assert row["city"] and row["city_name"], row["id"]
        page = svc.PAGES_BY_ID[row["id"]]
        measured_only = bool(page.get("measured_only"))
        assert row["measured_only"] is measured_only, row["id"]
        # 시드는 서울, 실측 거점은 PAGES 에 명시된 등록 도시를 그대로 따라야 한다.
        if measured_only:
            assert page.get("city"), row["id"]
            expected = cities.by_id(page["city"])
        else:
            expected = cities.by_id("seoul")
        assert row["city"] == expected.id, row["id"]
        assert row["city_name"] == expected.short, row["id"]


def test_explicit_gyeonggi_slug_resolves_in_collectors():
    """경기 거점을 **이름으로 부르면** 수집기가 찾아야 한다.

    2026-08-30: `GYEONGGI_HUBS` 를 별도 dict 로 두었는데 수집기·파이프라인은 `HUBS` 만
    보고 있었다. `building_vacancy hwajeong` 이 "미등록 거점 — 건너뜀"을 찍고 **exit 0**
    으로 끝나, 체인이 수집 성공으로 읽었다. 조회는 `get_hub`(ALL_HUBS)로 모았고
    미등록은 이제 SystemExit 이다. 이 테스트는 그 되돌림을 막는다.
    """
    ph = _load_page_hubs()
    for slug in ph.GYEONGGI_HUBS:
        assert ph.get_hub(slug) is not None, f"{slug}: 이름을 대고 불러도 안 잡힌다"
    assert ph.get_hub("sinsa").slug == "garosugil", "별칭 해석이 깨졌다"
    assert ph.get_hub("존재하지않는거점") is None


def test_default_iteration_stays_seoul_only():
    """인자 없이 도는 전 거점 루프는 여전히 서울 54곳이어야 한다.

    경기 거점이 기본 순회에 섞이면 산출물 없는 거점이 매 실행마다 실패로 찍히고,
    거점 수를 세는 곳(coverage tier · Dockerfile 가드 · pppp_status)의 분모가 흔들린다.
    """
    ph = _load_page_hubs()
    assert len(ph.HUBS) == 54
    # 확장 배치는 늘어난다(08-30 서울 2차 12 · 경기 20). 고정할 것은 **개수가 아니라
    # 구조**다 — 기본 순회(HUBS)는 54 로 남고, ALL_HUBS 는 그 배치들의 합이며,
    # 어느 배치도 서로 슬러그를 겹치지 않는다. 종전에는 `54 + GYEONGGI` 로 적혀 있어
    # 배치가 하나 늘 때마다 깨졌다(09-01 에 86 != 74 로 배포가 막혔다).
    batches = (ph.SEOUL_BATCH2_HUBS, ph.GYEONGGI_HUBS)
    assert len(ph.ALL_HUBS) == 54 + sum(len(b) for b in batches)
    for b in batches:
        assert not (set(b) & set(ph.HUBS))
    # 슬러그 충돌은 조용히 거점을 **덮는다** — 08-30 에 파주 목동이 양천 목동에 덮여
    # ALL_HUBS 가 86 이 아니라 85 로 나왔다. 그래서 배치끼리도 겹치면 안 된다.
    assert not (set(ph.SEOUL_BATCH2_HUBS) & set(ph.GYEONGGI_HUBS))


def test_caveat_is_carried_from_hub_to_api():
    """예외 표시(`caveat`)가 거점 정의에서 API 응답까지 그대로 실려야 한다.

    2026-08-30: 일산 라페스타·웨스턴돔은 계획상가 밀집이라 공실 분모가 상업 재고의
    일부만 덮는다(상업 153동 중 집합건물 103동). **거점을 빼는 대신 왜 다른지 밝힌 채로
    싣기로** 결정했고(사용자 판단), 그 경고가 사라지면 빌린 값이 실측처럼 보인다.
    근거: docs/finding-ilsan-verdict-2026-08-30.md
    """
    ph = _load_page_hubs()
    from app.services import districts as svc

    hub_caveats = {s: h.caveat for s, h in ph.ALL_HUBS.items() if getattr(h, "caveat", "")}
    assert hub_caveats, "예외 표시가 붙은 거점이 하나도 없다 — caveat 이 지워졌는지 확인"

    rows = {r["id"]: r for r in svc.list_summaries()}
    for slug, text in hub_caveats.items():
        if slug not in rows:          # 아직 Gold 가 안 선 거점은 목록에 없다(정상)
            continue
        assert rows[slug].get("caveat") == text, f"{slug}: caveat 이 응답까지 안 실린다"

    # 예외가 아닌 거점은 비어 있어야 한다 — 전 거점에 경고가 붙으면 경고가 무의미해진다
    normal = [r for sid, r in rows.items() if sid not in hub_caveats]
    assert normal and all(not r.get("caveat") for r in normal)
