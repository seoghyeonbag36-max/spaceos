"""Gold 빌더 — B단계 Bronze → Silver 정제 → 기능별 Gold 테이블 (docs §9).

산출 (parquet 권장, pyarrow 없으면 csv 폴백):
  gold/garosugil/platform_district_timeseries   Platform·LSTM — 상권×분기 피처
  gold/garosugil/platform_store_graph_nodes     Platform·GNN — 노드 (엣지는 TODO)
  gold/garosugil/posting_cost_benefit           Posting — 업종×전략 (비용 컬럼 TODO)
  gold/garosugil/program_content_context        Program — 리뷰 키워드·트렌드·카테고리

선행: 수집기 실행으로 Bronze 를 채운다.
  python -m data.collectors.seoul_trdar
  python -m data.collectors.localdata
  python -m data.collectors.kakao_local
  python -m data.collectors.naver_blog

실행: python -m data.pipelines.build_gold
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

from data.collectors.common import GOLD, SILVER, load_latest
from data.config.garosugil import SLUG
from data.config.platform_districts import DISTRICT_TRDAR, SLUG as SLUG13

_GOLD_DIR = GOLD / SLUG
_SILVER_DIR = SILVER / SLUG

# Posting 3전략 — services/posting.py 와 동일 명칭 유지
_STRATEGIES = ("고급화", "가성비", "기능중심")


def _save(df: "pd.DataFrame", root: Path, name: str) -> None:
    """parquet 저장, pyarrow/fastparquet 없으면 csv 폴백."""
    root.mkdir(parents=True, exist_ok=True)
    try:
        path = root / f"{name}.parquet"
        df.to_parquet(path, index=False)
    except Exception:
        path = root / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"[gold] {path.name}: {len(df)}행 × {len(df.columns)}열")


def _quarter_of(ymd: str) -> str:
    """'YYYYMMDD…' → 'YYYYQ' (서울 상권분석 STDR_YYQU_CD 형식에 맞춤)."""
    s = re.sub(r"\D", "", str(ymd))
    if len(s) < 6:
        return ""
    return f"{s[:4]}{(int(s[4:6]) - 1) // 3 + 1}"


def build_platform_timeseries() -> None:
    """상권×분기 피처 테이블 — LSTM 입력 (ml/training/datasets.py 가 읽는다)."""
    selng = load_latest(SLUG, "seoul_trdar_selng.json")
    stor = load_latest(SLUG, "seoul_trdar_stor.json")
    if not selng and not stor:
        print("[gold] platform_district_timeseries: Bronze 없음 — seoul_trdar 수집 먼저")
        return

    frames = []
    if selng:
        df = pd.json_normalize(selng)
        # 업종 행 → 상권×분기 합계 매출 (필드명은 [미리보기] 확정치로 조정 TODO)
        cols = [c for c in ("STDR_YYQU_CD", "TRDAR_CD", "TRDAR_CD_NM") if c in df.columns]
        if cols and "THSMON_SELNG_AMT" in df.columns:
            g = (df.assign(THSMON_SELNG_AMT=pd.to_numeric(df["THSMON_SELNG_AMT"], errors="coerce"))
                   .groupby(cols, as_index=False)["THSMON_SELNG_AMT"].sum()
                   .rename(columns={"THSMON_SELNG_AMT": "selng_amt"}))
            frames.append(g)
    if stor:
        df = pd.json_normalize(stor)
        cols = [c for c in ("STDR_YYQU_CD", "TRDAR_CD") if c in df.columns]
        agg = {c: "sum" if c == "STOR_CO" else "mean"
               for c in ("STOR_CO", "OPBIZ_RT", "CLSBIZ_RT") if c in df.columns}
        if cols and agg:
            g = df.copy()
            for c in agg:
                g[c] = pd.to_numeric(g[c], errors="coerce")
            g = g.groupby(cols, as_index=False).agg(agg).rename(
                columns={"STOR_CO": "stor_co", "OPBIZ_RT": "opbiz_rt", "CLSBIZ_RT": "clsbiz_rt"})
            frames.append(g)

    if not frames:
        print("[gold] platform_district_timeseries: 예상 필드 없음 — 서비스 필드명 확인 필요")
        return
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on=[c for c in ("STDR_YYQU_CD", "TRDAR_CD") if c in f.columns], how="outer")

    # LOCALDATA 폐업 건수를 분기로 집계해 라벨 보조 컬럼으로 결합
    biz = load_latest(SLUG, "localdata_biz.json")
    if biz:
        closures = Counter(_quarter_of(r.get("dcbYmd", "")) for r in biz if r.get("dcbYmd"))
        closures.pop("", None)
        out["closure_cnt"] = out["STDR_YYQU_CD"].map(closures).fillna(0).astype(int)

    # TODO(§9): 생활인구(§2)·부동산원 공실률/임대료(§4)·SGIS 인구밀도(§3) 조인
    _save(out, _GOLD_DIR, "platform_district_timeseries")


def build_platform13_timeseries() -> None:
    """[Platform·LSTM] 거점×분기 피처 테이블 — gold/platform13/platform_district_timeseries.

    소스: bronze/platform13/seoul_trdar_{stor,selng}.json (collect_platform13 산출,
    행마다 district_id 부가됨). 집계 규칙:
      selng_amt  분기 추정매출 합(거점 내 상권×업종 전체)
      stor_co    분기 점포수 합
      opbiz_rt / clsbiz_rt  개업률/폐업률 — 점포수(STOR_CO) 가중 평균
      n_trdar    해당 분기에 데이터가 있는 상권코드 수 (커버리지 지표)
      flpop                길단위(유동)인구 분기 합 — seoul_trdar flpop 수집분
      vac_small / vac_mid  R-ONE 소규모/중대형 상가 공실률(%) — rone_rent 수집분
      rent_small           R-ONE 소규모 상가 임대료(천원/㎡)
    ⚠️ garosugil PoC gold 와 별개 신규 산출물 (덮어쓰기 아님).
    ⚠️ R-ONE 은 표본개편(2024Q3)·공유 상권 매핑(config/rone_districts.py 주석) 유의.
    """
    stor = load_latest(SLUG13, "seoul_trdar_stor.json")
    selng = load_latest(SLUG13, "seoul_trdar_selng.json")
    if not stor:
        print("[gold] platform13 timeseries: Bronze 없음 — seoul_trdar --platform13 수집 먼저")
        return

    sdf = pd.json_normalize(stor)
    for c in ("STOR_CO", "OPBIZ_RT", "CLSBIZ_RT"):
        sdf[c] = pd.to_numeric(sdf.get(c), errors="coerce")
    sdf["_w"] = sdf["STOR_CO"].fillna(0).clip(lower=1)  # 가중치 0 방지

    def _agg_stor(g: "pd.DataFrame") -> "pd.Series":
        w = g["_w"]
        return pd.Series({
            "stor_co": g["STOR_CO"].sum(),
            "opbiz_rt": (g["OPBIZ_RT"] * w).sum() / w.sum(),
            "clsbiz_rt": (g["CLSBIZ_RT"] * w).sum() / w.sum(),
            "n_trdar": g["TRDAR_CD"].nunique(),
        })

    out = (sdf.groupby(["district_id", "STDR_YYQU_CD"])
              .apply(_agg_stor, include_groups=False).reset_index()
              .rename(columns={"STDR_YYQU_CD": "quarter"}))

    if selng:
        edf = pd.json_normalize(selng)
        edf["THSMON_SELNG_AMT"] = pd.to_numeric(edf.get("THSMON_SELNG_AMT"), errors="coerce")
        g = (edf.groupby(["district_id", "STDR_YYQU_CD"], as_index=False)["THSMON_SELNG_AMT"].sum()
                .rename(columns={"STDR_YYQU_CD": "quarter", "THSMON_SELNG_AMT": "selng_amt"}))
        out = out.merge(g, on=["district_id", "quarter"], how="left")

    # 길단위(유동)인구 조인 — seoul_trdar --platform13-flpop 수집분 (거점 내 상권 합)
    flpop = load_latest(SLUG13, "seoul_trdar_flpop.json")
    if flpop:
        fdf = pd.json_normalize(flpop)
        fdf["TOT_FLPOP_CO"] = pd.to_numeric(fdf.get("TOT_FLPOP_CO"), errors="coerce")
        g = (fdf.groupby(["district_id", "STDR_YYQU_CD"], as_index=False)["TOT_FLPOP_CO"].sum()
                .rename(columns={"STDR_YYQU_CD": "quarter", "TOT_FLPOP_CO": "flpop"}))
        out = out.merge(g, on=["district_id", "quarter"], how="left")
    else:
        print("[gold] platform13: seoul_trdar_flpop 없음 — flpop 수집 시 조인")

    # 상권변화지표 조인 — 평균 운영/폐업 영업개월 (연속형, 거점 내 상권 평균)
    ix = load_latest(SLUG13, "seoul_trdar_ix.json")
    if ix:
        xdf = pd.json_normalize(ix)
        for c in ("OPR_SALE_MT_AVRG", "CLS_SALE_MT_AVRG"):
            xdf[c] = pd.to_numeric(xdf.get(c), errors="coerce")
        g = (xdf.groupby(["district_id", "STDR_YYQU_CD"], as_index=False)
                [["OPR_SALE_MT_AVRG", "CLS_SALE_MT_AVRG"]].mean()
                .rename(columns={"STDR_YYQU_CD": "quarter",
                                 "OPR_SALE_MT_AVRG": "ix_opr_mt",
                                 "CLS_SALE_MT_AVRG": "ix_cls_mt"}))
        out = out.merge(g, on=["district_id", "quarter"], how="left")
    else:
        print("[gold] platform13: seoul_trdar_ix 없음 — income-ix 수집 시 조인")

    # R-ONE 공실률·임대료 조인 (rone_rent 수집분 — 없으면 건너뜀)
    for series, col in (("vac_small", "vac_small"), ("vac_mid", "vac_mid"),
                        ("rent_small", "rent_small")):
        rone = load_latest(SLUG13, f"rone_{series}.json")
        if not rone:
            print(f"[gold] platform13: rone_{series} 없음 — rone_rent 수집 시 조인")
            continue
        rdf = (pd.json_normalize(rone)[["district_id", "quarter", "value"]]
                 .rename(columns={"value": col}))
        rdf[col] = pd.to_numeric(rdf[col], errors="coerce")
        rdf = rdf.groupby(["district_id", "quarter"], as_index=False)[col].mean()
        out = out.merge(rdf, on=["district_id", "quarter"], how="left")

    out = out.sort_values(["district_id", "quarter"]).reset_index(drop=True)

    # 커버리지 검증 — 매핑된 거점 전부 포함 여부 (미포함 거점은 경고)
    got = set(out["district_id"].unique())
    missing = sorted(set(DISTRICT_TRDAR) - got)
    q_min, q_max = out["quarter"].min(), out["quarter"].max()
    print(f"[gold] platform13 커버리지: 거점 {len(got)}/{len(DISTRICT_TRDAR)}, 분기 {q_min}~{q_max}")
    for did in sorted(got):
        n = (out["district_id"] == did).sum()
        print(f"  {did}: {n}분기")
    if missing:
        print(f"  [경고] 시계열 미포함 거점: {missing}")

    _save(out, GOLD / SLUG13, "platform_district_timeseries")


def build_platform13_store_graph_nodes() -> None:
    """[Platform·GNN] 거점 점포 노드 — kakao_local --platform13 수집분.

    gold/platform13/platform_store_graph_nodes.parquet (district_id 포함).
    가로수길 단일 거점 노드(gold/garosugil)와 별개 신규 산출물.
    """
    places = load_latest(SLUG13, "kakao_places.json")
    if not places:
        print("[gold] platform13 graph nodes: Bronze 없음 — kakao_local --platform13 먼저")
        return
    rows = [{
        "node_id": f"kakao:{d.get('id', '')}",
        "name": d.get("place_name", ""),
        "category": d.get("category_name", ""),
        # GNN 분류 라벨 — 우리가 수집한 7개 카테고리 그룹(음식점/카페/편의점/병원/약국/
        # 숙박/문화시설). category_name 의 1단계는 다른 분류체계(카페가 음식점 하위로
        # 접혀 음식점 78%)라 라벨로 부적합 — category_group_name 이 균형 잡힌 대분류다.
        "category_group": d.get("category_group_name", ""),
        "lon": d.get("x"), "lat": d.get("y"),
        # 동일 건물 엣지(build_store_graph_edges)의 그룹 키 — 지번(address_name)은
        # 같은 건물에도 표기가 갈려 도로명을 쓴다(카카오 보유율 99.6%)
        "road_address": d.get("road_address_name", ""),
        "place_url": d.get("place_url", ""),
        "district_id": d.get("district_id", ""),
        "source": "kakao",
    } for d in places]
    df = pd.DataFrame(rows)
    per = df.groupby("district_id").size()
    print(f"[gold] platform13 graph nodes: {len(df)}노드 / 거점 {per.index.nunique()}곳"
          f" (최소 {per.min()} · 최대 {per.max()})")
    _save(df, GOLD / SLUG13, "platform_store_graph_nodes")


def build_store_graph_nodes() -> None:
    """GNN 노드 테이블 — 카카오 현존 점포 + LOCALDATA 인허가를 소스 표기와 함께 통합."""
    rows: list[dict] = []
    for d in load_latest(SLUG, "kakao_places.json") or []:
        rows.append({
            "node_id": f"kakao:{d.get('id', '')}",
            "name": d.get("place_name", ""),
            "category": d.get("category_name", ""),
            "lon": d.get("x"), "lat": d.get("y"),
            "place_url": d.get("place_url", ""),
            "source": "kakao",
        })
    for r in load_latest(SLUG, "localdata_biz.json") or []:
        rows.append({
            "node_id": f"localdata:{r.get('mgtNo', '')}",
            "name": r.get("bplcNm", ""),
            "category": r.get("uptaeNm", ""),
            "lon": r.get("lon"), "lat": r.get("lat"),
            "place_url": "",
            "source": "localdata",
        })
    if not rows:
        print("[gold] platform_store_graph_nodes: Bronze 없음 — kakao_local/localdata 수집 먼저")
        return
    df = pd.DataFrame(rows)
    # TODO(GNN): 엣지 생성 — 공간 근접(kNN/PostGIS)·고객 공유·리뷰 유사도. §1-A bizesId 와
    # 좌표/상호 매칭으로 노드 통합(entity resolution)도 Silver 단계 과제.
    _save(df, _GOLD_DIR, "platform_store_graph_nodes")


def build_posting_cost_benefit() -> None:
    """업종×전략 비용-효용 골격 — 매출은 상권분석 실측, 비용 컬럼은 가맹정보 연동 TODO."""
    selng = load_latest(SLUG, "seoul_trdar_selng.json")
    if not selng:
        print("[gold] posting_cost_benefit: Bronze 없음 — seoul_trdar 수집 먼저")
        return
    df = pd.json_normalize(selng)
    if "SVC_INDUTY_CD_NM" not in df.columns or "THSMON_SELNG_AMT" not in df.columns:
        print("[gold] posting_cost_benefit: 예상 필드 없음 — 서비스 필드명 확인 필요")
        return
    df["THSMON_SELNG_AMT"] = pd.to_numeric(df["THSMON_SELNG_AMT"], errors="coerce")
    base = (df.groupby("SVC_INDUTY_CD_NM", as_index=False)["THSMON_SELNG_AMT"].mean()
              .rename(columns={"SVC_INDUTY_CD_NM": "industry", "THSMON_SELNG_AMT": "expected_revenue"}))
    out = base.merge(pd.DataFrame({"strategy": _STRATEGIES}), how="cross")
    # TODO(§8-C): 공정위 가맹정보 API에서 가맹금·인테리어 단가 → initial_cost 산출
    # TODO(§4): 부동산원 임대료 × 기준면적 → monthly_fixed 산출 → roi_months 계산
    out["initial_cost"] = None
    out["monthly_fixed"] = None
    out["roi_months"] = None
    _save(out, _GOLD_DIR, "posting_cost_benefit")


def build_program_context() -> None:
    """콘텐츠 컨텍스트 — 블로그 키워드 빈도 + 검색 트렌드 + 업종 카테고리 분포 (롱 포맷)."""
    rows: list[dict] = []

    posts = load_latest(SLUG, "naver_blog.json") or []
    tokens: Counter = Counter()
    stop = {"가로수길", "신사동", "신사역", "그리고", "있는", "하는", "정말", "너무"}
    for p in posts:
        text = re.sub(r"<[^>]+>", "", f"{p.get('title', '')} {p.get('description', '')}")
        tokens.update(t for t in re.findall(r"[가-힣]{2,}", text) if t not in stop)
    for kw, cnt in tokens.most_common(50):
        rows.append({"kind": "blog_keyword", "key": kw, "value": cnt})
    # TODO(Program): 감성 점수는 LLM(services/llm.py) 배치 분석으로 별도 컬럼 추가

    trend = load_latest(SLUG, "naver_datalab_trend.json") or {}
    for group in trend.get("results", []):
        for point in group.get("data", []):
            rows.append({"kind": f"trend:{group.get('title', '')}",
                         "key": point.get("period", ""), "value": point.get("ratio", 0)})

    places = load_latest(SLUG, "kakao_places.json") or []
    cats = Counter(str(d.get("category_name", "")).split(" > ")[-1] for d in places)
    for cat, cnt in cats.most_common(30):
        rows.append({"kind": "category", "key": cat, "value": cnt})

    if not rows:
        print("[gold] program_content_context: Bronze 없음 — naver_blog/kakao_local 수집 먼저")
        return
    _save(pd.DataFrame(rows), _GOLD_DIR, "program_content_context")


def run() -> None:
    if pd is None:
        print("pandas 필요: pip install pandas pyarrow")
        return
    _SILVER_DIR.mkdir(parents=True, exist_ok=True)
    build_platform_timeseries()
    build_platform13_timeseries()
    build_store_graph_nodes()
    build_posting_cost_benefit()
    build_program_context()


def run_platform13() -> None:
    """platform13 산출물만 갱신 — garosugil PoC gold 는 건드리지 않는다 (덮어쓰기 금지 규칙)."""
    if pd is None:
        print("pandas 필요: pip install pandas pyarrow")
        return
    build_platform13_timeseries()
    build_platform13_store_graph_nodes()


if __name__ == "__main__":
    import sys

    if "--platform13" in sys.argv:
        run_platform13()
    else:
        run()
