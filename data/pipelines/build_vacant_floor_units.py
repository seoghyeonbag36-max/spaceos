"""[Page·Posting] 층 단위 공실 매물 인벤토리 — gold/{slug}/vacant_floor_units.json.

`build_vacant_units` 와 **다른 것을 센다.** 둘의 차이를 먼저 적는다 — 이름이 비슷해
같은 것으로 읽히면 §0-Q 를 다시 밟는다.

| | `vacant_units.json` | `vacant_floor_units.json`(여기) |
|---|---|---|
| 단위 | 건물 1동 = 유닛 1개 | **(건물, 층)** = 유닛 1개 |
| 대상 | 통째로 빈 건물(`empty`·`high`) | **빈 층이 있는 모든 건물** — `partial` 포함 |
| 면적 | 상업면적 ÷ 호실 수(균등분할) | 그 **층의** 층별개요 실측 면적 |
| 쓰임 | 3-Tier ROI 모델의 **표본** | 화면에 거는 **매물 목록** |

## 왜 기존 산출물을 고치지 않았나 (2026-09-05)

`vacant_units.json` 을 층 단위로 쪼개는 것은 **2026-08-26 에 이미 해 봤고 되돌렸다**
(docs/feature-posting.md §0-Q · reports/unit_floor_split_probe_2026-08-26.json).
데이터가 없어서가 아니다 — 528 → 2,201 유닛으로 잘 쪼개졌고 마진도 KOSIS 대역 안에
남았다. 걸린 것은 사전등록 트립와이어 둘이었다:

    프라임 프리미엄  +0.058pp → **−1.343pp** (부호 역전)
    factory 승       +1.002pp → **−0.045pp** (부호 역전)

메커니즘은 분명하다. 층마다 유닛을 내면 **중앙값 유닛이 상층부로 올라가** 임대료
부담이 서울 평균 아래로 내려간다. 그 트립와이어는 "우리 인벤토리의 임대료 부담이
서울 평균보다 높다"를 재는 것이라, 상층부 공실이 표본에 들어오면 정의상 깨진다.

이 산출물은 그 트립와이어가 재는 것을 **재지 않는다.** 여기 실리는 건 ROI 모델의
표본이 아니라 "몇 층이 비었고 그 층이 몇 평인가"라는 매물 목록이다. 그래서 기존
파일을 갈아엎지 않고 **따로 낸다** — 임계값을 건드려 통과시키지 않으려는 것이고,
두 산출물을 하나로 합칠지는 ROI 표본의 정의 문제라 아직 열려 있다(→ §0-Q).

## 확정과 추정을 가른다

빈 층을 세는 규칙은 `build_page_master._aggregate` 와 **같다**. 규칙이 갈라지면 Page
와 이 목록이 같은 건물을 두고 서로 다른 층을 비었다고 말한다.

    빈 층 후보 = com_floors − occ_floors        (상업층 중 점포·인허가로 확인 안 된 층)
    확정(confirmed) = 후보에서 **층 미상 점포를 낮은 층부터 앉히고 남은** 층
    추정(probable)  = 그 배정에 먹힌 층 — 층 미상 점포가 다른 층에 있다면 이쪽도 빈다

괄호의 원인은 상가정보 `flrNo` 공란(약 30%)이다. 한 값으로 뭉개지 않고 `certainty`
로 드러낸다 — 추정 층을 확정처럼 그리면 "실측처럼 보이는 추정치"가 된다.

## 면적은 균등분할이 아니다

`vacant_units` 의 `area` 는 건물 상업면적 ÷ 호실 수라 **같은 건물의 두 유닛이 항상
같은 면적**이었다(그래서 '유닛 면적 입도' 게이트가 0.5 에 묶여 있다). 여기서는 그
층의 층별개요 면적을 그대로 쓴다. capacity 규약이 `STORES_PER_FLOOR=1`(층 수 = 호 수)
이라 층 하나가 곧 유닛 하나이고, 단위가 어긋나지 않는다.
⚠ 한 층에 실제로 여러 호실이 있는 건물에서는 이 값이 **그 층 전체**의 면적이다.
호실 단위로 더 내려가려면 전유부(집합건물 전용)가 필요한데, 어느 호가 비었는지는
어떤 소스에도 없다(docs/feature-posting.md §0-R·§0-S).

## 층 주용도를 같이 싣는 이유

`purps` 는 건축물대장이 그 층에 허용한 용도다(소매점·일반음식점·학원·의원 …).
업종 추천을 "자리(좌표)"가 아니라 "매물(층·면적·용도)" 기준으로 거르는 근거이고,
학습 없이 규칙만으로 후보를 좁힐 수 있는 유일한 실측 축이다.

실행: python -m data.pipelines.build_vacant_floor_units [거점 ...]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from data.collectors.building_vacancy import NON_CAPACITY_PURPS
from data.collectors.common import BRONZE, GOLD
from data.config.page_hubs import ACTIVE_HUBS, get_hub

_M2_PER_PYEONG = 3.3058

# 분모(capacity) 근거가 정밀한 방법만 — build_vacant_units 와 같은 기준이다.
_COUNTED_METHODS = {"floor_ouln"}
# 점포 매칭이 있는 건물만. polygon_only 는 active=0 이라 '공실'이 자동 성립한다.
_COUNTED_SOURCE_PREFIX = "stores+ledger"

# 이 밖의 면적은 3-Tier 계산이 의미를 잃는다(창고·대형 집합상가 등).
_MIN_PYEONG, _MAX_PYEONG = 5, 200


def _load_floor_rows(slug: str) -> dict[str, list[dict]]:
    """층별개요 원본(bronze bldg_flr_raw)을 날짜 오름차순 병합 — 최신이 이긴다."""
    merged: dict[str, list[dict]] = {}
    for p in sorted(BRONZE.glob(f"{slug}/*/bldg_flr_raw.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            merged.update(d)
    return merged


def _by_floor(rows: list[dict]) -> dict[int, dict]:
    """지상 상업층 → `{면적㎡, 주용도}`.

    negative 필터는 `floor_capacity.commercial_floor_nos` 와 **같다**. 층 집합이
    갈라지면 분모(capacity)와 이 목록이 서로 다른 건물을 가리키게 된다.
    한 층에 행이 여럿이면 면적은 더하고, 주용도는 **면적이 가장 큰 행**의 것을 쓴다
    (첫 행을 쓰면 부속 용도가 대표로 올라간다).
    """
    out: dict[int, dict] = {}
    for r in rows:
        if str(r.get("flrGbCdNm", "")) not in ("지상", ""):
            continue
        purps = str(r.get("mainPurpsCdNm") or "")
        if any(x in purps for x in NON_CAPACITY_PURPS):
            continue
        no = int(r.get("flrNo") or 0)
        if no <= 0:
            continue
        area = float(r.get("area") or 0.0)
        cur = out.setdefault(no, {"area": 0.0, "purps": "", "_top": -1.0})
        cur["area"] += area
        if area > cur["_top"]:
            cur["_top"], cur["purps"] = area, purps
    for v in out.values():
        v.pop("_top", None)
    return out


def _units_for(slug: str) -> list[dict]:
    master = GOLD / slug / "page_building_master.geojson"
    if not master.exists():
        return []
    flr_rows = _load_floor_rows(slug)
    if not flr_rows:
        return []

    fc = json.loads(master.read_text(encoding="utf-8"))

    # ── 지번(pnu) 단위로 접는다 ──────────────────────────────────────────────
    # 층 근거(com_floors·occ_floors·capacity)는 Page 마스터가 **지번당** 산출한다
    # ("같은 지번 여러 동을 합산하지 않는다" — build_page_master._aggregate).
    # 그래서 한 지번에 동이 여럿이면 모든 동이 **같은 층 집합**을 들고 있고, 동마다
    # 유닛을 내면 같은 층이 동 수만큼 복제된다(실측: 가로수길 중앙엠앤비사옥 1F 가
    # 156평짜리로 두 번 나왔다). 대표 1동만 남긴다 — 지상층수가 가장 큰 동을 고르고
    # (0/누락 동이 대표가 되면 bld_floors 가 0 으로 나간다) 몇 동인지는 실어 보낸다.
    # ⚠ 그 대신 "이 빈 층이 어느 동인가"는 말할 수 없다. 층 근거가 지번 단위라서다.
    by_pnu: dict[str, list[dict]] = {}
    for feat in fc["features"]:
        p = feat["properties"]
        if p.get("capacity_method") not in _COUNTED_METHODS:
            continue
        if not str(p.get("source") or "").startswith(_COUNTED_SOURCE_PREFIX):
            continue
        # 만실 건물은 뺀다. 상한 배정에서 상업층이 전부 찬 것으로 판정된 건물이라,
        # 여기에 '추정 공실층'을 실으면 목록이 우리 자신의 status 와 어긋난 말을 한다.
        if p.get("status") == "full":
            continue
        if not (p.get("com_floors") or []):
            continue
        by_pnu.setdefault(str(p.get("pnu") or ""), []).append(feat)

    out: list[dict] = []
    for pnu, feats in by_pnu.items():
        feat = max(feats, key=lambda f: f["properties"].get("floors") or 0)
        p = feat["properties"]
        com = sorted(p.get("com_floors") or [])

        occ = {int(f) for f in (p.get("occ_floors") or [])}
        unknown_n = int(p.get("unknown_n") or 0)
        cand = [f for f in com if f not in occ]
        if not cand:
            continue
        # 층 미상 점포를 **낮은 층부터** 앉힌다 — build_page_master._aggregate 의
        # 상한 계산과 같은 규칙이다. 남은 것이 확정, 먹힌 것이 추정.
        probable, confirmed = cand[:unknown_n], cand[unknown_n:]

        by_flr = _by_floor(flr_rows.get(pnu) or [])
        if not by_flr:
            continue                       # 면적을 가정하지 않는다

        ring = feat["geometry"]["coordinates"][0]
        pts = ring[:-1] if len(ring) > 2 and ring[0] == ring[-1] else ring
        lat = round(sum(q[1] for q in pts) / len(pts), 6)
        lng = round(sum(q[0] for q in pts) / len(pts), 6)
        name = p.get("name") or "(이름 미상)"

        for certainty, floors in (("confirmed", confirmed), ("probable", probable)):
            for fl in floors:
                info = by_flr.get(fl)
                if not info or info["area"] <= 0:
                    continue               # 그 층의 대장 면적이 없다 → 뺀다
                area_pyeong = round(info["area"] / _M2_PER_PYEONG)
                if not (_MIN_PYEONG <= area_pyeong <= _MAX_PYEONG):
                    continue
                out.append({
                    "id": f"vfu-{pnu}-{fl}",
                    "building_id": p.get("id"),
                    "pnu": pnu,
                    # 한 지번에 동이 여럿이면 층 근거를 동으로 나눌 수 없다 — 몇 동을
                    # 하나로 접었는지 드러낸다(1 이면 건물 하나가 곧 이 유닛이다).
                    "bldgs_on_pnu": len(feats),
                    "n": name,
                    "lat": lat, "lng": lng,
                    "floor": fl,
                    "floor_label": f"{fl}F",
                    # confirmed = 층 미상 점포를 다 앉히고도 남은 층(비었음이 확정)
                    # probable  = 그 배정에 먹힌 층(층 미상 점포가 다른 층이면 빈다)
                    "certainty": certainty,
                    "area": area_pyeong,
                    "area_m2": round(info["area"], 1),
                    # 건축물대장이 그 층에 허용한 용도 — 업종 후보를 거르는 근거
                    "purps": info["purps"],
                    "bld_status": p.get("status"),
                    "bld_floors": p.get("floors") or 0,
                    "bld_vacancy_rate": p.get("vacancy_rate"),
                    "com_floors": com,
                    "occ_floors": sorted(occ),
                    "unknown_n": unknown_n,
                    "was": p.get("industry") or "",
                })

    # 확정 먼저 → 낮은 층 먼저(1층이 값어치가 크다) → 면적 큰 순.
    # 상한(_MAX_UNITS)은 두지 않는다 — 목록을 자르는 것은 서빙·화면의 몫이고,
    # 파이프라인이 자르면 "이 거점에 매물이 12개뿐"이라고 말하게 된다.
    out.sort(key=lambda u: (u["certainty"] != "confirmed", u["floor"], -u["area"]))
    return out


def run(slugs: list[str]) -> dict[str, dict]:
    counts: dict[str, dict] = {}
    for slug in slugs:
        units = _units_for(slug)
        conf = sum(1 for u in units if u["certainty"] == "confirmed")
        counts[slug] = {"units": len(units), "confirmed": conf,
                        "probable": len(units) - conf,
                        "buildings": len({u["building_id"] for u in units})}
        if not units:
            continue
        out = {
            "source": ("Gold 건물 마스터(com_floors·occ_floors·unknown_n) + "
                       "건축물대장 층별개요(bronze bldg_flr_raw — 층별 면적·주용도)"),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": (
                "유닛 = (건물, 층). vacant_units.json 과 **다른 것을 센다** — 저쪽은 "
                "통째로 빈 건물 1동 = 유닛 1개(3-Tier ROI 모델의 표본)이고, 여기는 "
                "빈 층이 있는 모든 건물의 층마다 1개(화면에 거는 매물 목록)라 "
                "`partial` 건물이 들어온다. 층을 쪼갠 표본으로 ROI 트립와이어를 "
                "재면 중앙값 유닛이 상층부로 올라가 프라임 프리미엄 부호가 뒤집힌다 "
                "— 2026-08-26 에 실측하고 되돌린 자리다(docs/feature-posting.md §0-Q). "
                "그래서 이 파일은 그 표본을 대체하지 않는다. "
                "certainty=confirmed 는 층 미상 점포(상가정보 flrNo 공란 약 30%)를 "
                "낮은 층부터 다 앉히고도 남은 층이라 비었음이 확정이고, probable 은 "
                "그 배정에 먹힌 층이라 층 미상 점포가 다른 층에 있으면 빈다 — 둘을 "
                "같은 것으로 그리지 말 것. 배정 규칙은 build_page_master._aggregate "
                "의 상한 계산과 같다. "
                "area 는 그 층의 층별개요 실측 면적이다(vacant_units 의 균등분할과 "
                "다르다). ⚠ 한 층에 호실이 여럿이면 **그 층 전체**의 면적이며, "
                "호실 단위로는 내려갈 수 없다(§0-R·§0-S). "
                "purps 는 대장이 그 층에 허용한 용도다 — 업종 후보를 거르는 근거이지 "
                "현재 영업 중인 업종이 아니다."
            ),
            "counts": counts[slug],
            "units": units,
        }
        (GOLD / slug / "vacant_floor_units.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return counts


def main() -> None:
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(ACTIVE_HUBS)
    counts = run([s for s in slugs if get_hub(s) is not None])
    ok = {k: v for k, v in counts.items() if v["units"]}
    tot = sum(v["units"] for v in ok.values())
    conf = sum(v["confirmed"] for v in ok.values())
    print(f"[vacant-floor-units] 산출 {len(ok)}거점 / 시도 {len(counts)}거점 — "
          f"{tot}유닛 (확정 {conf} · 추정 {tot - conf})")
    for slug, v in sorted(ok.items(), key=lambda kv: -kv[1]["units"])[:15]:
        print(f"  {slug:18s} {v['units']:4d}유닛  확정 {v['confirmed']:4d}  "
              f"건물 {v['buildings']:4d}동")
    empty = [k for k, v in counts.items() if not v["units"]]
    if empty:
        print(f"  0유닛(마스터·층별개요 미적재): {', '.join(empty[:8])}"
              f"{' 외 %d곳' % (len(empty) - 8) if len(empty) > 8 else ''}")


if __name__ == "__main__":
    main()
