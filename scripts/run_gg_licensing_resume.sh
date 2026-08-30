#!/usr/bin/env bash
# 경기 인허가 수집 — 끊기면 다시 시도한다.
#
# gg_licensing 은 487페이지를 전량 훑고 **미완주면 저장하지 않는다**(부분 결과를 완료로
# 저장하면 빠진 줄 모르기 때문). 그래서 중단은 곧 처음부터인데, 같은 날 완주한 스캔은
# 스테이지(bronze/_gg_licensing_stage/{날짜}.json)에 남아 재사용된다.
# 이 스크립트는 그 위에 **재시도**만 얹는다. 세션이 죽어도 이 파일이 남아 다시 부를 수 있다.
cd "$(dirname "$0")/.." || exit 1
export PYTHONIOENCODING=utf-8
HUBS="ilsan westerndom tanhyeon unjeong yadang"
LOG=data/logs/gg-licensing-resume.log
for attempt in 1 2 3 4 5; do
  missing=""
  for s in $HUBS; do
    ls data/bronze/$s/*/licensing_biz.json >/dev/null 2>&1 || missing="$missing $s"
  done
  if [ -z "$missing" ]; then
    echo "[resume] 전 거점 완료" | tee -a "$LOG"; exit 0
  fi
  echo "[resume] 시도 $attempt — 남은 거점:$missing" | tee -a "$LOG"
  python -u -m data.collectors.gg_licensing $missing >> "$LOG" 2>&1
  echo "[resume] 시도 $attempt 종료 exit=$?" | tee -a "$LOG"
done
echo "[resume] 5회 시도 후에도 남음 — 로그 확인" | tee -a "$LOG"
exit 1
