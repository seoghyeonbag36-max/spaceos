"""Build Gold building business history from LocalData licensing records.

Input:
  data/bronze/{slug}/{latest}/licensing_biz.json

Output:
  data/gold/{slug}/building_history.json
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from data.collectors.common import BRONZE, GOLD, latest_bronze
from data.config.page_hubs import HUBS, PageHub
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

    histories: dict[str, list[dict]] = defaultdict(list)
    matched = 0
    for row in rows:
        start_date = _clean_date(row.get("APVPERMYMD"))
        if not start_date:
            continue
        pnu = _addr_pnu(str(row.get("SITEWHLADDR") or ""), dong_code, sigungu)
        if pnu not in pnu_to_ids:
            continue

        end_date = None if _is_open(row) else _clean_date(row.get("DCBYMD"))
        item = {
            "start_date": start_date,
            "end_date": end_date,
            "industry_type": str(row.get("UPTAENM") or "").strip(),
            "business_name": str(row.get("BPLCNM") or "").strip(),
            "source": "localdata",
            "closure_reason_summary": None,
        }
        for building_id in pnu_to_ids[pnu]:
            histories[building_id].append(item)
        matched += 1

    out = {k: sorted(v, key=lambda x: (x["start_date"], x["business_name"]))
           for k, v in sorted(histories.items())}
    dst = GOLD / slug / "building_history.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gold:{slug}] building_history.json: {len(out)} buildings, {matched} licensing records")
    return True


def run(hub: PageHub) -> bool:
    return build(hub.slug)


def main() -> None:
    import sys

    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(HUBS)
    ok = 0
    for slug in slugs:
        if slug not in HUBS:
            print(f"[building-history] unknown slug '{slug}', skipped")
            continue
        ok += run(HUBS[slug])
    print(f"[building-history] done: {ok}/{len(slugs)} districts")


if __name__ == "__main__":
    main()
