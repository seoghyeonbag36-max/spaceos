"""[Page] floor_ouln capacity 재산출 — bronze 층별개요 원본에서 **API 콜 없이** 다시 계산.

배경(2026-07-26): floor_capacity 의 층별개요 용도 필터가 표제부용 대분류 상수
(COMMERCIAL_PURPS)를 세부용도명에 적용하고 있었다. garosugil 실측으로 지상층 201개 중
12개(6.0%)만 매칭 → 559지번 중 420개가 "상업층 0" → capacity 가 붕괴했다. 여기에
`capacity = max(cap, active)` 클램프를 **저장**까지 하는 바람에 분모가 분자를 따라가
공실률이 0%(427동)/50%(111동) 두 값으로 고정됐다. 즉 기존 floor_ouln 산출물은
측정값이 아니라 아티팩트이고, calibrate 의 α=9.043 도 그 결과다.

floor_capacity 가 층별개요 응답 원본을 bronze/{SLUG}/bldg_flr_raw.json 에 통째로
남기므로 **재수집 없이** 필터·클램프만 고쳐 재계산할 수 있다(recalc_capacity 와 같은 전략).

두 산식을 나란히 리포트한다:
  floor_approx = 지상 전체 층수 × STORES_PER_FLOOR
  floor_ouln   = 상업용도 지상 층수 × STORES_PER_FLOOR   (주거·사무소·공장류 제외)

실행:
  python -m data.pipelines.recalc_floor_ouln --dry-run          # 영향만 출력
  python -m data.pipelines.recalc_floor_ouln garosugil          # 반영
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter

from data.collectors.building_vacancy import STORES_PER_FLOOR, classify
from data.collectors.common import GOLD, load_latest
from data.collectors.floor_capacity import _commercial_floors, ground_floors
from data.config.page_hubs import HUBS

# 재계산 대상 — 층별개요로 분모를 다시 깔 수 있는 방식만. expos_units(전유부 실측)는
# 층수 근사보다 정밀하므로 건드리지 않는다(recalc_capacity 의 회귀 교훈과 동일).
_TARGET_METHODS = {"floor_ouln", "floor_approx"}


def _vac(active: int, cap: int) -> tuple[float, float, str]:
    occ = min(active / cap, 1.0) if cap else 0.0
    return round(occ, 3), round((1 - occ) * 100, 1), classify(occ, "floor_ouln")


def _truncated(flr: dict) -> float:
    """지번당 층 레코드가 1개뿐인 비율. pageNo 누락 수집분 판별용.

    2026-07-26: floor_capacity 가 pageNo 없이 요청해 서버가 numOfRows=1 로 강제,
    건물당 첫 행(대개 지하1층)만 저장됐다. 이런 원본으로 재계산하면 '지상 상업층 0'
    이 대량 발생해 조용히 틀린 결과가 나오므로, 재계산을 거부하고 재수집을 안내한다.
    """
    if not flr:
        return 0.0
    return sum(1 for v in flr.values() if len(v) <= 1) / len(flr)


def run(slug: str, apply: bool) -> dict | None:
    flr = load_latest(slug, "bldg_flr_raw.json")
    if not flr:
        return None
    path = GOLD / slug / "building_vacancy.json"
    if not path.exists():
        return None

    trunc = _truncated(flr)
    if trunc > 0.5:
        print(f"[recalc-ouln:{slug}] ⚠ 층별개요 원본이 잘려 있습니다 — "
              f"{len(flr)}지번 중 {trunc*100:.0f}%가 층 레코드 1개뿐.\n"
              f"    pageNo 누락으로 건물당 1행만 수집된 원본이라 재계산이 불가능합니다.\n"
              f"    floor_capacity 를 (pageNo 수정본으로) 재실행해 원본을 다시 받으세요:\n"
              f"      python -m data.collectors.floor_capacity {slug}")
        return None

    rows = json.loads(path.read_text(encoding="utf-8"))

    before_m = Counter(r.get("capacity_method") for r in rows)
    before_pin = sum(1 for r in rows if r.get("capacity_method") in _TARGET_METHODS
                     and r.get("capacity") == r.get("active"))
    before_vac = [r["vacancy_bldg"] for r in rows
                  if r.get("capacity_method") in _TARGET_METHODS
                  and isinstance(r.get("vacancy_bldg"), (int, float))]

    changed = zero_com = 0
    ratios: list[float] = []
    after_vac: list[float] = []
    for r in rows:
        if r.get("capacity_method") not in _TARGET_METHODS:
            continue
        recs = flr.get(r.get("lnoCd", ""))
        if not recs:
            continue
        n_com, n_grnd = _commercial_floors(recs), ground_floors(recs)
        if not n_com:
            zero_com += 1          # 상업층 0 — 값을 지어내지 않고 기존 행 유지
            continue
        if n_grnd:
            ratios.append(n_grnd / n_com)
        cap = max(n_com * STORES_PER_FLOOR, 1)
        occ, vac, st = _vac(r.get("active", 0), cap)
        after_vac.append(vac)
        if apply:
            r.update(capacity=cap, capacity_method="floor_ouln",
                     occupancy=occ, vacancy_bldg=vac, status=st)
        changed += 1

    if apply and changed:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "slug": slug, "층별개요보유": len(flr), "재계산": changed, "상업층0유지": zero_com,
        "before_pinned": before_pin,
        "before_vac": round(statistics.fmean(before_vac), 1) if before_vac else None,
        "after_vac": round(statistics.fmean(after_vac), 1) if after_vac else None,
        "지상/상업 층비 중앙값": round(statistics.median(ratios), 2) if ratios else None,
        "before_methods": dict(before_m),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="반영하지 않고 영향만 출력")
    ap.add_argument("slugs", nargs="*", help="대상 거점 (기본: 전 거점)")
    args = ap.parse_args()
    apply = not args.dry_run

    slugs = args.slugs or list(HUBS)
    hit = 0
    for s in slugs:
        if s not in HUBS:
            print(f"[recalc-ouln] 미등록 거점 '{s}' — 건너뜀")
            continue
        r = run(s, apply)
        if r is None:
            continue
        hit += 1
        print(f"[recalc-ouln:{s}][{'APPLY' if apply else 'DRY-RUN'}] "
              f"층별개요 {r['층별개요보유']}지번 → 재계산 {r['재계산']}동 "
              f"(상업층0 유지 {r['상업층0유지']})")
        print(f"    capacity==active 로 고정돼 있던 행: {r['before_pinned']}동")
        print(f"    평균 공실 {r['before_vac']}% → {r['after_vac']}%")
        print(f"    지상 전체층수 / 상업층수 중앙값: {r['지상/상업 층비 중앙값']}배")
    if not hit:
        print("[recalc-ouln] bldg_flr_raw.json 을 가진 거점이 없습니다 "
              "(floor_capacity 를 먼저 실행해야 합니다).")
    elif not apply:
        print("[recalc-ouln] dry-run 이었습니다. 반영하려면 --dry-run 을 빼세요.")


if __name__ == "__main__":
    main()
