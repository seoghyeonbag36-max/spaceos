"""카카오 현존 점포 크로스체크 — 로드뷰 표본 라벨링 보조 근거 (검증 전용).

상가정보(분자) 기반 예측과 카카오 로컬 현존 점포를 대조해 roadview_sample.csv 에
참고 열을 추가한다:

  kakao_pip    건물 폴리곤 안(point-in-polygon)의 카카오 장소 **수**
  kakao_30m    폴리곤 중심 30m 내 장소 **수** (좌표 오차 폴백)
  crosscheck   예측 empty/high 인데 폴리곤 안에 현존 장소가 있으면 "상충(n)" 표시

## ⚠ 2026-09-15 — 장소를 저장하지 않는다

두 가지가 바뀌었다. 카카오 로컬은 응답 결과의 저장을 허용하지 않기 때문이다
(→ `docs/finding-map-provider-google-2026-09-15.md` §7-2):

  ① 소스가 **실시간 호출**이다. 종전에는 `bronze/{거점}/kakao_places.json` 을 읽었는데
     그 Bronze 자체를 없앴다(`data/collectors/kakao_local` 머리말).
  ② `kakao_names` 열을 **폐지했다.** 상호는 카카오 응답 내용이라 CSV(=저장)에 남길 수
     없다. 남는 것은 건수와 상충 표시 — 우리 예측에 대한 판정이라 저장해도 되는 것이다.
     이름이 필요하면 그 자리에서 콘솔로 보고 쓰되 기록하지 않는다(`--show-names`).

⚠️ 카카오 로컬은 쿼리당 45건 상한으로 커버리지가 불완전하다 — "카카오에 없음"은
폐업의 근거가 아니다. 이 열은 라벨링 참고·불일치 우선 확인용이며, 분자(active)
자체를 수정하지 않는다 (분자 정제는 인허가 이력 API 확보 후 Silver 단계 TODO).

실행: python -m data.validation.crosscheck_kakao
      python -m data.validation.crosscheck_kakao --show-names   # 콘솔에만 상호 표시
      (라벨 기입 전후 무관 — label_actual/memo 열은 보존한다)
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from data.collectors.common import GOLD
from data.config.garosugil import SLUG

_OUT = Path(__file__).resolve().parent
_CSV = _OUT / "roadview_sample.csv"
_NEAR_M = 30.0
_ADDED = ("kakao_pip", "kakao_30m", "crosscheck")
# 폐지된 열 — 과거 실행이 남긴 값을 재기록하지 않고 걷어낸다(약관: 상호 저장 금지).
_DROPPED = ("kakao_names",)


def _rings(geom: dict) -> list[list[list[float]]]:
    """Polygon/MultiPolygon 의 외곽 링 목록 (내부 구멍은 footprint 판정에 무시)."""
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


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """equirectangular 근사 (수백 m 스케일에서 충분)."""
    kx = 111320.0 * math.cos(math.radians(lat1))
    return math.hypot((lon2 - lon1) * kx, (lat2 - lat1) * 110540.0)


def run(show_names: bool = False) -> None:
    rows = list(csv.DictReader(_CSV.open(encoding="utf-8-sig")))
    if not rows:
        print("[crosscheck] roadview_sample.csv 비어 있음 — make_roadview_sample 먼저")
        return

    master = json.loads((GOLD / SLUG / "page_building_master.geojson").read_text(encoding="utf-8"))
    feats = {f["properties"]["id"]: f for f in master["features"]}

    # 실시간 호출 — 응답은 이 프로세스 안에서만 산다(파일로 내리지 않는다).
    from data.collectors.common import load_env
    from data.collectors.kakao_local import collect

    load_env()
    places = []
    for d in collect():
        try:
            places.append((float(d["x"]), float(d["y"]), d.get("place_name", "")))
        except (KeyError, TypeError, ValueError):
            continue
    if not places:
        print("[crosscheck] 카카오 조회 결과 0건 — KAKAO_REST_API_KEY 확인")
        return

    conflict = 0
    for r in rows:
        f = feats.get(r["id"])
        if f is None:
            r.update(dict.fromkeys(_ADDED, ""))
            continue
        rings = _rings(f["geometry"])
        clat, clon = (float(v) for v in r["coord"].split(","))

        in_names, near_names = [], []
        for lon, lat, name in places:
            if any(_pip(lon, lat, ring) for ring in rings):
                in_names.append(name)
            elif _dist_m(clat, clon, lat, lon) <= _NEAR_M:
                near_names.append(name)

        r["kakao_pip"] = str(len(in_names))
        r["kakao_30m"] = str(len(near_names))
        r["crosscheck"] = ""
        if show_names and (in_names or near_names):
            # 콘솔에만 — 리다이렉트하면 그것도 저장이다(모듈 머리말)
            print(f"    {r['jibun']}: {' / '.join((in_names or near_names)[:3])}")
        if r["status_predicted"] in ("empty", "high") and in_names:
            r["crosscheck"] = f"상충({len(in_names)})"
            conflict += 1

    for r in rows:                      # 폐지 열 제거
        for k in _DROPPED:
            r.pop(k, None)
    fields = [k for k in rows[0].keys()
              if k not in _ADDED and k not in _DROPPED] + list(_ADDED)
    with _CSV.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # 전수 참고 통계 — 공실 의심(empty) 전체 중 카카오 현존 장소가 있는 건물 비율
    empty_all = [f for f in master["features"] if f["properties"]["status"] == "empty"]
    empty_hit = 0
    for f in empty_all:
        rings = _rings(f["geometry"])
        if any(any(_pip(lon, lat, ring) for ring in rings) for lon, lat, _ in places):
            empty_hit += 1

    print(f"[crosscheck] 표본 {len(rows)}동 갱신 — 예측 empty/high 중 상충 {conflict}동")
    print(f"[crosscheck] (전수) empty {len(empty_all)}동 중 카카오 현존 장소 보유 {empty_hit}동 "
          f"({round(empty_hit / len(empty_all) * 100, 1) if empty_all else 0}%) — 과대추정 신호")
    print(f"[crosscheck] {_CSV.name} 에 {', '.join(_ADDED)} 열 추가 — 라벨링 시 참고")


if __name__ == "__main__":
    import sys

    run(show_names="--show-names" in sys.argv)
