"""층·용도별 업종 적합도 — `gold/platform_industry_floor_fit.json` 정적 서빙.

매물 하나(층 + 대장 그 층의 용도)를 주면 "이 조건의 자리에 **실제로** 어떤 업종이
들어와 있는가"의 관측 분포를 돌려준다. 손으로 적은 매칭표가 아니라 상가정보 × 층별개요
조인 결과다(66거점 69,735건).

## GNN 추천과 합치지 않는다

`industry_recommend`(GNN)는 **좌표** 기준이고 라벨이 7종(음식점·카페·병원·편의점·숙박·
문화시설·약국)이다. 자리의 입지를 말한다. 여기는 **매물**(층·대장 용도) 기준이고 라벨이
상가정보 업종 중분류다. 축도 어휘도 달라서, 한 점수로 뭉치면 둘 다 못 믿게 된다.
화면은 둘을 나란히 두되 무엇을 재는지 각각 밝혀야 한다.

## 표본이 얇으면 말하지 않는다

`(용도, 층)` 칸이 없으면 층만 본 분포로 물러나고(`basis="floor"`), 그것도 없으면
None 이다. 어느 근거로 답했는지 `basis` 가 밝힌다 — 폴백이 실측처럼 읽히면 안 된다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_FIT_JSON = (Path(__file__).resolve().parents[4]
             / "data" / "gold" / "platform_industry_floor_fit.json")
_TTL_SECONDS = 300.0

_cache: dict[str, Any] = {}


def clear_cache() -> None:
    """테스트·재적재용."""
    _cache.clear()


def _load() -> dict | None:
    now = time.monotonic()
    if _cache.get("data") is not None and now - _cache.get("at", 0.0) < _TTL_SECONDS:
        return _cache["data"]
    if not _FIT_JSON.exists():
        return None
    try:
        _cache["data"] = json.loads(_FIT_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    _cache["at"] = now
    return _cache["data"]


def _floor_key(no: int, cap: int) -> str:
    return f"{no}" if no < cap else f"{cap}+"


def fit_for(floor: int | None, purps: str | None, *, top_k: int = 3) -> dict | None:
    """매물 한 자리의 업종 관측 분포. 근거가 없으면 None.

    반환: `{basis, n, top:[{industry, share, n}], note}`
      · basis "purps_floor" — 대장 용도 + 층으로 좁힌 관측(가장 좁고 근거가 강하다)
      · basis "floor"       — 용도 칸의 표본이 얇아 층만 본 폴백
    """
    d = _load()
    if d is None or floor is None:
        return None
    cap = int(d.get("floor_cap") or 4)
    fk = _floor_key(int(floor), cap)

    cell = None
    basis = ""
    if purps:
        cell = (d.get("by_purps_floor") or {}).get(f"{purps}|{fk}")
        basis = "purps_floor"
    if cell is None:
        cell = (d.get("by_floor") or {}).get(fk)
        basis = "floor"
    if not cell:
        return None

    return {
        "basis": basis,
        "n": cell.get("n", 0),
        "top": (cell.get("top") or [])[:top_k],
        # 이 문구는 응답에 실려 화면까지 간다. 파일에만 적어 두면 API 만 보는 쪽이
        # "추천 업종"으로 읽는다 — 이것은 추천이 아니라 관측이다.
        "note": ("같은 조건(대장 용도·층)의 자리에서 **실제 영업 중인** 업종 분포다. "
                 "그 자리에서 잘 된다는 뜻이 아니다(매출·생존은 안 봤다)."
                 if basis == "purps_floor" else
                 "대장 용도 칸의 표본이 얇아 **층만** 보고 답한 폴백이다. "
                 "용도 제약은 반영되지 않았다."),
    }


def meta() -> dict | None:
    """표 자체의 근거·한계. 화면이 목록 하단에 근거를 밝히는 데 쓴다."""
    d = _load()
    if d is None:
        return None
    return {"built_at": d.get("built_at"), "source": d.get("source"),
            "note": d.get("note"), "min_sample": d.get("min_sample"),
            "stats": d.get("stats")}
