---
name: verify
description: SpaceOS 로컬 앱을 띄우고 변경분을 실제 표면에서 관찰하는 절차 (백엔드 API / Vite 프록시 / 지도 UI).
---

# SpaceOS 검증 레시피

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
API 는 `anchor_pct`/`anchor_gap_pp` 로 대조를 함께 내려보낸다 — **54/54 전 거점**이 앵커를
가지며(2026-08-17 `calibrate_vacancy` 재산출) 격차는 **-5.16 ~ +34.55%p** 다
(`GET /heatmap/vacancy` 전수 실측. 최소 cheongdam -5.16 / 최대 nokdu +34.55 /
garosugil +2.88). 대조가 안 되던 거점은 이제 없다. 모집단이 달라(우리는 호실·전수,
R-ONE 은 면적·표본) 격차 0 은 목표가 아니다.

🔴 **nokdu +34.55%p 는 가드레일(30%p)을 넘어 `test_gold_anchor_comparison_attached` 가
실패 중이다.** 검증에서 이 실패를 만나면 "환경 문제"가 아니라 **알려진 미해결 이상치**다
(2위 sharosugil 23.00p 와 11.5%p 벌어진 단독 이상치). → [docs/feature-page.md §0](../../../docs/feature-page.md)

⚠ `calibration.json` 의 `gap_pp` 필드를 인용하지 말 것 — 그건 집합건물을 포함한 혼합
추정(`estimated_vacancy_pct`) 기준이라 값이 훨씬 크다. 대표 집계 기준 격차는 API 가 준다.

## 지도 뷰(MapShell) 검증

App.tsx 네비 **"지도"** 탭이 진입점이다(2026-08-01 연결). 거점 선택은 실측 거점만 나온다
— **2026-08-17 대장 완주로 54곳 전부**가 목록에 뜬다(종전에는 미수집분이 빠져 있었다).

```python
pg.get_by_role('button', name='지도').click()
pg.wait_for_timeout(7000)          # 네이버 SDK + 폴리곤 렌더까지 넉넉히
pg.locator('.hub-select').select_option('hongdae')
```

- `.hub-select` 옵션 수 = `vacancy_source === "gold"` 인 거점 수(2026-08-15 현재 40)
- `.b-item` 수 = 그 거점 건물 수(가로수길 836, 홍대 1,329) — 0 이면 API 404 폴백을 탄 것
- `.map-canvas` 의 높이가 0 이 아닌지 반드시 확인(위 함정 참조)
