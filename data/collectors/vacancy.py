"""공실(VAC) 수집기 — 소상공인 상가(상권)정보 API + 한국부동산원 공실률.

공실은 SpaceOS가 푸는 핵심 문제다. 공식 '상업용 부동산 공실률'은 한국부동산원·
쿠시먼앤드웨이크필드 보고서(비 오픈API)가 권위 데이터원이라, config의 VAC base
앵커가 이를 반영한다. 본 수집기는 추가로 소상공인 상가 API에서 구별 활성 점포수를
받아 '점포 밀도/증감' 기반 공실 프록시를 산출(YoY 비교 시 폐업 신호)할 수 있다.

출처:
- 소상공인시장진흥공단 상가(상권)정보 API (공공데이터포털 15012005, 기관 B553077)
  https://www.data.go.kr/data/15012005/openapi.do
  엔드포인트: http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInArea (외 storeListInDong/Radius)
  국세청·카드사 기반. 상호·주소·업종·좌표 제공.
- 한국부동산원 상업용부동산 임대동향(공실률) / 쿠시먼앤드웨이크필드 가두상권 공실률 → base 앵커

환경변수:
- DATA_GO_KR_SERVICE_KEY: 공공데이터포털 인증키(디코딩 키).
- VACANCY_MODE=density 로 설정 시 점포밀도 프록시 사용, 기본은 base 앵커(공식 공실률).
"""
from __future__ import annotations

import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.config.seoul_districts import DISTRICTS

_SDSC_BASE = "http://apis.data.go.kr/B553077/api/open/sdsc2"


def _normalize_inverse(raw: dict[str, float]) -> dict[str, float]:
    """점포밀도 → 공실 프록시(0~100). 밀도 높을수록 공실 낮음 → 역방향 정규화."""
    if not raw:
        return {}
    lo, hi = min(raw.values()), max(raw.values())
    span = (hi - lo) or 1.0
    return {gu: round((1 - (v - lo) / span) * 100, 1) for gu, v in raw.items()}


def _store_count(sigungu_code: str, key: str) -> int:
    """시군구 단위 활성 점포 총수(totalCount). 실패 시 0."""
    try:
        r = requests.get(
            f"{_SDSC_BASE}/storeListInArea",
            params={"serviceKey": key, "divId": "signguCd", "key": sigungu_code,
                    "type": "json", "numOfRows": 1, "pageNo": 1},
            timeout=25,
        )
        r.raise_for_status()
        body = r.json().get("body", {})
        return int(body.get("totalCount", 0))
    except Exception:
        return 0


def fetch_vacancy() -> dict[str, float]:
    """구별 공실 지표(0~100, 높을수록 공실 多) 반환.

    기본(권장): config VAC base 앵커(한국부동산원·쿠시먼앤드웨이크필드 공식 공실률).
    VACANCY_MODE=density + DATA_GO_KR_SERVICE_KEY: 소상공인 점포밀도 역수 프록시.
    """
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    mode = os.getenv("VACANCY_MODE", "base")
    if mode != "density" or not key or requests is None:
        return _proxy_fallback()

    raw: dict[str, float] = {}
    try:
        for gu, meta in DISTRICTS.items():
            # 자치구 코드(5자리)로 활성 점포수 집계. divId/key 명세는 발급 후 확정(TODO).
            raw[gu] = float(_store_count(meta["code"][:5], key))
        # 점포밀도 ↔ 공실은 음의 상관 → 역방향 정규화.
        # 정밀화: 두 시점(YoY) 점포수 차로 순폐업 산출 권장(국세청 개·폐업 데이터).
        return _normalize_inverse(raw) if any(raw.values()) else _proxy_fallback()
    except Exception as exc:
        print(f"[vacancy] 실측 실패 → 프록시 폴백: {exc}")
        return _proxy_fallback()


def _proxy_fallback() -> dict[str, float]:
    """공식 공실률 기반 base 앵커(권위 데이터원)."""
    return {gu: float(m["base"]["VAC"]) for gu, m in DISTRICTS.items()}


if __name__ == "__main__":
    data = fetch_vacancy()
    for gu, v in sorted(data.items(), key=lambda x: -x[1])[:5]:
        print(f"{gu:6} VAC={v}")
