"""실측 거점 — 시드 없이 **Gold 산출물만으로** 서는 거점 목록.

## 왜 필요한가

`seoul_pages.DISTRICTS` 는 시드다. 한 항목이 서려면 `zones`(감성구역·리뷰수)·`units`
(공실유닛 임대료·권리금)·`events`·`insta` 를 사람이 적어야 한다. 서울 54거점은 그렇게
만들어졌고 지금도 그 값들이 화면에 쓰인다.

고양·파주에는 그 실측이 없다. 그런데 **Page 축은 이미 실측으로 서 있다** — 2026-08-30
화정은 건물 386동·Tier1(대장)·앵커 격차 -2.72%p 로 서울 54거점과 같은 기준을 통과했고
`/heatmap/buildings?district=hwajeong` 는 그 시점에 이미 386 features 를 응답했다.
막고 있던 것은 데이터가 아니라 **거점 목록의 스키마**였다.

그래서 두 갈래 중 하나를 골라야 했고(2026-08-30 판단), 고른 것은 이것이다:

    시드를 지어내지 않는다. 대신 **비어 있음이 1급 상태**인 거점 항목을 만든다.

`zones`·`units`·`events`·`insta` 는 빈 리스트로 두고, 그 축을 소비하는 값
(`sentiment`·`reviews`·`rec_top`)은 0 이 아니라 **None** 으로 내려보낸다. 0 은 "쟀더니
0" 으로 읽히지만 None 은 "재지 않았다"로 읽힌다 — 이 구분이 이 파일의 존재 이유다.

## 무엇이 이 목록에 오르는가

`data/config/page_hubs` 에 등록됐고 **Gold 가 실제로 선** 거점만 오른다(아래 `_is_measured`).
등록만 하고 수집 전인 거점은 오르지 않는다 — 목록에 뜨는데 지도가 비는 상태를 막는다.

## 어느 도시를 서빙하는가 — `SERVED_CITIES`

Gold 가 섰다고 자동으로 화면에 오르지는 않는다. 어느 도시를 **지금** 서빙할지는 제품
판단이고, 그 판단을 `SERVED_CITIES` 한 곳에 둔다(아래). 2026-09-03 현재 서울만이다.

## 서울 54거점은 건드리지 않는다

`seoul_pages.DISTRICTS` 는 그대로다. 이 모듈은 **더할 뿐** 기존 항목을 바꾸지 않는다.
`tests/test_districts.py::test_list_districts` 가 세는 54 는 시드 수이고, 여기서 더해지는
거점은 `tests/test_city_registry.py` 가 따로 센다.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path

from app.data import cities

logger = logging.getLogger(__name__)

# apps/backend/app/data/measured_pages.py → 저장소 루트
_REPO = Path(__file__).resolve().parents[4]
_GOLD = _REPO / "data" / "gold"
_PAGE_HUBS = _REPO / "data" / "config" / "page_hubs.py"


# 지금 화면에 올릴 도시. **수집·등재와 별개인 제품 판단**이라 코드 한 곳에 둔다.
#
# 2026-09-03: 경기(고양·파주) 작업을 중단하기로 해서 서울만 남겼다. 고양·파주 7거점
# (hwajeong·ilsan·westerndom·geumchon·unjeong·tanhyeon·yadang)은 Gold 도 앵커도 서 있고
# `page_hubs.GYEONGGI_HUBS` 에 그대로 등재돼 있다 — **지우지 않았다.** 재개할 때
# 여기에 도시 id 를 되넣으면 그날로 다시 뜬다.
#
# ⚠ 되넣기 전에 볼 것: 경기 거점의 예외 문구는 `page_hubs.PageHub.caveat` 에 있고,
#   그 파일이 배포 이미지에 실리는지는 `tests/test_deploy_image_ships_runtime_data.py`
#   가 지킨다(2026-09-02 에 안 실려서 프로덕션이 54거점만 냈다).
#
# 2026-09-05: **수집도 함께 멈추기로 했다.** 09-03 에 서빙만 끄고 수집 쪽은 그대로
# 두었더니, `chain_status` 와 `quota_preflight` 가 그 결정을 모른 채 경기 17거점의
# 대장·공실유닛을 계속 "다음 한 수"로 냈다. 그 줄을 집으면 화면에 닿지 않을 데이터에
# 하루치 쿼터가 사라진다(쿼터는 회수되지 않는다). 그래서 두 스크립트가 이 상수를 읽어
# 대상에서 뺀다 — **재개는 여기에 도시 id 를 되넣는 것 하나로 끝난다.**
#   · scripts/chain_status.py `_served_cities()` — 보류 거점은 다음 한 수를 안 낸다
#     (`--include-paused` 로 꺼낸다). 단계·근거는 그대로 보인다.
#   · scripts/quota_preflight.py `_paused()` — 실행줄과 콜 배정에서 뺀다
#   두 곳 다 **이 상수를 못 읽으면 아무것도 빼지 않는다** — 못 읽은 것을 '보류'로
#   단정하면 서울 잔여까지 조용히 사라지기 때문이다.
SERVED_CITIES: frozenset[str] = frozenset({"seoul"})


def _load_hubs() -> dict:
    """`data/config/page_hubs.py` 를 경로로 로드.

    `data/` 는 백엔드 패키지 밖이라 import 경로가 없다(tests/test_city_registry.py 와 같은 방식).
    """
    if not _PAGE_HUBS.exists():
        # 배포 이미지에 data/config 가 없을 때. **조용히 눕지 않는다** — 2026-09-02 에
        # 정확히 이 자리가 프로덕션에서 빈 dict 를 돌려주어 서울 2차 12거점 + 경기
        # 7거점이 화면에서 통째로 사라졌고, 폴백이 말이 없어서 아무도 몰랐다.
        # Dockerfile 이 `COPY data/config/` 를 하는지 볼 것(빌드 가드도 같이 있다).
        logger.warning(
            "page_hubs 를 못 읽는다(%s) — 시드 밖 거점이 목록에서 통째로 빠진다. "
            "배포 이미지에 data/config 가 실렸는지 확인할 것", _PAGE_HUBS)
        return {}
    key = "_measured_pages_hubs"
    if key in sys.modules:
        return getattr(sys.modules[key], "ALL_HUBS", {})
    spec = importlib.util.spec_from_file_location(key, _PAGE_HUBS)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, "ALL_HUBS", {})


def _coverage(slug: str) -> dict | None:
    p = _GOLD / slug / "coverage.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _is_measured(slug: str) -> bool:
    """Gold 가 실제로 선 거점인가 — 건물 마스터가 있어야 지도가 뜬다."""
    return (_GOLD / slug / "page_building_master.geojson").exists()


def _grid(hub) -> dict:
    """중심좌표·반경에서 격자를 만든다. 시드 거점은 손으로 적은 `grid` 를 쓰지만
    실측 거점은 적을 사람이 없으므로 **거점 정의에서 유도**한다.

    시드 격자(예: garosugil dlat 0.0009 ≈ 100m)와 같은 해상도를 쓴다 — 히트맵 셀 크기가
    거점마다 다르면 화면에서 비교가 안 된다.
    """
    dlat, dlng = 0.0009, 0.00113          # ≈100m (시드 거점과 동일 해상도)
    # radius_m 를 위경도로 환산 — 위도 1도 ≈ 111km, 경도는 cos(위도) 보정.
    import math
    dy = hub.radius_m / 111_000
    dx = hub.radius_m / (111_000 * max(math.cos(math.radians(hub.cy)), 0.1))
    return {
        "bb": {"s": round(hub.cy - dy, 6), "n": round(hub.cy + dy, 6),
               "w": round(hub.cx - dx, 6), "e": round(hub.cx + dx, 6)},
        "dlat": dlat, "dlng": dlng,
        "core": [round(hub.cy, 6), round(hub.cx, 6)],
    }


def _entry(hub, cov: dict | None) -> dict:
    city = cities.by_id(getattr(hub, "city", "seoul"))
    tier = (cov or {}).get("tier") or "미확인"
    shown = (cov or {}).get("shown")
    note = f"{city.short} · 건물 {shown}동 · {tier}" if shown else f"{city.short} · {tier}"
    return {
        "id": hub.slug,
        "name": hub.name,
        # 자치구·일반구는 시드에만 있는 값이라 실측 거점에는 없다. 도시명으로 대신하고
        # `city` 필드가 진짜 축을 갖는다(`cities.of_gu` 는 이 값을 못 찾아 서울로 눕히므로
        # `_summary` 가 `city` 를 직접 읽도록 되어 있어야 한다).
        "gu": city.short,
        "city": city.id,
        "type": "",                       # 상권 유형은 사람이 붙이는 라벨 — 비운다
        "center": [hub.cy, hub.cx],
        "zoom": 16,
        "sub": note,
        "poi": [],
        # ── 아래 넷이 이 파일의 요점이다: 비어 있는 것이 정상이고, 그 사실이 화면에 실린다
        "zones": [],                      # 감성구역 — 실측 소스 없음
        "units": [],                      # 공실유닛 — Gold vacant_units 가 서면 그쪽에서 온다
        "events": [],                     # 행사 — 시 단위 소스 미확인
        "insta": [],
        "grid": _grid(hub),
        "measured_only": True,            # 시드 거점과 구분하는 플래그(스키마·화면이 읽는다)
        # 예외 표시 — 이 거점의 수치를 다른 거점과 나란히 놓으면 안 되는 이유.
        # 비어 있으면 예외가 아니다(대다수 거점). `page_hubs.PageHub.caveat` 가 단일 출처다.
        "caveat": getattr(hub, "caveat", "") or "",
    }


def build() -> list[dict]:
    """Gold 가 선 비(非)시드 거점의 최소 필드 항목."""
    from app.data.seoul_pages import DISTRICTS_BY_ID

    out: list[dict] = []
    for slug, hub in sorted(_load_hubs().items()):
        if slug in DISTRICTS_BY_ID:       # 시드 거점이 이긴다 — 서울 54는 그대로
            continue
        if not _is_measured(slug):        # 수집 전 거점은 목록에 올리지 않는다
            continue
        # 서빙 대상 도시가 아니면 올리지 않는다. 산출물이 없어서가 아니라 **안 올리기로
        # 정해서** 빠지는 것이라, 두 이유를 위 조건과 갈라 둔다(위 SERVED_CITIES 주석).
        if getattr(hub, "city", "seoul") not in SERVED_CITIES:
            continue
        out.append(_entry(hub, _coverage(slug)))
    return out


MEASURED: list[dict] = build()
MEASURED_BY_ID: dict[str, dict] = {d["id"]: d for d in MEASURED}
