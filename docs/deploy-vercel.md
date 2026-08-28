# Vercel 배포 가이드 — ⛔ 2026-08-28 프로덕션에서 내려왔다

> **프로덕션은 이제 Cloud Run 이다 → [deploy-cloud-run.md](deploy-cloud-run.md)**
>
> 이 문서는 **이력**으로 남긴다. 여기 적힌 함정들(파이썬 두 버전 · cp314 휠 · 이중
> requirements · SQLAlchemy 3.14 지뢰)은 Vercel 서버리스 구조에서만 생기는 것이라
> Cloud Run 에서는 해당 없다. 다만 **왜 옮겼는지**의 근거라서 지우지 않는다.
>
> 옮긴 이유는 성능이 아니라 **약관**이다: Vercel 무료(Hobby)는 상업적 사용을 금지하는데
> SpaceOS 는 B2B 파일럿·DaaS 구독·M&A Exit 을 지향한다. 자세한 비교는
> `decision-infra-layer-2026-08-25.md`.

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

> **Python 버전 주의 — 두 버전이 쓰인다** (2026-08-27 배포 로그 실측으로 정정):
>
> | 단계 | 버전 | 무엇이 걸리나 |
> |---|---|---|
> | 의존성 해결 | **CPython 3.14.7** | 휠이 3.14 용으로 없으면 소스 빌드 → **빌드 실패** |
> | 함수 런타임 | **3.12** | 코드가 실제로 도는 곳. 3.12 에서 동작해야 한다 |
>
> 종전 서술("서버리스 빌드는 3.14 를 쓰며 `.python-version` 을 무시한다")은 앞 칸만 보고
> 뒤 칸을 런타임으로 오해한 것이다. 로그는 오히려 `.python-version`·`pyproject.toml`·
> `Pipfile.lock` 을 **찾아본 뒤** 없어서 3.12 로 떨어진다고 말한다
> (`No Python version specified in ... Using python version: 3.12`).
>
> 그래서 요구조건이 둘이다: **3.14 휠이 있을 것**(pydantic 2.12+/fastapi 0.119+ 하한 유지)
> **그리고 3.12 에서 돌 것**.
>
> ### ⚠ 지뢰 — SQLAlchemy 2.0.35 는 3.14 에서 깨진다
>
> 런타임이 3.12 라 지금은 안 터진다. 하지만 **Vercel 이 런타임을 3.14 로 올리거나
> 누가 `.python-version` 에 3.14 를 적는 순간 프로덕션이 다시 죽는다.**
> `sqlalchemy/util/typing.py::make_union_type` 이 `cast(Any, Union).__getitem__(types)`
> 를 부르는데 3.14 에서 `typing.Union` 이 바뀌어 `TypeError: descriptor '__getitem__'
> requires a 'typing.Union' object but received a 'tuple'` 로 터진다. `models/auth.py` 의
> `Mapped[datetime | None]` 같은 유니온 애노테이션을 매핑하는 자리다.
>
> 2026-08-27 에 CI `서버리스 임포트` 잡을 실수로 3.14 로 잡았다가 발견했다 — 잡은 3.12 로
> 고쳤고, **이 지뢰는 그대로 남아 있다.** 해소하려면 SQLAlchemy 를 3.14 지원 버전으로
> 올려야 한다(2.0.52 에는 cp314 휠이 있다). 올릴 때는 `apps/backend/requirements.txt` 와
> **같이** 올릴 것 — 배포와 테스트가 다른 버전을 쓰면 그 차이가 다음 함정이 된다.

## 환경변수 (필수 1개 — 등록 완료)

네이버 지도 키는 **빌드 타임** 변수라 Vercel 에 등록해야 지도가 뜬다.
`VITE_NAVER_MAPS_KEY_ID` 는 production/preview 에 등록 완료 (2026-07-19). 키 변경 시:

```powershell
vercel env rm VITE_NAVER_MAPS_KEY_ID production
vercel env add VITE_NAVER_MAPS_KEY_ID production   # 값: apps/frontend/.env 의 키와 동일
git commit --allow-empty -m "redeploy"; git push    # env 변경 후 재배포 트리거
```

### Program 백엔드 키 (미등록 — 2026-08-06 현재)

이 넷을 넣어야 Program 이 배포판에서 산다. **`data/.env` 는 업로드에서 제외되므로
로컬에 있어도 배포에는 없다** — Vercel 에 따로 넣어야 한다.

```powershell
vercel env add KAKAO_REST_API_KEY production    # 값: data/.env
vercel env add NAVER_CLIENT_ID production       # 값: data/.env
vercel env add NAVER_CLIENT_SECRET production   # 값: data/.env
vercel env add LLM_API_KEY production           # 값: apps/backend/.env
git commit --allow-empty -m "redeploy"; git push
```

| 키 | 없으면 | 다른 전제 |
|---|---|---|
| `KAKAO_REST_API_KEY` | `/marketing/places` 가 `source:"unavailable"` | 없음 — 표준 라이브러리만 쓴다 |
| `NAVER_CLIENT_ID/SECRET` | `/marketing/reviews` 가 `source:"unavailable"` | 없음 |
| `LLM_API_KEY` | 가게·상권 생성이 규칙 기반/시드로 폴백 | `anthropic` 설치(2026-08-06 해제 완료) + **크레딧 잔액** |

앞의 셋은 **의존성도 크레딧도 필요 없다** — 등록·재배포만으로 바로 산다.

확인:

```powershell
curl.exe -s "https://spaceos-sandy.vercel.app/api/v1/marketing/places?query=%EB%A7%A1%EA%B8%B0%EB%8B%A4"
# source 가 "kakao-local" 이면 성공, "unavailable" 이면 키 미반영
```

선택(백엔드): `POSTING_COPILOT_URL/KEY`(Posting 코파일럿) — 미설정 시 3-Tier 폴백.

## 배포 후 반드시 할 것 — NCP 도메인 등록

NCP 콘솔 → Services > Maps > Application → **Web 서비스 URL** 에 배포 도메인 추가:

```
https://spaceos-sandy.vercel.app
```

미등록 시 지도 타일이 인증오류로 표시되지 않는다 (localhost:5173 등록과 동일한 이유).

## 배포 확인 체크리스트

```powershell
curl.exe -s https://<프로젝트>.vercel.app/health                       # {"status":"ok",...}
curl.exe -s https://<프로젝트>.vercel.app/api/v1/commercial-districts   # 33거점 JSON
```

- `/` → 서울 25구 로드맵, "주요 Platform" 탭 → 33거점 대시보드 + 심층(히트맵 지도)
- 지도 타일 표시 여부 (안 뜨면 NCP 도메인 등록 확인)

## 배포판 제약 (의도된 것)

- `data/gold/garosugil/` 은 포함(2026-07-19, ~0.8MB) → `/api/v1/heatmap/buildings` 가 실데이터 응답.
  그 외 `data/` 는 미포함. git 자동 배포는 **GitHub 저장소 기준**이므로 `.vercelignore` 예외만으로는
  부족하고 파일이 실제로 git 에 들어 있어야 한다.
  ⚠ **2026-08-15 정정** — "`.gitignore` 에도 예외가 있어 둘 다 적용됨" 이라고 적어 뒀던 것은 틀렸다.
  `.gitignore` 의 `!data/gold/garosugil/**`(29~30줄)은 뒤따르는 `data/gold/*/*`(43줄)에 덮여
  **실효가 없다**(`git check-ignore --no-index` 로 확인). 지금 8개 파일이 배포되는 것은 규칙이
  살아서가 아니라 **이미 추적 중이라 gitignore 가 적용되지 않기 때문**이다. 결과가 같아 보여도
  차이는 실재한다 — garosugil 에 **새 산출물을 추가하면 조용히 빠진다.** 넣을 때는 `git add -f`
  로 확인하고, 커밋 후 `git ls-files data/gold/garosugil/` 로 들어갔는지 본다.
- `html/` 미포함 → `/maps` 정적 대시보드는 서빙되지 않음 (main.py 가 존재 시에만 mount — 에러 없음).
- DB/Redis 미연동 (로컬과 동일 — 시드 데이터 서빙).
