"""[Program] 상권 행사 서빙 — gold/platform_events.json 로드.

행사는 좌표·일정이 붙은 **실물**이라 지어내면 안 된다. 시드 행사는 좌표·일정까지
손으로 적은 값이었고, 근거 없는 효과 지표("유입 +52%")·이해관계자 역할·HA 메모까지
달고 있었다. 이제 서울열린데이터광장 문화행사에서 실제 행사만 싣는다.

**없으면 비운다.** 이 API 는 공공·문화시설 행사 중심이라 가두 상권 커버리지가 낮다
(가로수길 2건, 둘 다 800m 밖). 빈 거점을 시드로 채우면 지어낸 행사를 다시 지도에
찍는 셈이라, 빈 목록을 그대로 돌려주고 프론트가 빈 상태를 표시한다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_GOLD = Path(__file__).resolve().parents[4] / "data" / "gold"
_EVENTS_JSON = _GOLD / "platform_events.json"
_TTL_SECONDS = 300.0

# 거점 id 별칭 → 정규 slug (building_vacancy._ALIASES 와 동일하게 유지)
_ALIASES = {"gangnam-garosugil": "garosugil", "sinsa": "garosugil"}

_cache: dict[str, Any] = {}


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - _cache.get("at", 0.0) < _TTL_SECONDS:
        return _cache["data"]
    if not _EVENTS_JSON.exists():
        return None
    _cache["data"] = json.loads(_EVENTS_JSON.read_text(encoding="utf-8"))
    _cache["at"] = now
    return _cache["data"]


def is_available() -> bool:
    """행사 Gold 가 적재돼 있는가."""
    return _load() is not None


def for_district(district_id: str) -> list[dict] | None:
    """거점의 실제 행사 목록.

    반환값의 의미를 구분할 것:
      - `None`  Gold 미적재 (파이프라인 미실행) → 호출부가 출처를 "none" 으로 표기
      - `[]`    적재됐고 그 거점에 예정 행사가 없음 → 빈 상태를 그대로 보여준다
    """
    data = _load()
    if not data:
        return None
    slug = _ALIASES.get(district_id, district_id)
    return (data.get("districts") or {}).get(slug, [])
