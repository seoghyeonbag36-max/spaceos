"""[Program] 상권 행사 Gold — gold/platform_events.json 산출.

Bronze(`seoul_events.json`, 서울열린데이터광장 문화행사)를 거점별 표시용으로 정리한다.

## 시드에서 들고 오지 않는 것

시드 행사(`app/data/seoul_pages.py` 의 `e()`)는 좌표·일정과 함께 **효과 지표**
("유입 +52%", "전환 14%")·이해관계자 역할·HA 메모를 달고 있었다. 셋 다 근거 없이
적은 값이라 실데이터로 넘어오면서 **버린다**. 대신 API 가 실제로 주는 것만 싣는다:
장소·주최·기간·요금·대상·링크·거점 중심으로부터의 거리.

## 커버리지 한계 (2026-08-01 실측)

이 API 는 공공·문화시설 행사 중심이라 **상업 상권의 팝업·플리마켓을 거의 담지 않는다**.
도심 문화시설 밀집 거점은 풍부하지만(cityhall 86 · ikseon 78 · myeongdong 72),
가두 상권은 얇다(garosugil 2건, 둘 다 800m 밖). 없는 거점은 빈 목록으로 두고
프론트가 "예정된 공공 문화행사 없음"을 표시한다 — 시드로 채우지 않는다.

실행: python -m data.pipelines.build_events
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from data.collectors.common import GOLD, load_latest

_SRC_SLUG = "platform13"
_OUT = GOLD / "platform_events.json"

# 문화행사 분류(CODENAME) → 지도 아이콘. 없는 분류는 기본값.
_ICON = {
    "콘서트": "🎵", "클래식": "🎻", "뮤지컬/오페라": "🎭", "연극": "🎭",
    "전시/미술": "🖼️", "무용": "💃", "국악": "🪕", "축제-기타": "🎪",
    "축제-문화/예술": "🎪", "교육/체험": "🧑‍🏫", "영화": "🎬", "기타": "📌",
}
_DEFAULT_ICON = "📌"


def _fee(row: dict) -> str:
    """요금 표시. IS_FREE 가 '무료'면 그대로, 아니면 USE_FEE 원문(길면 자름)."""
    if str(row.get("IS_FREE") or "").strip() == "무료":
        return "무료"
    fee = str(row.get("USE_FEE") or "").strip()
    return (fee[:60] + "…") if len(fee) > 60 else (fee or "유료")


# 행사가 걸치는 시간대. TRDAR 수요신호의 구간과 같은 경계를 쓴다 —
# 오프라인 제안은 "유동 대비 매출이 빈 시간대"를 겨냥하므로, 그 시간대에 실제로 열리는
# 행사만 연계 후보가 된다. 두 축이 같은 눈금 위에 있어야 교집합을 낼 수 있다.
# 00~06 은 넣지 않는다(build_program_demand.ACTIONABLE_TMZONS 와 같은 이유).
_BANDS = [(6, 11, "06_11"), (11, 14, "11_14"), (14, 17, "14_17"),
          (17, 21, "17_21"), (21, 24, "21_24")]

# "19:30", "10:00 ~ 19:00", "(수) 19:30", "14시" 를 모두 잡는다.
_HOUR_RE = re.compile(r"(\d{1,2})\s*[:시]")

# 단일 시각만 적힌 행사(공연 시작시각)의 가정 상영시간. 종료시각을 모르므로 만들어 쓴다 —
# 값 자체는 근거가 없고, 밴드를 하나만 잡을지 둘을 잡을지를 가르는 용도다.
_ASSUMED_HOURS = 2


def _time_bands(raw: str) -> list[str]:
    """PRO_TIME 원문 → 걸치는 시간대 목록.

    원천(`PRO_TIME`)은 785/785 채워져 있는데 지금까지 Gold 로 넘기지 않았다. 그래서
    "6~11시가 비어 있다"는 수요신호와 "그 시간에 열리는 행사"를 맞출 수가 없었고,
    오프라인 제안이 시간 축 없이 나왔다(2026-08-16 정정).

    시각을 못 읽으면 **빈 목록**이다 — 0시로 넘겨짚지 않는다(785건 중 97건).
    """
    hours = [int(h) for h in _HOUR_RE.findall(raw or "") if 0 <= int(h) <= 24]
    if not hours:
        return []
    lo, hi = min(hours), max(hours)
    if hi == lo:
        hi = lo + _ASSUMED_HOURS
    return [name for a, b, name in _BANDS if lo < b and hi > a]


def _event(row: dict, idx: int) -> dict:
    """Bronze 행 → 표시용 행사. **API 가 준 필드만** 싣는다(효과 지표를 만들지 않는다)."""
    return {
        "id": f"ev{idx}",
        "n": str(row.get("TITLE") or "").strip(),
        "lat": float(row["LAT"]),
        "lng": float(row["LOT"]),
        "ic": _ICON.get(str(row.get("CODENAME") or ""), _DEFAULT_ICON),
        "category": str(row.get("CODENAME") or "").strip(),
        "when": str(row.get("DATE") or "").strip(),
        "place": str(row.get("PLACE") or "").strip(),
        "org": str(row.get("ORG_NAME") or "").strip(),
        "fee": _fee(row),
        "target": str(row.get("USE_TRGT") or "").strip(),
        "link": str(row.get("ORG_LINK") or row.get("HMPG_ADDR") or "").strip(),
        "distance_m": row.get("distance_m"),
        # 운영 시각과 그것이 걸치는 시간대 — 빈 시간대와의 교집합을 내는 축이다.
        "time": str(row.get("PRO_TIME") or "").strip(),
        "tm": _time_bands(str(row.get("PRO_TIME") or "")),
    }


def run() -> dict:
    rows = load_latest(_SRC_SLUG, "seoul_events.json")
    if rows is None:
        raise FileNotFoundError(
            "bronze seoul_events.json 없음 — `python -m data.collectors.seoul_events` 먼저 실행")

    by_district: dict[str, list[dict]] = {}
    for row in rows:
        did = row.get("district_id")
        if not did or not row.get("TITLE"):
            continue
        by_district.setdefault(did, []).append(row)

    districts = {
        did: [_event(r, i) for i, r in enumerate(
            # 가까운 것 → 빨리 시작하는 것 순. 상권 유입에 실제로 닿는 순서다.
            sorted(rs, key=lambda x: (x.get("distance_m", 9999), str(x.get("STRTDATE") or ""))), 1)]
        for did, rs in by_district.items()
    }

    out = {
        "source": "서울열린데이터광장 문화행사(culturalEventInfo)",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": (
            "공공·문화시설 행사 중심이라 상업 상권의 팝업·플리마켓 커버리지가 낮다. "
            "시드가 달고 있던 효과 지표(유입 +52% 등)·이해관계자 역할·HA 메모는 근거가 "
            "없어 들고 오지 않았다 — API 가 주는 사실만 싣는다."
        ),
        "districts": districts,
    }
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    out = run()
    d = out["districts"]
    total = sum(len(v) for v in d.values())
    print(f"[events] {len(d)}거점 · {total}건 → {_OUT}")
    for slug, evs in sorted(d.items(), key=lambda kv: -len(kv[1]))[:5]:
        print(f"  {slug:18s} {len(evs):4d}건")
    print(f"  garosugil          {len(d.get('garosugil', [])):4d}건")


if __name__ == "__main__":
    main()
