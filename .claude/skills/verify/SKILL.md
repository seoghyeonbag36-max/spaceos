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
| `apps/frontend/**` | 픽셀 | Playwright 미설치. 필요 시 설치 필요 |
| `data/pipelines/**` | Gold 산출물 → API | 파이프라인 재실행 대신 서빙되는 payload를 검사 |

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
- `polygon_only` — 매칭 없음. `active=0`, `capacity=floors×2`(합성), `vacancy_rate=100.0` 고정

`polygon_only`를 섞은 채 평균 공실률을 논하지 말 것. `calibrate_vacancy.py` 도
`stores+ledger` 만으로 집계한다. 부동산원 가두상권 앵커는 41.6%.
