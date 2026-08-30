---
name: hub-onboard
description: 새 거점(hub) 하나를 등록부터 Tier1(대장 실측 공실률)까지 올리는 절차 — 좌표 등록 → 점포·폴리곤·대장 수집 → Gold 빌드 → 앵커 대조. 거점을 추가하거나 기존 거점을 Tier2→Tier1 으로 올릴 때.
---

# 거점 온보딩 — 좌표 하나에서 Tier1 까지

거점은 **좌표와 반경만으로 시작**한다. 시군구·법정동은 점포·폴리곤의 PNU 19자리에서
건별로 파생하므로 도시 가정이 코드에 없다(`data/config/page_hubs.py` 머리말).
그래서 서울 거점이든 고양·파주 거점이든 아래 절차가 같다.

호출 인수 = 거점 slug(들). 비어 있으면 무엇을 올릴지 먼저 묻는다.

> 이 skill 은 **수집·빌드 절차**다. 등재·검증·배포까지 한 줄로 밀 때는 `hub-chain`,
> 지금 어느 단계인지는 `python scripts/chain_status.py <slug>`.

## 0. 먼저 재고 등록한다 — 등록이 아니라 프로브가 먼저다

거점을 코드에 적기 전에 **건물당 점포 수**를 잰다. 계획상가(집합건물)에 점포가 들어 있는
지형이면 우리 공실 분모(`floor_ouln` 일반건축물만)가 대다수를 놓친다.

| 지점 | 건물당 점포 | 판정 |
|---|---|---|
| 파주 금촌 3.0 · 서울 가로수길 4.0 · 파주 운정 5.3 · 고양 화정 8.5 | ≤10 | 통과 |
| 고양 일산 라페스타 **37.4** | >10 | 후보에서 내리거나 집합상가 비중을 명시한 채 넣는다 |

> 기준: 건물당 점포 수 > 10 이면 거점 후보에서 내린다 →
> `docs/plan-gyeonggi-expansion-2026-08-29.md` §3-B. 1콜이면 재는 값이다(`probe-first` skill).

## 1. 등록

`data/config/page_hubs.py` 의 `HUBS`(서울) 또는 `GYEONGGI_HUBS`(경기)에 한 줄:

```python
"hwajeong": PageHub("hwajeong", "화정", 126.8330, 37.6350, 500, 700, city="goyang"),
#            slug        표시명   경도(cx)  위도(cy)  radius_m stores_radius_m
```

- `stores_radius_m > radius_m` 을 지킨다 — 폴리곤 커버리지 ⊇ 점포 원칙(경계 건물 empty 오판 방지).
- 새 도시면 `apps/backend/app/data/cities.py` 의 `CITIES` 에도 같은 슬러그를 넣는다.
  **두 곳이 어긋나면 수집은 되는데 API 가 다른 도시로 부른다** —
  `apps/backend/tests/test_city_registry.py` 가 이 어긋남을 고정한다.
- 등재는 **수집 대상 등록일 뿐 화면 노출이 아니다.** Gold 가 서기 전에는
  `app/data/seoul_pages.DISTRICTS` 에 올리지 않는다(시드 zones/units 를 지어내지 않기 위해).

## 2. 수집 (Bronze) — 쿼터가 걸리는 것은 대장 하나뿐이다

```bash
python -m data.collectors.vworld_bldg <slug>          # 건물 폴리곤 (쿼터 넉넉)
python -m data.collectors.building_vacancy <slug>     # 점포 + 대장(전유부→표제부)
python -m data.collectors.floor_capacity <slug>       # 층별개요 → floor_ouln (정밀 분모)
```

`floor_capacity` 는 거점을 **반드시 명시**한다 — 비우면 garosugil 로 폴백한다.
중단됐으면 `--only-approx` 로 재개한다(저장된 건물은 이미 `floor_ouln` 이라 이 플래그가
곧 "완료분 건너뛰기"다). 플래그 없이 재실행하면 받은 것까지 다시 부른다.

- 건축HUB 는 **일 10,000콜이 오퍼레이션별로 따로** 걸린다. 거점당 전유부 ≈1,279콜 ·
  표제부 ≈861콜 — 전유부가 병목이다. 착수 전 `python scripts/quota_preflight.py`,
  하루치를 태우는 방법은 `quota` skill.
- 스모크만 볼 때는 `LIMIT_BUILDINGS=8`.
- 대장 없이 먼저 지도만 세우려면 `--no-ledger` (Tier2 — V-World 지상층수로 capacity 근사).

## 3. Gold 빌드

```bash
python -m data.pipelines.build_building_attrs <slug>
python -m data.pipelines.recalc_floor_ouln <slug>     # bronze 원본에서 분모 재계산(API 콜 0)
python -m data.pipelines.build_page_master <slug>     # page_building_master.geojson + coverage.json
python -m data.pipelines.build_vacant_units <slug>
python -m data.pipelines.calibrate_vacancy            # 전 거점 α 재산출
```

## 4. 통과 조건 — 문서가 아니라 `coverage.json` 을 읽는다

```bash
python -c "import json;d=json.load(open('data/gold/<slug>/coverage.json',encoding='utf-8'));print({k:d[k] for k in ('tier','shown','reference_vacancy_pct','reference_coverage_pct','by_capacity_method')})"
```

- `tier` == `Tier1(대장)` — 거점 수를 셀 때 이 필드가 **단일 기준**이다.
- `reference_coverage_pct` ≥ 80 — 미만이면 `floor_approx` 잔여가 많다는 뜻이니
  `floor_capacity` 를 더 돌린다.
- `reference_vacancy_pct` 를 R-ONE 앵커와 대조(`calibration.json.anchor_pct`).
  격차 30%p 초과면 가드레일 위반이다(현재 알려진 이상치: nokdu +34.55%p).

## 5. 서빙 확인

```bash
curl.exe -s "http://localhost:5173/api/v1/heatmap/buildings?district=<slug>"
```
`features` 수가 8이면 샘플 폴백을 탄 것이다 — Gold 가 안 닿았다는 뜻. 자세히는 `verify` skill.

## 함정

- **`polygon_only` 를 섞은 채 평균 공실률을 말하지 않는다.** `capacity_method` 가
  `expos_units`(집합건물)인 건물도 대표 집계에서 뺀다 — 분모는 정밀한데 분자가 비어
  공실률이 78~86% 로 튄다(2026-08-01 seoulsup 19.8%→67.0% 실측).
- **로그를 파일로 받을 때 `PYTHONIOENCODING=utf-8`** — cp949 에 `—` 가 없어 수집기가 죽는다.
- 이미 산출물이 있으면 수집기는 건너뛴다. 다시 받으려면 `--force`.
