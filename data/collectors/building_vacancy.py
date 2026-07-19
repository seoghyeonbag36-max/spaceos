"""[Page·핵심] 건물 단위 공실 추정 수집기 — docs/poc-building-vacancy.md §2 구현.

공식: 공실률_bldg = 1 − (활성 점포 수 / 상가 수용 호 수)
  분자 = 소상공인 상가정보 storeListInRadius → `bldMngNo`(bdMgtSn) 그룹핑
  분모 = 건축HUB(BldRgstHubService) 전유공용면적의 상업 전유 호 수(집합건물)
         / 표제부 지상층수 × 층당 2호 근사(일반건물, TODO 층별개요 정밀화)

D1 프로브(2026-07-07)로 확정된 실측 필드 기준. 구 BldRgstService_v2 는 서비스 종료.
지번 파생: 상가정보 `lnoCd`(19자리, PNU 동형) → sigunguCd/bjdongCd/platGbCd/bun/ji.

산출:
  bronze/{SLUG}/{날짜}/stores_raw.json        점포 원본 (무가공)
  bronze/{SLUG}/{날짜}/bldg_ledger_raw.json   지번별 대장 응답 원본
  gold/{SLUG}/building_vacancy.json           건물별 occupancy/vacancy/status
    → apps/backend/app/services/building_vacancy.py 의 _GAROSU 더미 대체 소스

쿼터: 건축HUB 일 1,000건 가정 — 건물당 전유부 1콜(+일반건물만 표제부 1콜).
      LIMIT_BUILDINGS 환경변수로 스모크 테스트 가능 (예: LIMIT_BUILDINGS=8).

실행: python -m data.collectors.building_vacancy
"""
from __future__ import annotations

import os
import time
from collections import Counter, defaultdict

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import load_env, save_json
from data.config.garosugil import CX, CY, SLUG, STORES_RADIUS_M

BASE_SDSC = "http://apis.data.go.kr/B553077/api/open/sdsc2"
BASE_BLD = "http://apis.data.go.kr/1613000/BldRgstHubService"

# 상업 용도 키워드 (표제부 주용도·전유부 호별 용도 공통 필터)
COMMERCIAL_PURPS = ("근린생활", "판매", "업무", "숙박", "위락", "문화")
STORES_PER_FLOOR = 2          # 일반건물 근사: 층당 상가 호 수 (α보정 §3 대상)
_SLEEP = 0.05                 # API 예의 지연


_FAILS = [0]           # 연속 실패 카운터 (쿼터 소진 감지 → 부분 저장 후 중단)
_ABORT_AFTER = 15


def _get_json(url: str, params: dict) -> dict | None:
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        _FAILS[0] = 0
        return data
    except Exception as exc:
        _FAILS[0] += 1
        print(f"  [HTTP 실패 {_FAILS[0]}연속] {url.rsplit('/', 1)[-1]} — {exc}")
        return None


# ── 1. 분자: 상가정보 반경 수집 → bdMgtSn 그룹핑 ─────────────────────

def fetch_stores(key: str) -> list[dict]:
    """가로수길 반경 STORES_RADIUS_M 점포 전량 (페이징) — 폴리곤 범위보다 넓게."""
    rows: list[dict] = []
    page = 1
    while True:
        data = _get_json(f"{BASE_SDSC}/storeListInRadius", {
            "serviceKey": key, "type": "json", "numOfRows": 1000, "pageNo": page,
            "radius": STORES_RADIUS_M, "cx": CX, "cy": CY,
        })
        items = (data or {}).get("body", {}).get("items", []) or []
        rows += items
        total = (data or {}).get("body", {}).get("totalCount", 0)
        print(f"[stores] p{page}: {len(items)}건 (누적 {len(rows)}/{total})")
        if not items or len(rows) >= int(total):
            break
        page += 1
        time.sleep(_SLEEP)
    return rows


def group_by_building(stores: list[dict]) -> dict[str, dict]:
    """bdMgtSn(=bldMngNo) 그룹 → 활성 점포 수·대표 지번·좌표·업종."""
    groups: dict[str, list[dict]] = defaultdict(list)
    no_key = 0
    for s in stores:
        k = s.get("bldMngNo") or ""
        if not k:
            no_key += 1        # TODO(Silver): 좌표 PIP 폴백으로 건물 귀속
            continue
        groups[k].append(s)
    print(f"[group] 건물 {len(groups)}동 / bdMgtSn 누락 {no_key}건(PIP 폴백 TODO)")

    out: dict[str, dict] = {}
    for k, ss in groups.items():
        lno = Counter(s.get("lnoCd", "") for s in ss if s.get("lnoCd")).most_common(1)
        out[k] = {
            "bdMgtSn": k,
            "name": Counter(s.get("bldNm", "") for s in ss if s.get("bldNm")).most_common(1)[0][0]
                    if any(s.get("bldNm") for s in ss) else "",
            "lnoCd": lno[0][0] if lno else "",
            "lat": sum(float(s["lat"]) for s in ss) / len(ss),
            "lon": sum(float(s["lon"]) for s in ss) / len(ss),
            "active": len(ss),
            "industry": Counter(s.get("indsMclsNm", "") for s in ss).most_common(1)[0][0],
        }
    return out


# ── 2. 분모: 건축HUB capacity ────────────────────────────────────────

def _jibun(lno_cd: str) -> dict | None:
    """lnoCd(19자리, PNU 동형) → 건축HUB 요청 파라미터."""
    if not lno_cd or len(lno_cd) != 19:
        return None
    return {
        "sigunguCd": lno_cd[0:5], "bjdongCd": lno_cd[5:10],
        "platGbCd": str(max(int(lno_cd[10]) - 1, 0)),
        "bun": lno_cd[11:15], "ji": lno_cd[15:19],
    }


def _body(data: dict | None) -> dict:
    return (data or {}).get("response", {}).get("body", {}) or {}


def _items(data: dict | None) -> list[dict]:
    """건축HUB 응답 body.items.item — dict/list 편차 흡수."""
    item = (_body(data).get("items", {}) or {}).get("item", [])
    return [item] if isinstance(item, dict) else (item or [])


_MAX_EXPOS_PAGES = 8   # 건물당 전유부 페이지 상한 (100행×8 = 800호. 쿼터 보호)


def fetch_capacity(key: str, jibun: dict, raw_store: dict) -> tuple[int | None, str]:
    """(capacity, method). 전유부 상업 호 수 → 없으면 표제부 층수 근사."""
    common = {"serviceKey": key, "_type": "json", "numOfRows": 100, **jibun}

    # 전유공용면적 — 서버가 페이지당 100행 반환 → totalCount 까지 페이징
    rows: list[dict] = []
    page, total = 1, None
    while page <= _MAX_EXPOS_PAGES:
        expos = _get_json(f"{BASE_BLD}/getBrExposPubuseAreaInfo", {**common, "pageNo": page})
        got = _items(expos)
        rows += got
        total = int(_body(expos).get("totalCount") or 0)
        if not got or len(rows) >= total:
            break
        page += 1
        time.sleep(_SLEEP)
    raw_store["expos"] = rows
    raw_store["expos_total"] = total

    # 상업 전유 호만 capacity 로 카운트 — 오피스텔·주택 호는 제외 (§1-2)
    units = {
        (r.get("dongNm", ""), r.get("hoNm", ""), r.get("flrNoNm", ""))
        for r in rows
        if r.get("exposPubuseGbCdNm") == "전유"
        and any(p in str(r.get("mainPurpsCdNm", "")) for p in COMMERCIAL_PURPS)
    }
    if units:
        return len(units), "expos_units"

    time.sleep(_SLEEP)
    title = _get_json(f"{BASE_BLD}/getBrTitleInfo", common)
    rows = _items(title)
    raw_store["title"] = rows
    if not rows:
        return None, "no_ledger"
    t = rows[0]
    if not any(p in str(t.get("mainPurpsCdNm", "")) for p in COMMERCIAL_PURPS):
        return None, "non_commercial"
    floors = int(t.get("grndFlrCnt") or 0)
    if floors <= 0:
        return None, "no_ledger"
    # TODO(정밀화): 층별개요(getBrFlrOulnInfo)로 상업 용도 층만 카운트
    return max(floors * STORES_PER_FLOOR, 1), "floor_approx"


# ── 3. 지표 산출 ─────────────────────────────────────────────────────

def classify(occ: float | None, method: str) -> str:
    """MapShell/백엔드 status 코드 (full/partial/high/empty/unknown/n_a)."""
    if method == "non_commercial":
        return "n_a"
    if occ is None:
        return "unknown"
    if occ >= 0.9:
        return "full"
    if occ >= 0.5:
        return "partial"
    if occ > 0:
        return "high"
    return "empty"


def main() -> None:
    load_env()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key or requests is None:
        print("[bldg-vac] DATA_GO_KR_SERVICE_KEY 미설정(또는 requests 없음) — 건너뜀")
        return

    stores = fetch_stores(key)
    if not stores:
        print("[bldg-vac] 점포 0건 — 키/파라미터 확인")
        return
    save_json(stores, SLUG, "stores_raw.json")
    buildings = group_by_building(stores)

    limit = int(os.getenv("LIMIT_BUILDINGS", "0"))
    targets = list(buildings.values())
    targets.sort(key=lambda b: -b["active"])          # 점포 많은 건물 우선
    if limit:
        targets = targets[:limit]
        print(f"[bldg-vac] LIMIT_BUILDINGS={limit} — 스모크 테스트 모드")

    ledger_raw: dict[str, dict] = {}
    results: list[dict] = []
    for i, b in enumerate(targets, 1):
        if _FAILS[0] >= _ABORT_AFTER:
            print(f"[bldg-vac] ⚠ 연속 실패 {_FAILS[0]}회(쿼터 소진 추정) — {i-1}동까지 부분 저장 후 중단")
            break
        jibun = _jibun(b["lnoCd"])
        if jibun is None:
            cap, method = None, "no_jibun"
        else:
            raw: dict = {}
            cap, method = fetch_capacity(key, jibun, raw)
            ledger_raw[b["lnoCd"]] = raw
            time.sleep(_SLEEP)

        occ = min(b["active"] / cap, 1.0) if cap else None
        results.append({
            **b,
            **(jibun or {}),
            "capacity": cap,
            "capacity_method": method,
            "occupancy": None if occ is None else round(occ, 3),
            "vacancy_bldg": None if occ is None else round((1 - occ) * 100, 1),
            "status": classify(occ, method),
            "match_method": "bdMgtSn_group",
        })
        if i % 50 == 0 or i == len(targets):
            print(f"[ledger] {i}/{len(targets)}동 처리")

    save_json(ledger_raw, SLUG, "bldg_ledger_raw.json")

    from data.collectors.common import GOLD
    gold_dir = GOLD / SLUG
    gold_dir.mkdir(parents=True, exist_ok=True)
    import json
    (gold_dir / "building_vacancy.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    st = Counter(r["status"] for r in results)
    cm = Counter(r["capacity_method"] for r in results)
    print(f"[gold] building_vacancy.json ({len(results)}동)")
    print(f"[bldg-vac] status 분포: {dict(st)}")
    print(f"[bldg-vac] capacity 방식: {dict(cm)}")


if __name__ == "__main__":
    main()
