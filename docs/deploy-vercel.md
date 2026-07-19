# Vercel 배포 가이드

프론트(Vite 정적 빌드) + 백엔드(FastAPI, Python 서버리스 함수)를 **Vercel 프로젝트 하나**로 배포한다.
로컬의 `localhost:5173`(프론트) + `localhost:8000`(백엔드) 구성이 배포에서는
`https://<프로젝트>.vercel.app` 단일 도메인으로 합쳐진다 — `/api/*` 요청은 서버리스 FastAPI가 받는다.

## 구성 파일 (이미 셋팅됨 — spaceos/ 루트)

| 파일 | 역할 |
|------|------|
| `vercel.json` | 빌드 명령(`apps/frontend` 빌드) + 산출물 경로 + `/api/*`, `/health` → 서버리스 함수 rewrite |
| `api/index.py` | 서버리스 진입점 — `apps/backend/app.main:app`(ASGI)을 그대로 노출 |
| `requirements.txt` | 서버리스 최소 의존성 (fastapi/pydantic/pydantic-settings) |
| `.vercelignore` | 대용량·무관 파일 업로드 제외 (data, html, ml, 문서 등) |

## 배포 절차 (CLI — 이 저장소는 git 미연동이므로 CLI 업로드 방식)

```powershell
npm i -g vercel                # 최초 1회
cd C:\Users\USER\Documents\Claude\Projects\SpaceOS\spaceos
vercel login                   # 최초 1회 (브라우저 인증)
vercel                         # 프리뷰 배포 — 프로젝트 생성 질문에 기본값(현재 디렉토리 루트) 그대로
vercel --prod                  # 프로덕션 배포
```

> 프로젝트 생성 질문 중 "In which directory is your code located?" 는 `./` (spaceos 루트) 그대로.
> 빌드 설정은 vercel.json 이 우선하므로 프레임워크 자동감지 값은 무시해도 된다.

## 환경변수 (필수 1개)

네이버 지도 키는 **빌드 타임** 변수라 Vercel 에 등록해야 지도가 뜬다:

```powershell
vercel env add VITE_NAVER_MAPS_KEY_ID production   # 값: apps/frontend/.env 의 키와 동일
vercel env add VITE_NAVER_MAPS_KEY_ID preview
vercel --prod                                       # env 추가 후 재배포
```

선택(백엔드): `LLM_API_KEY`(Program LLM 생성 — requirements.txt 의 anthropic 주석 해제 필요),
`POSTING_COPILOT_URL/KEY`(Posting 코파일럿). 미설정 시 각각 규칙 기반/3-Tier 폴백으로 동작한다.

## 배포 후 반드시 할 것 — NCP 도메인 등록

NCP 콘솔 → Services > Maps > Application → **Web 서비스 URL** 에 배포 도메인 추가:

```
https://<프로젝트>.vercel.app
```

미등록 시 지도 타일이 인증오류로 표시되지 않는다 (localhost:5173 등록과 동일한 이유).

## 배포 확인 체크리스트

```powershell
curl.exe -s https://<프로젝트>.vercel.app/health                       # {"status":"ok",...}
curl.exe -s https://<프로젝트>.vercel.app/api/v1/commercial-districts   # 13거점 JSON
```

- `/` → 서울 25구 로드맵, "주요 Platform" 탭 → 13거점 대시보드 + 심층(히트맵 지도)
- 지도 타일 표시 여부 (안 뜨면 NCP 도메인 등록 확인)

## 배포판 제약 (의도된 것)

- `data/gold/` 미포함 → `/api/v1/heatmap/buildings` 는 샘플 폴백(8동) 응답.
  실데이터를 서빙하려면 `.vercelignore` 에서 `data/gold/garosugil` 만 예외 처리(`!/data/gold/garosugil/`)할 것.
- `html/` 미포함 → `/maps` 정적 대시보드는 서빙되지 않음 (main.py 가 존재 시에만 mount — 에러 없음).
- DB/Redis 미연동 (로컬과 동일 — 시드 데이터 서빙).
- git 연동 배포(푸시 자동 배포)를 원하면: `git init` 후 GitHub 업로드 → Vercel 대시보드에서
  Import → Root Directory 를 `spaceos` 로 지정하면 이 구성이 그대로 적용된다.
