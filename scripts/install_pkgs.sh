#!/bin/bash
# 클라우드 세션(claude.ai/code)에서만 의존성을 설치한다.
#
# 왜 setup script 가 아니라 이 스크립트인가 (2026-09-06)
#   claude.ai/code 환경 다이얼로그의 Setup script 에 pip/npm 을 직접 적었더니
#   **아무것도 설치되지 않은 채 세션이 떴다**. 증상은 pytest 가 fastapi·pydantic·
#   alembic 을 못 찾아 22개 파일이 수집 단계에서 전부 깨지고, npm run build 가
#   node_modules 부재로 전역 typescript 6 을 잡아 tsconfig 의 baseUrl 을
#   에러로 뱉는 것이었다. 원인 후보가 셋인데(작업 디렉터리가 저장소 루트가
#   아님 · Ubuntu 24.04 의 PEP 668 externally-managed 차단 · 환경 캐시가 있으면
#   setup script 를 건너뜀) 어느 것인지 밖에서는 가릴 수 없다.
#
#   그래서 세 경우를 전부 견디는 쪽으로 옮겼다. Anthropic 문서도 npm install ·
#   pip install 같은 **프로젝트 셋업은 SessionStart 훅**으로 하라고 적고 있다
#   (setup script 는 VM 자체를 provisioning 하는 용도). 훅만이 저장소 루트를
#   $CLAUDE_PROJECT_DIR 로 보장받고, 캐시와 무관하게 매 세션 돈다.
#
# 로컬에서는 즉시 빠진다 — CLAUDE_CODE_REMOTE 는 클라우드 VM 에서만 true 다.

set -u

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# $CLAUDE_PROJECT_DIR 가 저장소 루트다. 없으면 이 파일 위치에서 되짚는다
# (setup script 가 `bash scripts/install_pkgs.sh` 로 부르는 경우).
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
echo "[install_pkgs] repo root: $ROOT"

# --- backend ---------------------------------------------------------------
# ⚠ 2026-09-06: 처음엔 `pip install -q` 로 적었다가 실패 이유를 통째로 가렸다.
#    "WARN 설치 실패"만 남고 무엇이 왜 안 됐는지가 없어 한 사이클을 더 태웠다.
#    설치 로그는 실패했을 때만, 그러나 반드시 보인다.
#
# 인터프리터 선택: 이 프로젝트는 requires-python = ~=3.11.0 이고 CI 도 3.11 로 돈다.
# 클라우드 VM 의 기본 python 이 더 최신이면 requirements.txt 의 핀 고정 버전에
# 그 버전용 휠이 없어(psycopg2-binary==2.9.9 가 대표적이다) 소스 빌드로 넘어가고
# libpq 헤더가 없어 죽는다. 그래서 3.11 이 있으면 그것을 먼저 쓴다.
echo "[install_pkgs] 기본 python: $(python -V 2>&1) at $(command -v python || echo '?')"

PY=python
for cand in python3.11 /usr/bin/python3.11 /usr/local/bin/python3.11; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$cand"
    echo "[install_pkgs] 3.11 발견: $cand — 이것으로 설치한다"
    break
  fi
done

if "$PY" -c "import fastapi" 2>/dev/null; then
  # 훅은 매 세션 도는데 setup script 와 달리 환경 캐시 이득을 못 받는다.
  # 재설치를 피하는 이 검사가 세션 시작 지연을 좌우한다.
  echo "[install_pkgs] backend: 이미 설치됨 — 건너뜀"
else
  REQ="$ROOT/apps/backend/requirements.txt"
  if [ ! -f "$REQ" ]; then
    echo "[install_pkgs] WARN backend: $REQ 가 없다 — 루트 판정이 틀렸다"
  else
    echo "[install_pkgs] backend: $PY 로 설치 시작"
    LOG="$(mktemp)"
    # ① 평범하게 → ② PEP 668(externally-managed) 차단이면 그것만 넘어서
    # → ③ uv(사전 설치돼 있다)로 마지막 시도. uv 는 해석기가 달라 가끔 통과한다.
    if "$PY" -m pip install -r "$REQ" >"$LOG" 2>&1 \
       || "$PY" -m pip install --break-system-packages -r "$REQ" >>"$LOG" 2>&1 \
       || { command -v uv >/dev/null 2>&1 \
            && uv pip install --python "$PY" -r "$REQ" >>"$LOG" 2>&1; }; then
      echo "[install_pkgs] backend: 설치 완료"
    else
      echo "[install_pkgs] WARN backend 설치 실패 — pytest 는 못 돈다. 로그 마지막 40줄:"
      tail -40 "$LOG"
    fi
    rm -f "$LOG"
  fi
fi

# 기본 python 과 설치에 쓴 인터프리터가 다르면 `python -m pytest` 로는 못 찾는다.
# 어떤 명령을 써야 하는지 여기서 알려 준다 — 모르면 "또 설치 실패"로 읽힌다.
if [ "$PY" != "python" ] && "$PY" -c "import fastapi" 2>/dev/null \
   && ! python -c "import fastapi" 2>/dev/null; then
  echo "[install_pkgs] ⚠ 백엔드 의존성은 $PY 에만 있다."
  echo "[install_pkgs]   테스트: cd apps/backend && $PY -m pytest -q"
fi

# --- frontend --------------------------------------------------------------
# node_modules 가 없으면 npm run build 가 전역 tsc 를 잡는다. 그러면 코드가
# 멀쩡해도 tsconfig 의 baseUrl 이 에러로 나온다 — 원인을 코드에서 찾게 되는 함정.
FE="$ROOT/apps/frontend"
if [ -d "$FE/node_modules" ]; then
  echo "[install_pkgs] frontend: 이미 설치됨 — 건너뜀"
elif [ ! -f "$FE/package-lock.json" ]; then
  echo "[install_pkgs] WARN frontend: $FE/package-lock.json 이 없다"
else
  echo "[install_pkgs] frontend: 설치 시작"
  (cd "$FE" && npm ci --no-audit --no-fund) \
    || echo "[install_pkgs] WARN frontend 설치 실패 — npm run build 는 못 돈다"
fi

echo "[install_pkgs] 완료"
# 설치가 실패해도 0 으로 끝낸다 — 훅이 실패하면 세션이 뜨지 않는다.
# 대신 위의 WARN 이 세션 컨텍스트에 남아 조용한 실패가 되지 않게 한다.
exit 0
