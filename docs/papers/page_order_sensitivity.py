"""사후 탐색: 동일 지번의 다중 폴리곤 진단과 행 순서 민감도. 기존 집계 코드는 변경하지 않는다."""
from __future__ import annotations
import copy
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/"apps/backend"),str(ROOT/"docs/papers")]
import run_page_quality_audit as audit
from app.services import gold_vacancy
from data.config.page_hubs import ACTIVE_HUBS


def main():
    audit.protect_writes()
    plan={"created_at_utc":datetime.now(timezone.utc).isoformat(),"status":"post_hoc_exploratory",
          "trigger":"broad same-lot signature check flagged different capacities; all inspected examples used polygon approximations",
          "scope":"qualify flags by measurement path; reorder identical feature multiset without changing values or production exclusions",
          "variants":["reverse","sort_by_id","shuffle_seed_20260906"],
          "outcomes":["aggregate equality","changed grid cell values and membership"],
          "not_claimed":"independent ground truth, field accuracy, maximum possible sensitivity"}
    audit.write(audit.BASE/"exploratory-order-plan.json",plan)
    reports=[]; qualifications=[]
    flags=audit.read(audit.BASE/"findings.json")
    flagged=defaultdict(set)
    for r in flags:
        if r["rule"]=="within_lot_values_consistent" and r["result"]=="fail":flagged[r["hub"]].add(r["entity_key"])
    original_loader=gold_vacancy.load_master
    try:
        for slug in sorted(ACTIVE_HUBS):
            fc=audit.read(ROOT/f"data/gold/{slug}/page_building_master.geojson")
            by=defaultdict(list)
            for f in fc["features"]:by[f["properties"].get("pnu") or f["properties"].get("id")].append(f)
            for key in sorted(flagged[slug]):
                fs=by[key]
                served=[f for f in fs if audit.eligible(f)]
                qualifications.append({"hub":slug,"lot_key":key,"polygons":len(fs),"eligible_polygons":len(served),
                    "methods":sorted({f["properties"]["capacity_method"] for f in fs}),
                    "sources":sorted({f["properties"]["source"] for f in fs}),
                    "assessment":"scope_mismatch_in_broad_rule_not_confirmed_error" if not served else "review_required",
                    "why":"polygon-derived approximations need not have identical capacity across buildings sharing a parcel; serving excludes them" if not served else "eligible values require review"})
            gold_vacancy.load_master=lambda _slug, current=fc:current
            baseline=gold_vacancy.build_cells(slug,audit.grid_for(slug))
            if baseline is None:raise RuntimeError("No serving baseline: "+slug)
            basecells={(r["i"],r["j"]):r for r in baseline["cells"]}
            variants={"reverse":list(reversed(fc["features"])),"sort_by_id":sorted(fc["features"],key=lambda f:str(f["properties"].get("id")))}
            shuffled=list(fc["features"]);random.Random(20260906).shuffle(shuffled);variants["shuffle_seed_20260906"]=shuffled
            for label,features in variants.items():
                trial={**fc,"features":features}
                gold_vacancy.load_master=lambda _slug,current=trial:current
                result=gold_vacancy.build_cells(slug,audit.grid_for(slug))
                newcells={(r["i"],r["j"]):r for r in result["cells"]}
                common=set(basecells)&set(newcells)
                diffs=[abs(newcells[k]["v"]-basecells[k]["v"]) for k in common]
                reports.append({"hub":slug,"variant":label,
                    "aggregate_unchanged":all(baseline[k]==result[k] for k in ("capacity","sum_stores","sum_vac","buildings","avg_vacancy","inventory_coverage_pct","anchor_pct","anchor_gap_pp")),
                    "baseline_cells":len(basecells),"variant_cells":len(newcells),
                    "entered_cells":len(set(newcells)-set(basecells)),"exited_cells":len(set(basecells)-set(newcells)),
                    "common_cells":len(common),"changed_common_cell_values":sum(v>0 for v in diffs),
                    "max_abs_common_cell_vacancy_delta_pp":max(diffs) if diffs else None,
                    "changed_common_capacity_or_active":sum(any(basecells[k][f]!=newcells[k][f] for f in ("capacity","stores")) for k in common)})
    finally:gold_vacancy.load_master=original_loader
    audit.write(audit.BASE/"same-lot-flag-qualification.json",qualifications)
    audit.write(audit.BASE/"order-sensitivity.json",reports)
    print(json.dumps({"qualified_lots":len(qualifications),"eligible_flagged_lots":sum(q["eligible_polygons"]>0 for q in qualifications),
        "trial_count":len(reports),"aggregate_changed_trials":sum(not r["aggregate_unchanged"] for r in reports),
        "cell_affected_hubs":len({r["hub"] for r in reports if r["changed_common_capacity_or_active"] or r["entered_cells"] or r["exited_cells"]})},ensure_ascii=False))


if __name__=="__main__":main()
