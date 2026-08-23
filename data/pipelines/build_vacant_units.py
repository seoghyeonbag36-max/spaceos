"""[Posting] 실제 공실 유닛 Gold — gold/{slug}/vacant_units.json 산출.

⚠️ **백엔드에 아직 배선되지 않았다 — 남은 근거 부재 2건 때문이다(2026-08-22 기준).**
산출물은 **54거점 216유닛**이다(2026-08-23 재실행. 08-22 판은 580유닛).
**580 → 216 은 면적이 아니라 분자 때문이다** — 인허가 5종→27종 확장으로 영업이 더
확인되면서 `empty`/`high` 로 잡히던 건물이 실제 영업 중으로 판명됐다. 종전 목록은
그만큼 분자 결손으로 부풀어 있었다(경위: docs/feature-page.md 「인허가 27종 실수집」).
`/postings` 는 아직 시드 유닛을 쓴다. 아래 셋 중 3번은 풀렸고 1·2번이 남았다.
종전 미산출 5곳(kyunghee·wangsimni·sadang·sukmyung·hyehwa)은 막힘이 아니라 대기였고,
08-17 대장 완주로 silver/{slug}/building_attrs.json 에 com_area_flr 이 채워지면서
재실행만으로 풀렸다(sadang 만 8유닛, 나머지 4곳 12유닛).

✅ **추적 문제는 해소됐다(2026-08-23 확인).** 54개 `vacant_units.json` 전부 `git ls-files`
에 잡힌다 — 이미 추적 중인 파일에는 gitignore 가 적용되지 않기 때문이다. 배포에서
조용히 시드로 떨어질 걱정은 없다.

`tier_scenarios()` 가 요구하는 세 입력이 실제 건물 유닛에 없는데, **무엇으로 대신할지
정할 자료 자체가 없다.** 결정을 미룬 게 아니라 결정 근거가 없는 상태다.

  1. `prem`(권리금) — **해상도 부족**(2026-08-09 정정. 이전 기록은 "공개 통계 부재"였으나
     사실이 아니다). 통계는 있다 — 「상가건물임대차 실태조사」(국가승인통계 142006,
     중기부·소상공인시장진흥공단)가 권리금을 포함한다. 다만 표본이 **전국 임차인 7,000**
     이라 시도·상권유형 단위 공표이고, 54거점에 내릴 표본 밀도가 없다(R-ONE 임대료는
     거점 상권 단위라 층 계수로 유닛까지 내릴 수 있었다). 0 이면 초기투자 과소,
     임의 추정치면 그 위 ROI 가 전부 가정이 된다. 어느 쪽이 덜 틀린지 판단할 기준이 없다.
     → 거점 단위 권리금 소스 확보, 또는 "시뮬레이션이 권리금을 포함해야 하는가"라는
     제품 판단이 있어야 풀린다.
  2. `foot` — **공간 해상도 부재.** posting_inputs 의 혼합 보정은 "거점 flpop + 시드의
     거점 내 서열"인데 실제 건물 유닛에는 시드 서열이 없다. 건물 좌표로 서열을 만들려 해도
     거점 안을 구분할 유동인구가 없다(flpop 은 거점 단위, living_population 은 산출물 없음).
     → 구역/격자 단위 유동인구가 필요한데 **현재 경로로는 안 된다**: 설정된
     `SPOP_LOCAL_RESD_DONG` 은 행정동 단위이고 `living_population.py` 는 그걸 다시 25구
     상대값으로 집계한다(신사동 하나가 통째로 한 값). 실제로 필요한 건 생활인구 **50m 격자**
     (파일 다운로드 경로, REST API 아님) 또는 골목상권 **10m 도로 단위** — 둘 다 미확인·수집기 없음.
  3. ~~`rec`(추천 Tier) — 기준 정의 부재~~ → **해소(2026-08-16).** 회수 최단으로 정의하고
     `services/districts.recommend_tier()` 가 계산한다. 시드의 `rec` 필드를 읽지 않으므로
     이 파이프라인 산출물처럼 rec 이 없는 유닛도 그대로 통과한다.
     ⚠ 다만 그 위의 **비용 모델이 아직 보정되지 않았다** — `month_cost` 에 원가·인건비가
     없어 마진이 51~73%(실제 외식업 10~20%), 회수기간이 0.5~1.6개월로 나온다. 전수
     실측에서 `factory` 는 어떤 입력에서도 1위가 되지 못한다. 기준이 아니라 비용 모델이
     병목으로 옮겨갔다.

근거 없이 배선하면 "실제 건물"이라는 겉모습에 가정값 셋이 올라타 오히려 시드보다 위험해진다
— 실측처럼 보이는 추정치가 가장 나쁘다. 그래서 산출까지만 하고 멈췄다.


## 무엇이 바뀌나

지금까지 Posting 유닛은 거점당 손으로 적은 5개였다(`seoul_pages.py` 의 `u()`).
좌표·면적·업종이 전부 가공이라 "가로수길 메인로 1F 42평"은 실제로 존재하지 않는
자리였다. 이 파이프라인은 **Gold 건물 마스터에서 실제로 공실인 건물**을 뽑아
유닛으로 만든다 — 이름·좌표·층수·업종·공실률이 전부 실측이고, 면적은 건축물대장
상업면적(silver `building_attrs.com_area_flr`)에서 온다.

## 유닛 하나의 면적

건물의 상업면적을 호실 수로 나눈 **호실당 평균 면적**이다(㎡ → 평).
건물 전체 면적이 아니라 한 자리의 면적이어야 3-Tier 계산(인테리어비·매출 추정)이
맞기 때문이다. 대장 상업면적이 없는 건물은 유닛에서 제외한다 — 면적을 가정하면
그 위에 쌓인 투자비·매출이 전부 가정이 된다.

## 여전히 실데이터가 아닌 것

- `prem` 권리금: 거점 단위 소스가 없다(통계 142006 은 전국 7,000 표본이라 해상도 부족).
  거점 중앙값 기반 추정치를 넣고 `inputs_source.prem = "seed"` 로 표기한다.
- `rec`(추천 Tier)·`persona`·`note`: 시드의 서술 필드. 유닛이 실제 건물로 바뀌면
  의미가 없어 **넣지 않는다**(프론트는 없으면 그 줄을 그리지 않는다).

실행: python -m data.pipelines.build_vacant_units [거점 ...]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from data.collectors.common import GOLD, SILVER
from data.config.page_hubs import HUBS

_M2_PER_PYEONG = 3.3058

# 분모(capacity) 근거가 정밀한 방법만. services/gold_vacancy 와 같은 기준이다.
_COUNTED_METHODS = {"floor_ouln"}
# 점포 매칭이 있는 건물만 — polygon_only 는 active=0 이라 '공실'이 자동 성립한다.
_COUNTED_SOURCE_PREFIX = "stores+ledger"
# 공실로 볼 상태
_VACANT_STATUS = {"empty", "high"}

# 유닛이 너무 작거나 크면 3-Tier 계산이 의미를 잃는다(창고·대형 집합상가 등).
_MIN_PYEONG, _MAX_PYEONG = 5, 200
_MAX_UNITS = 12   # 프론트 카드 수 상한


def _units_for(slug: str) -> list[dict]:
    master = GOLD / slug / "page_building_master.geojson"
    attrs_path = SILVER / slug / "building_attrs.json"
    if not master.exists():
        return []
    attrs = json.loads(attrs_path.read_text(encoding="utf-8")) if attrs_path.exists() else {}

    fc = json.loads(master.read_text(encoding="utf-8"))
    out: list[dict] = []
    for feat in fc["features"]:
        p = feat["properties"]
        if p.get("status") not in _VACANT_STATUS:
            continue
        if p.get("capacity_method") not in _COUNTED_METHODS:
            continue
        if not str(p.get("source") or "").startswith(_COUNTED_SOURCE_PREFIX):
            continue
        capacity = p.get("capacity") or 0
        if capacity <= 0:
            continue

        at = attrs.get(str(p.get("pnu") or ""), {})
        com_area = at.get("com_area_flr")
        if not com_area:
            continue                      # 면적을 가정하지 않는다 — 없으면 유닛에서 뺀다
        area_pyeong = round(com_area / capacity / _M2_PER_PYEONG)
        if not (_MIN_PYEONG <= area_pyeong <= _MAX_PYEONG):
            continue

        ring = feat["geometry"]["coordinates"][0]
        pts = ring[:-1] if len(ring) > 2 and ring[0] == ring[-1] else ring
        lat = sum(q[1] for q in pts) / len(pts)
        lng = sum(q[0] for q in pts) / len(pts)

        floors = p.get("floors") or 1
        out.append({
            "id": f"vu-{p.get('id')}",
            "n": at.get("bld_nm") or p.get("name") or "(이름 미상)",
            "grp": p.get("industry") or "",
            "lat": round(lat, 6), "lng": round(lng, 6),
            "area": area_pyeong,
            "floor": "1F",                # 상가정보 flrNo 로 층을 특정하기 전까지 1층 가정
            "was": p.get("industry") or "",
            "capacity": capacity, "active": p.get("active") or 0,
            "vacancy_rate": p.get("vacancy_rate"),
            "bld_floors": floors,
            "com_area_m2": round(float(com_area), 1),
        })

    # 공실률 높은 순 → 면적 큰 순. 입점 검토 우선순위에 가깝다.
    out.sort(key=lambda u: (-(u["vacancy_rate"] or 0), -u["area"]))
    return out[:_MAX_UNITS]


def run(slugs: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for slug in slugs:
        units = _units_for(slug)
        if not units:
            counts[slug] = 0
            continue
        out = {
            "source": ("Gold 건물 마스터(공실 건물) + 건축물대장 상업면적"
                       "(silver building_attrs.com_area_flr)"),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": ("면적은 건물 상업면적 ÷ 호실 수(호실당 평균, 평). 대장 면적이 없는 "
                     "건물은 제외했다 — 면적을 가정하면 그 위 투자비·매출이 전부 가정이 된다. "
                     "층은 1F 가정(상가정보 flrNo 매칭 전). 권리금은 거점 단위 소스가 없어 "
                     "유닛에 없다 — 통계(상가건물임대차 실태조사 142006)는 있으나 전국 7,000 "
                     "표본이라 시도·상권유형 단위다."),
            "units": units,
        }
        path = GOLD / slug / "vacant_units.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        counts[slug] = len(units)
    return counts


def main() -> None:
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(HUBS)
    counts = run([s for s in slugs if s in HUBS])
    ok = {k: v for k, v in counts.items() if v}
    print(f"[vacant-units] 산출 {len(ok)}거점 / 시도 {len(counts)}거점")
    for slug, n in sorted(ok.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {slug:18s} {n:3d}유닛")
    empty = [k for k, v in counts.items() if not v]
    if empty:
        print(f"  0유닛(건물 마스터·대장면적 미적재): {', '.join(empty[:8])}"
              f"{' 외 %d곳' % (len(empty) - 8) if len(empty) > 8 else ''}")


if __name__ == "__main__":
    main()
