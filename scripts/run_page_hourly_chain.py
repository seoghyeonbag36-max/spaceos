"""Page 24시간 축 체인 — hub_adong 완주를 기다린 뒤 수집 → Gold 까지 이어 돌린다.

## 왜 체인인가

세 단계가 **앞의 산출물을 입력으로** 받는다:

  1. `build_hub_adong`            거점 ↔ 행정동 (카카오 역지오코딩, 약 80콜/거점 → 2시간대)
  2. `living_population_hourly`   행정동 시간대별 생활인구 (하루 11콜 × 28일)
  3. `build_page_footfall_hourly` 거점 24시간 프로파일 (Gold)

1번이 도는 동안 2번을 돌리면 **아직 매핑에 없는 거점의 행정동을 빼놓고** Bronze 를
만든다. 그 결손은 날짜 건너뛰기 때문에 영구화된다 — 그래서 기다린다.
(수집기의 `_already()` 가 행수로 재검사하므로 결손 파일은 다시 받아지지만,
애초에 두 번 받을 이유가 없다.)

## 1번이 안 끝나면

프로세스가 사라졌는데 거점 수가 모자라면 **거기까지로 진행한다.** 무한정 기다리는
것보다 낫다 — 부분 산출물이라도 Gold 가 `sample` 과 `hours_covered` 로 범위를
밝히므로, 덜 채워진 것이 조용히 완성처럼 보이지는 않는다.

실행: python scripts/run_page_hourly_chain.py [--days 28] [--hubs 54]
산출: reports/page_hourly_chain.json + reports/logs/page_hourly_*.log
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB_ADONG = ROOT / "data" / "silver" / "hub_adong.json"
OUT = ROOT / "reports" / "page_hourly_chain.json"
LOGDIR = ROOT / "reports" / "logs"

POLL_S = 60
MAX_WAIT_S = 4 * 3600        # 4시간이면 80콜/거점 × 54거점 에 충분히 여유가 있다


def _env() -> dict:
    e = dict(os.environ)
    # cp949 콘솔에서 em dash 에 죽는 것을 막는다(CLAUDE.md · 08-19 실측).
    e.update({"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
              "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    return e


def hub_count() -> int:
    if not HUB_ADONG.exists():
        return 0
    try:
        return len(json.loads(HUB_ADONG.read_text(encoding="utf-8")).get("hubs") or {})
    except (ValueError, OSError):
        return 0


def hub_adong_running() -> bool:
    """build_hub_adong 프로세스가 아직 있나 — 커맨드라인으로 판정한다."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |"
             " Where-Object { $_.CommandLine -like '*build_hub_adong*' } |"
             " Measure-Object).Count"],
            capture_output=True, text=True, timeout=60)
        return int((r.stdout or "0").strip() or 0) > 0
    except Exception:
        # 판정 불가면 '돌고 있다'고 본다 — 기다리다 타임아웃하는 쪽이,
        # 아직 도는 중인데 반쪽 매핑으로 수집을 시작하는 쪽보다 낫다.
        return True


def wait_for_hub_adong(target: int) -> dict:
    t0 = time.time()
    last = -1
    while True:
        n = hub_count()
        if n != last:
            print(f"[chain] hub_adong {n}/{target}거점 · {datetime.now():%T}", flush=True)
            last = n
        if n >= target:
            return {"waited_s": round(time.time() - t0), "hubs": n, "why": "완주"}
        if not hub_adong_running():
            # 파일은 run() 끝에 한 번 쓰이므로, 프로세스가 사라진 뒤의 값이 최종이다.
            n = hub_count()
            return {"waited_s": round(time.time() - t0), "hubs": n,
                    "why": f"프로세스 종료(거점 {n}/{target})"}
        if time.time() - t0 > MAX_WAIT_S:
            return {"waited_s": round(time.time() - t0), "hubs": n,
                    "why": f"{MAX_WAIT_S // 3600}시간 대기 초과"}
        time.sleep(POLL_S)


def step(name: str, cmd: list[str]) -> dict:
    log = LOGDIR / f"page_hourly_{name}.log"
    t0 = time.time()
    with log.open("w", encoding="utf-8") as fh:
        r = subprocess.run(cmd, cwd=ROOT, env=_env(),
                           stdout=fh, stderr=subprocess.STDOUT)
    secs = round(time.time() - t0, 1)
    tail = ""
    try:
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace")
                         .splitlines()[-3:])
    except OSError:
        pass
    print(f"[chain] {name}: exit={r.returncode} ({secs}s)\n{tail}", flush=True)
    return {"step": name, "exit": r.returncode, "seconds": secs,
            "log": str(log.relative_to(ROOT))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--hubs", type=int, default=54,
                    help="이 거점 수가 채워지면 다음 단계로 넘어간다")
    a = ap.parse_args()
    LOGDIR.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    rec: dict = {"started": datetime.now().isoformat(timespec="seconds")}
    rec["wait"] = wait_for_hub_adong(a.hubs)
    print(f"[chain] 대기 종료 — {rec['wait']}", flush=True)

    if rec["wait"]["hubs"] == 0:
        rec["aborted"] = "hub_adong 산출물이 비어 있다 — 수집을 시작하지 않는다"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[chain] 중단: {rec['aborted']}", flush=True)
        return

    rec["steps"] = []
    for name, cmd in (
        ("collect", [sys.executable, "-u", "-m",
                     "data.collectors.living_population_hourly",
                     "--days", str(a.days)]),
        ("gold", [sys.executable, "-u", "-m",
                  "data.pipelines.build_page_footfall_hourly"]),
    ):
        res = step(name, cmd)
        rec["steps"].append(res)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        if res["exit"] != 0:
            print(f"[chain] {name} 실패 — 뒤 단계는 돌리지 않는다", flush=True)
            break

    print(f"[chain] 끝 — {OUT.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
