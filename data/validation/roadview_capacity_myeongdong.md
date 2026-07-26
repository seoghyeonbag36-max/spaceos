# capacity 방식 판정 표본 — 명동 (myeongdong) 30동

라벨은 `roadview_capacity_myeongdong.csv` 에 기입합니다. 링크는 **카카오 로드뷰**(좌표 기준)라
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
| 1 | 예장동 9 | expos_units | high | 97.0% | 1/33 | — | [로드뷰](https://map.kakao.com/link/roadview/37.559852,126.991489) |
| 2 | 충무로3가 33-3 | floor_approx | high | 71.4% | 4/14 | 7 | [로드뷰](https://map.kakao.com/link/roadview/37.562925,126.993288) |
| 3 | 명동1가 28-2 | floor_approx | high | 78.6% | 3/14 | 7 | [로드뷰](https://map.kakao.com/link/roadview/37.563951,126.985014) |
| 4 | 을지로2가 199-18 | floor_approx | full | 0.0% | 4/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.565699,126.983961) |
| 5 | 관수동 320 | floor_approx | full | 0.0% | 9/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.565646,126.991262) |
| 6 | 회현동2가 59 | floor_approx | high | 75.0% | 1/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.557725,126.982944) |
| 7 | 을지로2가 204 | expos_units | high | 79.2% | 5/24 | — | [로드뷰](https://map.kakao.com/link/roadview/37.566951,126.984912) |
| 8 | 남산동2가 27-2 | floor_approx | full | 0.0% | 4/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.558586,126.985700) |
| 9 | 충무로2가 61-1 | floor_approx | high | 87.5% | 2/16 | 8 | [로드뷰](https://map.kakao.com/link/roadview/37.561762,126.988093) |
| 10 | 을지로2가 203 | expos_units | partial | 43.5% | 35/62 | — | [로드뷰](https://map.kakao.com/link/roadview/37.565645,126.988138) |
| 11 | 남산동1가 15 | floor_approx | partial | 25.0% | 3/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.558617,126.984495) |
| 12 | 명동2가 2-23 | floor_approx | partial | 50.0% | 8/16 | 8 | [로드뷰](https://map.kakao.com/link/roadview/37.563735,126.985456) |
| 13 | 다동 92 | expos_units | partial | 45.0% | 11/20 | — | [로드뷰](https://map.kakao.com/link/roadview/37.567861,126.981731) |
| 14 | 초동 54 | floor_approx | partial | 25.0% | 3/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.563528,126.992032) |
| 15 | 저동2가 8 | floor_approx | full | 0.0% | 4/2 | 1 | [로드뷰](https://map.kakao.com/link/roadview/37.565357,126.990900) |
| 16 | 관철동 173-2 | floor_approx | partial | 37.5% | 5/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.569123,126.985104) |
| 17 | 을지로2가 101-11 | floor_approx | high | 60.0% | 4/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.566438,126.989168) |
| 18 | 다동 155 | expos_units | partial | 44.6% | 31/56 | — | [로드뷰](https://map.kakao.com/link/roadview/37.567140,126.980361) |
| 19 | 수표동 99 | floor_approx | full | 0.0% | 34/34 | 17 | [로드뷰](https://map.kakao.com/link/roadview/37.567522,126.988420) |
| 20 | 충무로1가 24-11 | floor_approx | partial | 50.0% | 2/4 | 2 | [로드뷰](https://map.kakao.com/link/roadview/37.561095,126.983894) |
| 21 | 충무로3가 49 | expos_units | high | 73.0% | 10/37 | — | [로드뷰](https://map.kakao.com/link/roadview/37.562240,126.992632) |
| 22 | 관철동 11-14 | floor_approx | partial | 30.0% | 7/10 | 5 | [로드뷰](https://map.kakao.com/link/roadview/37.568636,126.985885) |
| 23 | 을지로1가 188-3 | floor_approx | high | 85.2% | 8/54 | 27 | [로드뷰](https://map.kakao.com/link/roadview/37.565635,126.979434) |
| 24 | 관수동 302-16 | floor_approx | high | 87.5% | 1/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.565718,126.991420) |
| 25 | 회현동2가 88 | expos_units | partial | 33.3% | 8/12 | — | [로드뷰](https://map.kakao.com/link/roadview/37.560203,126.982932) |
| 26 | 관철동 175 | expos_units | high | 60.0% | 6/15 | — | [로드뷰](https://map.kakao.com/link/roadview/37.569060,126.984945) |
| 27 | 저동2가 3-1 | floor_approx | high | 62.5% | 3/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.565339,126.990096) |
| 28 | 충무로2가 50-10 | floor_approx | high | 92.9% | 2/28 | 14 | [로드뷰](https://map.kakao.com/link/roadview/37.562104,126.989282) |
| 29 | 남학동 18 | floor_approx | high | 87.5% | 1/8 | 4 | [로드뷰](https://map.kakao.com/link/roadview/37.560438,126.991070) |
| 30 | 회현동1가 71-6 | floor_approx | partial | 16.7% | 5/6 | 3 | [로드뷰](https://map.kakao.com/link/roadview/37.558373,126.980884) |