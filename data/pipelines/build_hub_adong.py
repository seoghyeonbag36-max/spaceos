"""[Page] 거점 ↔ 행정동 매핑 사이드카 (silver/hub_adong.json).

## 왜 필요한가

생활이동(수도권 생활이동)·생활인구는 **행정동** 단위다. 우리 Page 는 건물 단위라
그대로는 못 붙는다. 둘을 잇는 표가 저장소에 없다 — `config/garosugil.py` 에
신사동 행정동코드가 **한 줄 하드코딩**돼 있는 것이 전부고, 그나마 "자릿수 재확인"
주석이 달려 있다. 66거점으로 늘어난 지금 그 방식은 못 쓴다.

## 행정동은 이미 우리 손에 있다 (2026-09-15 정정)

**종전 구현은 카카오 `coord2regioncode` 로 건물 좌표를 역지오코딩했다. 불필요했다.**
그때 적어 둔 근거가 틀렸다:

> "`stores_raw.lnoAdr` 에서 뽑히는 것은 **법정동**이고 … 생활이동은 **행정동**이다"

맞는 말이지만 `lnoAdr`(지번주소 문자열)에만 맞다. 상가정보 API 응답에는 행정동이
**별도 필드로 들어 있다** — `adongCd`(8자리)·`adongNm`. 저장소에 커밋된 프로브
로그가 그 증거다(`data/logs/probe_d1_2026-07-07.log`, 2026-07-07 실측 샘플):

    'signguNm': '강남구', 'adongCd': '11680510', 'adongNm': '신사동',
    'ldongCd': '1168010700', 'ldongNm': '신사동', 'lnoCd': '11680107001050500 00'

`adongCd` 는 **8자리**이고, 이 저장소가 요구하는 형식과 정확히 같다
(`data/tests/test_page_footfall_hourly.py::test_adong8_*` 가 신사동 = `11680510` 을
고정한다). 즉 역지오코딩으로 받아오던 값이 이미 Bronze 에 있었다.

그래서 카카오 호출을 없앴다. 두 가지가 같이 해결된다:

  ① **약관** — 카카오 로컬은 응답 저장을 허용하지 않는다(실시간 호출만). 종전 구현은
     응답을 `silver/coord_adong_cache.json` 과 이 사이드카로 영구화했다.
     → `docs/finding-map-provider-google-2026-09-15.md` §7-2
  ② **시간·쿼터** — 거점당 약 80콜(66거점 2시간대)이 **0콜**이 된다.

## 건물 → 행정동 배정 규칙

점포는 행정동을 들고 있고 건물은 안 들고 있다. 둘을 잇는 방법이 두 가지이고,
`build_district_zones` 가 이미 **두 방법의 일치율을 실측**해 뒀다(99.2%, 5,732동):

  1. **PNU 직접 조인** — 건물 `pnu` == 점포 `lnoCd`. 정확하지만 **79.3%만** 붙는다
     (점포가 없는 건물이 있다).
  2. **kNN 다수결** — 가장 가까운 점포 9개의 행정동 최빈값. 100% 붙는다.

여기서는 **1 을 먼저 쓰고 안 되면 2 로 내려간다.** 정확한 것을 먼저 쓰고 빈 자리만
근사로 채우는 순서다. 배정 근거는 거점별로 집계해 찍는다(`by_method`) — 근사 비중이
조용히 커지는 것을 막는다.

⚠ kNN 은 scipy 를 쓴다(`build_district_zones`·`build_store_graph_edges` 와 같은 지연
임포트). scipy 가 없으면 PNU 조인만으로 돌고 **그 사실을 로그로 밝힌다** — 조용히
커버리지가 깎이지 않게.

## 가중치를 함께 낸다

한 거점이 행정동 여러 개에 걸치는 것이 정상이다(가로수길은 신사동 하나가 아니다).
생활이동 값을 거점에 얹으려면 **거점이 그 행정동을 얼마나 차지하는가**가 필요하다.
건물 수가 아니라 **상업 연면적**(`silver/{slug}/building_attrs.com_area_flr`)으로
가중한다 — 사람이 모이는 곳은 건물 개수가 아니라 상업 바닥면적을 따라간다.
`build_page_footfall` 이 상권 값을 셀에 얹을 때와 같은 철학이고, 면적 가중은
2026-08-23 분모 정정(고시원·독서실 제외)이 반영된 값을 그대로 탄다.

실행:
  python -m data.pipelines.build_hub_adong            # 전 거점
  python -m data.pipelines.build_hub_adong nokdu      # 일부만
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

from data.collectors.common import GOLD, SILVER, load_latest
from data.config.page_hubs import ACTIVE_HUBS, ALL_HUBS
from data.pipelines.build_building_attrs import load as load_attrs

_OUT = SILVER / "hub_adong.json"

# 이웃 표본 수. build_district_zones 가 PNU 조인과 99.2% 일치를 확인한 값이다 —
# 두 파이프라인이 같은 규칙을 쓰도록 값을 맞춘다.
KNN_K = 9


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


def adong_index(rows: list[dict]) -> tuple[list[tuple[float, float]],
                                           list[tuple[str, str, str]],
                                           dict[str, tuple[str, str, str]]]:
    """상가정보 행 → (좌표 목록, 라벨 목록, PNU→라벨 사전).

    라벨은 `(행정동코드, 행정동명, 구명)`. 코드가 비어 있는 행은 버린다 — 이름만으로는
    생활인구·생활이동과 조인할 수 없다(동명이동이 있다).
    """
    pts: list[tuple[float, float]] = []
    labels: list[tuple[str, str, str]] = []
    by_pnu: dict[str, tuple[str, str, str]] = {}
    for r in rows:
        code = str(r.get("adongCd") or "").strip()
        if not code:
            continue
        label = (code, str(r.get("adongNm") or "").strip(),
                 str(r.get("signguNm") or "").strip())
        pnu = str(r.get("lnoCd") or "").strip()
        if pnu:
            by_pnu.setdefault(pnu, label)
        try:
            pts.append((float(r["lon"]), float(r["lat"])))
        except (KeyError, TypeError, ValueError):
            continue    # 좌표가 없으면 kNN 표본에는 못 들어가도 PNU 조인에는 남는다
        else:
            labels.append(label)
    return pts, labels, by_pnu


def _knn_voter(pts: list[tuple[float, float]], labels: list[tuple[str, str, str]]):
    """좌표 → 최근접 KNN_K 개의 행정동 최빈값. scipy 가 없으면 None."""
    if not pts:
        return None
    try:
        from scipy.spatial import cKDTree   # 지연 임포트 — 서빙에는 안 실린다
    except ImportError:
        return None
    tree = cKDTree(pts)
    k = min(KNN_K, len(pts))

    def vote(lon: float, lat: float) -> tuple[str, str, str] | None:
        _, idx = tree.query([lon, lat], k=k)
        ids = idx if hasattr(idx, "__iter__") else [idx]
        near = [labels[i] for i in ids if i < len(labels)]
        if not near:
            return None
        top = Counter(n[0] for n in near).most_common(1)[0][0]
        return next(n for n in near if n[0] == top)

    return vote


def build(slug: str) -> tuple[dict, dict] | None:
    """거점 하나 → ({행정동코드: {...weight}}, 배정 통계). 재료가 없으면 None."""
    master = GOLD / slug / "page_building_master.geojson"
    if not master.exists():
        print(f"[hub-adong:{slug}] page_building_master.geojson 없음 — 건너뜀")
        return None
    rows = load_latest(slug, "stores_raw.json") or []
    if not rows:
        print(f"[hub-adong:{slug}] stores_raw.json 없음 — "
              f"data.collectors.building_vacancy 먼저")
        return None

    pts, labels, by_pnu = adong_index(rows)
    if not by_pnu and not pts:
        print(f"[hub-adong:{slug}] adongCd 를 가진 점포 0건 — 건너뜀")
        return None
    vote = _knn_voter(pts, labels)
    if vote is None and pts:
        print(f"[hub-adong:{slug}] ⚠ scipy 없음 — PNU 조인만으로 배정한다"
              f"(커버리지가 낮아진다)")

    feats = json.loads(master.read_text(encoding="utf-8")).get("features") or []
    attrs = load_attrs(slug)

    acc: dict[str, dict] = defaultdict(
        lambda: {"adm_nm": None, "gu": None, "buildings": 0, "com_area_m2": 0.0})
    stat = {"pnu": 0, "knn": 0, "missed": 0}
    for f in feats:
        p = f.get("properties") or {}
        label = by_pnu.get(str(p.get("pnu") or "").strip())
        if label:
            stat["pnu"] += 1
        elif vote is not None:
            c = _centroid(f.get("geometry") or {})
            label = vote(*c) if c else None
            if label:
                stat["knn"] += 1
        if not label:
            stat["missed"] += 1
            continue
        code, nm, gu = label
        a = acc[code]
        a["adm_nm"] = a["adm_nm"] or nm
        a["gu"] = a["gu"] or gu
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

    out = dict(sorted(acc.items(), key=lambda kv: -kv[1]["weight"]))
    top = list(out.items())[:3]
    print(f"[hub-adong:{slug}] 행정동 {len(out)}개 · 배정 PNU {stat['pnu']}/kNN "
          f"{stat['knn']} · 미배정 {stat['missed']}동 · "
          + " · ".join(f"{v['adm_nm']}({v['weight']:.0%})" for _, v in top))
    return out, stat


def run(slugs: list[str]) -> dict:
    out: dict[str, dict] = {}
    total = Counter()
    for slug in slugs:
        got = build(slug)
        if got is None:
            continue
        out[slug], stat = got
        total.update(stat)

    doc = {
        "source": ("소상공인 상가정보 adongCd/adongNm(8자리 행정동) × "
                   "gold/{거점}/page_building_master — 건물 배정은 PNU 조인 우선, "
                   "빈 자리만 최근접 점포 9개 다수결(build_district_zones 가 두 방법의 "
                   "99.2% 일치를 실측)"),
        "weight": ("거점이 그 행정동을 차지하는 비중. 기준은 상업 연면적"
                   "(silver/building_attrs.com_area_flr)이며, 대장 미수집 거점만 건물 수로 물러선다."),
        "assign": {"pnu": total["pnu"], "knn": total["knn"], "missed": total["missed"]},
        "note": ("2026-09-15 카카오 coord2regioncode 를 걷어냈다 — 행정동은 상가정보 "
                 "응답에 이미 있었다(data/logs/probe_d1_2026-07-07.log). 카카오는 응답 "
                 "저장을 허용하지 않으므로 이 경로가 약관에도 저촉했다. "
                 "silver/coord_adong_cache.json 은 더 만들지 않는다."),
        "hubs": out,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[hub-adong] 완료: {len(out)}거점 · 배정 PNU {total['pnu']} / kNN "
          f"{total['knn']} / 미배정 {total['missed']} · API 호출 0 → "
          f"{_OUT.relative_to(SILVER.parent)}")
    return out


def load() -> dict[str, dict]:
    """소비처용 로더 — {slug: {adm_cd: {...weight}}}. 없으면 빈 dict."""
    if not _OUT.exists():
        return {}
    return (json.loads(_OUT.read_text(encoding="utf-8")).get("hubs") or {})


def main() -> None:
    argv = sys.argv[1:]
    slugs = [a for a in argv if not a.startswith("-")] or list(ACTIVE_HUBS)
    run([s for s in slugs if s in ALL_HUBS])


if __name__ == "__main__":
    main()
