"""[Platform·GNN] Page 건물 마스터 → 자리 단위 물리 피처 테이블.

산출: gold/features/page_building.parquet (node_id × 건물 물리 피처)

## 왜 이 피처가 필요한가 (2026-08-17 분석)

train_gnn 의 피처 95개 중 **자리마다 값이 달라지는 것은 5개뿐**이다 — dx·dy·상권중심거리·
주변밀집도·건물규모. 나머지 90개는 거점 상수(원핫 54 + TRDAR 36)라, 거점 안에서 자리를
구분하는 데 기여하지 못한다. 그래서 거점 사전분포가 원리적으로 못 맞히는 자리에서의
Top-3 회수율(**off-prior**)이 26.45% 로, 자리를 전혀 안 보는 값싼 규칙(42.42%)보다 낮다.

off-prior 를 올릴 레버로 지목된 것이 셋이고 그 첫째가 **Page 의 건물 물리 특성**이다:
편의점은 노면·저층, 병원은 층수 많은 건물 상층부, 약국은 병원 인접 — 지금 모델에는
이 중 아무 정보도 없다(`log_bld_size` 는 카카오 점포 수에서 만든 프록시일 뿐 대장이 아니다).
→ docs/finding-sequence-and-accuracy-2026-08-17.md §9

건물 단위 값은 **거점 안에서 변한다**(거점당 평균 844동). 거점 원핫이 이미 표현하는
거점 상수와 달리 새 정보가 있다.

## 누출 방지 원칙 (build_trdar_demand 와 동일)

건물 마스터의 **`industry`(대표 업종) 는 절대 쓰지 않는다** — 그 건물 점포들의 최빈 업종
이므로 곧 라벨이다. 같은 이유로 `occ_floors`·`active`·`stores` 처럼 '현재 어떤 점포가
들어와 있는가'에서 파생된 값도 라벨과 상관이 높아 제외한다. 남기는 것은 **그 자리가
공실이어도 관측 가능한** 대장·물리 속성뿐이다:

  vacancy_rate  건물 공실률 (Page 의 핵심 산출)
  capacity      수용 호수 (전유부·층별개요 기반)
  floors/height 지상층수·높이
  com_floors    상업 층 구성 — 층수·최고층·1층 포함 여부
  licensed      인허가로 층이 확인됐는가
  unknown_n     층 미상 호수 (품질 지표)

## 조인

건물은 Polygon, 카카오 노드는 점이다. 거점별로 나눠 ① 외곽 bbox 로 후보를 걸러
② ray casting 으로 포함 판정, ③ 포함하는 건물이 없으면 중심점 최근접(≤50m).
shapely 는 이 저장소에 없다 — 표준 라이브러리 + numpy 로 구현한다.

실행: python -m data.pipelines.build_page_building_features
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
_GOLD = _REPO / "data" / "gold"
_OUT = _GOLD / "features" / "page_building.parquet"

_M_PER_DEG_LAT = 111000.0
_M_PER_DEG_LON = 88300.0
_NEAREST_MAX_M = 50.0   # 이보다 멀면 '그 건물'로 보지 않는다

# 산출 피처 — 이름을 여기 고정한다(train_gnn 이 명시 목록으로 읽어 차원이 조용히 안 바뀌게)
FEATURE_COLS: list[str] = [
    "bld_vacancy_rate",      # 0~1
    "log_bld_capacity",
    "bld_floors",
    "bld_height",
    "bld_com_floor_n",
    "bld_com_floor_max",
    "bld_has_ground_floor",  # 1층이 상업층인가
    "bld_licensed",
    "log_bld_unknown_n",
    "bld_matched",           # 조인 성공 지시자 — 결측을 0 으로 채우므로 필요하다
]


def _rings(geom: dict) -> list[np.ndarray]:
    """Polygon / MultiPolygon → 외곽 링 배열 목록."""
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon":
        return [np.asarray(c[0], dtype=float)] if c else []
    if t == "MultiPolygon":
        return [np.asarray(p[0], dtype=float) for p in c if p]
    return []


def _in_ring(x: float, y: float, ring: np.ndarray) -> bool:
    """ray casting — 짝수/홀수 규칙. ring 은 (N,2) [lon,lat]."""
    xs, ys = ring[:, 0], ring[:, 1]
    xj, yj = np.roll(xs, 1), np.roll(ys, 1)
    # y 구간을 걸치는 변만 교차 후보
    straddle = (ys > y) != (yj > y)
    if not straddle.any():
        return False
    with np.errstate(divide="ignore", invalid="ignore"):
        xint = xs + (y - ys) * (xj - xs) / (yj - ys)
    return bool(np.count_nonzero(straddle & (x < xint)) % 2)


def _load_nodes() -> pd.DataFrame:
    """그래프 노드 — train_gnn.load_graph() 와 **같은 우선순위**로 집는다.

    거점별 `gold/{slug}/platform_store_graph_nodes.parquet` 는 낡은 사본이 남아 있다
    (garosugil 209행·category_group 없음). 실제 학습이 쓰는 것은 platform13 의
    40,388행이므로 여기서 그걸 집지 않으면 피처가 노드의 0.5% 에만 붙는다.
    """
    for slug in ("platform13", "garosugil"):
        p = _GOLD / slug / "platform_store_graph_nodes.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            if "district_id" in df:
                print(f"[page-feat] 노드 소스: gold/{slug} ({len(df):,}행)")
                return df
    raise SystemExit("[page-feat] 그래프 노드 없음 — build_gold 먼저 실행")


def _district_table(slug: str, nodes: pd.DataFrame) -> pd.DataFrame | None:
    gj = _GOLD / slug / "page_building_master.geojson"
    if not gj.exists() or nodes.empty:
        return None

    feats = json.loads(gj.read_text(encoding="utf-8")).get("features") or []
    rings, props, bbox, cen = [], [], [], []
    for f in feats:
        rs = _rings(f.get("geometry") or {})
        if not rs:
            continue
        r = max(rs, key=len)      # 대표 링(가장 점이 많은 것)
        rings.append(r)
        props.append(f.get("properties") or {})
        bbox.append((r[:, 0].min(), r[:, 0].max(), r[:, 1].min(), r[:, 1].max()))
        cen.append((r[:, 0].mean(), r[:, 1].mean()))
    if not rings:
        return None

    bb = np.asarray(bbox)          # (B,4) lon_min, lon_max, lat_min, lat_max
    cc = np.asarray(cen)           # (B,2)

    rows = []
    for nid, lon, lat in nodes[["node_id", "lon", "lat"]].itertuples(index=False):
        lon, lat = float(lon), float(lat)
        cand = np.flatnonzero((bb[:, 0] <= lon) & (lon <= bb[:, 1])
                              & (bb[:, 2] <= lat) & (lat <= bb[:, 3]))
        hit = -1
        for b in cand:
            if _in_ring(lon, lat, rings[b]):
                hit = int(b)
                break
        if hit < 0:
            dy = (cc[:, 1] - lat) * _M_PER_DEG_LAT
            dx = (cc[:, 0] - lon) * _M_PER_DEG_LON
            d = np.sqrt(dx * dx + dy * dy)
            b = int(np.argmin(d))
            if d[b] <= _NEAREST_MAX_M:
                hit = b
        rows.append({"node_id": nid, "district_id": slug,
                     **_props_to_feats(props[hit] if hit >= 0 else None)})
    return pd.DataFrame(rows)


def _props_to_feats(p: dict | None) -> dict[str, float]:
    """건물 속성 → 피처. p 가 None(미조인)이면 전부 0 + bld_matched=0.

    ⚠ `industry`·`occ_floors`·`active`·`stores` 는 쓰지 않는다 — 현재 입주 업종에서
      파생된 값이라 라벨 누출이다(모듈 docstring 의 누출 방지 원칙).
    """
    if not p:
        return {c: 0.0 for c in FEATURE_COLS}
    com = [int(f) for f in (p.get("com_floors") or []) if isinstance(f, (int, float))]
    vac = p.get("vacancy_rate")
    return {
        "bld_vacancy_rate": (float(vac) / 100.0) if vac is not None else 0.0,
        "log_bld_capacity": float(np.log1p(max(0.0, float(p.get("capacity") or 0)))),
        "bld_floors": float(p.get("floors") or 0),
        "bld_height": float(p.get("height") or 0),
        "bld_com_floor_n": float(len(com)),
        "bld_com_floor_max": float(max(com)) if com else 0.0,
        "bld_has_ground_floor": 1.0 if 1 in com else 0.0,
        "bld_licensed": float(p.get("licensed") or 0),
        "log_bld_unknown_n": float(np.log1p(max(0.0, float(p.get("unknown_n") or 0)))),
        "bld_matched": 1.0,
    }


def build() -> pd.DataFrame:
    nodes = _load_nodes()
    parts = []
    for s, grp in nodes.groupby(nodes["district_id"].fillna("").astype(str)):
        t = _district_table(s, grp)
        if t is not None and len(t):
            parts.append(t)
            print(f"[page-feat] {s:<18} 노드 {len(t):5d} · 조인 "
                  f"{t['bld_matched'].mean():6.1%}")
    if not parts:
        raise SystemExit("[page-feat] 산출물 없음 — page_building_master.geojson 확인")
    df = pd.concat(parts, ignore_index=True)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_OUT, index=False)
    print(f"\n[page-feat] {_OUT.relative_to(_REPO)} · {len(df):,}행 × "
          f"{len(FEATURE_COLS)}피처 · 전체 조인율 {df['bld_matched'].mean():.1%}")
    return df


if __name__ == "__main__":
    build()
