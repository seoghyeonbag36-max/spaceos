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

다거점: config/page_hubs.py HUBS 를 순회한다. 점포(sdsc2)·폴리곤(V-World)은 쿼터가
넉넉하나 **건축HUB 대장은 일일 쿼터가 빡빡**하다(garosugil 1곳 ≈ 720동 = 720~1,440콜).
  --no-ledger (또는 PAGE_LEDGER=0): 대장 수집을 건너뛰고 stores_raw.json 만 남긴다.
    → build_page_master 가 V-World 폴리곤 지상층수로 capacity 를 근사(Tier 2 확장 경로).
  기본(ledger on)은 garosugil 처럼 대장까지 받는 정밀 경로(Tier 1). 쿼터 감안해 거점 지정 권장:
    python -m data.collectors.building_vacancy seongsu           # 1곳 정밀
    python -m data.collectors.building_vacancy --no-ledger       # 전 거점 점포만

실행: python -m data.collectors.building_vacancy [slug ...] [--no-ledger] [--force]
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import GOLD, latest_bronze, load_env, load_latest, save_json
from data.config.page_hubs import HUBS, PageHub

BASE_SDSC = "http://apis.data.go.kr/B553077/api/open/sdsc2"
BASE_BLD = "http://apis.data.go.kr/1613000/BldRgstHubService"

# 상업 용도 키워드 (표제부 주용도·전유부 호별 용도 공통 필터)
COMMERCIAL_PURPS = ("근린생활", "판매", "업무", "숙박", "위락", "문화")

# 분자에서 제외할 사무실형 업종 대분류 — 분모(상업 층·상가 호)와 도메인 정합.
# 사무실 입주 업종을 세면 점포 수용량 대비 분자가 부풀어 공실이 과소추정된다
# (2026-07-19 정합 교정: 미필터 시 집계 공실률 5.7% vs 부동산원 41.6%).
NON_STOREFRONT_LCLS = ("과학·기술", "부동산", "시설관리·임대")
STORES_PER_FLOOR = 2          # 일반건물 근사: 층당 상가 호 수 (α보정 §3 대상)
_SLEEP = 0.05                 # API 예의 지연


_FAILS = [0]           # 연속 실패 카운터 (쿼터 소진 감지 → 부분 저장 후 중단)
_ABORT_AFTER = 15
_RETRIES = 4           # 연결·DNS 오류 재시도 횟수 (이 환경은 DNS getaddrinfo 가 간헐 실패)
_BACKOFF = (1, 3, 8, 15)   # 재시도 간 대기(초) — 일시적 DNS 블립을 넘긴다


def _get_json(url: str, params: dict) -> dict | None:
    """건축HUB GET. 연결/DNS 일시 오류는 백오프 재시도(_FAILS 미가산),
    재시도 소진 시에만 실패로 집계 — DNS 블립에 배치 전체가 죽지 않게 한다."""
    last = None
    for attempt in range(_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            _FAILS[0] = 0
            return data
        except Exception as exc:
            last = exc
            if attempt < _RETRIES:
                time.sleep(_BACKOFF[min(attempt, len(_BACKOFF) - 1)])
    _FAILS[0] += 1
    print(f"  [HTTP 실패 {_FAILS[0]}연속] {url.rsplit('/', 1)[-1]} — {last}")
    return None


# ── 1. 분자: 상가정보 반경 수집 → bdMgtSn 그룹핑 ─────────────────────

def fetch_stores(key: str, hub: PageHub) -> list[dict]:
    """거점 반경 stores_radius_m 점포 전량 (페이징) — 폴리곤 범위보다 넓게."""
    rows: list[dict] = []
    page = 1
    while True:
        data = _get_json(f"{BASE_SDSC}/storeListInRadius", {
            "serviceKey": key, "type": "json", "numOfRows": 1000, "pageNo": page,
            "radius": hub.stores_radius_m, "cx": hub.cx, "cy": hub.cy,
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
        if s.get("indsLclsNm") in NON_STOREFRONT_LCLS:
            continue           # 사무실형 업종 — 분모(상가 호수)와 도메인 불일치
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


_CHECKPOINT = 150   # 이 동수마다 부분 저장 — 중단돼도 진행분 보존(재개 가능)


def _save_ledger(slug: str, results: list[dict], ledger_raw: dict[str, dict]) -> None:
    """대장 결과 부분/최종 저장 — bronze(원본) + gold(building_vacancy)."""
    save_json(ledger_raw, slug, "bldg_ledger_raw.json")
    gold_dir = GOLD / slug
    gold_dir.mkdir(parents=True, exist_ok=True)
    (gold_dir / "building_vacancy.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def run_hub(key: str, hub: PageHub, do_ledger: bool = True,
            refresh_stores: bool = False) -> bool:
    """거점 하나 수집. do_ledger=False 면 점포만(Tier 2).

    재개 가능: 대장 루프는 _CHECKPOINT 동마다 저장하고, 재실행 시 기존
    building_vacancy.json 의 완료 건물(bdMgtSn)을 건너뛴다. 중단(쿼터 소진·강제
    종료)돼도 진행분이 남아 다음 실행이 나머지만 채운다. refresh_stores=False 면
    기존 stores_raw 를 재사용해 점포 재수집을 생략한다(재개 효율).
    반환: 성공 여부.
    """
    _FAILS[0] = 0
    slug = hub.slug

    stores = None if refresh_stores else load_latest(slug, "stores_raw.json")
    if stores is None:
        stores = fetch_stores(key, hub)
        if not stores:
            print(f"[bldg-vac:{slug}] 점포 0건 — 키/파라미터 확인")
            return False
        save_json(stores, slug, "stores_raw.json")
    else:
        print(f"[bldg-vac:{slug}] 기존 stores_raw {len(stores)}건 재사용(--force 로 재수집)")

    if not do_ledger:
        print(f"[bldg-vac:{slug}] --no-ledger — 점포 {len(stores)}건만 저장(대장 생략, "
              f"build_page_master 가 폴리곤 층수로 capacity 근사)")
        return True

    buildings = group_by_building(stores)
    limit = int(os.getenv("LIMIT_BUILDINGS", "0"))
    targets = list(buildings.values())
    targets.sort(key=lambda b: -b["active"])          # 점포 많은 건물 우선
    if limit:
        targets = targets[:limit]
        print(f"[bldg-vac:{slug}] LIMIT_BUILDINGS={limit} — 스모크 테스트 모드")

    # 재개: 기존 대장 산출물(Tier1)의 완료 건물은 건너뛴다
    results: list[dict] = []
    done: set[str] = set()
    gold_path = GOLD / slug / "building_vacancy.json"
    if gold_path.exists():
        try:
            prev = json.loads(gold_path.read_text(encoding="utf-8"))
            if isinstance(prev, list) and prev and "capacity_method" in prev[0]:
                results = prev
                done = {r.get("bdMgtSn") for r in prev if r.get("bdMgtSn")}
        except (json.JSONDecodeError, OSError):
            pass
    ledger_raw: dict[str, dict] = (load_latest(slug, "bldg_ledger_raw.json") or {}) if done else {}

    todo = [b for b in targets if b["bdMgtSn"] not in done]
    print(f"[bldg-vac:{slug}] 대장 대상 {len(todo)}동 (전체 {len(targets)} · 기존완료 {len(done)})")

    since = 0
    for b in todo:
        if _FAILS[0] >= _ABORT_AFTER:
            print(f"[bldg-vac:{slug}] ⚠ 연속 실패 {_FAILS[0]}회(쿼터 소진 추정) — "
                  f"{len(results)}동까지 저장 후 중단(다음 실행이 재개)")
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
        since += 1
        if since >= _CHECKPOINT:
            _save_ledger(slug, results, ledger_raw)
            print(f"[checkpoint:{slug}] {len(results)}/{len(targets)}동 저장")
            since = 0

    _save_ledger(slug, results, ledger_raw)

    st = Counter(r["status"] for r in results)
    cm = Counter(r["capacity_method"] for r in results)
    print(f"[gold:{slug}] building_vacancy.json ({len(results)}동)")
    print(f"[bldg-vac:{slug}] status 분포: {dict(st)}")
    print(f"[bldg-vac:{slug}] capacity 방식: {dict(cm)}")
    return True


def main() -> None:
    load_env()
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key or requests is None:
        print("[bldg-vac] DATA_GO_KR_SERVICE_KEY 미설정(또는 requests 없음) — 건너뜀")
        return

    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("-")]
    force = "--force" in argv
    do_ledger = "--no-ledger" not in argv and os.getenv("PAGE_LEDGER", "1") != "0"
    slugs = args or list(HUBS)
    for slug in slugs:
        hub = HUBS.get(slug)
        if hub is None:
            print(f"[bldg-vac] 미등록 거점 '{slug}' — page_hubs.HUBS 확인, 건너뜀")
            continue
        if do_ledger:
            # 대장 모드: 완료 판정이 애매하므로 run_hub 의 재개 로직에 맡긴다
            # (기존 완료 건물은 건너뛰고 나머지만 채운다). 점포는 기존분 재사용.
            run_hub(key, hub, do_ledger=True, refresh_stores=force)
        else:
            # Tier2(점포만): 이미 있으면 건너뛰고, 있으면 신선 수집이 목적이라 재수집
            if not force and latest_bronze(slug, "stores_raw.json") is not None:
                print(f"[bldg-vac:{slug}] stores_raw.json 이미 존재 — 건너뜀(--force 로 재수집)")
                continue
            run_hub(key, hub, do_ledger=False, refresh_stores=True)


if __name__ == "__main__":
    main()
