"""조기 종료 기준 ablation — top1 / macro_f1 / offprior3 를 같은 조건으로 돌려 비교한다.

왜 러너가 따로 필요한가:
  ① 이 머신에서 GNN 학습이 무작위 에포크에서 **세그폴트**한다(2026-08-17: 11회 중 1회 완주).
     train_gnn.py 에 체크포인트 재개가 있으므로, 죽으면 다시 부르기만 하면 이어간다.
     사람이 붙어 있지 않은 동안 그 재호출을 대신 하는 것이 이 스크립트다.
  ② 세 기준을 **같은 조건**(seed·epochs·patience)으로 돌려야 비교가 성립한다.

⚠ 전 arm 이 `--no-save` 다. 서빙 산출물(models/gnn/*.json·pt)은 건드리지 않는다 —
  어느 기준이 이기는지 정하기 전에 산출물을 갈아치우면 /recommend-industry 응답이
  실험 도중에 바뀐다. 승자를 고른 뒤 사람이 저장 런을 따로 돌린다.

산출: reports/gnn_selectby_ablation.json (arm 별 metrics + 크래시 횟수)
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "gnn_selectby_ablation.json"
LOGDIR = ROOT / "reports" / "logs"
ARMS_DEFAULT = ("top1", "macro_f1", "offprior3")
EPOCHS = 600
PATIENCE = 80
MAX_RETRY = 40          # 세그폴트 재시도 상한 — 무한 루프로 밤새 돌지 않게 한다
METRIC_TAG = "[gnn·metrics]"


def _env() -> dict:
    # 스레드 1개 · UTF-8 은 이 저장소의 학습 실행 규약이다(CLAUDE.md).
    # cp949 에는 em dash 가 없어 로그 리다이렉트가 UnicodeEncodeError 로 죽는다.
    e = dict(os.environ)
    e.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
              "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    return e


def _run_arm(arm: str) -> dict:
    log = LOGDIR / f"gnn_{arm}.log"
    cmd = [sys.executable, "-u", "-m", "ml.training.train_gnn",
           "--epochs", str(EPOCHS), "--patience", str(PATIENCE),
           "--select-by", arm, "--no-save"]
    crashes, metrics = 0, None
    for attempt in range(1, MAX_RETRY + 1):
        # ⚠ stdout=PIPE 로 받아 종료 후에 쓰면 **도는 동안 진행이 안 보인다.**
        #   그래서 15시간짜리가 된 것을 아무도 모른 채 지나갔다(2026-08-24).
        #   자식의 stdout 을 파일에 직접 물려 실시간으로 흐르게 한다.
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"\n=== {arm} 시도 {attempt} · {datetime.now():%F %T} ===\n")
            fh.flush()
            start = fh.tell()      # 이번 시도가 쓰기 시작하는 위치
            r = subprocess.run(cmd, cwd=ROOT, env=_env(),
                               stdout=fh, stderr=subprocess.STDOUT)
        # 로그 전체를 훑으면 **이전 시도의 지표**를 주워올 수 있다 — 크래시 후
        # 재시도했는데 옛 성공 기록을 보고 '완주했다' 고 판정하면 최악이다.
        with log.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(start)
            tail = fh.read()
        for line in reversed(tail.splitlines()):
            if line.startswith(METRIC_TAG):
                # train_gnn 은 dict 를 repr 로 찍는다 — literal_eval 이면 충분하고
                # eval 과 달리 코드를 실행하지 않는다.
                try:
                    metrics = ast.literal_eval(line[len(METRIC_TAG):].strip())
                except (ValueError, SyntaxError):
                    metrics = None
                break
        if metrics is not None:
            return {"arm": arm, "metrics": metrics, "crashes": crashes,
                    "attempts": attempt, "log": str(log.relative_to(ROOT))}
        crashes += 1
        # 재개 파일이 있으면 이어간다. 없으면 처음부터인데, 그건 train_gnn 이 알아서 한다.
        time.sleep(3)
    return {"arm": arm, "metrics": None, "crashes": crashes,
            "attempts": MAX_RETRY, "log": str(log.relative_to(ROOT)),
            "note": f"{MAX_RETRY}회 재시도에도 완주 못 함 — 로그를 볼 것"}


def main(argv: list[str] | None = None) -> None:
    arms = tuple(argv) if argv else ARMS_DEFAULT
    unknown = [a for a in arms if a not in ARMS_DEFAULT]
    if unknown:
        raise SystemExit(f"알 수 없는 arm: {unknown} — {ARMS_DEFAULT} 중에서 고른다")
    LOGDIR.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now().isoformat(timespec="seconds")
    # 이미 끝난 arm 의 결과는 보존한다 — 한 arm 만 다시 돌릴 때 앞의 것이 날아가면
    # 비교표가 반쪽이 된다.
    results = []
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            results = [r for r in prev.get("results", [])
                       if r.get("arm") not in arms and r.get("metrics")]
            if results:
                print(f"[ablation] 기존 결과 이어받음: {[r['arm'] for r in results]}",
                      flush=True)
        except (ValueError, OSError):
            pass
    for arm in arms:
        print(f"[ablation] {arm} 시작 {datetime.now():%F %T}", flush=True)
        res = _run_arm(arm)
        results.append(res)
        m = res["metrics"]
        print(f"[ablation] {arm} 종료 — crashes {res['crashes']} · "
              f"off-prior {(m or {}).get('test_offprior_top3')} · "
              f"top3 {(m or {}).get(f'test_top3')} · "
              f"macro_f1 {(m or {}).get('test_macro_f1')}", flush=True)
        # arm 하나 끝날 때마다 쓴다 — 중간에 PC 가 죽어도 거기까지는 남는다.
        OUT.write_text(json.dumps(
            {"started": started, "epochs": EPOCHS, "patience": PATIENCE,
             "saved_artifacts": False, "results": results},
            ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ablation] 전부 끝 — {OUT.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
