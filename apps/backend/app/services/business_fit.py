"""내 업종으로 본 상권(business fit) — 창업자·업종 바꾸기·상권 옮기기 사업자용 비교(화면설계서 3판).

## 왜 (2026-09-13 주요 고객 재정의)

2판까지 화면은 **상권을 먼저 고르는** 분석가를 위한 것이었다. 3판의 주요 고객은 업종이 정해진
창업자와, 지금 상권에서 업종을 바꾸거나 같은 업종으로 상권을 옮기려는 사업자다. 이들은 업종에서
출발하므로 두 질문에 답해야 한다.

- 창업·옮기기: "내 업종이면 **어느 상권**인가" → `fit_by_district(key)`
- 바꾸기:      "지금 상권에서 **무엇으로** 바꾸나" → `industries_in_district(district_id)`

⚠ 이름이 비슷한 `industry_fit`(층·용도별 업종 **관측 분포**, Page 층별 매물)과 다른 것이다.
  저쪽은 매물 조건에서 실제로 영업 중인 업종이고, 여기는 사업자 업종 기준 상권·업종 비교다.

## 업종 이름표가 두 벌이다

- 모델(GNN) 추천은 **7종**(음식점·카페·병원·편의점·숙박·문화시설·약국)만 안다.
- 상권 업종 구성은 카카오 플레이스 **말단 라벨**이다(`platform_profile._categories`).

사업자가 고르는 12종(`INDUSTRIES`)이 둘을 잇는다. 7종 밖 업종은 `model_label=None` 이고
**입지 적합도를 내지 않는다** — 가까운 업종 점수로 대신 채우면 그 업종의 답인 것처럼 읽힌다.

## 값의 정의와 한계

- `fit` 입지 적합도 = 그 상권 점포 자리(그래프 노드)마다 GNN 이 매긴 "이 자리에 그 업종이 있을
  확률"의 평균(`platform_profile._district_means` 와 같은 식). **매출·생존이 아니다** — 비슷한
  입지에 그 업종이 이미 모여 있는 정도다. 산출물이 노드마다 Top-3 만 실어 그 밖은 0 으로 보므로
  절대값은 낮게 나온다 → **순위를 가리는 데만** 쓴다.
- `same_n / sample_n` 같은 업종 비중 = 카카오 플레이스 업종 라벨 **상위 표본**에서 센 값.
  상권 전체 점포 수가 아니다. 높다고 좋다·나쁘다로 판정하지 않는다(경쟁일 수도, 검증된 수요일 수도).
- `rent_1f_per_pyeong` = R-ONE 소규모상가 1층 평당 월임대료(만원). 없는 상권은 None — 이웃 값으로
  채우지 않는다. 인접 상권 표본을 빌렸으면 `rent_shared=True`.
- 공실률은 싣지 않는다 — 화면이 `/commercial-districts` 응답에서 합친다(`_served` 참조).
"""
from __future__ import annotations

import time

from app.services import districts as districts_svc
from app.services import industry_recommend, marketing, posting_inputs

_PYEONG_TO_M2 = 3.3058
_TTL_SECONDS = 300.0

# 사업자가 고르는 업종 12종 — **순서가 화면 칩 순서다.**
#   key          안정 식별자(URL·저장값). 바꾸면 브라우저에 저장된 「내 사업」이 깨진다.
#   label        화면 이름
#   input        Posting 업종칸·Program 카테고리칸에 채우는 말
#   model_label  GNN 7종 라벨. 없으면 None(적합도 없음)
#   needles      같은 업종으로 세는 카카오 라벨 부분문자열
INDUSTRIES: list[dict] = [
    {"key": "cafe", "label": "카페·디저트", "input": "카페", "model_label": "카페",
     "needles": ("카페", "커피", "디저트", "베이커리", "제과", "빙수", "아이스크림", "브런치")},
    {"key": "restaurant", "label": "음식점", "input": "음식점", "model_label": "음식점",
     "needles": ("한식", "일식", "중식", "양식", "분식", "치킨", "피자", "고기", "국수", "해물",
                 "뷔페", "돈까스", "스테이크", "족발", "곱창", "포케", "음식", "식당", "면요리",
                 "덮밥", "카레")},
    {"key": "bar", "label": "술집", "input": "주점", "model_label": None,
     "needles": ("호프", "주점", "술집", "포차", "와인", "이자카야", "맥주", "바텐더")},
    {"key": "beauty", "label": "미용·네일", "input": "미용실", "model_label": None,
     "needles": ("미용", "헤어", "네일", "에스테틱", "왁싱", "뷰티", "피부관리")},
    {"key": "clinic", "label": "병·의원", "input": "병원", "model_label": "병원",
     "needles": ("의원", "병원", "외과", "내과", "치과", "한의", "부인과", "안과", "이비인후",
                 "비뇨", "소아", "정신건강", "재활", "피부과", "성형")},
    {"key": "pharmacy", "label": "약국", "input": "약국", "model_label": "약국",
     "needles": ("약국",)},
    {"key": "convenience", "label": "편의점·생활", "input": "편의점", "model_label": "편의점",
     "needles": ("편의점", "CU", "GS25", "세븐일레븐", "마트", "슈퍼", "세탁")},
    {"key": "fashion", "label": "옷·잡화", "input": "의류", "model_label": None,
     "needles": ("의류", "패션", "신발", "가방", "화장품", "잡화", "안경", "주얼리", "액세서리", "편집")},
    {"key": "education", "label": "학원·교육", "input": "학원", "model_label": None,
     "needles": ("학원", "교육", "스터디", "독서실")},
    {"key": "fitness", "label": "운동·여가", "input": "운동시설", "model_label": None,
     "needles": ("헬스", "필라테스", "요가", "골프", "클라이밍", "스포츠", "당구", "볼링", "PC방", "노래")},
    {"key": "lodging", "label": "숙박", "input": "숙박", "model_label": "숙박",
     "needles": ("호텔", "모텔", "여관", "게스트하우스", "숙박", "펜션", "레지던스")},
    {"key": "culture", "label": "전시·공연", "input": "문화시설", "model_label": "문화시설",
     "needles": ("전시", "미술", "공연", "극장", "박물", "갤러리", "서점")},
]
_BY_KEY = {i["key"]: i for i in INDUSTRIES}

SOURCE = ("입지 적합도 = GNN 업종 추천 상권 평균(gold/platform_industry_recommend.json) · "
          "같은 업종 = 카카오 플레이스 업종 라벨 상위 표본(gold/{거점}/program_content_context.csv) · "
          "임대료 = R-ONE 소규모상가 1층 · 공실률 = 건축물대장 실측")
NOTE = ("입지 적합도는 비슷한 입지에 그 업종이 이미 모여 있는 정도를 모델이 배운 값이다 — 매출·생존율이 아니다. "
        "산출물이 자리마다 상위 3개 업종만 실어 절대값은 낮게 나오므로 순위를 가리는 데만 쓴다. "
        "같은 업종 비중은 카카오 플레이스 표본에서 센 값이라 상권 전체 점포 수가 아니다.")

_cache: dict[str, tuple[float, object]] = {}


def public(item: dict) -> dict:
    """화면에 내는 업종 필드 — needles 는 규칙이라 싣지 않는다(설계서 대응표가 사람용 정본)."""
    return {k: item[k] for k in ("key", "label", "input", "model_label")}


def industries() -> list[dict]:
    return [public(i) for i in INDUSTRIES]


def get(key: str) -> dict | None:
    return _BY_KEY.get(key)


def _cached(name: str, build):
    now = time.monotonic()
    hit = _cache.get(name)
    if hit and now - hit[0] < _TTL_SECONDS:
        return hit[1]
    value = build()
    _cache[name] = (now, value)
    return value


def _all_means() -> dict[str, dict[str, float]]:
    """상권 → {GNN 라벨: 노드 평균 확률}. 노드 47k × Top-3 를 한 번만 돈다."""
    def build() -> dict[str, dict[str, float]]:
        data = industry_recommend._load() or {}
        out: dict[str, dict[str, float]] = {}
        for did, nodes in (data.get("districts") or {}).items():
            if not nodes:
                continue
            agg: dict[str, float] = {}
            for item in nodes.values():
                for t in item.get("top", []):
                    agg[t["industry"]] = agg.get(t["industry"], 0.0) + t["score"]
            out[did] = {k: v / len(nodes) for k, v in agg.items()}
        return out
    return _cached("means", build)


def _same_counts(district_id: str) -> tuple[dict[str, int], int] | None:
    """상권의 업종 12종별 같은 업종 표본 수와 표본 합. 컨텍스트가 없으면 None."""
    rows = marketing.context_rows(district_id)
    if rows is None:
        return None
    cats = [(label, n) for kind, label, n in rows if kind == "category"]
    if not cats:
        return None
    total = sum(n for _, n in cats)
    counts = {
        i["key"]: round(sum(n for label, n in cats if any(nd in label for nd in i["needles"])))
        for i in INDUSTRIES
    }
    return counts, round(total)


def _rent_1f(district_id: str) -> float | None:
    row = posting_inputs.for_district(district_id) or {}
    per_m2 = row.get("rent_per_m2_krw_thousand")
    return round(per_m2 * _PYEONG_TO_M2 / 10, 1) if per_m2 else None


def _served() -> list[dict]:
    """서빙 상권 — `/commercial-districts` 가 요약을 만드는 것과 같은 목록(`PAGES`).

    ⚠ `list_summaries()` 를 부르지 않는다. 요약은 상권마다 격자를 다시 계산해 로컬 실측
    66상권에 121초(데운 뒤 15초)가 걸렸다(2026-09-13). 공실률은 화면이 이미 받아 둔
    상권 목록에서 합친다 — 같은 값을 두 엔드포인트가 따로 만들면 어긋날 자리만 늘어난다.
    """
    return districts_svc.PAGES


def fit_by_district(key: str) -> dict | None:
    """업종 하나로 서빙 상권 전체를 견준다. 모르는 업종이면 None."""
    item = get(key)
    if item is None:
        return None
    return _cached(f"fit:{key}", lambda: _fit_by_district(item))


def _fit_by_district(item: dict) -> dict:
    key = item["key"]
    label = item["model_label"]
    means = _all_means() if label else {}
    rows: list[dict] = []
    for s in _served():
        did = s["id"]
        same = _same_counts(did)
        fit = None
        if label and did in means:
            fit = round(means[did].get(label, 0.0), 4)
        rows.append({
            "district_id": did, "name": s.get("name"), "gu": s.get("gu"),
            "fit": fit, "fit_rank": None,
            "same_n": same[0][key] if same else None,
            "sample_n": same[1] if same else None,
            "same_share": (round(same[0][key] / same[1], 4) if same and same[1] else None),
            "rent_1f_per_pyeong": _rent_1f(did),
            "rent_shared": posting_inputs.is_shared_rone(did),
        })

    covered = bool(label) and any(r["fit"] is not None for r in rows)
    if covered:
        # 적합도가 있는 상권만 순위를 매긴다. 그래프에 없는 상권은 0 이 아니라 순위 없음으로 뒤에 둔다.
        ranked = sorted((r for r in rows if r["fit"] is not None), key=lambda r: -r["fit"])
        for n, r in enumerate(ranked, start=1):
            r["fit_rank"] = n
        rows = ranked + sorted((r for r in rows if r["fit"] is None), key=lambda r: r["name"] or "")
        fits = [r["fit"] for r in ranked]
        seoul_fit = round(sum(fits) / len(fits), 4)
    else:
        rows.sort(key=lambda r: r["name"] or "")
        seoul_fit = None

    return {
        "industry": public(item),
        "model_covered": covered,
        "seoul_fit": seoul_fit,
        "ranked_n": sum(1 for r in rows if r["fit_rank"] is not None),
        "districts": rows,
        "source": SOURCE,
        "note": NOTE,
    }


def industries_in_district(district_id: str) -> dict | None:
    """한 상권 안에서 업종 12종을 견준다(바꾸기). 모델·표본 둘 다 없으면 None."""
    means = _all_means().get(district_id)
    same = _same_counts(district_id)
    if means is None and same is None:
        return None
    rows = []
    for item in INDUSTRIES:
        label = item["model_label"]
        fit = round(means.get(label, 0.0), 4) if (label and means is not None) else None
        rows.append({
            **public(item), "fit": fit, "fit_rank": None,
            "same_n": same[0][item["key"]] if same else None,
            "same_share": (round(same[0][item["key"]] / same[1], 4) if same and same[1] else None),
        })
    ranked = sorted((r for r in rows if r["fit"] is not None), key=lambda r: -r["fit"])
    for n, r in enumerate(ranked, start=1):
        r["fit_rank"] = n
    # 7종 밖 업종은 순위 없이 원래 칩 순서대로 뒤에 둔다.
    rows = ranked + [r for r in rows if r["fit"] is None]
    return {
        "district_id": district_id,
        "rows": rows,
        "sample_n": same[1] if same else None,
        "source": SOURCE,
        "note": NOTE,
    }
