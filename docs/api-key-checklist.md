# API 키 발급 체크리스트 (어디서·어떻게)

> §7 `.env` 체크리스트의 각 키를 **어디서 가져오는지** 한 장으로 정리. 며칠에 걸쳐 진행해도 되도록 상태 칸을 둔다. 상세 응답필드는 [api-keys-and-specs.md](api-keys-and-specs.md).
>
> ⚠️ 발급받은 키는 **이 문서/채팅에 붙여넣지 말 것.** 오직 로컬 `.env`(gitignore됨)에만. `.env`는 `data/.env.example`·`apps/frontend/.env.example`을 복사해 만든다.

## 진행 요약 (2026-07-04 기준)
- [x] 공공데이터포털 회원가입 + `상가(상권)정보(15012005)` 활용신청
- [x] 공공데이터포털 `건축HUB 건축물대장정보(15134735)` 활용신청 ← ⚠️ 프로브는 `15044713` 기준(§1 참고)
- [ ] 공공데이터포털 **Decoding 인증키**를 `data/.env`에 입력
- [ ] 서울 열린데이터광장 인증키
- [ ] 통계청 SGIS consumer_key/secret
- [ ] 네이버 NCP Maps Client ID (+도메인 등록)
- [ ] (선택) 네이버 개발자센터 검색/데이터랩

---

## 1. `DATA_GO_KR_SERVICE_KEY` — 공공데이터포털 (키 1개, 여러 API 공용)
- **사이트**: [www.data.go.kr](https://www.data.go.kr)
- **로그인**: 일반 회원가입(이메일) 또는 간편로그인
- **발급 경로**:
  1. 원하는 API 상세페이지에서 **[활용신청]** → 활용목적 입력 → 신청 (대부분 **자동승인**)
  2. **마이페이지 > 데이터활용 > 인증키 발급현황**에서 **일반 인증키(Decoding)** 복사
- **넣을 곳**: `data/.env` → `DATA_GO_KR_SERVICE_KEY=` (한 줄, 두 API 공용)
- **활용신청할 API 목록**(같은 키가 각각에 인가됨):
  - [x] 소상공인 상가(상권)정보 — [15012005](https://www.data.go.kr/data/15012005/openapi.do)
  - [ ] 건축물대장정보 — **권장 [15044713](https://www.data.go.kr/data/15044713/openapi.do)** (프로브와 일치) / 또는 신청한 건축HUB [15134735](https://www.data.go.kr/data/15134735/openapi.do)
  - [ ] (선택) 부동산원 임대동향 — [15002275](https://www.data.go.kr/data/15002275/openapi.do)
- **확인**(브라우저): `http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius?serviceKey={디코딩키}&radius=400&cx=127.0230&cy=37.5205&type=json&numOfRows=5&pageNo=1`

## 2. `SEOUL_OPENAPI_KEY` — 서울 열린데이터광장 (유동인구)
- **사이트**: [data.seoul.go.kr](https://data.seoul.go.kr)
- **로그인**: 회원가입(이메일)
- **발급 경로**: 상단 **[Open API] > 인증키 신청/관리** → 신청 정보 입력 → **즉시 발급**
- **넣을 곳**: `data/.env` → `SEOUL_OPENAPI_KEY=`
- **확인**: `http://openapi.seoul.go.kr:8088/{KEY}/json/SPOP_LOCAL_RESD_DONG/1/5/`

## 3. `SGIS_CONSUMER_KEY` / `SGIS_CONSUMER_SECRET` — 통계청 SGIS (인구밀도)
- **사이트**: [sgis.kostat.go.kr/developer](https://sgis.kostat.go.kr/developer) *(국가데이터처 이관: sgis.mods.go.kr)*
- **로그인**: 회원가입
- **발급 경로**: **개발지원센터 > 서비스 신청** → 약관동의 → 정보입력 → **테스트키 즉시발급**(`consumer_key`+`consumer_secret` 2개)
- **넣을 곳**: `data/.env` → `SGIS_CONSUMER_KEY=` / `SGIS_CONSUMER_SECRET=`
- **특이**: 키 2개로 먼저 accessToken(4h) 발급 후 데이터 호출(2단계). 상세 §3.

## 4. `VITE_NAVER_MAPS_KEY_ID` — 네이버 NCP Maps (지도 베이스, 필수)
- **사이트**: [console.ncloud.com](https://console.ncloud.com) (네이버 클라우드 플랫폼)
- **로그인**: NCP 회원가입 ⚠️ **휴대폰 인증 + 결제수단 등록** 필요(무료 쿼터 내 과금無)
- **발급 경로**: **Services > Application(Maps) 등록** → **Web 서비스 URL에 `http://localhost:5173` 등록**(필수) → **Client ID(=ncpKeyId)** 발급
- **넣을 곳**: `apps/frontend/.env` → `VITE_NAVER_MAPS_KEY_ID=`
- **주의**: 도메인 미등록 시 지도 인증오류. 배포 도메인도 추후 추가 등록.

## 5. `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` — 네이버 개발자센터 (선택: 검색·데이터랩)
- **사이트**: [developers.naver.com](https://developers.naver.com)
- **로그인**: 네이버 아이디
- **발급 경로**: **Application > 애플리케이션 등록** → 사용 API에 **검색 + 데이터랩(검색어트렌드)** 체크 → Client ID/Secret 발급
- **넣을 곳**: `data/.env` → `NAVER_CLIENT_ID=` / `NAVER_CLIENT_SECRET=`
- **참고**: NCP Maps(4번)와 **다른 사이트**. 지도=NCP콘솔, 검색/트렌드=개발자센터.

## (키 아님) GIS건물통합정보 — 건물 폴리곤
- **사이트**: [data.go.kr/data/15083092](https://www.data.go.kr/data/15083092) → **파일데이터 다운로드**(강남구 분) — 인증키 불필요.

---

## 한눈에 — 사이트 매핑
| 키 | 사이트 | 로그인 | 승인 |
|---|---|---|---|
| `DATA_GO_KR_SERVICE_KEY` | data.go.kr | 이메일 | 대개 자동 |
| `SEOUL_OPENAPI_KEY` | data.seoul.go.kr | 이메일 | 즉시 |
| `SGIS_CONSUMER_KEY/SECRET` | sgis.kostat.go.kr | 이메일 | 즉시(테스트키) |
| `VITE_NAVER_MAPS_KEY_ID` | console.ncloud.com | NCP(휴대폰+결제) | 즉시 |
| `NAVER_CLIENT_ID/SECRET` | developers.naver.com | 네이버ID | 즉시 |

## 우선순위 (막히면 위에서부터)
1. `DATA_GO_KR_SERVICE_KEY` → 건물 공실 D1 프로브 실행 관문
2. `VITE_NAVER_MAPS_KEY_ID` → MapShell 지도 렌더
3. `SEOUL_OPENAPI_KEY`(유동인구) → 4. `SGIS_*`(인구밀도) → 5. `NAVER_*`(선택)
