"""α보정 — 건물 추정 공실률을 부동산원 공식 통계에 스케일 정렬 (poc §3-1).

앵커(2025 기준, poc-building-vacancy.md §0.5 — 부동산원 CSV 로더 연동 시 자동 갱신 TODO):
  가두상권(도로변) 41.6% / 신사역 집합상가 9.99%

방법(v1): 매칭건물(stores+ledger) 집계 공실률 대비 가두 앵커의 비율 α를 산출해
gold/{SLUG}/calibration.json 에 기록한다. 개별 건물 vacancy 에 α를 곱한
`vacancy_calibrated` 는 소비층(API/ML)이 선택적으로 사용.

한계(문서화): 추정치는 '가두(1층 도로변)'와 '집합상가'가 섞여 있어 단일 α는 근사다.
→ 정밀화: 1층 도로변/집합 분리 집계 후 이중 앵커 (poc §5 특이점).

실행: python -m data.pipelines.calibrate_vacancy
"""
from __future__ import annotations

import json

from data.collectors.common import GOLD
from data.config.garosugil import SLUG

ANCHOR_STREET = 41.6   # 부동산원 가두상권 공실률 (%) — TODO: CSV 로더로 대체
ANCHOR_MALL = 9.99     # 부동산원 신사역 집합상가 공실률 (%)


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

    out = {
        "estimated_vacancy_pct": est,
        "anchor_street_pct": ANCHOR_STREET,
        "anchor_mall_pct": ANCHOR_MALL,
        "alpha_street": alpha,
        "gap_pp": gap,
        "buildings_used": len(known),
        "note": "vacancy_calibrated = vacancy_bldg × alpha_street (근사). "
                "가두/집합 분리 집계 정밀화 TODO (poc §5).",
    }
    dst = GOLD / SLUG / "calibration.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[calibrate] 추정 {est}% vs 가두 앵커 {ANCHOR_STREET}% → gap {gap}%p, α={alpha}")
    print(f"[calibrate] {dst.relative_to(GOLD.parent)}")


if __name__ == "__main__":
    run()
