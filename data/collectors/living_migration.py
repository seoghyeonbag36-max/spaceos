"""[Page·유동] 수도권 생활이동 수집기 — "몇 시에 · 어떤 사람이 · 어디서" 를 채운다.

## 이 데이터가 무엇인가

서울시 × KT 「수도권 생활이동」(data.seoul.go.kr OA-22300 계열). 행정동 단위 OD 로
**도착시간(0~23) · 출발 행정동 · 도착 행정동 · 성별 · 나이 · 이동유형 · 평균 이동시간
· 이동인구** 를 준다. 이동유형은 출근·등교·쇼핑·관광·병원·귀가·기타 7종이다.

기존 `living_population.py`(생활인구)는 **체류** — 몇 명이 있나 — 만 안다. 이 수집기가
그 위에 **어디서 왔나 · 왜 왔나** 를 얹는다. 대체가 아니라 레이어 추가다.

⚠ **행정안전부 「지역별 인구이동 현황」과 혼동하지 말 것.** 그쪽은 주민등록 전입신고
기반이라 월 단위 **거주지 이전**이고 시간대 축이 아예 없다. 상권 방문을 못 센다.

## REST 가 아니라 파일이다 (설계가 갈리는 지점)

이 데이터셋은 `/F/` — **파일(ZIP) 다운로드**이고 일별로 쌓인다. 저장소의 다른 수집기처럼
`urlopen` 페이징을 돌 수 없다. 그리고 행정동 OD × 24시간 × 성 × 연령 × 이동유형이라
하루치도 수백만 행이다. 그래서 이 수집기는:

  1. **내려받은 파일을 읽는 쪽**이다(다운로드는 포털 로그인 뒤라 자동화하지 않는다).
  2. 원본을 bronze 에 **그대로 쌓지 않는다.** 스트리밍으로 읽으며 즉시 접는다 —
     `build_building_attrs` 가 85MB 대장을 행 단위로 접는 것과 같은 이유다.
  3. 거점 **도착 행정동**에 걸리는 행만 남긴다(`build_hub_adong` 산출물 기준).

파일 위치: `SEOUL_MIGRATION_DIR` 환경변수 또는 첫 번째 인자. `.zip` · `.csv` 둘 다 읽는다.

## 컬럼명을 고정하지 않는다

포털 파일의 헤더 표기가 배포분마다 흔들린다(공백·괄호·영문 병기). 그래서 헤더를
**정규화 후 부분일치**로 매핑하고, 하나라도 못 찾으면 **실제 헤더를 찍고 멈춘다.**
조용히 기본값을 쓰면 근거 없는 숫자가 gold 까지 흘러간다.

산출: bronze/{slug}/{날짜}/living_migration.json
실행:
  python -m data.collectors.living_migration <파일디렉터리> [slug ...]
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from data.collectors.common import load_env, save_json, today
from data.config.page_hubs import HUBS
from data.pipelines.build_hub_adong import load as load_hub_adong

# 헤더 정규화 후 이 조각이 들어 있으면 그 열로 본다. 순서가 곧 우선순위다.
_COLS: dict[str, tuple[str, ...]] = {
    "ym":       ("대상연월", "연월"),
    "dow":      ("요일",),
    "hour":     ("도착시간", "시간대", "도착시각"),
    "org":      ("출발행정동", "출발시군구", "출발지"),
    "dst":      ("도착행정동", "도착시군구", "도착지"),
    "sex":      ("성별",),
    "age":      ("나이", "연령"),
    "purpose":  ("이동유형", "이동목적"),
    "mins":     ("평균이동시간", "이동시간"),
    "pop":      ("이동인구", "이동인구합"),
}

# 이동유형 코드 → 한글. 배포분에 따라 이미 한글인 경우도 있어 양쪽을 받는다.
PURPOSES = ("출근", "등교", "쇼핑", "관광", "병원", "귀가", "기타")

_MASK = "*"          # KT 비식별 처리로 인구가 가려진 행 표기


def _norm(s: str) -> str:
    """헤더 정규화 — 공백·괄호·언더바를 걷어낸다."""
    return "".join(ch for ch in str(s) if ch.isalnum())


def _map_header(header: list[str]) -> dict[str, int]:
    """헤더 → {논리명: 열 index}. 못 찾은 것이 있으면 실제 헤더를 알리고 멈춘다."""
    norm = [_norm(h) for h in header]
    idx: dict[str, int] = {}
    for logical, cands in _COLS.items():
        for c in cands:
            hit = next((i for i, h in enumerate(norm) if _norm(c) in h), None)
            if hit is not None:
                idx[logical] = hit
                break
    missing = [k for k in _COLS if k not in idx]
    if missing:
        raise SystemExit(
            f"[migration] 컬럼 매핑 실패 {missing}\n"
            f"    실제 헤더: {header}\n"
            f"    → _COLS 에 이 배포분 표기를 추가할 것 (추측으로 진행하지 않는다)")
    return idx


def _rows(path: Path):
    """zip 안의 csv 든 맨 csv 든 한 줄씩 흘려보낸다 (통째로 메모리에 올리지 않는다)."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not name.lower().endswith(".csv"):
                    continue
                with z.open(name) as fh:
                    yield from csv.reader(io.TextIOWrapper(fh, encoding="utf-8-sig"))
    else:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            yield from csv.reader(fh)


def _pop(v: str) -> float | None:
    """이동인구 — 비식별 마스킹(`*`)은 0 이 아니라 '모름'이다. 0 으로 접지 않는다."""
    s = str(v).strip()
    if not s or s == _MASK:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def collect(src: Path, slugs: list[str]) -> dict[str, dict]:
    hub_adong = load_hub_adong()
    if not hub_adong:
        raise SystemExit("[migration] silver/hub_adong.json 없음 — "
                         "먼저 `python -m data.pipelines.build_hub_adong` 를 돌릴 것")

    # 도착 행정동 → [거점]. 한 행정동이 여러 거점에 걸릴 수 있다(무해 — 양쪽에 센다).
    dst_idx: dict[str, list[str]] = defaultdict(list)
    for slug in slugs:
        for cd in (hub_adong.get(slug) or {}):
            dst_idx[str(cd)].append(slug)
    if not dst_idx:
        raise SystemExit(f"[migration] 대상 거점의 행정동이 비어 있다: {slugs}")

    files = sorted(p for p in ([src] if src.is_file() else src.iterdir())
                   if p.suffix.lower() in (".zip", ".csv"))
    if not files:
        raise SystemExit(f"[migration] {src} 에 .zip/.csv 가 없다")
    print(f"[migration] 파일 {len(files)}개 · 도착 행정동 {len(dst_idx)}개 · "
          f"거점 {len(slugs)}")

    # slug → 축별 누적. 축을 여기서 다 접어 두면 gold 빌더가 파일을 다시 안 읽는다.
    acc: dict[str, dict] = {s: {
        "hour": defaultdict(float),                 # 도착시간 0~23
        "purpose": defaultdict(float),              # 이동유형
        "sex_age": defaultdict(float),              # "F|20"
        "hour_purpose": defaultdict(float),         # "14|쇼핑"
        "origin": defaultdict(float),               # 출발 행정동
        "dow": defaultdict(float),
        "mins_num": 0.0, "mins_den": 0.0,           # 이동시간 가중평균용
        "rows": 0, "masked": 0, "pop_total": 0.0, "ym": set(),
    } for s in slugs}

    scanned = 0
    for path in files:
        it = _rows(path)
        try:
            header = next(it)
        except StopIteration:
            continue
        ix = _map_header(header)
        for row in it:
            scanned += 1
            if len(row) <= max(ix.values()):
                continue
            hits = dst_idx.get(str(row[ix["dst"]]).strip())
            if not hits:
                continue
            pop = _pop(row[ix["pop"]])
            hour = str(row[ix["hour"]]).strip()
            purpose = str(row[ix["purpose"]]).strip()
            sex = str(row[ix["sex"]]).strip()
            age = str(row[ix["age"]]).strip()
            org = str(row[ix["org"]]).strip()
            dow = str(row[ix["dow"]]).strip()
            try:
                mins = float(row[ix["mins"]])
            except (TypeError, ValueError):
                mins = None
            for slug in hits:
                a = acc[slug]
                a["rows"] += 1
                a["ym"].add(str(row[ix["ym"]]).strip())
                if pop is None:
                    a["masked"] += 1
                    continue
                a["pop_total"] += pop
                a["hour"][hour] += pop
                a["purpose"][purpose] += pop
                a["sex_age"][f"{sex}|{age}"] += pop
                a["hour_purpose"][f"{hour}|{purpose}"] += pop
                a["origin"][org] += pop
                a["dow"][dow] += pop
                if mins is not None:
                    a["mins_num"] += mins * pop
                    a["mins_den"] += pop
        print(f"[migration] {path.name} 처리 — 누적 스캔 {scanned:,}행")

    out: dict[str, dict] = {}
    for slug, a in acc.items():
        if not a["rows"]:
            print(f"[migration:{slug}] 걸린 행 0 — 행정동 코드 자릿수 확인 필요")
            continue
        doc = {
            "ym": sorted(a["ym"]),
            "rows": a["rows"],
            "masked_rows": a["masked"],
            "pop_total": round(a["pop_total"], 1),
            "avg_move_min": round(a["mins_num"] / a["mins_den"], 2) if a["mins_den"] else None,
            "by_hour": {k: round(v, 1) for k, v in sorted(a["hour"].items())},
            "by_dow": {k: round(v, 1) for k, v in sorted(a["dow"].items())},
            "by_purpose": {k: round(v, 1) for k, v in
                           sorted(a["purpose"].items(), key=lambda kv: -kv[1])},
            "by_sex_age": {k: round(v, 1) for k, v in
                           sorted(a["sex_age"].items(), key=lambda kv: -kv[1])},
            "by_hour_purpose": {k: round(v, 1) for k, v in sorted(a["hour_purpose"].items())},
            # 출발지는 꼬리가 길다 — 상위 50 만 남긴다(나머지는 합으로).
            "origin_top": {k: round(v, 1) for k, v in
                           sorted(a["origin"].items(), key=lambda kv: -kv[1])[:50]},
            "origin_other": round(
                sum(sorted(a["origin"].values(), reverse=True)[50:]), 1),
            "note": ("도착 행정동 기준 집계. 이동인구가 `*`(KT 비식별)인 행은 "
                     "masked_rows 로만 세고 합계에서 뺐다 — 0 으로 접으면 과소집계다."),
        }
        save_json(doc, slug, "living_migration.json")
        out[slug] = doc
        top = list(doc["by_purpose"].items())[:3]
        print(f"[migration:{slug}] {doc['rows']:,}행 · 이동인구 {doc['pop_total']:,.0f} · "
              + " · ".join(f"{k} {v/doc['pop_total']:.0%}" for k, v in top))
    return out


def main() -> None:
    load_env()
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    src = Path(argv[0]) if argv else Path(os.getenv("SEOUL_MIGRATION_DIR", ""))
    if not src or not src.exists():
        raise SystemExit(
            "[migration] 원본 위치를 못 찾았다.\n"
            "  data.seoul.go.kr OA-22300(수도권 생활이동)에서 파일을 내려받은 뒤\n"
            "  python -m data.collectors.living_migration <디렉터리> [slug ...]\n"
            "  또는 data/.env 에 SEOUL_MIGRATION_DIR= 를 넣을 것")
    slugs = [s for s in argv[1:] if s in HUBS] or list(HUBS)
    collect(src, slugs)


if __name__ == "__main__":
    main()
