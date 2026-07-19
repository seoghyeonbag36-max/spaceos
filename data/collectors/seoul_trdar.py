"""[B단계·Platform] 서울시 상권분석서비스 수집기 — 분기 시계열 (docs §8-A).

기존 `SEOUL_OPENAPI_KEY` 공용(생활인구와 동일 키·동일 URL 형식). 서비스별로 전량
페이징한 뒤 거점 상권(TRDAR_CD_NM 키워드 매칭) 행만 Bronze 에 저장한다 —
서울 전체 덤프는 수십만 행이라 거점 행만 남기되, 행 자체는 무가공 원본.

용도: LSTM 학습 피처(추정매출·점포·개폐업률·길단위인구·소득소비) + 상권변화지표.
⚠️ 서비스명·필드명은 데이터셋마다 편차 — 상세페이지 [미리보기]에서 최종 확인(TODO).

실행: python -m data.collectors.seoul_trdar
"""
from __future__ import annotations

import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import load_env, save_json
from data.config.garosugil import SLUG, TRDAR_NAME_KEYWORDS
from data.config.platform_districts import (
    ALL_TRDAR_CODES,
    QUARTERS,
    SLUG as SLUG13,
    TRDAR_TO_DISTRICT,
)

# 파일명 접미사 → 서울 열린데이터광장 서비스명 (※발급 후 [미리보기]로 재확인)
SERVICES: dict[str, str] = {
    "relm": "TbgisTrdarRelm",          # 상권영역 (폴리곤·상권코드 마스터)
    "selng": "VwsmTrdarSelngQq",       # 추정매출
    "stor": "VwsmTrdarStorQq",         # 점포수·개업률·폐업률
    "flpop": "VwsmTrdarFlpopQq",       # 길단위(유동)인구
    "income": "VwsmTrdarIncomeQq",     # 소득소비
    "ix": "VwsmTrdarIxQq",             # 상권변화지표
}

_PAGE = 1000          # 요청당 최대 행
_MAX_ROWS = 300_000   # 폭주 방지 상한


def _fetch_all(key: str, service: str) -> list[dict]:
    """서비스 전량 페이징 수집. 오류 응답(RESULT.CODE)은 예외로 승격."""
    rows: list[dict] = []
    start = 1
    while start <= _MAX_ROWS:
        url = f"http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{start + _PAGE - 1}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if service not in body:  # 인증오류·서비스명 오타 등
            msg = body.get("RESULT", {}).get("MESSAGE", str(body)[:200])
            raise RuntimeError(f"{service}: {msg}")
        payload = body[service]
        page = payload.get("row", [])
        rows.extend(page)
        total = int(payload.get("list_total_count", 0))
        start += _PAGE
        if not page or start > total:
            break
    return rows


def _filter_garosu(rows: list[dict]) -> list[dict]:
    return [
        r for r in rows
        if any(k in str(r.get("TRDAR_CD_NM", "")) for k in TRDAR_NAME_KEYWORDS)
    ]


def collect() -> dict[str, int]:
    """서비스별 수집 → 거점 필터 → Bronze 저장. 반환: 파일명 접미사 → 저장 행 수."""
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key or requests is None:
        print("[seoul_trdar] SEOUL_OPENAPI_KEY 미설정(또는 requests 없음) — 건너뜀")
        return {}

    counts: dict[str, int] = {}
    for suffix, service in SERVICES.items():
        try:
            rows = _fetch_all(key, service)
            hit = _filter_garosu(rows)
            save_json(hit, SLUG, f"seoul_trdar_{suffix}.json")
            print(f"  {service}: 전체 {len(rows)}행 중 거점 {len(hit)}행")
            counts[suffix] = len(hit)
        except Exception as exc:  # 서비스 단위로만 실패시키고 계속 진행
            print(f"  {service}: 실패 — {exc}")
            counts[suffix] = -1
    return counts


def _fetch_page(key: str, service: str, start: int, end: int, extra: str = "") -> tuple[list[dict], int]:
    """단일 페이지 요청. (rows, list_total_count) 반환. 오류 응답은 예외."""
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}{extra}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if service not in body:
        msg = body.get("RESULT", {}).get("MESSAGE", str(body)[:200])
        raise RuntimeError(f"{service}: {msg}")
    payload = body[service]
    return payload.get("row", []), int(payload.get("list_total_count", 0))


def collect_platform13() -> dict[str, int]:
    """[Platform·LSTM] 13거점(platform_districts.DISTRICT_TRDAR) 분기 시계열 수집.

    전략 (2026-07-19 프로브 확정 — data/probe_trdar_api.py):
      relm  전량 1,650행(2페이지) → 코드 필터
      stor  분기+상권코드 경로 필터 지원 → (코드×분기) 직접 쿼리
      selng 코드 필터 미지원(총량 46만행) → 분기별 전량(~22페이지) 후 로컬 필터
    Bronze: data/bronze/platform13/{날짜}/seoul_trdar_{relm,stor,selng}.json
    각 행에 district_id(거점 id)를 부가한다 — 원본 필드는 무가공 유지.
    """
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key or requests is None:
        print("[seoul_trdar] SEOUL_OPENAPI_KEY 미설정(또는 requests 없음) — 건너뜀")
        return {}
    counts: dict[str, int] = {}

    def _tag(rows: list[dict]) -> list[dict]:
        return [{**r, "district_id": TRDAR_TO_DISTRICT[str(r.get("TRDAR_CD", ""))]}
                for r in rows if str(r.get("TRDAR_CD", "")) in TRDAR_TO_DISTRICT]

    # 1) relm — 상권 마스터 (좌표·면적 포함)
    rows: list[dict] = []
    start = 1
    while True:
        page, total = _fetch_page(key, "TbgisTrdarRelm", start, start + _PAGE - 1)
        rows.extend(page)
        start += _PAGE
        if not page or start > total:
            break
    hit = _tag(rows)
    save_json(hit, SLUG13, "seoul_trdar_relm.json")
    counts["relm"] = len(hit)
    missing = set(ALL_TRDAR_CODES) - {str(r["TRDAR_CD"]) for r in hit}
    if missing:
        print(f"  [경고] relm 에 없는 매핑 코드: {sorted(missing)}")

    # 2) stor — (코드×분기) 직접 쿼리
    stor_rows: list[dict] = []
    for q in QUARTERS:
        q_hits = 0
        for code in ALL_TRDAR_CODES:
            try:
                page, _ = _fetch_page(key, "VwsmTrdarStorQq", 1, _PAGE, f"/{q}/{code}")
            except Exception as exc:
                print(f"  stor {q}/{code}: 실패 — {exc}")
                continue
            # 필터 미적용 응답(전체 반환) 방지 — 코드 일치 행만 채택
            page = [r for r in page if str(r.get("TRDAR_CD")) == code and str(r.get("STDR_YYQU_CD")) == q]
            q_hits += len(page)
            stor_rows.extend(page)
        print(f"  stor {q}: {q_hits}행")
    stor_rows = _tag(stor_rows)
    save_json(stor_rows, SLUG13, "seoul_trdar_stor.json")
    counts["stor"] = len(stor_rows)

    # 3) selng — 분기 전량 페이징 후 로컬 필터
    selng_rows: list[dict] = []
    for q in QUARTERS:
        start, total, q_rows = 1, 0, []
        while start <= _MAX_ROWS:
            try:
                page, total = _fetch_page(key, "VwsmTrdarSelngQq", start, start + _PAGE - 1, f"/{q}")
            except Exception as exc:
                print(f"  selng {q}: 실패 — {exc}")
                break
            q_rows.extend(r for r in page if str(r.get("TRDAR_CD", "")) in TRDAR_TO_DISTRICT)
            start += _PAGE
            if not page or start > total:
                break
        print(f"  selng {q}: 전체 {total}행 중 거점 {len(q_rows)}행")
        selng_rows.extend(q_rows)
    selng_rows = _tag(selng_rows)
    save_json(selng_rows, SLUG13, "seoul_trdar_selng.json")
    counts["selng"] = len(selng_rows)
    return counts


def collect_platform13_flpop() -> int:
    """[Platform·LSTM] 길단위(유동)인구 분기 시계열 — selng 와 같은 분기 전량 페이징.

    VwsmTrdarFlpopQq 는 상권당 1행/분기(≈1,650행)라 분기별 2페이지면 전량이다.
    Bronze: data/bronze/platform13/{날짜}/seoul_trdar_flpop.json (district_id 부가).
    """
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key or requests is None:
        print("[seoul_trdar] SEOUL_OPENAPI_KEY 미설정(또는 requests 없음) — 건너뜀")
        return 0

    def _tag(rows: list[dict]) -> list[dict]:
        return [{**r, "district_id": TRDAR_TO_DISTRICT[str(r.get("TRDAR_CD", ""))]}
                for r in rows if str(r.get("TRDAR_CD", "")) in TRDAR_TO_DISTRICT]

    flpop_rows: list[dict] = []
    for q in QUARTERS:
        start, total, q_rows = 1, 0, []
        while start <= _MAX_ROWS:
            try:
                page, total = _fetch_page(key, "VwsmTrdarFlpopQq", start, start + _PAGE - 1, f"/{q}")
            except Exception as exc:
                print(f"  flpop {q}: 실패 — {exc}")
                break
            q_rows.extend(r for r in page if str(r.get("TRDAR_CD", "")) in TRDAR_TO_DISTRICT)
            start += _PAGE
            if not page or start > total:
                break
        print(f"  flpop {q}: 전체 {total}행 중 거점 {len(q_rows)}행")
        flpop_rows.extend(q_rows)
    flpop_rows = _tag(flpop_rows)
    save_json(flpop_rows, SLUG13, "seoul_trdar_flpop.json")
    return len(flpop_rows)


if __name__ == "__main__":
    import sys

    load_env()
    if "--platform13-flpop" in sys.argv:
        collect_platform13_flpop()
    elif "--platform13" in sys.argv:
        collect_platform13()
    else:
        collect()
