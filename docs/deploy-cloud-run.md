# Cloud Run 배포 가이드 (프로덕션, 2026-08-28~)

프론트(Vite 정적 빌드) + 백엔드(FastAPI)를 **컨테이너 하나**에 담아 Cloud Run 으로 낸다.
Vercel 에서 옮겨 온 경위는 [deploy-vercel.md](deploy-vercel.md) 머리말 참조.

## 좌표

| 항목 | 값 |
|---|---|
| **프로덕션 URL** | https://spaceos-798830962560.us-central1.run.app |
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

- `data/gold/*/page_building_master.geojson` 이 50개 이상인가 (54거점 기준)
- 프론트 `dist/index.html` 이 있는가
- `VITE_NAVER_MAPS_KEY_ID` 가 비어 있지 않은가

⚠ 이 저장소가 두 번 당한 양식이 **데이터가 빠졌는데 화면은 멀쩡해 보인다**는 것이다
(2026-08-15 `.vercelignore` 가 `data/` 를 빼먹어 프로덕션이 gold 를 한 파일도 못 읽었는데
07-19 부터 아무도 몰랐다). 조용한 폴백보다 시끄러운 빌드 실패가 낫다.

⚠ Dockerfile 에 heredoc(`RUN python - <<'PY'`)을 쓰지 말 것 — Cloud Build 의 기본
빌더(BuildKit 아님)가 파싱하지 못하고 `unknown instruction` 으로 죽는다.

## 모니터링

Cloud Monitoring 업타임 체크 **2개**가 5분마다 돈다. 실패하면
`seoghyeonbag36@gmail.com` 으로 메일이 온다(알림 정책: "SpaceOS 프로덕션 다운 알림").

| 체크 | 보는 것 |
|---|---|
| SpaceOS health | `/health` 가 200 이고 `"status":"ok"` 를 담는가 |
| SpaceOS districts gold | 분석 API 가 `"vacancy_source":"gold"` 를 담는가 |

두 번째가 핵심이다. 첫 번째만 있으면 **프로세스는 살아 있고 데이터만 비어 있는 상태**를
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

## 아직 안 붙은 것

- **계정 DB(Neon)** — `DATABASE_URL` 미설정. 분석 API 는 DB 없이 돌지만 가입·API키는 못 쓴다.
  자격증명이 붙은 요청은 500 이 난다(조용히 통과하지 않는다).
