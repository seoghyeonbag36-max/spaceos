"""α보정 — 건물 추정 공실률을 부동산원 공식 통계에 스케일 정렬 (poc §3-1).

앵커(2025 기준, poc-building-vacancy.md §0.5 — 부동산원 CSV 로더 연동 시 자동 갱신 TODO):
  가두상권(도로변) 41.6% / 신사역 집합상가 9.99%

방법(v1): 매칭건물(stores+ledger) 집계 공실률 대비 가두 앵커의 비율 α를 산출해
gold/{SLUG}/calibration.json 에 기록한다. 개별 건물 vacancy 에 α를 곱한
`vacancy_calibrated` 는 소비층(API/ML)이 선택적으로 사용.

정밀화(v2, poc §5 특이점): building_vacancy.json 의 capacity_method 로
집합건물(expos_units — 전유부 호수 실측)과 일반건물(floor_approx — 층수 근사)을
분리 집계해 각각 집합상가/가두 앵커에 정렬한 이중 α 를 `segments` 에 기록한다.
상단 combined 키(v1)는 기존 소비층 호환을 위해 유지한다.

실행: python -m data.pipelines.calibrate_vacancy
"""
from __future__ import annotations

import json

from data.collectors.common import GOLD
from data.config.garosugil import SLUG

ANCHOR_STREET = 41.6   # 부동산원 가두상권 공실률 (%) — TODO: CSV 로더로 대체
ANCHOR_MALL = 9.99     # 부동산원 신사역 집합상가 공실률 (%)

# capacity_method → 세그먼트: 전유부 호수 실측 = 집합건물, 층수 근사 = 일반(가두)
_SEGMENT_OF = {"expos_units": "mall", "floor_approx": "street"}


def _segments() -> dict:
    """building_vacancy.json 을 가두/집합으로 분리 집계해 세그먼트별 α 산출."""
    src = GOLD / SLUG / "building_vacancy.json"
    if not src.exists():
        return {}
    rows = json.loads(src.read_text(encoding="utf-8"))
    agg: dict[str, dict[str, int]] = {
        "street": {"active": 0, "capacity": 0, "buildings": 0},
        "mall": {"active": 0, "capacity": 0, "buildings": 0},
    }
    for r in rows:
        seg = _SEGMENT_OF.get(r.get("capacity_method", ""))
        if seg is None or not r.get("capacity"):
            continue
        agg[seg]["active"] += r["active"]
        # 하한 = active (build_page_master 와 동일한 음수 공실률 방지 규칙)
        agg[seg]["capacity"] += max(r["capacity"], r["active"])
        agg[seg]["buildings"] += 1

    out: dict[str, dict] = {}
    for seg, anchor in (("street", ANCHOR_STREET), ("mall", ANCHOR_MALL)):
        a = agg[seg]
        if not a["capacity"]:
            continue
        est = round((1 - a["active"] / a["capacity"]) * 100, 1)
        out[seg] = {
            "estimated_vacancy_pct": est,
            "anchor_pct": anchor,
            "alpha": round(anchor / est, 3) if est else None,
            "gap_pp": round(est - anchor, 1),
            "buildings": a["buildings"],
        }
    return out


def run() -> None:
    src = GOLD / SLUG / "page_building_master.geojson"
    if not src.exists():
        print("[calibrate] page_building_master 없음 — build_page_master 먼저")
        return
    fc = json.loads(src.read_text(encoding="utf-8"))
    known = [f["properties"] for f in fc["features"]
             if f["properties"].get("source") == "stores+ledger"]
    act = sum(p["active"] for p in known)
    cap = sum(p["capacity"] for p in known)
    est = round((1 - act / cap) * 100, 1)
    alpha = round(ANCHOR_STREET / est, 3)
    gap = round(est - ANCHOR_STREET, 1)

    segments = _segments()
    out = {
        "estimated_vacancy_pct": est,
        "anchor_street_pct": ANCHOR_STREET,
        "anchor_mall_pct": ANCHOR_MALL,
        "alpha_street": alpha,
        "gap_pp": gap,
        "buildings_used": len(known),
        "segments": segments,
        "note": "combined(v1) = 가두·집합 혼합 단일 α (기존 소비층 호환용). "
                "segments(v2) = capacity_method 로 분리한 이중 앵커 — "
                "가두 보정은 segments.street.alpha, 집합은 segments.mall.alpha 사용 권장.",
    }
    dst = GOLD / SLUG / "calibration.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[calibrate] combined: 추정 {est}% vs 가두 앵커 {ANCHOR_STREET}% → gap {gap}%p, α={alpha}")
    for seg, label in (("street", "가두(floor_approx)"), ("mall", "집합(expos_units)")):
        if seg in segments:
            s = segments[seg]
            print(f"[calibrate] {label}: 추정 {s['estimated_vacancy_pct']}% vs 앵커 {s['anchor_pct']}% "
                  f"→ gap {s['gap_pp']}%p, α={s['alpha']} ({s['buildings']}동)")
    print(f"[calibrate] {dst.relative_to(GOLD.parent)}")


if __name__ == "__main__":
    run()
