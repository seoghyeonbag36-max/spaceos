#!/usr/bin/env python
"""`DISTRICT_TRDAR` 에 15거점을 넣은 뒤의 재실행 — 2026-09-24.

## 왜 다시 도는가

bronze 의 상권분석 자료는 **수집 시점의 매핑으로 필터돼** 저장된다
(`seoul_trdar.py` 의 `_tag()` 가 `TRDAR_TO_DISTRICT` 에 없는 행을 버린다).
그래서 매핑을 245 → 352코드로 늘려도 **이미 받아둔 bronze 에는 새 107코드가 없다.**
수집부터 다시 돌아야 `build_trdar_demand` 가 81거점을 낸다.

`datalab` 은 상권이 아니라 거점 이름으로 받으므로 이미 81거점이다 — 건너뛴다.

## 선행 대기

앞 체인(옛 매핑으로 돈 것)이 끝나기를 기다린다. 같은 API·같은 산출물을 동시에
건드리면 서로를 덮으므로 **순차**여야 한다.
"""

from __future__ import annotations

import subprocess
import sys
import time

WAIT_PID = 27712          # 앞 체인 (옛 매핑)
STEPS = "trdar,flpop,incomeix,demand,gold,edges,trend,demand-csv,footfall,posting"


def _alive(pid: int) -> bool:
    """⚠ `tasklist` 는 **cp949** 로 찍는다(한글 Windows).

    `text=True` 로 받으면 UTF-8 로 디코드하려다 UnicodeDecodeError 가 나고
    `stdout` 이 `None` 이 되어 `in` 이 TypeError 로 죽는다(09-24 실측).
    바이트로 받아 디코드하지 않는다 — PID 는 ASCII 라 비교에 문제가 없다.
    """
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
    ).stdout or b""
    return str(pid).encode() in out


def main() -> int:
    print(f"=== [{time.strftime('%H:%M:%S')}] 앞 체인(PID {WAIT_PID}) 종료 대기 ===", flush=True)
    while _alive(WAIT_PID):
        time.sleep(30)
    print(f"=== [{time.strftime('%H:%M:%S')}] 앞 체인 종료 확인 — 재실행 시작 ===", flush=True)

    rc = subprocess.call([
        sys.executable, "-u", "scripts/run_batch2_chain.py", "--only", STEPS,
    ])
    print(f"=== [{time.strftime('%H:%M:%S')}] 재실행 종료 rc={rc} ===", flush=True)
    print("=== RERUN ALL DONE ===", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
