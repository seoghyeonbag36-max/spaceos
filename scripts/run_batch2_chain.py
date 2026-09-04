"""서울 2차 12거점을 Page 밖의 세 트랙까지 끌어올리는 선형 체인 (2026-09-04).

## 무엇을 고치는가

08-30 에 12거점이 Page(Tier1 대장 실측)까지 서고 09-03 에 서빙에 올랐는데,
`DISTRICT_TRDAR`·`DISTRICT_PLACES` 매핑이 비어 있어 **Platform·Posting·Program
산출물에서 통째로 빠져 있었다**(실측 09-04, 전부 54/66):

    gold/{slug}/program_content_context.csv     54 — 12거점 없음
    gold/platform_page_footfall.json            54 — 〃
    gold/page_footfall_hourly.json              54 — 〃
    gold/platform_posting_inputs.json           54 — 〃
    gold/platform_industry_recommend.json       54 — 〃

수집이 덜 된 것이 아니라 **파이프라인이 12거점을 안 돌았다.** 매핑은 09-03 에
채워졌고(`reports/trdar_seoul_batch2_2026-09-03.json` 대조 전량 일치), 남은 것은
그 매핑 위에서 수집·빌드를 한 번 다시 도는 것뿐이다.

## 이미 끝난 단계는 다시 돌리지 않는다

09-03 수집분이 **이미 66거점**이다(실측: kakao 47,442행 / blog 23,966행 /
trdar_relm 245행 — 셋 다 district 66, batch2 12/12). R-ONE 도 09-01 분이 86거점을
덮는다. 그래서 기본 실행은 **분기 시계열 3종만** 다시 받는다:

    seoul_trdar_{stor,selng}  최신 2026-07-25 · 54거점 (batch2 0/12)
    seoul_trdar_flpop         〃
    seoul_trdar_ix            〃

`--recollect-all` 을 주면 카카오·블로그까지 전부 다시 받는다(쿼터를 다시 태운다).

## 순서가 왜 이런가

`build_gold --platform13` 이 분기 시계열·점포 노드를 동시에 먹고, 그 산출물을
엣지 빌드 → LSTM/GNN 이 받는다. Page 24시간 축(`build_hub_adong` → 생활인구 →
`build_page_footfall_hourly`)은 앞의 것과 독립이라 뒤에 붙였다 — 앞이 실패해도
이쪽은 돌 수 있게. `build_hub_adong` 은 카카오 역지오코딩이라 12거점 × 약 80콜이다.

실행:
    python scripts/run_batch2_chain.py                    # 전체
    python scripts/run_batch2_chain.py --from gold        # 수집 건너뛰고 빌드부터
    python scripts/run_batch2_chain.py --only trdar,gold  # 지정 단계만
    python scripts/run_batch2_chain.py --list             # 단계 목록만

산출: reports/batch2_chain.json + reports/logs/batch2_*.log
돌아와서 볼 것: python scripts/pppp_status.py  (54/66 이 66/66 이 됐는가)
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
OUT = ROOT / "reports" / "batch2_chain.json"
LOGDIR = ROOT / "reports" / "logs"

# (단계명, argv, 필수, 기본실행)
#   필수=True  실패하면 뒤를 안 돌린다 — 반쪽 산출물이 완성처럼 보이는 것을 막는다.
#   기본실행=False 는 09-03 수집분이 이미 66거점이라 --recollect-all 없이는 건너뛴다.
STEPS: list[tuple[str, list[str], bool, bool]] = [
    ("trdar",     ["data.collectors.seoul_trdar", "--platform13"],            False, True),
    ("flpop",     ["data.collectors.seoul_trdar", "--platform13-flpop"],      False, True),
    ("incomeix",  ["data.collectors.seoul_trdar", "--platform13-income-ix"],  False, True),
    ("kakao",     ["data.collectors.kakao_local", "--platform13"],            False, False),
    ("blog",      ["data.collectors.naver_blog", "--platform13"],             False, False),
    ("rone",      ["data.collectors.rone_rent"],                              False, False),
    ("datalab",   ["data.collectors.naver_datalab", "--hubs"],                False, True),
    # ⚠ `build_trdar_demand` 는 `build_gold --platform13` 에 **안 들어 있다**(별도 빌더다).
    #   빼면 `gold/features/trdar_demand.parquet` 가 54거점에 머물고, 그걸 먹는
    #   `build_page_footfall`(유동·밀도 레이어)과 `train_gnn` 의 `_demand` 블록이
    #   12거점을 못 본다 — 나머지가 다 66이라 더 안 보인다. 그래서 gold 앞에 세운다.
    ("demand",    ["data.pipelines.build_trdar_demand"],                     True,  True),
    ("gold",      ["data.pipelines.build_gold", "--platform13"],              True,  True),
    ("edges",     ["data.pipelines.build_store_graph_edges", "--platform13"], True,  True),
    # ⚠ `build_gold --platform13` 은 program_content_context.csv 를 **통째로 다시 쓴다**.
    #   그래서 그 CSV 에 행을 얹는 빌더는 gold 뒤에 **둘 다** 와야 한다:
    #     trend  — 검색 트렌드 라벨 (없으면 ha_guard 트렌드 검사가 조용히 통과)
    #     demand — 상권 수요신호 (없으면 리뷰 없는 공실에 댈 근거가 사라진다)
    #   2026-09-04 에 demand 를 빠뜨려 이 게이트가 81.8% → 1.5% 로 떨어졌다.
    ("trend",     ["data.pipelines.build_program_trend"],                     False, True),
    ("demand-csv", ["data.pipelines.build_program_demand"],                  False, True),
    ("footfall",  ["data.pipelines.build_page_footfall"],                     False, True),
    ("posting",   ["data.pipelines.build_posting_inputs"],                    False, True),
    ("lstm",      ["ml.training.train_lstm"],                                 False, True),
    ("gnn",       ["ml.training.train_gnn"],                                  False, True),
    ("adong",     ["data.pipelines.build_hub_adong"],                         False, True),
    ("livingpop", ["data.collectors.living_population_hourly", "--days", "28"], False, True),
    ("hourly",    ["data.pipelines.build_page_footfall_hourly"],              False, True),
]

_NAMES = [s[0] for s in STEPS]


def _env() -> dict:
    e = dict(os.environ)
    # cp949 콘솔은 로그의 em dash 에서 죽는다(CLAUDE.md · 08-19 실측).
    e.update({"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
              "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    return e


def _step(name: str, argv: list[str]) -> dict:
    log = LOGDIR / f"batch2_{name}.log"
    print(f"\n━━ {name} ({argv[0]}) — {datetime.now():%H:%M:%S}", flush=True)
    t0 = time.time()
    with log.open("w", encoding="utf-8") as fh:
        r = subprocess.run([sys.executable, "-u", "-m", *argv],
                           cwd=ROOT, env=_env(), stdout=fh, stderr=subprocess.STDOUT)
    secs = round(time.time() - t0, 1)
    tail = ""
    try:
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-4:])
    except OSError:
        pass
    print(f"[batch2] {name}: exit={r.returncode} ({secs}s)\n{tail}", flush=True)
    return {"step": name, "exit": r.returncode, "seconds": secs,
            "log": str(log.relative_to(ROOT))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", help="이 단계부터 (단계명)")
    ap.add_argument("--only", help="쉼표로 나열한 단계만")
    ap.add_argument("--recollect-all", action="store_true",
                    help="09-03 에 이미 66거점으로 받은 카카오·블로그·R-ONE 도 다시 받는다")
    ap.add_argument("--list", action="store_true", help="단계 목록만 출력")
    a = ap.parse_args()

    if a.list:
        for n, argv, crit, dflt in STEPS:
            print(f"{n:10s} {'필수' if crit else '   '} {'기본' if dflt else '옵션'}  {' '.join(argv)}")
        return 0

    if a.only:
        want = [w.strip() for w in a.only.split(",")]
        bad = [w for w in want if w not in _NAMES]
        if bad:
            print(f"모르는 단계: {bad} — 가능: {_NAMES}")
            return 2
        steps = [s for s in STEPS if s[0] in want]
    else:
        steps = STEPS
        if a.start:
            if a.start not in _NAMES:
                print(f"모르는 단계: {a.start} — 가능: {_NAMES}")
                return 2
            steps = steps[_NAMES.index(a.start):]
        if not a.recollect_all:
            steps = [s for s in steps if s[3]]

    LOGDIR.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rec: dict = {"started": datetime.now().isoformat(timespec="seconds"),
                 "plan": [s[0] for s in steps], "steps": []}
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    for name, argv, critical, _ in steps:
        res = _step(name, argv)
        rec["steps"].append(res)
        rec["updated"] = datetime.now().isoformat(timespec="seconds")
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        if res["exit"] != 0 and critical:
            rec["aborted"] = f"{name} 실패(필수 단계) — 뒤 단계는 돌리지 않는다"
            OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[batch2] {rec['aborted']}", flush=True)
            return 1

    failed = [s["step"] for s in rec["steps"] if s["exit"] != 0]
    rec["failed"] = failed
    rec["finished"] = datetime.now().isoformat(timespec="seconds")
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[batch2] 끝 — 실패 {failed or '없음'} · {OUT.relative_to(ROOT)}", flush=True)
    print("[batch2] 다음: python scripts/pppp_status.py (54/66 → 66/66 확인)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
