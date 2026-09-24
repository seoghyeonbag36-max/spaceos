#!/usr/bin/env python
"""15거점 층별개요(정밀분모) 수집 — 2026-09-24 루프 사이클.

전유부(대장)가 15거점 전부 완료된 뒤의 다음 한 수다. 대상과 그룹 분리는
`scripts/quota_preflight.py` 가 찍어 준 것을 그대로 쓴다 — 손으로 고르지 않는다.

  그룹1: floor_ouln 이 0 인 10거점 → 플래그 없이 전량 (재수집 낭비가 없다)
  그룹2: floor_ouln 을 이미 가진 5거점 → `--only-approx` 로 미시도분만

⚠ 반드시 **순차**로 돈다. 429 는 오퍼레이션이 아니라 키 단위라 두 수집기를 동시에
  돌리면 서로를 죽이고 하루치를 통째로 버린다 (skills/quota §하지 말 것 1).

재개: `floor_capacity` 가 bronze 시도이력을 보고 완료분을 건너뛴다. 죽었으면 그냥
  다시 부르면 이어받는다 — `--force` 는 그 재개를 무효로 만드니 쓰지 않는다.
"""

import subprocess
import sys
import time

GROUPS = [
    # floor_ouln 0 인 10거점 — 미시도 3,978동
    (
        [
            "seochoyeok", "dogok", "guui", "yangjae", "bonseobu",
            "gildong", "gurojeonhwa", "jamsil-tour", "gurodigital", "nowon",
        ],
        [],
    ),
    # floor_ouln 보유 5거점 — 미시도 412동만
    (
        ["daerim", "poi", "bangbang", "maebong", "ydp-gucheong"],
        ["--only-approx"],
    ),
]


def main() -> int:
    for idx, (slugs, flags) in enumerate(GROUPS, start=1):
        label = " ".join(flags) or "(전량)"
        print(
            f"=== [{time.strftime('%H:%M:%S')}] GROUP{idx} START {label} "
            f"{len(slugs)}거점: {' '.join(slugs)} ===",
            flush=True,
        )
        cmd = [sys.executable, "-u", "-m", "data.collectors.floor_capacity", *flags, *slugs]
        rc = subprocess.call(cmd)
        print(f"=== [{time.strftime('%H:%M:%S')}] GROUP{idx} DONE rc={rc} ===", flush=True)

    print("=== ALL DONE ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
