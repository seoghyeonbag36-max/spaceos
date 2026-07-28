"""[Page] 분자(active) 재산출 — 현재 stores_raw + 현행 업종 필터로 **API 콜 없이** 갱신.

배경(2026-07-28): building_vacancy.json 의 `active` 는 그 건물이 **처음 수집된 시점**의
값이 그대로 남는다. run_hub 의 재개 로직이 기존 행을 완료로 보고 건너뛰기 때문이다.
그래서 NON_STOREFRONT_LCLS(사무실형 업종 제외, 2026-07-19 도입) 이전에 수집된 행은
필터가 적용되지 않은 분자를 그대로 들고 있다.

  garosugil 실측: 1,092행 중 341행이 미필터 값. 예) bdMgtSn …027324 는 active=98 로
  저장돼 있지만 현행 필터로 다시 세면 19 다(5.2배). 거점 합계로는 4,462 → 3,346.

build_page_master 는 stores_raw 로 분자를 다시 세므로(`fresh`) 지도 산출물은 영향을
받지 않았다. 그러나 **calibrate_vacancy 는 building_vacancy.json 을 직접 읽는다** —
즉 α 와 calibration.json 의 세그먼트 공실률이 오염된 분자로 계산돼 왔다. 같은 거점의
집계 공실률이 파이프라인(56.0%)과 calibration(38.3%) 사이에서 갈라진 원인 중 하나다.

수집기의 group_by_building 을 그대로 재사용하므로 산출 규칙이 어긋날 수 없다.
capacity 는 건드리지 않는다(분모 재산출은 recalc_capacity / recalc_floor_ouln 담당).

실행:
  python -m data.pipelines.refresh_active --dry-run        # 전 거점 영향만 출력
  python -m data.pipelines.refresh_active garosugil        # 거점 지정 반영
"""
from __future__ import annotations

import json
import sys
from collections import Counter

from data.collectors.building_vacancy import classify, group_by_building
from data.collectors.common import GOLD, load_latest
from data.config.page_hubs import HUBS


def run(slug: str, dry_run: bool) -> dict | None:
    gold = GOLD / slug / "building_vacancy.json"
    if not gold.exists():
        return None
    rows = json.loads(gold.read_text(encoding="utf-8"))
    if not rows or "capacity_method" not in rows[0]:
        return None                      # Tier2(대장 없음) — 대상 아님
    stores = load_latest(slug, "stores_raw.json")
    if not stores:
        print(f"[refresh-active:{slug}] stores_raw.json 없음 — 건너뜀")
        return None

    groups = group_by_building(stores)   # 수집기와 동일 규칙(업종 필터 포함)

    changed = missing = 0
    act_b = act_a = 0
    for r in rows:
        act_b += r.get("active") or 0
        g = groups.get(r.get("bdMgtSn", ""))
        if g is None:
            # 현재 stores_raw 에 해당 건물의 점포가 하나도 없다 — 전부 사무실형이라
            # 필터에 걸렸거나 폐업했다. 어느 쪽이든 활성 점포 0 이 사실이므로 0 으로 둔다.
            # (건물 자체는 유지한다 — capacity 는 대장에서 온 별개 근거다.)
            missing += 1
            new = 0
        else:
            new = g["active"]
        act_a += new
        if new == r.get("active"):
            continue
        changed += 1
        if dry_run:
            continue
        r["active"] = new
        cap = r.get("capacity")
        occ = min(new / cap, 1.0) if cap else None
        r["occupancy"] = None if occ is None else round(occ, 3)
        r["vacancy_bldg"] = None if occ is None else round((1 - occ) * 100, 1)
        r["status"] = classify(occ, r.get("capacity_method", ""))

    if not dry_run:
        gold.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"slug": slug, "buildings": len(rows), "changed": changed,
            "no_stores": missing, "active_before": act_b, "active_after": act_a}


def main() -> None:
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    slugs = [a for a in argv if not a.startswith("-")] or list(HUBS)

    print(f"{'거점':16s} {'건물':>6s} {'갱신':>6s} {'점포0':>6s} {'active 합':>18s}")
    tot: Counter = Counter()
    for slug in slugs:
        s = run(slug, dry)
        if s is None:
            continue
        print(f"{s['slug']:16s} {s['buildings']:6d} {s['changed']:6d} {s['no_stores']:6d} "
              f"{s['active_before']:8d}→{s['active_after']:<9d}")
        for k, v in s.items():
            if isinstance(v, int):
                tot[k] += v
    print(f"{'합계':16s} {tot['buildings']:6d} {tot['changed']:6d} {tot['no_stores']:6d} "
          f"{tot['active_before']:8d}→{tot['active_after']:<9d}")
    if dry:
        print("\n--dry-run — 파일은 변경하지 않았다.")


if __name__ == "__main__":
    main()
