"""[Page] 생활이동 → 유입 레이어 산출물 (gold/platform_page_migration.json).

`build_page_footfall` 과 짝이다. 그쪽은 **얼마나 있나**(체류·밀도), 이쪽은
**몇 시에 · 누가 · 어디서 왔나**(유입)를 답한다. 서빙 계층은 파케이도 CSV 도 읽지
않고 이 JSON 하나만 본다 — Vercel 서버리스에 pandas 가 없다는 §0-5 사고와 같은 조합을
다시 만들지 않기 위해서다.

입력: bronze/{slug}/{날짜}/living_migration.json (collectors/living_migration 산출)
출력: gold/platform_page_migration.json

## 무엇이 실측이고 무엇이 근사인가

- **실측**: 도착 행정동 단위의 시간대·성연령·이동유형·출발지 구성.
- **근사**: 거점 **안에서의** 분포. 원천이 행정동 집계라 거점 내부는 모른다.
  거점이 행정동 여러 개에 걸리면 `silver/hub_adong.json` 의 **상업 연면적 가중**으로
  섞는다. 응답의 `resolution: "adong"` 이 이 사실을 밝힌다 — 밝히지 않으면
  건물 단위 실측처럼 읽힌다.

실행: python -m data.pipelines.build_page_migration
"""
from __future__ import annotations

import json
from collections import defaultdict

from data.collectors.common import GOLD, load_latest
from data.config.page_hubs import HUBS
from data.pipelines.build_hub_adong import load as load_hub_adong

_OUT = GOLD / "platform_page_migration.json"

HOURS = [f"{h:02d}" for h in range(24)]


def _share(d: dict[str, float]) -> dict[str, float]:
    """구성비. 합이 0 이면 빈 dict — 0 으로 채우면 '사람이 없다'는 거짓이 된다."""
    tot = sum(d.values())
    return {k: round(v / tot, 6) for k, v in d.items()} if tot > 0 else {}


def _peak(by_hour: dict[str, float]) -> dict | None:
    """최번시 — 슬라이더 기본값과 카드 문구가 쓴다."""
    if not by_hour:
        return None
    h, v = max(by_hour.items(), key=lambda kv: kv[1])
    tot = sum(by_hour.values())
    return {"hour": h, "pop": round(v, 1),
            "share": round(v / tot, 4) if tot else None}


def run() -> dict:
    hub_adong = load_hub_adong()
    districts: dict[str, dict] = {}
    skipped: list[str] = []

    for slug in HUBS:
        doc = load_latest(slug, "living_migration.json")
        if not doc:
            skipped.append(slug)
            continue

        by_hour = {h: float(doc.get("by_hour", {}).get(h, 0.0)) for h in HOURS}
        # 원천의 시간 표기가 "0"/"00" 로 갈리는 배포분이 있어 양쪽을 합친다.
        for k, v in (doc.get("by_hour") or {}).items():
            ks = str(k).strip()
            if ks.isdigit() and f"{int(ks):02d}" in by_hour and ks not in HOURS:
                by_hour[f"{int(ks):02d}"] += float(v)

        adong = hub_adong.get(slug) or {}
        districts[slug] = {
            "ym": doc.get("ym"),
            "pop_total": doc.get("pop_total"),
            "avg_move_min": doc.get("avg_move_min"),
            "masked_rows": doc.get("masked_rows"),
            "by_hour": {h: round(v, 1) for h, v in by_hour.items()},
            "hour_share": _share(by_hour),
            "peak": _peak(by_hour),
            "purpose_share": _share({k: float(v) for k, v in
                                     (doc.get("by_purpose") or {}).items()}),
            "sex_age_share": _share({k: float(v) for k, v in
                                     (doc.get("by_sex_age") or {}).items()}),
            "origin_top": doc.get("origin_top"),
            "origin_other": doc.get("origin_other"),
            # 이 거점이 어느 행정동을 얼마나 차지하는가 — 근사의 근거를 함께 싣는다.
            "adong": {cd: {"nm": v.get("adm_nm"), "w": v.get("weight"),
                           "basis": v.get("weight_basis")}
                      for cd, v in adong.items()},
        }

    doc = {
        "source": "서울시×KT 수도권 생활이동(data.seoul.go.kr OA-22300 계열)",
        "built_from": "bronze/{slug}/*/living_migration.json + silver/hub_adong.json",
        "resolution": "adong",
        "hours": HOURS,
        "note": ("값은 **도착 행정동 단위 집계**다. 거점 내부 분포는 알 수 없으므로 "
                 "거점이 여러 행정동에 걸치면 상업 연면적 가중으로 섞는다 — 건물 단위 "
                 "실측이 아니다. 행안부 「지역별 인구이동 현황」(주민등록 전입신고, 월 단위 "
                 "거주지 이전)과는 다른 데이터다."),
        "districts": districts,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"→ {_OUT.name}  ({_OUT.stat().st_size/1024:.0f}KB)")
    print(f"   거점 {len(districts)}/{len(HUBS)}")
    if skipped:
        print(f"   생활이동 미수집 {len(skipped)}거점: {', '.join(skipped[:6])}"
              f"{' …' if len(skipped) > 6 else ''}")
        print("   → python -m data.collectors.living_migration <파일디렉터리>")
    return doc


if __name__ == "__main__":
    run()
