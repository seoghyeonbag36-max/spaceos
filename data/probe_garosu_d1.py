"""D1 관통 검증 프로브 — 가로수길 3-API 스키마·조인 확인 (건물 단위 공실 PoC).

목적(설계서 docs/poc-building-vacancy.md §5 D1):
  1) 소상공인 상가정보(반경) → 실제 응답 필드 확인 + 건물관리번호(bdMgtSn) 존재 검증
  2) 점포를 bdMgtSn(건물)별로 그룹핑 → 활성 점포 수(분자, occupancy) 산출
  3) 한 건물의 지번(시군구+법정동+본번+부번)으로 건축물대장 표제부/전유공용면적 조회
     → capacity(분모: 상업용도 전유 호 수) 산출 가능 여부 검증
  4) bdMgtSn ↔ 지번 ↔ 대장이 실제로 이어지는지 "관통" 1회 확인

실행:
  export DATA_GO_KR_SERVICE_KEY="<디코딩 인증키>"   # PowerShell: $env:DATA_GO_KR_SERVICE_KEY="..."
  python data/probe_garosu_d1.py

주의:
  - 아래 3개 API 각각 data.go.kr에서 '활용신청'이 승인돼 있어야 한다(§ 하단 목록).
  - 건축물대장 엔드포인트는 건축HUB(15134735, BldRgstHubService) 기준.
    ※ 구 BldRgstService_v2(15044713)는 2026-07 확인 시 서비스 종료('Unexpected errors') —
      건축HUB가 유일한 경로다. 실패 시 로그로 원인 표시.
  - 이 스크립트는 '검증용'이다. 확정된 필드/조인은 collectors/building_vacancy.py 로 옮긴다.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

# Windows 콘솔(cp949)에서 특수문자 출력 크래시 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("requests 필요: pip install requests")
    sys.exit(1)

# ── 가로수길 코어 축 (강남구 신사동) ─────────────────────────────────
GAROSU_CX = 127.0230   # 경도(lon)  ※ 네이버/카카오 지도에서 최종 확정 권장
GAROSU_CY = 37.5205    # 위도(lat)
RADIUS_M = 400
GANGNAM_SIGUNGU = "11680"   # 강남구 시군구코드
SINSA_BJDONG = "10700"      # 신사동 법정동코드 뒤 5자리(1168010700) ※실행 시 재확인

BASE_SDSC = "http://apis.data.go.kr/B553077/api/open/sdsc2"
BASE_BLD = "http://apis.data.go.kr/1613000/BldRgstHubService"
COMMERCIAL_PURPS = ("근린생활시설", "판매시설", "업무시설", "숙박시설", "위락시설")


def _get(url: str, params: dict) -> dict | None:
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  [HTTP 실패] {url}\n            {exc}")
        return None


def step1_stores(key: str) -> list[dict]:
    """반경 400m 점포 조회 → 필드/건물관리번호 검증."""
    print("\n=== STEP 1. 소상공인 상가정보 (storeListInRadius) ===")
    js = _get(f"{BASE_SDSC}/storeListInRadius", {
        "serviceKey": key, "radius": RADIUS_M, "cx": GAROSU_CX, "cy": GAROSU_CY,
        "type": "json", "numOfRows": 1000, "pageNo": 1,
    })
    if not js:
        return []
    body = js.get("body", js.get("response", {}).get("body", {}))
    items = body.get("items") or []
    if isinstance(items, dict):
        items = items.get("item", [])
    total = body.get("totalCount", len(items))
    print(f"  총 {total}건, 수신 {len(items)}건")
    if items:
        keys = sorted(items[0].keys())
        print(f"  응답 필드({len(keys)}): {keys}")
        has_bld = any(k in items[0] for k in ("bdMgtSn", "buldMnnm", "bldMngNo"))
        print(f"  ▶ 건물관리번호 필드 존재? {'예' if has_bld else '아니오 — 조인전략 재검토 필요'}")
        print(f"  샘플 1건: {items[0]}")
    return items


def step2_group_by_building(items: list[dict]) -> dict[str, list[dict]]:
    """bdMgtSn(건물)별 그룹핑 → 건물당 활성 점포 수(분자)."""
    print("\n=== STEP 2. 건물(bdMgtSn)별 그룹핑 → occupancy 분자 ===")
    groups: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        bld = it.get("bdMgtSn") or it.get("bldMngNo") or ""
        if bld:
            groups[bld].append(it)
    print(f"  건물 수(고유 bdMgtSn): {len(groups)}")
    top = sorted(groups.items(), key=lambda x: -len(x[1]))[:5]
    for bld, sts in top:
        print(f"   - {bld}: 활성점포 {len(sts)}개 (예: {sts[0].get('bizesNm','?')})")
    return groups


def step3_ledger(key: str, sample_store: dict) -> None:
    """한 점포의 지번 → 건축물대장 표제부/전유공용면적 → capacity 검증."""
    print("\n=== STEP 3. 건축물대장 조인 (지번 기반) → capacity 분모 ===")
    # 상가정보 지번 필드에서 본번/부번 추출(필드명은 STEP1 로그로 확정)
    bun = str(sample_store.get("lnoMnno") or sample_store.get("지번본번지") or "").split(".")[0]
    ji = str(sample_store.get("lnoSlno") or sample_store.get("지번부번지") or "0").split(".")[0]
    print(f"  대상 지번: 시군구 {GANGNAM_SIGUNGU} / 법정동 {SINSA_BJDONG} / 본번 {bun} / 부번 {ji}")
    if not bun:
        print("  ▶ 상가정보에서 지번 본번 미확보 — STEP1 필드명 확인 후 매핑 수정 필요")
        return
    common = {"serviceKey": key, "sigunguCd": GANGNAM_SIGUNGU, "bjdongCd": SINSA_BJDONG,
              "platGbCd": "0", "bun": bun.zfill(4), "ji": ji.zfill(4),
              "_type": "json", "numOfRows": 100, "pageNo": 1}

    title = _get(f"{BASE_BLD}/getBrTitleInfo", common)
    if title:
        its = _dig_items(title)
        print(f"  [표제부] {len(its)}건")
        if its:
            t = its[0]
            print(f"    주용도: {t.get('mainPurpsCdNm')} / 연면적: {t.get('totArea')} / "
                  f"지상층수: {t.get('grndFlrCnt')} / 세대·가구·호: "
                  f"{t.get('hhldCnt')}·{t.get('fmlyCnt')}·{t.get('hoCnt')}")

    expos = _get(f"{BASE_BLD}/getBrExposPubuseAreaInfo", common)
    if expos:
        its = _dig_items(expos)
        commercial_units = [
            u for u in its
            if u.get("exposPubuseGbCdNm") == "전유"
            and any(p in (u.get("mainPurpsCdNm") or "") for p in COMMERCIAL_PURPS)
        ]
        print(f"  [전유공용면적] 전체 {len(its)}행 / 상업 전유 호(capacity 후보): {len(commercial_units)}")
        print("  ▶ capacity 산출 가능? " +
              ("예 — 상업 전유 호 카운트" if commercial_units else
               "집합 아님/미검출 → 층별개요·면적근사 폴백 필요"))


def _dig_items(js: dict) -> list[dict]:
    body = js.get("response", {}).get("body", {})
    items = body.get("items") or {}
    if isinstance(items, dict):
        items = items.get("item", [])
    return items if isinstance(items, list) else [items] if items else []


def main() -> None:
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key:
        print("환경변수 DATA_GO_KR_SERVICE_KEY 미설정 — 키 발급/설정 후 재실행.")
        sys.exit(1)
    stores = step1_stores(key)
    if not stores:
        print("\n점포 미수신 — 서비스키 승인/반경/좌표 확인 후 재시도.")
        return
    step2_group_by_building(stores)
    step3_ledger(key, stores[0])
    print("\n=== D1 관통 검증 종료 — 위 로그로 필드/조인 확정 후 collector 구현 ===")


if __name__ == "__main__":
    main()
