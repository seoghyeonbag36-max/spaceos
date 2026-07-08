# 로드뷰 검증 샘플 30동 — 라벨은 roadview_sample.csv 에 기입

링크 클릭 → 네이버 지도에서 해당 건물 → **거리뷰**로 1층 공실 여부 확인.
`label_actual` 값: `공실`(전층/1층 명백 공실) · `부분공실` · `영업` · `불명`

| # | 건물 | 예측 | 공실률 | 지도 |
|---|---|---|---|---|
| 1 | 신사동 512-18 (0/10호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20512-18) |
| 2 | 제 (6/8호) | partial | 25.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%A0%9C) |
| 3 | 신사동 544-4 (1/6호) | high | 83.3% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20544-4) |
| 4 | 주은빌딩 (9/10호) | full | 10.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%A3%BC%EC%9D%80%EB%B9%8C%EB%94%A9) |
| 5 | 지 (1/8호) | high | 87.5% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%A7%80) |
| 6 | 영화빌딩 (1/10호) | high | 90.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%98%81%ED%99%94%EB%B9%8C%EB%94%A9) |
| 7 | 신사동 521-1 (3/10호) | high | 70.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20521-1) |
| 8 | 샤론빌딩 (4/8호) | partial | 50.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%83%A4%EB%A1%A0%EB%B9%8C%EB%94%A9) |
| 9 | 조양빌딩 (25/25호) | full | 0.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%A1%B0%EC%96%91%EB%B9%8C%EB%94%A9) |
| 10 | 신사동 512-0 (0/8호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20512-0) |
| 11 | 신사동 546-11 (0/4호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20546-11) |
| 12 | 신사동 512-12 (4/8호) | partial | 50.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20512-12) |
| 13 | 신사동 549-9 (8/8호) | full | 0.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20549-9) |
| 14 | 신사동 536-6 (1/8호) | high | 87.5% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20536-6) |
| 15 | 신사동 513-2 (0/12호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20513-2) |
| 16 | 신사동 568-1 (0/8호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20568-1) |
| 17 | 춘곡빌딩 (5/10호) | partial | 50.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%B6%98%EA%B3%A1%EB%B9%8C%EB%94%A9) |
| 18 | 압구정동 11-1 (0/12호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%95%95%EA%B5%AC%EC%A0%95%EB%8F%99%2011-1) |
| 19 | 신사동 545-19 (0/4호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20545-19) |
| 20 | 고황빌딩 (14/14호) | full | 0.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EA%B3%A0%ED%99%A9%EB%B9%8C%EB%94%A9) |
| 21 | 신사동 562-6 (0/6호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20562-6) |
| 22 | 덕호빌딩 (7/7호) | full | 0.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EB%8D%95%ED%98%B8%EB%B9%8C%EB%94%A9) |
| 23 | 신사동 554-13 (4/6호) | partial | 33.3% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20554-13) |
| 24 | 압구정동 10-12 (0/14호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%95%95%EA%B5%AC%EC%A0%95%EB%8F%99%2010-12) |
| 25 | 신사동 550-6 (0/2호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20550-6) |
| 26 | 신사동 556-7 (0/6호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20556-7) |
| 27 | 조각집하이즈빌딩 (3/12호) | high | 75.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%A1%B0%EA%B0%81%EC%A7%91%ED%95%98%EC%9D%B4%EC%A6%88%EB%B9%8C%EB%94%A9) |
| 28 | 모닝빌 (2/10호) | high | 80.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EB%AA%A8%EB%8B%9D%EB%B9%8C) |
| 29 | 신사동 513-1 (0/10호) | empty | 100.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%8B%A0%EC%82%AC%EB%8F%99%20513-1) |
| 30 | 정빌딩 (4/10호) | high | 60.0% | [열기](https://map.naver.com/p/search/%EC%84%9C%EC%9A%B8%20%EA%B0%95%EB%82%A8%EA%B5%AC%20%EC%A0%95%EB%B9%8C%EB%94%A9) |