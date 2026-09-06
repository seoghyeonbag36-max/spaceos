"""Page 감사 입력 인벤토리. 원본은 읽기 전용, 출력은 docs/papers/audits 아래만 허용."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from data.config.page_hubs import ACTIVE_HUBS  # noqa: E402

BRONZE = {
    "bldg_polygons.geojson": "latest_lexical_day",
    "stores_raw.json": "latest_lexical_day",
    "licensing_biz.json": "latest_lexical_day",
    "bldg_ledger_raw.json": "all_snapshots_merge_evidence",
    "bldg_flr_raw.json": "all_snapshots_merge_evidence",
}
SILVER = ("building_attrs.json", "expos_units.json")
GOLD = ("building_vacancy.json", "page_building_master.geojson",
        "coverage.json", "calibration.json", "vacant_units.json")
RONE = ("rone_vac_mid.json", "rone_vac_small.json")


def git(*args: str, data: bytes | None = None, allowed: tuple[int, ...] = (0,)) -> bytes:
    result = subprocess.run(["git", *args], cwd=ROOT, input=data, capture_output=True)
    if result.returncode not in allowed:
        raise RuntimeError(f"git {args[0]} failed: {result.returncode}")
    return result.stdout


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("입력 경로가 저장소 밖을 가리킵니다")
    return path.relative_to(ROOT).as_posix()


def fingerprint(path: Path) -> tuple[str, int, int]:
    rel(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"해시 계산 중 변경: {rel(path)}")
    return digest.hexdigest(), after.st_size, after.st_mtime_ns


def inventory_paths() -> list[tuple[str, str, str, list[Path]]]:
    groups = []
    for slug in sorted(ACTIVE_HUBS):
        for name, policy in BRONZE.items():
            paths = sorted((ROOT / "data/bronze" / slug).glob(f"*/{name}"))
            groups.append((slug, name, policy, [p for p in paths if p.is_file()]))
        for layer, names in (("silver", SILVER), ("gold", GOLD)):
            for name in names:
                p = ROOT / "data" / layer / slug / name
                groups.append((slug, name, "fixed_path", [p] if p.is_file() else []))
    for name in RONE:
        paths = sorted((ROOT / "data/bronze/platform13").glob(f"*/{name}"))
        groups.append(("platform13", name, "latest_lexical_day", [p for p in paths if p.is_file()]))
    return groups


def temporal_metadata(path: Path) -> dict:
    # 수정 시각이나 폴더명을 관측일로 바꾸지 않는다. 거대한 원본 본문은 파싱하지 않는다.
    result = {"observation_period": None, "observation_status": "not_extracted",
              "retrieved_at": None, "retrieved_at_status": "not_verified",
              "declared_built_at": None}
    if path.name in {"coverage.json", "vacant_units.json"} or path.name in RONE:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            value = obj.get("built_at")
            result["declared_built_at"] = value if isinstance(value, str) else None
        elif path.name in RONE and isinstance(obj, list):
            quarters = sorted({str(row["quarter"]) for row in obj
                               if isinstance(row, dict) and row.get("quarter") is not None})
            result["observation_period"] = {"field": "quarter", "values": quarters}
            result["observation_status"] = "declared_in_source_not_independently_verified"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in args.run_id):
        raise ValueError("run-id에는 영문 소문자·숫자·하이픈·밑줄만 사용")
    output = ROOT / "docs/papers/audits" / args.run_id
    if not output.resolve().is_relative_to((ROOT / "docs/papers").resolve()) or output.exists():
        raise ValueError("출력 경로가 허용 범위 밖이거나 이미 존재합니다")
    started = now()
    head = git("rev-parse", "HEAD").decode().strip()
    branch = git("branch", "--show-current").decode().strip()
    if not branch.startswith(("chore/", "fix/")):
        raise ValueError("chore/* 또는 fix/* 브랜치에서 실행")
    tracked = set(git("ls-files", "-z").decode("utf-8").strip("\0").split("\0"))
    modified = set(git("diff", "--name-only", "HEAD", "-z").decode("utf-8").strip("\0").split("\0"))
    diff_hash = hashlib.sha256(git("diff", "--binary", "HEAD")).hexdigest()
    registry = ROOT / "data/config/page_hubs.py"
    registry_hash = fingerprint(registry)[0]
    groups = inventory_paths()
    group_signature = [(s, n, policy, [rel(p) for p in ps]) for s, n, policy, ps in groups]
    records = []
    selectors = []
    for slug, name, policy, paths in groups:
        selected = paths[-1:] if policy == "latest_lexical_day" else paths
        selectors.append({"scope": slug, "artifact": name, "policy": policy,
                          "available_paths": [rel(p) for p in paths],
                          "current_rebuild_inputs": [rel(p) for p in selected],
                          "selection_status": "available" if paths else "missing",
                          "historical_gold_input_verified": False})
        for path in paths:
            digest, size, mtime = fingerprint(path)
            relative = rel(path)
            layer = path.relative_to(ROOT).parts[1]
            row = {"path": relative, "scope": slug, "layer": layer, "artifact": name,
                   "sha256": digest, "bytes": size, "capture_mtime_ns": mtime,
                   "git_tracked": relative in tracked,
                   "git_modified_from_head": relative in modified if relative in tracked else None,
                   "cloud_access": "not_checked", "selection_policy": policy,
                   "selected_for_current_rebuild": path in selected,
                   "historical_gold_input_verified": False,
                   "collection_directory_label": path.parent.name if layer == "bronze" else None,
                   "collection_directory_semantics": "storage_label_not_verified_observation_date" if layer == "bronze" else None}
            row.update(temporal_metadata(path))
            records.append(row)
        if len(selectors) % 120 == 0:
            print(f"인벤토리 진행: {len(selectors)}/{len(groups)} 자료군, {len(records)} 파일", flush=True)

    untracked = [r["path"] for r in records if not r["git_tracked"]]
    ignored = set()
    if untracked:
        encoded = ("\0".join(untracked) + "\0").encode("utf-8")
        ignored = set(git("check-ignore", "-z", "--stdin", data=encoded, allowed=(0, 1))
                      .decode("utf-8").strip("\0").split("\0"))
    for row in records:
        row["git_ignored_when_untracked"] = row["path"] in ignored if not row["git_tracked"] else None

    # 환경변수·인증정보·원천 행을 출력하지 않고 코드 파일과 의존성 버전만 기록한다.
    code_paths = {p for base in ("data", "apps/backend/app") for p in (ROOT / base).rglob("*.py")
                  if not any(x in p.parts for x in (".venv", "venv", "__pycache__"))}
    code_paths.add(Path(__file__).resolve())
    code_paths.update(p for base in ("data", "apps/backend") for p in (ROOT / base).glob("*requirements*.txt"))
    code_records = []
    for p in sorted(code_paths):
        digest, size, mtime = fingerprint(p)
        code_records.append({"path": rel(p), "sha256": digest, "bytes": size, "capture_mtime_ns": mtime})

    changed = []
    for row in records + code_records:
        p = ROOT / row["path"]
        if not p.exists() or (p.stat().st_size, p.stat().st_mtime_ns) != (row["bytes"], row["capture_mtime_ns"]):
            changed.append(row["path"])
    ending_groups = inventory_paths()
    if group_signature != [(s, n, policy, [rel(p) for p in ps]) for s, n, policy, ps in ending_groups]:
        changed.append("input_path_set")
    if fingerprint(registry)[0] != registry_hash or git("rev-parse", "HEAD").decode().strip() != head:
        changed.append("registry_or_head")
    if changed:
        raise RuntimeError(f"관측 도중 변경되어 manifest를 생성하지 않음: {changed}")

    dependencies = {}
    for package in ("pandas", "numpy", "pyproj", "shapely", "geopandas", "fastapi", "pydantic"):
        try:
            dependencies[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = None
    missing = [s for s in selectors if not s["available_paths"]]
    counts = Counter(r["layer"] for r in records)
    hub_readiness = []
    for slug in sorted(ACTIVE_HUBS):
        own = [s for s in selectors if s["scope"] == slug]
        available = {s["artifact"] for s in own if s["available_paths"]}
        hub_readiness.append({"slug": slug,
            "gold_master_available": "page_building_master.geojson" in available,
            "core_bronze_families_available": all(n in available for n in BRONZE),
            "attrs_available": "building_attrs.json" in available,
            "historical_lineage": "unverified", "rebuild_test": "not_run",
            "missing_artifacts": [s["artifact"] for s in own if not s["available_paths"]]})
    summary = {"hubs": len(ACTIVE_HUBS), "files": len(records), "bytes": sum(r["bytes"] for r in records),
               "files_by_layer": dict(counts), "tracked_files": sum(r["git_tracked"] for r in records),
               "untracked_ignored_files": len(ignored - {""}), "missing_artifact_groups": len(missing),
               "gold_master_hubs": sum(h["gold_master_available"] for h in hub_readiness),
               "core_bronze_available_hubs": sum(h["core_bronze_families_available"] for h in hub_readiness),
               "attrs_available_hubs": sum(h["attrs_available"] for h in hub_readiness)}
    manifest = {"schema_version": "1", "audit_run_id": args.run_id, "started_at_utc": started,
        "completed_at_utc": now(), "scope": "Page 핵심 객체·층·서빙 자료 및 R-ONE 공실 앵커 보조자료",
        "not_in_scope": ["유동·밀도 레이어 원천", "Posting 비용 원천", "독립 현장 정답", "전체 저장소의 모든 데이터"],
        "capture": {"mode": "read_only_fingerprints_no_source_copies", "end_stat_and_pathset_check": "pass",
                    "immutable_snapshot": False, "historical_build_manifest_available": "not_established",
                    "warning": "비트 해시는 현재 파일의 지문이다. 과거 Gold 입력의 증명이나 원본 보존 사본이 아니다. 실행 전 재검증 필수."},
        "code": {"head": head, "branch": branch, "tracked_worktree_diff_sha256": diff_hash,
                 "scope": "data 및 backend app Python 파일·requirements; 완전한 환경 잠금 아님", "files": code_records},
        "environment": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                        "platform": platform.system(), "packages": dependencies},
        "hub_registry": {"path": "data/config/page_hubs.py", "sha256": registry_hash,
                         "active_hubs": [asdict(ACTIVE_HUBS[s]) for s in sorted(ACTIVE_HUBS)]},
        "selection_note": "정적 코드의 현재 입력 선택을 기록. 병합 자료군은 모든 보존 파일을 열거하며 행별 승자·완전성은 아직 검증하지 않음.",
        "summary": summary, "hub_readiness": hub_readiness, "selectors": selectors,
        "files": records, "missing": missing,
        "gates": {"inventory": "complete", "g0": "partial_fingerprints_captured_lineage_and_immutability_unverified",
                  "structural_audit": "not_run", "independent_review": "not_run", "reproduction": "not_run"}}
    output.mkdir(parents=True, exist_ok=False)
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (output / "manifest.json").write_text(payload, encoding="utf-8", newline="\n")
    fields = ["path", "scope", "layer", "artifact", "bytes", "sha256", "git_tracked",
              "git_modified_from_head", "git_ignored_when_untracked", "cloud_access", "selection_policy",
              "selected_for_current_rebuild", "collection_directory_label", "declared_built_at",
              "observation_status", "historical_gold_input_verified"]
    with (output / "inventory.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    (output / "manifest.sha256").write_text(fingerprint(output / "manifest.json")[0] + "  manifest.json\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": rel(output), "summary": summary, "gates": manifest["gates"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
