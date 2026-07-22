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

## 배포 방식 (git 자동 배포 — 2026-07-19 전환 완료)

GitHub `seoghyeonbag36-max/spaceos` ↔ Vercel 프로젝트 `spaceos` 가 연결되어 있어
**`main` 에 푸시하면 자동으로 프로덕션 배포**된다. 수동 배포가 필요하면 `vercel --prod`.

- **프로덕션 URL**: https://spaceos-sandy.vercel.app
- Root Directory: `.` (저장소 루트가 spaceos 자체이므로 기본값)
- 배포 상태 확인: `vercel ls` / 실패 로그: `vercel inspect <배포URL> --logs`

> **Python 버전 주의**: Vercel 서버리스 빌드는 Python 3.14 를 사용하며 `.python-version` 파일을
> 무시한다. 루트 `requirements.txt` 는 cp314 휠이 있는 pydantic 2.12+/fastapi 0.119+ 하한을
> 유지할 것 (구버전 고정 시 pydantic-core 소스 컴파일 → PyO3 미지원으로 빌드 실패).

## 환경변수 (필수 1개 — 등록 완료)

네이버 지도 키는 **빌드 타임** 변수라 Vercel 에 등록해야 지도가 뜬다.
`VITE_NAVER_MAPS_KEY_ID` 는 production/preview 에 등록 완료 (2026-07-19). 키 변경 시:

```powershell
vercel env rm VITE_NAVER_MAPS_KEY_ID production
vercel env add VITE_NAVER_MAPS_KEY_ID production   # 값: apps/frontend/.env 의 키와 동일
git commit --allow-empty -m "redeploy"; git push    # env 변경 후 재배포 트리거
```

선택(백엔드): `LLM_API_KEY`(Program LLM 생성 — requirements.txt 의 anthropic 주석 해제 필요),
`POSTING_COPILOT_URL/KEY`(Posting 코파일럿). 미설정 시 각각 규칙 기반/3-Tier 폴백으로 동작한다.

## 배포 후 반드시 할 것 — NCP 도메인 등록

NCP 콘솔 → Services > Maps > Application → **Web 서비스 URL** 에 배포 도메인 추가:

```
https://spaceos-sandy.vercel.app
```

미등록 시 지도 타일이 인증오류로 표시되지 않는다 (localhost:5173 등록과 동일한 이유).

## 배포 확인 체크리스트

```powershell
curl.exe -s https://<프로젝트>.vercel.app/health                       # {"status":"ok",...}
curl.exe -s https://<프로젝트>.vercel.app/api/v1/commercial-districts   # 27거점 JSON
```

- `/` → 서울 25구 로드맵, "주요 Platform" 탭 → 27거점 대시보드 + 심층(히트맵 지도)
- 지도 타일 표시 여부 (안 뜨면 NCP 도메인 등록 확인)

## 배포판 제약 (의도된 것)

- `data/gold/garosugil/` 은 포함(2026-07-19, ~0.8MB) → `/api/v1/heatmap/buildings` 가 실데이터 응답.
  그 외 `data/` 는 미포함. git 자동 배포는 **GitHub 저장소 기준**이므로 `.vercelignore` 예외만으로는
  부족하고 `.gitignore` 에도 `!data/gold/garosugil/**` 예외가 있어야 한다 (둘 다 적용됨, 2026-07-19).
- `html/` 미포함 → `/maps` 정적 대시보드는 서빙되지 않음 (main.py 가 존재 시에만 mount — 에러 없음).
- DB/Redis 미연동 (로컬과 동일 — 시드 데이터 서빙).
