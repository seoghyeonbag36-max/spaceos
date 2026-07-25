"""[Page·분자 보강] 서울 인허가 수집기 — 영업 중 업소로 상가정보 누락 크로스체크.

2026-07-19 지상검증에서 상가정보(분자)가 실제 영업 점포를 누락해 공실이
과대추정됨을 확인(예: 실제 다점포 건물이 활성 1건으로 잡혀 high 오판).
서울 열린데이터광장의 지방행정 인허가 서비스(LOCALDATA_*)로 업종별 인허가
현황을 받아 건물 단위 분자의 하한(licensed)을 만든다. build_page_master 의
_licensed_pip 이 좌표 자가보정 후 폴리곤 PIP 로 건물에 귀속시킨다.

※ 경위: localdata.go.kr 는 2026-04-16 폐쇄, data.go.kr 이관 API(일반음식점·
  휴게음식점·숙박업·제과점영업·관광숙박업·대규모점포 활용신청 완료)는 상세
  스펙이 포털 로그인(Swagger) 뒤라 자동화 확인 불가. 서울 범위이므로 동일
  원천의 서울 열린데이터광장 서비스로 대체(전국 확장 시 data.go.kr 이관 TODO).

다거점: 경로 필터 미지원 → 서울 전역을 **한 번만** 페이징하며 각 행을 (구,동)으로
거점 버킷에 나눠 담는다(12거점 재스캔 방지). 거점의 (구,동) 집합은 이미 수집된
각 거점 stores_raw.json 의 lnoAdr 에서 파생한다. 한 동이 여러 거점에 걸쳐도
무해하다 — build_page_master 가 거점 폴리곤 PIP 로 다시 거른다.
쿼터: 총 ~700콜(일반음식점 535k 행이 대부분). SEOUL_OPENAPI_KEY(관대).

산출: bronze/{slug}/{날짜}/licensing_biz.json
실행: python -m data.collectors.seoul_licensing [slug ...] [--force]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict

from data.collectors.common import latest_bronze, load_env, load_latest, save_json
from data.config.page_hubs import HUBS

# 2026-07-19 프로브 확정 서비스 ID (서울 열린데이터광장)
SERVICES: dict[str, str] = {
    "일반음식점": "LOCALDATA_072404",
    "휴게음식점": "LOCALDATA_072405",
    "제과점영업": "LOCALDATA_072218",
    "숙박업": "LOCALDATA_031101",
    "관광숙박업": "LOCALDATA_031103",
    # TODO 대규모점포: 서울 서비스 ID 미확인(ERROR-500) — data.go.kr 이관 API 로 보강
}

_PAGE = 1000
_KEEP = ("MGTNO", "BPLCNM", "UPTAENM", "TRDSTATEGBN", "TRDSTATENM",
         "DTLSTATEGBN", "DTLSTATENM", "DCBYMD", "APVPERMYMD",
         "SITEWHLADDR", "RDNWHLADDR", "X", "Y")

# 지번주소에서 (구, 법정동) 추출 — 숫자 포함 동명(을지로3가) 허용
_GU_DONG = re.compile(r"([가-힣]+구)\s+([가-힣]+[0-9]*(?:동|가|리))")


def _get(key: str, sid: str, start: int, end: int) -> dict | None:
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{sid}/{start}/{end}/"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  [{sid}] {start}~{end} 실패 — {exc}")
        return None


def _hub_pairs(slug: str) -> set[tuple[str, str]]:
    """거점 stores_raw 의 lnoAdr 에서 (구, 동) 쌍 집합 파생."""
    pairs: set[tuple[str, str]] = set()
    for s in load_latest(slug, "stores_raw.json") or []:
        m = _GU_DONG.search(s.get("lnoAdr", "") or "")
        if m:
            pairs.add((m.group(1), m.group(2)))
    return pairs


def collect(slugs: list[str], force: bool = False) -> None:
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key:
        print("[licensing] SEOUL_OPENAPI_KEY 미설정 — 건너뜀")
        return

    targets = [s for s in slugs if s in HUBS
               and (force or latest_bronze(s, "licensing_biz.json") is None)]
    skipped = [s for s in slugs if s in HUBS and s not in targets]
    if skipped:
        print(f"[licensing] 이미 존재 — 건너뜀: {', '.join(skipped)} (--force 로 재수집)")
    if not targets:
        print("[licensing] 수집 대상 거점 없음")
        return

    # (구,동) → [거점 slug] 역인덱스: 행당 O(1) 버킷 조회
    idx: dict[tuple[str, str], list[str]] = defaultdict(list)
    empty_filter = []
    for s in targets:
        pairs = _hub_pairs(s)
        if not pairs:
            empty_filter.append(s)
            continue
        for pair in pairs:
            idx[pair].append(s)
    if empty_filter:
        print(f"[licensing] ⚠ stores_raw 없음/동 파생 실패 — 건너뜀: {', '.join(empty_filter)}")
    print(f"[licensing] 대상 {len(targets)}거점 · (구,동) 쌍 {len(idx)}종 · 전역 스캔 시작")

    buckets: dict[str, list[dict]] = {s: [] for s in targets}
    for label, sid in SERVICES.items():
        start, total = 1, None
        while True:
            body = _get(key, sid, start, start + _PAGE - 1)
            blk = (body or {}).get(sid)
            if not blk:
                code = ((body or {}).get("RESULT") or {}).get("CODE", "no-body")
                print(f"  [{sid}] 중단 ({code})")
                break
            total = int(blk.get("list_total_count") or 0)
            for r in blk.get("row") or []:
                m = _GU_DONG.search(str(r.get("SITEWHLADDR", "")))
                if not m:
                    continue
                hits = idx.get((m.group(1), m.group(2)))
                if not hits:
                    continue
                row = {k: r.get(k) for k in _KEEP}
                row["svc"] = label
                for s in hits:
                    buckets[s].append(row)
            if start + _PAGE > total:
                break
            start += _PAGE
            time.sleep(0.05)
        print(f"[licensing] {label}({sid}): 전체 {total}행 스캔")

    for s in targets:
        save_json(buckets[s], s, "licensing_biz.json")
        print(f"[licensing:{s}] 거점 인허가 {len(buckets[s])}행")


if __name__ == "__main__":
    load_env()
    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("-")]
    collect(args or list(HUBS), force="--force" in argv)
