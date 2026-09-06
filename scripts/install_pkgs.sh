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
# 이미 있으면 건너뛴다. 훅은 매 세션 도는데 setup script 와 달리 환경 캐시의
# 이득을 못 받으므로, 재설치를 피하는 이 검사가 세션 시작 지연을 좌우한다.
if python -c "import fastapi" 2>/dev/null; then
  echo "[install_pkgs] backend: 이미 설치됨 — 건너뜀"
else
  REQ="$ROOT/apps/backend/requirements.txt"
  if [ ! -f "$REQ" ]; then
    echo "[install_pkgs] WARN backend: $REQ 가 없다 — 루트 판정이 틀렸다"
  else
    echo "[install_pkgs] backend: 설치 시작"
    # Ubuntu 24.04 는 시스템 파이썬에 pip install 을 막는다(PEP 668).
    # 먼저 평범하게 시도하고, 그 차단에만 걸리면 --break-system-packages 로 넘는다.
    python -m pip install -q -r "$REQ" \
      || python -m pip install -q --break-system-packages -r "$REQ" \
      || echo "[install_pkgs] WARN backend 설치 실패 — pytest 는 못 돈다"
  fi
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
