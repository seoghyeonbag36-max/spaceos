# 네이버 지도 / 네이버페이 연동

> SpaceOS의 "디지털 스킨십" 채널은 네이버 생태계다. 지도(첫 접점·위치 시각화)와 페이(성공보수·구독 결제)를 연동한다.
> ⚠️ 키 값은 모두 `.env`(.gitignore 보호)에 저장하고 코드에 하드코딩하지 않는다.

## 1. 네이버 지도 (NAVER Cloud Platform — Maps)

네이버 지도는 NAVER Cloud Platform 콘솔에서 Application을 등록해 사용한다. (Maps > Application)

### 1.1 Web Dynamic Map (프런트 JS v3)
```html
<!-- 2025년부터 파라미터가 ncpClientId → ncpKeyId 로 변경됨 (둘 다 한시적 호환) -->
<script src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=YOUR_KEY_ID"></script>
```
- 콘솔에서 **Web 서비스 URL**에 개발 도메인 등록 필수 (예: `http://localhost:5173`).
- 프런트 코드: `apps/frontend/src/lib/naverMap.ts` (래퍼 스텁 제공).

### 1.2 REST API (백엔드 — Geocoding/Directions)
| 기능 | 엔드포인트 |
|------|-----------|
| Geocoding(주소→좌표) | `https://maps.apigw.ntruss.com/map-geocode/v2/geocode` |
| Reverse Geocoding | `https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc` |
| Directions(경로) | `https://maps.apigw.ntruss.com/map-direction/v1/driving` |

인증 헤더(REST):
```
X-NCP-APIGW-API-KEY-ID: {Client ID}
X-NCP-APIGW-API-KEY:    {Client Secret}
```
- 용도: 크롤링한 상가 **주소 → 좌표 정규화**(Silver 레이어), 상권 내 동선 분석.
- 백엔드 코드: `apps/backend/app/services/naver_geo.py`.

## 2. 네이버페이 (NAVER Pay — 결제형 연동)

개발자센터: https://developer.pay.naver.com/ — 가맹점 등록 후 사용.

결제 플로우(결제형 / 주문형):
```
① 결제 예약(reserve)  →  ② 사용자 인증(네이버페이 창)  →  ③ 결제 승인(apply, paymentId)  →  ④ 결제내역/정산 조회
```
| 단계 | 엔드포인트(개념) | SpaceOS 용도 |
|------|----------------|-------------|
| 예약 | `/payments/v2.2/reserve` | B2B 구독료(DaaS), 리포트 단건(5만원) 결제 시작 |
| 승인 | `/payments/v2.2/apply/payment` | `paymentId`로 실제 승인 |
| 조회 | `/payments/v2.2/list/...` | 정산·거래완료 내역 → 성공보수 정산 |

- 백엔드 코드: `apps/backend/app/api/v1/payments.py` (스텁 제공).
- 결제 모델: ⑴ DaaS 월 구독, ⑵ 리포트 단건, ⑶ 공실 매칭 성공보수.

## 3. 환경변수(.env) 키

```bash
# 네이버 지도
NAVER_MAPS_KEY_ID=...        # 프런트 ncpKeyId 와 동일 (VITE_NAVER_MAPS_KEY_ID 로도)
NAVER_MAPS_CLIENT_SECRET=... # REST 호출용
# 네이버페이
NAVER_PAY_CLIENT_ID=...
NAVER_PAY_CLIENT_SECRET=...
NAVER_PAY_CHAIN_ID=...
```
