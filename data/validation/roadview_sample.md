# 로드뷰 검증 샘플 30동 — 라벨은 roadview_sample.csv 에 기입

링크 클릭 → 네이버 지도에서 해당 건물 → **거리뷰**로 확인.
링크는 지번주소 검색이다. 표의 `건물`(상호명)은 참고용이며, 건물 특정은 지번 또는 CSV 의 `coord`(폴리곤 중심좌표)를 기준으로 한다.

## 판정 기준 — 건물 전체 호실 (1층만 보지 않는다)

예측 `status` 의 분모 `capacity` 가 **건물 전체 호수**(건축물대장 호수 또는 층수×2)이므로,
라벨도 전체 호실 기준이어야 채점이 성립한다. 1층만 보고 판정하면 상층 공실이 있는 건물이
일괄 `영업` 으로 라벨되어 정확도가 체계적으로 깎인다.

거리뷰에서 **간판·층별 안내판·창문/블라인드·임대 현수막**으로 상층부까지 판정할 것.

| label_actual | 의미 |
|---|---|
| `공실` | 영업 중인 호실이 없거나 사실상 전무 (전층 공실·임대 현수막) |
| `부분공실` | 영업 호실과 빈 호실이 섞여 있음 |
| `영업` | 빈 호실이 없거나 거의 없음 |
| `불명` | 거리뷰 미제공·가림·신축 등으로 판정 불가 → 채점 제외 |

## 대상 30동

| # | 지번 | 건물(상호) | 예측 | 공실률 | 층 | 지도 |
|---|---|---|---|---|---|---|
| 1 | 신사동 512-18 | — (0/10호) | empty | 100.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20512-18) |
| 2 | 신사동 534-6 | 제 (6/8호) | partial | 25.0% | 4F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20534-6) |
| 3 | 신사동 544-4 | — (1/6호) | high | 83.3% | 3F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20544-4) |
| 4 | 신사동 566-8 | 주은빌딩 (9/10호) | full | 10.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20566-8) |
| 5 | 신사동 540-21 | 지 (1/8호) | high | 87.5% | 4F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20540-21) |
| 6 | 신사동 547 | 영화빌딩 (1/10호) | high | 90.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20547) |
| 7 | 신사동 521-1 | — (3/10호) | high | 70.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20521-1) |
| 8 | 신사동 566-6 | 샤론빌딩 (4/8호) | partial | 50.0% | 0F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20566-6) |
| 9 | 신사동 565-3 | 조양빌딩 (25/25호) | full | 0.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20565-3) |
| 10 | 신사동 512 | — (0/8호) | empty | 100.0% | 4F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20512) |
| 11 | 신사동 546-11 | — (0/4호) | empty | 100.0% | 2F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20546-11) |
| 12 | 신사동 512-12 | — (4/8호) | partial | 50.0% | 4F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20512-12) |
| 13 | 신사동 549-9 | — (8/8호) | full | 0.0% | 3F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20549-9) |
| 14 | 신사동 536-6 | — (1/8호) | high | 87.5% | 4F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20536-6) |
| 15 | 신사동 513-2 | — (0/12호) | empty | 100.0% | 6F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20513-2) |
| 16 | 신사동 568-1 | — (0/8호) | empty | 100.0% | 4F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20568-1) |
| 17 | 신사동 561-30 | 춘곡빌딩 (5/10호) | partial | 50.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20561-30) |
| 18 | 압구정동 11-1 | — (0/12호) | empty | 100.0% | 6F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%95%95%EA%B5%AC%EC%A0%95%EB%8F%99%2011-1) |
| 19 | 신사동 545-19 | — (0/4호) | empty | 100.0% | 2F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20545-19) |
| 20 | 신사동 519-1 | 고황빌딩 (14/14호) | full | 0.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20519-1) |
| 21 | 신사동 562-6 | — (0/6호) | empty | 100.0% | 3F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20562-6) |
| 22 | 신사동 523-33 | 덕호빌딩 (7/7호) | full | 0.0% | 6F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20523-33) |
| 23 | 신사동 554-13 | — (4/6호) | partial | 33.3% | 3F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20554-13) |
| 24 | 압구정동 10-12 | — (0/14호) | empty | 100.0% | 7F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%95%95%EA%B5%AC%EC%A0%95%EB%8F%99%2010-12) |
| 25 | 신사동 550-6 | — (0/2호) | empty | 100.0% | 1F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20550-6) |
| 26 | 신사동 556-7 | — (0/6호) | empty | 100.0% | 3F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20556-7) |
| 27 | 신사동 507-7 | 조각집하이즈빌딩 (3/12호) | high | 75.0% | 6F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20507-7) |
| 28 | 신사동 553-22 | 모닝빌 (2/10호) | high | 80.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20553-22) |
| 29 | 신사동 513-1 | — (0/10호) | empty | 100.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20513-1) |
| 30 | 신사동 509-1 | 정빌딩 (4/10호) | high | 60.0% | 5F | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20509-1) |