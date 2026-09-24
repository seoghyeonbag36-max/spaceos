#!/usr/bin/env bash
# 서울 3차 확장 5거점 — 폴리곤 → 점포+전유부(대장) 순차 수집.
# 재개 가능: building_vacancy 는 _CHECKPOINT(150동)마다 저장하고 재실행 시 기존분을 건너뛴다.
set -u
# 인자로 거점을 받는다. 비우면 5거점 전부 — 재개 시 남은 것만 대면 된다.
HUBS="${*:-bangbang gildong nowon gurodigital ydp-gucheong}"
for s in $HUBS; do
  echo "=== [$(date +%H:%M:%S)] HUB START $s ==="
  python -u -m data.collectors.vworld_bldg "$s"      || echo "!! vworld 실패 $s"
  python -u -m data.collectors.building_vacancy "$s" || echo "!! ledger 실패 $s"
  echo "=== [$(date +%H:%M:%S)] HUB DONE $s ==="
done
echo "=== ALL DONE ==="
