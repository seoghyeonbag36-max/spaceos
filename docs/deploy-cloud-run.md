# Cloud Run 배포 가이드 (프로덕션, 2026-08-28~)

프론트(Vite 정적 빌드) + 백엔드(FastAPI)를 **컨테이너 하나**에 담아 Cloud Run 으로 낸다.
Vercel 에서 옮겨 온 경위는 [deploy-vercel.md](deploy-vercel.md) 머리말 참조.

## 좌표

| 항목 | 값 |
|---|---|
| **프로덕션 URL** | **https://spaceos-twin.web.app** (Firebase Hosting) |
| Cloud Run 원본 URL | https://spaceos-798830962560.us-central1.run.app |
| GCP 프로젝트 | `spaceos-digital-twin` (표시명 SpaceOS) · 번호 `798830962560` |
| 리전 | `us-central1` — **무료 한도가 적용되는 리전이라 그렇다** |
| 이미지 | `us-central1-docker.pkg.dev/spaceos-digital-twin/spaceos/web` |
| 결제 계정 | `011EDC-4A0AA8-3262D5` |

## 배포는 자동이다

`main` 에 푸시하면 `.github/workflows/deploy.yml` 이 **테스트 → 빌드 → 배포 → 검증** 을
순서대로 돈다. 검증 단계가 `/health` 200 과 분석 API 의 `"vacancy_source":"gold"` 를
확인하므로, **배포는 성공했는데 데이터가 비어 있는 상태**로는 초록이 안 뜬다.

인증은 Workload Identity 연합이다 — 저장소에 서비스계정 키를 두지 않는다. 공급자에
`assertion.repository=='seoghyeonbag36-max/spaceos'` 조건이 걸려 있어 다른 저장소의
토큰으로는 이 서비스계정을 못 빌린다.

### 수동 배포 (긴급 시)

```powershell
$g = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
# 키는 apps/frontend/.env 의 VITE_NAVER_MAPS_KEY_ID
& $g builds submit --config cloudbuild.yaml --substitutions=_NAVER_KEY=<키> --project=spaceos-digital-twin
& $g run deploy spaceos --image=us-central1-docker.pkg.dev/spaceos-digital-twin/spaceos/web:latest `
    --region=us-central1 --project=spaceos-digital-twin
```

⚠ **`--set-env-vars` 를 함부로 붙이지 말 것.** 그 플래그는 기존 환경변수를 통째로
갈아엎는다. `JWT_SECRET` 이 사라지면 `_guard_prod_secrets` 가 기동을 막아 서비스가 죽는다
(2026-08-28 실제로 겪었다). 값을 **더할** 때는 `--update-env-vars` 를 쓴다.

⚠ bash 를 거치면 `--set-env-vars` 의 `^##^` 구분자 문법이 깨진다 — 변수명이
`##JWT_SECRET` 으로 들어간 적이 있다. PowerShell 에서 쉼표 구분으로 넣을 것.

## 왜 한 컨테이너인가

`apps/frontend/src/lib/api.ts` 가 `/api/v1` 을 **상대경로로 하드코딩**한다. 프론트와 API 를
다른 호스트로 쪼개면 프론트가 통째로 깨지고 CORS 설정·프록시가 따라붙는다. 한 컨테이너에
두면 같은 오리진이라 그 문제가 아예 생기지 않는다(`app/main.py` 맨 끝 마운트).

부수 효과로 Cloudflare Pages 가 필요 없어졌다 — 계획에 있었지만 가입이 막혀 있었고,
이 구조에서는 애초에 안 쓴다.

## 이 구조가 없애는 위험 둘

1. **이중 requirements 소멸.** Vercel 은 루트 `requirements.txt`(배포 전용 최소 셋)를 썼고
   그게 백엔드용과 갈라져 2026-08-26~27 프로덕션을 18시간 죽였다. Cloud Run 은 CI 가
   테스트하는 `apps/backend/requirements.txt` 하나만 쓴다 — 갈라질 목록이 없다.
2. **런타임 버전 고정.** Dockerfile 이 `python:3.11-slim` 을 박는다. 플랫폼이 파이썬을
   몰래 올릴 수 없다(Vercel 은 빌드 3.14 / 런타임 3.12 로 두 버전을 썼고, 3.14 로 올라가면
   SQLAlchemy 2.0.35 가 깨지는 지뢰가 있었다).

## 빌드 시점 가드

`Dockerfile` 이 이미지 안에서 확인한다. 하나라도 어긋나면 **이미지를 만들지 않는다**:

- `data/gold/*/page_building_master.geojson` 이 50개 이상인가
  (임계는 **일부러 느슨하다** — 잡으려는 것은 0, 즉 gold 가 통째로 안 실린 경우이지 정확한
  거점 수가 아니다. 정확한 수를 박으면 서빙 판단이 바뀔 때마다 배포가 깨진다.
  2026-09-05 실측 73개 = 서빙 서울 66 + 경기 보류 7)
- 프론트 `dist/index.html` 이 있는가
- `VITE_NAVER_MAPS_KEY_ID` 가 비어 있지 않은가

⚠ 이 저장소가 두 번 당한 양식이 **데이터가 빠졌는데 화면은 멀쩡해 보인다**는 것이다
(2026-08-15 `.vercelignore` 가 `data/` 를 빼먹어 프로덕션이 gold 를 한 파일도 못 읽었는데
07-19 부터 아무도 몰랐다). 조용한 폴백보다 시끄러운 빌드 실패가 낫다.

⚠ Dockerfile 에 heredoc(`RUN python - <<'PY'`)을 쓰지 말 것 — Cloud Build 의 기본
빌더(BuildKit 아님)가 파싱하지 못하고 `unknown instruction` 으로 죽는다.

### 로컬에서 미리 확인하기 (2026-08-28 부터 가능)

WSL2 설치 후 Docker Desktop 엔진이 뜬다. 배포 전에 같은 이미지를 손에서 확인할 수 있다:

```bash
docker build --build-arg VITE_NAVER_MAPS_KEY_ID=<키> -t spaceos-local:test .
docker run -d --name spaceos-smoke -p 18080:8080 \
  -e JWT_SECRET=local-smoke-secret-not-real -e DATABASE_URL="<Neon URL>" spaceos-local:test
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:18080/health
docker rm -f spaceos-smoke
```

실측(2026-08-28): 이미지 **775MB** · gold 106MB(거점 56 디렉터리 · master 54개) ·
프론트 dist 포함 · 네이버 키가 `MapShell-*.js` 번들에 인라인됨. 로컬 컨테이너가
프로덕션과 동일하게 당시 상권 54곳 전부 `gold` 로 응답했다.

> **갱신 2026-09-05**: 저장소의 gold 는 **거점 75 디렉터리 · master 73개**로 늘었고,
> 서빙은 **서울 66거점이 전부 `gold`** 로 응답한다(전 거점 `GET /heatmap/vacancy` 호출로 확인).
> 이미지 크기는 그 뒤 재측정하지 않았다 — 위 775MB 는 08-28 값이다.

## 모니터링

Cloud Monitoring 업타임 체크 **4개**가 5분마다 돈다. 실패하면
`seoghyeonbag36@gmail.com` 으로 메일이 온다(알림 정책: "SpaceOS 프로덕션 다운 알림").

| 체크 | 대상 | 보는 것 |
|---|---|---|
| SpaceOS health | Cloud Run 원본 | `/health` 가 200 이고 `"status":"ok"` 인가 |
| SpaceOS districts gold | Cloud Run 원본 | 분석 API 가 `"vacancy_source":"gold"` 를 담는가 |
| SpaceOS hosting health | `spaceos-twin.web.app` | 같은 검사, 사용자가 실제로 쓰는 주소에서 |
| SpaceOS hosting gold | `spaceos-twin.web.app` | 같은 검사, 사용자가 실제로 쓰는 주소에서 |

**둘로 나눠 두는 이유**: Cloud Run 이 멀쩡해도 Hosting 리라이트가 깨지면 사용자는 못 쓴다.
원본만 보면 그 고장이 안 보인다. 반대로 Hosting 만 보면 어느 층이 깨졌는지 모른다.

**gold 검사가 핵심이다.** health 만 있으면 **프로세스는 살아 있고 데이터만 비어 있는 상태**를
못 잡는다 — 그게 이 저장소의 반복 실패 양식이다.

## 무료 한도와 그 경계

Cloud Run Always Free: 월 200만 요청 · 180,000 vCPU초 · 360,000 GiB초 · **egress 1GiB**.

실측(2026-08-28): gzip 기준 거점 1회 조회 약 110KB(건물 90KB + 요약 6.5KB + 레이어 ~15KB).
**egress 1GiB ≈ 거점 조회 9,700회/월** 이 실질 상한이다. 요청 수가 아니라 여기가 먼저 찬다.

⚠ 무료 한도는 **미국 리전 전용**이라 서울에서 왕복 150~200ms 가 붙는다. API p95 <200ms
목표를 이 구성으로는 못 맞춘다. 유료 파일럿이 생기면 리전을 `asia-northeast3`(서울)로
옮긴다 — **설정 한 줄이고 재작성이 아니다.** 그때까지는 지연을 감수한다.

⚠ 무료 체험(90일/$300) 종료 시 결제계정이 **자동으로 닫힌다.** 그때 수동으로 유료 계정
전환을 해야 Always Free 가 이어진다. 전환해도 한도 안에서는 $0 다.

## 읽기 좋은 주소 — Firebase Hosting (2026-08-29)

`spaceos-798830962560...` 의 숫자는 프로젝트 번호라 Cloud Run 에서 못 바꾼다. 앞에 Firebase
Hosting 을 세워 **https://spaceos-twin.web.app** 을 얻었다. `firebase.json` 이 모든 요청(`**`)을
Cloud Run 서비스 `spaceos`(us-central1)로 리라이트한다.

- Firebase 프로젝트 = GCP 프로젝트(`spaceos-digital-twin`). 새로 만들지 않았다
- 사이트 ID 는 `spaceos-twin` — `spaceos` 는 다른 프로젝트가 선점했다
- 배포: `npx firebase-tools deploy --only hosting --project spaceos-digital-twin`
- **정적 파일은 0개다.** 프론트도 컨테이너가 낸다(단일 출처 유지 — 아래 참조)

⚠ **Firebase 를 처음 쓰는 계정은 CLI 로 프로젝트를 붙일 수 없다.** `projects:addfirebase` 가
Owner·`firebase.admin` 이 있어도 403 `PERMISSION_DENIED` 로 막힌다(오류 문구는 이유를 안 밝힌다).
콘솔에서 프로젝트를 한 번 만들어 **약관에 동의**해야 풀린다. 2026-08-29 에 이걸로 막혔다.

⚠ 프론트를 Hosting 에 따로 올리지 않는 이유: CDN 이라 빠르고 Cloud Run egress 도 아끼지만,
프론트가 **두 곳**에 살게 되어 한쪽만 배포되면 낡은 화면이 새 API 를 부른다. 단일 출처를
지킨다. egress 가 실제로 문제되면 그때 나눈다.

## 계정 DB — Neon Postgres (2026-08-28 연결)

`DATABASE_URL` 이 Cloud Run 환경변수로 붙어 있다. **Neon 서버리스 Postgres 18.6**,
`-pooler` 엔드포인트(서버리스는 커넥션이 금방 바닥나므로 풀링 쪽을 쓴다).

마이그레이션은 로컬에서 원격 Neon 을 향해 돌린다:

```bash
cd apps/backend
DATABASE_URL="<Neon 접속 문자열>" python -m alembic upgrade head
DATABASE_URL="<...>" python -m alembic check     # 드리프트 0 확인
```

⚠ **`--set-env-vars`·`--update-env-vars` 에 이 URL 을 넣을 때는 `gcloud.cmd` 를 쓰지 말 것.**
URL 의 `&`(`...sslmode=require&channel_binding=require`)를 cmd 래퍼가 명령 구분자로
해석해 **값이 조용히 잘린다**(150자 → 126자, 2026-08-28 실측). 접속은 되므로 눈치채기
어렵다. `bin\gcloud.ps1`(PowerShell 래퍼)로 넣으면 온전히 들어간다.

검증(2026-08-28, 프로덕션 URL 로 실제 호출):

| 단계 | 결과 |
|---|---|
| `POST /auth/signup` | 201 · 조직·사용자·멤버십 생성 |
| `GET /auth/me` | 200 · role=admin |
| `POST /auth/api-keys` | 201 · `sk_spaceos_…` 발급 |
| 익명 분석 호출 | 200 (공개 데모 유지) |
| API 키 분석 호출 | 200 · 사용량 기록됨 |
| **잘못된 키** | **401** — DB 가 없던 때는 500 이었다. 이제 설계대로 거절한다 |
| `GET /admin/usage` | `active_orgs: 1` 로 움직임 확인 |

⚠ 검증에 쓴 연기시험 조직은 **지웠다.** 안 지우면 `active_orgs` 가 가짜 파일럿 1건으로
시작해 KPI② 가 거짓이 된다. 지금 계정층 5개 표는 전부 0행이고, **`active_orgs: 0` 이
정직한 현재 값**이다.

⚠ 한글이 든 JSON 을 curl 로 보낼 때 Windows 셸이 cp949 로 인코딩하면 서버가
`There was an error parsing the body`(400)로 거절한다. UTF-8 파일로 만들어
`--data-binary @파일` 로 보낼 것.
