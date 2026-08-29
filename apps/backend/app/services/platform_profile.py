"""Platform·상권 정체성 — "이 상권은 어떤 플랫폼인가" 와 "어느 자리에 무엇이 들어와야 하나".

Platform 트랙의 본질은 모델 지표가 아니다. 답해야 하는 것은 둘이다:

  ① **이 상권은 어떤 플랫폼인가** — 무엇이 모여 있고(업종 구성), 누가 오고(연령·성별),
     언제 오고(시간대·주말), 밖에서 뭐라고 말하며(블로그 키워드), 어디로 가고 있나
     (검색 트렌드·개폐업률).
  ② **그 플랫폼 안 어느 자리에 어떤 업소가 들어오면 좋은가** — 실측 공실 인벤토리의
     자리마다 GNN 최근접 노드 추천을 붙인다.

LSTM 예측·GNN 성능 지표는 이 두 답을 **뒷받침하는 근거**이지 답 자체가 아니다
(2026-08-29 방향 확정).

## 입력 — 전부 이미 있는 산출물이다. 새로 수집하지 않았다

| 재료 | 파일 | 비고 |
|---|---|---|
| 블로그 키워드·검색 트렌드·업종 분포·수요신호 | `gold/{거점}/program_content_context.csv` | Program 이 쓰던 것을 Platform 이 같이 본다 |
| 공실 자리 | `gold/{거점}/vacant_units.json` | Posting 인벤토리(services/vacant_inventory) |
| 자리별 업종 추천 | `gold/platform_industry_recommend.json` | GNN(services/industry_recommend) |

CSV 파서는 `services/marketing` 에 한 벌만 둔다 — 두 벌이 되면 인코딩·결측 규칙이
조용히 갈린다(marketing 의 로더 주석 참조).

## 하지 않는 것

- **직전 업종과 추천 업종을 자동으로 비교해 "업종 전환"이라고 판정하지 않는다.**
  직전 업종은 상가정보 분류(`비알코올` 등), 추천은 GNN 7군(`카페`·`음식점` 등)이라
  눈금이 다르다. 둘을 나란히 보여주고 판단은 사람에게 남긴다.
- 감성은 여기 없다. 리뷰 수집 미착수라 전부 시드이고(`/{거점}/sentiment`),
  정체성의 근거로 쓰면 지어낸 성격을 상권에 붙이게 된다.
"""
from __future__ import annotations

from app.services import industry_recommend, marketing, vacant_inventory

# 카카오 플레이스 업종(말단 라벨)을 사람이 읽는 군으로 묶는 규칙.
# 부분문자열 우선순위 매칭이라 **순서가 규칙의 일부다** — 위에서 먼저 걸리면 끝난다.
# 라벨 체계가 카카오 것이라 브랜드명("CU")이나 상호("후라토식당")가 섞여 들어오는데,
# 억지로 분류하지 않고 걸리지 않으면 '기타'로 남겨 화면에 그대로 드러낸다.
_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("카페·디저트", ("카페", "커피", "디저트", "베이커리", "제과", "빙수", "아이스크림", "브런치")),
    ("주점·야간", ("호프", "주점", "술집", "포차", "와인", "이자카야", "맥주", "바텐더")),
    ("음식점", ("한식", "일식", "중식", "양식", "분식", "치킨", "피자", "고기", "국수",
              "해물", "뷔페", "돈까스", "스테이크", "족발", "곱창", "포케", "음식", "식당",
              "면요리", "덮밥", "카레")),
    ("의료·뷰티", ("의원", "병원", "외과", "내과", "치과", "한의", "약국", "네일", "미용",
                "헤어", "에스테틱", "피부", "성형", "왁싱", "스파", "부인과", "안과",
                "이비인후", "비뇨", "소아", "정신건강", "재활", "요양", "검진")),
    ("문화·전시", ("전시", "미술", "공연", "극장", "박물", "갤러리", "서점", "도서")),
    ("숙박", ("호텔", "모텔", "여관", "게스트하우스", "숙박", "펜션", "레지던스")),
    ("생활·편의", ("편의점", "CU", "GS25", "세븐일레븐", "이마트", "마트", "슈퍼",
                "세탁", "은행", "약수터", "우체국")),
    ("패션·리테일", ("의류", "패션", "신발", "가방", "쇼핑", "백화점", "화장품", "잡화",
                  "안경", "주얼리", "액세서리", "편집")),
    ("교육·오피스", ("학원", "교육", "사무", "오피스", "스터디", "독서실")),
    ("여가·스포츠", ("헬스", "필라테스", "요가", "골프", "클라이밍", "스포츠", "당구",
                 "노래", "PC방", "볼링")),
]

# 정체성 판정 임계 — 최대 군이 이 비중을 넘으면 '중심형', 아니면 상위 2군 '복합형'.
_DOMINANT_SHARE = 0.40

# 표시용 2차 불용어. 파이프라인에도 불용어가 있지만(build_gold._program_context_rows)
# 상위 50 에 일반어가 남는다("매일"·"있습니다"·"다양한"). 여기서 **거르되 몇 개를
# 걸렀는지 응답에 밝힌다** — 조용히 지우면 화면의 빈도 순위가 원문과 달라진 것을 알 수 없다.
# ⚠ 지역·업종·감성 어휘는 절대 넣지 말 것("신사"·"디저트"·"감성"은 그 자체가 정체성 신호다).
_DISPLAY_STOP = frozenset({
    "다음", "매일", "정보", "시간", "있습니다", "있어서", "다양한", "먹고", "지하", "층에",
    "그리고", "하지만", "위치", "오늘", "저는", "제가", "같아요", "합니다", "이번", "가서",
    "해서", "너무", "진짜", "정말", "여기", "거기", "조금", "많이", "하는", "하고", "되는",
    "에서", "으로", "이라", "라고", "서울의", "있는", "많은", "대한", "때문", "생각",
})

_AGE_LABEL = {
    "agrde_10": "10대", "agrde_20": "20대", "agrde_30": "30대",
    "agrde_40": "40대", "agrde_50": "50대", "agrde_60_above": "60대 이상",
}
# 시간대 라벨·행동 가능 구간은 marketing 과 같은 값을 쓴다(같은 TRDAR 6구간이다).
_TMZON_LABEL = marketing._TMZON_LABEL
_ACTIONABLE = marketing._ACTIONABLE_TMZONS


def group_of(category: str) -> str | None:
    """업종 라벨 → 군. 어느 규칙에도 안 걸리면 None(= 기타)."""
    for name, needles in _GROUPS:
        if any(n in category for n in needles):
            return name
    return None


def _categories(rows: list[tuple[str, str, float]]) -> dict:
    """업종 분포를 군으로 묶는다. 군마다 **어떤 라벨이 들어갔는지 같이 싣는다** —
    묶음이 근거를 가리면 안 되므로 화면에서 펼쳐 볼 수 있어야 한다."""
    cats = [(k, v) for kd, k, v in rows if kd == "category"]
    if not cats:
        return {"groups": [], "ungrouped": [], "total": 0}

    buckets: dict[str, list[tuple[str, float]]] = {}
    ungrouped: list[tuple[str, float]] = []
    for label, n in cats:
        g = group_of(label)
        if g:
            buckets.setdefault(g, []).append((label, n))
        else:
            ungrouped.append((label, n))
    total = sum(v for _, v in cats)
    groups = [
        {
            "group": g,
            "n": round(sum(v for _, v in members)),
            "share": round(sum(v for _, v in members) / total, 4) if total else 0.0,
            "members": [{"label": lb, "n": round(v)}
                        for lb, v in sorted(members, key=lambda kv: -kv[1])],
        }
        for g, members in buckets.items()
    ]
    groups.sort(key=lambda g: -g["n"])
    return {
        "groups": groups,
        "ungrouped": [{"label": lb, "n": round(v)}
                      for lb, v in sorted(ungrouped, key=lambda kv: -kv[1])],
        "total": round(total),
    }


def _archetype(groups: list[dict]) -> tuple[str | None, str]:
    """상권 유형 한 줄 + 그 판정 규칙. 근거가 없으면 라벨을 만들지 않는다."""
    rule = (f"카카오 플레이스 업종 라벨을 {len(_GROUPS)}개 군으로 묶어, "
            f"최대 군 비중이 {int(_DOMINANT_SHARE * 100)}% 이상이면 '중심형', "
            f"아니면 상위 2군 '복합형'으로 적는다")
    if not groups:
        return None, rule
    top = groups[0]
    if top["share"] >= _DOMINANT_SHARE or len(groups) == 1:
        return f"{top['group']} 중심형", rule
    return f"{top['group']}·{groups[1]['group']} 복합형", rule


def _keywords(rows: list[tuple[str, str, float]], limit: int = 24) -> dict:
    """블로그 언급 키워드 — 이 상권이 밖에서 어떻게 불리는지."""
    kws = [(k, v) for kd, k, v in rows if kd == "blog_keyword"]
    kept = [(k, v) for k, v in kws if k not in _DISPLAY_STOP]
    kept.sort(key=lambda kv: -kv[1])
    return {
        "words": [{"word": k, "n": round(v)} for k, v in kept[:limit]],
        "dropped": len(kws) - len(kept),
        "scanned": len(kws),
    }


def _trends(rows: list[tuple[str, str, float]]) -> list[dict]:
    """검색 트렌드 방향 — 최근 3개월 평균 vs 직전 3개월 평균.

    판정 규칙과 임계(±5%)는 `marketing._trend_summary` 와 **같은 값**을 쓴다.
    두 화면이 같은 계열을 두고 다른 방향을 말하면 안 된다.
    """
    series: dict[str, list[tuple[str, float]]] = {}
    for kd, k, v in rows:
        if kd.startswith("trend:"):
            series.setdefault(kd.split(":", 1)[1], []).append((k, v))

    out: list[dict] = []
    for name, points in series.items():
        vals = [v for _, v in sorted(points, key=lambda kv: kv[0])][-6:]
        if len(vals) < 6:
            continue                      # 6점 미만이면 방향을 만들지 않는다
        prior, recent = sum(vals[:3]) / 3, sum(vals[3:]) / 3
        if prior <= 0:
            continue
        change = (recent - prior) / prior
        out.append({
            "keyword": name,
            "prior": round(prior, 1),
            "recent": round(recent, 1),
            "change_pct": round(change * 100, 1),
            "direction": ("flat" if abs(change) < marketing._TREND_FLAT_BAND
                          else "up" if change > 0 else "down"),
            "points": [{"period": p, "value": round(v, 2)}
                       for p, v in sorted(points, key=lambda kv: kv[0])],
        })
    out.sort(key=lambda t: t["keyword"])
    return out


def _demand(rows: list[tuple[str, str, float]]) -> dict:
    """누가·언제 오는가 (TRDAR 상권 수요신호)."""
    d = {k: v for kd, k, v in rows if kd == "demand"}
    if not d:
        return {}

    bands = [
        {"band": t, "label": _TMZON_LABEL[t],
         "flpop": d[f"flpop_tmzon_{t}"], "selng": d.get(f"selng_tmzon_{t}"),
         "gap": (round(d[f"flpop_tmzon_{t}"] - d[f"selng_tmzon_{t}"], 2)
                 if f"selng_tmzon_{t}" in d else None)}
        for t in _TMZON_LABEL if f"flpop_tmzon_{t}" in d
    ]
    actionable = [b for b in bands if b["band"] in _ACTIONABLE]
    ages = [{"band": _AGE_LABEL[k], "share": d[k]} for k in _AGE_LABEL if k in d]

    return {
        "bands": bands,
        # 사람이 가장 많은 시간대 / 유동 대비 매출이 가장 빈 시간대.
        # 00~06 은 뺀다 — 심야 격차는 상권의 빈틈이 아니라 가게가 닫혀 있어서다.
        "peak_band": (max(actionable, key=lambda b: b["flpop"])["band"]
                      if actionable else None),
        "gap_band": marketing._gap_band(rows),
        "ages": ages,
        "female_share": d.get("fml_share"),
        "weekend_flpop": d.get("flpop_wkend"),
        "weekend_selng": d.get("selng_wkend"),
        "store_count": d.get("stor_co"),
        "franchise_share": d.get("frc_share"),
        "open_rate": d.get("opbiz_rt"),
        "close_rate": d.get("clsbiz_rt"),
        "trdar_n": d.get("trdar_n"),
    }


def identity(district_id: str) -> dict | None:
    """이 상권이 어떤 플랫폼인지 — Gold 컨텍스트 미적재면 None."""
    rows = marketing.context_rows(district_id)
    if rows is None:
        return None
    cats = _categories(rows)
    archetype, rule = _archetype(cats["groups"])
    return {
        "archetype": archetype,
        "archetype_rule": rule,
        "categories": cats,
        "keywords": _keywords(rows),
        "trends": _trends(rows),
        "demand": _demand(rows),
        "source": ("카카오 플레이스(업종) · 네이버 블로그(키워드) · 네이버 데이터랩"
                   "(검색 트렌드) · 서울 상권분석 TRDAR(수요신호) — "
                   "gold/{거점}/program_content_context.csv"),
    }


def _district_means(district_id: str) -> dict[str, float]:
    """상권 전체 노드의 업종별 평균 확률 — 자리별 추천을 **상권 평균과 견주기** 위한 기준선.

    ⚠ 근사다. 산출물은 노드마다 Top-3 만 싣고 있어 그 밖 업종은 0 으로 본다. 그래서
    이 평균은 실제보다 조금 낮고, 아래 `delta` 는 조금 높게 나온다. 순위를 가리는
    용도(어느 업종이 이 자리에서 상권 평균보다 두드러지나)로만 쓰고 절대값으로 읽지 않는다.

    왜 필요한가 — GNN Top-1 은 상권 사전확률에 눌려 거의 모든 자리가 같은 답("음식점")을
    낸다. 그대로 늘어놓으면 "어느 자리에 무엇"이 아니라 "모든 자리에 같은 것"이 된다.
    상권 평균을 빼면 그 자리만의 신호가 남는다.
    """
    data = industry_recommend._load() or {}
    nodes = (data.get("districts") or {}).get(district_id) or {}
    if not nodes:
        return {}
    agg: dict[str, float] = {}
    for item in nodes.values():
        for t in item.get("top", []):
            agg[t["industry"]] = agg.get(t["industry"], 0.0) + t["score"]
    n = len(nodes)
    return {k: v / n for k, v in agg.items()}


def _distinct(recs: list[dict], means: dict[str, float]) -> dict | None:
    """이 자리에서 상권 평균 대비 가장 두드러지는 업종. 기준선이 없으면 None."""
    if not recs or not means:
        return None
    best = max(recs, key=lambda r: r["score"] - means.get(r["industry"], 0.0))
    mean = means.get(best["industry"], 0.0)
    return {
        "industry": best["industry"],
        "score": best["score"],
        "district_mean": round(mean, 4),
        "delta_pp": round((best["score"] - mean) * 100, 1),
    }


def openings(district_id: str, limit: int = 60) -> dict:
    """어느 자리에 어떤 업소가 들어오면 좋은가 — 공실 인벤토리 × GNN 추천.

    자리는 건축물대장 실측 공실 유닛이고, 추천은 그 좌표에서 400m 안 최근접
    그래프 노드의 Top-3 다. 노드가 없으면 **추천을 비운 채 자리만 싣는다** —
    거점 평균으로 대신 채우면 그 자리의 답인 것처럼 읽힌다.
    """
    units = vacant_inventory.units(district_id)
    means = _district_means(district_id)
    out: list[dict] = []
    matched = 0
    for u in units[:limit]:
        rec = None
        if u.get("lat") is not None and u.get("lng") is not None:
            rec = industry_recommend.recommend(district_id, u["lat"], u["lng"])
        if rec:
            matched += 1
        out.append({
            "unit_id": u.get("id"),
            "name": u.get("n"),
            "lat": u.get("lat"), "lng": u.get("lng"),
            "area_py": u.get("area"),
            "floor": u.get("floor"),
            "capacity": u.get("capacity"),
            "vacancy_rate": u.get("vacancy_rate"),
            # 직전 업종. **추천과 눈금이 다르다**(상가정보 분류 ↔ GNN 7군) —
            # 자동으로 비교해 '업종 전환'이라 판정하지 않는다.
            "was": (u.get("was") or "").strip() or None,
            "recommendations": (rec or {}).get("recommendations", []),
            "matched_distance_m": (rec or {}).get("matched_distance_m"),
            # 이 자리만의 신호 — 상권 평균을 뺀 뒤 가장 두드러지는 업종
            "distinct": _distinct((rec or {}).get("recommendations", []), means),
        })
    # **상권 평균과 가장 다른 자리부터** 보여준다. 1위 확률로 줄 세우면 사전확률에 눌려
    # 거의 모든 자리가 같은 업종·비슷한 값이라 순서가 정보를 담지 못한다(추천 없는 자리는 뒤로).
    out.sort(key=lambda o: -(o["distinct"]["delta_pp"] if o.get("distinct") else -1e9))
    return {
        "sites": out,
        "unit_count": len(units),
        "matched_count": matched,
        "match_radius_m": industry_recommend._MAX_MATCH_M,
        "source": ("자리 = 건축물대장 실측 공실 인벤토리(gold/{거점}/vacant_units.json) · "
                   "업종 = GNN 최근접 노드 Top-3(gold/platform_industry_recommend.json)"),
        "distinct_note": ("‘상권 평균 대비’는 이 상권 전체 노드의 업종별 평균 확률을 뺀 값이다. "
                          "산출물이 노드마다 Top-3 만 실어 그 밖 업종을 0 으로 보는 근사라, "
                          "자리 간 비교용이지 절대값이 아니다."),
    }


def profile(district_id: str) -> dict | None:
    """정체성 + 자리 제안. 둘 다 없으면 None(= 이 거점은 Platform 산출물이 없다)."""
    ident = identity(district_id)
    sites = openings(district_id)
    if ident is None and not sites["sites"]:
        return None
    return {"district_id": district_id, "identity": ident, "openings": sites}
