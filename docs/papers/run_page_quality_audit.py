"""Page 구조·표집·영향·재현성 감사. 원본 수정/네트워크 호출 없이 연구 폴더에만 출력."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/backend")]
BASE = ROOT / "docs/papers/audits/page-analysis-20260906"
MANIFEST = ROOT / "docs/papers/audits/page-inventory-20260906/manifest.json"
from data.config.page_hubs import ACTIVE_HUBS


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write(p, obj):
    p = Path(p)
    if not p.resolve().is_relative_to(BASE.resolve()):
        raise ValueError("연구 출력 경계 밖")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")


def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(4*1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def canon(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def csvout(name, rows):
    if not rows:
        return
    with (BASE/name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def verify_manifest(m):
    expected = MANIFEST.with_name("manifest.sha256").read_text().split()[0]
    if sha(MANIFEST) != expected:
        raise RuntimeError("manifest 해시 불일치")
    def check(r):
        p = ROOT/r["path"]
        return r["path"] if not p.is_file() or sha(p) != r["sha256"] else None
    with ThreadPoolExecutor(max_workers=4) as pool:
        failed = [x for x in pool.map(check, m["files"]+m["code"]["files"]) if x]
    if failed:
        raise RuntimeError("입력/코드 변경: "+repr(failed))
    # 추가 스냅샷도 기존 run에 조용히 혼입하지 않는다.
    for s in m["selectors"]:
        if s["policy"] != "fixed_path":
            actual = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/"data/bronze"/s["scope"]).glob("*/"+s["artifact"]) if p.is_file())
            if actual != s["available_paths"]:
                raise RuntimeError("입력 경로 집합 변경")
    return {"manifest_sha256": sha(MANIFEST), "data_files_rehashed": len(m["files"]),
            "code_files_rehashed": len(m["code"]["files"]), "status": "pass"}


def protect_writes():
    def guard(event, args):
        if event == "socket.connect":
            raise RuntimeError("감사 중 네트워크 연결 금지")
        if event == "open":
            path, mode, flags = args
            if isinstance(path, (str, bytes, os.PathLike)) and ((isinstance(mode,str) and any(c in mode for c in "wax+")) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))):
                if not Path(os.fsdecode(path)).resolve().is_relative_to(BASE.resolve()):
                    raise RuntimeError("원본 쓰기 차단: "+str(path))
    sys.addaudithook(guard)


def selected(m, slug, name):
    s = next(s for s in m["selectors"] if s["scope"] == slug and s["artifact"] == name)
    return [ROOT/p for p in s["current_rebuild_inputs"]]


def grid_for(slug):
    from app.data.seoul_pages import DISTRICTS_BY_ID
    if slug in DISTRICTS_BY_ID:
        return DISTRICTS_BY_ID[slug]["grid"]
    from app.data.measured_pages import _grid
    return _grid(ACTIVE_HUBS[slug])


def geometry_basic(g):
    if not isinstance(g,dict) or g.get("type") not in {"Polygon","MultiPolygon"}:
        return False
    polys = [g.get("coordinates",[])] if g["type"] == "Polygon" else g.get("coordinates",[])
    if not polys:
        return False
    for poly in polys:
        if not poly:
            return False
        for ring in poly:
            if len(ring)<4 or ring[0] != ring[-1]:
                return False
            if any(len(pt)<2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in pt[:2]) or not (-180<=pt[0]<=180 and -90<=pt[1]<=90) for pt in ring):
                return False
    return True  # 위상 유효성·자가교차까지 확인한 것은 아니다.


def num(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def eligible(f):
    p=f["properties"]
    g=f.get("geometry") or {}
    return (num(p.get("capacity")) and p["capacity"]>0 and p.get("capacity_method")=="floor_ouln"
            and p.get("source")!="polygon_only" and g.get("type")=="Polygon" and bool(g.get("coordinates")))


def unit(p):
    if isinstance(p.get("com_floors"),list) and p["com_floors"]:
        return "floor"
    if p.get("capacity_method")=="expos_units":
        return "unit"
    return "unknown_or_proxy"


def audit(m):
    from data.pipelines.build_page_master import _classify, _pip, _rings
    rule_counts=defaultdict(Counter)
    failures=[]; hubs=[]; entities={}; releases=[]; impact=[]; rawstats=[]
    def check(slug,key,rule,value):
        result="not_evaluable" if value is None else "pass" if value else "fail"
        rule_counts[rule][result]+=1
        if result!="pass":
            failures.append({"hub":slug,"entity_key":key,"rule":rule,"result":result,
                             "interpretation":"structural_check_not_independent_ground_truth"})
        return result=="fail"
    for idx,slug in enumerate(sorted(ACTIVE_HUBS)):
        fc=read(ROOT/f"data/gold/{slug}/page_building_master.geojson")
        feats=fc["features"]
        ids=Counter(f["properties"].get("id") for f in feats)
        source_polys=read(selected(m,slug,"bldg_polygons.geojson")[0])["features"]
        source_pnu={f["properties"].get("pnu") for f in source_polys}
        rings=defaultdict(list)
        for f in source_polys:
            rings[f["properties"].get("pnu")].extend(_rings(f["geometry"]))
        seen={}; field_conflicts=0; eligible_rows=[]
        for i,f in enumerate(feats):
            p=f["properties"]; key=p.get("pnu") or f"unresolved:{slug}:{p.get('id')}:{i}"
            bad=False
            bad |= check(slug,key,"master_id_unique",ids[p.get("id")]==1 if p.get("id") else None)
            bad |= check(slug,key,"master_pnu_in_current_polygon_source",p["pnu"] in source_pnu if p.get("pnu") else None)
            bad |= check(slug,key,"geometry_basic",geometry_basic(f.get("geometry")))
            c,a=p.get("capacity"),p.get("active")
            valid=num(c) and c>0 and num(a) and 0<=a<=c
            bad |= check(slug,key,"capacity_active_range",valid)
            rate=p.get("vacancy_rate")
            bad |= check(slug,key,"vacancy_formula",abs(rate-round((1-min(a/c,1))*100,1))<1e-8 if valid and num(rate) else None)
            bad |= check(slug,key,"status_formula",p.get("status")==_classify(a/c) if valid else None)
            u=unit(p)
            if u=="floor":
                com=p["com_floors"]; occ=p.get("occ_floors"); unk=p.get("unknown_n")
                floor_ok=isinstance(occ,list) and num(unk) and len(com)==len(set(com)) and set(occ)<=set(com) and len(occ)==len(set(occ)) and c==len(set(com)) and a==len(occ)+unk and 0<=unk<=c-len(occ)
                bad |= check(slug,key,"floor_semantics",floor_ok)
                lo,hi=p.get("vacancy_rate_lo"),p.get("vacancy_rate_hi")
                bad |= check(slug,key,"floor_interval_formula",0<=lo<=hi<=100 and abs(lo-round((1-a/c)*100,1))<1e-8 and abs(hi-round((1-len(occ)/c)*100,1))<1e-8 if floor_ok and num(lo) and num(hi) else None)
            signature={k:p.get(k) for k in ("capacity","active","capacity_method","source","vacancy_rate","com_floors","occ_floors","unknown_n")}
            if key in seen and seen[key]!=signature:
                field_conflicts+=1; bad |= check(slug,key,"within_lot_values_consistent",False)
            elif key not in seen:
                check(slug,key,"within_lot_values_consistent",True)
            seen.setdefault(key,signature)
            entity=entities.setdefault(key,{"entity_key":key,"hubs":set(),"units":set(),"eligible":False,"flagged":False})
            entity["hubs"].add(slug); entity["units"].add(u); entity["eligible"] |= eligible(f); entity["flagged"] |= bad
            if eligible(f) and key not in {k for k,_ in eligible_rows}:
                eligible_rows.append((key,p))
        # 분모가 전역 전체 상권이 아니라 이 거점의 현행 집계 프레임임을 유지한다.
        cap=sum(p["capacity"] for _,p in eligible_rows)
        act=sum(min(p.get("active") or 0,p["capacity"]) for _,p in eligible_rows)
        floor_rows=[(k,p) for k,p in eligible_rows if unit(p)=="floor" and isinstance(p.get("occ_floors"),list) and num(p.get("unknown_n"))]
        floor_c=sum(p["capacity"] for _,p in floor_rows)
        lower_active=sum(p["active"] for _,p in floor_rows)
        upper_unknown_active=sum(len(p["occ_floors"]) for _,p in floor_rows)
        bounds={"hub":slug,"eligible_lots":len(eligible_rows),"floor_lots":len(floor_rows),"floor_capacity":floor_c,
                "floor_vacancy_lower_pct":100*(1-lower_active/floor_c) if floor_c else None,
                "floor_vacancy_upper_pct":100*(1-upper_unknown_active/floor_c) if floor_c else None,
                "range_width_pp":100*(lower_active-upper_unknown_active)/floor_c if floor_c else None,
                "interpretation":"existing_unknown_floor_assignment_range_not_confidence_interval"}
        impact.append(bounds)
        cov=read(ROOT/f"data/gold/{slug}/coverage.json")
        check(slug,slug,"coverage_shown_equals_master",cov.get("shown")==len(feats))
        check(slug,slug,"temporal_observation_alignment",None)
        hubs.append({"hub":slug,"polygons":len(feats),"lots":len(seen),"eligible_lots":len(eligible_rows),
                     "capacity":cap,"active":act,"vacancy_pct":round((1-act/cap)*100,2) if cap else None,
                     "unit_counts":dict(Counter(unit(p) for _,p in eligible_rows)),"conflicting_duplicate_rows":field_conflicts})
        stores=read(selected(m,slug,"stores_raw.json")[0]); storeids=Counter(r.get("bizesId") for r in stores)
        in_frame=outside=missing_geo=0
        for r in stores:
            if r.get("lnoCd") not in rings:
                continue
            in_frame+=1
            try: x,y=float(r.get("lon")),float(r.get("lat"))
            except (ValueError,TypeError): missing_geo+=1;continue
            if not (math.isfinite(x) and math.isfinite(y)):
                missing_geo+=1; continue
            if not any(_pip(x,y,ring) for ring in rings[r["lnoCd"]]): outside+=1
        rawstats.append({"hub":slug,"stores":len(stores),"missing_store_ids":storeids.get(None,0)+storeids.get("",0),
                         "duplicate_store_id_excess":sum(n-1 for k,n in storeids.items() if k and n>1),
                         "store_rows_with_matching_pnu":in_frame,"outside_same_pnu_footprint":outside,
                         "coordinates_not_evaluable":missing_geo,"note":"coordinate_disagreement_not_confirmed_misassignment; point_on_boundary_may_count_outside"})
        # 릴리스 비교는 각 거점의 최초/최종 보존 점포 파일. 과거 범위·관측 시점 동일성 미확인.
        ss=next(s for s in m["selectors"] if s["scope"]==slug and s["artifact"]=="stores_raw.json")
        if len(ss["available_paths"])>1:
            old=read(ROOT/ss["available_paths"][0]); new=stores
            def indexed(rows):
                counts=Counter(r.get("bizesId") for r in rows)
                return {r["bizesId"]:r for r in rows if r.get("bizesId") and counts[r["bizesId"]]==1}
            aa,bb=indexed(old),indexed(new); common=set(aa)&set(bb)
            fields=("lnoCd","bldMngNo","flrNo","hoNo","lon","lat","indsLclsCd")
            releases.append({"hub":slug,"old":ss["available_paths"][0],"new":ss["available_paths"][-1],
                "common_unique_ids":len(common),"entered_ids":len(set(bb)-set(aa)),"exited_ids":len(set(aa)-set(bb)),
                "changed_common_ids":sum(any(aa[k].get(f)!=bb[k].get(f) for f in fields) for k in common),
                "changes_by_field":{f:sum(aa[k].get(f)!=bb[k].get(f) for k in common) for f in fields},
                "claim":"release_difference_only_not_error_or_business_turnover"})
        if (idx+1)%10==0: print(f"구조 감사 {idx+1}/{len(ACTIVE_HUBS)}",flush=True)
    write(BASE/"structural-audit.json",{"rules":dict(rule_counts),"hubs":hubs,"raw_store_diagnostics":rawstats,
          "excluded_checks":["full_geometry_topology","independent_ground_truth","all_ledger_rows","reconstructed_all_join_edges"],
          "legacy_lineage_status":"not_verified"})
    write(BASE/"findings.json",failures); write(BASE/"impact-intervals.json",impact);write(BASE/"release-comparison.json",releases)
    csvout("hub-summary.csv",hubs);csvout("impact-intervals.csv",impact)
    strata=defaultdict(list)
    for entity in entities.values():
        entity["hubs"]=sorted(entity["hubs"]);entity["units"]=sorted(entity["units"])
        st="+".join(entity["units"])+"|eligible="+str(entity["eligible"])+"|flagged="+str(entity["flagged"])
        strata[st].append(entity)
    rng=random.Random(20260906); sample=[]; design=[]
    for st,items in sorted(strata.items()):
        items=sorted(items,key=lambda r:r["entity_key"])
        n=min(len(items),max(2,math.ceil(200*len(items)/len(entities))))
        design.append({"stratum":st,"population":len(items),"sample":n,"inclusion_probability":n/len(items)})
        for e in rng.sample(items,n):
            sample.append({"entity_key":e["entity_key"],"hubs":"|".join(e["hubs"]),"stratum":st,
                           "inclusion_probability":n/len(items),"sampling_weight":len(items)/n,
                           "reviewer_a":"","reviewer_b":"","reference_observed_at":"",
                           "evidence_ref":"","review_label":"unresolved","reason":"independent_review_not_performed"})
    csvout("independent-review-sample.csv",sample)
    write(BASE/"sample-design.json",{"seed":20260906,"target_budget":200,"actual_sample":len(sample),
        "frame_size":len(entities),"frame_sha256":canon([e for k,e in sorted(entities.items())]),"strata":design,
        "review_status":"not_performed","error_rate":None,"reason":"human_or_temporally_matched_reference_unavailable",
        "scope":"master_global_lots_only; unmatched_raw_entities_not_sampled_in_this_run",
        "plan_deviation":"operational pilot allocation; no claimed target precision; strata fixed in code before execution"})
    legacy=[]
    for p in sorted((ROOT/"data/validation").glob("*.csv")):
        with p.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
        legacy.append({"path":p.relative_to(ROOT).as_posix(),"sha256":sha(p),"rows":len(rows),
            "nonempty_labels":sum(bool(r.get("label_actual","").strip()) for r in rows),
            "ai_marked_memos":sum("AI" in r.get("memo","") for r in rows),
            "independent_current_truth":"not_established"})
    write(BASE/"legacy-review-evidence.json",legacy)


def worker(m,tag):
    from data.pipelines import build_page_master as builder
    from app.services import gold_vacancy, building_vacancy
    dest=BASE/tag
    dest.mkdir(exist_ok=False)
    protect_writes()
    mapping={(s["scope"],s["artifact"]):s["current_rebuild_inputs"] for s in m["selectors"]}
    def pinned(slug,name):
        paths=mapping[(slug,name)]
        return read(ROOT/paths[-1]) if paths else None
    builder.load_latest=pinned
    builder.GOLD=dest/"gold"
    results=[]
    for slug in sorted(ACTIVE_HUBS):
        target=dest/"gold"/slug;target.mkdir(parents=True)
        for name in ("building_vacancy.json","calibration.json"):
            shutil.copyfile(ROOT/"data/gold"/slug/name,target/name)
        ok=builder.run(ACTIVE_HUBS[slug])
        if not ok:
            raise RuntimeError("재빌드 실패: "+slug)
        building_vacancy._GOLD_DIR=dest/"gold";building_vacancy._cache.clear()
        gold_vacancy._GOLD_DIR=dest/"gold";gold_vacancy._anchor_cache.clear()
        result=gold_vacancy.build_cells(slug,grid_for(slug))
        write(dest/"serving"/(slug+".json"),result)
        results.append({"hub":slug,"status":"completed","synthetic_fallback":False if result else None})
    write(dest/"status.json",results)


def compare():
    from app.services import gold_vacancy,building_vacancy
    comparisons=[]; serving_checks=[]; changed=[]
    for slug in sorted(ACTIVE_HUBS):
        old=read(ROOT/f"data/gold/{slug}/page_building_master.geojson")
        a=read(BASE/f"repeat-a/gold/{slug}/page_building_master.geojson")
        b=read(BASE/f"repeat-b/gold/{slug}/page_building_master.geojson")
        coverage_a=read(BASE/f"repeat-a/gold/{slug}/coverage.json");coverage_b=read(BASE/f"repeat-b/gold/{slug}/coverage.json")
        coverage_a.pop("built_at",None);coverage_b.pop("built_at",None)
        def featuremap(obj):
            return {f["properties"]["id"]:f for f in obj["features"]}
        oo,aa,bb=map(featuremap,(old,a,b)); common=set(oo)&set(aa)
        field_changes=Counter()
        for k in sorted(common):
            before,after=oo[k]["properties"],aa[k]["properties"]
            fields=[f for f in set(before)|set(after) if before.get(f)!=after.get(f)]
            field_changes.update(fields)
            if fields or oo[k]["geometry"]!=aa[k]["geometry"]:
                changed.append({"hub":slug,"id":k,"changed_fields":sorted(fields),
                                "geometry_changed":oo[k]["geometry"]!=aa[k]["geometry"],
                                "old_unit":unit(before),"new_unit":unit(after),
                                "vacancy_delta_pp":after["vacancy_rate"]-before["vacancy_rate"] if unit(before)==unit(after) and num(before.get("vacancy_rate")) and num(after.get("vacancy_rate")) else None})
        building_vacancy._GOLD_DIR=ROOT/"data/gold";building_vacancy._cache.clear()
        gold_vacancy._GOLD_DIR=ROOT/"data/gold";gold_vacancy._anchor_cache.clear()
        baseline=gold_vacancy.build_cells(slug,grid_for(slug))
        write(BASE/"baseline-serving"/(slug+".json"),baseline)
        sa=read(BASE/f"repeat-a/serving/{slug}.json");sb=read(BASE/f"repeat-b/serving/{slug}.json")
        # 실제 서빙 함수와 별도 감사 합산의 교차 검사.
        hub=next(x for x in read(BASE/"structural-audit.json")["hubs"] if x["hub"]==slug)
        serving_checks.append({"hub":slug,"pass":baseline is not None and all(baseline[k]==hub[h] for k,h in (("capacity","capacity"),("sum_stores","active"),("buildings","eligible_lots"),("avg_vacancy","vacancy_pct")))})
        comparisons.append({"hub":slug,"repeat_master_bytes_equal":sha(BASE/f"repeat-a/gold/{slug}/page_building_master.geojson")==sha(BASE/f"repeat-b/gold/{slug}/page_building_master.geojson"),
            "repeat_master_semantics_equal":canon(aa)==canon(bb),"repeat_coverage_except_built_at_equal":canon(coverage_a)==canon(coverage_b),
            "repeat_serving_equal":canon(sa)==canon(sb),"stored_master_same_as_current_rebuild":canon(oo)==canon(aa),
            "common_polygon_ids":len(common),"entered_polygon_ids":len(set(aa)-set(oo)),"exited_polygon_ids":len(set(oo)-set(aa)),
            "changed_fields":dict(field_changes),"old_lots":baseline["buildings"] if baseline else None,
            "rebuilt_lots":sa["buildings"] if sa else None,"old_capacity":baseline["capacity"] if baseline else None,
            "rebuilt_capacity":sa["capacity"] if sa else None,"old_vacancy_pct":baseline["avg_vacancy"] if baseline else None,
            "rebuilt_vacancy_pct":sa["avg_vacancy"] if sa else None,
            "delta_pp":round(sa["avg_vacancy"]-baseline["avg_vacancy"],2) if sa and baseline else None,
            "causal_interpretation":"not_established; current_inputs_and_code_not_historical_build_provenance"})
    write(BASE/"reproduction-comparison.json",comparisons);write(BASE/"changed-polygons.json",changed)
    write(BASE/"serving-crosscheck.json",serving_checks);csvout("reproduction-summary.csv",[{k:v for k,v in r.items() if k!="changed_fields"} for r in comparisons])
    if not all(x["pass"] for x in serving_checks):
        raise RuntimeError("감사 독립 합산과 서빙 집계가 다름: 교차 검사 확인 필요")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker",choices=["repeat-a","repeat-b"])
    args=parser.parse_args();m=read(MANIFEST)
    if args.worker:
        worker(m,args.worker);return
    if BASE.exists():raise RuntimeError("기존 실행 폴더가 있습니다. 덮어쓰지 않습니다")
    print("manifest 입력 및 코드 재해시",flush=True)
    verification=verify_manifest(m)
    BASE.mkdir(parents=True)
    plan={"created_at_utc":datetime.now(timezone.utc).isoformat(),"manifest_sha256":sha(MANIFEST),
        "runner_sha256":sha(__file__),"targets":"this runner and analysis run directory only",
        "structural_checks":"master identity, basic geometry, arithmetic, floor semantics, same-lot consistency, coverage, current polygon provenance; raw store diagnostics",
        "not_claimed":"complete ledger audit, all join-edge reconstruction, independently confirmed occupancy accuracy",
        "impact":"existing floor-uncertainty interval; current rebuild vs stored Gold (noncausal)",
        "reproduction":"two fresh subprocesses with pinned selected Bronze, stored Gold capacity and stored Silver attrs; master/coverage/serving only",
        "normalization":"master feature map keyed by unique id; coverage drops only built_at; actual file hashes also retained",
        "sampling":{"seed":20260906,"target":200,"allocation":"min(Nh,max(2,ceil(200*Nh/N)))","labels":"unresolved until independent review"},
        "gates":"pre/post hash equality, audit-vs-serving crosscheck, fresh-process output comparisons"}
    write(BASE/"analysis-plan.json",plan);write(BASE/"input-verification-before.json",verification)
    protect_writes()
    audit(m)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONIOENCODING="utf-8")
    for tag in ("repeat-a","repeat-b"):
        print("격리 재실행 시작: "+tag,flush=True)
        with (BASE/(tag+".log")).open("w",encoding="utf-8") as log:
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--worker",tag],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError(tag+" 실패; 로그 확인")
        print("격리 재실행 완료: "+tag,flush=True)
    compare()
    print("원본 보존 사후 재해시",flush=True)
    write(BASE/"input-verification-after.json",verify_manifest(m))
    paths=sorted(p for p in BASE.rglob("*") if p.is_file())
    write(BASE/"output-hashes.json",[{"path":p.relative_to(BASE).as_posix(),"sha256":sha(p)} for p in paths])
    print("분석 산출물 완료: "+str(BASE.relative_to(ROOT)),flush=True)


if __name__=="__main__":main()
