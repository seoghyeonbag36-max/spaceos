"""[Page] 전유부 페이지 상한에 잘린 건물만 재수집 — bronze 원본 복구.

배경(2026-07-26): building_vacancy 의 _MAX_EXPOS_PAGES 가 8(=800호)이라 대형
집합건물의 전유부 응답이 잘린 채 bronze 에 저장됐다. 잘린 원본은 recalc_capacity
로 복구되지 않으므로(데이터 자체가 없음) 해당 건물만 다시 받아야 한다.
  실측: 8거점 6,539동 중 49동 절단, 최대 7,881호(seoulsup), 총 1,047페이지.

대상 판정: bldg_ledger_raw.json 의 expos_total > len(expos) 인 지번.
  → 상한을 올린 지금 기준으로 다시 페이징해 expos 를 통째로 교체한다.
표제부(title)는 잘리지 않으므로 건드리지 않는다.

재수집 후 반드시 recalc_capacity 를 돌려야 gold 에 반영된다:
  python -m data.collectors.refetch_truncated_expos seongsu seoulsup
  python -m data.pipelines.recalc_capacity seongsu seoulsup

실행: python -m data.collectors.refetch_truncated_expos [slug ...] [--dry-run] [--include-capped]

2026-08-09: 수집기가 대형 지번(totalCount > _EXPOS_FULL_MAX)을 **일부러** 끊고
`expos_capped` 를 남긴다(쿼터 보호 — dongdaemun 34,600 → 3,900콜). 그 지번은 기본
대상에서 뺀다. 넣으면 절감분이 그대로 되돌아온다. 집합건물을 대표 집계에 넣게 될 때만
--include-capped 로 연다.
"""
from __future__ import annotations

import os
import sys
import time

from data.collectors.building_vacancy import (
    BASE_BLD,
    _MAX_EXPOS_PAGES,
    _SLEEP,
    _get_json,
    _body,
    _items,
    _jibun,
)
from data.collectors.common import latest_bronze, load_env, load_latest, save_json
from data.config.page_hubs import ACTIVE_HUBS, ALL_HUBS

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


def truncated(raw_all: dict, include_capped: bool = False) -> list[str]:
    """expos_total 보다 실제 저장 행이 적은 지번(lnoCd) 목록.

    `expos_capped` 가 붙은 지번은 **의도적 부분 수집**이라 기본적으로 제외한다
    (building_vacancy._EXPOS_FULL_MAX). 이걸 빼지 않으면 쿼터를 아끼려고 끊은 것을
    이 스크립트가 그대로 되받는다.
    """
    return [
        lno for lno, v in raw_all.items()
        if (v.get("expos_total") or 0) > len(v.get("expos") or [])
        and (include_capped or not v.get("expos_capped"))
    ]


def fetch_all_expos(key: str, jibun: dict) -> tuple[list[dict], int]:
    """전유부 전량 페이징 (상한 _MAX_EXPOS_PAGES). 반환 (rows, totalCount)."""
    common = {"serviceKey": key, "_type": "json", "numOfRows": 100, **jibun}
    rows: list[dict] = []
    page, total = 1, 0
    while page <= _MAX_EXPOS_PAGES:
        data = _get_json(f"{BASE_BLD}/getBrExposPubuseAreaInfo", {**common, "pageNo": page})
        got = _items(data)
        rows += got
        total = int(_body(data).get("totalCount") or 0)
        if not got or len(rows) >= total:
            break
        page += 1
        time.sleep(_SLEEP)
    return rows, total


def run(key: str, slug: str, dry_run: bool, include_capped: bool = False) -> tuple[int, int]:
    """거점 하나. 반환 (대상 건물 수, 복구된 건물 수)."""
    raw_all = load_latest(slug, "bldg_ledger_raw.json")
    if not raw_all:
        return 0, 0
    targets = truncated(raw_all, include_capped)
    if not targets:
        print(f"[refetch:{slug}] 절단 건물 없음")
        return 0, 0

    need = sum(-(-(raw_all[l].get("expos_total") or 0) // 100) for l in targets)
    print(f"[refetch:{slug}] 절단 {len(targets)}동 — 예상 {need}페이지")
    if dry_run:
        return len(targets), 0

    fixed = 0
    for i, lno in enumerate(targets, 1):
        jibun = _jibun(lno)
        if jibun is None:
            continue
        rows, total = fetch_all_expos(key, jibun)
        before = len(raw_all[lno].get("expos") or [])
        if len(rows) > before:
            raw_all[lno]["expos"] = rows
            raw_all[lno]["expos_total"] = total
            fixed += 1
            print(f"  [{i}/{len(targets)}] {lno} {before} → {len(rows)}행 (total {total})")
        time.sleep(_SLEEP)

    # 같은 날짜 폴더에 덮어써 최신 bronze 를 갱신 (load_latest 가 이 파일을 읽는다)
    path = latest_bronze(slug, "bldg_ledger_raw.json")
    date = path.parent.name if path else None
    save_json(raw_all, slug, "bldg_ledger_raw.json", date=date)
    return len(targets), fixed


def main() -> None:
    load_env()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    include_capped = "--include-capped" in argv
    if (not key or requests is None) and not dry:
        print("[refetch] DATA_GO_KR_SERVICE_KEY 미설정(또는 requests 없음) — 중단")
        return
    slugs = [a for a in argv if not a.startswith("-")] or list(ACTIVE_HUBS)

    t = f = 0
    for slug in slugs:
        if slug not in ALL_HUBS:
            print(f"[refetch] 미등록 거점 '{slug}' — 건너뜀")
            continue
        a, b = run(key or "", slug, dry, include_capped)
        t += a
        f += b
    print(f"[refetch] 대상 {t}동 / 복구 {f}동"
          + (" (--dry-run — 호출하지 않음)" if dry else " → recalc_capacity 를 이어서 실행할 것"))


if __name__ == "__main__":
    main()
