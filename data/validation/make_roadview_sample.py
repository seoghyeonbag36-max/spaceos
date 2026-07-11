"""로드뷰 지상검증(ground truth) 샘플 생성 — poc §3-2 (PoC exit 판정 재료).

page_building_master 에서 status 층화 샘플 30동을 뽑아
  data/validation/roadview_sample.csv   ← 사용자가 label_actual 채움
  data/validation/roadview_sample.md    ← 클릭 가능한 네이버 지도 링크 목록
을 만든다. 라벨 규칙(label_actual): 공실 / 부분공실 / 영업 / 불명

판정 기준은 **건물 전체 호실**(1층이 아니라). status 의 분모 capacity 가 건물 전체
호수이므로 라벨도 같은 척도여야 한다. 링크는 상호명이 아닌 pnu 지번주소로 만든다.

채점: 라벨 입력 후 python -m data.validation.score_labels

실행: python -m data.validation.make_roadview_sample
"""
from __future__ import annotations

import csv
import json
import random
import re
from pathlib import Path
from urllib.parse import quote

from data.collectors.common import GOLD
from data.config.garosugil import SLUG
from data.pipelines.build_page_master import _label

_OUT = Path(__file__).resolve().parent
_QUOTA = {"empty": 12, "high": 8, "partial": 5, "full": 5}   # 계 30동
_SEED = 42   # 재현 가능 샘플

# gold 의 name 이 상호명이 아니라 지번(폴백 라벨)인 경우를 표에서 숨기기 위한 판별.
# 구 gold 는 부번 0 을 "신사동 512-0" 으로 기록했으므로 그 형태도 함께 잡는다.
_JIBUN_RE = re.compile(r"^\S+동\s+\d+(-\d+)?$")


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
            # 링크는 항상 pnu 지번주소로 만든다. name 은 상가정보 상호명이라
            # 잘리거나("제", "지") 동명 건물이 여럿("○○빌딩")이라 건물 특정이 안 된다.
            jibun = _label(p["pnu"], "")
            addr = f"서울 강남구 {jibun}"
            rows.append({
                "id": p["id"], "name": p["name"], "jibun": jibun,
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
          "링크 클릭 → 네이버 지도에서 해당 건물 → **거리뷰**로 확인.",
          "링크는 지번주소 검색이다. 표의 `건물`(상호명)은 참고용이며, 건물 특정은 "
          "지번 또는 CSV 의 `coord`(폴리곤 중심좌표)를 기준으로 한다.",
          "",
          "## 판정 기준 — 건물 전체 호실 (1층만 보지 않는다)",
          "",
          "예측 `status` 의 분모 `capacity` 가 **건물 전체 호수**(건축물대장 호수 또는 층수×2)이므로,",
          "라벨도 전체 호실 기준이어야 채점이 성립한다. 1층만 보고 판정하면 상층 공실이 있는 건물이",
          "일괄 `영업` 으로 라벨되어 정확도가 체계적으로 깎인다.",
          "",
          "거리뷰에서 **간판·층별 안내판·창문/블라인드·임대 현수막**으로 상층부까지 판정할 것.",
          "",
          "| label_actual | 의미 |",
          "|---|---|",
          "| `공실` | 영업 중인 호실이 없거나 사실상 전무 (전층 공실·임대 현수막) |",
          "| `부분공실` | 영업 호실과 빈 호실이 섞여 있음 |",
          "| `영업` | 빈 호실이 없거나 거의 없음 |",
          "| `불명` | 거리뷰 미제공·가림·신축 등으로 판정 불가 → 채점 제외 |",
          "",
          "## 대상 30동",
          "",
          "| # | 지번 | 건물(상호) | 예측 | 공실률 | 층 | 지도 |",
          "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        name = "—" if (not r["name"] or _JIBUN_RE.match(r["name"])) else r["name"]
        md.append(f"| {i} | {r['jibun']} | {name} ({r['active']}/{r['capacity']}호) "
                  f"| {r['status_predicted']} | {r['vacancy_rate']}% | {r['floors']}F "
                  f"| [열기]({r['naver_link']}) |")
    (_OUT / "roadview_sample.md").write_text("\n".join(md), encoding="utf-8")

    print(f"[validation] {csv_path.name} / roadview_sample.md — {len(rows)}동")


if __name__ == "__main__":
    run()
