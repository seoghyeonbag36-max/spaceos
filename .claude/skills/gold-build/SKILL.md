---
name: gold-build
description: Bronze → Silver → Gold 재빌드와 서빙 반영 — 어떤 산출물이 어떤 파이프라인에서 나오고 무엇이 무엇을 입력으로 받는지. 데이터가 바뀌었거나 API 응답이 비어 있을 때.
---

# Gold 빌드 — 무엇이 무엇을 먹는가

3계층 규칙: **Bronze(무가공 원본) → Silver(정제) → Gold(서빙용)**. 소비층(API·ML)은
Gold 만 읽는다. 순서를 어기면 조용히 결손이 영구화된다 — 앞 단계가 덜 찬 채로 뒤를
돌리면 그 결손이 "이미 받은 날짜"로 캐시되기 때문이다(`run_page_hourly_chain.py` 머리말).

## 트랙별 산출물과 빌더

| 트랙 | Gold 산출물 | 빌더 |
|---|---|---|
| Page | `gold/{slug}/page_building_master.geojson` · `coverage.json` | `build_page_master` |
| Page | `gold/{slug}/building_vacancy.json` | 수집기 `building_vacancy` |
| Page | `gold/{slug}/vacant_units.json` | `build_vacant_units` |
| Page | `gold/{slug}/calibration.json` (α·앵커) | `calibrate_vacancy` |
| Page(유동) | 24시간 프로파일 | `build_hub_adong` → `living_population_hourly` → `build_page_footfall_hourly` |
| Platform | `platform_district_timeseries` · `platform_store_graph_{nodes,edges}` | `build_gold` · `build_store_graph_edges` |
| Platform | `gold/platform_vacancy_forecast.json` | `ml.training.train_lstm` |
| Platform | `gold/platform_industry_recommend.json` | `ml.training.train_gnn` |
| Posting | `gold/platform_posting_inputs.json` | `build_posting_inputs` |
| Program | `gold/{slug}/program_content_context.csv` | `build_gold` |

## 자주 쓰는 실행

```bash
# 한 거점 Page 재빌드 (수집은 그대로 두고 빌드만)
python -m data.pipelines.build_building_attrs <slug>
python -m data.pipelines.build_page_master <slug>
python -m data.pipelines.build_vacant_units <slug>
python -m data.pipelines.calibrate_vacancy

# Platform 분기 갱신 — 수집→Gold→학습→검증을 한 번에 (분기 1회)
python -m data.pipelines.refresh_platform                # 전체 (약 40~50분)
python -m data.pipelines.refresh_platform --skip-collect # 빌드·학습만 (약 7분)

# 영향만 먼저 본다 (쓰지 않는다)
python -m data.pipelines.recalc_capacity --dry-run
python -m data.pipelines.recalc_floor_ouln --dry-run
python -m data.pipelines.refresh_active --dry-run
```

`refresh_platform` 은 새 분기를 `data/config/platform_districts.py` 의 `QUARTERS` 에
추가한 **뒤에** 돌린다. 안 그러면 옛 분기까지만 다시 만든다.

## 백엔드가 pandas 없이 읽는 정적 JSON

`platform_vacancy_forecast.json` · `platform_industry_recommend.json` ·
`platform_posting_inputs.json` 은 **서빙 컨테이너에 pandas 를 싣지 않으려고** 정적
JSON 으로 떨군다. parquet 만 갱신하고 이 JSON 을 다시 안 만들면 API 는 옛 값을 계속 준다.

## 반드시 확인 — 산출물이 서빙에 닿았는가

빌드 성공은 서빙 성공이 아니다. 이 저장소가 **두 번 당한 양식**이 "데이터가 빠졌는데
화면은 멀쩡해 보인다"이다(2026-08-15 `.vercelignore` 가 `data/` 를 빼먹어 프로덕션이
gold 를 한 파일도 못 읽었는데 07-19 부터 아무도 몰랐다).

```bash
curl.exe -s "http://localhost:8000/api/v1/heatmap/buildings?district=<slug>" | head -c 300
python scripts/pppp_status.py     # 산출물을 세어 진행률을 낸다 — 문서를 믿지 않는다
```

`features` 8건 = 샘플 폴백, 800건대 = Gold 실데이터.

## 함정

- **`_is_offsite` 의 home_terms.** 거점이 속한 도시 이름을 타지명으로 세면 그 도시 글이
  전멸한다 — 2026-08-29 실측으로 "고양 화정 맛집" 100/100건이 폐기됐다(서울은 0건).
  새 도시를 붙일 때 `build_gold._HOME_TERMS_DEFAULT` 를 확인한다.
- **재실행은 안전하지만 무료가 아니다.** 수집기는 산출물이 있으면 건너뛴다. `--force` 는
  쿼터를 다시 태운다.
- **`calibration.json` 의 `gap_pp` 를 인용하지 말 것** — 집합건물을 포함한 혼합 추정 기준이다.
  대표 집계 기준 격차는 API 가 `anchor_gap_pp` 로 내려준다.
