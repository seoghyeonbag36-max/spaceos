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
#
# 2026-08-23 확장 — 왜 늘렸나. 분자(상가정보+인허가)가 못 보는 층이 분모에 그대로 남아
# 공실이 과대추정된다. 54거점 지상 2층↑ 상업층 55,286행을 용도별로 재 보니 **미커버
# 용도가 분모의 69.7%**, 그 중 점포·인허가가 하나도 확인 안 된 층이 약 21,300개였다.
# 아래 확장은 그 층들을 겨냥한다(용도별 확인율은 docs/feature-page.md 참조).
#
# 서비스 ID 는 추측하지 않았다 — `openapi.seoul.go.kr` 에 LOCALDATA_{CCGGSS} 를 전수로
# 찔러(01~12 대분류, 없으면 ERROR-500) 살아 있는 161종을 뽑고, 각 응답의 업소명 표본으로
# 업종을 특정했다. 괄호 안 숫자는 그때 확인한 서울 전체 행수다.
SERVICES: dict[str, str] = {
    # ── 기존 5종 (식품접객·숙박) ──────────────────────────────────────────
    "일반음식점": "LOCALDATA_072404",      # 536,645
    "휴게음식점": "LOCALDATA_072405",      # 147,053
    "제과점영업": "LOCALDATA_072218",      #  16,714
    "숙박업": "LOCALDATA_031101",          #     948
    "관광숙박업": "LOCALDATA_031103",      #   7,115

    # ── 의료 — 분모 8,778층(의원·한의원·치과의원), 확인율 49~67% ──────────
    "의원": "LOCALDATA_010102",            #  37,602
    "병원": "LOCALDATA_010101",            #     929
    "부속의료기관": "LOCALDATA_010103",    #     146
    "약국": "LOCALDATA_010106",            #  22,413

    # ── 소매 — 분모 7,877층, 확인율 34~38%. 소매업은 자유업이라 인허가가 없어
    #    담배소매인 지정·즉석판매제조가공업·안전상비의약품 판매자로 에둘러 잡는다.
    "담배소매업": "LOCALDATA_114302",              #  95,402
    "즉석판매제조가공업": "LOCALDATA_072219",      # 155,478
    "안전상비의약품판매": "LOCALDATA_010105",      #  18,013 (편의점)

    # ── 미용·이용·목욕 — 분모 1,794층 ────────────────────────────────────
    "미용업": "LOCALDATA_051801",          #  99,442
    "이용업": "LOCALDATA_051901",          #  15,627
    "목욕장업": "LOCALDATA_114401",        #   3,990
    "안마원": "LOCALDATA_010110",          #     605

    # ── 체육시설 — 분모 1,168층 ──────────────────────────────────────────
    "당구장업": "LOCALDATA_103201",        #  14,034
    "체력단련장업": "LOCALDATA_104201",    #   7,309
    "체육도장업": "LOCALDATA_104101",      #   5,708
    "골프연습장업": "LOCALDATA_103101",    #   3,618
    "무도학원업": "LOCALDATA_103302",      #     414

    # ── 게임·노래 — 분모 480층 ───────────────────────────────────────────
    "노래연습장업": "LOCALDATA_030901",            #  12,801
    "인터넷컴퓨터게임시설제공업": "LOCALDATA_030505",  #  16,854
    "게임제공업": "LOCALDATA_030506",              #  10,206
    "복합유통게임제공업": "LOCALDATA_030504",      #   4,640

    # ── 주점 — 분모 466층 ────────────────────────────────────────────────
    "단란주점": "LOCALDATA_072301",        #  11,615
    "유흥주점": "LOCALDATA_072302",        #   4,989

    # ── 못 채운 것 ───────────────────────────────────────────────────────
    # TODO 학원·교습소(분모 7,167층·확인율 47.6%): **지방행정 인허가에 없다.** 학원은
    #   교육청 소관(학원법)이라 LOCALDATA 계열이 아니다 — 01~12 대분류 전수 스캔에서
    #   나오지 않았다. 서울시 교육청 '학원·교습소 현황' 또는 나이스 공시로 따로 받아야 한다.
    # TODO 탁구장업(분모 121층): 서비스 ID 미확인. 체육시설업 그룹(10_32~10_42)에서
    #   업소명 표본이 비어 특정 못 했다.
    # TODO 대규모점포: 서울 ID 는 LOCALDATA_082501(1,051)로 확인됐으나 **집계에서 제외되는
    #   집합건물**이고 백화점 층 확인율이 이미 98.3% 라 넣을 이유가 없다.
    # TODO 통신판매업(LOCALDATA_082604, 940,503): 온라인 사업자라 신고 주소가 자택·사무실이다.
    #   층 확인에 쓰면 없는 점포를 만든다 — 의도적으로 뺀다.
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
