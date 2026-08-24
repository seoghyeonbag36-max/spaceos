"""무인 전체 검증 — 백엔드 테스트 + 프론트 타입체크·빌드를 순서대로 돌리고 결과를 남긴다.

왜 필요한가: 오늘 `ml/training/train_gnn.py` 의 조기 종료 기준을 바꿨다. 그 변경이
서빙·API 표면을 건드리지 않았다는 것은 **테스트가 통과해야** 말할 수 있는데,
사람이 자리에 없는 동안 돌려두면 돌아왔을 때 실측으로 시작할 수 있다.

판단이 전혀 안 들어가는 작업이라 무인 실행에 맞다 — 실패해도 고치지 않고 **기록만** 한다.
자동으로 고치기 시작하면, 자리에 없는 사이에 무엇이 왜 바뀌었는지 아무도 모르게 된다.

산출: reports/full_verify.json + reports/logs/verify_*.log
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "full_verify.json"
LOGDIR = ROOT / "reports" / "logs"

# (이름, 커맨드, 작업디렉터리, 셸필요)
STEPS = [
    ("backend-pytest", [sys.executable, "-m", "pytest", "-q"], ROOT / "apps" / "backend", False),
    ("gnn-import", [sys.executable, "-c",
                    "import ml.training.train_gnn as t; "
                    "print('SELECT_BY', t.SELECT_BY); "
                    "print('FLOOR', t.OFFPRIOR_TOP3_FLOOR)"], ROOT, False),
    ("pppp-status", [sys.executable, "scripts/pppp_status.py"], ROOT, False),
    # 프론트는 npm 이라 Windows 에서 셸이 필요하다(npm.cmd).
    ("frontend-build", "npm run build", ROOT / "apps" / "frontend", True),
]

TIMEOUT = 1800  # 스텝당 30분 — 무인이라 매달리지 않게 상한을 둔다


def _env() -> dict:
    e = dict(os.environ)
    # cp949 에는 em dash 가 없다 — 로그를 파일로 받을 때 UnicodeEncodeError 로 죽는다.
    e.update({"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    return e


def main() -> None:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    results = []
    started = datetime.now().isoformat(timespec="seconds")
    for name, cmd, cwd, shell in STEPS:
        log = LOGDIR / f"verify_{name}.log"
        t0 = datetime.now()
        if not Path(cwd).exists():
            results.append({"step": name, "status": "skipped",
                            "note": f"경로 없음: {cwd}"})
            continue
        try:
            r = subprocess.run(cmd, cwd=cwd, env=_env(), shell=shell,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace",
                               timeout=TIMEOUT)
            log.write_text(r.stdout or "", encoding="utf-8")
            status, code = ("pass" if r.returncode == 0 else "fail"), r.returncode
        except subprocess.TimeoutExpired:
            log.write_text(f"{TIMEOUT}초 초과", encoding="utf-8")
            status, code = "timeout", None
        except FileNotFoundError as e:
            log.write_text(str(e), encoding="utf-8")
            status, code = "missing-tool", None
        secs = round((datetime.now() - t0).total_seconds(), 1)
        results.append({"step": name, "status": status, "exit": code,
                        "seconds": secs, "log": str(log.relative_to(ROOT))})
        print(f"[verify] {name}: {status} ({secs}s)", flush=True)
        # 스텝마다 쓴다 — 도중에 전원이 나가도 거기까지는 남는다.
        OUT.write_text(json.dumps({"started": started, "results": results},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [r for r in results if r["status"] not in ("pass", "skipped")]
    print(f"[verify] 끝 — 실패 {len(bad)}건 / {len(results)}스텝", flush=True)


if __name__ == "__main__":
    main()
