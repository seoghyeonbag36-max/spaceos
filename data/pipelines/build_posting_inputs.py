"""[Posting] 3-Tier 폴백 입력의 실데이터 소스 — gold/platform_posting_inputs.json 산출.

## 배경

`services/districts.tier_scenarios()` 는 유닛의 네 입력으로 시나리오를 계산한다:
`area`(면적) · `rent`(월임대료) · `prem`(권리금) · `foot`(유동인구 등급).
넷 다 `app/data/seoul_pages.py` 에 손으로 적은 프록시였다. 이 파이프라인은 그중
**실데이터가 있는 둘**(rent·foot)을 gold 시계열에서 뽑아 거점별로 떨군다.

| 입력 | 실데이터 | 판정 |
|---|---|---|
| `rent` | R-ONE 소규모상가 임대료(`rent_small`, 천원/㎡) 54거점 × 21분기 | ✅ 교체 |
| `foot` | 서울 상권분석 유동인구(`flpop`) 54거점 × 21분기 | ✅ 교체 |
| `area` | 없음 — silver `com_area_flr` 은 **건물** 단위지 유닛 단위가 아니다 | ❌ 시드 유지 |
| `prem` | 없음 — 권리금은 공개 통계가 없다(bronze 전수 확인) | ❌ 시드 유지 |

## 층 계수가 필요한 이유

R-ONE 소규모상가 임대료는 사실상 **1층 기준 시세**다. 시드 270유닛과 대조하면
R-ONE 환산/시드 비율이 층수에 따라 단조 증가한다(2026-08-01 실측 중앙값):

    1F 1.69 · B1 2.21 · 2F 3.66 · 3F 3.83 · 4F 5.25 · 5F 5.00 · 6F 6.84 · 7F 8.17

즉 R-ONE 값을 상층에 그대로 곱하면 임대료를 2~8배 과대계상한다. 그래서 1층을
1.00 으로 놓은 층 계수를 곱한다. **이 계수는 실측이 아니라 계수다** — 관측된
중앙값에서 출발하되 표본이 1~4건뿐인 꼬리(8F 등)의 노이즈를 빼고 단조가 되도록
다듬었으며, 한국 상가 관례(2층 이상은 1층의 30~50%)와도 부합한다.

## 산출

`data/gold/platform_posting_inputs.json` — 백엔드가 pandas 없이 읽는 정적 JSON
(Vercel 서버리스에 pandas 를 싣지 않는다. platform_vacancy_forecast.json 과 같은 이유).

실행: python -m data.pipelines.build_posting_inputs
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from data.collectors.common import GOLD

_TIMESERIES = GOLD / "platform13" / "platform_district_timeseries.parquet"
_OUT = GOLD / "platform_posting_inputs.json"

# 층 계수 — 1층 = 1.00 기준. 실측이 아니라 계수다(모듈 상단 설명 참조).
_FLOOR_FACTOR: dict[str, float] = {
    "B2": 0.60, "B1": 0.75,
    "1F": 1.00,
    "2F": 0.45, "3F": 0.40,
}
# 4층 이상은 하나로 묶는다 — 관측 표본이 층당 1~4건이라 층별로 나눌 근거가 없다.
_FLOOR_FACTOR_HIGH = 0.30
_PYEONG_TO_M2 = 3.3058


def floor_factor(floor: str) -> float:
    """유닛 층 라벨 → 임대료 계수. 모르는 라벨은 1층으로 본다(과소계상보다 안전)."""
    f = (floor or "").strip().upper()
    if f in _FLOOR_FACTOR:
        return _FLOOR_FACTOR[f]
    if f.endswith("F") and f[:-1].isdigit() and int(f[:-1]) >= 4:
        return _FLOOR_FACTOR_HIGH
    return _FLOOR_FACTOR["1F"]


def monthly_rent(rent_per_m2: float, area_pyeong: float, floor: str) -> int:
    """R-ONE 천원/㎡ + 면적(평) + 층 → 월임대료(만원). 시드 rent 와 같은 단위."""
    return round(rent_per_m2 * area_pyeong * _PYEONG_TO_M2 * floor_factor(floor) / 10)


def _foot_grades(flpop: pd.Series) -> dict[str, str]:
    """유동인구 → 저/중/고 3분위.

    절대 기준선이 아니라 **54거점 내 상대 등급**이다 — tier_scenarios 의 _FOOT_K
    (저 0.8 / 중 1.0 / 고 1.25)가 애초에 상대 배수라 분위수가 맞다.
    """
    lo, hi = flpop.quantile([1 / 3, 2 / 3])
    return {d: ("저" if v <= lo else "고" if v > hi else "중") for d, v in flpop.items()}


def run() -> dict:
    if not _TIMESERIES.exists():
        raise FileNotFoundError(
            f"{_TIMESERIES} 없음 — `python -m data.pipelines.build_gold` 를 먼저 실행할 것")

    df = pd.read_parquet(_TIMESERIES)
    quarter = df["quarter"].max()
    latest = df[df["quarter"] == quarter].set_index("district_id")

    missing = [c for c in ("rent_small", "flpop") if c not in latest.columns]
    if missing:
        raise KeyError(f"gold 시계열에 필요한 열이 없다: {missing}")

    grades = _foot_grades(latest["flpop"])
    districts = {
        d: {
            "rent_per_m2_krw_thousand": round(float(row.rent_small), 2),
            "flpop": int(row.flpop),
            "foot": grades[d],
        }
        for d, row in latest.iterrows()
        if pd.notna(row.rent_small) and pd.notna(row.flpop)
    }

    out = {
        "source": "R-ONE 소규모상가 임대료(rent_small) + 서울 상권분석 유동인구(flpop)",
        "quarter": str(quarter),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rent_unit": "천원/㎡·월 (R-ONE 소규모상가, 사실상 1층 기준)",
        "floor_factor": {**_FLOOR_FACTOR, "4F+": _FLOOR_FACTOR_HIGH},
        "note": (
            "층 계수는 실측이 아니라 계수다 — R-ONE 은 1층 기준이라 상층에 그대로 곱하면 "
            "2~8배 과대계상된다(2026-08-01 시드 270유닛 대조). area(면적)·prem(권리금)은 "
            "실데이터 소스가 없어 시드 프록시를 그대로 쓴다."
        ),
        "districts": districts,
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    out = run()
    d = out["districts"]
    print(f"[posting-inputs] {out['quarter']} · {len(d)}거점 → {_OUT}")
    rents = sorted((v["rent_per_m2_krw_thousand"], k) for k, v in d.items())
    print(f"  임대료(천원/㎡) {rents[0][0]:.1f}({rents[0][1]}) ~ {rents[-1][0]:.1f}({rents[-1][1]})")
    from collections import Counter
    print(f"  유동인구 등급 {dict(Counter(v['foot'] for v in d.values()))}")


if __name__ == "__main__":
    main()
