"""네이버 클라우드 플랫폼 Maps REST(Geocoding) 래퍼.

크롤링·공공데이터로 들어온 상가/건물 주소를 좌표로 정규화해 Silver 레이어에 적재한다.
- 인증: Client ID(Key ID) + Client Secret (둘 다 필요).
- 콘솔 > Maps > Application 에서 'Geocoding' API 체크되어 있어야 한다(미체크 시 401/403).
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger("spaceos.naver_geo")

# NCP 신 Maps API 엔드포인트(2025~). 헤더는 소문자 규약을 사용한다.
GEOCODE_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"
_RETRY = 2  # 일시 오류 시 재시도 횟수


def _headers() -> dict[str, str]:
    """런타임에 환경변수를 읽는다(.env 로드 타이밍 의존성 제거)."""
    key_id = os.getenv("NAVER_MAPS_KEY_ID", "")
    secret = os.getenv("NAVER_MAPS_CLIENT_SECRET", "")
    if not key_id or not secret:
        # TODO: app/core/config.py 의 Settings 로 통합 후 기동 시점 검증으로 승격
        logger.warning("NAVER_MAPS_KEY_ID / CLIENT_SECRET 미설정 — geocode 호출이 실패합니다.")
    return {
        "x-ncp-apigw-api-key-id": key_id,
        "x-ncp-apigw-api-key": secret,
        "Accept": "application/json",
    }


async def geocode(address: str) -> dict | None:
    """주소 문자열 → {lat, lng, road, jibun, confidence}.

    실패(미발견/네트워크 오류) 시 None 을 반환하고, 실패 주소는 호출측에서
    Silver 정제 실패 로그(data/silver/_geocode_failed.csv 등)에 적재한다.
    """
    if not address or not address.strip():
        return None

    params = {"query": address.strip()}
    last_exc: Exception | None = None

    for attempt in range(_RETRY + 1):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(GEOCODE_URL, params=params, headers=_headers())
                r.raise_for_status()
                items = r.json().get("addresses", [])
                if not items:
                    logger.info("geocode 결과 없음: %s", address)
                    return None
                a = items[0]
                return {
                    "lat": float(a["y"]),
                    "lng": float(a["x"]),
                    "road": a.get("roadAddress"),
                    "jibun": a.get("jibunAddress"),
                    # 동일 질의 다건 매칭 시 신뢰도 판단용(상위 1건 채택)
                    "confidence": "high" if len(items) == 1 else "ambiguous",
                }
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            last_exc = exc
            if attempt < _RETRY:
                await asyncio.sleep(0.4 * (attempt + 1))  # 지수 백오프
                continue
            logger.warning("geocode 실패(%s): %s", address, exc)
            return None

    logger.warning("geocode 최종 실패(%s): %s", address, last_exc)
    return None


async def geocode_batch(addresses: list[str], concurrency: int = 5) -> list[dict | None]:
    """주소 리스트 일괄 정규화. NCP 호출량 제한 보호용으로 동시성을 제한한다."""
    sem = asyncio.Semaphore(concurrency)

    async def _one(addr: str) -> dict | None:
        async with sem:
            return await geocode(addr)

    return await asyncio.gather(*[_one(a) for a in addresses])
