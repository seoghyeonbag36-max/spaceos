#!/usr/bin/env bash
# 2차 확장 13거점 1차 수집 — 점포·폴리곤만. **건축HUB 쿼터를 쓰지 않는다.**
#
# 대장(전유부/층별개요)은 여기서 돌리지 않는다. 그건 쿼터가 하루치 사라지는 자원이라
# 별도 세션에서 한 거점씩 돌린다(hub-chain §3). build_page_master 도 돌리지 않는다 —
# 마스터가 생기면 그 거점이 서빙 목록에 뜨고, 대장 없이 뜨면 공실이 합성값이 된다.
#
# 재개 가능: 이미 받은 거점은 수집기가 스스로 건너뛴다(--force 를 쓰지 않는다).
cd "$(dirname "$0")/.." || exit 1
export PYTHONIOENCODING=utf-8
HUBS="bamgasi wondang baekseok daehwa haengsin madu juyeop kintex starfield samsong munsan mokdong pajuoutlet"
LOG=data/logs/batch2-stores.log
for s in $HUBS; do
  echo "=== $s ===" | tee -a "$LOG"
  python -u -m data.collectors.vworld_bldg "$s" >> "$LOG" 2>&1 || echo "[warn] $s 폴리곤 실패" | tee -a "$LOG"
  python -u -m data.collectors.building_vacancy "$s" --no-ledger >> "$LOG" 2>&1 || echo "[warn] $s 점포 실패" | tee -a "$LOG"
done
echo "[batch2] 수집 루프 종료" | tee -a "$LOG"
