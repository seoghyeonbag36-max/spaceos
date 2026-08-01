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

import calendar
import datetime
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


# 광역시도·주요 시 지명. 서울 거점 질의에 이 지명이 걸리면 동명이지(同名異地) 글이다.
# "서울" 언급이 함께 있으면 비교·이동 서술일 수 있어 남긴다(예: "서울 가로수길 vs 창원").
_OFFSITE_PLACES = frozenset({
    "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "수원", "창원", "고양", "용인", "성남", "청주", "전주", "천안", "김해", "포항", "제주",
    "강릉", "여수", "경주", "안산", "안양", "평택", "시흥", "파주", "의정부", "춘천", "원주",
    "목포", "순천", "거제", "양산", "진주", "구미", "경산", "아산", "군산", "익산", "충주",
    "제천", "속초", "통영",
})


def _is_offsite(text: str, hub_terms: frozenset[str] = frozenset()) -> bool:
    """서울 거점 컨텍스트에 섞인 타 지역 글인가 (동명이지 필터).

    수집 질의를 "서울 {거점명} …"로 좁힌 것이 1차 방어고(collectors/naver_blog.py),
    이 함수는 그래도 새는 잔여분을 막는 2차 방어다. 2026-08-01 A/B 실측에서 질의 정제만으로
    오염이 30~47% → 1~3% 로 떨어졌고, 이 필터가 그 1~3% 를 마저 걷어낸다.

    판정은 두 단계다.

    1. **타지명 + 거점명 인접** — "평택시 장안동", "인천 논현동"처럼 타 시도명이 거점명
       바로 앞에 붙으면 그 거점명은 같은 이름의 다른 동네다. 동명이지의 정의 그 자체라
       서울을 함께 언급하더라도 버린다. 이 규칙이 필요한 이유: 평택 분양 광고가 본문에
       "서울·수도권"을 끼워 넣고 말미에 "평택시 장안동에 위치"를 다는 형태로 2번 규칙을
       빠져나가, jangan 상위 키워드에 '브레인시티'(평택 개발지구)가 올라와 있었다.
    2. **타지명 단독** — 거점명과 붙어 있지 않아도 타 시도명이 나오면 타 지역 글로 본다.
       단 "서울"이 함께 있으면 남긴다. 서울 상호에 지명이 들어간 경우(시청역 '진주회관',
       여의도 '진주집', 안암 '제주고깃집')를 죽이지 않기 위한 예외다.
    """
    for hub in hub_terms:
        for place in _OFFSITE_PLACES:
            if re.search(rf"{re.escape(place)}(?:특별시|광역시|시|군|구)?\s*{re.escape(hub)}", text):
                return True
    if "서울" in text:
        return False
    return any(p in text for p in _OFFSITE_PLACES)


# 한 블로거가 한 거점 키워드 집계에 넣을 수 있는 글 수 상한.
#
# 상권 프로필은 **여러 사람의 언급이 겹칠 때** 신호가 된다. 한 사람이 같은 템플릿으로 150번
# 쓴 걸 150으로 세면 그 사람의 광고가 곧 상권 프로필이 된다 — 2026-08-01 nambu 실측에서
# 한 수거업체 블로거가 386건 중 154건(40%)을 도배해 상위 키워드가 '마트배달·롯데리아배달'
# (전부 148건 동률)로 채워져 있었다. 동률 빈도는 한 템플릿이 반복됐다는 신호다.
# 3으로 잡은 이유: 진짜 동네 블로거도 한 상권에 여러 번 쓰지만 그 사람 한 명이 상위 키워드를
# 좌우해선 안 된다. 상한을 올릴수록 도배가 살아나고, 1로 내리면 표본이 얇아진다.
# 한계: 체험단처럼 **여러 계정에 분산 발행**된 광고는 이 규칙으로 못 잡는다
#       (cheongdam '조재범' 37건이 서로 다른 블로거 36명 — _PROGRAM_STOPWORDS 주석 참조).
_MAX_POSTS_PER_BLOGGER = 3


def _hub_terms(posts: list[dict]) -> frozenset[str]:
    """거점 고유 지명 — `_query`("서울 장안동 맛집")에서 광역·업종어를 뺀 나머지.

    동명이지 인접 판정(`_is_offsite`)의 기준어다. 질의에서 뽑으므로 54거점 지명을
    따로 유지하지 않는다.
    """
    generic = {"서울", "맛집", "카페", "팝업"}
    return frozenset(t for t in _query_tokens(posts) if t not in generic)


def _complete_trend_points(group: dict, end_date: str) -> list[dict]:
    """검색 트렌드에서 **미완성 마지막 달**을 잘라낸 데이터 포인트.

    데이터랩 월 단위 응답의 마지막 버킷은 수집 시점까지만 집계된 부분합이다. 그걸 그대로
    실으면 달이 끝나지 않았다는 이유만으로 급락한 것처럼 보인다 — 2026-07-18 수집분에서
    신사동 63.4→35.6(56%), 가로수길 19.1→9.9(52%)로 찍혔는데 18/31일=58% 라는
    절단 비율과 거의 같다. 즉 저 급락은 상권 신호가 아니라 집계 아티팩트다.
    이 절단값이 Program 상권 카피의 트렌드 오독(2026-08-01)의 입력이었다.

    endDate 가 그 달의 말일이면 완성된 달이므로 그대로 둔다.
    """
    points = list(group.get("data", []))
    if not points or not end_date:
        return points
    try:
        end = datetime.date.fromisoformat(end_date[:10])
    except ValueError:
        return points
    last_day = calendar.monthrange(end.year, end.month)[1]
    if end.day >= last_day:          # 달이 끝난 뒤 수집 — 자를 것 없음
        return points
    partial = f"{end.year:04d}-{end.month:02d}"
    return [p for p in points if not str(p.get("period", "")).startswith(partial)]


def _program_context_rows(posts: list[dict], places: list[dict],
                          trend: dict | None, stop: set[str]) -> list[dict]:
    """콘텐츠 컨텍스트 롱 포맷 행 생성 — 거점 단위 공통 로직.

    kind: blog_keyword(빈도 상위 50) / trend:{그룹명} / category(상위 30).
    stop 은 거점 고유 검색어(그 자체로는 신호가 아니다)와 일반 불용어의 합집합.

    블로그 글은 두 번 거른다: 동명이지 글은 `_is_offsite` 로 버리고, 남은 글의 토큰에서
    불용어를 뺀다. 트렌드는 미완성 달을 잘라낸다(`_complete_trend_points`).
    """
    rows: list[dict] = []

    tokens: Counter = Counter()
    kept = offsite = flooded = 0
    hub_terms = _hub_terms(posts)
    per_blogger: Counter = Counter()
    for p in posts:
        text = re.sub(r"<[^>]+>", "", f"{p.get('title', '')} {p.get('description', '')}")
        if _is_offsite(text, hub_terms):
            offsite += 1
            continue
        blogger = str(p.get("bloggerlink", ""))
        per_blogger[blogger] += 1
        if blogger and per_blogger[blogger] > _MAX_POSTS_PER_BLOGGER:
            flooded += 1
            continue
        kept += 1
        tokens.update(t for t in re.findall(r"[가-힣]{2,}", text) if t not in stop)
    if offsite or flooded:
        print(f"       필터: 동명이지 {offsite}건 · 도배 {flooded}건 제외 "
              f"→ {kept}/{len(posts)}건 집계")
    for kw, cnt in tokens.most_common(50):
        rows.append({"kind": "blog_keyword", "key": kw, "value": cnt})
    # TODO(Program): 감성 점수는 LLM(services/llm.py) 배치 분석으로 별도 컬럼 추가

    end_date = str((trend or {}).get("endDate", ""))
    for group in (trend or {}).get("results", []):
        for point in _complete_trend_points(group, end_date):
            rows.append({"kind": f"trend:{group.get('title', '')}",
                         "key": point.get("period", ""), "value": point.get("ratio", 0)})

    cats = Counter(str(d.get("category_name", "")).split(" > ")[-1] for d in places)
    for cat, cnt in cats.most_common(30):
        rows.append({"kind": "category", "key": cat, "value": cnt})
    return rows


def build_program_context() -> None:
    """콘텐츠 컨텍스트 — 블로그 키워드 빈도 + 검색 트렌드 + 업종 카테고리 분포 (롱 포맷).

    불용어는 platform13 경로와 같은 규칙으로 만든다: 일반 불용어 + 그 거점의 검색어 토큰
    (`_query` 에서 파생). 예전에는 여기만 {"가로수길","신사동",…} 를 손으로 적어 뒀는데,
    질의가 "서울 가로수길 …"로 바뀌면 그 목록이 조용히 낡는다.
    """
    posts = load_latest(SLUG, "naver_blog.json") or []
    stop = _PROGRAM_STOPWORDS | _query_tokens(posts) | {"신사동", "신사역"}
    rows = _program_context_rows(
        posts,
        load_latest(SLUG, "kakao_places.json") or [],
        load_latest(SLUG, "naver_datalab_trend.json") or {},
        stop,
    )
    if not rows:
        print("[gold] program_content_context: Bronze 없음 — naver_blog/kakao_local 수집 먼저")
        return
    _save(pd.DataFrame(rows), _GOLD_DIR, "program_content_context")


# 거점 무관 일반 불용어. 거점 고유어(지명·"맛집"/"카페" 등 검색어)는 하드코딩하지 않고
# 그 거점의 blog _query 에서 파생한다 — 54거점에 지명 목록을 손으로 유지하지 않기 위해서다.
#
# 2026-08-01 확장: 54거점 blog_keyword 전수를 훑어 **어느 상권에 붙여도 뜻이 같은 말**만
# 추가했다(후기·추천·좋은·실제로·방문…). 업종·분위기·메뉴처럼 상권마다 값이 다른 말은
# 남긴다 — 그게 컨텍스트의 알맹이다.
# 한계: 체험단 바이럴로 퍼진 인명·상호(cheongdam '조재범' 37건/36블로거)는 여기서 못 막는다.
#   문서빈도(11.3%)로도 블로거 집중도(1인 최대 1.8%)로도 걸러지지 않는 분산 발행이라,
#   자동 규칙을 만들면 진짜 상호명까지 함께 죽는다. 남는 한계로 둔다.
_PROGRAM_STOPWORDS = {
    "그리고", "있는", "하는", "정말", "너무",
    # 후기·추천 상투어
    "후기", "추천", "리뷰", "솔직", "방문", "다녀온", "다녀왔어요", "가봤어요", "내돈내산",
    # 평가 형용사
    "좋은", "좋아요", "맛있는", "맛있게", "괜찮은", "최고", "인생",
    # 지시·시간 부사
    "실제로", "요즘", "오늘", "어제", "이번", "여기", "저기", "거기", "그냥", "진짜", "완전",
    # 무의미 연결어
    "때문에", "위해", "함께", "같이", "많이", "조금", "다시", "바로", "가장",
    # 가게 정보 상투어 — 블로그 포스팅 양식에 늘 붙는 항목명이라 상권 변별력이 0 이다.
    # 정제 전 상위 5 를 이것들이 차지하고 있었다(garosugil '주소'(108)·'영업시간'(98) 등).
    "주소", "위치", "영업시간", "전화번호", "브레이크타임", "라스트오더", "메뉴판", "가격표",
    # 광역 지명(질의 접두어) — 서울 거점이라 변별력이 없다
    "서울",
}


def _query_tokens(posts: list[dict]) -> set[str]:
    """블로그 글의 `_query`(검색어)에서 나온 토큰 — 신호가 아니라 질의 자체다."""
    return {t for p in posts for t in re.findall(r"[가-힣]{2,}", str(p.get("_query", "")))}


def build_program13_context() -> None:
    """[Program] 54거점 콘텐츠 컨텍스트 — gold/{거점}/program_content_context.

    소스: bronze/platform13/{naver_blog,kakao_places}.json (행마다 district_id 부가됨).
    services/marketing.py 가 가게 단위 생성 시 이 파일을 상권 컨텍스트로 결합하는데,
    지금까지 garosugil 한 곳만 있어 나머지 거점은 컨텍스트 없이 생성됐다 — 그 공백을 푼다.

    ⚠️ garosugil 은 전용 Bronze(검색 트렌드 포함)로 이미 만들어진 PoC 산출물이라 건드리지
       않는다(덮어쓰기 금지 규칙). platform13 Bronze 에는 datalab 트렌드가 없어 이 경로의
       산출물에는 trend:* 행이 없다 — 키워드·업종 분포만으로도 프롬프트 컨텍스트는 선다.
    """
    posts = load_latest(SLUG13, "naver_blog.json") or []
    places = load_latest(SLUG13, "kakao_places.json") or []
    if not posts and not places:
        print("[gold] program13 context: Bronze 없음 — naver_blog/kakao_local --platform13 먼저")
        return

    by_posts: dict[str, list[dict]] = {}
    by_places: dict[str, list[dict]] = {}
    for src, dst in ((posts, by_posts), (places, by_places)):
        for row in src:
            dst.setdefault(str(row.get("district_id", "")), []).append(row)

    built = 0
    for slug in sorted(set(by_posts) | set(by_places)):
        if not slug or slug == SLUG:      # garosugil PoC gold 는 보존
            continue
        dis_posts = by_posts.get(slug, [])
        # 그 거점의 검색어 토큰은 신호가 아니라 질의 자체 — 키워드 집계에서 뺀다
        stop = _PROGRAM_STOPWORDS | _query_tokens(dis_posts)
        rows = _program_context_rows(dis_posts, by_places.get(slug, []), None, stop)
        if not rows:
            continue
        _save(pd.DataFrame(rows), GOLD / slug, "program_content_context")
        built += 1
    print(f"[gold] program13 context: {built}개 거점 생성 (garosugil 은 전용 Bronze 로 별도 유지)")


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
    build_program13_context()


if __name__ == "__main__":
    import sys

    if "--platform13" in sys.argv:
        run_platform13()
    else:
        run()
