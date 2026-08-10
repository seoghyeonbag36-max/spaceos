"""[Page·분모 정밀화] 층별개요 기반 capacity 재산출 — poc §1-2 TODO 구현.

2026-07-19 지상검증 잔여 오차(영업→high 9동)의 원인: floor_approx 가
지상층 전체 × 2호를 분모로 잡아, 상층부가 사무실·주거·단일 임차인 건물의
상가 수용량을 과대추정한다.

교정: 건축HUB 층별개요(getBrFlrOulnInfo)로 각 층 용도를 받아
  상업 용도(근린생활·판매·위락·숙박·문화) 층 수 × 2호
만 분모로 삼는다. 대상은 gold/building_vacancy.json 중 capacity_method
== "floor_approx" 행 전부 (~560동, 건물당 1콜 — 쿼터 내).

산출: building_vacancy.json 의 capacity/capacity_method("floor_ouln") 갱신
      + bronze/{SLUG}/{날짜}/bldg_flr_raw.json

실행: python -m data.collectors.floor_capacity <slug ...> [--only-approx]
  거점을 **반드시 명시한다** — 비우면 garosugil 로 폴백한다(경고를 찍는다).
  --only-approx : 이미 floor_ouln 인 건물의 재수집을 끄고 floor_approx 만 받는다.
                  Tier1 거점의 소량 잔여를 회수할 때 쓴다(§run 주석의 46콜/동 참조).

중단됐다면 **--only-approx 로 재개한다.** 150동마다 부분 저장하고 저장된 건물은
capacity_method 가 floor_ouln 으로 바뀌므로, 이 플래그가 곧 "완료분 건너뛰기"가 된다.
플래그 없이 재실행하면 이미 받은 것까지 다시 부른다.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter

from data.collectors.common import GOLD, load_env, save_json
from data.config.page_hubs import HUBS
from data.collectors.building_vacancy import (
    BASE_BLD, NON_CAPACITY_PURPS, STORES_PER_FLOOR, _body, _get_json, _items, _jibun,
    _ts, classify,
)

_SLEEP = 0.05
_MAX_FLR_PAGES = 5      # 100행/페이지 — 500층이면 어떤 건물이든 덮는다


def ground_floors(rows: list[dict]) -> int:
    """층별개요의 '지상' 층 수 — floor_approx 분모(표제부 지상층수)에 대응."""
    return len({(r.get("flrGbCd", ""), r.get("flrNo", "")) for r in rows
                if str(r.get("flrGbCdNm", "")) in ("지상", "")})


def _commercial_floors(rows: list[dict]) -> int:
    """층별개요 행에서 '지상' 상업 용도 층 수를 센다 (지하는 분모 제외 유지).

    2026-07-26 교정: 층별개요의 mainPurpsCdNm 은 전유부와 마찬가지로 **세부용도명**
    ("사무소"/"일반음식점"/"소매점"/"미용원")이라, 표제부용 대분류 상수
    (COMMERCIAL_PURPS)를 positive 필터로 쓰면 거의 걸리지 않는다.
    garosugil 실측: 지상층 201개 중 대분류 매칭 12개(6.0%)뿐 → 559동 중 420동이
    "상업층 0" 으로 떨어졌고, 그 결과 capacity 가 붕괴해 공실률이 0%/50% 두 값으로
    고정됐다(538동 중 427동이 0%). building_vacancy 의 전유부(expos_units)에서
    이미 같은 버그를 잡았던 것과 동일한 원인이다.
    → 전유부와 같은 negative 필터로 통일한다. 매칭률 6.0% → 55.2%.

    mainPurpsCdNm 만 본다(etcPurps 병합 안 함) — expos_units 와 도메인을 맞추기 위해서다.
    etcPurps 까지 이어 붙이면 "소매점 + 부속 사무소" 같은 층이 통째로 탈락한다.
    """
    return len(commercial_floor_nos(rows))


def commercial_floor_nos(rows: list[dict]) -> set[int]:
    """지상 상업층의 **층번호 집합**. 층 단위 매칭(점포 flrNo 대조)의 분모 후보다.

    _commercial_floors 와 같은 필터이며 결과를 개수 대신 번호로 돌려준다. flrNo 가
    비어 있는 행은 뺀다(13거점 지상 상업행 11,812개 중 2개뿐이라 영향이 없다).
    """
    return {int(r.get("flrNo") or 0) for r in rows
            if str(r.get("flrGbCdNm", "")) in ("지상", "")
            and not any(p in str(r.get("mainPurpsCdNm", "")) for p in NON_CAPACITY_PURPS)
            and int(r.get("flrNo") or 0) > 0}


def capacity_floors(com_nos: set[int], store_nos: set[int], grnd_flr: int = 0) -> set[int]:
    """분모 층 집합 = 층별개요 상업층 ∪ **점포가 확인된 지상층**.

    점포가 있는 층은 정의상 상업층인데, 층별개요 용도 필터가 그런 층을 떨어뜨려
    13거점 점포의 22.6%가 분모 밖에 있었다(`docs/finding-anchor-population.md`).
    상가정보 flrNo 에는 실제 층수를 넘는 오기가 섞여 있어 표제부 지상층수(모르면
    상업층 최댓값)까지만 인정한다.
    """
    cap = grnd_flr or max(com_nos, default=0)
    return com_nos | {f for f in store_nos if 0 < f <= cap}


_CHECKPOINT = 150   # 이 동수마다 부분 저장 — building_vacancy 와 같은 주기


def _persist(slug: str, path, rows: list[dict], raw: dict[str, list]) -> None:
    """진행분을 bronze·gold 에 쓴다. 중간에도, 끝에서도 같은 경로로 저장한다.

    2026-08-10: 예전에는 거점 하나가 **다 끝나야** 썼다. dongdaemun 1,782동은 그게
    22분짜리 무저장 구간이라, 그 사이 재부팅으로 1,450콜을 통째로 잃었다(실제로 잃었다).
    쿼터가 하루 10,000 인 자원이라 이 구멍은 감당이 안 된다.

    gold 를 먼저 임시파일에 쓰고 교체한다 — 저장 도중 죽어도 기존 파일이 남는다.
    building_vacancy.json 에는 대장 수집 결과가 들어 있어 깨지면 손해가 크다.
    """
    save_json(raw, slug, "bldg_flr_raw.json")
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run(key: str, slug: str, only_approx: bool = False) -> None:
    path = GOLD / slug / "building_vacancy.json"
    if not path.exists():
        print(f"[flr-cap:{slug}] building_vacancy.json 없음 — 건너뜀")
        return
    rows = json.loads(path.read_text(encoding="utf-8"))
    # floor_ouln 도 대상에 넣는다 — 2026-07-19 수집분은 pageNo 누락으로 층 1개만 받아
    # 산출된 아티팩트라 재수집 대상이다(공실률이 0%/50% 두 값으로 고정돼 있었다).
    #
    # 2026-08-10: 그 재수집이 이제는 대부분 낭비다. pageNo 는 07-26 에 고쳤고 Tier1
    # 거점은 08-01 에 재수집을 끝냈으므로, 남은 floor_approx 를 마저 받으려고 멀쩡한
    # floor_ouln 을 통째로 다시 부르게 된다 — 21거점 실측으로 263동 회수에 12,108콜
    # (동당 46콜)이다. 일일 쿼터가 10,000 인 상황에서 감당할 수 없다.
    # --only-approx 는 그 조항만 끈다. 기본값은 바꾸지 않는다 — 07-19 이전 산출물이
    # 남아 있을 수 있는 거점에서 조용히 낡은 값을 남기는 쪽이 더 나쁘다.
    wanted = ("floor_approx",) if only_approx else ("floor_approx", "floor_ouln")
    targets = [r for r in rows if r.get("capacity_method") in wanted]
    label = "floor_approx 만" if only_approx else "floor_approx + 기존 floor_ouln 재수집"
    print(f"[flr-cap:{slug}] 대상 {len(targets)}동 ({label})")

    raw: dict[str, list] = {}
    updated = failed = skipped = 0
    for i, b in enumerate(targets, 1):
        jibun = _jibun(b.get("lnoCd", ""))
        if jibun is None:
            continue
        # pageNo 를 반드시 넣는다. 빠지면 서버가 numOfRows 요청값을 무시하고 **1행만**
        # 돌려준다(2026-07-26 확인: totalCount=12 인데 numOfRows=1). 2026-07-19 수집분이
        # 건물당 1개 층만 담긴 이유이고, 그 1행이 대개 지하1층이라 '지상 상업층 0' 이
        # 대량 발생했다. pageNo=1 을 넣으면 12행이 정상 반환된다(서버 상한 100행).
        items: list[dict] = []
        page = 1
        while page <= _MAX_FLR_PAGES:
            flr = _get_json(f"{BASE_BLD}/getBrFlrOulnInfo",
                            {"serviceKey": key, "_type": "json", "numOfRows": 100,
                             "pageNo": page, **jibun})
            got = _items(flr)
            items += got
            total = int(_body(flr).get("totalCount") or 0)
            if not got or len(items) >= total:
                break
            page += 1
            time.sleep(_SLEEP)
        if not items:
            failed += 1
            continue
        raw[b["lnoCd"]] = items
        n_com = _commercial_floors(items)
        if not n_com:
            # 상업 층 0 — 예전에는 capacity=2 를 지어냈지만, 그러면 max(2, active) 가
            # capacity 를 active 로 만들어 공실이 정의상 0% 가 된다. 근거 없는 값을
            # 만드느니 기존 floor_approx 를 유지한다(2026-07-26 교정).
            skipped += 1
            continue
        # capacity 에 active 클램프를 **저장하지 않는다**. 클램프를 쓰면 분모가
        # 분자를 따라가 공실률이 0% 로 눌린다(garosugil 538동 중 427동이 이렇게 됐다).
        # 하한 규칙은 집계 시점(calibrate_vacancy._agg / build_page_master)에만 적용한다.
        b["capacity"] = max(n_com * STORES_PER_FLOOR, 1)
        b["capacity_method"] = "floor_ouln"
        occ = min(b["active"] / b["capacity"], 1.0)
        b["occupancy"] = round(occ, 3)
        b["vacancy_bldg"] = round((1 - occ) * 100, 1)
        b["status"] = classify(occ, "floor_ouln")
        updated += 1
        if i % 50 == 0 or i == len(targets):
            print(f"[{_ts()}] [flr-cap:{slug}] {i}/{len(targets)}동 "
                  f"(갱신 {updated}, 상업층0 유지 {skipped}, 응답없음 {failed})")
        if updated and i % _CHECKPOINT == 0:
            _persist(slug, path, rows, raw)
            print(f"[flr-cap:{slug}] 체크포인트 저장 — {i}/{len(targets)}동까지")
        time.sleep(_SLEEP)

    _persist(slug, path, rows, raw)
    cm = Counter(r.get("capacity_method") for r in rows)
    print(f"[flr-cap:{slug}] building_vacancy.json 갱신 — capacity_method: {dict(cm)}")


def main() -> None:
    load_env()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key:
        print("[flr-cap] DATA_GO_KR_SERVICE_KEY 미설정 — 건너뜀")
        return
    argv = sys.argv[1:]
    only_approx = "--only-approx" in argv
    slugs = [a for a in argv if not a.startswith("-")]
    if not slugs:
        # 조용히 garosugil 로 떨어지면 안 된다 — 다른 거점을 받으려고 실행한 사람이
        # 로그를 안 보면 하루치 쿼터를 엉뚱한 데 쓴 걸 모른다(2026-08-10).
        slugs = ["garosugil"]
        print("[flr-cap] ⚠ 거점 미지정 — garosugil 로 폴백합니다. "
              "의도한 게 아니면 지금 중단하고 거점을 명시하십시오.")
    for s in slugs:
        if s not in HUBS:
            print(f"[flr-cap] 미등록 거점 '{s}' — 건너뜀")
            continue
        run(key, s, only_approx)


if __name__ == "__main__":
    main()
