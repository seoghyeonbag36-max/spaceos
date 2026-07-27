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

# 엔드포인트명 — 쿼터는 **오퍼레이션별로 따로** 걸린다. 2026-07-26 확인: 전유부가
# 429 로 완전히 막힌 시각에도 표제부·층별개요는 100% 성공했다.
EP_EXPOS = "getBrExposPubuseAreaInfo"   # 전유부 — capacity 정밀 경로(집합건물)
EP_TITLE = "getBrTitleInfo"             # 표제부 — 층수 근사 폴백

# 상업 용도 키워드 — **표제부 전용**. getBrTitleInfo 의 mainPurpsCdNm 은 대분류명
# ("제2종근린생활시설"/"제1종근린생활시설"/"업무시설")이라 아래 positive 필터가 맞는다.
COMMERCIAL_PURPS = ("근린생활", "판매", "업무", "숙박", "위락", "문화")

# 전유부(getBrExposPubuseAreaInfo)의 mainPurpsCdNm 은 **세부용도명**("소매점"/"일반음식점"
# /"의원"/"학원")이라 위 대분류 필터가 걸리지 않는다. 같은 상수를 양쪽에 쓰던 것이
# 2026-07-26 확인된 버그: 압구정로데오 전유 호 중 대분류로 매칭되는 것은
# "기타제1종근린생활시설" 24건뿐이고 소매점 209·일반음식점 104·의원 79·휴게음식점 41은
# 전부 탈락 → capacity 14.6배 과소집계 → occupancy 1.0 clip 이 전체의 73%.
# 세부용도명은 종류가 많아 positive 열거는 반드시 누락이 생기므로 negative 로 제외한다.
# 주거 + 사무실형을 뺀다. 사무실형을 빼는 이유는 분자의 NON_STOREFRONT_LCLS 와 같다 —
# 분자에서 사무실 입주 업종을 제외했으므로 분모(수용 호수)에서도 빼야 도메인이 맞는다.
# 2026-07-26 garosugil 실측으로 확인: 사무소를 남기면 집합 세그먼트 추정 공실률이
# 36.9%(앵커 격차 26.9%p), 빼면 31.1%(격차 21.1%p)로 부동산원 앵커에 더 가깝다.
# 공장/창고류를 빼는 이유도 같다 — 지식산업센터(아파트형 공장)는 전유 호가 수백
# 개인데 "기타공장"이라 상가가 아니다. 2026-07-26 성수 실측: capacity>200 인 9개 동의
# 전유 호 2,268개 중 1,979개(87%)가 "기타공장"이었고, 이 때문에 expos_units 세그먼트
# 추정 공실률이 88.5%(앵커 9.99%)까지 부풀었다.
NON_CAPACITY_PURPS = ("아파트", "오피스", "다세대주택", "단독주택",
                      "연립주택", "기숙사", "도시형생활주택", "사무소",
                      "공장", "제조업소", "창고", "주차장", "공공시설")

# 분자에서 제외할 사무실형 업종 대분류 — 분모(상업 층·상가 호)와 도메인 정합.
# 사무실 입주 업종을 세면 점포 수용량 대비 분자가 부풀어 공실이 과소추정된다
# (2026-07-19 정합 교정: 미필터 시 집계 공실률 5.7% vs 부동산원 41.6%).
NON_STOREFRONT_LCLS = ("과학·기술", "부동산", "시설관리·임대")
STORES_PER_FLOOR = 2          # 일반건물 근사: 층당 상가 호 수 (α보정 §3 대상)
_SLEEP = 0.05                 # API 예의 지연


# 연속 실패 카운터는 **엔드포인트별**이다. 전역 하나로 두면 서로 다른 엔드포인트가
# 카운터를 덮어써 중단 장치가 무력화된다 — 2026-07-26 을지로에서 실제로 발생했다:
# 전유부가 429 로 죽어 _FAILS=1 이 되면 곧이어 표제부 호출이 성공해 0 으로 리셋되고,
# 이 왕복이 무한 반복돼 "실패 1연속" 이 15 에 영원히 도달하지 못했다. 그 결과 전유부가
# 완전히 막힌 채로 건물당 27초(백오프)를 태우며 31시간짜리 스톨이 됐다.
_FAILS: dict[str, int] = defaultdict(int)
_ABORT_AFTER = 15          # 한 엔드포인트가 이만큼 연속 실패하면 거점 수집을 중단
_DEAD_AFTER = 5            # 429 로 이만큼 연속 소진되면 그 엔드포인트를 세션 내 포기
_DEAD: set[str] = set()    # 포기한 엔드포인트 — 이후 호출은 즉시 None (대기 없음)


def _ep(url: str) -> str:
    return url.rsplit("/", 1)[-1]


_RETRIES = 4           # 연결·DNS 오류 재시도 횟수 (이 환경은 DNS getaddrinfo 가 간헐 실패)
_BACKOFF = (1, 3, 8, 15)   # 재시도 간 대기(초) — 일시적 DNS 블립을 넘긴다

# 429(레이트 리밋)는 DNS 블립과 성격이 다르다. 블립은 27초면 지나가지만 리밋은
# 계속 두드릴수록 조여진다. 2026-07-26 을지로 수집 중 getBrExposPubuseAreaInfo 에서
# 429 가 발생, _BACKOFF 를 다 쓰고도 실패해 해당 건물이 조용히 no_ledger 로 강등됐다.
# → 429 전용 백오프 + Retry-After 존중 + 전역 감속(_PACE)으로 분리 대응한다.
#
# 재시도를 2회로 줄인 이유: 엔드포인트가 **하드 블록**(일일 쿼터 소진)된 경우 긴 백오프는
# 순손실이다. 을지로 실측에서 건물당 27초를 태우며 시간당 120동밖에 못 나갔다.
# 짧게 두 번만 시도하고, _DEAD_AFTER 회 연속이면 엔드포인트 자체를 포기하는 쪽이 빠르다.
# (일시적 리밋이면 _PACE 감속으로 회복되고, 하드 블록이면 몇 분 안에 포기한다.)
_RETRIES_429 = 2
_BACKOFF_429 = (5, 20)
_PACE = [0.0]          # 429 누적 시 매 요청 앞에 붙는 전역 지연(초). 성공하면 서서히 회복
_PACE_STEP = 0.25      # 429 1회당 가산
_PACE_MAX = 3.0
_PACE_DECAY = 0.01     # 성공 1회당 감산
_N429 = [0]            # 429 총 발생 수 (리포트용)
_LAST_429 = [False]    # 직전 _get_json 실패가 429 때문이었나 (강등 사유 구분용)


def _resp_of(exc: Exception):
    return getattr(exc, "response", None)


def _is_429(exc: Exception) -> bool:
    r = _resp_of(exc)
    return r is not None and getattr(r, "status_code", None) == 429


def _retry_after(exc: Exception) -> float | None:
    """429 응답의 Retry-After(초) — 없거나 파싱 실패면 None."""
    r = _resp_of(exc)
    if r is None:
        return None
    try:
        return max(0.0, float(r.headers.get("Retry-After", "")))
    except (TypeError, ValueError):
        return None


def _get_json(url: str, params: dict) -> dict | None:
    """건축HUB GET. 연결/DNS 일시 오류는 백오프 재시도(_FAILS 미가산),
    재시도 소진 시에만 실패로 집계 — DNS 블립에 배치 전체가 죽지 않게 한다.

    429 는 별도 처리: Retry-After 를 우선 존중하고, 없으면 _BACKOFF_429 로 쉰다.
    동시에 _PACE 를 올려 이후 모든 요청을 전역 감속시킨다(리밋 재유발 방지).
    실패로 끝나면 _LAST_429 를 세워 호출부가 '대장 없음'과 구분할 수 있게 한다.

    같은 엔드포인트가 429 로 _DEAD_AFTER 회 연속 소진되면 그 엔드포인트를 포기하고
    이후 호출은 **대기 없이 즉시** None 을 돌려준다. 막힌 문을 계속 두드리며 백오프에
    시간을 태우지 않기 위해서다.
    """
    ep = _ep(url)
    if ep in _DEAD:
        _LAST_429[0] = True          # 사유는 여전히 레이트 리밋 → rate_limited 로 기록
        return None

    last = None
    saw_429 = False
    for attempt in range(_RETRIES + 1):
        try:
            if _PACE[0]:
                time.sleep(_PACE[0])
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            _FAILS[ep] = 0
            _LAST_429[0] = False
            if _PACE[0]:                      # 성공 누적 시 감속 해제
                _PACE[0] = max(0.0, _PACE[0] - _PACE_DECAY)
            return data
        except Exception as exc:
            last = exc
            if _is_429(exc):
                saw_429 = True
                _N429[0] += 1
                _PACE[0] = min(_PACE[0] + _PACE_STEP, _PACE_MAX)
                wait = _retry_after(exc)
                if wait is None:
                    wait = _BACKOFF_429[min(attempt, len(_BACKOFF_429) - 1)]
                limit = _RETRIES_429          # 429 는 짧게 끊는다
            else:
                wait = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                limit = _RETRIES
            if attempt >= limit:
                break
            time.sleep(wait)

    _FAILS[ep] += 1
    _LAST_429[0] = saw_429
    tag = f"429 x{_N429[0]} · pace {_PACE[0]:.2f}s" if saw_429 else "연결/기타"
    print(f"  [HTTP 실패 {_FAILS[ep]}연속 | {tag}] {ep} — {last}")
    if saw_429 and _FAILS[ep] >= _DEAD_AFTER:
        _DEAD.add(ep)
        print(f"  ⚠ [{ep}] 429 로 {_FAILS[ep]}회 연속 소진 — 이 엔드포인트를 "
              f"이번 실행에서 포기합니다(이후 호출은 즉시 rate_limited).")
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


# 건물당 전유부 페이지 상한(100행/페이지). 대형 집합건물은 전유 호가 수천 개라
# 기존 8페이지(800호)로는 원본이 잘렸다 — 2026-07-26 실측: 8거점 6,539동 중 49동이
# 절단, 최대 7,881호(seoulsup). 절단되면 capacity 가 과소집계되고 재계산으로도
# 복구되지 않아(원본 자체가 없음) 재수집이 필요하다. 80페이지=8,000호로 올린다.
# 페이징은 totalCount 까지만 돌므로 일반 건물(대부분 1페이지)의 콜 수는 늘지 않는다.
_MAX_EXPOS_PAGES = 80


def expos_units(rows: list[dict]) -> set[tuple[str, str, str]]:
    """전유부 응답 → 상업 전유 호 집합 (동/호/층 튜플).

    bronze 의 bldg_ledger_raw.json 원본만으로 capacity 를 재산출할 수 있도록
    필터를 함수로 분리한다(recalc_capacity 파이프라인이 같은 로직을 재사용).
    """
    return {
        (r.get("dongNm", ""), r.get("hoNm", ""), r.get("flrNoNm", ""))
        for r in rows
        if r.get("exposPubuseGbCdNm") == "전유"
        and not any(p in str(r.get("mainPurpsCdNm", "")) for p in NON_CAPACITY_PURPS)
    }


def fetch_capacity(key: str, jibun: dict, raw_store: dict) -> tuple[int | None, str]:
    """(capacity, method). 전유부 상업 호 수 → 없으면 표제부 층수 근사.

    429 로 응답을 못 받은 경우 "rate_limited" 를 돌려준다. 예전에는 이때 "no_ledger"
    로 떨어져 **대장이 원래 없는 건물과 구분이 불가능**했고, 재개 로직이 완료로
    간주해 영영 재시도되지 않았다(2026-07-26 을지로에서 확인).
    전유부만 리밋에 걸리고 표제부는 성공하는 경우도 위험하다 — 실제로는 집합건물인데
    floor_approx 로 강등돼 capacity 가 뒤바뀌므로, 이 경우도 재수집 대상으로 돌린다.
    """
    common = {"serviceKey": key, "_type": "json", "numOfRows": 100, **jibun}

    # 전유공용면적 — 서버가 페이지당 100행 반환 → totalCount 까지 페이징
    rows: list[dict] = []
    page, total = 1, None
    throttled = False
    while page <= _MAX_EXPOS_PAGES:
        expos = _get_json(f"{BASE_BLD}/getBrExposPubuseAreaInfo", {**common, "pageNo": page})
        if expos is None and _LAST_429[0]:
            throttled = True
        got = _items(expos)
        rows += got
        total = int(_body(expos).get("totalCount") or 0)
        if not got or len(rows) >= total:
            break
        page += 1
        time.sleep(_SLEEP)
    raw_store["expos"] = rows
    raw_store["expos_total"] = total

    # 상업 전유 호만 capacity 로 카운트 — 오피스텔·주택 호는 제외 (§1-2).
    # 전유부는 세부용도명이므로 NON_CAPACITY_PURPS negative 필터를 쓴다(위 주석 참조).
    units = expos_units(rows)
    if units:
        return len(units), "expos_units"
    if throttled:
        return None, "rate_limited"      # 전유부 유실 — 표제부 폴백은 오판 위험

    time.sleep(_SLEEP)
    title = _get_json(f"{BASE_BLD}/getBrTitleInfo", common)
    if title is None and _LAST_429[0]:
        return None, "rate_limited"
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

# 재개 시 '완료'로 치지 않고 다시 시도할 capacity_method — 수집 실패이지 사실이 아니다.
_RETRY_METHODS = {"rate_limited"}


def _ts() -> str:
    """진행 로그용 시각.

    배치는 로그를 append 만 하고 시각을 남기지 않았다. 그래서 2026-07-27 에 "어제보다
    왜 느린가"를 따지는 데 파일 mtime 과 Windows 이벤트 로그(Kernel-Power 506/507)로
    구간을 역산해야 했고, 절전으로 멈춘 146분을 실제 작업 시간으로 착각해 ETA 를 8배
    틀리게 냈다. 체크포인트에 시각을 박으면 그 역산이 통째로 필요 없어진다.
    """
    return time.strftime("%H:%M:%S")


def _save_ledger(slug: str, results: list[dict], ledger_raw: dict[str, dict]) -> None:
    """대장 결과 부분/최종 저장 — bronze(원본) + gold(building_vacancy).

    429 강등분은 gold/{slug}/rate_limited.json 에 따로 남긴다. building_vacancy.json
    안에서도 capacity_method 로 식별되지만, 재수집 대상을 눈으로 찾을 수 있어야 한다.
    """
    save_json(ledger_raw, slug, "bldg_ledger_raw.json")
    gold_dir = GOLD / slug
    gold_dir.mkdir(parents=True, exist_ok=True)
    (gold_dir / "building_vacancy.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    limited = [{"bdMgtSn": r.get("bdMgtSn"), "lnoCd": r.get("lnoCd"),
                "name": r.get("name"), "active": r.get("active")}
               for r in results if r.get("capacity_method") in _RETRY_METHODS]
    dst = gold_dir / "rate_limited.json"
    if limited:
        dst.write_text(json.dumps(
            {"slug": slug, "count": len(limited), "n429": _N429[0],
             "note": "429로 대장을 못 받은 건물. 다음 building_vacancy 실행이 자동 재시도한다.",
             "buildings": limited}, ensure_ascii=False, indent=2), encoding="utf-8")
    elif dst.exists():
        dst.unlink()          # 모두 복구됐으면 흔적을 남기지 않는다


def run_hub(key: str, hub: PageHub, do_ledger: bool = True,
            refresh_stores: bool = False) -> bool:
    """거점 하나 수집. do_ledger=False 면 점포만(Tier 2).

    재개 가능: 대장 루프는 _CHECKPOINT 동마다 저장하고, 재실행 시 기존
    building_vacancy.json 의 완료 건물(bdMgtSn)을 건너뛴다. 중단(쿼터 소진·강제
    종료)돼도 진행분이 남아 다음 실행이 나머지만 채운다. refresh_stores=False 면
    기존 stores_raw 를 재사용해 점포 재수집을 생략한다(재개 효율).
    반환: 성공 여부.
    """
    _FAILS.clear()          # 거점마다 실패 카운터 초기화 (_DEAD 는 실행 전체에서 유지)
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
                # rate_limited 는 '완료'가 아니라 '429로 못 받은 것' — 재개 시 다시 시도해야
                # 하므로 기존 행을 버리고 done 에서도 뺀다(안 그러면 영영 재수집 안 됨).
                retry = sum(1 for r in prev if r.get("capacity_method") in _RETRY_METHODS)
                results = [r for r in prev if r.get("capacity_method") not in _RETRY_METHODS]
                done = {r.get("bdMgtSn") for r in results if r.get("bdMgtSn")}
                if retry:
                    print(f"[bldg-vac:{slug}] 이전 실행의 429 강등 {retry}동 — 재수집 대상에 포함")
        except (json.JSONDecodeError, OSError):
            pass
    ledger_raw: dict[str, dict] = (load_latest(slug, "bldg_ledger_raw.json") or {}) if done else {}

    todo = [b for b in targets if b["bdMgtSn"] not in done]
    print(f"[{_ts()}] [bldg-vac:{slug}] 대장 대상 {len(todo)}동 "
          f"(전체 {len(targets)} · 기존완료 {len(done)})")

    since = 0
    for b in todo:
        # 대장 산출에 필수인 전유부가 포기 상태면 더 돌 이유가 없다 — 남은 건물이
        # 전부 rate_limited 로 채워질 뿐이다. 즉시 중단하고 다음 실행에 넘긴다.
        if EP_EXPOS in _DEAD:
            print(f"[bldg-vac:{slug}] ⚠ {EP_EXPOS} 쿼터 소진 — "
                  f"{len(results)}동까지 저장 후 중단(쿼터 리셋 후 재실행하면 재개)")
            break
        worst = max(_FAILS.values(), default=0)
        if worst >= _ABORT_AFTER:
            ep = max(_FAILS, key=_FAILS.get)
            print(f"[bldg-vac:{slug}] ⚠ {ep} 연속 실패 {worst}회 — "
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
            print(f"[{_ts()}] [checkpoint:{slug}] {len(results)}/{len(targets)}동 저장")
            since = 0

    _save_ledger(slug, results, ledger_raw)

    st = Counter(r["status"] for r in results)
    cm = Counter(r["capacity_method"] for r in results)
    print(f"[{_ts()}] [gold:{slug}] building_vacancy.json ({len(results)}동)")
    print(f"[bldg-vac:{slug}] status 분포: {dict(st)}")
    print(f"[bldg-vac:{slug}] capacity 방식: {dict(cm)}")
    if _N429[0] or cm.get("rate_limited"):
        print(f"[bldg-vac:{slug}] ⚠ 429 {_N429[0]}회 · 강등 {cm.get('rate_limited', 0)}동"
              f" · 현재 감속 {_PACE[0]:.2f}s — 재실행하면 강등분만 자동 재수집")
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
