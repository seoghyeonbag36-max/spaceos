# capacity 방식 판정 표본 — 익선동 (ikseon) 30동

라벨은 `roadview_capacity_ikseon.csv` 에 기입합니다. 링크는 **카카오 로드뷰**(좌표 기준)라
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
| 1 | 관훈동 155-1 | expos_units | high | 85.7% | 2/14 | — | [로드뷰](https://map.kakao.com/link/roadview/37.574790,126.983789) |
| 2 | 종로3가 28 | expos_units | high | 71.4% | 2/7 | — | [로드뷰](https://map.kakao.com/link/roadview/37.570736,126.992903) |
| 3 | 경운동 63-7 | floor_approx | high | 85.0% | 3/20 | 10 | [로드뷰](https://map.kakao.com/link/roadview/37.574367,126.986755) |
| 4 | 장사동 203-1 | expos_units | high | 66.7% | 1/3 | — | [로드뷰](https://map.kakao.com/link/roadview/37.569015,126.994295) |
| 5 | 안국동 159 | floor_approx | partial | 50.0% | 4/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.576520,126.984570) |
| 6 | 와룡동 61 | floor_approx | high | 87.5% | 1/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.574268,126.991431) |
| 7 | 종로3가 109-2 | floor_approx | full | 0.0% | 2/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.569988,126.990095) |
| 8 | 경운동 64-19 | floor_approx | partial | 50.0% | 1/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.574223,126.986314) |
| 9 | 와룡동 139 | floor_approx | high | 80.0% | 2/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.576484,126.990151) |
| 10 | 종로3가 144-1 | floor_approx | high | 62.5% | 3/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.570205,126.992857) |
| 11 | 종로3가 19 | expos_units | partial | 50.0% | 3/6 | — | [로드뷰](https://map.kakao.com/link/roadview/37.570691,126.991635) |
| 12 | 경운동 47-1 | floor_approx | full | 0.0% | 19/6 | 3 | [로드뷰](https://map.kakao.com/link/roadview/37.573835,126.986552) |
| 13 | 봉익동 37-15 | floor_approx | full | 0.0% | 2/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.572520,126.993016) |
| 14 | 관훈동 155-1 | expos_units | partial | 42.9% | 8/14 | — | [로드뷰](https://map.kakao.com/link/roadview/37.574610,126.983948) |
| 15 | 익선동 166-60 | floor_approx | partial | 50.0% | 1/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.572907,126.989382) |
| 16 | 경운동 63-10 | floor_approx | full | 0.0% | 2/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.574223,126.986925) |
| 17 | 관훈동 27-1 | floor_approx | partial | 50.0% | 1/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.573988,126.985352) |
| 18 | 낙원동 193 | floor_approx | high | 78.6% | 3/14 | 7 | [로드뷰](https://map.kakao.com/link/roadview/37.570808,126.990254) |
| 19 | 관철동 19-7 | expos_units | partial | 20.0% | 4/5 | — | [로드뷰](https://map.kakao.com/link/roadview/37.569276,126.985262) |
| 20 | 공평동 120-2 | floor_approx | full | 0.0% | 4/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.571708,126.982851) |
| 21 | 봉익동 38-9 | floor_approx | partial | 40.0% | 6/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.572241,126.993299) |
| 22 | 낙원동 288 | expos_units | partial | 48.3% | 138/267 | — | [로드뷰](https://map.kakao.com/link/roadview/37.572266,126.987670) |
| 23 | 묘동 149-1 | floor_approx | partial | 25.0% | 6/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.573574,126.991023) |
| 24 | 관수동 4-3 | floor_approx | high | 75.0% | 4/16 | 8 | [로드뷰](https://map.kakao.com/link/roadview/37.569583,126.988873) |
| 25 | 낙원동 220 | floor_approx | high | 75.0% | 2/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.572024,126.988442) |
| 26 | 권농동 187-21 | floor_approx | partial | 50.0% | 1/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.573863,126.992008) |
| 27 | 관훈동 155-1 | expos_units | high | 92.9% | 1/14 | — | [로드뷰](https://map.kakao.com/link/roadview/37.574727,126.983857) |
| 28 | 돈의동 102 | floor_approx | high | 62.5% | 3/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.571745,126.990605) |
| 29 | 관철동 14-10 | floor_approx | high | 83.3% | 2/12 | 6 | [로드뷰](https://map.kakao.com/link/roadview/37.569699,126.985896) |
| 30 | 관철동 12-6 | floor_approx | high | 91.7% | 1/12 | 6 | [로드뷰](https://map.kakao.com/link/roadview/37.568925,126.986496) |