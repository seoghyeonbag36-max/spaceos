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
# data/config 는 **서빙이 런타임에 읽는다**(백엔드 패키지 밖이라 경로로 로드한다):
#   app/data/measured_pages.py    → page_hubs.py    (시드 밖 거점 목록)
#   app/services/posting_inputs.py → rone_districts.py (앵커 공유 표기)
# 2026-08-30~09-02 동안 이 줄이 없어서 프로덕션이 조용히 **54거점만** 서빙했다 —
# 서울 2차 12거점과 경기 7거점이 통째로 빠졌고, `rone-shared` 라벨도 `rone` 으로
# 눕고 있었다. 두 로더 다 "파일 없으면 빈 값" 으로 눕도록 쓰여 있어 아무 데도 안 터졌다.
COPY data/config/ ./data/config/
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
      echo "빌드 중단: page_building_master.geojson 이 ${n}개뿐이다 (임계 50 미만 — 2026-09-05 실측 73개)"; \
      echo "  업로드 규칙(.gitignore/.dockerignore)이 바뀌어 gold 가 빠졌을 가능성이 크다"; exit 1; \
    fi; \
    echo "가드 통과: gold 거점 ${n}개 · 프론트 index.html 있음"

# 거점 목록 가드 — gold 파일이 있는 것과 **서빙이 그것을 목록에 올리는 것**은 다른 일이다.
# 위 가드는 파일만 세므로 data/config 가 빠져도 통과한다(2026-09-02 실측: gold 73거점이
# 멀쩡히 실린 이미지가 화면에는 54거점만 냈다). 그래서 서빙 코드를 실제로 불러 센다.
#
# 임계는 **느슨하게** 둔다. 잡으려는 것은 0(= config 가 통째로 안 실림)이지 정확한
# 거점 수가 아니다. 서빙 대상은 제품 판단으로 바뀐다 — 2026-09-03 경기 중단으로
# 19 → 12 가 됐다(app/data/measured_pages.SERVED_CITIES). 정확한 수를 박아 두면
# 판단이 바뀔 때마다 배포가 깨진다.
RUN set -eu; \
    PYTHONPATH=/app/apps/backend python -c "import sys; from app.data import measured_pages as m; h=len(m._load_hubs()); n=len(m.MEASURED); print('page_hubs %d거점 로드 · 시드 밖 서빙 %d거점' % (h, n)); sys.exit(0 if h >= 50 and n >= 10 else 1)" \
      || { echo "빌드 중단: 시드 밖 거점이 서빙 목록에 안 오른다 — data/config 가 이미지에 안 들어왔을 가능성이 크다"; \
           echo "  확인: COPY data/config/ · .dockerignore · gcloud 업로드(.gitignore)"; exit 1; }

# app.main 을 import 할 수 있게 (WORKDIR 은 /app 이므로 경로 계산과 분리된다)
ENV PYTHONPATH=/app/apps/backend
ENV FRONTEND_DIR=/app/apps/frontend/dist
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=prod

# Cloud Run 이 $PORT 를 주입한다(기본 8080). 셸 형식이라 변수가 확장된다.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
