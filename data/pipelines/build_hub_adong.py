"""[Page] 거점 ↔ 행정동 매핑 사이드카 (silver/hub_adong.json).

## 왜 필요한가

생활이동(수도권 생활이동)·생활인구는 **행정동** 단위다. 우리 Page 는 건물 단위라
그대로는 못 붙는다. 둘을 잇는 표가 저장소에 없다 — `config/garosugil.py` 에
신사동 행정동코드가 **한 줄 하드코딩**돼 있는 것이 전부고, 그나마 "자릿수 재확인"
주석이 달려 있다. 54거점으로 늘어난 지금 그 방식은 못 쓴다.

## 왜 법정동→행정동 변환표가 아니라 좌표 역지오코딩인가

`stores_raw.lnoAdr` 에서 뽑히는 것은 **법정동**이고(seoul_licensing._hub_pairs 가 그렇게
쓴다), 생활이동은 **행정동**이다. 둘은 1:1 이 아니다 — 신사동(법정) 하나가 행정동
여러 개에 걸리기도 하고 반대도 있다. 변환표를 따로 들이면 그 표가 또 낡는다.
건물 좌표는 이미 우리 손에 있으므로(`page_building_master.geojson`) **카카오
coord2regioncode 로 좌표에서 직접 행정동을 받는다.** 같은 좌표에서 법정동도 같이
돌려주므로 기존 법정동 기반 코드와의 대조도 공짜로 된다.

## 가중치를 함께 낸다

한 거점이 행정동 여러 개에 걸치는 것이 정상이다(가로수길은 신사동 하나가 아니다).
생활이동 값을 거점에 얹으려면 **거점이 그 행정동을 얼마나 차지하는가**가 필요하다.
건물 수가 아니라 **상업 연면적**(`silver/{slug}/building_attrs.com_area_flr`)으로
가중한다 — 사람이 모이는 곳은 건물 개수가 아니라 상업 바닥면적을 따라간다.
`build_page_footfall` 이 상권 값을 셀에 얹을 때와 같은 철학이고, 면적 가중은
2026-08-23 분모 정정(고시원·독서실 제외)이 반영된 값을 그대로 탄다.

## 호출 절약

좌표를 **약 100m 격자로 뭉쳐서** 중복 호출을 없앤다. 한 지번의 건물 여럿이 같은
행정동인 것은 자명한데 그걸 매번 묻는 것은 쿼터 낭비다(22,000동 → 격자 수천 개).

실행:
  python -m data.pipelines.build_hub_adong            # 전 거점
  python -m data.pipelines.build_hub_adong nokdu      # 일부만
  python -m data.pipelines.build_hub_adong --force    # 캐시 무시하고 다시 묻는다
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import GOLD, SILVER, load_env
from data.config.page_hubs import ACTIVE_HUBS, ALL_HUBS
from data.pipelines.build_building_attrs import load as load_attrs

_URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
_SLEEP_S = 0.03
_RETRIES = 5

# 좌표 뭉치기 격자. 위도 0.001° ≈ 111m, 경도 0.001° ≈ 88m(서울 위도) — 행정동
# 경계를 가로지를 만큼 크지 않으면서 호출을 한 자릿수로 줄인다.
_GRID = 0.001

_OUT = SILVER / "hub_adong.json"
_CACHE = SILVER / "coord_adong_cache.json"


def _cell(lon: float, lat: float) -> str:
    """좌표 → 격자 키. 같은 셀이면 같은 행정동으로 본다."""
    return f"{round(lon / _GRID):d}_{round(lat / _GRID):d}"


def _centroid(geom: dict) -> tuple[float, float] | None:
    """폴리곤/포인트에서 대표 좌표 하나. 정밀도가 아니라 소속 판정용이라 평균이면 족하다."""
    def _walk(c):
        if not isinstance(c, list):
            return
        if c and isinstance(c[0], (int, float)) and len(c) >= 2:
            yield float(c[0]), float(c[1])
            return
        for x in c:
            yield from _walk(x)

    pts = list(_walk((geom or {}).get("coordinates")))
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _lookup(key: str, lon: float, lat: float) -> dict | None:
    """coord2regioncode — 행정동(H)·법정동(B)을 함께 돌려준다."""
    if requests is None:
        return None
    headers = {"Authorization": f"KakaoAK {key}"}
    for attempt in range(_RETRIES):
        try:
            r = requests.get(_URL, params={"x": lon, "y": lat},
                             headers=headers, timeout=15)
            if r.status_code == 429:
                time.sleep(min(2 ** attempt, 10))
                continue
            r.raise_for_status()
            docs = r.json().get("documents") or []
        except Exception:
            time.sleep(min(2 ** attempt, 10))
            continue
        out: dict = {}
        for d in docs:
            if d.get("region_type") == "H":
                out["adm_cd"] = d.get("code")
                out["adm_nm"] = d.get("region_3depth_name")
                out["gu"] = d.get("region_2depth_name")
            elif d.get("region_type") == "B":
                out["bjd_cd"] = d.get("code")
                out["bjd_nm"] = d.get("region_3depth_name")
        return out or None
    return None


def run(slugs: list[str], force: bool = False) -> dict:
    key = os.getenv("KAKAO_REST_API_KEY")
    if not key:
        print("[hub-adong] KAKAO_REST_API_KEY 미설정 — 중단")
        return {}

    cache: dict[str, dict] = {}
    if _CACHE.exists() and not force:
        try:
            cache = json.loads(_CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
    print(f"[hub-adong] 좌표 캐시 {len(cache)}셀")

    out: dict[str, dict] = {}
    calls = 0
    for slug in slugs:
        master = GOLD / slug / "page_building_master.geojson"
        if not master.exists():
            print(f"[hub-adong:{slug}] page_building_master.geojson 없음 — 건너뜀")
            continue
        feats = json.loads(master.read_text(encoding="utf-8")).get("features") or []
        attrs = load_attrs(slug)

        # 행정동별 누적: 건물 수 + 상업 연면적(가중치의 본체)
        acc: dict[str, dict] = defaultdict(
            lambda: {"adm_nm": None, "gu": None, "buildings": 0, "com_area_m2": 0.0})
        missed = 0
        for f in feats:
            p = f.get("properties") or {}
            c = _centroid(f.get("geometry") or {})
            if c is None:
                missed += 1
                continue
            lon, lat = c
            ck = _cell(lon, lat)
            reg = cache.get(ck)
            if reg is None:
                reg = _lookup(key, lon, lat)
                calls += 1
                time.sleep(_SLEEP_S)
                if reg is None:
                    missed += 1
                    continue
                cache[ck] = reg
                if calls % 200 == 0:
                    _CACHE.parent.mkdir(parents=True, exist_ok=True)
                    _CACHE.write_text(json.dumps(cache, ensure_ascii=False),
                                      encoding="utf-8")
                    print(f"[hub-adong] {calls}콜 — 캐시 부분 저장")
            cd = reg.get("adm_cd")
            if not cd:
                missed += 1
                continue
            a = acc[cd]
            a["adm_nm"] = a["adm_nm"] or reg.get("adm_nm")
            a["gu"] = a["gu"] or reg.get("gu")
            a["buildings"] += 1
            at = attrs.get(p.get("pnu") or "") or {}
            a["com_area_m2"] += float(at.get("com_area_flr") or 0)

        tot_area = sum(v["com_area_m2"] for v in acc.values())
        tot_bld = sum(v["buildings"] for v in acc.values())
        for v in acc.values():
            # 면적이 한 톨도 없으면(대장 미수집 거점) 건물 수로 물러선다. 조용히 0 을
            # 주면 그 행정동이 지도에서 사라지므로 근거를 바꿔서라도 값을 남긴다.
            v["weight"] = round(v["com_area_m2"] / tot_area, 6) if tot_area > 0 else (
                round(v["buildings"] / tot_bld, 6) if tot_bld else 0.0)
            v["weight_basis"] = "com_area_flr" if tot_area > 0 else "buildings"
            v["com_area_m2"] = round(v["com_area_m2"], 1)
        out[slug] = dict(sorted(acc.items(), key=lambda kv: -kv[1]["weight"]))
        top = list(out[slug].items())[:3]
        print(f"[hub-adong:{slug}] 행정동 {len(acc)}개 · 좌표미상 {missed}동 · "
              + " · ".join(f"{v['adm_nm']}({v['weight']:.0%})" for _, v in top))

    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    doc = {
        "source": "카카오 로컬 coord2regioncode — 건물 좌표 → 행정동(H)",
        "weight": ("거점이 그 행정동을 차지하는 비중. 기준은 상업 연면적"
                   "(silver/building_attrs.com_area_flr)이며, 대장 미수집 거점만 건물 수로 물러선다."),
        "grid_deg": _GRID,
        "hubs": out,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[hub-adong] 완료: {len(out)}거점 · 신규 {calls}콜 → "
          f"{_OUT.relative_to(SILVER.parent)}")
    return out


def load() -> dict[str, dict]:
    """소비처용 로더 — {slug: {adm_cd: {...weight}}}. 없으면 빈 dict."""
    if not _OUT.exists():
        return {}
    return (json.loads(_OUT.read_text(encoding="utf-8")).get("hubs") or {})


def main() -> None:
    load_env()
    argv = sys.argv[1:]
    slugs = [a for a in argv if not a.startswith("-")] or list(ACTIVE_HUBS)
    run([s for s in slugs if s in ALL_HUBS], force="--force" in argv)


if __name__ == "__main__":
    main()
