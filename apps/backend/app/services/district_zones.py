"""거점 구역 로더 — `gold/{거점}/district_zones.json` 한 벌.

## 무엇이 바뀌었나 (2026-09-05)

이 자리는 `app/data/seoul_pages.py` 의 **손으로 적은 감성 구역**이었다. 54거점 ×
6구역 = 324개가 전부 사람이 쓴 값이었고(감성 76.8 · 리뷰 2,140건 · "+41%"),
2차 12거점에는 아예 없어 화면이 "이 거점의 감성 구역이 없다"를 냈다.

이제 66거점이 **행정동 실측 구역** 하나의 규칙 위에 선다
(`data/pipelines/build_district_zones.py`). 구역 수는 거점마다 다르다 — 1~11개,
중앙 3 — **거점이 실제로 몇 개 행정동에 걸쳐 있느냐**가 정하기 때문이다. 시드가
전 거점 6개로 똑같았던 것은 실측이 아니라 서식이었다는 뜻이다.

## 감성은 여전히 없다 — 그리고 그게 응답에 드러난다

`s`·`d`·`r` 은 **null**, `f` 는 빈 배열로 나간다. 0 으로 채우면 "쟀더니 0"으로
읽힌다. 2026-08-25 실측으로 세 다리가 모두 끊긴 것을 확인했다(feature-platform §0-K):
블로그 원문에 좌표가 없어 구역으로 못 내려오고(구조), 점포명 귀속은 3.18%이며(귀속),
부정어가 0.53%다(신호). 좌표를 가진 점포 리뷰 채널이 생기기 전에는 채울 수 없다.

⚠ **공실률·점포수를 `s` 에 옮겨 담아 "감성"으로 부르지 말 것.** AGENTS.md 가 Gold
활력 지표로의 대체를 금지한다 — 그건 측정이 아니라 이름 바꾸기다.

## 합계는 거점 대표값과 맞는다

`sum(zones.capacity) + residual.capacity == 거점 분모` 가 66거점 전부에서 성립한다
(`active` 도 같다). `residual` 은 스필오버로 뺀 작은 행정동 몫이다 — 그냥 버리면
구역 합계가 거점 대표값과 어긋나 두 화면이 서로 다른 말을 한다.
`data/tests/test_district_zones.py` 가 이 항등식을 고정한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

_cache: dict[str, dict | None] = {}


def path(slug: str) -> Path:
    return _GOLD_DIR / slug / "district_zones.json"


def slug_of(district_id: str | None) -> str | None:
    """거점 id → 파일 슬러그. 슬러그 모양이 아니면 None(경로 조작 차단)."""
    s = district_id or ""
    return s if _SLUG_RE.match(s) else None


def clear_cache() -> None:
    """테스트·재적재용. 프로세스 전역 캐시를 비운다."""
    _cache.clear()


def load(district_id: str | None) -> dict | None:
    """`gold/{거점}/district_zones.json` 통째로. 없거나 깨졌으면 None.

    파일이 없는 것은 **정상 상태**다(아직 파이프라인을 안 돌린 거점). 예외를 올리지
    않고 None 을 주어 호출부가 빈 목록으로 물러나게 한다.
    """
    slug = slug_of(district_id)
    if slug is None:
        return None
    if slug in _cache:
        return _cache[slug]
    p = path(slug)
    data: dict | None = None
    if p.exists():
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("zones"), list):
                data = loaded
        except (OSError, ValueError):
            data = None
    _cache[slug] = data
    return data


def zones(district_id: str | None) -> list[dict]:
    """거점의 구역 목록. 없으면 빈 리스트."""
    d = load(district_id)
    return list(d["zones"]) if d else []
