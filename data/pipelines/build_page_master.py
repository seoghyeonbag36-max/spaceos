"""Gold 빌더 — page_building_master.geojson (Page 공실 레이어의 단일 소스).

결합: V-World 건물 폴리곤(bronze bldg_polygons.geojson, key=pnu 19자리)
  ⊕ 건물 공실 지표(gold building_vacancy.json, key=lnoCd 19자리 — PNU 동형)
  ⊕ 점포 원본(bronze stores_raw.json) — PIP 폴백의 입력

규칙:
  - 폴리곤 pnu == 공실 lnoCd 매칭. 같은 지번 여러 공실행은 active·capacity 합산 후 재분류.
  - **PIP 폴백(poc §2-1 3단계, 2026-07-19 지상검증 후 구현)**: 어느 폴리곤과도
    지번 매칭이 안 된 점포(그룹 지번 불일치·bdMgtSn 누락)를 좌표 point-in-polygon
    으로 건물에 귀속시켜 분자(active)에 합산한다. 지상검증에서 실제 만실 건물이
    조인 실패로 empty 오판되던 주범(정확도 32.1%)을 고치는 경로.
  - 미매칭 폴리곤 중 '상업용도'(용도코드 03/04/05/07/14/15/16)는 PIP 점포도 0
    일 때만 status "empty"(공실 의심). 주거·기타 용도는 지도에서 제외.
  - status 는 프론트(MapShell VacStatus) 규격 4종만 출력: full/partial/high/empty.
    unknown(대장 미확인)·n_a(비상업)는 제외하고 카운트만 보고.

산출: gold/{SLUG}/page_building_master.geojson
  properties: id/name/status/capacity/active/industry/vacancy_rate (+floors/height)
  → apps/backend/app/services/building_vacancy.py 가 이 파일을 서빙.

다거점: config/page_hubs.py HUBS 를 순회한다. 동명맵(_DONG)은 거점 상수가 아니라
점포 주소(lnoAdr)에서 동적으로 구성하고, gold building_vacancy.json(대장 산출물)이
없는 거점은 V-World 폴리곤 지상층수로 capacity 를 근사한다(Tier 2 확장 경로).

실행: python -m data.pipelines.build_page_master [slug ...]
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import re
from collections import Counter, defaultdict

from data.collectors.building_vacancy import (
    NON_STOREFRONT_LCLS, STORES_PER_FLOOR as _STORES_PER_FLOOR)
from data.collectors.common import GOLD, load_latest
from data.config.page_hubs import HUBS, PageHub
from data.pipelines.build_building_attrs import lic_floors
from data.pipelines.build_building_attrs import load as load_attrs

# 건물통합 용도코드(대분류 5자리) 중 상가 capacity 를 가질 수 있는 상업 계열
_COMMERCIAL_PRPS = ("03", "04", "05", "07", "14", "15", "16")
# 층당 호 수 근사는 수집기 상수를 **직접 import** 한다. 값을 여기 복제해 두면 한쪽만
# 고쳤을 때 지도(pip_only·polygon_only)와 대장 산출물의 분모 정의가 조용히 갈라진다.

# 지번주소(lnoAdr/SITEWHLADDR) → 법정동 토큰 (예: "신사동", "을지로3가"). 숫자 포함 동명 허용.
# (?![가-힣]): 뒤에 한글이 더 붙는 토큰은 배제 — "성동구"의 '성동'을 동으로 오파싱하지 않게 한다
# (성수동2가 를 놓치던 버그). 동명은 지번주소에서 뒤에 공백/숫자/끝이 오는 완결 토큰이다.
_DONG_TOKEN = re.compile(r"([가-힣]+[0-9]*(?:동|가|리))(?![가-힣])")


def _build_dong_map(stores: list[dict]) -> dict[str, str]:
    """stores_raw 에서 {법정동코드5: 동명} 사전 구성 (lnoCd 뒤5 + lnoAdr).

    거점 상수였던 _DONG 을 대체 — 어느 거점에서든 점포 주소로 라벨 동명을 얻는다.
    """
    m: dict[str, str] = {}
    for s in stores:
        lno = s.get("lnoCd", "")
        if len(lno) != 19:
            continue
        code = lno[5:10]
        if code in m:
            continue
        hit = _DONG_TOKEN.search(s.get("lnoAdr", "") or "")
        if hit:
            m[code] = hit.group(1)
    return m


def _label(pnu: str, name: str, dong_map: dict[str, str] | None = None) -> str:
    if name:
        return name
    dong = (dong_map or {}).get(pnu[5:10], pnu[5:10])
    bon, bu = int(pnu[11:15]), int(pnu[15:19])
    # 부번 0000 = 부번 없음 → "신사동 547-0" 이 아니라 "신사동 547" (지번 표기 규칙)
    return f"{dong} {bon}-{bu}" if bu else f"{dong} {bon}"


def _classify(occ: float | None) -> str | None:
    if occ is None:
        return None
    if occ >= 0.9:
        return "full"
    if occ >= 0.5:
        return "partial"
    if occ > 0:
        return "high"
    return "empty"


def _rings(geom: dict) -> list[list[list[float]]]:
    """Polygon/MultiPolygon 외곽 링 목록."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def _pip(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """ray casting — ring 은 [lon, lat] 목록."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _split_stores(stores: list[dict], displayed_pnu: set[str]) -> tuple[dict[str, int], list[dict]]:
    """점포를 (직접 매칭 신선 카운트, PIP 후보)로 나눈다 (이중 계상 방지).

    수집기(collectors/building_vacancy.py)와 동일하게 bdMgtSn 그룹의 최빈 lnoCd
    를 대표 지번으로 삼는다.
      - 대표 지번이 표시 폴리곤과 매칭된 그룹 → fresh[지번] 에 점포 수 합산
        (gold building_vacancy 의 active 는 구반경 수집분이라 이 값으로 갱신).
      - 매칭 안 된 그룹 + bdMgtSn 누락 점포 → PIP 후보.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    candidates: list[dict] = []
    for s in stores:
        k = s.get("bldMngNo") or ""
        if k:
            groups[k].append(s)
        else:
            candidates.append(s)

    fresh: dict[str, int] = defaultdict(int)
    for ss in groups.values():
        lno = Counter(s.get("lnoCd", "") for s in ss if s.get("lnoCd")).most_common(1)
        rep = lno[0][0] if lno else ""
        if rep in displayed_pnu:
            fresh[rep] += len(ss)
        else:
            candidates.extend(ss)
    return fresh, candidates


def _pip_fallback(stores: list[dict], polys: list[dict]) -> dict[str, int]:
    """미계상 점포를 좌표로 폴리곤에 귀속 → {pnu: 추가 점포 수}.

    bbox 프리필터로 폴리곤 전수 스캔 비용을 줄인다.
    """
    # 폴리곤 인덱스: (bbox, rings, pnu)
    index = []
    for f in polys:
        rings = _rings(f["geometry"])
        if not rings:
            continue
        xs = [c[0] for r in rings for c in r]
        ys = [c[1] for r in rings for c in r]
        index.append((min(xs), min(ys), max(xs), max(ys), rings, f["properties"].get("pnu", "")))

    extra: dict[str, int] = defaultdict(int)
    orphan = pip_hit = 0
    for s in stores:
        try:
            lon, lat = float(s["lon"]), float(s["lat"])
        except (KeyError, TypeError, ValueError):
            continue
        orphan += 1
        for x0, y0, x1, y1, rings, pnu in index:
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            if any(_pip(lon, lat, r) for r in rings):
                extra[pnu] += 1
                pip_hit += 1
                break
    print(f"[page-master] PIP 폴백: 미매칭 점포 {orphan}건 중 {pip_hit}건을 "
          f"{len(extra)}동에 귀속 ({round(pip_hit / orphan * 100, 1) if orphan else 0}%)")
    return extra


_ADDR_JIBUN_RE = re.compile(r"([가-힣]+[0-9]*(?:동|가|리))(?![가-힣])\s+(\d+)(?:-(\d+))?")


def _addr_pnu(addr: str, dong_code: dict[str, str], sigungu: str) -> str | None:
    """지번주소 → PNU 19자리 (자가 보정 기준점 산출용 — 대지 가정).

    dong_code: {동명 → 법정동코드5}, sigungu: 시군구코드5 — 둘 다 점포에서 파생.
    """
    m = _ADDR_JIBUN_RE.search(addr)
    if not m:
        return None
    dong = dong_code.get(m.group(1))
    if not dong:
        return None
    return f"{sigungu}{dong}1{int(m.group(2)):04d}{int(m.group(3) or 0):04d}"


def _licensed_pip(polys: list[dict], slug: str, dong_map: dict[str, str],
                  sigungu: str) -> dict[str, dict]:
    """인허가(bronze licensing_biz.json) '영업 중' 업소를 좌표 PIP 로 건물 귀속.

    상가정보가 누락한 영업 업소를 잡는 분자 하한(licensed) — 2026-07-19 지상검증의
    high 오판(실제 영업 건물의 활성 과소집계) 보정.

    좌표계: X/Y 는 중부원점 TM 계열이나 표준 EPSG(2097/5174) 어느 것과도 정확히
    일치하지 않는다(2026-07-19 실측: 2097 기준 동서 -257m 상수 오프셋 = 경도
    10.405초). → **자가 보정**: 지번주소가 폴리곤과 매칭되는 행으로 중위 오프셋을
    추정해 전체 좌표에 적용한다 (825점 검증: 보정 후 중위 잔차 2.7m, <20m 100%).
    """
    rows = load_latest(slug, "licensing_biz.json") or []
    alive = []
    # 같은 점포가 업종 수만큼 세어지는 것을 막는다(2026-08-23, 5종→27종 확장).
    # 편의점 한 곳이 담배소매업 + 안전상비의약품판매 + 휴게음식점으로 3장을 갖는다 —
    # 3거점 실측 중복률 0.6%(5종) → **3.8%**(27종). 층은 합집합이라 중복이 무해하지만
    # `unknown`(층 미상)은 상한 산정에서 빈 층을 채우므로 그대로 두면 공실이 과소추정된다.
    # 키는 (업소명, 지번주소) — 중복 행끼리 주소가 같아 층 표기도 같으므로 정보 손실이 없다.
    seen: set[tuple[str, str]] = set()
    dup = 0
    for r in rows:
        if str(r.get("DCBYMD") or "").strip():
            continue
        if str(r.get("TRDSTATEGBN", "")) != "01" and "영업" not in str(r.get("TRDSTATENM", "")):
            continue
        try:
            x, y = float(str(r.get("X", "")).strip()), float(str(r.get("Y", "")).strip())
        except ValueError:
            continue
        addr = str(r.get("SITEWHLADDR", ""))
        key = (re.sub(r"\s+", "", str(r.get("BPLCNM") or "")), re.sub(r"\s+", "", addr))
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        alive.append((x, y, addr, str(r.get("RDNWHLADDR", ""))))
    if dup:
        print(f"[page-master] licensing: 동일 점포 중복 인허가 {dup}건 제외 "
              f"(업종 여러 장을 가진 점포 — 남은 {len(alive)}건)")
    if not alive:
        if rows:
            print("[page-master] licensing: 영업·좌표 유효 행 0 — 건너뜀")
        return {}

    try:
        from pyproj import Transformer
    except ImportError:
        print("[page-master] pyproj 없음 (pip install pyproj) — licensing 건너뜀")
        return {}
    tr = Transformer.from_crs("EPSG:2097", "EPSG:4326", always_xy=True)

    # 폴리곤 인덱스 + pnu별 중심 (자가 보정 기준점)
    index = []
    cent: dict[str, tuple[float, float]] = {}
    for f in polys:
        rings = _rings(f["geometry"])
        if not rings:
            continue
        xs = [c[0] for r in rings for c in r]
        ys = [c[1] for r in rings for c in r]
        pnu = f["properties"].get("pnu", "")
        index.append((min(xs), min(ys), max(xs), max(ys), rings, pnu))
        cent[pnu] = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    # 자가 보정: 지번주소→pnu 매칭 행의 (변환좌표 − 폴리곤중심) 중위 오프셋
    dong_code = {v: k for k, v in dong_map.items()}   # 동명 → 법정동코드5
    dlons: list[float] = []
    dlats: list[float] = []
    for x, y, addr, _rdn in alive:
        pnu = _addr_pnu(addr, dong_code, sigungu)
        if pnu not in cent:
            continue
        lon, lat = tr.transform(x, y)
        clon, clat = cent[pnu]
        kx = 111320.0 * math.cos(math.radians(clat))
        dlons.append((lon - clon) * kx)
        dlats.append((lat - clat) * 110540.0)
    if len(dlons) < 20:
        print(f"[page-master] licensing: 보정 기준점 부족({len(dlons)}) — 건너뜀")
        return {}
    dlons.sort(); dlats.sort()
    off_e, off_n = dlons[len(dlons) // 2], dlats[len(dlats) // 2]

    out: dict[str, dict] = defaultdict(lambda: {"n": 0, "floors": set(), "unknown": 0})
    hit = 0
    for x, y, addr, rdn in alive:
        lon, lat = tr.transform(x, y)
        kx = 111320.0 * math.cos(math.radians(lat))
        lon -= off_e / kx
        lat -= off_n / 110540.0
        for x0, y0, x1, y1, rings, pnu in index:
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            if any(_pip(lon, lat, r) for r in rings):
                o = out[pnu]
                o["n"] += 1
                # 인허가 주소에는 층이 문자열로 들어 있다("지상2층 201호") — 영업 중
                # 업소의 86.3%(13거점 44,493건)에서 파싱된다. 상가정보 flrNo 공란
                # 30%를 메우는 **독립 층 소스**다(2026-08-01).
                fl, found = lic_floors(f"{addr} {rdn}")
                o["floors"] |= fl
                o["unknown"] += not fl and not found
                hit += 1
                break
    print(f"[page-master] licensing: 오프셋(동서 {off_e:.1f}m, 남북 {off_n:.1f}m, "
          f"기준점 {len(dlons)}) 보정 — 영업 업소 {len(alive)}건 중 {hit}건을 {len(out)}동에 귀속")
    return {k: {"n": v["n"], "floors": sorted(v["floors"]), "unknown": v["unknown"]}
            for k, v in out.items()}


# capacity 근거의 정밀도 순위. 한 지번에 방법이 섞이면 **가장 조악한** 것으로 라벨링한다
# — 집계에서 그 지번을 신뢰 구간 밖으로 빼기 위해서다(낙관 라벨은 편향을 숨긴다).
_METHOD_RANK = {"expos_units": 0, "floor_ouln": 1, "floor_approx": 2}
# 분모 근거가 정밀해 대표 집계에 넣는 방법 — calibrate_vacancy.primary 와 같은 정의.
PRECISE_METHODS = ("expos_units", "floor_ouln")


def _method_of(rows: list[dict]) -> str:
    """지번에 속한 공실행들의 대표 capacity_method (가장 조악한 것)."""
    ms = [r.get("capacity_method", "") for r in rows if r.get("capacity")]
    ms = [m for m in ms if m in _METHOD_RANK]
    return max(ms, key=lambda m: _METHOD_RANK[m]) if ms else ""


def _aggregate(rows: list[dict], extra: int = 0, fresh: int | None = None,
               licensed: int = 0, at: dict | None = None, lic: dict | None = None) -> dict:
    """같은 지번(lnoCd)의 공실행 → 분자·분모.

    **층 단위(2026-08-01).** 행에 `capacity_floors`(recalc_floor_ouln 산출)가 있으면
    분자·분모를 모두 **층**으로 센다. STORES_PER_FLOOR=1 이라 '층 수 = 호 수' 로
    기존 표기(active/capacity)와 단위가 그대로 맞는다.
      · 분모 = 지번의 상업층 합집합 — 같은 지번 여러 동을 **합산하지 않는다**
        (capacity 는 지번당 산출물이라 합산하면 동 수만큼 부풀었다).
      · 분자 = 점포가 확인된 층 수 + 층을 모르는 점포(공란 약 30%)·PIP·인허가를
        빈 층에 낮은 층부터 앉힌 상한. 하한은 `active_floors_lo` 로 따로 보고한다.
    층 근거가 없는 행(집합건물 expos_units 등)은 종전대로 점포 수로 센다.

    fresh 가 주어지면 gold 의 active 합 대신 사용한다 (최신·광반경 stores_raw 재집계).
    licensed(인허가 영업 업소 수)는 분자의 하한 — 상가정보 누락 보정 (max 결합).
    """
    active = max((fresh if fresh is not None else sum(r["active"] for r in rows)) + extra,
                 licensed)
    top = max(rows, key=lambda r: r["active"])
    base = {"name": next((r["name"] for r in rows if r.get("name")), ""),
            "industry": top.get("industry", ""),
            "capacity_method": _method_of(rows)}

    floors: set[int] = set()
    for r in rows:
        floors |= set(r.get("capacity_floors") or [])
    if floors:
        at = at or {}
        lic = lic or {}
        # 분자 = 점포(상가정보 flrNo) ∪ 인허가(주소 층 표기) 로 확인된 층
        known = set(at.get("store_flr_nos") or []) | set(lic.get("floors") or [])
        occ_floors = sorted(floors & known)
        lo = len(occ_floors)
        # 층을 모르는 것만 빈 층에 배정(상한): 상가정보 공란 + 인허가 무표기 + PIP 점포.
        spare = ((at.get("store_flr_unknown") or 0) + (lic.get("unknown") or 0) + extra)
        hi = min(len(floors), lo + spare)
        return base | {"active": hi, "capacity": len(floors),
                       "active_floors_lo": lo, "active_floors_hi": hi,
                       # 층 **번호** 자체 — 3D 트윈이 '몇 층이 비었나'를 실배치로 그리는 근거.
                       # 개수(lo/hi)만 남기면 프론트는 아래부터 채우는 근사밖에 못 한다.
                       "com_floors": sorted(floors),   # 분모: 상업 용도 층
                       "occ_floors": occ_floors,       # 분자 하한: 점포·인허가로 확인된 층
                       "unknown_n": hi - lo,           # 층 미상 점포로 배정된 층 수(상한−하한)
                       "stores": active,                    # 점포 수(참고·하위호환)
                       "occupancy": hi / len(floors)}

    caps = [r["capacity"] for r in rows if r.get("capacity")]
    # capacity 하한 = active (근사 과소추정 시 음수 공실률 방지 — 프론트 vacRate 클램프 겸용)
    cap = max(sum(caps), active) if caps else None
    return base | {"active": active, "capacity": cap, "stores": active,
                   "occupancy": min(active / cap, 1.0) if cap else None}


def run(hub: PageHub) -> bool:
    """거점 하나의 page_building_master.geojson 산출. 반환: 성공 여부.

    building_vacancy.json(대장 산출물)이 있으면 정밀 capacity(Tier 1), 없으면
    폴리곤 지상층수 근사(Tier 2)로 동작한다.
    """
    slug = hub.slug
    polys = load_latest(slug, "bldg_polygons.geojson")
    if not polys:
        print(f"[page-master:{slug}] bldg_polygons.geojson 없음 — vworld_bldg 수집 먼저")
        return False

    attrs = load_attrs(slug)          # 층 단위 매칭용 사이드카(없으면 점포 수 기준으로 폴백)
    vac_path = GOLD / slug / "building_vacancy.json"
    vac = json.loads(vac_path.read_text(encoding="utf-8")) if vac_path.exists() else []
    tier = "Tier1(대장)" if vac else "Tier2(폴리곤근사)"

    by_lno: dict[str, list[dict]] = defaultdict(list)
    for r in vac:
        if r.get("lnoCd"):
            by_lno[r["lnoCd"]].append(r)

    # 신선 재집계 + PIP 폴백: 직접 매칭 분자 갱신, 미계상 점포는 좌표로 건물에 귀속
    poly_pnu = {f["properties"].get("pnu", "") for f in polys["features"]}
    displayed_pnu = poly_pnu & set(by_lno)
    stores = [s for s in (load_latest(slug, "stores_raw.json") or [])
              if s.get("indsLclsNm") not in NON_STOREFRONT_LCLS]
    if not stores:
        print(f"[page-master:{slug}] stores_raw.json 없음 — PIP 폴백 생략(직접 매칭만)")
    dong_map = _build_dong_map(stores)
    sigungu = Counter(s["lnoCd"][0:5] for s in stores
                      if len(s.get("lnoCd", "")) == 19).most_common(1)
    sigungu_cd = sigungu[0][0] if sigungu else ""
    fresh: dict[str, int] = {}
    extra: dict[str, int] = {}
    if stores:
        fresh, candidates = _split_stores(stores, displayed_pnu)
        extra = _pip_fallback(candidates, polys["features"])
    licensed = _licensed_pip(polys["features"], slug, dong_map, sigungu_cd)

    feats: list[dict] = []
    stats: Counter = Counter()
    seen_pnu: Counter = Counter()
    for f in polys["features"]:
        p = f["properties"]
        pnu = p.get("pnu", "")
        if len(pnu) != 19:
            stats["bad_pnu"] += 1
            continue
        floors = int(p.get("ground_floor_co") or 0)

        pip_n = extra.get(pnu, 0)
        lic = licensed.get(pnu) or {}
        lic_n = lic.get("n", 0)
        if pnu in by_lno:
            agg = _aggregate(by_lno[pnu], extra=pip_n,
                             fresh=fresh.get(pnu, 0) if stores else None,
                             licensed=lic_n, at=attrs.get(pnu), lic=lic)
            status = _classify(agg["occupancy"])
            if status is None:                    # capacity 미확인 → 지도 제외
                stats["excluded_unknown"] += 1
                continue
            props = {
                "name": _label(pnu, agg["name"], dong_map),
                "status": status,
                "capacity": agg["capacity"], "active": agg["active"],
                "industry": agg["industry"],
                "vacancy_rate": round((1 - min(agg["active"] / agg["capacity"], 1.0)) * 100, 1),
                "vacancy_rate_lo": (round((1 - agg["active_floors_hi"] / agg["capacity"]) * 100, 1)
                                    if "active_floors_hi" in agg else None),
                "vacancy_rate_hi": (round((1 - agg["active_floors_lo"] / agg["capacity"]) * 100, 1)
                                    if "active_floors_lo" in agg else None),
                "stores": agg["stores"],
                "source": "stores+ledger" + ("+pip" if pip_n else ""),
                "capacity_method": agg["capacity_method"],
                "active_pip": pip_n, "licensed": lic_n,
                # 층 실배치(BuildingTwin) — 층 근거가 있는 행에만 실린다.
                # 없는 건물은 프론트가 종전 근사(아래부터 채우기)로 폴백한다.
                "com_floors": agg.get("com_floors"),
                "occ_floors": agg.get("occ_floors"),
                "unknown_n": agg.get("unknown_n"),
            }
        elif pip_n > 0 or lic_n > 0:
            # 지번 매칭은 없지만 점포(PIP)·인허가가 귀속된 건물 — 층수 근사 분모로 재분류
            act = max(pip_n, lic_n)
            cap = max(floors * _STORES_PER_FLOOR, act, 1)
            occ = min(act / cap, 1.0)
            props = {
                "name": _label(pnu, "", dong_map),
                "status": _classify(occ),
                "capacity": cap, "active": act,
                "industry": "",
                "vacancy_rate": round((1 - occ) * 100, 1),
                "source": "pip_only",             # TODO: 대장 조회로 capacity 정밀화
                "capacity_method": "floor_approx",   # 폴리곤 지상층수 × 2 — 대장 근거 없음
                "active_pip": pip_n, "licensed": lic_n,
            }
        else:
            # 활성 점포·인허가 0 — 상업용도 건물만 '공실 의심'으로 표시
            if not str(p.get("buld_prpos_code", ""))[:2] in _COMMERCIAL_PRPS:
                stats["excluded_non_commercial"] += 1
                continue
            props = {
                "name": _label(pnu, "", dong_map),
                "status": "empty",
                "capacity": max(floors * _STORES_PER_FLOOR, 1), "active": 0,
                "industry": "",
                "vacancy_rate": 100.0,
                "source": "polygon_only",         # TODO: 대장 재확인으로 승격
                "capacity_method": "floor_approx",   # 상동 — 공실 의심 표시용이며 집계 제외
                "active_pip": 0, "licensed": 0,
            }

        seen_pnu[pnu] += 1
        props.update({
            "id": f"{pnu}-{seen_pnu[pnu]}",
            "pnu": pnu,
            "floors": floors,
            "height": float(p.get("hg") or 0),
        })
        stats[props["status"]] += 1
        feats.append({"type": "Feature", "geometry": f["geometry"], "properties": props})

    out = {"type": "FeatureCollection", "district": slug, "features": feats}
    dst = GOLD / slug / "page_building_master.geojson"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    # Tier1 은 대장 매칭 건물(stores+ledger), Tier2 는 폴리곤근사(pip_only) 기준으로 참고 공실률 산출
    ref = [f for f in feats if f["properties"]["source"].startswith("stores+ledger")]
    if not ref:
        ref = [f for f in feats if f["properties"]["source"] == "pip_only"]
    act = sum(f["properties"]["active"] for f in ref)
    cap = sum(f["properties"]["capacity"] for f in ref)
    print(f"[gold:{slug}] page_building_master.geojson: {len(feats)}동 · {tier}")
    print(f"[page-master:{slug}] status: "
          + ", ".join(f"{k}={stats[k]}" for k in ("full", "partial", "high", "empty")))
    print(f"[page-master:{slug}] 제외: unknown={stats['excluded_unknown']}, "
          f"비상업={stats['excluded_non_commercial']}")

    # ── 집계 공실률 — **capacity_method 별로 분해해서 본다** (2026-07-28) ──────────
    # 예전에는 stores+ledger 전체를 한 덩어리로 합산했다. 그러면 지표가 "이 상권이
    # 얼마나 비었나" 가 아니라 "이 거점 건물 중 몇 %가 어느 capacity 방법을 받았나"
    # 를 재는 셈이 된다. 2026-07-27 garosugil 이 정확히 그렇게 39.1% → 56.0% 로 뛰었다:
    # 기존 558동은 active·capacity 가 한 톨도 안 변했고, 신규 유입 372동 중 304동이
    # 전부 floor_approx(지상 **전체** 층수 × 2호) 로 들어왔을 뿐이다.
    # → 대표값(primary)은 분모 근거가 정밀한 expos_units + floor_ouln 만 쓴다.
    # 지번(pnu) 단위로 **중복 제거**하고 집계한다. 한 지번에 폴리곤이 여러 개인 경우
    # (동일 대지에 여러 동 — V-World 에서 흔하다) 지도에는 동마다 그려야 하지만, 각
    # feature 는 그 지번의 active·capacity 를 통째로 물려받으므로 그대로 합산하면 같은
    # 건물이 N 배 가중된다. 2026-07-28 seoulsup 실측: "쌍용아파트"(act 23 / cap 189)가
    # 폴리곤 8개에 복제돼 거점 공실의 30% 를 혼자 만들어냈다.
    seen: set[str] = set()
    by_method: dict[str, list[dict]] = defaultdict(list)
    for f in ref:
        p = f["properties"]
        if p["pnu"] in seen:
            continue
        seen.add(p["pnu"])
        by_method[p.get("capacity_method") or "unknown"].append(p)

    def _rate(ps: list[dict]) -> tuple[int, int, float | None]:
        a = sum(p["active"] for p in ps)
        c = sum(p["capacity"] for p in ps)
        return a, c, round((1 - a / c) * 100, 1) if c else None

    methods_rep: dict[str, dict] = {}
    for m, ps in sorted(by_method.items(), key=lambda kv: -len(kv[1])):
        a, c, v = _rate(ps)
        methods_rep[m] = {"buildings": len(ps), "active": a, "capacity": c, "vacancy_pct": v}

    precise = [p for m in PRECISE_METHODS for p in by_method.get(m, [])]
    p_act, p_cap, p_vac = _rate(precise)
    uniq = sum(len(v) for v in by_method.values())
    coverage = round(len(precise) / uniq * 100, 1) if uniq else None
    if cap:
        print(f"[page-master:{slug}] 집계 공실률(혼합, 하위호환): "
              f"{round((1 - act / cap) * 100, 1)}% — 방법 구성비에 흔들리므로 앵커 비교 금지")
    for m, s in methods_rep.items():
        print(f"[page-master:{slug}]   {m:13s} {s['buildings']:5d}동 "
              f"{s['active']:5d}/{s['capacity']:6d} = {s['vacancy_pct']}%")
    if p_cap:
        print(f"[page-master:{slug}] ▶ 대표 집계 공실률(정밀 분모만): {p_vac}% "
              f"({len(precise)}동, 커버리지 {coverage}%)")
        if coverage is not None and coverage < 80:
            print(f"[page-master:{slug}] ⚠ 커버리지 {coverage}% — floor_approx 잔여가 많다. "
                  f"`python -m data.collectors.floor_capacity {slug}` 로 층별개요를 채울 것.")
    else:
        print(f"[page-master:{slug}] ⚠ 정밀 분모 건물 0동 — 대표 집계 공실률 산출 불가"
              f"(floor_capacity 미수집 거점).")

    # 커버리지 리포트 — **관리자 전용**. 공개 지도는 status 4종만 그리므로 '대장 미확인
    # 으로 제외된 N동'이 사용자에게는 보이지 않는다. 그 사실을 운영자가 확인할 수 있게
    # 별도 파일로 남긴다(2026-07-26). 지도에 섞어 표시하면 근거가 다른 데이터가 한
    # 화면에 오게 되어 "대장 기반 실측" 논증이 무너지므로 노출 경로를 분리한다.
    shown = sum(stats[k] for k in ("full", "partial", "high", "empty"))
    excluded = stats["excluded_unknown"] + stats["excluded_non_commercial"]
    (GOLD / slug / "coverage.json").write_text(json.dumps({
        "slug": slug,
        "hub_name": hub.name,
        "tier": tier,
        "built_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "shown": shown,
        "excluded_total": excluded,
        "excluded_unknown": stats["excluded_unknown"],
        "excluded_non_commercial": stats["excluded_non_commercial"],
        "coverage_pct": round(shown / (shown + excluded) * 100, 1) if shown + excluded else None,
        "status": {k: stats[k] for k in ("full", "partial", "high", "empty")},
        "source": dict(Counter(f["properties"]["source"] for f in feats)),
        "reference_vacancy_pct": p_vac,
        "reference_buildings": len(precise),
        "reference_coverage_pct": coverage,
        "mixed_vacancy_pct": round((1 - act / cap) * 100, 1) if cap else None,
        "by_capacity_method": methods_rep,
        "note": "excluded_unknown = 건축물대장에서 capacity 를 얻지 못해 지도에서 뺀 건물. "
                "공개 지도에는 노출하지 않는다(관리자 전용). "
                "reference_vacancy_pct = 분모 근거가 정밀한 방법(expos_units·floor_ouln)만 "
                "집계한 대표값이며 reference_coverage_pct 가 낮으면 신뢰하지 말 것. "
                "mixed_vacancy_pct(구 reference)는 floor_approx 를 섞은 값이라 방법 "
                "구성비에 따라 흔들린다 — 하위호환용.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def main() -> None:
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    slugs = args or list(HUBS)
    ok = 0
    for slug in slugs:
        hub = HUBS.get(slug)
        if hub is None:
            print(f"[page-master] 미등록 거점 '{slug}' — page_hubs.HUBS 확인, 건너뜀")
            continue
        if run(hub):
            ok += 1
    print(f"[page-master] 완료: {ok}/{len(slugs)}거점")


if __name__ == "__main__":
    main()
