"""공실 유닛 인벤토리 로더 — `gold/{거점}/vacant_units.json` 한 벌.

## 왜 별도 모듈인가

이 파일은 **Posting 의 인벤토리**다(건축물대장 실측으로 뽑은 실제 공실 자리).
Program 이 입력 계약 ①층(자리)에서 같은 파일을 빌려 쓴다 — 대상이 *"Platform 내 빈
Page 에 Posting(창업)할 기업"* 이라 의미상 Posting 이 선행하기 때문이다.

2026-08-23 에는 로더가 `program_site` 안에만 있었다. 그 상태로 Posting 이 인벤토리를
쓰려면 Posting → Program 을 임포트해야 하는데, 이는 문서화된 의존 방향
(Posting 선행 · Program 후행)을 거꾸로 세운다. 그래서 로더를 여기로 내리고 양쪽이
같은 것을 본다 — **파일 계약이 두 벌이 되면 한쪽만 고쳐지고 조용히 갈라진다.**

## 이 파일에 없는 것

시드(`app/data/seoul_pages.py`)의 유닛에는 있고 여기에는 **없는** 필드가 있다:

| 필드 | 시드 | 실 인벤토리 | 왜 |
|---|---|---|---|
| `rent` | 손으로 적음 | 없음 | R-ONE 으로 계산한다(posting_inputs) |
| `foot` | 손으로 적음 | 없음 | 상권 유동총량으로 계산한다(posting_inputs) |
| `prem` | 손으로 적음 | **없음** | 권리금은 공개 통계가 없다 → **입력 계약**으로 받는다 |
| `rec`·`persona`·`note` | 손으로 적음 | 없음 | 서술 문구다. `rec` 은 이미 계산으로 대체됐다(recommend_tier) |

`prem` 이 없는 것을 "결측"으로 두면 계산이 못 돈다. 0 으로 채우되 **채웠다는 사실을
`inputs_source["prem"]` 로 밝힌다** — 권리금 0 은 관측이 아니라 전제다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# 거점 id 별칭. program_site._DISTRICT_ALIAS · marketing._DISTRICT_ALIAS 와 어긋나면
# 같은 요청이 층마다 다른 거점을 가리킨다 — 늘릴 때는 셋을 같이 고친다.
_DISTRICT_ALIAS: dict[str, str] = {}

_cache: dict[str, dict | None] = {}


def path(slug: str) -> Path:
    return _GOLD_DIR / slug / "vacant_units.json"


def slug_of(district_id: str | None) -> str | None:
    """거점 id → 파일 슬러그. 슬러그 모양이 아니면 None(경로 조작 차단)."""
    s = _DISTRICT_ALIAS.get(district_id or "", district_id or "")
    return s if _SLUG_RE.match(s) else None


def clear_cache() -> None:
    """테스트·재적재용. 프로세스 전역 캐시를 비운다."""
    _cache.clear()


def load(district_id: str | None) -> dict | None:
    """`gold/{거점}/vacant_units.json` 통째로. 없거나 깨졌으면 None.

    파일이 없는 것은 **정상 상태**다(거점에 공실이 없거나 아직 안 돌렸거나). 예외를
    올리지 않고 None 을 주어 호출부가 시드로 물러나게 한다 — 다만 그 사실이 응답에
    드러나야 한다(`inputs_source` · `site_source`).
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
            if isinstance(loaded, dict) and isinstance(loaded.get("units"), list):
                data = loaded
        except (OSError, ValueError):
            data = None
    _cache[slug] = data
    return data


def units(district_id: str | None) -> list[dict]:
    """거점의 공실 유닛 목록. 없으면 빈 리스트."""
    d = load(district_id)
    return list(d["units"]) if d else []
