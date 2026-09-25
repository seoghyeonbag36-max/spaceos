"""채용 문서용 로컬 근거 감사. 원본은 읽기만 하고 집계와 해시만 기록한다."""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / "apps/backend")]

SOURCES = {
    "E01": ("apps/frontend/src/lib/naverMap.ts", "loadNaverMaps"),
    "E02": ("apps/backend/app/services/gold_vacancy.py", "build_cells"),
    "E03": ("apps/backend/app/services/districts.py", "cells_for"),
    "E04": ("apps/backend/app/services/building_history.py", "get_history"),
    "E05": ("apps/backend/app/services/industry_recommend.py", "recommend"),
    "E06": ("apps/backend/app/services/vacancy_forecast.py", "get_forecast"),
    "E07": ("apps/backend/app/services/marketing.py", "generate_program"),
    "E08": ("apps/backend/app/services/district_zones.py", "zones"),
    "E09": ("data/pipelines/build_gold.py", ""),
    "E10": ("data/pipelines/build_page_master.py", "_licensed_pip"),
    "E11": ("data/config/page_hubs.py", "ACTIVE_HUBS"),
    "E12": ("docs/papers/page-study/evidence-verification.json", ""),
    "E13": ("apps/backend/tests/conftest.py", "SPACEOS_"),
    "E14": ("apps/backend/app/services/districts.py", "recommend_tier"),
    "E15": ("apps/frontend/package.json", ""),
    "E16": ("apps/backend/app/main.py", "FastAPI"),
    "E17": ("ml/training/datasets.py", "load_gold"),
    "E18": ("ml/training/train_gnn.py", ""),
    "E19": ("ml/training/train_lstm.py", ""),
    "E20": ("apps/backend/app/services/vacant_inventory.py", ""),
    "E21": ("apps/frontend/src/lib/api.ts", ""),
}

def main() -> None:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               PLACEOS_LIVE_LLM="0", SPACEOS_LIVE_LLM="0",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    sources = {}
    for eid, (rel, symbol) in SOURCES.items():
        p = ROOT / rel
        raw = p.read_bytes()
        sources[eid] = {"path": rel, "symbol": symbol,
                        "symbol_present": not symbol or symbol in raw.decode("utf-8"),
                        "sha256": hashlib.sha256(raw).hexdigest()}
    from data.config.page_hubs import ACTIVE_HUBS
    from app.services import districts
    source_counts = collections.Counter()
    failures = []
    for slug in sorted(ACTIVE_HUBS):
        page = districts.PAGES_BY_ID.get(slug)
        if page is None:
            failures.append(slug)
            continue
        cells = districts.cells_for(page)
        source_counts[cells["vacancy_source"]] += 1
        if sum(c["capacity"] for c in cells["cells"]) != cells["capacity"]:
            failures.append(slug)
        if sum(c["vac_n"] for c in cells["cells"]) != cells["sum_vac"]:
            failures.append(slug)
    import pandas as pd
    ts_path = ROOT / "data/gold/platform13/platform_district_timeseries.parquet"
    df = pd.read_parquet(ts_path)
    ts = {"path": ts_path.relative_to(ROOT).as_posix(), "rows": len(df),
          "districts": int(df.district_id.nunique()),
          "quarter_min": str(df.quarter.min()), "quarter_max": str(df.quarter.max()),
          "quarters": int(df.quarter.nunique()), "columns": list(df.columns),
          "duplicate_district_quarter": int(df.duplicated(["district_id", "quarter"]).sum()),
          "missing_by_column": {k:int(v) for k,v in df.isna().sum().items()},
          "sha256": hashlib.sha256(ts_path.read_bytes()).hexdigest()}
    commands = []
    for args in [["scripts/pppp_status.py", "--json"], ["scripts/chain_status.py", "--all", "--json"]]:
        result = subprocess.run([sys.executable, "-X", "utf8", *args], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", env=env, timeout=180)
        entry = {"command": "python " + " ".join(args), "exit_code": result.returncode}
        try:
            parsed = json.loads(result.stdout)
            name = "status_pppp.json" if "pppp" in args[0] else "status_chain.json"
            (OUT / name).write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
            entry["result"] = name
        except ValueError:
            entry["parse"] = "실패"
        commands.append(entry)
    tests = ["tests/test_districts.py::test_list_districts",
             "tests/test_districts.py::test_gold_cells_are_internally_consistent",
             "tests/test_districts.py::test_lot_polygons_counted_once",
             "tests/test_districts.py::test_polygon_only_never_counted",
             "tests/test_building_history.py::test_history_absent_returns_empty_not_dummy",
             "tests/test_building_history.py::test_shared_lot_history_is_labeled_lot_scope"]
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
                            cwd=ROOT / "apps/backend", capture_output=True, text=True,
                            encoding="utf-8", env=env, timeout=180)
    # 외부 제출 패키지에는 이 로그를 넣지 않는다. 경로도 작업공간 상대경로로 바꾼다.
    output = (result.stdout + result.stderr).replace(str(ROOT), "<repo>")
    (OUT / "repository_tests.txt").write_text(output, encoding="utf-8")
    audit = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
             "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
             "python": sys.version.split()[0], "active_hubs": len(ACTIVE_HUBS),
             "serving_pages": len(districts.PAGES_BY_ID), "heatmap_source_counts": dict(source_counts),
             "heatmap_consistency_failures": failures, "timeseries": ts,
             "sources": sources, "status_commands": commands,
             "tests": {"names": tests, "exit_code": result.returncode,
                       "summary": output.splitlines()[-1] if output.splitlines() else "출력 없음"},
             "limitations": ["로컬 서비스 함수 및 선택 테스트 범위", "브라우저 및 배포 환경 미검증",
                             "ML 재학습과 LLM 실호출 미실행", "개인 기여 미확인"]}
    (OUT / "repository_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:audit[k] for k in ["commit", "active_hubs", "heatmap_source_counts", "heatmap_consistency_failures", "tests"]}, ensure_ascii=False, indent=2))
    print("시계열", ts["rows"], ts["districts"], ts["quarter_min"], ts["quarter_max"])

if __name__ == "__main__":
    main()
