#!/usr/bin/env bash
# ⚠ 이 스크립트를 쓰지 말 것 — scripts/run_batch2_chain.py 가 대신한다 (2026-09-04).
#   2026-09-03 실행이 `fork: retry: Resource temporarily unavailable` 로 중간에 죽었고
#   (reports/logs/batch2_platform_2026-09-03.log 끝), 그런데 앞의 세 수집은 성공해
#   **반쪽 상태가 완주처럼 보였다**: kakao·blog·relm 은 66거점인데 분기 시계열은
#   2026-07-25·54거점에 그대로 멈춰 있었다. 아무도 몰랐다.
#   후속은 단계별 로그·재개(--from)·필수단계 중단을 갖춘 파이썬 드라이버다:
#       python scripts/run_batch2_chain.py            # 전체
#       python scripts/run_batch2_chain.py --list     # 단계 목록
#   이 파일은 그때 무엇을 돌렸는지의 이력으로만 남긴다.
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
