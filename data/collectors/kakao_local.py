"""[B단계·Program/Posting] 카카오 로컬 수집기 — 장소·카테고리 크로스체크 (docs §8-E).

`KAKAO_REST_API_KEY`(developers.kakao.com 즉시발급)로 거점 반경의 현존 점포를
카테고리별로 수집한다. 용도: 상가정보 API(§1-A)의 폐업 반영 지연 보완 + 업종
카테고리·place_url(리뷰 크롤링 시드) 확보.

⚠️ 카카오 로컬은 쿼리당 최대 45건(15건×3페이지)만 노출한다. 다만 응답 meta.total_count
는 상한과 무관하게 실제 총계를 알려주므로(강남역 음식점 600m = 925건, pageable_count 는
45), 이 값을 보고 45건 아래로 떨어질 때까지 원을 재귀 분할해 전수에 가깝게 모은다.
2026-07-23 분할 수집 도입 — 27거점 실측 총계 23,850건(분할 전 노출은 5,646건).

실행: python -m data.collectors.kakao_local
      python -m data.collectors.kakao_local --platform13          # 27거점 분할 수집
      python -m data.collectors.kakao_local --platform13 --no-split  # 구 동작(45건 상한)
"""
from __future__ import annotations

import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import load_env, save_json
from data.config.garosugil import CX, CY, RADIUS_M, SLUG

_URL = "https://dapi.kakao.com/v2/local/search/category.json"

# 노출 상한: size 15 × 3페이지. total_count 가 이 값을 넘으면 분할한다.
_PAGE_SIZE = 15
_MAX_PAGE = 3
_CAP = _PAGE_SIZE * _MAX_PAGE

# 분할 파라미터
_SPLIT_TARGET = 25    # 자식 셀 1개가 노려야 할 건수 — 분할 계수 n 산정 기준(상한 45에 여유)
_MAX_SPLIT = 4        # 한 단계 최대 n×n (n=4 → 16분할). 과분할은 요청 수만 늘린다
_MAX_DEPTH = 4        # 재귀 상한 — 초과 시 잔여 건수를 residual 로 보고
_MIN_RADIUS_M = 40    # 이보다 작게 쪼개지 않는다(건물 단위, 좌표 오차와 구분 불가)
_SLEEP_S = 0.05       # 공공 API 예의상 호출 간격
# 일시 네트워크 오류 재시도 — DNS 장애(getaddrinfo)가 수십 초 지속될 수 있어
# 짧은 백오프는 못 버틴다(2026-07-24 재수집 중 DNS 장애로 다수 거점 과소수집).
# 8회 × 상한 15s ≈ 요청당 최대 ~90초까지 버틴다.
_RETRIES = 8
_MAX_BACKOFF_S = 15.0
_WORKERS = 8          # 거점 병렬 수집 스레드 수(카카오 일 쿼터 10만/앱 대비 여유)

# TLS 핸드셰이크 재수립이 요청 지연의 83%(673ms→115ms, 2026-07-23 측정)라 커넥션을
# 재사용한다. requests.Session 은 스레드 안전하지 않으므로 스레드마다 하나씩 둔다.
_local = threading.local()


def _session(key: str) -> "requests.Session":
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"Authorization": f"KakaoAK {key}"})
        _local.session = s
    return s

_M_PER_DEG_LAT = 111000.0


def _m_per_deg_lon(lat: float) -> float:
    return 111320.0 * math.cos(math.radians(lat))

# 상권 분석에 쓰는 카테고리 그룹 코드
CATEGORY_GROUPS: dict[str, str] = {
    "FD6": "음식점",
    "CE7": "카페",
    "CS2": "편의점",
    "HP8": "병원",
    "PM9": "약국",
    "AD5": "숙박",
    "CT1": "문화시설",
}


def _page(key: str, group: str, cx: float, cy: float, radius: int, page: int) -> dict:
    """카테고리 검색 1페이지. 응답 body(documents + meta) 를 그대로 반환.

    27거점 분할 수집은 수천 요청·수십 분짜리라 일시 오류(SSLEOFError·타임아웃)를
    반드시 재시도한다. 재시도가 없으면 예외가 호출부까지 올라가 그 거점의 카테고리
    하나가 통째로 비어버린다(2026-07-23 hongdae 음식점 유실).
    """
    last: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            resp = _session(key).get(
                _URL,
                params={
                    "category_group_code": group, "x": cx, "y": cy, "radius": radius,
                    "page": page, "size": _PAGE_SIZE, "sort": "distance",
                },
                timeout=15,
            )
            if resp.status_code == 429:  # 쿼터 초과 — 길게 쉬고 재시도
                time.sleep(2.0 * (attempt + 1))
                last = RuntimeError("429 Too Many Requests")
                continue
            resp.raise_for_status()
            time.sleep(_SLEEP_S)
            return resp.json()
        except Exception as exc:  # noqa: BLE001 — 네트워크 예외 전반을 재시도 대상으로
            last = exc
            time.sleep(min(0.5 * 2 ** attempt, _MAX_BACKOFF_S))  # 0.5→1→2→…→상한
    raise RuntimeError(f"{_RETRIES}회 재시도 실패: {last}")


def _search_category(key: str, group: str, cx: float | None = None, cy: float | None = None,
                     radius: int | None = None) -> list[dict]:
    """카테고리 1개를 페이징 수집 (최대 45건 제한). 좌표 미지정 시 가로수길 기본.

    분할 없이 노출 상한까지만 — 구 동작 유지용(--no-split).
    """
    cx = cx if cx is not None else CX
    cy = cy if cy is not None else CY
    radius = radius if radius is not None else RADIUS_M
    docs: list[dict] = []
    for page in range(1, _MAX_PAGE + 1):
        body = _page(key, group, cx, cy, radius, page)
        docs.extend(body.get("documents", []))
        if body.get("meta", {}).get("is_end", True):
            break
    return docs


def _collect_circle(key: str, group: str, cx: float, cy: float, radius: int,
                    out: dict[str, dict], stats: dict[str, int], depth: int = 0,
                    bounds: tuple[float, float, int] | None = None) -> None:
    """원 1개를 수집하되 total_count 가 노출 상한을 넘으면 n×n 으로 재귀 분할한다.

    1페이지 응답이 total_count 와 첫 15건을 동시에 주므로 별도 탐침 요청은 쓰지 않는다
    (분할로 버려지는 페이지가 없도록 첫 15건도 그대로 out 에 담는다).
    자식 원들은 부모의 bbox(한 변 2R)를 덮으므로 부모 원 밖까지 걸린다. bounds=(위도,
    경도, 반경)를 주면 그 원과 아예 겹치지 않는 자식은 건너뛴다 — 거점 밖 밀집지
    (예: 가로수길 반경 밖 압구정 병원)로 재귀가 새는 낭비를 막는다. 경계에 걸친 자식은
    남기고, 최종 반경 필터는 호출부에서 좌표 기준으로 한 번에 적용한다.
    """
    if bounds is not None:
        b_lat, b_lng, b_r = bounds
        if _dist_m(cy, cx, b_lat, b_lng) > b_r + radius:
            return  # 자식 원 전체가 거점 반경 밖 — 수집해도 어차피 버려진다
    body = _page(key, group, cx, cy, radius, 1)
    stats["req"] += 1
    meta = body.get("meta", {})
    total = int(meta.get("total_count", 0))
    for d in body.get("documents", []):
        out.setdefault(d.get("id", d.get("place_url", "")), d)
    if total == 0:
        return

    if total > _CAP and depth < _MAX_DEPTH and radius > _MIN_RADIUS_M:
        # 자식 1개가 _SPLIT_TARGET 건이 되도록 n 을 고른다(면적비 → sqrt).
        n = min(_MAX_SPLIT, max(2, math.ceil(math.sqrt(total / _SPLIT_TARGET))))
        # 부모 bbox 를 n×n 정사각으로 쪼개고 각 칸의 외접원(반지름 = 한 변 × √2/2)으로 덮는다
        side = 2.0 * radius / n
        child_r = max(_MIN_RADIUS_M, math.ceil(side * math.sqrt(2) / 2))
        for i in range(n):
            for j in range(n):
                ox = side * (i + 0.5) - radius
                oy = side * (j + 0.5) - radius
                _collect_circle(key, group,
                                cx + ox / _m_per_deg_lon(cy), cy + oy / _M_PER_DEG_LAT,
                                child_r, out, stats, depth + 1, bounds)
        return

    # 잎 노드 — 남은 페이지까지 훑는다
    page = 2
    while not meta.get("is_end", True) and page <= _MAX_PAGE:
        body = _page(key, group, cx, cy, radius, page)
        stats["req"] += 1
        meta = body.get("meta", {})
        for d in body.get("documents", []):
            out.setdefault(d.get("id", d.get("place_url", "")), d)
        page += 1
    if total > _CAP:
        # 더 못 쪼갠 채 상한에 걸린 잔여 — 0 이 아니면 _MAX_DEPTH/_MIN_RADIUS_M 재검토
        stats["residual"] += total - _CAP


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat1 - lat2) * _M_PER_DEG_LAT
    dx = (lon1 - lon2) * _m_per_deg_lon(lat1)
    return math.sqrt(dx * dx + dy * dy)


def collect() -> list[dict]:
    """카테고리별 반경 수집 → 중복(장소 id) 제거 → Bronze 저장."""
    key = os.getenv("KAKAO_REST_API_KEY")
    if not key or requests is None:
        print("[kakao_local] KAKAO_REST_API_KEY 미설정(또는 requests 없음) — 건너뜀")
        return []

    seen: dict[str, dict] = {}
    for group, label in CATEGORY_GROUPS.items():
        try:
            docs = _search_category(key, group)
        except Exception as exc:
            print(f"  {group}({label}): 실패 — {exc}")
            continue
        capped = " ★45건 상한 — 분할 필요" if len(docs) >= 45 else ""
        print(f"  {group}({label}): {len(docs)}건{capped}")
        for d in docs:
            seen[d.get("id", d.get("place_url", ""))] = d

    places = list(seen.values())
    save_json(places, SLUG, "kakao_places.json")
    return places


def _collect_district(key: str, did: str, lat: float, lng: float, radius: int,
                      split: bool) -> dict:
    """거점 1개를 수집(카테고리 전부) → 반경 필터까지 적용한 {pid: place} 반환.

    거점 병렬 실행의 작업 단위. district_id 는 여기서 부가한다. 스레드에서 도므로
    print 대신 결과 dict 로만 소통하고(로그는 병합하는 메인 스레드가 순서대로 찍는다),
    거점 간 중복 판정도 메인에서 결정적으로 처리한다.
    """
    found: dict[str, dict] = {}
    stats = {"req": 0, "residual": 0}
    capped: list[str] = []
    failed: list[str] = []
    for group, label in CATEGORY_GROUPS.items():
        cat: dict[str, dict] = {}
        try:
            if split:
                _collect_circle(key, group, lng, lat, radius, cat, stats,
                                bounds=(lat, lng, radius))
            else:
                for d in _search_category(key, group, cx=lng, cy=lat, radius=radius):
                    cat.setdefault(d.get("id", d.get("place_url", "")), d)
                if len(cat) >= _CAP:
                    capped.append(label)
        except Exception as exc:
            # 재시도까지 소진한 실패 — 그 거점·카테고리가 통째로 빈다. 부분 수집분은
            # 살리되 메인에서 목록으로 다시 알린다(조용한 결측 방지).
            failed.append(f"{did}/{label}: {exc}")
        for pid, d in cat.items():
            # 분할 시 자식 원이 거점 반경 밖까지 덮으므로 여기서 잘라낸다
            try:
                if _dist_m(lat, lng, float(d["y"]), float(d["x"])) > radius:
                    continue
            except (KeyError, TypeError, ValueError):
                pass  # 좌표 파싱 실패는 버리지 않고 통과(하류에서 결측 처리)
            if pid not in found:
                found[pid] = {**d, "district_id": did}
    return {"places": found, "stats": stats, "capped": capped, "failed": failed}


def collect_platform13(split: bool = True, workers: int = _WORKERS) -> list[dict]:
    """[Platform·GNN] 27거점 현존 점포 수집 — GNN 노드 확장(가로수길→27거점)의 원천.

    거점×카테고리 반경 수집, 행마다 district_id 부가.
    split=True(기본)면 total_count 기준 재귀 분할로 45건 상한을 넘어 전수에 가깝게 모은다.
    split=False 면 구 동작(카테고리당 45건) — 빠른 확인용.
    거점을 workers 스레드로 병렬 수집하되, 병합은 DISTRICT_PLACES 순서로 결정적으로
    한다(인접 거점 반경 중복 시 먼저 정의된 거점 소속 유지 — 순차 실행과 동일 결과).
    Bronze: data/bronze/platform13/{날짜}/kakao_places.json
    """
    from data.config.platform_places import DISTRICT_PLACES

    key = os.getenv("KAKAO_REST_API_KEY")
    if not key or requests is None:
        print("[kakao_local] KAKAO_REST_API_KEY 미설정(또는 requests 없음) — 건너뜀")
        return []

    order = list(DISTRICT_PLACES.items())
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {did: ex.submit(_collect_district, key, did, lat, lng, radius, split)
                for did, (lat, lng, radius, _n) in order}

        seen: dict[str, dict] = {}
        tot_req = tot_resid = 0
        failed: list[str] = []
        for did, _v in order:  # 결정적 병합 순서(완료를 기다리되 순서는 정의순)
            res = futs[did].result()
            n_before = len(seen)
            for pid, d in res["places"].items():
                if pid not in seen:  # 먼저 정의된 거점 우선
                    seen[pid] = d
            tot_req += res["stats"]["req"]
            tot_resid += res["stats"]["residual"]
            failed += res["failed"]
            note = f" · 요청 {res['stats']['req']}" if split else ""
            if split and res["stats"]["residual"]:
                note += f" · ⚠ 미수집 추정 {res['stats']['residual']}"
            elif res["capped"]:
                note = f" ★상한: {','.join(res['capped'])}"
            print(f"  {did}: {len(seen) - n_before}건{note}")

    places = list(seen.values())
    if split:
        print(f"[kakao_local] 총 {len(places)}건 · 요청 {tot_req}회 · 미수집 추정 {tot_resid}건")
    if failed:
        print(f"[kakao_local] ⚠ 수집 실패 {len(failed)}건 — {'; '.join(failed)}")
    save_json(places, "platform13", "kakao_places.json")
    return places


if __name__ == "__main__":
    import sys

    load_env()
    if "--platform13" in sys.argv:
        collect_platform13(split="--no-split" not in sys.argv)
    else:
        collect()
