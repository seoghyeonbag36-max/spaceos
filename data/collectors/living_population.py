"""유동인구(FOOT) 수집기 — 서울 생활인구 / 우리마을가게 상권분석.

출처:
- 서울 열린데이터광장 '서울 생활인구'(SKT·KT 기지국 전수화, 50m 격자/행정동, 5분~시간 단위)
  https://data.seoul.go.kr  (파일 다운로드 + REST API)
- 서울시 상권분석 서비스(골목상권, 서울신용보증재단): 추정 유동인구(KT 생활인구 기반 10m 도로 단위)
  https://golmok.seoul.go.kr

반환: 구 이름 → 0~100 정규화 유동인구 지표(25구 상대). config.SCORE_BANDS["FOOT"]에 투입.

환경변수:
- SEOUL_OPENAPI_KEY: 서울 열린데이터광장 인증키. 없으면 프록시(base) 폴백.
- SEOUL_LIVING_POP_SERVICE / _SGG_FIELD / _VALUE_FIELD: 구독 데이터셋별 서비스명·필드명.
"""
from __future__ import annotations

import os

try:  # 선택 의존성 — 폴백 모드에선 불필요
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.config.seoul_districts import DISTRICTS

# 서울 생활인구 OpenAPI 서비스명/필드는 '구독한 데이터셋'마다 다르므로 env로 주입.
_SEOUL_LIVING_POP_DATASET = os.getenv("SEOUL_LIVING_POP_SERVICE", "SPOP_LOCAL_RESD_DONG")
_F_SIGUNGU = os.getenv("SEOUL_LIVING_POP_SGG_FIELD", "SGG_CD")
_F_POP = os.getenv("SEOUL_LIVING_POP_VALUE_FIELD", "TOT_LVPOP_CO")


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    """구별 원시 인구수를 25구 상대 0~100으로 정규화."""
    if not raw:
        return {}
    lo, hi = min(raw.values()), max(raw.values())
    span = (hi - lo) or 1.0
    return {gu: round((v - lo) / span * 100, 1) for gu, v in raw.items()}


def fetch_living_population(year_month: str | None = None) -> dict[str, float]:
    """서울 생활인구 API에서 구별 평균 체류인구를 수집해 0~100 정규화 반환."""
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key or requests is None:
        return _proxy_fallback()

    raw: dict[str, float] = {}
    try:
        for gu, meta in DISTRICTS.items():
            url = (
                f"http://openapi.seoul.go.kr:8088/{key}/json/"
                f"{_SEOUL_LIVING_POP_DATASET}/1/1000/{year_month or ''}"
            )
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            rows = resp.json().get(_SEOUL_LIVING_POP_DATASET, {}).get("row", [])
            total = sum(
                float(r.get(_F_POP, 0))
                for r in rows
                if str(r.get(_F_SIGUNGU, "")).startswith(meta["code"][:5])
            )
            raw[gu] = total
        return _normalize(raw) if any(raw.values()) else _proxy_fallback()
    except Exception as exc:  # 네트워크/스키마 변동 시 폴백
        print(f"[living_population] 실측 실패 -> 프록시 폴백: {exc}")
        return _proxy_fallback()


def _proxy_fallback() -> dict[str, float]:
    """API 키 미설정 시: config의 FOOT base 앵커를 그대로 사용."""
    return {gu: float(m["base"]["FOOT"]) for gu, m in DISTRICTS.items()}


if __name__ == "__main__":
    data = fetch_living_population()
    for gu, v in sorted(data.items(), key=lambda x: -x[1])[:5]:
        print(f"{gu:6} FOOT={v}")
