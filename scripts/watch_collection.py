"""수집 로그 감시 — 거점이 끝날 때마다 1건씩, 프로세스가 죽으면 사유와 함께 보고.

building_vacancy(대장) / floor_capacity(층별개요) 두 수집기의 로그를 모두 읽는다.
거점 완료 시각은 로그가 아니라 bronze 산출물의 mtime 을 쓴다 — 완료 직후 기록되므로
폴링 간격과 무관하게 정확하다.

**drain-then-check**: 프로세스가 죽은 것을 감지하면 로그를 **다시 읽어** 남은 완료
이벤트를 처리한 뒤에 실패를 선언한다. 이 순서가 이 스크립트의 핵심이다.

  2026-07-26 songridan 오탐: 루프가 로그를 먼저 읽고(스냅샷) → 프로세스 생존을
  확인(PowerShell 호출에 ~1초)하는 순서였는데, 그 1초 사이에 수집기가 마지막 줄을
  쓰고 정상 종료했다. 스냅샷에는 완료 줄이 없고 프로세스는 죽어 있으니 "미완료 상태로
  사망"으로 판정했다. 실제로는 446/446동 exit=0 정상 완료였다.
  낡은 스냅샷으로 실패를 선언하면 안 된다 — 죽음을 봤으면 로그를 다시 읽어야 한다.

실행:
  python scripts/watch_collection.py --log data/logs/flrcap-10hubs.log --mode flrcap \
      --expect apgujeong-rodeo,yeonnam,ikseon
  python scripts/watch_collection.py --log data/logs/bldgvac.log --mode bldgvac \
      --expect ikseon,euljiro,hongdae
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 모드별 (완료 라인 정규식, 완료 시각을 읽을 bronze 파일명, 프로세스 식별 문자열)
MODES = {
    "bldgvac": (re.compile(r"\[gold:([a-z0-9-]+)\] building_vacancy\.json"),
                "bldg_ledger_raw.json", "building_vacancy"),
    "flrcap": (re.compile(r"\[flr-cap:([a-z0-9-]+)\] building_vacancy\.json 갱신"),
               "bldg_flr_raw.json", "floor_capacity"),
}


def read_log(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def bronze_mtime(slug: str, filename: str, date: str) -> dt.datetime | None:
    p = ROOT / "data" / "bronze" / slug / date / filename
    try:
        return dt.datetime.fromtimestamp(p.stat().st_mtime)
    except OSError:
        return None


def make_alive_check(needle: str):
    def alive() -> bool:
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" "
                 "| Select-Object -ExpandProperty CommandLine"],
                capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return True          # 감지 실패는 '살아있음' — 오탐 종료보다 낫다
        return any(needle in line for line in out.stdout.splitlines())
    return alive


def watch(read, alive, done_re, expect, on_event, interval=20.0, sleep=time.sleep) -> int:
    """폴링 루프. read/alive/sleep 를 주입받아 테스트 가능하게 한다.

    반환: 0 = 전 거점 완료, 1 = 미완료 상태로 프로세스 종료.
    """
    reported: list[str] = []

    def drain(text: str) -> None:
        """스냅샷에서 아직 보고하지 않은 완료 거점을 순서대로 내보낸다."""
        for slug in done_re.findall(text):
            if slug not in reported:
                reported.append(slug)
                on_event(slug)

    while True:
        drain(read())
        if all(s in reported for s in expect):
            return 0

        if not alive():
            # ── drain-then-check ──────────────────────────────────────────
            # 죽음을 확인한 뒤 로그를 **다시** 읽는다. 위의 스냅샷은 alive() 호출
            # (~1초) 이전 것이라, 그 사이에 쓰인 마지막 완료 줄이 빠져 있을 수 있다.
            drain(read())
            if all(s in reported for s in expect):
                return 0
            on_event(None, missing=[s for s in expect if s not in reported])
            return 1

        sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--mode", choices=sorted(MODES), required=True)
    ap.add_argument("--expect", required=True, help="쉼표로 구분한 거점 slug")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--interval", type=float, default=20.0)
    args = ap.parse_args()

    done_re, bronze_file, needle = MODES[args.mode]
    log = Path(args.log)
    expect = [s.strip() for s in args.expect.split(",") if s.strip()]
    prev = [None]           # 직전 거점 완료 시각 (소요시간 계산용)
    seen = [0]              # 보고한 거점 수

    def on_event(slug, missing=None):
        now = dt.datetime.now()
        if slug is None:
            print(f"[DEAD {now:%H:%M:%S}] 수집 프로세스 종료 — "
                  f"미완료 {len(missing)}거점: {', '.join(missing)}", flush=True)
            return
        seen[0] += 1
        end = bronze_mtime(slug, bronze_file, args.date) or now
        took = f" · {(end - prev[0]).total_seconds() / 60:.1f}분" if prev[0] else ""
        prev[0] = end
        print(f"[DONE {end:%H:%M:%S}] {slug} 완료{took} ({seen[0]}/{len(expect)})", flush=True)

    rc = watch(lambda: read_log(log), make_alive_check(needle), done_re, expect,
               on_event, interval=args.interval)
    if rc == 0:
        print(f"[ALL DONE {dt.datetime.now():%H:%M:%S}] {len(expect)}거점 완료", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
