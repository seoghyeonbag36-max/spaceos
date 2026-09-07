---
name: verify
description: SpaceOS 변경분을 실제 표면에서 확인하는 절차 — 정적 3종(pytest·build·torch) + 로컬 앱을 띄워 API·Vite 프록시·지도 픽셀까지. 작업을 마쳤을 때.
---

# SpaceOS 검증 레시피

## 0. 정적 검증 3종 — 변경 직후 항상

```bash
cd apps/backend && pytest -q                 # 백엔드 테스트/임포트
cd apps/frontend && npm run build            # 프론트 타입체크 + 빌드
cd ml && python -c "import torch; print('torch', torch.__version__)"
```

무인으로 한 번에: `python scripts/run_full_verify.py`
(→ `reports/full_verify.json` + `reports/logs/verify_*.log`)

실패하면 원인과 수정안을 제시하고 통과까지 반복한다. `CLAUDE.md` 규칙도 같이 본다 —
경로 · 타입힌트 · 한국어 주석 · 더미의 `TODO` 표기.

**아래는 정적 검증이 잡지 못하는 것**을 위한 절차다. 이 저장소에서 실제로 밟은 함정은
전부 "테스트는 초록인데 화면·데이터가 틀린" 자리에서 나왔다.

## 띄우기

```powershell
# 터미널 1 — 백엔드 (127.0.0.1:8000)
cd apps\backend ; py -3.11 -m uvicorn app.main:app --port 8000
# 터미널 2 — 프론트 (localhost:5173, /api → :8000 프록시)
cd apps\frontend ; npm run dev
```

`--reload` 없이 띄우면 코드 수정이 반영되지 않는다. 서비스 모듈을 고쳤으면 재기동할 것.

## 표면 고르기

| 변경 위치 | 표면 | 두드리는 법 |
|---|---|---|
| `apps/backend/**` | HTTP 소켓 | `curl.exe`로 `:8000` 직접 |
| 프론트가 소비하는 API | Vite 프록시 이음매 | `:5173/api/v1/...` — 브라우저가 타는 실제 경로 |
| `apps/frontend/**` | 픽셀 | Playwright(python) + chromium 설치됨(2026-07-24) — 아래 참조 |
| `data/pipelines/**` | Gold 산출물 → API | 파이프라인 재실행 대신 서빙되는 payload를 검사 |

## 프론트 픽셀 검증 (Playwright)

`python -m playwright install chromium` 완료(2026-07-24). 백엔드+Vite 를 띄운 뒤:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    pg = p.chromium.launch().new_page(viewport={'width':1440,'height':900})
    pg.goto('http://localhost:5173/', wait_until='networkidle')
    pg.get_by_role('button', name='주요 Platform').click()
    pg.screenshot(path='...png')
```

레이아웃 회귀는 스크린샷보다 DOM 측정이 확실하다. 스크롤 구조를 볼 때:

```js
[...document.querySelectorAll('*')].filter(el => {
  const oy = getComputedStyle(el).overflowY;
  return (oy === 'auto' || oy === 'scroll') && el.scrollHeight > el.clientHeight + 1;
})   // 창 스크롤 하나만 있어야 하므로 결과는 빈 배열이어야 한다
```

## 함정 (실제로 밟은 것들)

- **PowerShell 5.1 `Invoke-WebRequest`는 한글을 깨뜨린다.** FastAPI가 `application/json`에
  charset을 안 붙여 PS가 ISO-8859-1로 디코딩한다. 와이어는 정상. 확인하려면:
  ```powershell
  $wc = New-Object System.Net.WebClient; $wc.Encoding = [System.Text.Encoding]::UTF8
  $wc.DownloadString($url) | ConvertFrom-Json
  ```
- **상태 코드 프로브는 `curl.exe`로.** `Invoke-WebRequest`의 catch 블록에서
  `$_.Exception.Response`가 null이라 404/422를 못 읽는다.
  `curl.exe -s -w "HTTP:%{http_code}"` 를 쓸 것.
- **`py -3.11`** 로 부른다. `python`은 다른 버전일 수 있다.
- **전역 CSS가 로드되는지부터 확인할 것.** `styles/tokens.css` 는 오래 MapShell.tsx
  (당시 라우팅되지 않던 컴포넌트)에서만 import 돼 있어 리셋이 죽어 있었다 — CSS 를 고쳐도
  화면이 안 바뀐다. 빌드 산출물에서 규칙이 실제로 나오는지 보는 게 빠르다:
  `grep -o "html,body{[^}]*}" dist/assets/*.css`
- **네이버 지도 컨테이너는 `inset:0` 만으로 크기가 잡히지 않는다.** SDK 가 초기화하면서
  컨테이너의 `position` 을 `relative` 로 덮어써 `inset` 이 사이징이 아니라 오프셋으로
  해석되고, 높이가 0 으로 접혀 지도가 통째로 사라진다(2026-08-01 실측). `width/height:100%`
  를 같이 준다. 스크린샷만 보면 "지도 키 문제"로 오진하기 쉬우니 DOM 으로 재라:
  `document.querySelector('.map-canvas').getBoundingClientRect()`

## 공실 레이어(`/api/v1/heatmap/buildings`) 검증

```powershell
curl.exe -s "http://localhost:5173/api/v1/heatmap/buildings?district=gangnam-garosugil"
```

- 거점 에일리어스 3종: `gangnam-garosugil` / `garosugil` / `sinsa` → 모두 200
- 미지원 거점 → 404, `district` 누락 → 422
- **features 수로 데이터 경로를 판별한다**: 800 = Gold 실데이터, 8 = 샘플 폴백
- Gold 원본: `data/gold/garosugil/page_building_master.geojson`
- 폴백 경로를 보려면 파일을 잠시 rename → 요청 → 되돌린다.
  `services/building_vacancy.py` 는 mtime 캐시라, 되돌리면 mtime이 같아 캐시가 그대로 산다.
  재로딩까지 보려면 `(Get-Item $gold).LastWriteTime = Get-Date` 로 mtime을 건드릴 것.
  **끝나면 원래 mtime을 복원**한다.

### payload에서 볼 것

`properties.source` 가 데이터 신뢰도를 가른다:

- `stores+ledger` — 상가정보 점포 매칭됨 (실측 기반)
- `polygon_only` — 매칭 없음. `active=0`, `capacity=floors×STORES_PER_FLOOR`(합성), `vacancy_rate=100.0` 고정

`polygon_only`를 섞은 채 평균 공실률을 논하지 말 것. `calibrate_vacancy.py` 도
`stores+ledger` 만으로 집계한다.

`properties.capacity_method` 는 분모의 근거를 가른다 — 이것도 섞으면 안 된다:

- `floor_ouln` — 층별개요 상업층. **거점 대표 집계는 이것만** 쓴다.
- `expos_units` — 전유부 실측(집합건물). **분모는 정밀하지만 분자가 비어 있다** — 상가정보가
  집합상가 **내부** 점포를 그 건물 bdMgtSn 으로 귀속시키지 못해 공실률이 78~86% 로 나온다.
  건물 수로는 소수인데 호실이 많아 **분모의 52~82%** 를 차지하는 거점이 있어, 섞으면 거점
  대표값이 통째로 무너진다(2026-08-01 앵커 대조: seoulsup 19.8% → 67.0%). 층·호 단위
  매칭(flrNo/hoNo) 전까지 대표 집계에서 뺀다.
- `floor_approx` — 지상 **전체** 층수 근사. 주거·사무 층까지 상가로 세어 분모가 부푼다.
  `mixed_vacancy_pct` 에만 섞여 있고 앵커 비교에 쓰면 안 된다.

> ⚠ `coverage.json` 의 `reference_vacancy_pct` 는 `expos_units` 를 포함한 구 기준이다.
> 현재 API 대표값(`services/gold_vacancy.py`)과 다르며, 대표값으로 인용하지 말 것.

앵커는 **거점별 R-ONE 중대형상가 공실률**이다(`calibration.json.anchor_pct`,
garosugil = 17.6%). 예전에 쓰던 공통 41.6% 는 부동산원 통계가 아니라 가로수길 가두
1층 실태조사(2024) 값을 잘못 표기한 것이라 2026-07-28 폐기했다.
API 는 `anchor_pct`/`anchor_gap_pp` 로 대조를 함께 내려보낸다 — **서빙 66거점 전부**가 앵커를
가진다(2026-09-05 기준 · `pppp_status.py` 의 `R-ONE 앵커 대조 보유` 게이트가 센다). 모집단이 달라(우리는 호실·전수, R-ONE 은 면적·표본) 격차 0 은 목표가 아니다.

**2026-08-30 전수 재측정**(TestClient 로 당시 54거점 `GET /heatmap/vacancy` 전부 호출):
격차 **-10.66 ~ +21.77%p** (최소 cheongdam -10.66 / 최대 nokdu +21.77 / garosugil -1.78).
가드레일 30%p 를 넘는 거점은 **0곳**이고 `pytest -k anchor` **3건 전부 통과**한다.

> 이 문단은 08-17 측정치(nokdu +34.55 / sharosugil 23.00 / garosugil +2.88, 테스트 실패
> 중)를 적고 있었다. 그 뒤 Gold 가 재빌드되며 값이 바뀌었는데 문서만 남아 있었다 —
> **이 저장소의 주된 실패 양식이 그대로 재현된 자리다.** 인용 전에 다시 재라:
> `python scripts/chain_status.py <slug>` 가 서빙과 같은 기준(`floor_ouln` 만)으로 찍는다.

⚠ `calibration.json` 의 `gap_pp` 필드를 인용하지 말 것 — 그건 집합건물을 포함한 혼합
추정(`estimated_vacancy_pct`) 기준이라 값이 훨씬 크다. 대표 집계 기준 격차는 API 가 준다.

## 66거점 전수는 손으로 돌지 않는다 — `scripts/screen_loop.py`

아래 절차는 **거점 하나**를 사람이 여는 방식이다. 거점 66 × 탭 4 = 264조합을 그렇게
돌 수는 없어서, 반복되는 부분만 떼어 무인 루프로 만들었다(2026-09-07).

```bash
# 백엔드(:8000) + Vite(:5173) 를 먼저 띄운 뒤
set PYTHONIOENCODING=utf-8
python -u scripts/screen_loop.py                            # 66거점 × 4탭
python -u scripts/screen_loop.py --hubs yeonnam,sinchon,hongdae
python -u scripts/screen_loop.py --self-check               # 브라우저 없이 판정부만
python -u scripts/screen_loop.py --hubs yeonnam --canary    # 없는 셀렉터를 넣어 실검사
```

거점마다 네 단계를 잰다 — S1 콘솔 에러·pageerror·API 5xx 0 / S2 지도 캔버스 + SDK 자식
/ S3 공실 폴리곤 수 > 0 · 결론 문장 · 거점 목록 · 상세패널(`.b-detail .b-name`) / S4 렌더 3초.
산출은 `reports/screen_loop.json` 과 **실패한 조합만** `reports/screens/*.png`.
조합마다 리포트를 다시 쓰므로 중간에 끊겨도 다시 부르면 이어 받는다.

경계 — 이 루프가 **하지 않는** 것은 아래 절차에 그대로 남는다:
- 층 스택·거리뷰(`.b-twin`)는 열지 않는다 → 아래 "건물 상세" 절이 계속 맡는다.
- Program 생성(`/marketing/generate`)은 부르지 않는다(Claude 실호출·크레딧).

⚠ **아직 실제 앱에 대고 돌린 적이 없다**(2026-09-07 기준 코드까지). 검증한 것은
판정부 자기검사(`--self-check`)·정적 셀렉터 대조(`scripts/test_screen_loop.py`)와,
앱 DOM 을 흉내낸 가짜 페이지에 대한 전 경로 실행이다. 첫 실행에서 지도 오버레이 계수가
0 으로 나오면 폴리곤이 SVG 가 아니라 canvas 로 그려진 것이다 — `screen_loop.py` 의
`MAP_JS` 한 곳만 고친다(원시 계수 paths/divs/canvases 를 같이 남기는 이유다).

## 지도 뷰(MapShell) 검증

⚠ **탭 이름이 바뀌었다(2026-09-06 실측).** 이 절은 `"지도"` 탭을 진입점이라고 적고 있었는데
그런 탭은 이제 없다 — 217d469 가 네비를 갈면서 **`"지도"` → `"Page"`** 가 됐고, 별도로
**`"거점"`**(HubExplorer) 이 새로 생겼다. 낡은 이름으로 `get_by_role` 을 부르면 30초 타임아웃만
난다. 현재 네비: `서울 · 거점 · Platform · Page · Posting · Program`.

| 탭 | 컴포넌트 | 무엇 |
|---|---|---|
| `Page` | MapShell | 공실 4레이어 + 건물 클릭 패널 + 층 스택·거리뷰 (종전 "지도") |
| `거점` | HubExplorer | 거점 목록 + 실측범위 경계 + 요약 |

지도는 더 이상 MapShell 이 만들지 않는다 — `MapHost` 가 앱 전체에서 하나만 만들어 들고,
탭 전환 때 `visibility` 로 숨긴다. 그래서 **탭을 옮겨도 언마운트되지 않는다**(카메라 유지).

```python
pg.get_by_role('button', name='Page').first.click()
pg.wait_for_timeout(9000)          # 네이버 SDK + 폴리곤 렌더까지 넉넉히
pg.select_option('.hub-select', 'garosugil')
```

- `.hub-select` 옵션 수 = 서빙 거점 수(**2026-09-06 실측 66**)
- `.b-item` 수 = 그 거점 건물 수(**가로수길 840**) — 0 이면 API 404 폴백을 탄 것.
  `/heatmap/buildings` payload 의 `features` 수와 **같아야 한다**(다르면 필터가 먹은 것)
- `.map-canvas` 의 높이가 0 이 아닌지 반드시 확인(위 함정 참조)
- ⚠ **`.b-name` 은 목록행과 상세패널 양쪽에 있다.** `querySelector('.b-name')` 은 목록 첫 행을
  집으므로 선택한 건물을 확인하려면 **`.b-detail .b-name`** 으로 좁힐 것. 이걸 모르면 패널이
  엉뚱한 건물을 그린다고 오진한다(2026-09-06 실제로 그렇게 한 번 헛짚었다)

### 건물 상세(층 스택 + 거리뷰) — 게이트가 선언만 하는 자리

`pppp_status.py` 의 `지도·건물상세 표면` 은 **선언 게이트**라 여기서만 참·거짓이 갈린다.
층이 하나뿐인 건물을 고르면 스택이 한 줄만 나와 증거가 얇으니, **세 종류가 다 나오는
건물**을 고른다(payload 에서 `com_floors` 길이가 크고 `active < capacity` 인 것).

```python
i = pg.evaluate("t => [...document.querySelectorAll('.b-item')].findIndex(e => e.innerText.includes(t))", '동남빌딩')
pg.query_selector_all('.b-item')[i].click()
pg.click('.b-twin')                # 「층별 공실 · 거리뷰 보기」
pg.wait_for_timeout(9000)          # 거리뷰 파노라마까지
```

볼 것 — 2026-09-06 가로수길 동남빌딩 실측값:

- `.fstack-row` **7행** · 색 **3종**(`vacant` 주황 / `occupied` 초록 / `uncertain` 노랑)
- `.sview-canvas` 의 자식이 **1 이상**(0 이면 파노라마가 안 붙은 것 — fd04852 가 잡은 결함)
- `.sview-meta` 에 **촬영일**이 있을 것(`2026-01-20 촬영 · … 에서 9m`). 촬영일 없이 거리뷰만
  그리면 게이트 주장이 깨진다 — 거리뷰는 공실 판정의 근거가 아니라는 표식이 그 문구다
