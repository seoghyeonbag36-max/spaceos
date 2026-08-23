"""[Posting] 공정위 가맹사업 정보공개서 → tier별 평균 점포면적 A (gold/platform_posting_store_area.json).

## 왜 이 파일이 필요한가

`posting_revenue.avg_store_pyeong()` 은 A 를 **임차료에서 역산**하고 있었다:

    A[tier] = (KOSIS 점포당 임차료 ÷ 12) ÷ 우리 54거점 평당임대료 중앙

그 파일 스스로가 이것을 **하한**이라고 적어 두었다 — 분모로 쓴 평당임대료가 서울
전체가 아니라 전부 프라임인 54거점 값이라, 서울 평균으로 나눴다면 A 가 더 컸을
것이기 때문이다. A 가 작으면 평당매출이 부풀고 마진이 실제보다 좋아 보인다.
그래서 §0-E 는 "공정위 기준면적을 확보하면 이 상수를 갈아끼운다"고 예약해 두었다.

    python data/pipelines/build_posting_store_area.py

## 면적을 어떻게 얻는가 — 나눗셈 하나

공정위 API 는 면적을 직접 주지 않는다. 대신 같은 행에 둘을 준다:

    avrgSlsAmt        평균매출금액
    arUnitAvrgSlsAmt  면적단위평균매출금액

가맹사업법 시행령 정보공개서 표준양식의 면적단위는 **3.3㎡(1평)** 이므로

    A(평) = avrgSlsAmt / arUnitAvrgSlsAmt

이고, 둘이 같은 금액 단위라 **단위가 무엇이든 나눗셈에서 상쇄된다.** 금액 단위를
몰라도 면적은 정확하다는 뜻이다.

## 가맹점수로 가중하는 이유

브랜드 단순 중앙값을 쓰면 1개점짜리 신생 브랜드와 1,000개점 브랜드가 같은 무게를
갖는다. 우리가 알고 싶은 것은 "이 tier 의 **점포** 하나가 보통 몇 평인가"이므로
가맹점수(`frcsCnt`)로 가중한 중앙값을 주값으로 쓴다. 단순 중앙값도 함께 실어
차이를 드러낸다(value 는 25.4 → 18.5 로 크게 움직인다 — 소형 브랜드 쏠림이었다).

## 모집단이 다르다는 것은 알고 쓴다

이 A 는 **전국 가맹점(프랜차이즈)** 이고, 매출 분자는 서울 실측이다. 축이 완전히
같지는 않다. 그래도 임차료 역산보다 직접적인 실측이고 스스로 하한임을 인정한 값을
대체하므로 개선이다 — `basis` 필드로 어느 쪽이 쓰였는지 산출물에 남긴다.
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from data.collectors.common import GOLD, load_env  # noqa: E402

URL = "http://apis.data.go.kr/1130000/FftcBrandFrcsStatsService/getBrandFrcsStats"
YEAR = "2024"
OUT = GOLD / "platform_posting_store_area.json"

# 공정위 업종중분류(indutyMlsfcNm) ↔ tier. build_posting_cost_rates.TIER_KSIC 의
# KSIC 업종명과 1:1 로 맞춘 것이다 — 두 파이프라인이 같은 tier 축을 써야 평당매출
# (= 매출 ÷ A) 의 분자와 분모가 같은 업종을 가리킨다.
#   premium 56122 일식 · 56123 양식 · 56121 중식
#   value   56111 한식일반 · 56162 치킨 · 56213 생맥주
#   factory 56221 커피 · 56161 패스트푸드 · 56150 제과
# "기타 외국식"은 양식으로 볼지 애매해서 뺐다(보수적).
TIER_INDUTY = {
    "일식": "premium", "서양식": "premium", "중식": "premium",
    "한식": "value", "치킨": "value", "주점": "value",
    "커피": "factory", "패스트푸드": "factory", "제과제빵": "factory",
}

# 평수 상식 대역. 밖으로 나가면 두 금액의 단위가 서로 다른 행이므로 버린다.
SANE_PYEONG = (2.0, 200.0)


def fetch(key: str) -> list[dict]:
    """브랜드별 가맹점 현황 전수(2024). totalCount 를 채울 때까지 페이지를 넘긴다."""
    rows: list[dict] = []
    for page in range(1, 30):
        q = urllib.parse.urlencode({
            "serviceKey": key, "pageNo": page, "numOfRows": 1000,
            "resultType": "json", "yr": YEAR,
        })
        with urllib.request.urlopen(f"{URL}?{q}", timeout=90) as r:
            doc = json.loads(r.read().decode("utf-8", "replace"))
        if doc.get("resultCode") not in (None, "00"):
            raise RuntimeError(f"API {doc.get('resultCode')} {doc.get('resultMsg')}")
        items = doc.get("items") or []
        rows += items
        total = int(doc.get("totalCount") or 0)
        print(f"[ftc] page {page} +{len(items)} → {len(rows)}/{total}")
        if not items or len(rows) >= total:
            break
    return rows


def _weighted_median(pairs: list[tuple[float, int]]) -> float:
    """가중 중앙값 — 누적 가중치가 절반을 넘는 지점의 값."""
    s = sorted(pairs)
    total = sum(w for _, w in s)
    acc = 0
    for v, w in s:
        acc += w
        if acc >= total / 2:
            return v
    return s[-1][0]


def aggregate(rows: list[dict]) -> dict:
    per: dict[str, list[tuple[float, int]]] = defaultdict(list)
    skipped = 0
    for it in rows:
        tier = TIER_INDUTY.get((it.get("indutyMlsfcNm") or "").strip())
        if not tier:
            continue
        try:
            sales = float(it["avrgSlsAmt"])
            unit = float(it["arUnitAvrgSlsAmt"])
            stores = int(float(it.get("frcsCnt") or 0))
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        # 매출 0 은 미기재(신규·소규모 브랜드)다. 0 을 면적으로 바꿀 방법은 없다.
        if sales <= 0 or unit <= 0 or stores < 1:
            skipped += 1
            continue
        pyeong = sales / unit
        if not (SANE_PYEONG[0] <= pyeong <= SANE_PYEONG[1]):
            skipped += 1
            continue
        per[tier].append((pyeong, stores))

    tiers: dict[str, dict] = {}
    for tier, pairs in per.items():
        vals = [p for p, _ in pairs]
        tiers[tier] = {
            "pyeong": round(_weighted_median(pairs), 1),
            "pyeong_brand_median": round(st.median(vals), 1),
            "brands": len(pairs),
            "stores": sum(w for _, w in pairs),
        }
    return {
        "source": f"공정거래위원회 가맹정보 브랜드별 가맹점 현황(data.go.kr 15110241), 기준 {YEAR}",
        "note": (
            "A(평) = avrgSlsAmt / arUnitAvrgSlsAmt. 정보공개서 면적단위가 3.3㎡ 라 몫이 "
            "평이고, 두 값이 같은 금액 단위라 단위는 상쇄된다. pyeong 은 가맹점수 가중 "
            "중앙값(주값), pyeong_brand_median 은 브랜드 단순 중앙값. 전국 가맹점 모집단이라 "
            "서울 실측 매출과 축이 완전히 같지는 않다."
        ),
        "skipped": skipped,
        "tiers": tiers,
    }


def main() -> None:
    load_env()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key:
        print("[ftc] DATA_GO_KR_SERVICE_KEY 미설정 — 건너뜀")
        return
    doc = aggregate(fetch(key))
    if len(doc["tiers"]) != 3:
        # 세 tier 가 다 안 차면 쓰지 않는다. 일부만 실측이면 tier 간 비교가
        # 서로 다른 근거 위에 서게 되고, 그건 조용히 틀리는 쪽이다.
        print(f"[ftc] tier 부족({sorted(doc['tiers'])}) — 저장하지 않는다")
        return
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gold] {OUT.relative_to(_ROOT)}")
    for tier, v in doc["tiers"].items():
        print(f"  {tier:8s} {v['pyeong']:5.1f}평 (브랜드중앙 {v['pyeong_brand_median']:5.1f}) "
              f"브랜드 {v['brands']:5d} · 가맹점 {v['stores']:6d}")


if __name__ == "__main__":
    main()
