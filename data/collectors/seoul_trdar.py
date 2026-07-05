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


if __name__ == "__main__":
    load_env()
    collect()
