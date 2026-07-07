# API 키 발급 후 진행 단계 (검증 → 수집 → 가공 → 연결 → 확인)

> [api-key-checklist.md](api-key-checklist.md)로 키를 다 채운 **다음**에 밟을 순서. 담당(사용자/개발)과 분기점을 명시한다. 상위 로드맵은 [spaceos-vibe-build-sequence.md](spaceos-vibe-build-sequence.md), 건물 공실 설계는 [poc-building-vacancy.md](poc-building-vacancy.md).

## 한눈 요약
```
[사용자] 키 채움
   ↓
STEP1 키 검증 ─────▶ 지도 뜸 (회의 1번 ✅)
   ↓
STEP2 D1 프로브 실행 → 로그 전달   ← 여기서 개발로 인계
   ↓
STEP3 Bronze 수집 콜렉터 구현
   ↓
STEP4 Gold + GeoJSON, /heatmap 실데이터 교체
   ↓
STEP5 백엔드 기동 (⚠️ Python 3.11 필요)
   ↓
STEP6 MapShell 실데이터 렌더 (회의 2·3번 ✅)
   ↓
STEP7 정합 검증 (PoC exit)
```
**핵심 분기점 2개** — ① STEP2에서 D1 프로브 출력을 넘기면 STEP3~4는 개발이 진행. ② STEP5의 Python 3.11은 백엔드 실서빙 전제(미리 설치 권장).

---

## STEP 1. 키 검증 — 사용자 (5~10분)
채운 키가 실제로 되는지 하나씩 확인. 여기서 걸러야 뒤가 안 막힌다.

| 키 | 확인 방법 | 성공 신호 |
|---|---|---|
| `DATA_GO_KR_SERVICE_KEY` | 상가 테스트 URL을 브라우저에 | JSON 응답 |
| `VITE_NAVER_MAPS_KEY_ID` | `cd apps/frontend && npm run dev` → "가로수길 Page" | 지도 타일 렌더(안내 오버레이 사라짐) |
| `SEOUL_OPENAPI_KEY` | `openapi.seoul.go.kr:8088/{KEY}/json/SPOP_LOCAL_RESD_DONG/1/5/` | JSON |
| `SGIS_*` | `auth/authentication.json?consumer_key=&consumer_secret=` | accessToken 반환 |

상가 테스트 URL:
```
http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius?serviceKey={디코딩키}&radius=400&cx=127.0230&cy=37.5205&type=json&numOfRows=5&pageNo=1
```
→ 이 시점에 **회의 1번(지도 크게)이 실물 완성**.

## STEP 2. D1 관통 검증 — 사용자 실행 → 로그 인계
```powershell
cd spaceos/data
python probe_garosu_d1.py     # DATA_GO_KR_SERVICE_KEY 사용
```
- 확인점: 상가정보 실제 필드, `bdMgtSn` 존재, 지번→건축물대장 capacity 산출 여부
- ✅ 건축물대장 API 확정 — **15134735(건축HUB, BldRgstHubService)**. 구 15044713은 서비스 종료(2026-07 확인). 프로브 `BASE_BLD`는 HUB 경로로 교체 완료.
- **출력 로그를 개발에 전달** → 실제 스키마 확정 후 STEP3 착수.

## STEP 3. Bronze 수집 콜렉터 구현 — 개발 (D1 결과 기반)
| 데이터 | 파일 | 내용 |
|---|---|---|
| 건물 공실 | `data/collectors/building_vacancy.py` (신규) | 상가 반경수집 → `bdMgtSn` 그룹 → 지번 대장조회 → occupancy |
| 유동인구 | `data/collectors/living_population.py` 확장 | 서울 생활인구 신사동 시간대별 |
| 인구밀도 | 신규 콜렉터 | SGIS 2단계(auth→population) |
| 임대·거시공실 | 신규 로더 | 부동산원 CSV(키 무관, 파일 다운로드) |

## STEP 4. Silver/Gold 가공 → GeoJSON — 개발
- 점포↔건물 매칭 결과를 `building_vacancy` Gold로 산출
- 백엔드 `/heatmap/buildings` **샘플 → 실데이터 교체** (`apps/backend/app/services/building_vacancy.py`)
- PoC 단계는 PostGIS 없이 파일/메모리로 시작 가능

## STEP 5. 백엔드 실서빙 — ⚠️ Python 3.11 필요
- 현재 PC는 3.8/3.14뿐 → 기존 코드(3.9+ 문법)가 임포트 실패.
- **Python 3.11 설치 → `cd apps/backend && pip install -r requirements.txt` → `uvicorn app.main:app --reload`**
- 그래야 프론트가 Vite 프록시로 실제 GeoJSON 수신.

## STEP 6. 프론트 실데이터 확인 — 개발 + 사용자
- MapShell이 실제 건물 폴리곤 / 유동인구 히트맵 / 인구밀도·임대 코로플레스 렌더
- **회의 2·3번(4데이터 표현)이 실데이터로 완성**

## STEP 7. 정합 검증 (PoC exit) — 개발
- 건물 추정 공실률을 구 집계 → **부동산원 공실률과 ±5%p**
- 로드뷰 샘플 20~30건 라벨로 status 정확도 **70%+**
- 가로수길 특이점: 가두상권(1층) vs 집합상가 분리 집계 (poc-building-vacancy.md §5 참조)

---

## 담당 요약
| STEP | 담당 | 산출/결과 |
|---|---|---|
| 1 키 검증 | 사용자 | 지도 렌더 + 키 유효 확인 |
| 2 D1 프로브 | 사용자 → 개발 | 실제 스키마 로그 |
| 3 콜렉터 | 개발 | Bronze 수집 |
| 4 Gold/GeoJSON | 개발 | `/heatmap` 실데이터 |
| 5 백엔드 기동 | 사용자(환경) | Python 3.11 서버 |
| 6 프론트 확인 | 개발+사용자 | 실데이터 지도 |
| 7 정합 검증 | 개발 | PoC exit 판정 |
