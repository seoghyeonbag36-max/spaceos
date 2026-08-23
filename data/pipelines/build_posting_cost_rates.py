"""[Posting] KOSIS 서비스업조사 → tier별 영업비용률 (gold/platform_posting_cost_rates.json).

## 왜 이 파일이 필요한가

`docs/feature-posting.md` §0-F 가 서울 2024 업종별 영업비용률을 **표로만** 적어 두고
있었다. 표는 사람이 읽지만 `tier_scenarios` 는 못 읽는다 — 그리고 손으로 옮겨 적은
표는 낡아도 아무도 모른다(이 프로젝트의 주된 실패 양식). 그래서 API 에서 받아
산출물로 떨군다.

    python data/pipelines/build_posting_cost_rates.py

## 통계표

`orgId=101` · `tblId=DT_3KB9001` (통계청 서비스업조사 — 시도/산업별 총괄), 기준 2024.
분류축은 `objL1=SGG`(시도) · `objL2=IND_11`(산업, KSIC 5자리까지).

## 임차료를 왜 따로 빼는가 — 이중계상 방지

KOSIS 영업비용(T05)에는 **임차료(T053)가 이미 들어 있다.** 그런데 우리 모델의
`month_cost` 는 유닛별 임대료(R-ONE 실측 + 면적 + 층계수)를 따로 갖고 있다. 영업비용률을
그대로 곱하면 임차료를 두 번 세게 된다.

그래서 이 파이프라인은 **비임차 영업비용률**을 함께 낸다:

    비임차_영업비용률 = (영업비용 − 임차료) / 매출액

`month_cost = rent(유닛 실측) + rev × 비임차_영업비용률` 로 쓰면 임차료는 우리 실측
쪽에서 한 번만 들어간다. 이렇게 하면 자리별 임대료 차이가 손익에 그대로 드러나는데,
그것이 공실 인벤토리에서 우리가 보고 싶은 바로 그 신호다.

⚠ 매출원가(T051)는 음식점업 전 업종 미공표(`-`)다. 대신 항등식
`영업비용 = 인건비 + 임차료 + 기타경비` 가 성립한다(원가가 기타경비에 흡수). 비용
모델에 필요한 것은 원가율이 아니라 영업비용률 전체이므로 이걸로 충분하다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))

from kosis_probe import DATA_URL, _get  # noqa: E402

ORG, TBL, YEAR_CNT = "101", "DT_3KB9001", "1"
SEOUL = "11"

# tier ↔ 업종 대표군 (docs/feature-posting.md §0-B 에서 정한 매핑, §0-F 에서 KSIC 확정).
# 업종별 통계를 tier 축으로 옮기는 유일한 다리다 — 바꾸면 비용률·매출계수가 같이 움직인다.
TIER_KSIC = {
    "premium": {"56122": "일식", "56123": "양식", "56121": "중식"},
    "value": {"56111": "한식일반", "56162": "치킨", "56213": "생맥주"},
    "factory": {"56221": "커피", "56161": "패스트푸드", "56150": "제과"},
}
ITEMS = ["T01", "T03", "T05", "T051", "T052", "T053", "T054", "T06"]
ITEM_NM = {"T01": "estab", "T03": "sales", "T05": "opex", "T051": "cogs",
           "T052": "labor", "T053": "rent", "T054": "other", "T06": "profit"}


def _num(v) -> float | None:
    """KOSIS 는 미공표를 '-' 로 준다. 0 으로 읽으면 비율이 조용히 틀어진다."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch() -> dict[str, dict[str, float | None]]:
    codes = [c for m in TIER_KSIC.values() for c in m]
    rows = _get(DATA_URL, method="getList", orgId=ORG, tblId=TBL,
                objL1=SEOUL, objL2="+".join(codes), itmId="+".join(ITEMS),
                prdSe="Y", newEstPrdCnt=YEAR_CNT)
    rows = rows if isinstance(rows, list) else [rows]
    out: dict[str, dict] = {}
    for r in rows:
        ksic = r.get("C2")
        item = ITEM_NM.get(r.get("ITM_ID", ""))
        if not ksic or not item:
            continue
        d = out.setdefault(ksic, {"ksic": ksic, "period": r.get("PRD_DE")})
        d[item] = _num(r.get("DT"))
    return out


def main() -> None:
    raw = fetch()
    missing = [c for m in TIER_KSIC.values() for c in m if c not in raw]
    if missing:
        raise SystemExit(f"KOSIS 응답에 없는 업종 코드: {missing}")

    industries, tiers = {}, {}
    for tier, ksics in TIER_KSIC.items():
        # 비율은 매출가중으로 합산한다. 사업체수 가중은 영세업체가 과대대표된다.
        agg = {k: 0.0 for k in ("estab", "sales", "opex", "labor", "rent", "other", "profit")}
        for ksic, nm in ksics.items():
            d = raw[ksic]
            sales, opex, rent = d.get("sales"), d.get("opex"), d.get("rent")
            if not sales or opex is None or rent is None:
                raise SystemExit(f"{nm}({ksic}) 매출/영업비용/임차료 미공표 — 비용률 산출 불가")
            # 항등식 검증: 영업비용 = 인건비 + 임차료 + 기타경비 (매출원가는 기타경비에 흡수)
            parts = sum(v for k in ("labor", "rent", "other") if (v := d.get(k)) is not None)
            resid = opex - parts
            industries[ksic] = {
                "name": nm, "tier": tier, "period": d.get("period"),
                "estab": d.get("estab"), "sales_mn": sales, "opex_mn": opex,
                "labor_mn": d.get("labor"), "rent_mn": rent, "other_mn": d.get("other"),
                "cogs_mn": d.get("cogs"),          # 음식점업은 전부 None(미공표)
                "opex_rate": round(opex / sales, 4),
                "rent_rate": round(rent / sales, 4),
                "opex_rate_ex_rent": round((opex - rent) / sales, 4),
                "identity_residual_mn": round(resid, 1),
            }
            for k in agg:
                agg[k] += d.get(k) or 0.0
        s = agg["sales"]
        tiers[tier] = {
            "ksic": sorted(ksics), "estab": int(agg["estab"]), "sales_mn": s,
            "opex_rate": round(agg["opex"] / s, 4),
            "rent_rate": round(agg["rent"] / s, 4),
            # ▼ 비용 모델이 실제로 쓰는 값. rent 는 유닛별 실측으로 따로 들어간다.
            "opex_rate_ex_rent": round((agg["opex"] - agg["rent"]) / s, 4),
            "labor_rate": round(agg["labor"] / s, 4),
            "profit_rate": round(agg["profit"] / s, 4),
        }

    doc = {
        "source": {"org_id": ORG, "tbl_id": TBL, "name": "통계청 서비스업조사 시도/산업별 총괄",
                   "region": "서울특별시(11)",
                   "period": industries[next(iter(industries))]["period"],
                   "unit": "백만원"},
        "note": ("opex_rate_ex_rent = (영업비용 − 임차료) / 매출액. 임차료를 뺀 것은 "
                 "month_cost 가 유닛별 임대료(R-ONE)를 따로 갖고 있어 이중계상이 되기 "
                 "때문이다. 매출원가(T051)는 음식점업 미공표라 기타경비에 흡수돼 있다."),
        "tiers": tiers, "industries": industries,
    }
    out = _ROOT / "data" / "gold" / "platform_posting_cost_rates.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"→ {out.relative_to(_ROOT)}  ({doc['source']['period']}년 · 서울)")
    print(f"{'tier':10s} {'사업체':>7s} {'영업비용률':>9s} {'임차료율':>8s} "
          f"{'비임차비용률':>11s} {'인건비율':>8s} {'영업이익률':>9s}")
    for t, v in tiers.items():
        print(f"{t:10s} {v['estab']:7,d} {v['opex_rate']*100:8.1f}% {v['rent_rate']*100:7.1f}% "
              f"{v['opex_rate_ex_rent']*100:10.1f}% {v['labor_rate']*100:7.1f}% "
              f"{v['profit_rate']*100:8.1f}%")
    bad = [i["name"] for i in industries.values() if abs(i["identity_residual_mn"]) > 1]
    print(f"항등식 잔차 >1백만원 업종: {bad or '없음'}")


if __name__ == "__main__":
    main()
