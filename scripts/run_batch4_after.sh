#!/usr/bin/env bash
# 3차 체인이 끝난 뒤 4차 10거점을 이어 받는다.
# ⚠ 전유부를 동시에 두 줄로 돌리지 않기 위해 **기다렸다가** 시작한다 (429 는 키 단위).
# 순서는 건물 수 오름차순 — 남은 쿼터 안에서 **완주하는 거점 수**를 최대화한다.
# 쿼터가 소진되면 수집기가 스스로 강등(rate_limited)하고 넘어가며, 재실행하면 강등분만 다시 받는다.
set -u
LOG=reports/logs/batch3_chain.log
while ! grep -q "=== ALL DONE ===" "$LOG"; do sleep 60; done
echo "=== [$(date +%H:%M:%S)] 3차 완료 확인 — 4차 시작 ==="
bash scripts/run_batch3_chain.sh \
  jamsil-tour seochoyeok yangjae maebong gurojeonhwa dogok daerim bonseobu guui poi
