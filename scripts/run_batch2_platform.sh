#!/usr/bin/env bash
# 서울 2차 12거점을 Platform·Program 수집에 태운다 (2026-09-03).
# 12거점이 DISTRICT_TRDAR·DISTRICT_PLACES 에 등재된 뒤 한 번 돌리면 되는 스크립트다.
# 수집기는 66거점 전체를 다시 받는다(파일을 통째로 다시 쓰는 구조) — 서울 열린데이터·
# 카카오·네이버는 건축HUB 와 달리 일일 쿼터가 빡빡하지 않아 전량 재수집이 싸다.
set -u
export PYTHONIOENCODING=utf-8
LOG=reports/logs
mkdir -p "$LOG"
run() { echo "=== $* — $(date +%H:%M:%S)"; python -u -m "$@"; echo "--- exit $? — $(date +%H:%M:%S)"; }
run data.collectors.kakao_local  --platform13
run data.collectors.naver_blog   --platform13
run data.collectors.seoul_trdar  --platform13
run data.collectors.seoul_trdar  --platform13-flpop
run data.collectors.seoul_trdar  --platform13-income-ix
echo "=== 수집 종료 $(date +%H:%M:%S)"
