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
from data.config.page_hubs import HUBS

ANCHOR_STREET = 41.6   # 부동산원 가두상권 공실률 (%) — TODO: CSV 로더로 대체
ANCHOR_MALL = 9.99     # 부동산원 신사역 집합상가 공실률 (%)

# capacity_method → 세그먼트: 전유부 호수 실측 = 집합건물, 층수 기반 = 일반(가두)
_SEGMENT_OF = {"expos_units": "mall", "floor_approx": "street", "floor_ouln": "street"}

# methods(v3) 용 앵커 — 층수 기반 두 방법을 분리해 각각 α 를 낸다. 2026-07-26 실측상
# floor_ouln(garosugil)은 앵커 대비 -37%p, floor_approx(12거점)는 +19~23%p 로 편향
# 방향이 반대라 같은 α 를 공유할 수 없다. segments(v2)는 기존 소비층 호환을 위해
# 둘을 street 로 묶은 채 유지하고, 거점별 보정은 methods 를 쓴다.
_ANCHOR_OF = {"expos_units": ANCHOR_MALL, "floor_approx": ANCHOR_STREET,
              "floor_ouln": ANCHOR_STREET}


def _agg(rows: list[dict], keys: set[str]) -> dict | None:
    """capacity_method 가 keys 에 속한 건물 집계 → 추정 공실률·α."""
    act = cap = n = 0
    for r in rows:
        if r.get("capacity_method") not in keys or not r.get("capacity"):
            continue
        act += r["active"]
        # 하한 = active (build_page_master 와 동일한 음수 공실률 방지 규칙)
        cap += max(r["capacity"], r["active"])
        n += 1
    if not cap:
        return None
    est = round((1 - act / cap) * 100, 1)
    anchor = _ANCHOR_OF.get(next(iter(keys)), ANCHOR_STREET) if len(keys) == 1 else None
    out = {"estimated_vacancy_pct": est, "buildings": n}
    if anchor is not None:
        out |= {"anchor_pct": anchor,
                "alpha": round(anchor / est, 3) if est else None,
                "gap_pp": round(est - anchor, 1)}
    return out


def _methods(rows: list[dict]) -> dict:
    """capacity_method 별 α (v3) — 거점별 보정의 권장 소스."""
    present = {r.get("capacity_method") for r in rows} & set(_ANCHOR_OF)
    return {m: a for m in sorted(present) if (a := _agg(rows, {m})) is not None}


def _segments(slug: str) -> dict:
    """building_vacancy.json 을 가두/집합으로 분리 집계해 세그먼트별 α 산출."""
    src = GOLD / slug / "building_vacancy.json"
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


def run(slug: str) -> bool:
    """거점 하나의 calibration.json 산출. 반환: 성공 여부.

    combined(v1)은 기존과 동일하게 page_building_master.geojson 에서 계산한다.
    master 가 아직 없는 거점(수집만 끝난 상태)도 segments/methods 는 낼 수 있으므로
    combined 키만 비운 채 저장한다.
    """
    vac = GOLD / slug / "building_vacancy.json"
    if not vac.exists():
        return False
    rows = json.loads(vac.read_text(encoding="utf-8"))
    if not rows or "capacity_method" not in rows[0]:
        return False                       # Tier2(대장 없음) — 보정 대상 아님

    out: dict = {
        "anchor_street_pct": ANCHOR_STREET,
        "anchor_mall_pct": ANCHOR_MALL,
    }
    src = GOLD / slug / "page_building_master.geojson"
    if src.exists():
        fc = json.loads(src.read_text(encoding="utf-8"))
        known = [f["properties"] for f in fc["features"]
                 if str(f["properties"].get("source", "")).startswith("stores+ledger")]
        act = sum(p["active"] for p in known)
        cap = sum(p["capacity"] for p in known)
        if cap:
            est = round((1 - act / cap) * 100, 1)
            out |= {
                "estimated_vacancy_pct": est,
                "alpha_street": round(ANCHOR_STREET / est, 3) if est else None,
                "gap_pp": round(est - ANCHOR_STREET, 1),
                "buildings_used": len(known),
            }
            print(f"[calibrate:{slug}] combined: 추정 {est}% vs 가두 앵커 "
                  f"{ANCHOR_STREET}% → gap {out['gap_pp']}%p, α={out['alpha_street']}")
    else:
        print(f"[calibrate:{slug}] page_building_master 없음 — combined 생략"
              f"(segments/methods 만 산출)")

    segments = _segments(slug)
    methods = _methods(rows)
    out |= {
        "segments": segments,
        "methods": methods,
        "note": "combined(v1) = 가두·집합 혼합 단일 α (기존 소비층 호환용). "
                "segments(v2) = capacity_method 로 분리한 이중 앵커 — "
                "가두 보정은 segments.street.alpha, 집합은 segments.mall.alpha 사용 권장. "
                "methods(v3) = capacity_method 단위 α. floor_ouln 과 floor_approx 는 "
                "편향 방향이 반대라 street 로 묶으면 안 되므로 거점별 보정은 이쪽을 쓴다.",
    }
    dst = GOLD / slug / "calibration.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for m, s in methods.items():
        print(f"[calibrate:{slug}]   {m:13s} 추정 {s['estimated_vacancy_pct']:5.1f}% "
              f"vs 앵커 {s['anchor_pct']:5.2f}% → gap {s['gap_pp']:+6.1f}%p, "
              f"α={s['alpha']} ({s['buildings']}동)")
    return True


def main() -> None:
    import sys

    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(HUBS)
    ok = sum(1 for s in slugs if s in HUBS and run(s))
    print(f"[calibrate] 완료: {ok}거점")


if __name__ == "__main__":
    main()
