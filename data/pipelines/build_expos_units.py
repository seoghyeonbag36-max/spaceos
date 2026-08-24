"""[Posting] 전유부 **유닛별 실면적** 사이드카 (silver/{거점}/expos_units.json).

## 왜 필요한가

`vacant_units.json` 의 `area` 는 **건축물대장 상업면적 ÷ capacity** 다. 건물 단위는
실측이지만 건물 **안** 유닛들은 균등분할이라, 유닛 하나의 면적은 사실상 추정이다.

그게 얼마나 큰 근사인지 실측했다(2026-08-24, 가로수길 대장 33MB):
한 건물 안 상업 전유 유닛의 면적이 **19.6 ~ 45.1배** 벌어진다.

    1168010700105010000: 유닛 47 · min 9.9 / 중앙 127.3 / max 445.2 m2 → 45.1배

즉 균등분할은 "조금 거친 값" 이 아니라 **개별 유닛에 대해서는 크게 틀린 값**이다.
그런데 진짜 값이 이미 저장소 안에 있었다 — `build_building_attrs.fold_ledger` 가
전유 행마다 `area` 를 읽는데 **합계로 접고 개별 값을 버린다**(같은 파일 119행).
이 파이프라인은 그 개별 값을 남긴다.

## 무엇을 남기고 무엇을 남기지 않나

남기는 것: 지번(PNU) → 상업 전유 유닛 목록 `[{flr, ho, area_m2}]` + 층별 요약.
**남기지 않는 것: 어느 유닛이 어느 공실인지.** 대장 전유 호(`hoNm`)와 우리 인벤토리의
유닛은 서로 다른 식별체계이고, 붙이는 규칙(층 중앙값? 건물 중앙값? 호 매칭?)은
**제품 판단**이다. 추출은 기계적이지만 배정은 아니라서, 여기서는 재료만 만든다.

⚠ 필터는 `build_building_attrs` 와 **같은 규칙**을 쓴다(`exposPubuseGbCdNm == "전유"`
  + `is_commancial` 네거티브 필터). 규칙을 여기 옮겨 적지 않고 그 모듈에서 가져온다 —
  한쪽만 고쳐지면 상업면적 합계와 유닛 목록이 조용히 어긋난다.

⚠ 대장 원본은 거점당 최대 85MB 이고 이 환경은 메모리가 빡빡하다. `stream_rows` 로
  행 하나씩 흘려 받는다(indent 6 — 층별개요의 4 와 다르다. 4 로 부르면 **한 행도
  못 읽으면서 오류도 안 난다**: 2026-08-24 실제로 밟았다).

실행: python -m data.pipelines.build_expos_units [거점 ...]
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from data.collectors.common import BRONZE, SILVER
from data.config.page_hubs import HUBS
from data.pipelines.build_building_attrs import is_commercial, stream_rows

_ITEM_INDENT = 6          # 대장(bldg_ledger_raw.json) 전용. 층별개요는 4.
FILENAME = "expos_units.json"


def _floor_label(nm: object) -> str:
    """`flrNoNm` 원문을 그대로 쓴다 — '지2층'/'지하1층'/'9' 가 섞여 있다.

    정규화하지 않는 이유: 배정 규칙을 정할 때 어떤 표기가 얼마나 섞였는지 보이는 편이
    낫다. 여기서 접으면 그 정보가 사라지고, 접는 규칙 자체가 또 하나의 추정이 된다.
    """
    return str(nm or "").strip()


def collect_hub(slug: str) -> dict:
    """거점 하나의 전유 유닛 목록. 날짜별 체크포인트 중 **더 많이 담긴 쪽**을 남긴다."""
    per_pnu: dict[str, list[dict]] = {}
    for p in sorted((BRONZE / slug).glob("*/bldg_ledger_raw.json")):
        cur: dict[str, list[dict]] = {}
        for pnu, lst, row in stream_rows(p, _ITEM_INDENT):
            if row is None or lst != "expos":
                continue
            if row.get("exposPubuseGbCdNm") != "전유":
                continue
            if not is_commercial(row.get("mainPurpsCdNm")):
                continue
            try:
                area = float(row.get("area") or 0)
            except (TypeError, ValueError):
                continue
            if area <= 0:
                continue
            cur.setdefault(str(pnu), []).append({
                "flr": _floor_label(row.get("flrNoNm")),
                "ho": str(row.get("hoNm") or "").strip(),
                "area_m2": round(area, 2),
                "purps": str(row.get("mainPurpsCdNm") or "").strip(),
            })
        # 빈 체크포인트가 나중 날짜라는 이유로 채워진 것을 덮어쓰면 안 된다.
        for pnu, units in cur.items():
            if len(units) >= len(per_pnu.get(pnu, [])):
                per_pnu[pnu] = units
    return per_pnu


def _summarise(units: list[dict]) -> dict:
    ar = [u["area_m2"] for u in units]
    by_flr: dict[str, list[float]] = {}
    for u in units:
        by_flr.setdefault(u["flr"], []).append(u["area_m2"])
    return {
        "n": len(ar),
        "min_m2": round(min(ar), 1), "max_m2": round(max(ar), 1),
        "median_m2": round(statistics.median(ar), 1),
        # 균등분할이 얼마나 틀린지 한 눈에 보이는 수 — 1 에 가까우면 균등분할이 무해하다.
        "spread_ratio": round(max(ar) / min(ar), 1) if min(ar) > 0 else None,
        "by_floor_median_m2": {k: round(statistics.median(v), 1)
                               for k, v in sorted(by_flr.items())},
        "by_floor_n": {k: len(v) for k, v in sorted(by_flr.items())},
    }


def run(slugs: list[str]) -> dict:
    totals = {"hubs": 0, "pnu": 0, "units": 0, "spreads": []}
    for slug in slugs:
        if not (BRONZE / slug).exists():
            print(f"  {slug}: bronze 없음 — 건너뜀")
            continue
        per_pnu = collect_hub(slug)
        if not per_pnu:
            print(f"  {slug}: 상업 전유 유닛 0 — 대장 원본이 비었다(수집 필요)")
            continue
        doc = {
            "source": "건축물대장 전유부(expos) — exposPubuseGbCdNm='전유' + 상업용도",
            "built_from": f"bronze/{slug}/*/bldg_ledger_raw.json",
            "filter": ("build_building_attrs.is_commercial 과 동일 규칙 — 상업면적 "
                       "합계(com_area)와 같은 모집단이어야 한다"),
            "note": ("유닛별 **실면적**이다. 다만 이 호(hoNm)가 우리 인벤토리의 어느 "
                     "공실 유닛인지는 여기서 정하지 않는다 — 식별체계가 달라서 배정 "
                     "규칙이 필요하고, 그것은 제품 판단이다."),
            "pnu": {k: {"units": v, **_summarise(v)}
                    for k, v in sorted(per_pnu.items())},
        }
        dst = SILVER / slug / FILENAME
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

        n_u = sum(len(v) for v in per_pnu.values())
        spreads = [doc["pnu"][k]["spread_ratio"] for k in doc["pnu"]
                   if doc["pnu"][k]["spread_ratio"]]
        totals["hubs"] += 1
        totals["pnu"] += len(per_pnu)
        totals["units"] += n_u
        totals["spreads"] += spreads
        med = round(statistics.median(spreads), 1) if spreads else None
        print(f"  {slug}: 지번 {len(per_pnu)} · 유닛 {n_u} · 면적편차 중앙 {med}배 "
              f"→ silver/{slug}/{FILENAME}")

    sp = totals["spreads"]
    if sp:
        print(f"\n합계: 거점 {totals['hubs']} · 지번 {totals['pnu']} · "
              f"유닛 {totals['units']}")
        print(f"건물 내 면적편차(max/min) 중앙 {statistics.median(sp):.1f}배 · "
              f"상위10% {sorted(sp)[int(len(sp) * 0.9)]:.1f}배 — "
              f"균등분할이 개별 유닛에 대해 얼마나 틀린지를 나타낸다")
    return totals


def load(slug: str) -> dict:
    """소비처용 로더 — {pnu: {units, n, median_m2, ...}}. 없으면 빈 dict."""
    p = SILVER / slug / FILENAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("pnu") or {}
    except (OSError, ValueError):
        return {}


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    run([s for s in (argv or list(HUBS)) if s in HUBS])
