"""[Program] 상권 수요신호를 콘텐츠 컨텍스트에 합류 — gold/{거점}/program_content_context.

Program 의 대상이 2026-08-16 에 **공실에 창업할 기업**으로 재정의되면서, 근거의 종류가
바뀌었다. 영업 중인 가게라면 리뷰가 근거지만, 아직 열지 않은 가게에는 리뷰가 없다.
대신 쓸 수 있는 것이 **그 자리가 속한 상권의 수요 구조**다 — 누가(연령·성별), 언제
(시간대·요일) 오고, 그중 언제 실제로 돈을 쓰는가.

두 출력이 같은 데이터에서 갈린다:
  - **온라인(퍼포먼스)** — 매출이 유동을 앞서는 시간대에 광고를 태운다(전환 구간).
  - **오프라인(유동인구 확대)** — 유동이 매출을 앞서는 시간대가 비어 있는 구간이다.
    가로수길 06~11시는 유동 17.7% / 매출 4.1% 로 **+13.7%p** 벌어진다 — 아침 마켓 같은
    제안이 "어느 상권에나 해당하는 말"이 되지 않게 붙잡아 주는 수치가 이것이다.

## 왜 파케이를 그대로 쓰지 않는가

원천은 `gold/features/trdar_demand.parquet`(190상권×46열, GNN 학습용)인데 **런타임은
이걸 읽을 수 없다.** `.vercelignore` 가 `**/*.parquet` 를 배포에서 빼고, 서버리스에는
pandas 도 pyarrow 도 없다. 2026-08-06 에 정확히 이 조합으로 사고가 났다 — 컨텍스트를
`pd.read_parquet` 로 읽던 코드가 프로덕션에서 항상 실패했고, 그 실패가 except 에 잡혀
컨텍스트가 **늘 None** 이었는데 화면은 시드로 멀쩡해 보여 아무도 몰랐다.

그래서 산출물을 이미 배포·서빙되는 **CSV(kind/key/value 3열)** 에 얹는다. 런타임은
표준 라이브러리 csv 로만 읽는다. 학습(파케이)과 서빙(CSV)의 원천이 갈리지 않도록
**같은 파일에서 파생**시키고, 이 스크립트가 유일한 생성 경로다.

## 거점 ↔ TRDAR 은 1:N 이다

54거점이 190상권으로 쪼개지므로(거점당 평균 3.5) 하나로 합쳐야 한다. 구성비(share)는
**유동인구(flpop_tot) 가중평균**, 총량(flpop/selng/점포)은 합으로 접는다. 단순평균을
쓰면 작은 상권이 큰 상권과 같은 무게를 갖는다 — 가로수길에 붙은 두 상권의 규모가
다르므로 그대로 두면 구성비가 실제와 어긋난다.

실행: python -m data.pipelines.build_program_demand      (저장소 루트 spaceos/ 에서)
      python data/pipelines/build_program_demand.py --dry-run    쓰지 않고 미리보기
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD = ROOT / "data" / "gold"
DEMAND_PARQUET = GOLD / "features" / "trdar_demand.parquet"

# CSV 에 실을 kind 접두. 런타임(services/marketing._district_context)이 이 접두로 고른다.
KIND = "demand"

# 시간대 6구간 — TRDAR 원 컬럼의 접미와 같다.
TMZONS = ["00_06", "06_11", "11_14", "14_17", "17_21", "21_24"]

# 오프라인 제안이 겨냥할 수 있는 시간대. **00~06 을 뺀다.**
# 심야에 유동이 매출을 앞서는 것은 상권의 빈틈이 아니라 당연한 일이고(가게가 닫혀 있다),
# 실제로 이 값을 빼지 않으면 54거점 중 대다수에서 00~06 이 '최대 격차'로 뽑힌다.
# 그 위에 제안을 세우면 새벽 플리마켓 같은 말이 나온다. 데이터에는 6구간을 다 싣되,
# "빈 시간대" 해석은 이 목록 안에서만 한다.
ACTIONABLE_TMZONS = TMZONS[1:]

AGE_BANDS = ["10", "20", "30", "40", "50", "60_above"]


def _load() -> "list[dict]":
    """파케이 → dict 목록. 여기서만 pandas 를 쓴다(빌드 타임 전용)."""
    try:
        import pandas as pd
    except ImportError:
        print("pandas 필요: pip install pandas pyarrow")
        return []
    if not DEMAND_PARQUET.exists():
        print(f"[demand] 원천 없음: {DEMAND_PARQUET} — build_trdar_demand 먼저")
        return []
    return pd.read_parquet(DEMAND_PARQUET).to_dict("records")


def _nan(v: object) -> bool:
    return v is None or (isinstance(v, float) and v != v)


def _fold(rows: list[dict]) -> dict[str, float]:
    """한 거점에 붙은 TRDAR 상권 여러 개 → 지표 하나로.

    구성비는 flpop_tot 가중평균, 총량은 합. 가중치 합이 0 이면(유동 결측) 단순평균으로
    떨어진다 — 0 으로 나누느니 덜 정확한 값을 내는 편이 낫다.

    ⚠ **매출 결측을 0 으로 접지 않는다.** 190상권 중 5곳이 `has_selng=0` 이고 selng_*
    가 통째로 NaN 이다(예: 청담 '영동대교남단'). 0 으로 세면 "그 시간대에 매출이 없다"는
    거짓이 되고, 유동-매출 격차가 실제보다 크게 벌어져 오프라인 제안의 근거가 부풀려진다.
    그래서 매출 지표는 **매출이 있는 상권만으로** 따로 가중하고, 한 곳도 없으면 아예
    내보내지 않는다(런타임이 키 부재로 "모른다"를 구분할 수 있게).
    """
    def _wavg(src: list[dict], weights: list[float], col: str) -> float | None:
        pairs = [(float(r[col]), wi) for r, wi in zip(src, weights) if not _nan(r.get(col))]
        tw = sum(wi for _, wi in pairs)
        if not pairs:
            return None
        if tw <= 0:                       # 유동이 전부 0 이면 단순평균으로 떨어진다
            return sum(v for v, _ in pairs) / len(pairs)
        return sum(v * wi for v, wi in pairs) / tw

    w = [float(r.get("flpop_tot") or 0.0) for r in rows]
    sel = [r for r in rows if not _nan(r.get("selng_tot"))]
    sw = [float(r.get("flpop_tot") or 0.0) for r in sel]

    out: dict[str, float] = {}

    def put(key: str, val: float | None, scale: float = 1.0) -> None:
        if val is not None:
            out[key] = val * scale

    for t in TMZONS:
        put(f"flpop_tmzon_{t}", _wavg(rows, w, f"flpop_tmzon_{t}_share"), 100)
        put(f"selng_tmzon_{t}", _wavg(sel, sw, f"selng_tmzon_{t}_share"), 100)
    for a in AGE_BANDS:
        put(f"agrde_{a}", _wavg(rows, w, f"flpop_agrde_{a}_share"), 100)
    put("fml_share", _wavg(rows, w, "flpop_fml_share"), 100)
    put("flpop_wkend", _wavg(rows, w, "flpop_wkend_share"), 100)
    put("selng_wkend", _wavg(sel, sw, "selng_wkend_share"), 100)
    put("frc_share", _wavg(rows, w, "stor_frc_share"), 100)
    put("opbiz_rt", _wavg(rows, w, "stor_opbiz_rt"))
    put("clsbiz_rt", _wavg(rows, w, "stor_clsbiz_rt"))
    out["stor_co"] = sum(float(r.get("stor_co") or 0.0) for r in rows)
    out["trdar_n"] = float(len(rows))
    out["trdar_selng_n"] = float(len(sel))     # 매출 근거가 몇 개 상권에서 왔는지
    return out


def _rows_for(metrics: dict[str, float]) -> list[tuple[str, str, float]]:
    """(kind, key, value) 3열 — 기존 CSV 스키마를 그대로 따른다."""
    return [(KIND, k, round(v, 2)) for k, v in metrics.items()]


def _merge_csv(path: Path, new_rows: list[tuple[str, str, float]]) -> None:
    """기존 CSV 의 demand 행만 갈아끼운다.

    **덮어쓰지 않는다** — blog_keyword·category·trend 는 다른 파이프라인의 산출물이고,
    특히 garosugil 의 trend 행은 전용 Bronze 에서만 나오므로 날리면 복구가 비싸다.
    재실행해도 demand 행이 중복되지 않도록 먼저 걸러낸 뒤 덧붙인다(멱등).
    """
    kept: list[tuple[str, str, str]] = []
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("kind") or "").startswith(KIND):
                    continue
                kept.append((r["kind"], r["key"], r["value"]))

    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "key", "value"])
        w.writerows(kept)
        w.writerows(new_rows)


def run(dry: bool = False) -> None:
    records = _load()
    if not records:
        return

    by_district: dict[str, list[dict]] = {}
    for r in records:
        slug = str(r.get("district_id") or "")
        if slug:
            by_district.setdefault(slug, []).append(r)

    written = skipped = 0
    for slug, rows in sorted(by_district.items()):
        path = GOLD / slug / "program_content_context.csv"
        if not path.exists():
            # 컨텍스트 CSV 가 없는 거점에 demand 만 있는 파일을 만들지 않는다 —
            # 키워드·업종 분포 없이 수요신호만 있으면 프롬프트가 한쪽으로 기운다.
            skipped += 1
            continue
        m = _fold(rows)
        if dry:
            gaps = [(m[f"flpop_tmzon_{t}"] - m[f"selng_tmzon_{t}"], t) for t in ACTIONABLE_TMZONS
                    if f"selng_tmzon_{t}" in m and f"flpop_tmzon_{t}" in m]
            gap = max(gaps) if gaps else (None, "매출결측")
            g = f"{gap[1]} {gap[0]:+.1f}%p" if gaps else "매출 결측 — 격차 산출 불가"
            print(f"  {slug:<18} TRDAR {int(m['trdar_n'])}개(매출 {int(m['trdar_selng_n'])}) "
                  f"· 최대격차 {g} · 여성 {m['fml_share']:.1f}% · 폐업률 {m['clsbiz_rt']:.2f}")
        else:
            _merge_csv(path, _rows_for(m))
        written += 1

    head = "[demand:dry]" if dry else "[demand]"
    print(f"{head} {written}개 거점 {'미리보기' if dry else '갱신'}"
          f"{f' · 컨텍스트 CSV 없어 건너뜀 {skipped}' if skipped else ''}")


if __name__ == "__main__":
    run(dry="--dry-run" in sys.argv)
