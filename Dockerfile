# SpaceOS — Cloud Run 단일 컨테이너 (프론트 정적 + FastAPI API)
#
# ## 왜 한 컨테이너인가
# `apps/frontend/src/lib/api.ts` 가 `/api/v1` 을 **상대경로로 하드코딩**한다. 프론트와
# API 를 다른 호스트로 쪼개면 프론트가 통째로 깨지고 CORS 설정이 따라붙는다. 한 컨테이너에
# 두면 같은 오리진이라 그 문제가 아예 생기지 않는다(main.py 맨 끝 마운트 참조).
#
# ## 왜 저장소 레이아웃을 그대로 옮기는가
# 서비스 13개가 `Path(__file__).resolve().parents[4] / "data" / "gold"` 로 Gold 를 찾는다
# (admin.py 는 parents[5]). 컨테이너 안에서도 `/app/apps/backend/app/...` 구조를 유지하면
# 그 계산이 그대로 맞아서 **코드를 한 줄도 안 고쳐도 된다.** 13파일을 리팩터하는 것보다
# 이쪽이 위험이 작다.
#
# ## Vercel 과 달라지는 것 — 이중 requirements 가 사라진다
# Vercel 은 루트 `requirements.txt`(배포 전용 최소 셋)를 썼고, 그게 백엔드용과 갈라져
# 2026-08-26~27 프로덕션을 18시간 죽였다. 여기서는 CI 가 테스트하는 바로 그
# `apps/backend/requirements.txt` 하나만 쓴다. 목록이 하나뿐이라 갈라질 수가 없다.

# ── 1단계: 프론트 빌드 ────────────────────────────────────────────────────────
# `apps/frontend/dist` 는 .gitignore 대상이라 업로드에 안 실린다 → 여기서 만든다.
FROM node:20-slim AS frontend

WORKDIR /fe
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci
COPY apps/frontend/ ./

# 네이버 지도 키는 **빌드 타임** 변수다(Vite 가 번들에 인라인한다). 런타임 환경변수로는
# 못 넣는다. 값은 cloudbuild.yaml 의 치환변수로 주입한다.
# ⚠ 비우고 빌드하면 지도만 조용히 안 뜨고 나머지는 멀쩡해 보인다 — 그래서 아래에서 막는다.
ARG VITE_NAVER_MAPS_KEY_ID=""
ENV VITE_NAVER_MAPS_KEY_ID=${VITE_NAVER_MAPS_KEY_ID}
RUN test -n "$VITE_NAVER_MAPS_KEY_ID" || \
      (echo "빌드 중단: VITE_NAVER_MAPS_KEY_ID 가 비었다. 이대로 빌드하면 배포는 성공하고 지도만 안 뜬다." && exit 1)
RUN npm run build

# ── 2단계: 런타임 ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# psycopg2-binary 는 휠로 오지만, 소스 빌드로 떨어질 때를 대비해 남긴다.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq-dev gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 — 소스가 바뀌어도 이 레이어는 캐시된다.
COPY apps/backend/requirements.txt ./apps/backend/requirements.txt
RUN pip install --no-cache-dir -r apps/backend/requirements.txt

# 저장소 레이아웃 유지 (위 "왜 저장소 레이아웃을" 참조)
COPY apps/backend/ ./apps/backend/
COPY data/gold/ ./data/gold/
COPY --from=frontend /fe/dist/ ./apps/frontend/dist/

# ── 빌드 시점 가드 ───────────────────────────────────────────────────────────
# 이 저장소가 반복해 당한 실패 양식: **데이터가 빠졌는데 화면은 멀쩡해 보인다.**
# 2026-08-15 에 .vercelignore 가 data/ 를 통째로 빼먹어 프로덕션이 gold 를 한 파일도
# 못 읽었는데 07-19 부터 아무도 몰랐다(건물 836동 → 샘플 8동, 전 거점 synthetic).
# 여기서는 그 상태로 이미지가 **만들어지지 않게** 한다. 조용한 폴백보다 시끄러운 실패가 낫다.
#
# ⚠ heredoc(`RUN python - <<'PY'`)을 쓰지 말 것 — Cloud Build 의 기본 빌더(BuildKit 아님)가
#   파싱하지 못하고 `unknown instruction` 으로 죽는다(2026-08-28 실측). 셸로만 쓴다.
#   RUN 은 Docker 가 변수 치환을 하지 않으므로 `$n`·`$(...)` 는 셸이 그대로 처리한다.
RUN set -eu; \
    n=$(ls -1 /app/data/gold/*/page_building_master.geojson 2>/dev/null | wc -l); \
    if [ ! -f /app/apps/frontend/dist/index.html ]; then \
      echo "빌드 중단: 프론트 index.html 이 없다 — 빌드 산출물이 안 들어왔다"; exit 1; \
    fi; \
    if [ "$n" -lt 50 ]; then \
      echo "빌드 중단: page_building_master.geojson 이 ${n}개뿐이다 (54거점 기준 50 미만)"; \
      echo "  업로드 규칙(.gitignore/.dockerignore)이 바뀌어 gold 가 빠졌을 가능성이 크다"; exit 1; \
    fi; \
    echo "가드 통과: gold 거점 ${n}개 · 프론트 index.html 있음"

# app.main 을 import 할 수 있게 (WORKDIR 은 /app 이므로 경로 계산과 분리된다)
ENV PYTHONPATH=/app/apps/backend
ENV FRONTEND_DIR=/app/apps/frontend/dist
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=prod

# Cloud Run 이 $PORT 를 주입한다(기본 8080). 셸 형식이라 변수가 확장된다.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
