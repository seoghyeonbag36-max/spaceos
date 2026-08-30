"""[Page·분자 보강] 경기 인허가 수집기 — 고양·파주 거점의 영업 중 업소 하한.

서울은 `seoul_licensing.py` 가 서울 열린데이터광장에서 받는다. 경기는 그 소스가 없어서
**경기데이터드림 Open API `GENRESTRT`**(일반음식점 현황_인허가)로 받는다.
죽은 경로들(LOCALDATA 폐쇄 · 표준데이터 파일 403 · data.go.kr LINK형)과 이 선택의 근거는
docs/finding-gyeonggi-licensing-source-2026-08-30.md.

## 왜 전량을 훑는가

이 API 에는 **시군 필터가 없다.** `SIGUN_NM` 은 무시되고(고양시/파주시/빈값 모두 486,387행),
`SIGUN_CD` 는 파라미터로 인식되지만 응답의 `SIGUN_CD` 가 전 행 null 이라 코드값을 알 수 없다
(2026-08-30 실측). 그래서 서울 수집기와 같은 전략을 쓴다 — **전량을 한 번 페이징하며
각 행을 거점 버킷에 나눠 담는다.** 경기데이터드림은 호출 횟수 제한이 없다.

## 좌표계 (중요)

경기 응답은 **이미 WGS84**(`REFINE_WGS84_LAT/LOGT`)다. 서울 인허가의 X/Y 는 중부원점 TM
계열이라 `build_page_master._licensed_pip` 이 `EPSG:2097 → 4326` 변환을 한다. 그래서
여기서 만드는 행에는 **`CRS` 를 명시**하고, 소비층이 그 표기를 보고 변환을 건너뛴다.
표기를 빼먹으면 변환을 한 번 더 먹어 좌표가 통째로 어긋나는데, **PIP 가 아무 건물에도
안 걸려 분자 보강이 0 이 되고 그게 정상처럼 보인다** — 조용히 틀리는 종류다.

산출: bronze/{slug}/{날짜}/licensing_biz.json  (서울 수집기와 **같은 스키마** + `CRS`)
중간: bronze/_gg_licensing_stage/{날짜}.json   (중단 대비 — 487콜을 다시 태우지 않는다)

실행: python -m data.collectors.gg_licensing [slug ...] [--force]
      거점을 비우면 GYEONGGI_HUBS 중 stores_raw 가 있는 거점 전부.
"""
from __future__ import annotations

import json
import re
import sys
import time

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import (BRONZE, latest_bronze, load_env, load_latest,
                                    save_json, today)
from data.config.page_hubs import GYEONGGI_HUBS, get_hub

_URL = "https://openapi.gg.go.kr/GENRESTRT"
_PAGE = 1000          # 포털 최대
_STAGE = BRONZE / "_gg_licensing_stage"
_LABEL = "일반음식점"

# 주소 → (시군, 구, 동). 고양은 구가 있고(`고양시 덕양구 화정동`) 파주는 없다
# (`파주시 금촌동`). 읍·면 단위는 리가 잎이다(`파주시 월롱면 도내리`).
_SIGUN = re.compile(r"([가-힣]+[시군])(?:\s|$)")
_GU = re.compile(r"([가-힣]+구)(?:\s|$)")
_LEAF = re.compile(r"([가-힣]+[0-9]*(?:동|가|리))(?:\s|$)")


def _place(addr: str) -> tuple[str, str, str] | None:
    """지번주소 → (시군, 구, 동). 못 뽑으면 None."""
    if not addr:
        return None
    sig = _SIGUN.search(addr)
    leaf = _LEAF.search(addr)
    if not sig or not leaf:
        return None
    gu = _GU.search(addr)
    return (sig.group(1), gu.group(1) if gu else "", leaf.group(1))


def _hub_places(slug: str) -> set[tuple[str, str, str]]:
    """거점 stores_raw 의 lnoAdr 에서 (시군, 구, 동) 집합 파생.

    거점 상수로 적지 않는다 — 거점이 걸치는 동은 반경에 따라 달라지고, 손으로 적으면
    반경을 바꿀 때마다 낡는다(서울 수집기와 같은 원칙).
    """
    out: set[tuple[str, str, str]] = set()
    for s in load_latest(slug, "stores_raw.json") or []:
        p = _place(str(s.get("lnoAdr") or ""))
        if p:
            out.add(p)
    return out


def _norm(r: dict) -> dict:
    """경기 응답 1행 → 서울 인허가 스키마(소비층 계약) + 좌표계 표기."""
    state = str(r.get("BSN_STATE_NM") or "").strip()
    return {
        "MGTNO": r.get("MANAGE_NO"),
        "BPLCNM": r.get("BIZPLC_NM"),
        "UPTAENM": r.get("BIZCOND_DIV_NM_INFO") or r.get("SANITTN_BIZCOND_NM"),
        # 서울은 "01"=영업. 경기는 코드 체계가 달라(BSN_STATE_DIV_CD) 이름으로 판정해
        # 서울 코드로 옮긴다 — 소비층이 "01" 과 "영업" 둘 다 보므로 양쪽을 채운다.
        "TRDSTATEGBN": "01" if "영업" in state else "02",
        "TRDSTATENM": state,
        "DTLSTATEGBN": None,        # 경기 응답에 상세상태 없음 — 지어내지 않는다
        "DTLSTATENM": None,
        "DCBYMD": r.get("CLSBIZ_DE"),
        "APVPERMYMD": r.get("LICENSG_DE"),
        "SITEWHLADDR": r.get("REFINE_LOTNO_ADDR"),
        "RDNWHLADDR": r.get("REFINE_ROADNM_ADDR"),
        "SITEAREA": r.get("LOCPLC_AR_INFO"),
        # always_xy 관례에 맞춰 X=경도, Y=위도.
        "X": r.get("REFINE_WGS84_LOGT"),
        "Y": r.get("REFINE_WGS84_LAT"),
        "CRS": "EPSG:4326",         # ← 이 표기가 소비층의 좌표 변환을 끈다
        "svc": _LABEL,
    }


def _fetch(key: str, page: int) -> dict | None:
    try:
        r = requests.get(_URL, params={"KEY": key, "Type": "json",
                                       "pIndex": page, "pSize": _PAGE}, timeout=60)
        return r.json()
    except Exception as e:                                  # noqa: BLE001
        print(f"  [gg-lic] p{page} 실패: {e}")
        return None


def _scan(key: str, idx: dict[tuple[str, str, str], list[str]],
          targets: list[str]) -> tuple[dict[str, list[dict]], bool]:
    """전량 페이징하며 거점 버킷으로 나눠 담는다. (버킷, 완주여부)

    완주 여부를 함께 돌려주는 이유는 서울 수집기와 같다 — 중간에 끊긴 부분 결과를
    완료로 저장하면 **빠진 줄 모른 채** 산출물이 만들어진다.
    """
    part: dict[str, list[dict]] = {s: [] for s in targets}
    page, total, done = 1, None, False
    while True:
        body = _fetch(key, page)
        blk = (body or {}).get("GENRESTRT")
        if not blk:
            code = ((body or {}).get("RESULT") or {}).get("CODE", "no-body")
            print(f"  [gg-lic] p{page} 중단 ({code}) — 부분 결과는 버린다")
            break
        if total is None:
            total = int(blk[0]["head"][0]["list_total_count"])
            print(f"[gg-lic] 전체 {total:,}행 · {-(-total // _PAGE)}페이지")
        for r in blk[1].get("row") or []:
            p = _place(str(r.get("REFINE_LOTNO_ADDR") or ""))
            if not p:
                continue
            hits = idx.get(p)
            if not hits:
                continue
            row = _norm(r)
            for s in hits:
                part[s].append(row)
        if page * _PAGE >= total:
            done = True
            break
        page += 1
        if page % 50 == 0:
            got = sum(len(v) for v in part.values())
            print(f"  [gg-lic] p{page}/{-(-total // _PAGE)} · 적재 {got:,}행")
        time.sleep(0.05)
    print(f"[gg-lic] 스캔 {total:,}행 · 거점 적재 "
          f"{sum(len(v) for v in part.values()):,}행"
          f"{'' if done else ' · ⚠ 미완주(저장 안 함)'}")
    return part, done


def collect(slugs: list[str], force: bool = False) -> None:
    load_env()
    import os
    key = os.getenv("GG_OPENAPI_KEY")
    if not key:
        raise SystemExit("[gg-lic] GG_OPENAPI_KEY 없음 — data/.env 확인 "
                         "(발급: https://data.gg.go.kr/portal/openapi/insertApikeyPage.do)")
    if requests is None:
        raise SystemExit("[gg-lic] requests 없음 — pip install requests")

    targets = [s for s in slugs
               if (force or latest_bronze(s, "licensing_biz.json") is None)]
    skipped = sorted(set(slugs) - set(targets))
    if skipped:
        print(f"[gg-lic] 이미 있음, 건너뜀: {', '.join(skipped)} (--force 로 재수집)")
    if not targets:
        return

    # (시군,구,동) → [거점...]  한 동이 여러 거점에 걸릴 수 있다.
    idx: dict[tuple[str, str, str], list[str]] = {}
    for s in targets:
        places = _hub_places(s)
        if not places:
            print(f"[gg-lic] {s}: stores_raw 가 없어 대상 동을 못 만든다 — 먼저 "
                  f"`python -m data.collectors.building_vacancy {s} --no-ledger`")
            continue
        for p in places:
            idx.setdefault(p, []).append(s)
    if not idx:
        raise SystemExit("[gg-lic] 대상 동 0 — 수집할 것이 없다")
    print(f"[gg-lic] 대상 거점 {len(targets)} · 동 {len(idx)}개")

    stage = _STAGE / f"{today()}.json"
    part: dict[str, list[dict]] | None = None
    if stage.exists() and not force:
        cached = json.loads(stage.read_text(encoding="utf-8"))
        if all(s in cached for s in targets):
            part = {s: cached[s] for s in targets}
            print(f"[gg-lic] 오늘 자 스테이지 재사용 — 스캔 생략")

    if part is None:
        part, done = _scan(key, idx, targets)
        if not done:
            raise SystemExit("[gg-lic] 미완주 — 저장하지 않는다. 다시 실행할 것")
        _STAGE.mkdir(parents=True, exist_ok=True)
        stage.write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")

    for s in targets:
        rows = part.get(s) or []
        alive = sum(1 for r in rows if r["TRDSTATEGBN"] == "01" and not (r.get("DCBYMD") or "").strip())
        save_json(rows, s, "licensing_biz.json")
        print(f"[gg-lic:{s}] {len(rows):,}행 (영업 {alive:,})")


def main() -> None:
    argv = sys.argv[1:]
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("-")]
    for s in args:
        if get_hub(s) is None:
            raise SystemExit(f"[gg-lic] 미등록 거점 '{s}' — page_hubs 확인")
    slugs = args or [s for s in GYEONGGI_HUBS
                     if latest_bronze(s, "stores_raw.json") is not None]
    if not slugs:
        raise SystemExit("[gg-lic] 대상 거점 없음 — 점포부터 수집할 것")
    collect(slugs, force=force)


if __name__ == "__main__":
    main()
