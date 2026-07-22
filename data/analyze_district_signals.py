"""[Platform] 거점별 실신호 요약 — seoul_pages 시드 작성의 근거 산출기.

Bronze(platform13)의 수집분을 거점 단위로 집계해, 시드(zones/units/grid)에 넣을
수치의 **근거**를 출력한다. 시드를 자동 생성하지는 않는다 — 판단(구역 분할·페르소나)은
사람이 하고, 이 스크립트는 그 판단이 기대는 실측치를 제공한다.

산출 항목
  - stor : 점포수(STOR_CO)·폐업률(CLSBIZ_RT)·개업률(OPBIZ_RT) 최신분기 + 추세
  - ix   : 상권변화지표(다이나믹/확장/축소/정체) — zones 의 증감(d) 방향 근거
  - kakao: 업종 구성(category_group_name) — units 의 업종·Tier 근거
  - naver: 블로그 언급 수 — zones 의 리뷰(r) 총량 배분 근거

실행: python -m data.analyze_district_signals [거점id ...]   (미지정 시 전 거점)
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

from data.collectors.common import load_latest
from data.config.platform_districts import SLUG


def _num(v: object) -> float:
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return 0.0


def _load(name: str) -> list[dict]:
    rows = load_latest(SLUG, name)
    return rows if isinstance(rows, list) else []


def analyze(district_ids: list[str] | None = None) -> dict[str, dict]:
    stor = _load("seoul_trdar_stor.json")
    ix = _load("seoul_trdar_ix.json")
    kakao = _load("kakao_places.json")
    blog = _load("naver_blog.json")

    by_id: dict[str, dict] = defaultdict(dict)
    ids = set(district_ids or {r["district_id"] for r in stor})

    # ── stor: 최신분기 점포수·개폐업률 + 직전 대비 추세 ────────────────────────
    quarters = sorted({str(r["STDR_YYQU_CD"]) for r in stor})
    latest, prev = (quarters[-1], quarters[-2]) if len(quarters) >= 2 else (quarters[-1], None)
    for did in ids:
        rows = [r for r in stor if r["district_id"] == did]
        cur = [r for r in rows if str(r["STDR_YYQU_CD"]) == latest]
        old = [r for r in rows if str(r["STDR_YYQU_CD"]) == prev] if prev else []
        n_cur = sum(_num(r["STOR_CO"]) for r in cur)
        n_old = sum(_num(r["STOR_CO"]) for r in old)
        cls = [_num(r["CLSBIZ_RT"]) for r in cur if _num(r["CLSBIZ_RT"]) > 0]
        opb = [_num(r["OPBIZ_RT"]) for r in cur if _num(r["OPBIZ_RT"]) > 0]
        by_id[did]["stor"] = {
            "quarter": latest,
            "stores": int(n_cur),
            "stores_prev": int(n_old),
            "store_delta_pct": round((n_cur - n_old) / n_old * 100, 2) if n_old else None,
            "clsbiz_rt": round(sum(cls) / len(cls), 2) if cls else None,
            "opbiz_rt": round(sum(opb) / len(opb), 2) if opb else None,
        }
        # 업종 상위 — units 업종 선정 근거
        ind = Counter()
        for r in cur:
            ind[r["SVC_INDUTY_CD_NM"]] += _num(r["STOR_CO"])
        by_id[did]["top_induty"] = [(k, int(v)) for k, v in ind.most_common(8)]

    # ── ix: 상권변화지표 최신분기 ──────────────────────────────────────────────
    for did in ids:
        rows = [r for r in ix if r["district_id"] == did]
        if not rows:
            by_id[did]["ix"] = None
            continue
        q = max(str(r["STDR_YYQU_CD"]) for r in rows)
        cur = [r for r in rows if str(r["STDR_YYQU_CD"]) == q]
        by_id[did]["ix"] = {
            "quarter": q,
            "labels": Counter(r["TRDAR_CHNGE_IX_NM"] for r in cur).most_common(),
            "opr_sale_mt_avg": round(sum(_num(r["OPR_SALE_MT_AVRG"]) for r in cur) / len(cur), 1),
            "cls_sale_mt_avg": round(sum(_num(r["CLS_SALE_MT_AVRG"]) for r in cur) / len(cur), 1),
        }

    # ── kakao: 업종 구성 ──────────────────────────────────────────────────────
    for did in ids:
        rows = [r for r in kakao if r["district_id"] == did]
        by_id[did]["kakao"] = {
            "places": len(rows),
            "groups": Counter(r["category_group_name"] for r in rows).most_common(8),
        }

    # ── naver: 블로그 언급 ────────────────────────────────────────────────────
    for did in ids:
        rows = [r for r in blog if r["district_id"] == did]
        by_id[did]["blog"] = {"posts": len(rows)}

    return dict(by_id)


def main() -> None:
    ids = sys.argv[1:] or None
    out = analyze(ids)
    for did in sorted(out):
        d = out[did]
        s, x = d.get("stor", {}), d.get("ix")
        print("=" * 72)
        print(f"[{did}]")
        print(f"  stor {s.get('quarter')}: 점포 {s.get('stores'):,}개 "
              f"(직전 {s.get('stores_prev'):,} / {s.get('store_delta_pct')}%) "
              f"폐업률 {s.get('clsbiz_rt')}% 개업률 {s.get('opbiz_rt')}%")
        if x:
            print(f"  ix   {x['quarter']}: {x['labels']}  "
                  f"영업개월 {x['opr_sale_mt_avg']} / 폐업개월 {x['cls_sale_mt_avg']}")
        print(f"  kakao: {d['kakao']['places']}곳 {d['kakao']['groups'][:5]}")
        print(f"  blog : {d['blog']['posts']}건")
        print(f"  업종상위: {d.get('top_induty', [])[:6]}")
    print("\nJSON:")
    print(json.dumps(out, ensure_ascii=False)[:200] + " …")


if __name__ == "__main__":
    main()
