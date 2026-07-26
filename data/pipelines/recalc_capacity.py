"""[Page] 건물 capacity 재산출 — bronze 대장 원본에서 **API 콜 없이** 다시 계산.

배경(2026-07-26): building_vacancy 의 전유부 용도 필터가 표제부용 대분류 상수
(COMMERCIAL_PURPS)를 세부용도명에 그대로 적용하고 있었다. 전유부 mainPurpsCdNm 은
"소매점"/"일반음식점"/"의원" 같은 세부용도라 대분류 키워드가 거의 걸리지 않아
capacity 가 14배 과소집계됐고, occupancy 가 1.0 으로 clip 되어 공실이 과소추정됐다.
  (압구정로데오 실측: capacity 47호 → 688호, clip 비율 73% → 33%)

fetch_capacity 가 전유부·표제부 응답 원본을 bronze/{SLUG}/bldg_ledger_raw.json 에
통째로 남기므로 **재수집 없이** 필터만 바꿔 재계산할 수 있다. 이 파이프라인은
collectors.building_vacancy 의 판정 로직(expos_units → 표제부 층수 근사)을 그대로
오프라인 재현해 gold/{SLUG}/building_vacancy.json 의 capacity 계열 필드를 갱신한다.

주의: 8페이지 상한(_MAX_EXPOS_PAGES=800호)에 걸려 잘린 건물은 원본 자체가 불완전해
재계산으로 복구되지 않는다. 해당 건물 수를 리포트에 표시한다(재수집 대상).

실행:
  python -m data.pipelines.recalc_capacity --dry-run           # 전 거점 영향만 출력
  python -m data.pipelines.recalc_capacity garosugil           # 거점 지정 반영
"""
from __future__ import annotations

import json
import sys
from collections import Counter

from data.collectors.building_vacancy import classify, expos_units
from data.collectors.common import GOLD, load_latest
from data.config.page_hubs import HUBS


def capacity_from_raw(raw: dict) -> tuple[int | None, str]:
    """bldg_ledger_raw 의 지번 1건 → (capacity, "expos_units") 또는 (None, "") .

    **전유부 경로만** 재판정한다. 버그가 전유부 용도 필터에만 있었으므로, 전유 호가
    잡히지 않으면 기존 값을 그대로 두는 것이 안전하다. 표제부 층수 근사를 여기서
    다시 계산하면 garosugil 처럼 층별개요(floor_ouln)로 산출된 더 정밀한 capacity 를
    floor_approx 로 덮어써 회귀가 난다(2026-07-26 실제 발생: 537동 강등, 가두 세그먼트
    추정 공실률 4.4% → 58.6% 로 왜곡).
    """
    units = expos_units(raw.get("expos") or [])
    return (len(units), "expos_units") if units else (None, "")


def run(slug: str, dry_run: bool) -> dict | None:
    gold = GOLD / slug / "building_vacancy.json"
    if not gold.exists():
        return None
    rows = json.loads(gold.read_text(encoding="utf-8"))
    if not rows or "capacity_method" not in rows[0]:
        return None                      # Tier2(대장 없음) — 대상 아님
    raw_all = load_latest(slug, "bldg_ledger_raw.json") or {}
    if not raw_all:
        print(f"[recalc:{slug}] bldg_ledger_raw.json 없음 — 건너뜀")
        return None

    before = Counter(r["capacity_method"] for r in rows)
    # 실제로 잘린 건물 = 저장 행 수가 totalCount 에 못 미치는 것.
    # (expos_total > 800 은 '큰 건물'일 뿐 복구 후에도 계속 참이라 지표로 못 쓴다.)
    truncated = sum(1 for v in raw_all.values()
                    if (v.get("expos_total") or 0) > len(v.get("expos") or []))
    clip_b = clip_a = 0
    cap_b = cap_a = 0

    for r in rows:
        raw = raw_all.get(r.get("lnoCd", ""))
        if raw is None:
            continue                     # no_jibun 등 원본 없는 건 그대로 둔다
        cap, method = capacity_from_raw(raw)
        occ_b = min(r["active"] / r["capacity"], 1.0) if r.get("capacity") else None
        if occ_b is not None and occ_b >= 1.0:
            clip_b += 1
        cap_b += r.get("capacity") or 0
        if cap is None:                  # 전유부 판정 불가 — 기존 산출값 보존
            cap_a += r.get("capacity") or 0
            if occ_b is not None and occ_b >= 1.0:
                clip_a += 1
            continue

        occ_a = min(r["active"] / cap, 1.0)
        if occ_a >= 1.0:
            clip_a += 1
        cap_a += cap

        r["capacity"] = cap
        r["capacity_method"] = method
        r["occupancy"] = round(occ_a, 3)
        r["vacancy_bldg"] = round((1 - occ_a) * 100, 1)
        r["status"] = classify(occ_a, method)

    after = Counter(r["capacity_method"] for r in rows)
    stat = {
        "slug": slug, "buildings": len(rows),
        "expos_before": before["expos_units"], "expos_after": after["expos_units"],
        "capacity_before": cap_b, "capacity_after": cap_a,
        "clip_before": clip_b, "clip_after": clip_a,
        "truncated_800": truncated,
    }
    if not dry_run:
        gold.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[recalc:{slug}] 반영 완료 — {gold}")
    return stat


def main() -> None:
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    slugs = [a for a in argv if not a.startswith("-")] or list(HUBS)

    print(f"{'거점':16s} {'건물':>6s} {'expos':>13s} {'capacity합':>16s} {'clip':>13s} {'800초과':>7s}")
    tot = Counter()
    for slug in slugs:
        s = run(slug, dry)
        if s is None:
            continue
        print(f"{s['slug']:16s} {s['buildings']:6d} "
              f"{s['expos_before']:5d}→{s['expos_after']:<7d} "
              f"{s['capacity_before']:7d}→{s['capacity_after']:<8d} "
              f"{s['clip_before']:5d}→{s['clip_after']:<7d} {s['truncated_800']:7d}")
        for k, v in s.items():
            if isinstance(v, int):
                tot[k] += v
    print(f"{'합계':16s} {tot['buildings']:6d} "
          f"{tot['expos_before']:5d}→{tot['expos_after']:<7d} "
          f"{tot['capacity_before']:7d}→{tot['capacity_after']:<8d} "
          f"{tot['clip_before']:5d}→{tot['clip_after']:<7d} {tot['truncated_800']:7d}")
    if dry:
        print("\n--dry-run — 파일은 변경하지 않았다.")


if __name__ == "__main__":
    main()
