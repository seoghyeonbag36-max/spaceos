"""α보정 — 건물 추정 공실률을 부동산원 공식 통계에 스케일 정렬 (poc §3-1).

앵커는 **거점별 R-ONE 실측치**를 쓴다(2026-07-28 교정). 이전에는 전 거점에 단일
상수 41.6% 를 적용했는데, 두 가지가 틀렸다:

  1) 41.6% 는 부동산원 통계가 아니다. poc-building-vacancy.md §0.5 의 가로수길
     **가두 1층 실태조사**(2024, 언론 인용) 값인데 코드 주석이 "부동산원 가두상권
     공실률" 로 잘못 달려 있었다. 같은 상권의 실제 R-ONE 값은 신사역 중대형
     **17.6%**(2026Q1)다 — 24%p 차이다.
  2) 가로수길 전용 값을 13거점 전부에 썼다. 압구정 7.8%, 연남 4.5%, 명동 5.0%
     인 상권까지 41.6% 에 정렬시키면 α 가 거점별로 최대 5배 어긋난다.

R-ONE 원본은 collectors/rone_rent.py 가 이미 bronze/platform13/{날짜}/rone_vac_*.json
에 받아 두었다(13거점 전 분기). 여기서 최신 분기를 읽어 거점별 앵커로 쓴다.
중대형(vac_mid)을 주 앵커로 삼는다 — 13거점 전부 비영(非零) 값이 있는 유일한 계열이다.
소규모(vac_small)는 표본이 없는 거점이 0.0 으로 내려와 α 를 발산시킨다(참고로만 기록).

방법(v1): 매칭건물(stores+ledger) 집계 공실률 대비 거점 앵커의 비율 α를 산출해
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
from functools import lru_cache

from data.collectors.common import GOLD, load_latest
from data.config.page_hubs import HUBS
from data.config.rone_districts import DISTRICT_RONE
from data.pipelines.build_building_attrs import load as load_attrs

# 폴백 앵커 — R-ONE 원본을 못 읽을 때만 쓴다. 전국 상권 중위 수준의 보수값이며
# 특정 상권을 대표하지 않는다(과거의 41.6% 처럼 특정 거점 값을 전 거점에 퍼뜨리지 않기 위해).
ANCHOR_FALLBACK = 10.0

# 가로수길 가두 1층 실태조사(2024) — **부동산원 통계가 아니다.** PoC 거점 선정 근거
# (poc §0.5)로 남기되 α 산출에는 쓰지 않는다. 측정 대상(메인도로 1층 점포)과
# 우리 지표(건물 전체 상가 호수)의 모집단이 다르기 때문이다.
REF_GAROSU_STREET_2024 = 41.6

# R-ONE 상권이 없는 거점을 위한 하위호환 상수 — 이전 ANCHOR_MALL.
ANCHOR_MALL = 9.99     # 부동산원 신사역 집합상가 공실률 (%)

_RONE_SLUG = "platform13"      # rone_rent.py 가 13거점 R-ONE 시계열을 여기 저장한다


@lru_cache(maxsize=None)
def _rone_latest(kind: str) -> dict[str, float]:
    """bronze 의 R-ONE 공실률 최신 분기 → {district_id: %}.

    kind: "vac_mid"(중대형) | "vac_small"(소규모).
    """
    rows = load_latest(_RONE_SLUG, f"rone_{kind}.json") or []
    if not rows:
        return {}
    latest = max(r["quarter"] for r in rows)
    return {r["district_id"]: float(r["value"])
            for r in rows if r["quarter"] == latest and r.get("value") is not None}


def anchor_of(slug: str) -> float:
    """거점의 R-ONE 중대형 공실률(%). 값이 없거나 0 이면 폴백."""
    return _rone_latest("vac_mid").get(slug) or ANCHOR_FALLBACK

# capacity_method → 세그먼트: 전유부 호수 실측 = 집합건물, 층수 기반 = 일반(가두)
_SEGMENT_OF = {"expos_units": "mall", "floor_approx": "street", "floor_ouln": "street"}

# methods(v3) 용 대상 — capacity 근거가 있는 방법만. 앵커는 거점별 R-ONE 값을 공유한다.
# (이전에는 방법별로 다른 상수 앵커를 붙였으나, 그 상수들이 특정 거점 값이라 다른
#  거점에서는 오히려 α 를 왜곡했다. 방법별 편향은 α 가 아니라 `gap_pp` 로 드러난다.)
_METHODS = ("expos_units", "floor_ouln", "floor_approx")


def _agg(rows: list[dict], keys: set[str], anchor: float | None = None) -> dict | None:
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
    out = {"estimated_vacancy_pct": est, "buildings": n}
    if anchor is not None:
        out |= {"anchor_pct": round(anchor, 2),
                "alpha": round(anchor / est, 3) if est else None,
                "gap_pp": round(est - anchor, 1)}
    return out


def _methods(rows: list[dict], anchor: float) -> dict:
    """capacity_method 별 α (v3) — 거점별 보정의 권장 소스."""
    present = {r.get("capacity_method") for r in rows} & set(_METHODS)
    return {m: a for m in sorted(present) if (a := _agg(rows, {m}, anchor)) is not None}


def _segments(rows: list[dict], anchor: float) -> dict:
    """building_vacancy.json 을 가두/집합으로 분리 집계해 세그먼트별 α 산출."""
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
    for seg in ("street", "mall"):
        a = agg[seg]
        if not a["capacity"]:
            continue
        est = round((1 - a["active"] / a["capacity"]) * 100, 1)
        out[seg] = {
            "estimated_vacancy_pct": est,
            "anchor_pct": round(anchor, 2),
            "alpha": round(anchor / est, 3) if est else None,
            "gap_pp": round(est - anchor, 1),
            "buildings": a["buildings"],
        }
    return out


def _rone_aligned(rows: list[dict], attrs: dict, anchor_mid: float,
                  anchor_small: float | None) -> dict:
    """R-ONE 과 **같은 모집단·단위**로 잰 공실률 (2026-08-01, docs/finding-anchor-population.md).

    R-ONE 중대형은 ① 면적 기준(공실면적/임대가능면적) ② 일반건축물 중 3층 이상 또는
    연면적 330㎡ 초과 ③ 표본(전국 5,761동, 상권당 약 16동)이다. 집합상가는 **별도 계열**
    이라 중대형 앵커에 넣으면 안 된다 — 13거점 집합 755동의 공실률이 72.7%로 대표값을
    통째로 끌어올리고 있었다.

    분자는 층 단위다(recalc_floor_ouln 이 넣은 active_floors_lo/hi). 상가정보 flrNo
    공란이 약 30% 라 단일 값이 될 수 없어 **밴드**로 낸다 — 하한은 공란을 전부 공실로,
    상한은 빈 층에 낮은 층부터 배정한다. 대표값은 면적가중 상한이다.
    """
    per: dict[str, dict] = {}
    for r in rows:
        if not r.get("capacity"):
            continue
        pnu = r.get("lnoCd", "")
        at = attrs.get(pnu, {})
        seg = ("mall" if r.get("capacity_method") == "expos_units" or at.get("is_mall")
               else at.get("rone_size") if at.get("is_shop") else None)
        if seg is None:
            continue
        # capacity·층 지표는 지번당 산출물이라 동(bdMgtSn)별로 합산하면 안 된다.
        prev = per.get(pnu)
        if prev and prev["cap"] >= r["capacity"]:
            prev["stores"] += r.get("active", 0)
            continue
        per[pnu] = {"seg": seg, "cap": r["capacity"],
                    "lo": r.get("active_floors_lo"), "hi": r.get("active_floors_hi"),
                    "stores": (prev["stores"] if prev else 0) + r.get("active", 0),
                    "area": at.get("com_area_flr") or at.get("com_area") or 0.0}

    out: dict = {}
    for seg, anchor in (("mid", anchor_mid), ("small", anchor_small), ("mall", None)):
        items = [d for d in per.values() if d["seg"] == seg]
        cap = sum(d["cap"] for d in items)
        if not cap:
            continue
        has_floor = [d for d in items if d["hi"] is not None]
        cap_f = sum(d["cap"] for d in has_floor)
        blk: dict = {"buildings": len(items),
                     # 호실(점포 수) 기준 — 하위호환 비교용. 분자·분모 단위가 달라
                     # 건물별 클램프가 필요하다.
                     "vacancy_units_pct": round(
                         (1 - sum(min(d["stores"], d["cap"]) for d in items) / cap) * 100, 1)}
        if cap_f:
            lo = sum(d["lo"] for d in has_floor)
            hi = sum(d["hi"] for d in has_floor)
            area = sum(d["area"] for d in has_floor if d["area"])
            blk |= {
                "buildings_floor": len(has_floor),
                "vacancy_floor_hi_pct": round((1 - hi / cap_f) * 100, 1),   # 낙관(상한 점유)
                "vacancy_floor_lo_pct": round((1 - lo / cap_f) * 100, 1),   # 비관(하한 점유)
                "vacancy_area_pct": round(
                    sum((1 - d["hi"] / d["cap"]) * d["area"] for d in has_floor if d["area"])
                    / area * 100, 1) if area else None,
            }
        if anchor:
            rep = blk.get("vacancy_area_pct") or blk.get("vacancy_floor_hi_pct")
            blk |= {"anchor_pct": round(anchor, 2),
                    "gap_pp": round(rep - anchor, 1) if rep is not None else None}
        out[seg] = blk
    out["note"] = ("R-ONE 정렬 지표(2026-08-01). mid=중대형 앵커 대조 대상"
                   "(일반건축물·상가 주용도·3층 이상 또는 330㎡ 초과), small=소규모 앵커, "
                   "mall=집합건축물(**중대형 앵커 대조 금지** — R-ONE 집합상가는 별도 계열). "
                   "대표값 = vacancy_area_pct(면적가중·층 점유 상한). 층 밴드는 상가정보 "
                   "flrNo 공란 약 30% 에서 오는 불확실성이며 lo/hi 사이가 참값 구간이다.")
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

    anchor = anchor_of(slug)
    out: dict = {
        "anchor_pct": round(anchor, 2),
        "anchor_source": ("R-ONE 중대형상가 공실률 (최신 분기) — "
                          f"{DISTRICT_RONE.get(slug, '매핑 없음')}"),
        "anchor_vac_small_pct": _rone_latest("vac_small").get(slug),
        "ref_garosu_street_2024_pct": REF_GAROSU_STREET_2024 if slug == "garosugil" else None,
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
                "alpha_street": round(anchor / est, 3) if est else None,
                "gap_pp": round(est - anchor, 1),
                "buildings_used": len(known),
            }
            print(f"[calibrate:{slug}] combined: 추정 {est}% vs 앵커 "
                  f"{anchor:.1f}% → gap {out['gap_pp']}%p, α={out['alpha_street']}")
    else:
        print(f"[calibrate:{slug}] page_building_master 없음 — combined 생략"
              f"(segments/methods 만 산출)")

    segments = _segments(rows, anchor)
    methods = _methods(rows, anchor)
    # primary(v4) = 분모 근거가 정밀한 방법만 (전유부 실측 + 층별개요). floor_approx
    # (지상 **전체** 층수 × 2호)는 주거·사무 층까지 상가로 세어 분모를 부풀리므로
    # 대표값에서 뺀다. 이걸 섞어 두면 "그 거점 건물 중 몇 %가 어느 방법을 받았는가"
    # 라는 수집 이력이 지표를 움직인다 — 2026-07-27 garosugil 이 그렇게 39.1%→56.0%
    # 로 뛰었다(기존 건물은 단 한 동도 안 변했는데 신규 304동이 전부 floor_approx).
    primary = _agg(rows, {"expos_units", "floor_ouln"}, anchor)
    if primary is not None:
        gross = sum(1 for r in rows if r.get("capacity_method") in _METHODS)
        primary["coverage_pct"] = round(primary["buildings"] / gross * 100, 1) if gross else None
        primary["excluded_floor_approx"] = sum(
            1 for r in rows if r.get("capacity_method") == "floor_approx")
    aligned = _rone_aligned(rows, load_attrs(slug), anchor,
                            _rone_latest("vac_small").get(slug))
    out |= {
        "rone_aligned": aligned,
        "primary": primary,
        "segments": segments,
        "methods": methods,
        "note": "⚠ 대표값은 2026-08-01부터 **rone_aligned** 다(R-ONE 과 같은 모집단·단위). "
                "아래 primary/segments/methods 는 하위호환용이며 집합건물이 섞여 있어 "
                "앵커 대조에 쓰면 과대추정된다. primary(v4) = 구 대표값. capacity 근거가 정밀한 expos_units(전유부 실측) "
                "+ floor_ouln(층별개요 상업층) 만 집계한다. floor_approx 는 분모 과대 편향이 "
                "커서 제외하며, coverage_pct 가 낮으면 그 거점은 floor_capacity 수집이 "
                "덜 된 상태다(대표값을 신뢰하기 전에 채울 것). "
                "combined(v1) = 방법 혼합 — 하위호환용이며 방법 구성비에 흔들리므로 "
                "앵커 비교에 쓰지 말 것. segments(v2) = 가두/집합 분리. "
                "methods(v3) = capacity_method 단위. 앵커는 거점별 R-ONE 중대형 공실률이다 "
                "(2026-07-28 이전의 전 거점 공통 41.6% 는 가로수길 가두 1층 실태조사 값을 "
                "부동산원 통계로 잘못 표기한 것이라 폐기). "
                "⚠ 알려진 한계: expos_units(집합건물) 세그먼트는 **분자**가 구조적으로 "
                "부족하다 — 상가정보가 대형 집합상가 내부 점포를 그 건물의 bdMgtSn 으로 "
                "귀속시키지 못한다. 11거점 실측(2026-07-28) 결과 floor_ouln 의 앵커 격차는 "
                "+4~+19%p 인데 expos_units 는 +21~+72%p 로 갈린다(예: 익선 피카디리플러스 "
                "capacity 1,031 / active 57). 집합건물 공실률은 아직 신뢰 구간 밖이며, "
                "층·호 단위 매칭(flrNo/hoNo) 을 붙이기 전까지 단독 인용하지 말 것.",
    }
    dst = GOLD / slug / "calibration.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    mid = aligned.get("mid") or {}
    if mid:
        # gap_pp 는 면적 기준 공실률이 있어야 나온다 — 없는 거점이 있다(2026-08-16 실측:
        # 08-16 승격 9거점). 예전에는 `{...:+}` 로 바로 포맷해 **로그 한 줄이 파이프라인을
        # 통째로 세웠다**. calibration.json 은 이미 쓰인 뒤라 첫 거점만 산출되고 나머지가
        # 조용히 빠졌다. 값이 없으면 없다고 찍고 넘어간다.
        gap = mid.get("gap_pp")
        gap_s = f"{gap:+}%p" if isinstance(gap, (int, float)) else "gap 산출 불가(면적 기준 결측)"
        print(f"[calibrate:{slug}] rone_aligned(mid): 면적 "
              f"{mid.get('vacancy_area_pct')}% · 층 "
              f"{mid.get('vacancy_floor_hi_pct')}~{mid.get('vacancy_floor_lo_pct')}% · "
              f"호실 {mid.get('vacancy_units_pct')}% vs 앵커 {mid.get('anchor_pct')}% "
              f"→ {gap_s} ({mid['buildings']}동)")
    if primary is not None:
        print(f"[calibrate:{slug}] primary: 추정 {primary['estimated_vacancy_pct']:5.1f}% "
              f"vs 앵커 {anchor:5.2f}% → gap {primary['gap_pp']:+6.1f}%p, "
              f"α={primary['alpha']} ({primary['buildings']}동, "
              f"커버리지 {primary['coverage_pct']}%)")
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
