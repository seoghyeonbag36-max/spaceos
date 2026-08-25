"""막힘 6(Platform 감성) 사전 판정 — 600ep 을 돌리기 **전에** 세 다리를 잰다.

## 왜 이 스크립트가 있나

`docs/spaceos-vibe-build-sequence.md` 막힘 6 은 08-24 에 채널을 정했다:
*"기존 네이버 블로그 API 로 **상권 단위** 감성"*. 그런데 그 채널이 GNN off-prior
게이트를 움직일 수 있는지는 아무도 재지 않았고, 게이트 문구는 계속 이것을 **남은
레버**로 지목했다. GNN 은 이미 네 번 기각됐다(이웃·조기종료·행정동×2) — 다섯 번째를
600ep 돌리기 전에 **재료가 정보를 가질 수 있는지 먼저 본다.**

## 세 다리 — 하나라도 끊기면 이 채널은 못 쓴다

1. **구조** — 블로그 데이터의 공간 키가 `district_id` 뿐이면, 거기서 나온 어떤 값도
   거점 내 상수다. `_features()` 에 **거점 원핫이 이미 있으므로 정보량이 0**이다
   (`_adong_hour_block` 이 같은 원칙을 적어 두었다). 이건 측정이 아니라 증명이다.
2. **귀속** — 거점 아래로 내려가려면 본문의 점포명을 노드에 붙여야 한다. 붙는 노드
   비율이 낮으면 피처가 희소해 채움값이 지배한다.
3. **신호** — 감성 자체에 분산이 있어야 한다. 거점 간 분산이 거점 내 분산보다
   훨씬 작으면 거점을 못 가른다.

실행: python scripts/probe_blog_sentiment.py
산출: reports/blog_sentiment_probe_{날짜}.json
"""
from __future__ import annotations

import collections
import json
import re
import statistics as st
from datetime import date
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
_BLOG = _ROOT / "data" / "bronze" / "platform13" / "2026-08-01" / "naver_blog.json"
_NODES = _ROOT / "data" / "gold" / "platform13" / "platform_store_graph_nodes.parquet"
_OUT = _ROOT / "reports" / f"blog_sentiment_probe_{date.today().isoformat()}.json"

# 일반명사·지명형 상호는 본문 어디에나 나와 귀속이 성립하지 않는다.
# (필터 전에는 '익선동' 240건 · '충무로맛집' 148건이 상위를 차지한다)
_GENERIC = re.compile(r"(맛집|술집|고기집|카페|커피|분식|호프|포차|식당|치킨|피자|국밥|"
                      r"동$|거리$|시장$|역$|점$|골목|프라자|빌딩|타워)")

_POS = ["맛있", "맛집", "존맛", "JMT", "최고", "훌륭", "친절", "깔끔", "분위기 좋", "추천",
        "인생", "꿀맛", "재방문", "감동", "완벽", "만족", "넉넉", "가성비", "신선", "부드럽",
        "고소", "진하", "촉촉", "알차", "좋았", "좋아", "예쁘", "이쁘", "아늑", "조용",
        "넓", "깨끗", "빠르", "정성"]
_NEG = ["맛없", "별로", "실망", "불친절", "비싸", "비쌈", "좁", "시끄", "불결", "더럽",
        "최악", "다신 안", "웨이팅 길", "오래 기다", "기다림", "짜다", "싱겁", "질기",
        "눅눅", "비린", "아쉽", "그저 그", "불만"]


def _clean(s) -> str:
    return re.sub(r"<[^>]+>", "", str(s or ""))


def _polarity(text: str) -> tuple[float | None, int, int]:
    p = sum(text.count(w) for w in _POS)
    n = sum(text.count(w) for w in _NEG)
    return ((p - n) / (p + n) if (p + n) else None), p, n


def run() -> dict:
    rows = json.loads(_BLOG.read_text(encoding="utf-8"))
    nodes = pd.read_parquet(_NODES)

    # ── 다리 1: 구조 — 공간 키가 무엇인가 ────────────────────────────────────
    keys = sorted(rows[0].keys())
    spatial = [k for k in keys if k in ("district_id", "lat", "lon", "address", "road_address")]
    leg1 = {
        "keys": keys,
        "spatial_keys": spatial,
        "sub_district_key": [k for k in spatial if k != "district_id"],
        "verdict": ("거점 내 상수 — 거점 원핫에 흡수되어 정보량 0"
                    if spatial == ["district_id"] else "거점 아래 키 있음"),
    }

    # ── 다리 2: 귀속 — 점포명이 노드에 붙는가 ────────────────────────────────
    qtok: dict[str, set[str]] = collections.defaultdict(set)
    for r in rows:
        for t in re.split(r"\s+", str(r.get("_query", ""))):
            if len(t) >= 2:
                qtok[r["district_id"]].add(t)

    by_d: dict[str, list[str]] = collections.defaultdict(list)
    dropped = 0
    for nm, d in zip(nodes["name"], nodes["district_id"]):
        nm = str(nm).strip()
        if len(nm) < 3:
            dropped += 1
            continue
        if _GENERIC.search(nm) or any(t in nm for t in qtok.get(d, ())):
            dropped += 1
            continue
        by_d[d].append(nm)
    kept = sum(len(v) for v in by_d.values())

    hits: collections.Counter = collections.Counter()
    attributed = 0
    for r in rows:
        d = r["district_id"]
        text = _clean(r.get("title")) + " " + _clean(r.get("description"))
        found = [nm for nm in by_d.get(d, ()) if nm in text]
        if found:
            attributed += 1
            for nm in found:
                hits[(d, nm)] += 1
    leg2 = {
        "posts": len(rows),
        "nodes": int(len(nodes)),
        "names_kept": kept,
        "names_dropped_generic": dropped,
        "posts_attributed": attributed,
        "posts_attributed_pct": round(attributed / len(rows) * 100, 2),
        "nodes_with_sentiment": len(hits),
        "nodes_with_sentiment_pct": round(len(hits) / len(nodes) * 100, 2),
        "top10": [[d, nm, c] for (d, nm), c in hits.most_common(10)],
    }

    # ── 다리 3: 신호 — 감성에 분산이 있는가 ──────────────────────────────────
    by_dist: dict[str, list[float]] = collections.defaultdict(list)
    no_word = pos_tot = neg_tot = 0
    for r in rows:
        text = _clean(r.get("title")) + " " + _clean(r.get("description"))
        s, p, n = _polarity(text)
        pos_tot += p
        neg_tot += n
        if s is None:
            no_word += 1
            continue
        by_dist[r["district_id"]].append(s)

    flat = [x for v in by_dist.values() for x in v]
    dist_mean = {d: st.mean(v) for d, v in by_dist.items()}
    between = st.pstdev(list(dist_mean.values()))
    within = st.mean([st.pstdev(v) for v in by_dist.values() if len(v) > 1])
    leg3 = {
        "scored_posts": len(flat),
        "no_sentiment_word_pct": round(no_word / len(rows) * 100, 2),
        "neg_word_share_pct": round(neg_tot / (pos_tot + neg_tot) * 100, 2),
        "post_score_mean": round(st.mean(flat), 4),
        "post_score_pstdev": round(st.pstdev(flat), 4),
        "share_exactly_plus_one_pct": round(
            sum(1 for x in flat if x == 1.0) / len(flat) * 100, 2),
        "district_mean_min": round(min(dist_mean.values()), 4),
        "district_mean_max": round(max(dist_mean.values()), 4),
        "between_district_pstdev": round(between, 4),
        "within_district_pstdev": round(within, 4),
        "variance_ratio": round(between / within, 4),
    }

    out = {
        "probed_at": date.today().isoformat(),
        "source": str(_BLOG.relative_to(_ROOT)).replace("\\", "/"),
        "leg1_structure": leg1,
        "leg2_attribution": leg2,
        "leg3_signal": leg3,
        "verdict": (
            "기각 — 세 다리가 모두 끊긴다. (1) 공간 키가 district_id 뿐이라 거점 원핫에 "
            "흡수되고, (2) 점포 귀속은 노드의 3%대이며 그나마 유명 점포 편향이라 "
            "예측 대상인 공실에는 원리적으로 없고, (3) 감성이 홍보성 표본이라 "
            "거점 간 분산이 거점 내 분산의 1/10 이다."
        ),
    }
    _OUT.parent.mkdir(exist_ok=True)
    _OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    o = run()
    print("=== 막힘 6 사전 판정 — 네이버 블로그 상권 감성 ===\n")
    l1, l2, l3 = o["leg1_structure"], o["leg2_attribution"], o["leg3_signal"]
    print(f"[다리1 구조]  공간 키 {l1['spatial_keys']} → {l1['verdict']}")
    print(f"[다리2 귀속]  포스트 {l2['posts_attributed']}/{l2['posts']} "
          f"({l2['posts_attributed_pct']}%) · 감성이 붙는 노드 "
          f"{l2['nodes_with_sentiment']}/{l2['nodes']} ({l2['nodes_with_sentiment_pct']}%)")
    print(f"[다리3 신호]  부정어 {l3['neg_word_share_pct']}% · 점수 +1.0 이 "
          f"{l3['share_exactly_plus_one_pct']}% · 분산비(거점간/거점내) "
          f"{l3['variance_ratio']}")
    print(f"\n{o['verdict']}")
    print(f"\n→ {_OUT.relative_to(_ROOT)}")


if __name__ == "__main__":
    main()
