"""[검증] capacity 산출 방식 판정용 로드뷰 샘플 — floor_approx vs floor_ouln 결착.

문제(2026-07-26): 같은 부동산원 가두 앵커(41.6%)에 대해 두 방식이 **반대 방향**으로 어긋난다.
  floor_ouln  (garosugil 538동) 추정 4.6%  → 앵커 대비 -37.0%p, α=9.043
  floor_approx(12거점 7,500여동) 추정 60~72% → 앵커 대비 +19~30%p, α=0.58~0.69
α 보정은 이 격차를 덮을 뿐 어느 쪽이 사실인지 말해주지 않는다. 앵커 자체가 이 도메인과
맞지 않을 가능성도 남아 있다. 실측 없이 floor_ouln 전면 도입(≈10,250콜)에 쿼터를
태우는 것은 도박이므로, **건축HUB 콜 0건**인 로드뷰 관찰로 먼저 결착낸다.

핵심 착안: 두 방식의 차이는 오직 '몇 개 층을 상가로 세는가' 하나다.
  floor_approx = 지상 전체 층수 × 2호
  floor_ouln   = 상업용도 층수  × 2호
따라서 로드뷰에서 **상업 용도 층 수**를 세면 분모 산식을 직접 판정할 수 있다.
덤으로 STORES_PER_FLOOR=2 근사 자체의 타당성도 units_actual 로 확인한다.

표본 추출: gold/{slug}/building_vacancy.json (page_building_master 보다 최신이고
capacity_method 를 갖는다). capacity_method × status 층화.

산출: data/validation/roadview_capacity_{slug}.csv   ← 사람이 라벨 기입
      data/validation/roadview_capacity_{slug}.md    ← 카카오 로드뷰 링크 목록
채점: python -m data.validation.score_capacity_method {slug}

실행: python -m data.validation.make_capacity_sample ikseon yeonnam myeongdong
"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from data.collectors.common import GOLD, load_latest
from data.config.page_hubs import HUBS
from data.pipelines.build_page_master import _build_dong_map, _label

_OUT = Path(__file__).resolve().parent
_SEED = 42

# 층화 쿼터 — 쟁점인 floor_approx 에 표본을 몰고, expos_units 는 대조군으로 소량.
# status 를 섞는 이유: 공실 예측이 맞는 구간과 틀린 구간에서 층수 오차가 다를 수 있다.
_QUOTA = {
    ("floor_approx", "high"):    10,
    ("floor_approx", "partial"):  7,
    ("floor_approx", "full"):     5,
    ("expos_units", "high"):      4,
    ("expos_units", "partial"):   4,
}

# sigunguCd → 자치구명. 네이버 지도 검색 링크를 구까지 붙여 동명 중복을 피한다
# (예: 신사동이 강남구·은평구 양쪽에 있어 구 없이는 엉뚱한 건물이 뜬다).
_GU = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}

_FIELDS = [
    "bdMgtSn", "jibun", "name", "capacity_method", "status_predicted",
    "vacancy_predicted", "active", "capacity", "implied_floors",
    "kakao_roadview", "naver_link", "coord",
    # ── 여기부터 사람이 채우는 칸 ───────────────────────────────
    "commercial_floors_actual",   # 로드뷰에서 센 '상가로 쓰이는' 지상 층 수 (필수)
    "total_floors_actual",        # 눈으로 센 지상 총 층수 (선택 — 대장 층수 검증용)
    "units_actual",               # 셀 수 있으면 상가 호실 수 (선택 — 층당 2호 검증용)
    "label_actual",               # 공실 / 부분공실 / 영업 / 불명
    "memo",
]


def _implied_floors(row: dict) -> str:
    """floor_approx 의 capacity 는 지상층수×2 이므로 층수를 되돌릴 수 있다."""
    if row.get("capacity_method") != "floor_approx" or not row.get("capacity"):
        return ""
    return str(round(row["capacity"] / 2))


def build(slug: str) -> bool:
    src = GOLD / slug / "building_vacancy.json"
    if not src.exists():
        print(f"[capacity-sample:{slug}] building_vacancy.json 없음 — 건너뜀")
        return False
    csv_path = _OUT / f"roadview_capacity_{slug}.csv"
    if csv_path.exists():
        prev = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
        if any((r.get("label_actual") or "").strip() for r in prev):
            print(f"[capacity-sample:{slug}] ⚠ 이미 라벨이 채워진 표본이 있습니다 — "
                  f"덮어쓰지 않고 건너뜁니다 ({csv_path.name})")
            return False

    rows = json.loads(src.read_text(encoding="utf-8"))
    dong_map = _build_dong_map(load_latest(slug, "stores_raw.json") or [])
    rng = random.Random(_SEED)

    out: list[dict] = []
    shortfall: list[str] = []
    for (method, status), n in _QUOTA.items():
        pool = [r for r in rows
                if r.get("capacity_method") == method and r.get("status") == status
                and r.get("lat") and r.get("lon")]
        picked = rng.sample(pool, min(n, len(pool)))
        if len(picked) < n:
            shortfall.append(f"{method}/{status} {len(picked)}/{n}")
        for r in picked:
            gu = _GU.get(str(r.get("sigunguCd", "")), "")
            jibun = _label(r.get("lnoCd", ""), "", dong_map)
            addr = f"서울 {gu} {jibun}".replace("  ", " ").strip()
            lat, lon = r["lat"], r["lon"]
            out.append({
                "bdMgtSn": r.get("bdMgtSn", ""),
                "jibun": jibun,
                "name": r.get("name", ""),
                "capacity_method": method,
                "status_predicted": status,
                "vacancy_predicted": r.get("vacancy_bldg", ""),
                "active": r.get("active", ""),
                "capacity": r.get("capacity", ""),
                "implied_floors": _implied_floors(r),
                # 좌표 기반이라 건물 특정이 정확하고 로드뷰가 바로 열린다
                "kakao_roadview": f"https://map.kakao.com/link/roadview/{lat:.6f},{lon:.6f}",
                "naver_link": f"https://map.naver.com/p/search/{quote(addr)}",
                "coord": f"{lat:.6f},{lon:.6f}",
                "commercial_floors_actual": "", "total_floors_actual": "",
                "units_actual": "", "label_actual": "", "memo": "",
            })

    if not out:
        print(f"[capacity-sample:{slug}] 층화 조건에 맞는 건물 없음 — 건너뜀")
        return False
    rng.shuffle(out)      # 예측이 뭉치지 않게 섞어 블라인드에 가깝게

    with csv_path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=_FIELDS)
        w.writeheader()
        w.writerows(out)

    hub = HUBS[slug].name if slug in HUBS else slug
    md = [f"# capacity 방식 판정 표본 — {hub} ({slug}) {len(out)}동",
          "",
          f"라벨은 `{csv_path.name}` 에 기입합니다. 링크는 **카카오 로드뷰**(좌표 기준)라",
          "클릭하면 해당 건물 앞에서 바로 열립니다. 상호명이 아니라 좌표로 특정하므로",
          "동명 건물 혼동이 없습니다.",
          "",
          "## 무엇을 세는가 — `commercial_floors_actual` 이 핵심",
          "",
          "이 표본의 목적은 공실률 정확도가 아니라 **분모(capacity) 산식 판정**입니다.",
          "현재 두 방식이 이렇게 갈립니다:",
          "",
          "| 방식 | capacity 산식 | 현재 추정 공실 |",
          "|---|---|---|",
          "| `floor_approx` | 지상 **전체** 층수 × 2호 | 60~72% (앵커 +19~30%p) |",
          "| `floor_ouln` | **상업용도** 층수 × 2호 | 4.6% (앵커 -37.0%p) |",
          "",
          "차이는 오직 '몇 개 층을 상가로 세는가' 입니다. 그러니 로드뷰에서",
          "**상가로 쓰이는 지상 층이 몇 개인지** 세어 `commercial_floors_actual` 에 적으면",
          "어느 산식이 맞는지 바로 판정됩니다.",
          "",
          "| 칸 | 채우는 법 | 필수 |",
          "|---|---|---|",
          "| `commercial_floors_actual` | 간판·쇼윈도·층별 안내판으로 상가가 든 지상 층 수 | **필수** |",
          "| `total_floors_actual` | 눈으로 센 지상 총 층수 (대장 층수 검증) | 선택 |",
          "| `units_actual` | 상가 호실 수를 셀 수 있으면 (층당 2호 근사 검증) | 선택 |",
          "| `label_actual` | `공실` / `부분공실` / `영업` / `불명` | **필수** |",
          "",
          "주거·사무실 전용 층은 상가에서 **뺍니다**. 판정 불가면 `label_actual` 에 `불명`.",
          "",
          "## 대상 건물",
          "",
          "| # | 지번 | 예측방식 | 예측 | 공실률 | active/capacity | 추정층수 | 로드뷰 |",
          "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(out, 1):
        md.append(f"| {i} | {r['jibun']} | {r['capacity_method']} | {r['status_predicted']} "
                  f"| {r['vacancy_predicted']}% | {r['active']}/{r['capacity']} "
                  f"| {r['implied_floors'] or '—'} | [로드뷰]({r['kakao_roadview']}) |")
    (_OUT / f"roadview_capacity_{slug}.md").write_text("\n".join(md), encoding="utf-8")

    dist = Counter(r["capacity_method"] for r in out)
    print(f"[capacity-sample:{slug}] {csv_path.name} — {len(out)}동 {dict(dist)}"
          + (f" · 표본 부족: {', '.join(shortfall)}" if shortfall else ""))
    return True


def main() -> None:
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not slugs:
        print("사용법: python -m data.validation.make_capacity_sample <slug> [slug ...]")
        return
    ok = sum(1 for s in slugs if build(s))
    print(f"[capacity-sample] 생성 {ok}거점 — 라벨 기입 후 score_capacity_method 실행")


if __name__ == "__main__":
    main()
