"""로드뷰 지상검증(ground truth) 샘플 생성 — poc §3-2 (PoC exit 판정 재료).

page_building_master 에서 status 층화 샘플 30동을 뽑아
  data/validation/roadview_sample.csv   ← 사용자가 label_actual 채움
  data/validation/roadview_sample.md    ← 클릭 가능한 네이버 지도 링크 목록
을 만든다. 라벨 규칙(label_actual): 공실 / 부분공실 / 영업 / 불명

채점: 라벨 입력 후 python -m data.validation.score_labels

실행: python -m data.validation.make_roadview_sample
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from urllib.parse import quote

from data.collectors.common import GOLD
from data.config.garosugil import SLUG

_OUT = Path(__file__).resolve().parent
_QUOTA = {"empty": 12, "high": 8, "partial": 5, "full": 5}   # 계 30동
_SEED = 42   # 재현 가능 샘플


def _center(geom: dict) -> tuple[float, float]:
    ring = geom["coordinates"][0]
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def run() -> None:
    src = GOLD / SLUG / "page_building_master.geojson"
    fc = json.loads(src.read_text(encoding="utf-8"))
    rng = random.Random(_SEED)

    rows: list[dict] = []
    for status, n in _QUOTA.items():
        pool = [f for f in fc["features"] if f["properties"]["status"] == status]
        for f in rng.sample(pool, min(n, len(pool))):
            p = f["properties"]
            lat, lon = _center(f["geometry"])
            addr = f"서울 강남구 {p['name']}" if p["name"][0].isdigit() is False else p["name"]
            rows.append({
                "id": p["id"], "name": p["name"],
                "status_predicted": status,
                "vacancy_rate": p["vacancy_rate"],
                "active": p["active"], "capacity": p["capacity"],
                "floors": p.get("floors", ""),
                "naver_link": f"https://map.naver.com/p/search/{quote(addr)}",
                "coord": f"{lat:.6f},{lon:.6f}",
                "label_actual": "",   # ← 공실 / 부분공실 / 영업 / 불명
                "memo": "",
            })
    rng.shuffle(rows)   # 상태가 뭉치지 않게 섞어 블라인드에 가깝게

    csv_path = _OUT / "roadview_sample.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    md = ["# 로드뷰 검증 샘플 30동 — 라벨은 roadview_sample.csv 에 기입",
          "",
          "링크 클릭 → 네이버 지도에서 해당 건물 → **거리뷰**로 1층 공실 여부 확인.",
          "`label_actual` 값: `공실`(전층/1층 명백 공실) · `부분공실` · `영업` · `불명`",
          "",
          "| # | 건물 | 예측 | 공실률 | 지도 |",
          "|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        md.append(f"| {i} | {r['name']} ({r['active']}/{r['capacity']}호) "
                  f"| {r['status_predicted']} | {r['vacancy_rate']}% "
                  f"| [열기]({r['naver_link']}) |")
    (_OUT / "roadview_sample.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[validation] {csv_path.name} / roadview_sample.md — {len(rows)}동")


if __name__ == "__main__":
    run()
