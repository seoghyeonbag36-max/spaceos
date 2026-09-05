"""[Posting] 층·용도별 업종 적합도 — gold/platform_industry_floor_fit.json.

## 무엇을 세는가

"대장이 **이 용도**로 허가한 **이 층**에, 실제로 어떤 업종이 들어와 있는가."
손으로 적은 매칭표가 아니라 **관측**이다 — 상가정보(업종·층)와 건축물대장 층별개요
(층·주용도)를 `(지번, 층)` 으로 조인해 센다.

    상가정보  lnoCd + flrNo + indsMclsNm(업종 중분류)
    층별개요  pnu   + flrNo + mainPurpsCdNm(그 층의 대장 용도)

## 왜 GNN 추천으로는 부족한가

`platform_industry_recommend.json`(GNN)은 라벨이 **7종**(음식점·카페·병원·편의점·숙박·
문화시설·약국)이고 조회 키가 **좌표**다. 자리의 입지는 말해 주지만 "3층 40평 학원 용도"
라는 **매물의 제약**은 안 본다 — 1층 요식업과 3층 학원은 들어갈 수 있는 업종이 다른데
그 축이 모델에 없다. 여기서 세는 것은 그 축이고, 둘은 **다른 것을 재므로 합치지 않는다.**

## 표본이 얇으면 말하지 않는다

`(용도, 층)` 조합은 꼬리가 길다. 표본이 `_MIN_SAMPLE` 미만이면 그 칸을 내지 않고
층만 본 분포(`by_floor`)로 물러나며, 그것도 얇으면 아무 것도 주지 않는다. 분포마다
`n`(표본 수)을 같이 실어, 화면이 "3건 중 2건"을 확률처럼 그리지 못하게 한다.

## 한계 (읽는 쪽이 알아야 하는 것)

- **조인율 약 30%.** 상가정보 `flrNo` 공란이 약 38%, 층별개요를 아직 못 받은 건물이
  나머지다. 즉 이 표는 층이 확인된 점포의 분포이지 전수가 아니다.
- **대장 용도는 허가지 현황이 아니다.** '학원' 용도 층에 실제로는 사무실이 있을 수 있다
  — 그 어긋남까지 이 표가 관측으로 담는다(그래서 표가 유용하다).
- 여기 나온 업종이 **그 자리에서 잘 된다는 뜻이 아니다.** 매출·생존은 안 봤다.
  이것은 "무엇이 들어갈 수 있는가"이지 "무엇이 돈이 되는가"가 아니다.

실행: python -m data.pipelines.build_industry_floor_fit [거점 ...]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

from data.collectors.building_vacancy import NON_CAPACITY_PURPS
from data.collectors.common import BRONZE, GOLD
from data.config.page_hubs import ACTIVE_HUBS, get_hub

# 이 미만이면 그 칸을 내지 않는다. 3건 중 2건을 67% 라고 부르면 안 된다.
_MIN_SAMPLE = 30
# 한 칸에 실을 업종 수. 꼬리는 화면에서 못 읽고 파일만 키운다.
_TOP_K = 8
# 층은 위로 갈수록 표본이 얇아진다 — 4층 이상은 한 칸으로 묶는다.
_FLOOR_CAP = 4


def _floor_key(no: int) -> str:
    return f"{no}" if no < _FLOOR_CAP else f"{_FLOOR_CAP}+"


def _ledger_floor_purps(slug: str) -> dict[tuple[str, int], str]:
    """`(지번, 층) → 대장 그 층의 주용도`. 필터는 capacity 산출과 같은 negative 필터다."""
    merged: dict[str, list[dict]] = {}
    for p in sorted(BRONZE.glob(f"{slug}/*/bldg_flr_raw.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            merged.update(d)

    out: dict[tuple[str, int], str] = {}
    best: dict[tuple[str, int], float] = {}
    for pnu, rows in merged.items():
        for r in rows:
            if str(r.get("flrGbCdNm", "")) not in ("지상", ""):
                continue
            purps = str(r.get("mainPurpsCdNm") or "")
            if not purps or any(x in purps for x in NON_CAPACITY_PURPS):
                continue
            no = int(r.get("flrNo") or 0)
            if no <= 0:
                continue
            # 한 층에 행이 여럿이면 면적이 가장 큰 행의 용도를 그 층의 대표로 삼는다
            # (vacant_floor_units._by_floor 와 같은 규칙 — 갈라지면 같은 층을 두고
            # 매물 카드와 적합도 표가 서로 다른 용도를 말한다).
            area = float(r.get("area") or 0.0)
            k = (pnu, no)
            if area >= best.get(k, -1.0):
                best[k], out[k] = area, purps
    return out


def _count(slugs: list[str]) -> tuple[dict, dict, dict]:
    by_pf: dict[str, Counter] = defaultdict(Counter)   # "용도|층" → 업종 카운트
    by_f: dict[str, Counter] = defaultdict(Counter)    # "층" → 업종 카운트 (폴백)
    stat = Counter()

    for slug in slugs:
        paths = sorted(BRONZE.glob(f"{slug}/*/stores_raw.json"))
        if not paths:
            continue
        try:
            stores = json.loads(paths[-1].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(stores, list):
            continue
        idx = _ledger_floor_purps(slug)
        if not idx:
            continue
        stat["hubs"] += 1

        for s in stores:
            stat["stores"] += 1
            raw = str(s.get("flrNo") or "").strip()
            if not raw.isdigit():
                stat["no_floor"] += 1
                continue
            no = int(raw)
            if no <= 0:
                stat["no_floor"] += 1
                continue
            inds = str(s.get("indsMclsNm") or "").strip()
            if not inds:
                stat["no_industry"] += 1
                continue
            fk = _floor_key(no)
            by_f[fk][inds] += 1
            purps = idx.get((str(s.get("lnoCd") or ""), no))
            if purps is None:
                stat["no_ledger"] += 1
                continue
            by_pf[f"{purps}|{fk}"][inds] += 1
            stat["joined"] += 1

    return by_pf, by_f, stat


def _shape(c: Counter) -> dict | None:
    n = sum(c.values())
    if n < _MIN_SAMPLE:
        return None
    return {
        "n": n,
        # 비중은 소수 3자리. 화면은 이것을 확률이 아니라 **관측 비중**으로 그려야 한다.
        "top": [{"industry": k, "share": round(v / n, 3), "n": v}
                for k, v in c.most_common(_TOP_K)],
    }


def run(slugs: list[str]) -> dict:
    by_pf, by_f, stat = _count(slugs)
    pf = {k: s for k, v in by_pf.items() if (s := _shape(v))}
    ff = {k: s for k, v in by_f.items() if (s := _shape(v))}

    out = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": ("상가정보(bronze stores_raw — indsMclsNm·flrNo) × 건축물대장 층별개요"
                   "(bronze bldg_flr_raw — mainPurpsCdNm) 를 (지번, 층) 으로 조인"),
        "note": (
            "'이 대장 용도의 이 층에 실제로 어떤 업종이 들어와 있는가'의 **관측 분포**다. "
            "손으로 적은 매칭표가 아니다. ⚠ 조인율은 약 30% — 상가정보 flrNo 공란이 "
            "약 38%, 층별개요 미수집 건물이 나머지다. 전수가 아니라 **층이 확인된 점포**의 "
            "분포다. ⚠ 대장 용도는 허가이지 현황이 아니다(그 어긋남까지 이 표가 담는다). "
            "⚠ 여기 나온 업종이 그 자리에서 **잘 된다**는 뜻이 아니다 — 매출·생존은 안 "
            "봤고, 이것은 '무엇이 들어갈 수 있는가'이지 '무엇이 돈이 되는가'가 아니다. "
            f"표본 {_MIN_SAMPLE}건 미만인 칸은 내지 않는다(얇은 표본을 확률처럼 그리면 "
            "안 된다). GNN 추천(platform_industry_recommend)과는 **다른 축**이다 — "
            "저쪽은 좌표 기준 7종 라벨, 이쪽은 매물(층·용도) 기준 관측이라 합치지 않는다."
        ),
        "min_sample": _MIN_SAMPLE,
        "floor_cap": _FLOOR_CAP,
        "stats": dict(stat),
        # "용도|층" → 관측 분포. 층은 1·2·3·4+ 로 묶는다.
        "by_purps_floor": pf,
        # 폴백: 용도를 못 맞췄을 때 층만 본 분포.
        "by_floor": ff,
    }
    (GOLD / "platform_industry_floor_fit.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(ACTIVE_HUBS)
    out = run([s for s in slugs if get_hub(s) is not None])
    st = out["stats"]
    print(f"[industry-floor-fit] 거점 {st.get('hubs', 0)} · 점포 {st.get('stores', 0):,} "
          f"→ 조인 {st.get('joined', 0):,} "
          f"({st.get('joined', 0) / max(st.get('stores', 1), 1) * 100:.1f}%)")
    print(f"  층 공란 {st.get('no_floor', 0):,} · 대장 미매칭 {st.get('no_ledger', 0):,} "
          f"· 업종 공란 {st.get('no_industry', 0):,}")
    print(f"  칸: 용도×층 {len(out['by_purps_floor'])} · 층만 {len(out['by_floor'])} "
          f"(표본 {out['min_sample']}건 이상)")
    for k, v in sorted(out["by_purps_floor"].items(), key=lambda kv: -kv[1]["n"])[:8]:
        top = " · ".join(f"{t['industry']} {t['share']*100:.0f}%" for t in v["top"][:3])
        print(f"    {k:24s} n={v['n']:6,}  {top}")


if __name__ == "__main__":
    main()
