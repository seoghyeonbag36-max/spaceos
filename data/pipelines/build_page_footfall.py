"""[Page] TRDAR 수요신호 → 유동·밀도 레이어 산출물 (gold/platform_page_footfall.json).

## 왜 필요한가

`MapShell` 의 유동인구 히트맵이 `sampleFootfall()` — 즉 `Math.random()` 으로 만든
120개 점이었다. 시간 슬라이더를 움직여도 아무것도 바뀌지 않았다(입력을 안 봤다).
밀도 레이어는 백엔드 엔드포인트조차 없어 "데이터 연동 예정" 문구만 있었다.

재료는 이미 저장소 안에 있었다 — `gold/features/trdar_demand.parquet` 에 서울 상권
190곳의 **좌표·면적·유동총량·시간대 6구간·점포수**가 전부 들어 있고 54거점 전부를
덮는다. Program 이 이미 이 파일을 쓴다(§0-C). 수집이 아니라 **배선이 없던 것**이다.

## 파케이를 런타임에 들이지 않는다

`services/marketing._district_context` 가 `import pandas` 로 시작해 **배포에서 한 번도
돈 적이 없던** 사고(feature-program.md §0-5)와 같은 조합이다. Vercel 서버리스에는
pandas·pyarrow 가 없다. 그래서 학습·분석은 파케이로 두되 **서빙은 이 JSON 만** 읽는다.
같은 파일에서 파생시키고 이 스크립트가 유일한 생성 경로다.

    python data/pipelines/build_page_footfall.py

## 무엇이 실측이고 무엇이 근사인가 (중요)

- **실측**: 상권별 유동인구 총량·시간대 구성비·점포수·면적·중심좌표.
- **근사**: 상권 **안에서의 분포**. TRDAR 은 상권 단위 집계라 상권 내부 어디가 더
  붐비는지는 모른다. 그래서 서빙 계층이 셀마다 **최근접 상권 값을 얹는다**
  (rent_layer 가 R-ONE 을 얹는 방식과 같다). 응답의 `resolution: "trdar"` 와
  범례가 이 사실을 밝힌다 — 밝히지 않으면 격자 단위 실측처럼 읽힌다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "data" / "gold" / "features" / "trdar_demand.parquet"
_OUT = _ROOT / "data" / "gold" / "platform_page_footfall.json"

# 시간대 6구간 — TRDAR 원천의 눈금 그대로다. Program 의 수요신호(§0-C)와 **같은 자**를
# 써야 두 트랙이 같은 시간대를 말한다.
TMZONS = ["00_06", "06_11", "11_14", "14_17", "17_21", "21_24"]


def main() -> None:
    if not _SRC.exists():
        raise SystemExit(f"{_SRC} 없음 — ml/data 파이프라인으로 먼저 생성할 것")
    d = pd.read_parquet(_SRC)

    need = ["trdar_cd", "trdar_nm", "district_id", "trdar_lat", "trdar_lon",
            "trdar_area_m2", "flpop_tot", "stor_co"]
    missing = [c for c in need if c not in d.columns]
    if missing:
        raise SystemExit(f"필수 열 없음: {missing}")

    districts: dict[str, list[dict]] = {}
    for r in d.itertuples(index=False):
        area = float(getattr(r, "trdar_area_m2") or 0)
        flpop = float(getattr(r, "flpop_tot") or 0)
        # 시간대 구성비. 합이 1 이 아닐 수 있어(반올림) 그대로 싣고 해석은 런타임에서 한다.
        shares = {t: round(float(getattr(r, f"flpop_tmzon_{t}_share") or 0), 6)
                  for t in TMZONS}
        districts.setdefault(str(r.district_id), []).append({
            "cd": str(r.trdar_cd), "nm": str(r.trdar_nm),
            "lat": round(float(r.trdar_lat), 6), "lng": round(float(r.trdar_lon), 6),
            "area_m2": round(area, 1),
            "flpop_tot": round(flpop, 1),
            "tmzon": shares,
            "stor_co": int(getattr(r, "stor_co") or 0),
            # 밀도 = 유동인구 ÷ 상권 면적. 면적이 0 이면 밀도가 정의되지 않는다 —
            # 0 으로 접으면 "사람이 없다"는 거짓이 되므로 None 으로 둔다.
            "flpop_per_1k_m2": round(flpop / area * 1000, 2) if area > 0 else None,
            "stor_per_1k_m2": round(int(getattr(r, "stor_co") or 0) / area * 1000, 3)
                              if area > 0 else None,
        })

    doc = {
        "source": "서울 열린데이터 상권분석(TRDAR) — gold/features/trdar_demand.parquet",
        "built_from": str(_SRC.relative_to(_ROOT)).replace("\\", "/"),
        "resolution": "trdar",
        "note": ("값은 **상권 단위 집계**다. 상권 내부의 분포는 알 수 없으므로 서빙 "
                 "계층이 격자 셀에 최근접 상권 값을 얹는다 — 격자 단위 실측이 아니다."),
        "tmzons": TMZONS,
        "districts": districts,
    }
    _OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    n_t = sum(len(v) for v in districts.values())
    sizes = sorted(len(v) for v in districts.values())
    print(f"→ {_OUT.relative_to(_ROOT)}  ({_OUT.stat().st_size/1024:.0f}KB)")
    print(f"   거점 {len(districts)} · 상권 {n_t} · 거점당 {sizes[0]}~{sizes[-1]}"
          f"(중앙 {sizes[len(sizes)//2]})")
    no_area = [t["nm"] for v in districts.values() for t in v if t["flpop_per_1k_m2"] is None]
    print(f"   면적 0 으로 밀도 미정: {len(no_area)}건 {no_area[:3]}")


if __name__ == "__main__":
    main()
