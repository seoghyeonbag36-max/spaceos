"""지도/IT 유입(MAP) 수집기 — 네이버 데이터랩 검색어트렌드.

'네이버 지도 같은 IT 서비스 유입'의 프록시로 지역·상권 키워드 검색 관심도를 쓴다.

데이터랩 핵심 특성: 한 요청 내 모든 그룹·시점을 통틀어 최댓값을 100으로 정규화한
'상대 비율'을 돌려준다(절대 검색량 아님). 따라서 구를 따로따로 부르면 구 간 비교가
불가능하다. → 모든 배치에 **공통 기준어("맛집")**를 끼워 넣어 척도를 고정하고,
한 번에 4개 구 + 기준어(=5그룹)씩 묶어 호출한다(25회 → 7회, 속도·정확도 동시 개선).

출처: https://developers.naver.com/docs/serviceapi/datalab/search/search.md
환경변수: NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (없거나 실패 시 프록시 폴백).
"""
from __future__ import annotations

import os
import time

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.config.seoul_districts import DISTRICTS

_DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
_ANCHOR_NAME = "__anchor__"
_ANCHOR_KEYWORDS = ["맛집"]  # 전 지역 공통·고검색 기준어 → 배치 간 척도 고정
_BATCH = 4                    # 구 4개 + 기준어 1개 = 5그룹(데이터랩 상한)
_TIMEOUT = 30
_RETRY = 2


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    if not raw:
        return {}
    lo, hi = min(raw.values()), max(raw.values())
    span = (hi - lo) or 1.0
    return {gu: round((v - lo) / span * 100, 1) for gu, v in raw.items()}


def _post_with_retry(headers: dict, body: dict) -> dict | None:
    """데이터랩 POST + 재시도. 비200/타임아웃 시 원인 출력 후 None."""
    for attempt in range(1, _RETRY + 1):
        try:
            resp = requests.post(_DATALAB_URL, headers=headers, json=body, timeout=_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            print(f"[naver_datalab] HTTP {resp.status_code} | {resp.text[:200]}")
            return None  # 인증·권한 오류는 재시도 무의미
        except Exception as exc:
            print(f"[naver_datalab] 시도 {attempt}/{_RETRY} 실패: {exc}")
            time.sleep(1.0)
    return None


def fetch_map_interest(start: str = "2025-01-01", end: str = "2025-12-31") -> dict[str, float]:
    """구별 검색 관심도를 0~100 정규화 반환(공통 기준어로 척도 고정)."""
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not cid or not secret or requests is None:
        return _proxy_fallback()

    headers = {
        "X-Naver-Client-Id": cid,
        "X-Naver-Client-Secret": secret,
        "Content-Type": "application/json",
    }
    items = list(DISTRICTS.items())
    raw: dict[str, float] = {}

    for i in range(0, len(items), _BATCH):
        chunk = items[i:i + _BATCH]
        groups = [{"groupName": gu, "keywords": meta["keywords"][:5]} for gu, meta in chunk]
        groups.append({"groupName": _ANCHOR_NAME, "keywords": _ANCHOR_KEYWORDS})
        body = {"startDate": start, "endDate": end, "timeUnit": "month", "keywordGroups": groups}

        data = _post_with_retry(headers, body)
        if data is None:
            print("[naver_datalab] 실측 실패 -> 프록시 폴백")
            return _proxy_fallback()

        for r in data.get("results", []):
            name = r.get("title") or r.get("groupName")
            if name == _ANCHOR_NAME:
                continue  # 기준어는 척도 고정용, 점수에서 제외
            ratios = [p["ratio"] for p in r.get("data", [])]
            raw[name] = sum(ratios) / len(ratios) if ratios else 0.0
        time.sleep(0.3)  # 호출 간 간격(rate-limit 예방)

    return _normalize(raw) if any(raw.values()) else _proxy_fallback()


def _proxy_fallback() -> dict[str, float]:
    return {gu: float(m["base"]["MAP"]) for gu, m in DISTRICTS.items()}


if __name__ == "__main__":
    data = fetch_map_interest()
    for gu, v in sorted(data.items(), key=lambda x: -x[1])[:5]:
        print(f"{gu:6} MAP={v}")
