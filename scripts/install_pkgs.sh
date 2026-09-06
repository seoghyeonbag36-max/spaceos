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
# ⚠ 2026-09-06 실측으로 확정 — 시스템 파이썬에는 설치하지 않는다.
#
#   두 번 실패하고 로그를 보고서야 원인이 나왔다. 클라우드 VM 에는 파이썬이 둘 있다:
#   기본 `python`(/usr/local/bin)과 Debian 계열 배포판이 깐 `python3.11`(/usr/bin).
#   requires-python = ~=3.11.0 을 맞추려고 후자를 골랐더니 이렇게 죽었다.
#
#     · 배포판이 깐 PyJWT 2.7.0 을 pip 이 덮어쓰려다 **RECORD 파일이 없어** 실패.
#       dist-packages 에 배포판 패키지 관리자가 넣은 것이라 pip 이 무엇을 지워야
#       할지 알 수 없다. --break-system-packages 로도 넘지 못한다 — 그건 PEP 668
#       차단을 푸는 것이지 이 문제를 푸는 게 아니다.
#     · 폴백으로 둔 uv 는 `No virtual environment found for Python 3.11` 로 멈췄다.
#       uv pip install 은 기본적으로 venv 를 요구한다.
#
#   그래서 시스템 파이썬을 건드리지 않고 **전용 venv** 에 넣는다. venv 는 배포판
#   dist-packages 를 물려받지 않으므로 PyJWT 충돌 자체가 생기지 않는다.
#   venv 생성은 uv 로 한다 — Debian 계열은 `python3.11 -m venv` 에 필요한
#   python3.11-venv 패키지가 빠져 있는 경우가 흔하다. uv 는 그것 없이 만든다.
#
#   ⚠ 대가: 세션이 `python -m pytest` 로는 못 찾는다. 아래에서 쓸 명령을 찍는다.

echo "[install_pkgs] 기본 python: $(python -V 2>&1) at $(command -v python || echo '?')"

REQ="$ROOT/apps/backend/requirements.txt"
VENV="$ROOT/apps/backend/.venv"     # .gitignore 에 이미 있다
VPY="$VENV/bin/python"

if [ ! -f "$REQ" ]; then
  echo "[install_pkgs] WARN backend: $REQ 가 없다 — 루트 판정이 틀렸다"
elif [ -x "$VPY" ] && "$VPY" -c "import fastapi, pytest" 2>/dev/null; then
  # 훅은 매 세션 도는데 setup script 와 달리 환경 캐시 이득을 못 받는다.
  # 재설치를 피하는 이 검사가 세션 시작 지연을 좌우한다.
  echo "[install_pkgs] backend: venv 에 이미 설치됨 — 건너뜀"
else
  LOG="$(mktemp)"
  if [ ! -x "$VPY" ]; then
    echo "[install_pkgs] backend: venv 생성 ($VENV)"
    uv venv --python 3.11 "$VENV" >"$LOG" 2>&1       || uv venv "$VENV" >>"$LOG" 2>&1       || python3.11 -m venv "$VENV" >>"$LOG" 2>&1       || python -m venv "$VENV" >>"$LOG" 2>&1       || true
  fi

  if [ ! -x "$VPY" ]; then
    echo "[install_pkgs] WARN backend: venv 를 만들지 못했다. 로그 마지막 40줄:"
    tail -40 "$LOG"
  else
    echo "[install_pkgs] backend: $("$VPY" -V 2>&1) 에 설치 시작"
    if uv pip install --python "$VPY" -r "$REQ" >>"$LOG" 2>&1        || "$VPY" -m pip install -r "$REQ" >>"$LOG" 2>&1; then
      echo "[install_pkgs] backend: 설치 완료"
    else
      echo "[install_pkgs] WARN backend 설치 실패 — pytest 는 못 돈다. 로그 마지막 40줄:"
      tail -40 "$LOG"
    fi
  fi
  rm -f "$LOG"
fi

# 어떤 명령으로 테스트를 돌려야 하는지 매번 찍는다. 이걸 모르면 세션이
# `python -m pytest` 를 쳤다가 "또 설치 실패"로 잘못 읽는다 — 실제로 그랬다.
if [ -x "$VPY" ] && "$VPY" -c "import pytest" 2>/dev/null; then
  echo "[install_pkgs] ✅ 백엔드 테스트는 이 명령으로:"
  echo "[install_pkgs]    cd apps/backend && .venv/bin/python -m pytest -q"
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
