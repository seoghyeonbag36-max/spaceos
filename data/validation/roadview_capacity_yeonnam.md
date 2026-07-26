# capacity 방식 판정 표본 — 연남동 (yeonnam) 29동

라벨은 `roadview_capacity_yeonnam.csv` 에 기입합니다. 링크는 **카카오 로드뷰**(좌표 기준)라
클릭하면 해당 건물 앞에서 바로 열립니다. 상호명이 아니라 좌표로 특정하므로
동명 건물 혼동이 없습니다.

## 무엇을 세는가 — `commercial_floors_actual` 이 핵심

이 표본의 목적은 공실률 정확도가 아니라 **분모(capacity) 산식 판정**입니다.
현재 두 방식이 이렇게 갈립니다:

| 방식 | capacity 산식 | 현재 추정 공실 |
|---|---|---|
| `floor_approx` | 지상 **전체** 층수 × 2호 | 60~72% (앵커 +19~30%p) |
| `floor_ouln` | **상업용도** 층수 × 2호 | 4.6% (앵커 -37.0%p) |

차이는 오직 '몇 개 층을 상가로 세는가' 입니다. 그러니 로드뷰에서
**상가로 쓰이는 지상 층이 몇 개인지** 세어 `commercial_floors_actual` 에 적으면
어느 산식이 맞는지 바로 판정됩니다.

| 칸 | 채우는 법 | 필수 |
|---|---|---|
| `commercial_floors_actual` | 간판·쇼윈도·층별 안내판으로 상가가 든 지상 층 수 | **필수** |
| `total_floors_actual` | 눈으로 센 지상 총 층수 (대장 층수 검증) | 선택 |
| `units_actual` | 상가 호실 수를 셀 수 있으면 (층당 2호 근사 검증) | 선택 |
| `label_actual` | `공실` / `부분공실` / `영업` / `불명` | **필수** |

주거·사무실 전용 층은 상가에서 **뺍니다**. 판정 불가면 `label_actual` 에 `불명`.

## 대상 건물

| # | 지번 | 예측방식 | 예측 | 공실률 | active/capacity | 추정층수 | 로드뷰 |
|---|---|---|---|---|---|---|---|
| 1 | 연남동 381-24 | floor_approx | high | 87.5% | 1/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.560424,126.925493) |
| 2 | 동교동 169-8 | floor_approx | high | 75.0% | 1/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.556477,126.925486) |
| 3 | 연남동 245-41 | floor_approx | full | 0.0% | 11/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.565530,126.921651) |
| 4 | 동교동 197-40 | floor_approx | full | 0.0% | 2/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.559963,126.923411) |
| 5 | 연남동 369-20 | floor_approx | partial | 25.0% | 6/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.563421,126.920782) |
| 6 | 동교동 150-19 | floor_approx | high | 75.0% | 2/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.560144,126.924667) |
| 7 | 연남동 573 | expos_units | high | 92.3% | 1/13 | — | [로드뷰](https://map.kakao.com/link/roadview/37.562710,126.921858) |
| 8 | 연희동 194-30 | expos_units | partial | 43.8% | 9/16 | — | [로드뷰](https://map.kakao.com/link/roadview/37.565228,126.930175) |
| 9 | 동교동 150-3 | floor_approx | full | 0.0% | 6/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.560423,126.924463) |
| 10 | 연남동 229-34 | floor_approx | partial | 30.0% | 7/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.563027,126.924857) |
| 11 | 연남동 482-2 | expos_units | high | 75.0% | 1/4 | — | [로드뷰](https://map.kakao.com/link/roadview/37.563095,126.918122) |
| 12 | 서교동 346-41 | floor_approx | partial | 37.5% | 5/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.555350,126.923868) |
| 13 | 동교동 166-5 | floor_approx | partial | 50.0% | 4/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.557405,126.925564) |
| 14 | 연남동 509-14 | floor_approx | high | 70.0% | 3/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.562971,126.921110) |
| 15 | 연남동 381-3 | floor_approx | full | 0.0% | 5/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.560964,126.925300) |
| 16 | 동교동 198-27 | floor_approx | high | 70.0% | 3/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.559089,126.923457) |
| 17 | 연남동 562-46 | expos_units | partial | 50.0% | 1/2 | — | [로드뷰](https://map.kakao.com/link/roadview/37.560987,126.919720) |
| 18 | 동교동 169-5 | floor_approx | full | 0.0% | 2/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.556631,126.925950) |
| 19 | 연남동 487-237 | floor_approx | partial | 50.0% | 1/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.563473,126.917805) |
| 20 | 연희동 340-27 | expos_units | high | 75.0% | 1/4 | — | [로드뷰](https://map.kakao.com/link/roadview/37.563779,126.931738) |
| 21 | 연남동 256-7 | floor_approx | partial | 50.0% | 3/6 | 3 | [로드뷰](https://map.kakao.com/link/roadview/37.562701,126.922831) |
| 22 | 동교동 158-24 | floor_approx | high | 60.0% | 4/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.557386,126.922893) |
| 23 | 연남동 223-21 | floor_approx | high | 66.7% | 2/6 | 3 | [로드뷰](https://map.kakao.com/link/roadview/37.564910,126.924266) |
| 24 | 연남동 369-15 | expos_units | partial | 33.3% | 2/3 | — | [로드뷰](https://map.kakao.com/link/roadview/37.563169,126.920759) |
| 25 | 연남동 573 | expos_units | high | 92.3% | 1/13 | — | [로드뷰](https://map.kakao.com/link/roadview/37.563493,126.921234) |
| 26 | 연남동 382-19 | floor_approx | high | 62.5% | 3/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.561063,126.925673) |
| 27 | 연희동 188-55 | floor_approx | high | 83.3% | 2/12 | 6 | [로드뷰](https://map.kakao.com/link/roadview/37.565976,126.929415) |
| 28 | 연남동 566-43 | floor_approx | high | 90.0% | 1/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.560971,126.922267) |
| 29 | 동교동 200-8 | floor_approx | partial | 16.7% | 5/6 | 3 | [로드뷰](https://map.kakao.com/link/roadview/37.558413,126.923130) |