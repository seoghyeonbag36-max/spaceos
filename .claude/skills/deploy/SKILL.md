---
name: deploy
description: 프로덕션 배포 — main 푸시로 도는 Cloud Run 자동 배포, 빌드 시점 가드, 긴급 수동 배포와 그 함정. 배포·롤백·프로덕션 확인이 필요할 때.
---

# 배포 — main 에 푸시하면 나간다

| 항목 | 값 |
|---|---|
| 프로덕션 | **https://spaceos-twin.web.app** (Firebase Hosting → Cloud Run) |
| Cloud Run | `spaceos` / `us-central1` (무료 한도 리전) · 프로젝트 `spaceos-digital-twin` |
| 파이프라인 | `.github/workflows/deploy.yml` — 테스트 → 빌드 → 배포 → **검증** |

프론트(Vite 정적)와 백엔드(FastAPI)가 **컨테이너 하나**다. `api.ts` 가 `/api/v1` 을
상대경로로 박고 있어 호스트를 쪼개면 프론트가 통째로 깨진다.

⚠ **Vercel 을 쓰지 않는다** — 2026-08-28 내려왔다(무료 플랜 상업적 사용 금지).
`vercel --prod` 금지. `docs/deploy-vercel.md` 는 이력으로만 남겼다.

## 절차

```bash
git push origin main      # ← 이것이 배포다
```

푸시는 **백그라운드로** 돌린다 — GCM 인증 창 때문에 포그라운드는 타임아웃한다.

CI 검증 단계가 `/health` 200 과 분석 API 의 `"vacancy_source":"gold"` 를 확인하므로
**배포는 됐는데 데이터가 비어 있는 상태로는 초록이 안 뜬다.**

## 빌드 시점 가드 (Dockerfile 안에서 확인, 하나라도 어긋나면 이미지를 만들지 않는다)

- `data/gold/*/page_building_master.geojson` 50개 이상
- 프론트 `dist/index.html` 존재
- `VITE_NAVER_MAPS_KEY_ID` 비어 있지 않음

조용한 폴백보다 시끄러운 빌드 실패가 낫다 — 이 저장소는 "데이터가 빠졌는데 화면은
멀쩡해 보인다"로 두 번 당했다.

## 배포 후 확인

```bash
curl.exe -s https://spaceos-twin.web.app/health          # ⚠ /api/v1 아래가 아니다
curl.exe -s "https://spaceos-twin.web.app/api/v1/heatmap/vacancy?district=<slug>" | head -c 200
#   → vacancy_source: "gold" 인가("synthetic" 이면 그 거점은 합성 폴백이다)
curl.exe -s "https://spaceos-twin.web.app/api/v1/commercial-districts" | head -c 300
```

## 긴급 수동 배포 (PowerShell)

```powershell
$g = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
& $g builds submit --config cloudbuild.yaml --substitutions=_NAVER_KEY=<키> --project=spaceos-digital-twin
& $g run deploy spaceos --image=us-central1-docker.pkg.dev/spaceos-digital-twin/spaceos/web:latest `
    --region=us-central1 --project=spaceos-digital-twin
```

## 함정

- **`--set-env-vars` 를 함부로 붙이지 말 것.** 기존 환경변수를 통째로 갈아엎는다.
  `JWT_SECRET` 이 사라지면 `_guard_prod_secrets` 가 기동을 막아 서비스가 죽는다
  (2026-08-28 실제로 겪었다). 값을 **더할** 때는 `--update-env-vars`.
- **bash 를 거치면 `^##^` 구분자 문법이 깨진다** — 변수명이 `##JWT_SECRET` 으로 들어간
  적이 있다. PowerShell 에서 쉼표 구분으로 넣는다.
- **Dockerfile 에 heredoc(`RUN python - <<'PY'`) 금지** — Cloud Build 기본 빌더가
  `unknown instruction` 으로 죽는다.
- 인증은 Workload Identity 연합이다. 저장소에 서비스계정 키를 두지 않는다.
