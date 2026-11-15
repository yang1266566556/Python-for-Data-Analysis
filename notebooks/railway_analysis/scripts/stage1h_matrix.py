"""Freeze observed timetable candidate matrices; unknown is never unreachable.

The complete-node raw matrix retains missing data. A separate complete-data
comparison subset is exported for input QA, not a claim of a completed 34-node
research design or an actual physical-connectivity classification.
"""

from railway_project_io import read_project_json
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

from stage1_collect import ROOT, TZ, TRAIN_FIELDS, write_csv, write_json, software_versions
from stage1b_transfer import read_csv
from stage1c_parser_v2 import PARSER_VERSION
from stage1e_followups import verify_checkpoint, PRIMARY
from stage1f_assess import merge_authenticated, consistency_conflicts, sha
from stage1d_routes import TemporalGraph, prepare_records, service, PATH_FIELDS

TARGET_JOB="user_stage1g_20261113_153248_952115"


def verified_input():
    rows,merge_info,_,_,_=merge_authenticated()
    job=ROOT/"data/raw"/TARGET_JOB
    if (job/"running.lock").exists():
        raise ValueError("Target collection is still running")
    plan=read_project_json(job / 'plan.json')
    protocol=read_project_json(job / 'protocol.json')
    metadata=read_project_json(job / 'metadata.json')
    assessment=read_project_json(Path(metadata['assessment_dir']) / 'assessment_summary.json')
    if sha(Path(metadata["assessment_dir"])/"merged_known_train_records.csv")!=protocol["merged_csv_sha256"]:
        raise ValueError("Previous merged source changed")
    if protocol["merged_csv_sha256"]!=assessment["merged_csv_sha256"]:
        raise ValueError("Target plan refers to a different merged version")
    station_cache={};new=[];issue_count=0
    for query in plan:
        checkpoint=job/"checkpoints"/(query["query_id"]+".json")
        if not checkpoint.exists():
            raise ValueError("Targeted batch incomplete; inspect before freezing matrices")
        cp=read_project_json(checkpoint)
        assert all(cp["query"][k]==v for k,v in query.items())
        parsed,issues,q=verify_checkpoint(cp,station_cache)
        assert q["rejected_count"]==0
        if datetime.fromisoformat(cp["source"]["accessed_at"])>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
            raise ValueError("Targeted query outside frozen source collection span")
        new.extend(parsed);issue_count+=len(issues)
    target_csv=ROOT/"data/processed"/TARGET_JOB/"targeted_train_records.csv"
    if [{k:str(r[k]) for k in TRAIN_FIELDS} for r in new]!=read_csv(target_csv):
        raise ValueError("Target CSV differs from authentic raw responses")
    combined=rows+new
    conflicts=consistency_conflicts(combined)
    if conflicts:
        raise ValueError("Source identity/time conflicts need resolution before routing: "+str(conflicts[:3]))
    return combined,dict(merge_info,target_queries_verified=len(plan),target_valid_records=len(new),target_issue_count=issue_count,
                         combined_source_records=len(combined),source_conflicts=0,target_csv_sha256=sha(target_csv))


def matrix_diagnostics(directed):
    a=np.asarray(directed,dtype=float)
    if a.ndim!=2 or a.shape[0]!=a.shape[1]:
        raise ValueError("Matrix must be square")
    if not np.isfinite(a).all() or (a<0).any() or not np.allclose(np.diag(a),0):
        raise ValueError("Matrix needs finite nonnegative entries and zero diagonal")
    n=len(a)
    offdiag=~np.eye(n,dtype=bool)
    if (a[offdiag]<=0).any():
        raise ValueError("Non-diagonal zero time is not supported by these data")
    symmetric=(a+a.T)/2
    gaps=np.abs(a-a.T)[np.triu_indices(n,1)]
    i,j,k=np.indices((n,n,n))
    distinct=(i!=j)&(j!=k)&(i!=k)
    violations=((symmetric[:,None,:]>symmetric[:,:,None]+symmetric[None,:,:]+1e-9)&distinct).sum()
    centering=np.eye(n)-np.ones((n,n))/n
    gram=-0.5*centering@(symmetric*symmetric)@centering
    eigenvalues=np.linalg.eigvalsh(gram)
    tolerance=1e-8*max(1.,float(np.max(np.abs(eigenvalues))))
    return symmetric,dict(node_count=n,finite=True,nonnegative=True,zero_diagonal=True,symmetric_after_mean=bool(np.allclose(symmetric,symmetric.T)),
                          direction_difference_median_min=float(np.median(gaps)),direction_difference_max_min=float(np.max(gaps)),
                          direction_pairs_differing=int((gaps>1e-9).sum()),unordered_direction_pairs=len(gaps),
                          triangle_inequality_violations_ordered_triples=int(violations),
                          gram_negative_eigenvalues=int((eigenvalues < -tolerance).sum()),gram_min_eigenvalue=float(eigenvalues[0]),
                          gram_negative_tolerance=tolerance,
                          note="Triangle and Gram tests are input diagnostics; no embedding or clustering was run. Symmetric averaging means average of observed directional costs.")


def freeze(actor="user"):
    if actor not in ("user","assistant"):
        raise ValueError("Invalid actor")
    rows,info=verified_input()
    raw=ROOT/"data/raw"/PRIMARY
    config=read_project_json(raw / 'protocol.json')
    nodes=read_csv(raw/"nodes.csv")
    core=[n for n in nodes if n["representative_city"] in config["anchor_stations"]]
    cities={n["representative_city"] for n in core}
    candidate_codes={s["station_code"] for s in read_csv(raw/"candidate_stations.csv")}
    out=ROOT/"data/processed"/(actor+"_stage1h_matrix_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    script_hashes={name:sha(ROOT/"scripts"/name) for name in ("stage1h_matrix.py","stage1d_routes.py","stage1f_assess.py","stage1c_parser_v2.py")}
    write_csv(out/"known_train_records_with_sources.csv",rows,TRAIN_FIELDS)
    route_rows,legs,comparison,missing_origins=[],[],[],set()
    for policy,threshold in [("draft83",60),("observed_group",30),("observed_group",60),("observed_group",90)]:
        scenario=policy+"_"+str(threshold)
        records=prepare_records(rows,cities,candidate_codes,policy,config["future_latest_arrival_exclusive"])
        g=TemporalGraph(records,config["query_date"],threshold,config["future_latest_arrival_exclusive"],config["future_elapsed_limit_minutes"])
        found=0
        for origin in core:
            distances,parents=g.shortest(origin["representative_city"])
            if scenario=="observed_group_60" and not g.deps_by_city[origin["representative_city"]]:
                missing_origins.add(origin["node_id"])
            for destination in core:
                if origin["node_id"]==destination["node_id"]:
                    continue
                terminals=[(distances[n],g.minute(records[i]["arrival_at"]),n) for n,i in g.arrs_by_city[destination["representative_city"]] if distances[n]!=float("inf")]
                r=dict(scenario=scenario,from_node=origin["node_id"],from_city=origin["representative_city"],to_node=destination["node_id"],to_city=destination["representative_city"],
                       time_min="",running_min="",wait_min="",transfers="",first_departure="",final_arrival="",
                       status="missing_first_departure_timetable" if not g.deps_by_city[origin["representative_city"]] else "not_found_in_observed_window_not_physical_unreachable")
                if terminals:
                    distance,_,terminal=min(terminals)
                    path,elapsed,wait=g.itinerary(terminal,parents)
                    assert elapsed==distance
                    r.update(time_min=elapsed,running_min=elapsed-wait,wait_min=wait,
                             transfers=sum(service(a)!=service(b) for a,b in zip(path,path[1:])),
                             first_departure=path[0]["departure_at"],final_arrival=path[-1]["arrival_at"],status="minimum_in_observed_timetable_model")
                    found+=1
                    for idx,row in enumerate(path):
                        legs.append(dict(scenario=scenario,from_node=origin["node_id"],to_node=destination["node_id"],leg_index=idx+1,edge_id=row["edge_id"],
                                         train_code=row["train_code"],train_no=row["train_no"],origin_service_date=row["origin_service_date"],from_name=row["from_name"],to_name=row["to_name"],
                                         departure_at=row["departure_at"],arrival_at=row["arrival_at"],duration_min=row["duration_min"],
                                         wait_before_min=0 if idx==0 else g.minute(row["departure_at"])-g.minute(path[idx-1]["arrival_at"]),
                                         same_service_as_previous=False if idx==0 else service(row)==service(path[idx-1]),raw_file=row["raw_file"],raw_row_index=row["raw_row_index"]))
                route_rows.append(r)
        comparison.append(dict(scenario=scenario,finite_core_directed_pairs=found,missing_core_directed_pairs=992-found,unique_model_service_edges=len(records)))
        print(f"{scenario}: {found}/992",flush=True)
    write_csv(out/"route_pairs_after_targeted.csv",route_rows,list(route_rows[0]))
    write_csv(out/"route_legs_with_sources.csv",legs,PATH_FIELDS)
    write_csv(out/"scenario_coverage.csv",comparison,list(comparison[0]))
    baseline={(r["from_node"],r["to_node"]):r for r in route_rows if r["scenario"]=="observed_group_60"}
    full=[]
    for origin in nodes:
        for destination in nodes:
            a,b=origin["node_id"],destination["node_id"]
            route=baseline.get((a,b))
            value=0 if a==b else route["time_min"] if route else ""
            status="diagonal" if a==b else route["status"] if route else "special_region_connection_review_pending"
            full.append(dict(from_node=a,from_city=origin["representative_city"],to_node=b,to_city=destination["representative_city"],time_min=value,status=status))
    write_csv(out/"raw_directed_time_34_long.csv",full,list(full[0]))
    lookup={(r["from_node"],r["to_node"]):r for r in full}
    all_ids=[n["node_id"] for n in nodes]
    wide=[dict(node_id=a,**{b:lookup[a,b]["time_min"] for b in all_ids}) for a in all_ids]
    statuses=[dict(node_id=a,**{b:lookup[a,b]["status"] for b in all_ids}) for a in all_ids]
    write_csv(out/"raw_directed_time_34.csv",wide,["node_id"]+all_ids)
    write_csv(out/"raw_status_34.csv",statuses,["node_id"]+all_ids)
    write_csv(out/"nodes_34.csv",nodes,list(nodes[0]))
    # This is an explicitly separate complete-data comparison subset, not a
    # declaration that omitted cities are physically disconnected.
    subset=[n for n in core if n["node_id"] not in missing_origins]
    subset_ids=[n["node_id"] for n in subset]
    array=np.array([[0 if a==b else float(lookup[a,b]["time_min"]) if lookup[a,b]["time_min"]!="" else np.nan for b in subset_ids] for a in subset_ids])
    symmetric,diagnostics=matrix_diagnostics(array)
    write_csv(out/"comparison_subset_nodes.csv",subset,list(subset[0]))
    write_csv(out/"comparison_subset_directed_minutes.csv",[dict(node_id=a,**{b:float(array[i,j]) for j,b in enumerate(subset_ids)}) for i,a in enumerate(subset_ids)],["node_id"]+subset_ids)
    write_csv(out/"comparison_subset_symmetric_mean_minutes.csv",[dict(node_id=a,**{b:float(symmetric[i,j]) for j,b in enumerate(subset_ids)}) for i,a in enumerate(subset_ids)],["node_id"]+subset_ids)
    omitted=[]
    for n in nodes:
        if n["node_id"] in subset_ids:
            continue
        reason="missing_initial_departure_timetable_not_unreachable" if n["node_id"] in missing_origins else "Macau_access_not_verified" if n["representative_city"]=="澳门" else "Taipei_cross_sea_rail_disconnection_in_assignment_source_pending"
        omitted.append(dict(node_id=n["node_id"],city=n["representative_city"],reason=reason,kept_in_full34=True))
    write_csv(out/"subset_omission_reasons.csv",omitted,list(omitted[0]))
    write_json(out/"subset_matrix_diagnostics.json",diagnostics)
    # Keep one source-grounded example showing the targeted-data effect.
    selected=[r for r in route_rows if r["scenario"]=="observed_group_60" and r["from_city"]=="海口" and r["to_city"]=="拉萨"]
    write_csv(out/"haikou_lhasa_summary.csv",selected,list(route_rows[0]))
    example=[r for r in legs if r["scenario"]=="observed_group_60" and r["from_node"]=="N21" and r["to_node"]=="N26"]
    write_csv(out/"haikou_lhasa_legs.csv",example,PATH_FIELDS)
    manifest=dict(actor=actor,created_at=datetime.now(TZ).isoformat(),primary_run=PRIMARY,targeted_run=TARGET_JOB,input=info,
                  software=software_versions(),analysis_script_hashes=script_hashes,
                  scenarios=comparison,full_node_count=34,raw34_missing_offdiagonal=sum(r["from_node"]!=r["to_node"] and r["time_min"]=="" for r in full),
                  comparison_subset_node_count=len(subset),subset_matrix_input_checks_passed=True,full34_algorithm_ready=False,
                  main34_scope_replaced=False,penalties_applied=False,imputation_applied=False,
                  symmetrization="(T_ij + T_ji)/2 only in explicitly named complete-data comparison matrix; directed source preserved",
                  data_scope="Known passenger timetable records including possible Yuehai train-ferry service; not a land-only rail graph or door-to-door time",
                  constraints=["Initial departures Nov 18; final arrival before Nov 23 and total at most 96h","Same-station transfer thresholds are 30/60/90 min assumptions",
                               "Observed 12306 city grouping remains an exploratory station-scope definition","No imputation or unreachable penalty for Lhasa's missing initial timetables",
                               "Macau access, Taiwan connection provenance and city coordinate sources still require final review","Complete-data subset is a comparison branch, not the full34 main result",
                               "Unknown schedules and original pending119 may affect global completeness and optimum values"],output_dir=str(out))
    write_json(out/"matrix_freeze_summary.json",manifest)
    return manifest


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("--actor",choices=["user","assistant"],default="user")
    print(json.dumps(freeze(parser.parse_args().actor),ensure_ascii=False,indent=2))
