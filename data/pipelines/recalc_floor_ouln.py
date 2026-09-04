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

**2026-08-01 층 단위 매칭.** 지금까지 분자는 '건물 내 점포 수'(층 무관), 분모는
'지상 상업층 수'라 단위가 달랐고 min(active, capacity) 클램프가 그 불일치를 덮고
있었다(`docs/finding-anchor-population.md`). 상가정보 원본의 flrNo 를 층별개요 층번호와
맞춰 두 가지를 같이 고친다:
  · 분모 = 층별개요 상업층 **∪ 점포·인허가가 확인된 지상층** — 점포의 22.6%가 분모 밖에
    있었다. 인허가는 주소에 층이 적혀 있어(영업 중의 86.3%) 상층부를 덮는 독립 소스다.
  · 분자 = **점포가 확인된 층 수**. flrNo 공란이 약 30%라 단일 값이 될 수 없어
    하한(층이 확인된 점포만)과 상한(층 미상 점포를 빈 층에 낮은 층부터 배정)을 함께 쓴다.
    대표 occupancy 는 **상한**이다 — 하한은 공란 30%를 전부 공실로 미는 편향이 있다.
행에 occupancy_lo/hi · vacancy_lo/hi · active_floors_lo/hi · capacity_floors 를 남긴다.
기존 `active`(점포 수)는 하위호환으로 그대로 둔다.

실행:
  python -m data.pipelines.recalc_floor_ouln --dry-run          # 영향만 출력
  python -m data.pipelines.recalc_floor_ouln garosugil          # 반영
  python -m data.pipelines.recalc_floor_ouln --legacy garosugil # 점포수 기준(구식)
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter

from data.collectors.building_vacancy import NO_COM_FLOOR, STORES_PER_FLOOR, classify
from data.collectors.common import BRONZE, GOLD
from data.collectors.floor_capacity import (
    _commercial_floors, capacity_floors, commercial_floor_nos, ground_floors,
)
from data.config.page_hubs import ACTIVE_HUBS, get_hub
from data.pipelines.build_building_attrs import load as load_attrs
from data.pipelines.build_building_attrs import run as build_attrs

# 재계산 대상 — 층별개요로 분모를 다시 깔 수 있는 방식만. expos_units(전유부 실측)는
# 층수 근사보다 정밀하므로 건드리지 않는다(recalc_capacity 의 회귀 교훈과 동일).
# no_com_floor 도 넣는다 — 이 모듈이 붙인 라벨이고, 근거(bronze 층별개요)가 그대로
# 남아 있으므로 NON_CAPACITY_PURPS 나 capacity_floors 가 넓어지면 **되돌릴 수 있어야**
# 한다. 넣지 않으면 강등이 편도가 되어 필터를 고쳐도 그 건물들이 영영 안 돌아온다.
_TARGET_METHODS = {"floor_ouln", "floor_approx", NO_COM_FLOOR}


def _vac(active: int, cap: int) -> tuple[float, float, str]:
    occ = min(active / cap, 1.0) if cap else 0.0
    return round(occ, 3), round((1 - occ) * 100, 1), classify(occ, "floor_ouln")


def occupied_floors(floors: set[int], store_nos: set[int], unknown: int) -> tuple[int, int]:
    """(점포 확인 층 수 하한, 층 미상 점포까지 배정한 상한).

    상한은 층 미상 점포를 **낮은 층부터** 빈 층에 하나씩 앉힌다. 1층 점포가 주소에
    층 표기를 생략하는 경우가 많아(공란 약 30%) 낮은 층 우선이 현실에 가깝다.
    """
    lo = len(floors & store_nos)
    return lo, min(len(floors), lo + max(unknown, 0))


def _truncated(flr: dict) -> float:
    """지번당 층 레코드가 1개뿐인 비율. pageNo 누락 수집분 판별용.

    2026-07-26: floor_capacity 가 pageNo 없이 요청해 서버가 numOfRows=1 로 강제,
    건물당 첫 행(대개 지하1층)만 저장됐다. 이런 원본으로 재계산하면 '지상 상업층 0'
    이 대량 발생해 조용히 틀린 결과가 나오므로, 재계산을 거부하고 재수집을 안내한다.
    """
    if not flr:
        return 0.0
    return sum(1 for v in flr.values() if len(v) <= 1) / len(flr)


def _load_flr(slug: str) -> dict | None:
    """bronze 층별개요를 **전 스냅샷 병합**해 읽는다.

    `load_latest` 를 쓰면 안 된다 — 층별개요는 건축HUB 일일 쿼터 때문에 날짜를 나눠
    조금씩 모으므로, 최신 폴더가 그날 받은 **일부**만 담고 있는 게 정상이다.
    최신 하나만 집으면 앞서 모은 대부분이 사라지고, 분모(상업층)가 비어 레거시
    폴백으로 떨어져 occupancy 가 1.0 으로 포화된다 → 공실률 0% 아티팩트.
    (2026-08-17 실측: dangsan 최신 18지번 vs 직전 160지번 → 평균 공실 19.5% → 0.0%)

    병합 규칙은 build_building_attrs 와 같다 — 같은 지번은 **층 레코드가 많은 쪽**을
    남긴다(부분 수집본이 완전본을 덮어쓰지 않게).
    """
    merged: dict = {}
    for p in sorted((BRONZE / slug).glob("*/bldg_flr_raw.json")):
        try:
            snap = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(snap, dict):
            continue
        for pnu, rows in snap.items():
            if len(rows or []) >= len(merged.get(pnu) or []):
                merged[pnu] = rows
    return merged or None


def run(slug: str, apply: bool, legacy: bool = False) -> dict | None:
    flr = _load_flr(slug)
    if not flr:
        return None
    path = GOLD / slug / "building_vacancy.json"
    if not path.exists():
        return None
    attrs = {} if legacy else (load_attrs(slug) or (build_attrs(slug), load_attrs(slug))[1])

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

    changed = zero_com = widened = demoted = 0
    ratios: list[float] = []
    after_vac: list[float] = []
    for r in rows:
        if r.get("capacity_method") not in _TARGET_METHODS:
            continue
        pnu = r.get("lnoCd", "")
        recs = flr.get(pnu)
        if not recs:
            continue
        n_grnd = ground_floors(recs)
        com_nos = commercial_floor_nos(recs)
        at = attrs.get(pnu, {})
        # 분자·분모의 층 근거 = 상가정보 flrNo ∪ 인허가 주소의 층 표기(독립 소스)
        store_nos = set(at.get("store_flr_nos") or []) | set(at.get("lic_flr_nos") or [])
        floors = (com_nos if legacy
                  else capacity_floors(com_nos, store_nos, at.get("grnd_flr") or 0))
        n_com = len(floors) if not legacy else _commercial_floors(recs)
        if not n_com:
            # 상업층 0. 값을 지어내지 않는 것(2026-07-26 교정)은 그대로 두되, **라벨은
            # 바꾼다**(2026-09-04). 종전에는 floor_approx 로 남겨서 "아직 층별개요를
            # 못 받았다"와 구별이 안 됐다. 이 행은 층별개요를 정상 수신했고 지상 상업층이
            # 0 이며 점포·인허가로 확인된 지상층도 없다 — 재호출로 바뀌지 않는 **판정**이다.
            # 실측 분포(66거점 642동 중 634동)도 이쪽이었다: 지상층 주용도가 여관·호텔·
            # 오피스텔·사무소·고시원, 즉 NON_CAPACITY_PURPS 모집단 그 자체다.
            # floor_approx 로 두면 capacity = 지상 전체 층수가 남아 13층 오피스텔이
            # 지도에 "공실 84.6%" 로 칠해진다(doksan 어반팰리스, active 2 / cap 13).
            # --legacy 는 좁은 필터(_commercial_floors)라 강등 근거로 쓰지 않는다.
            zero_com += 1
            if not legacy and r.get("capacity_method") == "floor_approx":
                demoted += 1               # dry-run 에서도 센다 — 규모를 보고 반영을 정한다
                if apply:
                    r.update(capacity=None, capacity_method=NO_COM_FLOOR,
                             occupancy=None, vacancy_bldg=None, status="n_a")
            continue
        widened += len(floors) > len(com_nos)
        if n_grnd:
            ratios.append(n_grnd / n_com)
        cap = max(n_com * STORES_PER_FLOOR, 1)
        if legacy:
            occ, vac, st = _vac(r.get("active", 0), cap)
            extra: dict = {}
        else:
            # 층 단위 매칭 — 분자도 층으로 센다(상한을 대표값으로).
            lo, hi = occupied_floors(
                floors, store_nos,
                (at.get("store_flr_unknown") or 0) + (at.get("lic_unknown") or 0))
            occ = round(hi / cap, 3) if cap else 0.0
            vac = round((1 - occ) * 100, 1)
            st = classify(occ, "floor_ouln")
            extra = {"active_floors_lo": lo, "active_floors_hi": hi,
                     "capacity_floors": sorted(floors),
                     "occupancy_lo": round(lo / cap, 3) if cap else 0.0,
                     "vacancy_lo": round((1 - lo / cap) * 100, 1) if cap else 0.0,
                     "occupancy_hi": occ, "vacancy_hi": vac}
        after_vac.append(vac)
        if apply:
            r.update(capacity=cap, capacity_method="floor_ouln",
                     occupancy=occ, vacancy_bldg=vac, status=st, **extra)
        changed += 1

    if apply and (changed or demoted):
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "slug": slug, "층별개요보유": len(flr), "재계산": changed, "상업층0": zero_com,
        "상업층0강등": demoted,
        "분모확장": widened,
        "before_pinned": before_pin,
        "before_vac": round(statistics.fmean(before_vac), 1) if before_vac else None,
        "after_vac": round(statistics.fmean(after_vac), 1) if after_vac else None,
        "지상/상업 층비 중앙값": round(statistics.median(ratios), 2) if ratios else None,
        "before_methods": dict(before_m),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="반영하지 않고 영향만 출력")
    ap.add_argument("--legacy", action="store_true",
                    help="층 단위 매칭 없이 점포 수 기준으로 재계산(2026-08-01 이전 방식)")
    ap.add_argument("slugs", nargs="*", help="대상 거점 (기본: 전 거점)")
    args = ap.parse_args()
    apply = not args.dry_run

    slugs = args.slugs or list(ACTIVE_HUBS)
    hit = 0
    for s in slugs:
        if get_hub(s) is None:
            # 이름을 대고 불렀는데 못 찾았다 = 오타이거나 미등록이다. 건너뛰고 exit 0 으로
            # 끝내면 부르는 쪽(hub-chain·loop-engine)이 수집된 줄 안다 — 2026-08-30 hwajeong.
            raise SystemExit(f"[recalc-ouln] 미등록 거점 '{s}' — page_hubs 의 HUBS/GYEONGGI_HUBS 확인")
        r = run(s, apply, legacy=args.legacy)
        if r is None:
            continue
        hit += 1
        print(f"[recalc-ouln:{s}][{'APPLY' if apply else 'DRY-RUN'}] "
              f"층별개요 {r['층별개요보유']}지번 → 재계산 {r['재계산']}동 "
              f"(상업층0 {r['상업층0']}동 중 {r['상업층0강등']}동 no_com_floor 강등)")
        print(f"    capacity==active 로 고정돼 있던 행: {r['before_pinned']}동")
        print(f"    점포 확인 층으로 분모가 넓어진 건물: {r['분모확장']}동")
        print(f"    평균 공실 {r['before_vac']}% → {r['after_vac']}%")
        print(f"    지상 전체층수 / 상업층수 중앙값: {r['지상/상업 층비 중앙값']}배")
    if not hit:
        print("[recalc-ouln] bldg_flr_raw.json 을 가진 거점이 없습니다 "
              "(floor_capacity 를 먼저 실행해야 합니다).")
    elif not apply:
        print("[recalc-ouln] dry-run 이었습니다. 반영하려면 --dry-run 을 빼세요.")


if __name__ == "__main__":
    main()
