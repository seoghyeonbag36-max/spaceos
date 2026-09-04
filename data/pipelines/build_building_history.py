"""Gold 건물 영업이력 빌더 — LocalData 인허가 기록 기반.

입력:  data/bronze/{slug}/{latest}/licensing_biz.json
산출:  data/gold/{slug}/building_history.json

## 산출 스키마 v2 (`lot-history/1`) — 2026-08-08 교체

인허가 주소(SITEWHLADDR)가 가리키는 것은 **지번(대지)**이지 동(棟)이 아니다. 한 지번에
여러 동이 올라간 경우 어느 동의 업소였는지는 원천 데이터에 없다.

v1 은 그 지번의 이력을 **그 지번의 모든 동에 통째로 복제**했다. 두 가지가 잘못이다.

  1. 없는 근거를 주장한다 — 가락시장(PNU 1171010700106000000)은 폴리곤 225개가 한 지번에
     있어서, 225개 동이 각각 "이 건물에 344개 업소가 있었다"고 말하게 됐다.
  2. 용량이 폭발한다 — garak 한 거점이 17.9MB, 41거점 합계 66MB. 대부분이 같은 레코드의
     사본이다(garak: 281동에 서로 다른 리스트가 21종뿐).

  복수 동 지번의 비중은 Tier2 만의 문제가 아니다 — 이미 배포된 13거점도
  ikseon 29% · myeongdong 23% · euljiro 17% 다. v1 은 처음부터 틀렸고 가락시장에서
  드러났을 뿐이다.

v2 는 **지번 단위로 한 번만 저장하고 건물은 지번을 가리킨다.**

    {
      "schema": "lot-history/1",
      "lots":      {"<pnu 19자리>": [ {레코드}, ... ]},   # 이력 본체 — 지번당 1회
      "buildings": {"<건물 id>": "<pnu>"}                 # 건물 → 지번 인덱스
    }

서빙(services/building_history.py)은 건물 id 로 지번을 찾아 그 지번의 이력을 돌려주되,
같은 지번을 **몇 개 동이 공유하는지**를 함께 내려보내 화면이 "이 건물"과 "이 지번"을
구분할 수 있게 한다. 정보를 버리지 않으면서 주장만 정확해진다.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from data.collectors.common import BRONZE, GOLD, latest_bronze
from data.config.page_hubs import ACTIVE_HUBS, PageHub, get_hub
from data.pipelines.build_page_master import _addr_pnu, _build_dong_map

_DATE_DIGITS = re.compile(r"\D+")


def _clean_date(value: object) -> str | None:
    digits = _DATE_DIGITS.sub("", str(value or "").strip())
    return digits if len(digits) == 8 else None


def _is_open(row: dict) -> bool:
    state = str(row.get("TRDSTATENM") or "").strip()
    return str(row.get("TRDSTATEGBN") or "").strip() == "01" or "영업" in state


def _load_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _pnu_to_building_ids(master: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for feature in master.get("features") or []:
        props = feature.get("properties") or {}
        pnu = props.get("pnu")
        building_id = props.get("id")
        if pnu and building_id:
            out[pnu].append(building_id)
    return out


def _sigungu_code(stores: list[dict]) -> str:
    hit = Counter(s["lnoCd"][0:5] for s in stores if len(s.get("lnoCd", "")) == 19).most_common(1)
    return hit[0][0] if hit else ""


def build(slug: str, date: str | None = None) -> bool:
    """Build one district's building_history.json."""
    master_path = GOLD / slug / "page_building_master.geojson"
    if date is None:
        licensing_path = latest_bronze(slug, "licensing_biz.json")
        stores_path = latest_bronze(slug, "stores_raw.json")
    else:
        licensing_path = BRONZE / slug / date / "licensing_biz.json"
        stores_path = BRONZE / slug / date / "stores_raw.json"

    master = _load_json(master_path)
    rows = _load_json(licensing_path) if licensing_path is not None else None
    stores = (_load_json(stores_path) if stores_path is not None else None) or []
    if master is None:
        print(f"[building-history:{slug}] page_building_master.geojson missing, skipped")
        return False
    if rows is None:
        print(f"[building-history:{slug}] licensing_biz.json missing, skipped")
        return False

    dong_code = {v: k for k, v in _build_dong_map(stores).items()}
    sigungu = _sigungu_code(stores)
    pnu_to_ids = _pnu_to_building_ids(master)

    lots: dict[str, list[dict]] = defaultdict(list)
    matched = 0
    for row in rows:
        start_date = _clean_date(row.get("APVPERMYMD"))
        if not start_date:
            continue
        pnu = _addr_pnu(str(row.get("SITEWHLADDR") or ""), dong_code, sigungu)
        if pnu not in pnu_to_ids:
            continue

        end_date = None if _is_open(row) else _clean_date(row.get("DCBYMD"))
        # 레코드는 **지번에 한 번만** 붙인다. 동 배분은 원천에 근거가 없다(모듈 상단 참조).
        lots[pnu].append({
            "start_date": start_date,
            "end_date": end_date,
            "industry_type": str(row.get("UPTAENM") or "").strip(),
            "business_name": str(row.get("BPLCNM") or "").strip(),
            "source": "localdata",
            "closure_reason_summary": None,
        })
        matched += 1

    # 이력이 있는 지번에 속한 건물만 인덱스에 넣는다 — 빈 지번을 가리키는 건물은 두지 않는다.
    buildings = {bid: pnu for pnu in sorted(lots) for bid in sorted(pnu_to_ids[pnu])}
    out = {
        "schema": "lot-history/1",
        "lots": {pnu: sorted(v, key=lambda x: (x["start_date"], x["business_name"]))
                 for pnu, v in sorted(lots.items())},
        "buildings": buildings,
    }
    dst = GOLD / slug / "building_history.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    # 들여쓰기 없이 쓴다 — 이 파일은 사람이 읽는 리포트가 아니라 **배포 번들에 실려
    # 런타임에 읽히는 산출물**이다(.vercelignore 가 포함시킨다). page_building_master
    # .geojson 과 같은 규약이다. 54거점 합계 실측 40MB → 27MB.
    dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    shared = sum(1 for pnu in lots if len(pnu_to_ids[pnu]) > 1)
    print(f"[gold:{slug}] building_history.json: 지번 {len(lots)}개(복수동 {shared}) · "
          f"건물 {len(buildings)}개 · 인허가 {matched}건")
    return True


def run(hub: PageHub) -> bool:
    return build(hub.slug)


def main() -> None:
    import sys

    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(ACTIVE_HUBS)
    ok = 0
    for slug in slugs:
        if get_hub(slug) is None:
            # 이름을 대고 불렀는데 못 찾았다 = 오타이거나 미등록이다. 건너뛰고 exit 0 으로
            # 끝내면 부르는 쪽(hub-chain·loop-engine)이 산출된 줄 안다 — 2026-08-30 hwajeong.
            raise SystemExit(f"[building-history] 미등록 거점 '{slug}' — "
                             "page_hubs 의 HUBS/GYEONGGI_HUBS 확인")
        ok += run(get_hub(slug))
    print(f"[building-history] done: {ok}/{len(slugs)} districts")


if __name__ == "__main__":
    main()
