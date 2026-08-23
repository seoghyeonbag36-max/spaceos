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

쿼터: 27종 약 1,277콜(40분). **업종 하나가 끝날 때마다 중간 저장**하므로 중단돼도
오늘 자 스테이지가 있는 업종은 다시 부르지 않는다(재개는 같은 명령을 다시 실행).

산출: bronze/{slug}/{날짜}/licensing_biz.json  (중간: bronze/_licensing_stage/{업종}.json)
실행: python -m data.collectors.seoul_licensing [slug ...] [--force]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import urllib.request
from collections import defaultdict

from data.collectors.common import (BRONZE, latest_bronze, load_env, load_latest,
                                    save_json, today)
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
# SITEAREA(영업장 면적, ㎡) — 식품접객·공중위생 계열에만 있고 담배소매·의원에는 없다(None).
# Posting 의 avg_store_pyeong(A) 은 지금 KOSIS 임차료 역산 대리값인데, 이 필드는
# **서울 전수·업태별 실측**이라 그 유일한 가정을 대조할 수 있다(docs/feature-page.md).
_KEEP = ("MGTNO", "BPLCNM", "UPTAENM", "TRDSTATEGBN", "TRDSTATENM",
         "DTLSTATEGBN", "DTLSTATENM", "DCBYMD", "APVPERMYMD",
         "SITEWHLADDR", "RDNWHLADDR", "SITEAREA", "X", "Y")

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


# 업종별 중간 저장 위치 — 27종 × 약 1,277콜(40분)을 무저장으로 돌리면 중단 한 번에
# 전부 잃는다(2026-08-23 실측: 일반음식점 537콜을 스캔한 뒤 세션 종료로 통째로 소실).
# floor_capacity 가 150동마다 저장하는 것과 같은 이유다. 업종 하나가 끝날 때마다
# {거점: 행} 을 여기 떨어뜨리고, 재실행하면 **오늘 자 스테이지가 있는 업종은 건너뛴다.**
# 전 업종이 모이면 거점별 bronze 로 병합하고 스테이지는 지운다.
_STAGE = BRONZE / "_licensing_stage"
NL = chr(10)


def _scan(key: str, sid: str, label: str, idx: dict,
          targets: list[str]) -> tuple[dict[str, list[dict]], bool]:
    """업종 하나를 전역 페이징하며 거점 버킷으로 나눠 담는다.

    반환의 두 번째 값은 **완주 여부**다. 네트워크가 끊기면 `_get` 이 None 을 돌려
    루프가 중간에 깨지는데, 그 부분 결과를 완료로 저장하면 그 업종은 재개 때
    다시 부르지 않는다 — 빠진 줄 모른 채 산출물이 만들어진다. 완주한 것만 남긴다.
    """
    part: dict[str, list[dict]] = {s: [] for s in targets}
    start, total = 1, None
    done = False
    while True:
        body = _get(key, sid, start, start + _PAGE - 1)
        blk = (body or {}).get(sid)
        if not blk:
            code = ((body or {}).get("RESULT") or {}).get("CODE", "no-body")
            print(f"  [{sid}] 중단 ({code}) — 부분 결과는 버린다")
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
                part[s].append(row)
        if start + _PAGE > total:
            done = True
            break
        start += _PAGE
        time.sleep(0.05)
    print(f"[licensing] {label}({sid}): 전체 {total}행 스캔 · "
          f"거점 적재 {sum(len(v) for v in part.values())}행"
          f"{'' if done else ' · ⚠ 미완주(저장 안 함)'}")
    return part, done


def _stage_load(label: str, targets: list[str]) -> dict[str, list[dict]] | None:
    """오늘 자 스테이지가 대상 거점을 전부 담고 있으면 그것을 쓴다(재개)."""
    p = _STAGE / f"{label}.json"
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if blob.get("date") != today() or not set(blob.get("rows", {})) >= set(targets):
        return None
    return blob["rows"]


def _stage_save(label: str, part: dict[str, list[dict]]) -> None:
    _STAGE.mkdir(parents=True, exist_ok=True)
    (_STAGE / f"{label}.json").write_text(
        json.dumps({"date": today(), "rows": part}, ensure_ascii=False), encoding="utf-8")


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

    missing: list[str] = []
    for i, (label, sid) in enumerate(SERVICES.items(), 1):
        part = _stage_load(label, targets)
        if part is None:
            part, done = _scan(key, sid, label, idx, targets)
            if done:
                _stage_save(label, part)
            else:
                missing.append(label)
            del part
        else:
            print(f"[licensing] {label}: 오늘 자 스테이지 재사용 "
                  f"({sum(len(v) for v in part.values())}행) — 콜 없음")
            del part
        print(f"[licensing] 진행 {i}/{len(SERVICES)}종")

    if missing:
        print(f"[licensing] ⚠ 미완주 {len(missing)}종 — bronze 병합을 하지 않는다: "
              f"{', '.join(missing)}" + NL
              + f"    스테이지 {len(list(_STAGE.glob('*.json')))}종은 남아 있다. "
              f"네트워크 복구 후 같은 명령을 다시 실행하면 남은 업종만 부른다.")
        return
    _merge_to_bronze(targets)


def _merge_to_bronze(targets: list[str]) -> None:
    """스테이지 27종 → 거점별 bronze. **업종 하나씩만** 메모리에 올린다.

    27종을 한 dict 에 쌓으면 3GB 를 넘긴다(일반음식점 한 종의 거점 적재가 570,392행,
    스테이지 282MB). 업종별로 읽어 거점 jsonl 에 흘려 두고, 마지막에 거점 단위로만
    다시 모은다 — 최대 점유가 '한 업종' 또는 '한 거점' 을 넘지 않는다.
    """
    merge = _STAGE / "_merge"
    shutil.rmtree(merge, ignore_errors=True)
    merge.mkdir(parents=True, exist_ok=True)
    for label in SERVICES:
        rows = (json.loads((_STAGE / f"{label}.json").read_text(encoding="utf-8"))
                .get("rows") or {})
        for s in targets:
            part = rows.get(s) or []
            if not part:
                continue
            with (merge / f"{s}.jsonl").open("a", encoding="utf-8") as f:
                f.writelines(json.dumps(r, ensure_ascii=False) + NL for r in part)
        del rows
    for s in targets:
        p = merge / f"{s}.jsonl"
        rows = [json.loads(ln) for ln in p.open(encoding="utf-8")] if p.exists() else []
        save_json(rows, s, "licensing_biz.json")
        print(f"[licensing:{s}] 거점 인허가 {len(rows)}행")
    # 거점 bronze 가 다 쓰인 뒤에만 스테이지를 버린다 — 중간에 죽으면 재개 지점이 남아야 한다.
    shutil.rmtree(_STAGE, ignore_errors=True)


if __name__ == "__main__":
    load_env()
    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("-")]
    collect(args or list(HUBS), force="--force" in argv)
