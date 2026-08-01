"""[Page] 건물 속성 사이드카 — bronze 대장·층별개요·상가정보에서 **API 콜 없이** 추출.

2026-08-01. 앵커 모집단 정렬(`docs/finding-anchor-population.md`)에 필요한 건물 속성이
지금은 bronze 원본에만 있어 파이프라인이 쓸 수 없다. 지번(pnu) 단위로 뽑아
silver/{거점}/building_attrs.json 에 캐시한다.

  · R-ONE 모집단 판정용 — 일반/집합, 지상층수, 연면적, 표제부 주용도
  · 층 단위 매칭용     — 층별개요의 지상 상업층 번호, 상가정보 점포의 층(flrNo),
                         인허가 영업 업소의 층(주소 문자열, 영업 중의 86.3%에 있다)
  · 면적 기준 대조용   — 지상 상업층 면적(일반) / 상업 전유면적(집합)

수집기가 소유한 gold/building_vacancy.json 을 건드리지 않는 사이드카라 프론트·백엔드
산출물에 영향이 없다. 소비처: pipelines/calibrate_vacancy · pipelines/recalc_floor_ouln ·
analyze_anchor_population.

⚠ bronze 의 bldg_ledger_raw.json 은 거점당 최대 85MB 인데 이 환경은 커밋 한도가 거의
찬 상태(페이지파일 여유 ~0.1GB)라 json.load 는 물론 **지번 블록 하나를 통째로 문자열로
모으는 것도** MemoryError 가 난다(전유 8,000행 건물이 있다). save_json 이 indent=2 로
쓰는 것을 이용해 **행(row) 객체 하나씩** 파싱해 즉시 집계로 접는다.

실행: python -m data.pipelines.build_building_attrs [거점 ...]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from data.collectors.building_vacancy import NON_CAPACITY_PURPS
from data.collectors.common import BRONZE, SILVER, load_latest
from data.config.page_hubs import HUBS

# R-ONE 중대형/소규모 표본이 되는 '상가건물'의 표제부 주용도. 업무시설·숙박시설은
# 1층에 점포가 있어도 상가 표본이 아니다(13거점 B모집단에 업무 509동·숙박 332동).
SHOP_PURPS = ("근린생활시설", "판매시설", "위락시설", "문화및집회시설")

_PNU = re.compile(r'^  "([^"]+)": [{[]$')
_FIELD = re.compile(r'^    "([A-Za-z_]+)": (.+?),?$')


def stream_rows(path: Path, item_indent: int):
    """indent=2 원본을 (지번, 리스트명, 행 dict) 로 흘려 준다.

    행 객체 하나씩만 메모리에 올린다. 리스트명은 대장(`title`/`expos`)에서만 나오고,
    층별개요처럼 지번 값이 곧 리스트인 파일에서는 None 이다.
    항목 종료 뒤 `(지번, 리스트명, None)` 을 한 번 더 흘려 지번 경계를 알린다.
    """
    open_item = " " * item_indent + "{"
    close_item = " " * item_indent + "}"
    pnu = lst = None
    item: list[str] | None = None
    with path.open(encoding="utf-8") as f:
        for line in f:
            s = line.rstrip("\n")
            if item is not None:
                if s.startswith(close_item):
                    yield pnu, lst, json.loads("".join(item) + "}")
                    item = None
                else:
                    item.append(line)
                continue
            if s.startswith(open_item):
                item = ["{"]
                continue
            m = _PNU.match(s)
            if m:
                if pnu is not None:
                    yield pnu, None, None
                pnu, lst = m.group(1), None
                continue
            m = _FIELD.match(s)
            if m and m.group(2) in ("[", "{"):
                lst = m.group(1)
            elif m and m.group(2).endswith("],"):
                lst = None                      # 빈 리스트(`"expos": [],`)
    if pnu is not None:
        yield pnu, None, None


def is_commercial(nm: object) -> bool:
    """세부용도명 네거티브 필터 — 전유부·층별개요 공통 (building_vacancy 와 동일 규칙)."""
    return not any(p in str(nm) for p in NON_CAPACITY_PURPS)


def _expos_flr_no(nm: object) -> int | None:
    """전유부 flrNoNm('지상3층'/'3층') → 3, 지하 → None."""
    s = str(nm)
    if "지하" in s:
        return None
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def _new_acc() -> dict:
    """지번 하나를 훑는 동안의 누적 상태 (행을 모아 두지 않는다)."""
    return {"title": None, "units": set(), "com_area": 0.0, "u1f": set(), "n_expos": 0,
            "flr_rows": 0, "com_flrs": set(), "com_area_flr": 0.0}


def fold_ledger(acc: dict, lst: str | None, row: dict) -> None:
    """대장 행 하나를 누적 — title 은 첫 행만, expos 는 상업 전유만 센다."""
    if lst == "title":
        if acc["title"] is None:
            acc["title"] = {"regstr_gb": row.get("regstrGbCdNm"),
                            "grnd_flr": int(row.get("grndFlrCnt") or 0),
                            "tot_area": float(row.get("totArea") or 0),
                            "main_purps": row.get("mainPurpsCdNm"),
                            "bld_nm": (row.get("bldNm") or "").strip()}
        return
    if lst != "expos":
        return
    acc["n_expos"] += 1
    if row.get("exposPubuseGbCdNm") != "전유" or not is_commercial(row.get("mainPurpsCdNm")):
        return
    dong, ho, flr = row.get("dongNm", ""), row.get("hoNm", ""), row.get("flrNoNm", "")
    acc["units"].add((dong, ho, flr))
    acc["com_area"] += float(row.get("area") or 0)
    if _expos_flr_no(flr) == 1:
        acc["u1f"].add((dong, ho))


def fold_flr(acc: dict, row: dict) -> None:
    """층별개요 행 하나를 누적 — 지상 상업층 번호·면적."""
    acc["flr_rows"] += 1
    if str(row.get("flrGbCdNm", "")) not in ("지상", ""):
        return
    if not is_commercial(row.get("mainPurpsCdNm")):
        return
    no = int(row.get("flrNo") or 0)
    if no > 0:
        acc["com_flrs"].add(no)
    acc["com_area_flr"] += float(row.get("area") or 0)


def _ledger_out(acc: dict) -> dict:
    out = dict(acc["title"] or {})
    if acc["n_expos"]:
        out |= {"expos_rows": acc["n_expos"],
                "com_units": len(acc["units"]),
                "com_area": round(acc["com_area"], 1),
                "com_1f_units": len(acc["u1f"])}
    return out


def _flr_out(acc: dict) -> dict:
    return {"flr_rows": acc["flr_rows"],
            "com_flr_nos": sorted(acc["com_flrs"]),
            "com_area_flr": round(acc["com_area_flr"], 1),
            "f1_com": 1 in acc["com_flrs"]}


# 인허가 주소의 층 표기: "지상1층" · "지상1,2층" · "1층9호" · "(신사동,지하1층)"
_LIC_FLR = re.compile(r"(지하|지상)?\s*(\d+)\s*(?:[,~]\s*\d+\s*)*층")


def lic_floors(addr: str) -> tuple[set[int], bool]:
    """인허가 주소 → (지상 층번호 집합, 층 표기 존재 여부). 지하는 버린다.

    영업 중 인허가의 86.3%(13거점 44,493건)에 층이 적혀 있다 — 상가정보 flrNo 공란
    약 30%를 메우는 독립 층 소스다.
    """
    out: set[int] = set()
    found = False
    for m in _LIC_FLR.finditer(addr or ""):
        found = True
        if m.group(1) == "지하":
            continue
        for n in re.findall(r"\d+", m.group(0)):
            if 0 < int(n) < 100:
                out.add(int(n))
    return out, found


def licensed_floors(slug: str) -> dict[str, dict]:
    """거점의 인허가 영업 업소를 좌표 PIP 로 건물에 귀속 → {pnu: {n, floors, unknown}}.

    좌표 자가보정·PIP 는 build_page_master 가 이미 갖고 있다(오프셋 −257m 보정).
    같은 로직을 두 벌 두지 않으려고 **함수 안에서** import 한다 — 모듈 최상단에서
    끌어오면 build_page_master ↔ build_building_attrs 순환 import 가 된다.
    """
    from data.pipelines.build_page_master import _build_dong_map, _licensed_pip

    polys = load_latest(slug, "bldg_polygons.geojson")
    stores = load_latest(slug, "stores_raw.json") or []
    if not polys or not stores:
        return {}
    dong_map = _build_dong_map(stores)
    sig = Counter(s["lnoCd"][0:5] for s in stores if len(s.get("lnoCd", "")) == 19).most_common(1)
    return _licensed_pip(polys["features"], slug, dong_map, sig[0][0] if sig else "")


def store_floors(slug: str) -> tuple[dict[str, list], dict[str, int]]:
    """상가정보 원본 → (지번별 점포 확인 지상층, 지번별 층 미상 점포 수).

    flrNo 는 '1' / 'B1' / '지' / 공란이 섞여 있다. 공란이 약 30% 라 층 단위 점유는
    단일 값이 아니라 상·하한 밴드로만 말할 수 있다(공란·지하는 지상층 판정에서 뺀다).
    """
    ps = sorted((BRONZE / slug).glob("*/stores_raw.json"))
    rows = json.loads(ps[-1].read_text(encoding="utf-8")) if ps else []
    known: dict[str, set] = defaultdict(set)
    unknown: dict[str, int] = defaultdict(int)
    for r in rows:
        pnu = r.get("lnoCd")
        if not pnu:
            continue
        s = str(r.get("flrNo") or "").strip()
        if re.fullmatch(r"\d+", s):
            known[pnu].add(int(s))
        elif not s:
            unknown[pnu] += 1
    return {k: sorted(v) for k, v in known.items()}, dict(unknown)


def run(slug: str) -> int:
    """거점 하나의 building_attrs.json 산출. 반환: 지번 수."""
    acc: dict[str, dict] = {}
    # 날짜별 체크포인트가 여러 벌 있다 — 근거가 더 많은 쪽을 남긴다(빈 레코드가
    # 나중 날짜라는 이유로 덮어쓰지 않도록).
    for p in sorted((BRONZE / slug).glob("*/bldg_ledger_raw.json")):
        cur, st = None, None
        for pnu, lst, row in stream_rows(p, 6):
            if pnu != cur:
                if cur is not None and (a := _ledger_out(st)):
                    if len(a) >= len(acc.get(cur, {})):
                        acc[cur] = {**acc.get(cur, {}), **a}
                cur, st = pnu, _new_acc()
            if row is not None:
                fold_ledger(st, lst, row)
        if cur is not None and (a := _ledger_out(st)) and len(a) >= len(acc.get(cur, {})):
            acc[cur] = {**acc.get(cur, {}), **a}
    for p in sorted((BRONZE / slug).glob("*/bldg_flr_raw.json")):
        cur, st = None, None
        for pnu, _lst, row in stream_rows(p, 4):
            if pnu != cur:
                if cur is not None and st["flr_rows"]:
                    prev = acc.setdefault(cur, {})
                    if st["flr_rows"] >= prev.get("flr_rows", 0):
                        prev.update(_flr_out(st))
                cur, st = pnu, _new_acc()
            if row is not None:
                fold_flr(st, row)
        if cur is not None and st["flr_rows"]:
            prev = acc.setdefault(cur, {})
            if st["flr_rows"] >= prev.get("flr_rows", 0):
                prev.update(_flr_out(st))

    known, unknown = store_floors(slug)
    for pnu, floors in known.items():
        acc.setdefault(pnu, {})["store_flr_nos"] = floors
    for pnu, n in unknown.items():
        acc.setdefault(pnu, {})["store_flr_unknown"] = n
    for pnu, lic in licensed_floors(slug).items():
        a = acc.setdefault(pnu, {})
        a["lic_flr_nos"] = lic["floors"]
        a["lic_n"] = lic["n"]
        a["lic_unknown"] = lic["unknown"]

    for pnu, a in acc.items():
        # 집합건물 판정 — 전유부가 있거나 표제부 등록구분이 '집합'.
        a["is_mall"] = bool(a.get("expos_rows")) or a.get("regstr_gb") == "집합"
        mp = str(a.get("main_purps") or "")
        a["is_shop"] = any(p in mp for p in SHOP_PURPS)
        fl, area = a.get("grnd_flr") or 0, a.get("tot_area") or 0
        a["rone_size"] = ("mid" if (fl >= 3 or area > 330)
                          else "small" if (fl <= 2 and 0 < area <= 330) else None)

    dst = SILVER / slug / "building_attrs.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(acc, ensure_ascii=False), encoding="utf-8")
    mall = sum(1 for a in acc.values() if a["is_mall"])
    shop = sum(1 for a in acc.values() if a["is_shop"])
    print(f"[attrs:{slug}] 지번 {len(acc)} (집합 {mall} · 상가주용도 {shop} · "
          f"층별개요 {sum(1 for a in acc.values() if a.get('com_flr_nos'))} · "
          f"점포층 {len(known)} · 인허가층 {sum(1 for a in acc.values() if a.get('lic_flr_nos'))}) "
          f"→ silver/{slug}/building_attrs.json")
    return len(acc)


def load(slug: str) -> dict[str, dict]:
    """소비처용 로더 — 없으면 빈 dict (호출부가 안내 문구를 낸다)."""
    p = SILVER / slug / "building_attrs.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main() -> None:
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(HUBS)
    done = 0
    for s in slugs:
        if s not in HUBS:
            print(f"[attrs] 미등록 거점 '{s}' — 건너뜀")
            continue
        if not (BRONZE / s).exists():
            continue
        if run(s):
            done += 1
    print(f"[attrs] 완료: {done}거점")


if __name__ == "__main__":
    main()
