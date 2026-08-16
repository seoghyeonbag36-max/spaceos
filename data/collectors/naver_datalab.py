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
import re
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


# ─────────────────── 거점(54) 단위 검색 트렌드 ───────────────────
# 위 fetch_map_interest 는 **자치구 25개**의 관심도 한 값을 뽑는다. 아래는 다른 목적이다 —
# 거점 54개의 **월별 시계열**을 받아 Program 컨텍스트의 `trend:*` 행을 만든다.
#
# 왜 필요한가: ha_guard._check_trend 는 컨텍스트에 실린 방향 라벨(상승/하락/보합)로
# "트렌드가 하락인데 유입이 늘고 있다"는 생성물을 잡는다. 그런데 라벨이 없으면 그냥
# 통과한다 — 지금까지 trend 행이 garosugil 한 곳에만 있어 **53거점에서 이 검사가 꺼져
# 있었다.** 생성량이 늘기 전에 켜는 것이 이 함수의 목적이다.
#
# ⚠ 데이터랩은 **전국** 검색이다. 거점명이 타 시도에도 있으면 방향이 오염된다. 이 저장소는
#   블로그 코퍼스에서 이미 같은 오염을 확인했다(cityhall `대전·부산·수원`, nonhyeon `인천`,
#   jangan·kyunghee `수원`). 아래 _HUB_KEYWORDS 로 그런 거점만 키워드를 좁힌다.
#   좁힐 수 없으면 검색량이 죽어 방향이 노이즈가 되므로, 억지로 붙이지 않고 그대로 둔 뒤
#   파이프라인이 저품질 시계열을 걸러낸다(build_program_trend._usable).

_TREND_MONTHS = 24
_HUB_BATCH = 4          # 거점 4 + 기준어 1 = 5그룹(데이터랩 상한)

# 이름 그대로 쓰면 타 시도가 섞이는 거점만 지정한다. 나머지는 거점명을 `·` 로 쪼개 쓴다.
_HUB_KEYWORDS: dict[str, list[str]] = {
    "cityhall": ["서울시청", "시청역"],       # 대전·부산·대구에도 시청역이 있다
    "nonhyeon": ["논현동", "논현역"],         # 인천 남동구 논현동
    "jangan": ["장안동", "장안평"],           # 대구·안동에도 장안동
    "kyunghee": ["회기동", "경희대"],         # 경희대 국제캠은 수원이다
    "nambu": ["남부터미널"],                  # 타 지역 '남부터미널' 이 있으나 서울이 압도적
}


def _hub_keywords(slug: str, name: str) -> list[str]:
    """거점 키워드 — 지정이 있으면 그것, 없으면 이름을 `·` 로 쪼갠다.

    '신사동 가로수길' 처럼 공백이 든 이름은 통째로도 검색되지만 검색량이 낮다.
    공백으로도 쪼개 개별 지명을 함께 넣는다(데이터랩은 그룹 내 키워드를 합산한다).
    """
    if slug in _HUB_KEYWORDS:
        return _HUB_KEYWORDS[slug]
    out: list[str] = []
    # 괄호는 구분자로 취급한다 — '을지로(힙지로)' 를 통째로 넘기면 데이터랩이 0건을
    # 돌려준다(2026-08-16 실측: euljiro 만 빈 시계열이었다).
    for part in re.split(r"[·()]", name):
        for tok in [part, *part.split()]:
            tok = tok.strip()
            if len(tok) >= 2 and tok not in out:
                out.append(tok)
    return out[:5]


def fetch_hub_trends(months: int = _TREND_MONTHS) -> dict[str, list[dict]]:
    """거점 slug → [{period, ratio}] 월별 시계열. 키 없음·실패 시 빈 dict."""
    import datetime

    from data.config.page_hubs import HUBS

    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not cid or not secret or requests is None:
        print("[datalab:hub] NAVER_CLIENT_ID/SECRET 없음 — 수집하지 않는다")
        return {}

    # **끝나지 않은 달을 요청하지 않는다.** endDate 를 이번 달 안에 두면 데이터랩이
    # 수집 시점까지의 부분합을 마지막 버킷으로 돌려주고, 달이 안 끝났다는 이유만으로
    # 급락한 것처럼 보인다(2026-08-16 실측: 마지막 값이 일관되게 직전의 ~50% — 16/31).
    # 그 절단값이 Program 트렌드 오독(2026-08-01)의 입력이었다.
    end = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
    start = (end - datetime.timedelta(days=int(months * 30.5))).replace(day=1)
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret,
               "Content-Type": "application/json"}

    items = sorted(HUBS.items())
    out: dict[str, list[dict]] = {}
    for i in range(0, len(items), _HUB_BATCH):
        chunk = items[i:i + _HUB_BATCH]
        groups = [{"groupName": slug, "keywords": _hub_keywords(slug, h.name)}
                  for slug, h in chunk]
        groups.append({"groupName": _ANCHOR_NAME, "keywords": _ANCHOR_KEYWORDS})
        data = _post_with_retry(headers, {
            "startDate": start.isoformat(), "endDate": end.isoformat(),
            "timeUnit": "month", "keywordGroups": groups})
        if data is None:
            print(f"[datalab:hub] 배치 {i // _HUB_BATCH + 1} 실패 — 건너뛴다")
            time.sleep(0.5)
            continue
        for r in data.get("results", []):
            name = r.get("title") or r.get("groupName")
            if name == _ANCHOR_NAME:
                continue
            out[name] = [{"period": p["period"], "ratio": p["ratio"]}
                         for p in r.get("data", [])]
        print(f"[datalab:hub] {min(i + _HUB_BATCH, len(items))}/{len(items)}거점")
        time.sleep(0.3)
    return out


def collect_hub_trends() -> None:
    """거점 트렌드를 Bronze 에 저장 (platform13/naver_datalab_hub_trend.json)."""
    from data.collectors.common import load_env, save_json
    from data.config.platform_districts import SLUG as SLUG13

    load_env()
    trends = fetch_hub_trends()
    if not trends:
        print("[datalab:hub] 수집 0건 — 저장하지 않는다")
        return
    save_json({"collected_at": time.strftime("%Y-%m-%d"), "trends": trends},
              SLUG13, "naver_datalab_hub_trend.json")
    print(f"[datalab:hub] {len(trends)}거점 저장")


if __name__ == "__main__":
    import sys

    if "--hubs" in sys.argv:
        collect_hub_trends()
    else:
        data = fetch_map_interest()
        for gu, v in sorted(data.items(), key=lambda x: -x[1])[:5]:
            print(f"{gu:6} MAP={v}")
