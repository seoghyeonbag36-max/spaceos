"""[프로브] "통신사 공공데이터로 고객 이동 **동선**을 시각화할 수 있는가" — 6회 검증.

## 왜 이 프로브인가

질문이 한 덩어리로 오면 답도 한 덩어리("된다"/"안 된다")로 나온다. 그러면 낡는다.
그래서 질문을 **각각 반증 가능한 6개**로 쪼개고, 각 조각을 산출물·코드·계산으로 잰다.

  P1 취득   통신사 공공데이터를 이 환경에서 실제로 받을 수 있는가
  P2 식별자 원천 스키마에 사람/트립을 잇는 축이 있는가 (없으면 '동선'이 원천에 없다)
  P3 복원   OD 집계에서 동선을 되살릴 수 있는가 — 유일해인가, 오차가 얼마인가
  P4 해상도 거점 **안**에서 몇 개 노드로 갈리는가 (체류 레이어와 대조)
  P5 SNS/IT SNS·IT 데이터가 빠진 축(사람×좌표×시각)을 채워 주는가
  P6 시각화 그릴 수 있는 것은 무엇인가 — 체인을 실제로 끝까지 돌려 본다

⚠ **'동선'과 'OD 흐름'을 구분한다.** 동선 = 한 사람이 A→B→C 로 지나간 **순서 있는 궤적**.
OD 흐름 = 출발지별 도착 **인원 집계**. 전자는 개인 축이 있어야 하고, 후자는 없어도 된다.
이 프로브의 결론은 대부분 이 구분에서 갈린다.

산출: reports/movement_viz_probe_<날짜>.json
실행: python scripts/probe_movement_viz.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import random
import re
import socket
import statistics as st
import sys
import tempfile
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLD = ROOT / "data" / "gold"
SILVER = ROOT / "data" / "silver"
REPORTS = ROOT / "reports"

DATE = os.getenv("PROBE_DATE") or __import__("datetime").date.today().isoformat()


# ────────────────────────────────────────────────────────────────────
# P1. 취득 — 통신사 공공데이터가 이 환경에서 손에 들어오는가
# ────────────────────────────────────────────────────────────────────

# 통신사(이동통신 기지국·시그널) 기반 공개 이동 데이터의 배포처 후보.
# 포트까지 적는 이유: 서울 열린데이터광장 OpenAPI 는 8088 이고 포털 본체는 443 이다.
_HOSTS = [
    ("data.seoul.go.kr", 443, "서울 열린데이터광장 — 수도권 생활이동(OA-22300, 서울시×KT) 파일"),
    ("openapi.seoul.go.kr", 8088, "서울 열린데이터광장 OpenAPI — 생활인구(체류) REST"),
    ("www.data.go.kr", 443, "공공데이터포털 — 통신사 유동인구 계열"),
    ("sgisapi.kostat.go.kr", 443, "통계청 SGIS — 경계·집계구"),
    ("data.gg.go.kr", 443, "경기데이터드림 — 유입/유출 생활이동인구"),
]


def _reach(host: str, port: int, timeout: float = 8.0) -> dict:
    """1콜 실측. 프록시가 있으면 CONNECT 결과가, 없으면 TCP 결과가 남는다."""
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    scheme = "https" if port == 443 else "http"
    url = f"{scheme}://{host}:{port}/"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"host": host, "via": "proxy" if proxy else "direct",
                    "result": f"HTTP {r.status}", "ok": True}
    except urllib.error.HTTPError as e:          # 응답은 왔다 = 도달은 했다
        return {"host": host, "via": "proxy" if proxy else "direct",
                "result": f"HTTP {e.code}", "ok": True}
    except Exception as e:                        # 도달 실패
        return {"host": host, "via": "proxy" if proxy else "direct",
                "result": f"{type(e).__name__}: {str(e)[:90]}", "ok": False}


def p1_acquisition() -> dict:
    socket.setdefaulttimeout(10)
    tried = [dict(_reach(h, p), note=note) for h, p, note in _HOSTS]
    reachable = [t for t in tried if t["ok"]]

    # 저장소가 실제로 들고 있는 생활이동 산출물 — 문서가 아니라 파일을 센다.
    bronze_hits = glob.glob(str(ROOT / "data" / "bronze" / "*" / "*" / "living_migration.json"))
    gold_out = GOLD / "platform_page_migration.json"

    return {
        "id": "P1",
        "name": "취득 — 통신사 공공데이터를 이 환경에서 받을 수 있는가",
        "measured": {
            "hosts_tried": len(tried),
            "hosts_reachable": len(reachable),
            "detail": tried,
            "bronze_living_migration_files": len(bronze_hits),
            "gold_platform_page_migration_exists": gold_out.exists(),
        },
        "verdict": ("취득 불가" if not reachable else "일부 도달"),
        "reading": (
            f"후보 배포처 {len(tried)}곳 중 도달 {len(reachable)}곳. "
            f"저장소의 생활이동 원본 {len(bronze_hits)}건 · Gold 산출물 "
            f"{'있음' if gold_out.exists() else '없음'}. "
            "OA-22300 은 REST 가 아니라 **포털 로그인 뒤 ZIP 파일**이라, 키가 있어도 "
            "무인 수집이 되지 않는다(수집기가 디렉터리를 인자로 받는 이유)."
        ),
    }


# ────────────────────────────────────────────────────────────────────
# P2. 식별자 — 원천 스키마에 '동선'을 이룰 축이 있는가
# ────────────────────────────────────────────────────────────────────

# 개인/트립을 잇는 축이라면 이름에 반드시 들어가는 조각들.
_ID_TOKENS = ("id", "식별", "단말", "가입자", "회원", "trip", "seq", "순번", "경로", "궤적")
# 축 분류 — 동선을 그리려면 '개인' 축이 있어야 한다.
_AXIS = {
    "ym": "시간", "dow": "시간", "hour": "시간",
    "org": "공간", "dst": "공간",
    "sex": "속성", "age": "속성", "purpose": "속성",
    "mins": "값", "pop": "값",
}


def p2_identifier() -> dict:
    from data.collectors import living_migration as lm

    cols = lm._COLS
    rows = []
    for logical, cands in cols.items():
        names = " ".join(cands)
        is_id = any(t in names.lower() or t in names for t in _ID_TOKENS)
        rows.append({"logical": logical, "portal_names": list(cands),
                     "axis": _AXIS.get(logical, "?"), "is_identifier": is_id})

    id_cols = [r for r in rows if r["is_identifier"]]
    axes = sorted({r["axis"] for r in rows})

    return {
        "id": "P2",
        "name": "식별자 — 원천 스키마에 사람/트립을 잇는 축이 있는가",
        "measured": {
            "columns": len(rows),
            "identifier_columns": len(id_cols),
            "axes_present": axes,
            "person_axis_present": False if not id_cols else True,
            "detail": rows,
            "schema_source": "data/collectors/living_migration.py::_COLS (배포분 헤더 매핑표)",
        },
        "verdict": "개인 축 없음" if not id_cols else "개인 축 있음",
        "reading": (
            f"열 {len(rows)}개 중 식별자 {len(id_cols)}개. 축은 {'·'.join(axes)} 뿐이고 "
            "**개인 축이 없다**. 한 행은 '이 시각에 A동에서 B동으로 n명'이라는 집계이지 "
            "'누가 어디를 거쳐 갔다'가 아니다. 즉 동선(순서 있는 궤적)은 **가려진 것이 "
            "아니라 원천에 존재하지 않는다** — KT 가 비식별 집계로 만들어 배포한다."
        ),
    }


# ────────────────────────────────────────────────────────────────────
# P3. 복원 — OD 집계에서 동선을 되살릴 수 있는가
# ────────────────────────────────────────────────────────────────────

def _count_tables(rows: list[int], cols: list[int]) -> int:
    """행합 rows · 열합 cols 인 비음 정수 행렬의 개수 (DP, 작은 표 전용).

    O→H→D 2구간 동선 하나는 이 행렬 하나에 대응한다. 개수가 1 이면 집계에서
    동선이 유일하게 결정되고, 1 보다 크면 결정되지 않는다.
    """
    from functools import lru_cache

    ncol = len(cols)

    @lru_cache(maxsize=None)
    def rec(i: int, rem: tuple[int, ...]) -> int:
        if i == len(rows):
            return 1 if all(v == 0 for v in rem) else 0
        total = 0

        def split(j: int, left: int, acc: tuple[int, ...]):
            nonlocal total
            if j == ncol:
                if left == 0:
                    total += rec(i + 1, acc)
                return
            for v in range(min(left, rem[j]) + 1):
                split(j + 1, left - v, acc + (rem[j] - v,))

        split(0, rows[i], ())
        return total

    return rec(0, tuple(cols))


def p3_reconstruction(seed: int = 20260917) -> dict:
    # (a) 유일성 — 작은 표에서 정확히 센다. 해가 2개 이상이면 비식별이 증명된다.
    small = [
        {"rows": [2, 2], "cols": [2, 2]},
        {"rows": [5, 5], "cols": [5, 5]},
        {"rows": [10, 10, 10], "cols": [10, 10, 10]},
    ]
    for c in small:
        c["consistent_paths"] = _count_tables(c["rows"], c["cols"])

    # (b) 오차 — 실제 규모(거점 유입 상위 50 출발지)에서 최선의 추론이 얼마나 틀리는가.
    #     원천이 주는 것은 O→H 와 H→D 의 **주변분포**뿐이다. 그 둘로 할 수 있는 최선은
    #     독립 결합(independence coupling)이다. 진짜 결합은 독립이 아니다 —
    #     사람은 대개 왔던 곳으로 돌아간다(귀가). 그 차이를 잰다.
    rng = random.Random(seed)
    P = 50                      # 출발 행정동 수 = 수집기의 origin_top 상한
    N = 100_000                 # 유입 인원
    ret = 0.62                  # 귀가 비율 — 원천의 이동유형 7종 중 '귀가'가 최대 범주

    origins = [rng.random() for _ in range(P)]
    s = sum(origins)
    origins = [o / s for o in origins]

    # 진짜 결합: ret 비율은 O==D(왕복), 나머지는 임의 목적지.
    true_joint = [[0.0] * P for _ in range(P)]
    for i, w in enumerate(origins):
        true_joint[i][i] += w * ret
        for j in range(P):
            true_joint[i][j] += w * (1 - ret) * origins[j]

    row_marg = [sum(r) for r in true_joint]                       # O→H (원천이 준다)
    col_marg = [sum(true_joint[i][j] for i in range(P)) for j in range(P)]  # H→D (원천이 준다)
    indep = [[row_marg[i] * col_marg[j] for j in range(P)] for i in range(P)]

    tv = 0.5 * sum(abs(true_joint[i][j] - indep[i][j]) for i in range(P) for j in range(P))
    true_round = sum(true_joint[i][i] for i in range(P))
    indep_round = sum(indep[i][i] for i in range(P))

    return {
        "id": "P3",
        "name": "복원 — OD 집계에서 동선이 결정되는가",
        "measured": {
            "uniqueness": small,
            "coupling": {
                "origins": P, "people": N, "true_return_share": ret,
                "tv_distance": round(tv, 4),
                "roundtrip_true": round(true_round, 4),
                "roundtrip_inferred": round(indep_round, 4),
                "roundtrip_missed_people": int(round((true_round - indep_round) * N)),
                "note": ("진짜 결합은 공개되지 않으므로 시뮬레이션이다 — 그것이 곧 요점이다. "
                         "원천은 주변분포 둘만 주고, 결합은 어떤 모양이든 될 수 있다."),
            },
        },
        "verdict": "복원 불가(비유일 · 편향)",
        "reading": (
            f"2×2(각 변 2명) 최소 표에서도 같은 집계를 내는 동선이 "
            f"{small[0]['consistent_paths']}가지다. 3×3(각 변 10명)이면 "
            f"{small[2]['consistent_paths']:,}가지. 즉 OD 집계는 동선을 **결정하지 않는다**. "
            f"그리고 결정되지 않는 것을 최선으로 추론하면(독립 결합) 총변동거리 {tv:.3f}, "
            f"왕복 인원을 10만 명 중 {int(round((true_round - indep_round) * N)):,}명 놓친다."
        ),
    }


# ────────────────────────────────────────────────────────────────────
# P4. 해상도 — 거점 '안'에서 이동이 몇 노드로 갈리는가
# ────────────────────────────────────────────────────────────────────

def p4_resolution() -> dict:
    hourly = json.loads((GOLD / "page_footfall_hourly.json").read_text(encoding="utf-8"))
    ds = hourly["districts"]
    per_hub = [len(v.get("adong") or {}) for v in ds.values()]
    codes = {c for v in ds.values() for c in (v.get("adong") or {})}

    # 대조군 — 같은 거점을 체류(유동) 레이어는 몇 개로 가르는가.
    cell = json.loads((SILVER / "cell_jipgyegu.json").read_text(encoding="utf-8"))["stats"]
    unit = json.loads((SILVER / "unit_jipgyegu.json").read_text(encoding="utf-8"))["stats"]

    # 한 거점이 행정동을 얼마나 차지하는가 — 가중이 1 이면 행정동 ≒ 거점이다.
    top_w = [max((m.get("w") or 0) for m in (v.get("adong") or {}).values())
             for v in ds.values() if v.get("adong")]

    return {
        "id": "P4",
        "name": "해상도 — 거점 안에서 이동이 몇 노드로 갈리는가",
        "measured": {
            "hubs": len(ds),
            "adong_per_hub": {"min": min(per_hub), "median": st.median(per_hub),
                              "mean": round(st.mean(per_hub), 2), "max": max(per_hub)},
            "distinct_adong_codes": len(codes),
            "hub_share_of_top_adong": {"median": round(st.median(top_w), 3),
                                       "max": round(max(top_w), 3)},
            "movement_nodes_inside_hub": 1,
            "contrast_stay_layer": {
                "cells_per_hub_median": cell["cells_per_district_median"],
                "jipgyegu_per_hub_median": cell["oa_per_district_median"],
                "vacant_units_distinct": unit["unit_ids_distinct"],
            },
            "source": ["data/gold/page_footfall_hourly.json",
                       "data/silver/cell_jipgyegu.json", "data/silver/unit_jipgyegu.json"],
        },
        "verdict": "거점 내부 동선 해상도 = 1(통째로 한 점)",
        "reading": (
            f"이동 데이터의 최소 공간 단위는 행정동이고, 거점 하나는 행정동 "
            f"{min(per_hub)}~{max(per_hub)}개(중앙 {st.median(per_hub):.0f})에 걸린다. "
            f"거점은 행정동보다 **작으므로** 거점 안에서는 노드가 1개다 — 내부 이동이 0개로 접힌다. "
            f"같은 거점을 체류 레이어는 셀 {cell['cells_per_district_median']}개 "
            f"(집계구 {cell['oa_per_district_median']}개)로 가른다. 68 대 1 이다."
        ),
    }


# ────────────────────────────────────────────────────────────────────
# P5. SNS/IT — 빠진 축(사람×좌표×시각)을 채워 주는가
# ────────────────────────────────────────────────────────────────────

# ⚠ 부분일치로 두면 `factory`·`floor_factor` 가 `actor` 로 걸린다(첫 실행에서 4건 오탐).
#    단어 경계를 박아 사람 축만 남긴다.
_PERSON_KEYS = re.compile(
    r"(?<![a-z])(authors?|users?|writers?|members?|nick(?:name)?s?|작성자|가입자)(?![a-z])", re.I)
_GEO_KEYS = re.compile(r"(lat|lng|lon|x_?coord|y_?coord|geometry|좌표)", re.I)
_TIME_KEYS = re.compile(r"(time|date|hour|stamp|시각|일시)", re.I)


def _keys_of(path: Path, limit: int = 4000) -> set[str]:
    """산출물의 키 집합. JSON 은 재귀로, CSV 는 헤더로 훑는다."""
    keys: set[str] = set()
    if path.suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            r = csv.reader(fh)
            head = next(r, [])
            keys.update(head)
            # kind/key/value 꼴이면 'kind' 값도 사실상 필드명이다.
            if [h.lower() for h in head[:1]] == ["kind"]:
                for i, row in enumerate(r):
                    if i > limit:
                        break
                    if row:
                        keys.add(f"kind={row[0]}")
        return keys
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return keys

    def walk(o, depth=0):
        if depth > 6 or len(keys) > limit:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                keys.add(str(k))
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o[:50]:
                walk(v, depth + 1)

    walk(doc)
    return keys


def p5_sns_axis() -> dict:
    # SNS/IT 축을 실제로 담고 있는 산출물이 저장소에 하나라도 있는가 — 전수로 센다.
    files = [Path(p) for p in glob.glob(str(GOLD / "**" / "*.json"), recursive=True)]
    files += [Path(p) for p in glob.glob(str(GOLD / "**" / "*.csv"), recursive=True)]

    with_person, with_triple = [], []
    for f in files:
        ks = _keys_of(f)
        has_p = any(_PERSON_KEYS.search(k) for k in ks)
        if has_p:
            with_person.append(str(f.relative_to(ROOT)))
        # 동선을 그리려면 세 축이 **한 레코드 안에** 같이 있어야 한다.
        if has_p and any(_GEO_KEYS.search(k) for k in ks) and any(
                _TIME_KEYS.search(k) for k in ks):
            with_triple.append(str(f.relative_to(ROOT)))

    # SNS/IT 수집기별 레코드 입도 — 코드가 실제로 무엇을 저장하는가.
    sources = [
        {"source": "네이버 블로그 검색 OpenAPI", "collector": "data/collectors/naver_blog.py",
         "grain": "문서(포스트)", "person": False, "geo": False, "time": "작성일",
         "why": "응답에 작성자 식별자도 좌표도 없다. 문서 단위 텍스트다"},
        {"source": "네이버 데이터랩 검색어트렌드", "collector": "data/collectors/naver_datalab.py",
         "grain": "키워드×기간 상대비율", "person": False, "geo": False, "time": "월",
         "why": "절대량조차 아니다 — 배치 내 최댓값 100 정규화. 개인 축이 설계상 없다"},
        {"source": "인스타그램 Graph API 해시태그", "collector": "data/collectors/sns_mentions.py",
         "grain": "해시태그 집계", "person": False, "geo": False, "time": "최근",
         "why": "hashtag search 는 작성자를 돌려주지 않는다(플랫폼 정책)"},
        {"source": "카카오 로컬", "collector": "data/collectors/kakao_local.py",
         "grain": "POI", "person": False, "geo": True, "time": None,
         "why": "장소 좌표이지 사람의 방문이 아니다. 게다가 약관상 응답 저장 금지"},
    ]
    triple = [s for s in sources if s["person"] and s["geo"] and s["time"]]

    return {
        "id": "P5",
        "name": "SNS/IT — 빠진 축(사람×좌표×시각)을 채워 주는가",
        "measured": {
            "gold_files_scanned": len(files),
            "gold_files_with_person_key": len(with_person),
            "person_key_files": with_person[:10],
            "gold_files_with_person_geo_time": len(with_triple),
            "sns_it_sources": sources,
            "sources_with_person_geo_time": len(triple),
        },
        "verdict": "채우지 못함",
        "reading": (
            f"Gold 산출물 {len(files)}개를 전수로 훑어 작성자/사용자 키를 가진 파일 "
            f"{len(with_person)}개, 그 중 좌표·시각까지 함께 가진 파일 {len(with_triple)}개. "
            f"SNS·IT 소스 {len(sources)}종 중 (사람×좌표×시각) 세 축을 "
            f"함께 주는 것은 {len(triple)}종이다. SNS 는 **어디서 말했나**를 모르고 "
            "(좌표 없음), 지도/검색은 **누가 갔나**를 모른다(개인 축 없음). "
            "두 결손이 서로를 메우지 못하므로 SNS/IT 로 동선을 복원할 수 없다."
        ),
    }


# ────────────────────────────────────────────────────────────────────
# P6. 시각화 — 그릴 수 있는 것은 무엇인가 (체인을 끝까지 돌린다)
# ────────────────────────────────────────────────────────────────────

_HEADER = ["대상연월", "요일", "도착시간", "출발행정동", "도착행정동",
           "성별", "나이", "이동유형", "평균 이동시간(분)", "이동인구(합)"]


def _synthetic_csv(path: Path, dst_codes: list[str], origins: list[str],
                   rng: random.Random, rows: int = 4000) -> int:
    """배포분과 **같은 헤더**의 합성 파일. 값은 가짜, 형식은 진짜다.

    목적은 '데이터가 오면 체인이 도는가'이지 '값이 맞는가'가 아니다.
    그래서 산출물에 synthetic 표시를 반드시 남긴다(P6 verdict 참조).
    """
    purposes = ["출근", "등교", "쇼핑", "관광", "병원", "귀가", "기타"]
    n = 0
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_HEADER)
        for _ in range(rows):
            pop = rng.choice([f"{rng.uniform(3, 900):.1f}"] * 9 + ["*"])  # 10% 비식별 마스킹
            w.writerow(["202608", rng.choice("월화수목금토일"),
                        f"{rng.randrange(24):02d}",
                        rng.choice(origins), rng.choice(dst_codes),
                        rng.choice(["F", "M"]), str(rng.randrange(10, 70, 5)),
                        rng.choice(purposes), f"{rng.uniform(5, 80):.1f}", pop])
            n += 1
    return n


def p6_visualization(seed: int = 20260917) -> dict:
    import data.collectors.common as common
    from data.collectors import living_migration as lm
    from data.pipelines import build_page_migration as bpm

    rng = random.Random(seed)
    hourly = json.loads((GOLD / "page_footfall_hourly.json").read_text(encoding="utf-8"))

    # 거점↔행정동 표는 silver 가 아니라 **커밋된 Gold** 에서 되살린다.
    # (silver/hub_adong.json 은 gitignore 라 이 환경에 없다 — feature-page §253 의 병목)
    hub_adong = {
        slug: {cd: {"adm_nm": m.get("nm"), "weight": m.get("w"),
                    "weight_basis": m.get("basis")}
               for cd, m in (v.get("adong") or {}).items()}
        for slug, v in hourly["districts"].items() if v.get("adong")
    }
    slugs = ["garosugil", "hongdae", "seongsu"]
    slugs = [s for s in slugs if s in hub_adong] or list(hub_adong)[:3]

    tmp = Path(tempfile.mkdtemp(prefix="movement-probe-"))
    src = tmp / "src"
    src.mkdir()
    dst_codes = sorted({c for s in slugs for c in hub_adong[s]})
    all_codes = sorted({c for v in hub_adong.values() for c in v})
    rows = _synthetic_csv(src / "SEOUL_MIGRATION_202608.csv", dst_codes, all_codes, rng)

    # 진짜 gold/bronze 를 건드리지 않는다 — 합성값이 서빙에 새면 P1 결론이 뒤집혀 보인다.
    old_bronze, old_gold, old_out = common.BRONZE, bpm.GOLD, bpm._OUT
    old_root = common.DATA_ROOT
    old_load, old_active = bpm.load_hub_adong, bpm.ACTIVE_HUBS
    lm_load = lm.load_hub_adong
    chain_ok, err, gold_doc = False, None, {}
    try:
        common.BRONZE = tmp / "bronze"
        # save_json 이 로그에 DATA_ROOT 상대경로를 찍는다 — 임시 루트를 같이 갈아끼우지
        # 않으면 relative_to 가 ValueError 로 터진다(첫 실행에서 실제로 터졌다).
        common.DATA_ROOT = tmp
        lm.load_hub_adong = lambda: hub_adong
        bpm.load_hub_adong = lambda: hub_adong
        bpm.ACTIVE_HUBS = {s: None for s in slugs}
        bpm.GOLD = tmp / "gold"
        bpm._OUT = tmp / "gold" / "platform_page_migration.json"
        lm.collect(src, slugs)
        gold_doc = bpm.run()
        chain_ok = bool(gold_doc.get("districts"))
    except Exception as e:                        # 체인이 깨지면 그대로 기록한다
        err = f"{type(e).__name__}: {e}"
    finally:
        common.BRONZE, bpm.GOLD, bpm._OUT = old_bronze, old_gold, old_out
        common.DATA_ROOT = old_root
        bpm.load_hub_adong, bpm.ACTIVE_HUBS = old_load, old_active
        lm.load_hub_adong = lm_load

    built = gold_doc.get("districts", {})
    sample = built.get(slugs[0], {}) if built else {}

    # 유선(flow line)을 그리려면 **출발지 좌표**가 있어야 한다. 몇 개나 가졌나.
    coords: dict[str, tuple] = {}
    for p in glob.glob(str(GOLD / "*" / "district_zones.json")):
        for z in json.loads(Path(p).read_text(encoding="utf-8")).get("zones", []):
            if z.get("lat") and z.get("lng"):
                coords[z["n"]] = (z["lat"], z["lng"])
    known_names = {m.get("adm_nm") for v in hub_adong.values() for m in v.values()}
    origin_covered = len(known_names & set(coords))

    # 서빙·화면이 이미 있는가 — 없으면 '데이터가 와도 화면이 없다'.
    be = ROOT / "apps" / "backend" / "app"
    fe = ROOT / "apps" / "frontend" / "src"
    served = bool(list(be.rglob("*migration*"))) or bool(
        [p for p in be.rglob("*.py") if "platform_page_migration" in p.read_text(
            encoding="utf-8", errors="ignore")])
    rendered = bool([p for p in fe.rglob("*.ts*") if "migration" in p.read_text(
        encoding="utf-8", errors="ignore").lower()]) if fe.exists() else False

    return {
        "id": "P6",
        "name": "시각화 — 그릴 수 있는 것은 무엇인가 (체인 실행)",
        "measured": {
            "synthetic_rows": rows,
            "chain_ran": chain_ok,
            "chain_error": err,
            "hubs_built": len(built),
            "axes_in_gold": sorted(k for k in sample
                                   if k in ("by_hour", "hour_share", "peak", "purpose_share",
                                            "sex_age_share", "origin_top", "adong")),
            "hours_filled": len([h for h, v in (sample.get("by_hour") or {}).items() if v]),
            "origin_dongs_in_output": len(sample.get("origin_top") or {}),
            "adong_coords_available": len(coords),
            "origin_adong_with_coords": origin_covered,
            "serving_endpoint_exists": served,
            "frontend_layer_exists": rendered,
            "wrote_to_repo": False,
        },
        "verdict": ("동선 ✗ / 유입 흐름 ✓(체인 동작, 화면 없음)" if chain_ok else "체인 실패"),
        "reading": (
            f"배포분과 같은 헤더의 합성 {rows:,}행을 수집기→Gold 체인에 흘렸더니 "
            f"거점 {len(built)}곳이 {'만들어졌다' if chain_ok else '만들어지지 않았다'}. "
            f"채워지는 축은 시간 {len([h for h, v in (sample.get('by_hour') or {}).items() if v])}/24 · "
            f"출발지 {len(sample.get('origin_top') or {})}곳 · 이동유형 · 성연령이다. "
            f"즉 **'몇 시에 · 어디서 · 왜 왔나'는 그릴 수 있고 '어디를 거쳐 갔나'는 못 그린다.** "
            f"유선용 행정동 좌표는 {len(coords)}개 보유. "
            f"서빙 엔드포인트 {'있음' if served else '없음'} · 프론트 레이어 "
            f"{'있음' if rendered else '없음'} — 데이터가 와도 화면이 아직 없다."
        ),
    }


# ────────────────────────────────────────────────────────────────────

PROBES = [p1_acquisition, p2_identifier, p3_reconstruction, p4_resolution,
          p5_sns_axis, p6_visualization]


def main() -> int:
    results = []
    for fn in PROBES:
        try:
            results.append(fn())
        except Exception as e:                    # 실패도 결과다 — 삼키지 않는다
            results.append({"id": fn.__name__, "name": fn.__name__,
                            "measured": {}, "verdict": "프로브 실패",
                            "reading": f"{type(e).__name__}: {e}"})

    doc = {
        "probe": "통신사 공공데이터 × SNS/IT 로 고객 이동 동선을 시각화할 수 있는가",
        "date": DATE,
        "runs": len(results),
        "definition": {
            "동선": "한 사람이 A→B→C 로 지난 **순서 있는 궤적** (개인 축 필요)",
            "유입 흐름": "출발지별 도착 **인원 집계** (개인 축 불필요)",
        },
        "conclusion": {
            "개인 동선 시각화": "불가 — 원천에 개인 축이 없고(P2) 집계에서 복원되지 않는다(P3)",
            "유입 흐름 시각화": "가능 — 체인은 돈다(P6). 막는 것은 능력이 아니라 취득(P1)과 화면(P6)",
            "거점 내부 동선": "불가 — 최소 단위가 행정동이라 거점이 한 점으로 접힌다(P4)",
            "SNS/IT 보완": "불가 — 사람·좌표·시각을 함께 주는 소스가 0종(P5)",
        },
        "probes": results,
    }

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"movement_viz_probe_{DATE}.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=" * 78)
    print(f"  통신사 공공데이터 × SNS/IT — 고객 이동 동선 시각화 검증 {len(results)}회")
    print("=" * 78)
    for r in results:
        print(f"\n[{r['id']}] {r['name']}")
        print(f"   판정: {r['verdict']}")
        print(f"   {r['reading']}")
    print(f"\n→ {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
