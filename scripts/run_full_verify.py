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

# 백엔드 의존성(fastapi 등)은 `apps/backend/.venv` 에 들어간다 — CLAUDE.md 가 적은
# 정식 실행도 `cd apps/backend && .venv/bin/python -m pytest -q` 다. sys.executable 로
# 돌리면 그 venv 밖 인터프리터에서 25개 모듈이 ImportError 로 죽고, 무인 검증이
# **코드 결함이 아닌 이유로** 빨갛게 끝난다(2026-09-15 실측). venv 가 있으면 그것을 쓴다.
_BACKEND_VENV = ROOT / "apps" / "backend" / ".venv" / (
    "Scripts/python.exe" if os.name == "nt" else "bin/python")
BACKEND_PY = str(_BACKEND_VENV) if _BACKEND_VENV.exists() else sys.executable

# (이름, 커맨드, 작업디렉터리, 셸필요)
STEPS = [
    ("backend-pytest", [BACKEND_PY, "-m", "pytest", "-q"], ROOT / "apps" / "backend", False),
    # ⚠ **2026-09-24 추가.** 이 스텝이 없어서 로컬은 초록인데 CI 가 47건으로 깨졌다.
    #   `data/tests` 는 CI 의 "데이터 파이프라인 pytest" 잡이 도는 자리인데 여기에는
    #   없었고, 그래서 "정적 검증 통과"라고 보고한 뒤에야 드러났다. 거점을 늘리면
    #   `gold/{slug}/district_zones.json` 같은 **거점별 산출물이 없는 것**을 잡는 게
    #   정확히 이쪽 테스트다(파라미터라이즈가 거점마다 돌아 한 번에 수십 건이 깨진다).
    ("data-pytest", [sys.executable, "-m", "pytest", "data/tests", "-q"], ROOT, False),
    ("gnn-import", [sys.executable, "-c",
                    "import ml.training.train_gnn as t; "
                    "print('SELECT_BY', t.SELECT_BY); "
                    "print('FLOOR', t.OFFPRIOR_TOP3_FLOOR)"], ROOT, False),
    ("pppp-status", [sys.executable, "scripts/pppp_status.py"], ROOT, False),
    # 신청서 원고의 근거 검사 — docs/apply/ 가 비어 있으면 통과한다.
    ("application-check", [sys.executable, "scripts/check_application.py"], ROOT, False),
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
