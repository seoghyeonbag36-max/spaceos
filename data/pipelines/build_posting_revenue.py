"""[Posting] 3-Tier 매출계수의 실측 근거 — gold/platform_posting_revenue.json 산출.

## 왜 만드나

`districts.tier_scenarios()` 의 매출식 `month_rev = k·area·foot + c` 에서 계수
`k`(41/30/18)·`c`(1150/760/430)는 **출처 주석이 없는 손으로 적은 값**이었다.
비용 모델만 실데이터로 보정하면 "비용은 실측, 매출은 가정"의 비대칭이 생기고
그 비대칭이 그대로 `roi_months` → 추천 결과에 실린다. 그래서 매출 쪽 근거를 먼저 깐다.

## 무엇을 재나 — 점포당 월 추정매출

서울 상권분석 서비스의 **상권×업종×분기 추정매출**(`THSMON_SELNG_AMT`)을 같은 키의
**점포수**(`STOR_CO`)로 나눈다. 분기 합계이므로 3으로 나눠 월 단위로 맞춘다.

    점포당 월매출(만원) = THSMON_SELNG_AMT / STOR_CO / 3 / 10000

이 값이 `month_rev` 가 재현해야 할 실측 대역이다. **가맹/비가맹, 면적, 층을 구분하지
않는 상권 평균**이라는 점이 한계다(아래 §한계).

## tier ↔ 업종 대표군 (2026-08-22 제품 판단)

원가율·인건비의 공개 통계는 전부 **업종별**로 공표되는데 우리 축은 전략(tier)이다.
그래서 tier 를 업종 대표군으로 정의한다 — 이렇게 해야 외부 통계를 계수로 내릴 수 있다.

| tier | 업종 대표군 | 고른 이유 |
|---|---|---|
| premium 고급화 | 일식·양식·중식음식점 | 풀서비스 정찬. 객단가가 높고 조리·접객 인력이 많다 |
| value 가성비 | 한식음식점·분식·치킨·호프간이주점 | 대중식당·주점. 회전과 객단가가 중간대 |
| factory 공장제 | 커피-음료·패스트푸드·제과점 | 표준화 레시피·높은 회전·최소 인력 |

⚠ **이 매핑 자체는 실측이 아니라 정의다.** 서울 상권분석의 10개 외식 업종을 셋으로
가른 것이고, 가르는 선은 "풀서비스 ↔ 표준화" 축으로 잡았다. 같은 한식이라도 고급
한정식과 백반집이 갈리는 현실을 이 축은 담지 못한다 — tier 를 업종 무관 운영방식으로
두는 대안이 있었으나(§ docs/feature-posting.md), 그 경우 외부 통계를 못 붙이므로
업종 대표군 쪽을 골랐다. **이 선택은 되돌릴 수 있고, 바꾸면 이 파일만 고치면 된다.**

## 한계 — 이 값을 그대로 계수로 쓸 수 없는 이유

1. **면적 축이 없다.** 상권분석은 점포 면적을 주지 않는다. 현재 모델은 매출을 면적
   선형으로 두는데, 그 기울기(`k`)를 이 실측만으로는 정할 수 없다. 이 산출물이 고정하는
   것은 **수준(level)** 이지 **기울기**가 아니다.
2. **점포 평균이라 신규 진입 가정이 아니다.** 자리 잡은 점포와 갓 연 점포가 섞여 있다.
3. **상권 경계 ≠ 거점 경계.** 한 거점에 여러 TRDAR 이 걸리므로 점포수 가중으로 합친다.

실행: python -m data.pipelines.build_posting_revenue
"""
from __future__ import annotations

import glob
import json
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data.collectors.common import GOLD

_BRONZE = Path("data/bronze/platform13")
_OUT = GOLD / "platform_posting_revenue.json"
_DEMAND = GOLD / "features" / "trdar_demand.parquet"

# tier → 서울 상권분석 서비스업종 코드. 위 표의 근거가 이 dict 다.
TIER_INDUTY = {
    "premium": {"CS100003": "일식음식점", "CS100004": "양식음식점", "CS100002": "중식음식점"},
    "value": {"CS100001": "한식음식점", "CS100008": "분식전문점",
              "CS100007": "치킨전문점", "CS100009": "호프-간이주점"},
    "factory": {"CS100010": "커피-음료", "CS100006": "패스트푸드점", "CS100005": "제과점"},
}
# 점포수가 적은 상권은 1~2개 점포의 튐이 그대로 중앙값이 된다.
_MIN_STORES = 5


def _latest(name: str) -> list[dict]:
    paths = sorted(glob.glob(str(_BRONZE / "*" / f"seoul_trdar_{name}.json")))
    if not paths:
        raise SystemExit(f"bronze 없음: seoul_trdar_{name}.json")
    return json.loads(Path(paths[-1]).read_text(encoding="utf-8"))


def _per_store_rows() -> tuple[str, list[tuple[str, str, float, float]]]:
    """(분기, [(trdar_cd, induty_cd, 점포당월매출_만원, 점포수)]) — 최신 분기만."""
    sel = _latest("selng")
    sto = _latest("stor")
    quarter = max(r["STDR_YYQU_CD"] for r in sel)

    stores = {(r["TRDAR_CD"], r["SVC_INDUTY_CD"]): r["STOR_CO"]
              for r in sto if r["STDR_YYQU_CD"] == quarter}

    rows: list[tuple[str, str, float, float]] = []
    for r in sel:
        if r["STDR_YYQU_CD"] != quarter:
            continue
        cd = r["SVC_INDUTY_CD"]
        n = stores.get((r["TRDAR_CD"], cd), 0) or 0
        if n < _MIN_STORES:
            continue                      # 표본이 얇으면 중앙값이 한 점포에 끌려간다
        amt = r.get("THSMON_SELNG_AMT") or 0
        if amt <= 0:
            continue
        rows.append((r["TRDAR_CD"], cd, amt / n / 3 / 10000, float(n)))
    return quarter, rows


def _stats(vals: list[float], weights: list[float]) -> dict:
    """점포수 가중 없이 중앙값·사분위, 점포수는 합계로만 싣는다.

    가중 중앙값을 쓰면 점포가 많은 대형 상권 하나가 거점 값을 결정해 버린다.
    거점 안 상권들의 '전형적인 한 점포'를 원하므로 비가중 중앙값을 쓴다.
    """
    s = sorted(vals)
    return {
        "n_obs": len(s),
        "stores": int(sum(weights)),
        "median": round(st.median(s), 1),
        "p25": round(s[len(s) // 4], 1),
        "p75": round(s[len(s) * 3 // 4], 1),
    }


def run() -> dict:
    quarter, rows = _per_store_rows()
    cd2tier = {cd: t for t, m in TIER_INDUTY.items() for cd in m}

    demand = pd.read_parquet(_DEMAND, columns=["trdar_cd", "district_id"])
    trdar2district = dict(zip(demand["trdar_cd"].astype(str), demand["district_id"]))

    seoul: dict[str, list] = defaultdict(list)
    seoul_w: dict[str, list] = defaultdict(list)
    by_d: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    by_d_w: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    by_induty: dict[str, list] = defaultdict(list)

    for trdar, cd, per_store, n in rows:
        tier = cd2tier.get(cd)
        if not tier:
            continue                      # 외식 10업종 밖(학원·미용실 등)은 대상이 아니다
        by_induty[cd].append(per_store)
        seoul[tier].append(per_store)
        seoul_w[tier].append(n)
        d = trdar2district.get(trdar)
        if d:
            by_d[d][tier].append(per_store)
            by_d_w[d][tier].append(n)

    districts = {}
    for d, tiers in by_d.items():
        districts[d] = {t: _stats(v, by_d_w[d][t]) for t, v in tiers.items() if v}

    induty_names = {cd: nm for m in TIER_INDUTY.values() for cd, nm in m.items()}
    out = {
        "source": ("서울 열린데이터 상권분석 추정매출(VwsmTrdarSelngQq) ÷ 점포수"
                   "(VwsmTrdarStorQq) ÷ 3개월. 단위 만원/월, 점포당."),
        "quarter": quarter,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "min_stores": _MIN_STORES,
        "tier_induty": TIER_INDUTY,
        "caveat": ("상권 평균이라 면적·층·가맹여부를 구분하지 않는다. 따라서 매출의 "
                   "**수준**은 이 값으로 고정할 수 있으나 면적 **기울기**는 정할 수 없다."),
        "seoul": {t: _stats(v, seoul_w[t]) for t, v in seoul.items()},
        "by_induty": {induty_names[cd]: _stats(v, [1.0] * len(v))
                      for cd, v in sorted(by_induty.items())},
        "districts": districts,
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    out = run()
    print(f"[posting-revenue] 분기 {out['quarter']} · 거점 {len(out['districts'])}")
    print("\n서울 전체 — tier별 점포당 월매출(만원)")
    for t in ("premium", "value", "factory"):
        s = out["seoul"].get(t)
        if s:
            print(f"  {t:8s} 관측 {s['n_obs']:4d} · 점포 {s['stores']:6d}"
                  f" · 중앙 {s['median']:7.1f}  (p25 {s['p25']} ~ p75 {s['p75']})")
    print("\n업종별 점포당 월매출(만원)")
    for nm, s in sorted(out["by_induty"].items(), key=lambda kv: -kv[1]["median"]):
        print(f"  {nm:12s} n={s['n_obs']:4d}  중앙 {s['median']:7.1f}"
              f"  (p25 {s['p25']} ~ p75 {s['p75']})")


if __name__ == "__main__":
    main()
