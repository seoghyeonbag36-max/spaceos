"""[Program] 서울시 문화행사 수집기 — 상권 행사 섹션의 실데이터 원천.

거점 행사(`app/data/seoul_pages.py` 의 `events`)는 좌표·일정이 붙은 실물처럼 보이지만
전부 손으로 적은 시드였다. 서울열린데이터광장 `culturalEventInfo` 는 실제 행사에
**좌표(LAT/LOT)·기간·장소·주최·요금**을 붙여 주므로 그대로 실측 대체가 된다.

⚠️ 대체되지 않는 것: 시드가 함께 적고 있던 **효과 지표**("유입 +52%", "전환 14%")와
이해관계자 역할·HA 메모는 이 API 에 없다. 지어낸 수치이므로 실데이터로 넘어갈 때
**들고 가지 않는다** — 근거 없는 효과 주장을 지도에 찍지 않기 위해서다.

전량(약 2만 행)을 한 번 받아 거점 반경으로 잘라 Bronze 에 저장한다. 서비스가 구 단위
필터를 지원하지 않아 전량 페이징이 유일한 경로다.

실행: python -m data.collectors.seoul_events
"""
from __future__ import annotations

import math
import os
from datetime import date, datetime

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import load_env, save_json
from data.config.page_hubs import ACTIVE_HUBS

SERVICE = "culturalEventInfo"
SLUG = "platform13"          # 거점 공통 Bronze 폴더(다거점 산출물 관례)
_PAGE = 1000
_MAX_ROWS = 60_000

# 거점 중심에서 이 반경 안의 행사만 그 거점 것으로 본다. 수집 반경(400~800m)보다 넉넉한
# 이유: 행사는 상권 바로 옆 공원·문화시설에서 열려도 그 상권의 유입 요인이다.
RADIUS_M = 1500

_M_PER_DEG_LAT = 111_000.0
_M_PER_DEG_LON = 88_300.0     # 서울 위도(약 37.5°)에서의 경도 1도 거리


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat1 - lat2) * _M_PER_DEG_LAT
    dx = (lon1 - lon2) * _M_PER_DEG_LON
    return math.sqrt(dx * dx + dy * dy)


def _fetch_all(key: str) -> list[dict]:
    """문화행사 전량 페이징. 오류 응답(RESULT.CODE)은 예외로 승격."""
    rows: list[dict] = []
    start = 1
    while start <= _MAX_ROWS:
        url = f"http://openapi.seoul.go.kr:8088/{key}/json/{SERVICE}/{start}/{start + _PAGE - 1}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if SERVICE not in body:
            msg = body.get("RESULT", {}).get("MESSAGE", str(body)[:200])
            raise RuntimeError(f"{SERVICE}: {msg}")
        payload = body[SERVICE]
        page = payload.get("row", [])
        rows.extend(page)
        total = int(payload.get("list_total_count", 0))
        start += _PAGE
        if not page or start > total:
            break
    return rows


def _coords(row: dict) -> tuple[float, float] | None:
    """(위도, 경도). 이 API 는 LOT 이 경도, LAT 이 위도다(이름이 헷갈리게 붙어 있다)."""
    try:
        lat, lon = float(row.get("LAT") or 0), float(row.get("LOT") or 0)
    except (TypeError, ValueError):
        return None
    # 서울 바깥 좌표·0,0 은 버린다(빈 값이 0 으로 들어오는 행이 있다)
    if not (37.0 < lat < 37.9 and 126.6 < lon < 127.3):
        return None
    return lat, lon


def _end_date(row: dict) -> date | None:
    raw = str(row.get("END_DATE") or "")[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def collect(upcoming_only: bool = True) -> dict[str, int]:
    """전량 수집 → 거점 반경으로 분배 → Bronze 저장. 반환: 거점 → 행사 수."""
    load_env()
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key or requests is None:
        print("[seoul_events] SEOUL_OPENAPI_KEY 미설정(또는 requests 없음) — 건너뜀")
        return {}

    rows = _fetch_all(key)
    today = date.today()
    print(f"[seoul_events] 전체 {len(rows)}행 수집")

    kept: list[dict] = []
    for row in rows:
        c = _coords(row)
        if c is None:
            continue
        if upcoming_only:
            end = _end_date(row)
            if end is None or end < today:
                continue          # 이미 끝난 행사는 상권 유입 요인이 아니다
        lat, lon = c
        near = [(h.slug, _dist_m(lat, lon, h.cy, h.cx)) for h in ACTIVE_HUBS.values()]
        for slug, d in near:
            if d <= RADIUS_M:
                kept.append({**row, "district_id": slug, "distance_m": round(d)})

    save_json(kept, SLUG, "seoul_events.json")
    counts: dict[str, int] = {}
    for r in kept:
        counts[r["district_id"]] = counts.get(r["district_id"], 0) + 1
    return counts


def main() -> None:
    counts = collect()
    if not counts:
        return
    print(f"[seoul_events] 거점 {len(counts)}곳에 배정")
    for slug, n in sorted(counts.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {slug:18s} {n:4d}건")


if __name__ == "__main__":
    main()
