"""Offline route/matrix acceptance after the six residual requests."""

from railway_project_io import read_project_json
import json
from datetime import datetime

import numpy as np

from stage1_collect import ROOT, TZ, write_csv, write_json, software_versions
from stage1b_transfer import read_csv
from stage1f_assess import consistency_conflicts
from stage1h_matrix import matrix_diagnostics
from stage1d_routes import TemporalGraph, prepare_records, service, PATH_FIELDS
from stage1i_dated_schedule import sha
from stage1k_residual import combined_after_six, J_JOB, PRIMARY


def evaluate(rows, metadata, actor="user"):
    if actor not in ("user","assistant"):
        raise ValueError("Invalid actor")
    conflicts=consistency_conflicts(rows)
    if conflicts:raise ValueError("Source event/station conflicts: "+str(conflicts[:3]))
    raw=ROOT/"data/raw"/PRIMARY
    config=read_project_json(raw / 'protocol.json')
    nodes=read_csv(raw/"nodes.csv")
    core=[n for n in nodes if n["representative_city"] in config["anchor_stations"]]
    cities={n["representative_city"] for n in core}
    candidate_codes={s["station_code"] for s in read_csv(raw/"candidate_stations.csv")}
    previous={(r["scenario"],r["from_node"],r["to_node"]):r for r in read_csv(ROOT/"data/processed"/J_JOB/"route_pairs.csv")}
    out=ROOT/"data/processed"/(actor+"_stage1k_matrix_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    route_rows, legs, coverage=[],[],[]
    for policy,threshold in [("draft83",60),("observed_group",30),("observed_group",60),("observed_group",90)]:
        scenario=policy+"_"+str(threshold)
        records=prepare_records(rows,cities,candidate_codes,policy,config["future_latest_arrival_exclusive"])
        graph=TemporalGraph(records,config["query_date"],threshold,config["future_latest_arrival_exclusive"],config["future_elapsed_limit_minutes"])
        count,newly,shorter=0,0,0
        for origin in core:
            distance,parents=graph.shortest(origin["representative_city"])
            for dest in core:
                if origin["node_id"]==dest["node_id"]:continue
                row=dict(scenario=scenario,from_node=origin["node_id"],from_city=origin["representative_city"],to_node=dest["node_id"],to_city=dest["representative_city"],
                         time_min="",running_min="",wait_min="",transfers="",first_departure="",final_arrival="",status="not_found_in_collected_timetable_not_unreachable")
                terminals=[(distance[n],graph.minute(records[i]["arrival_at"]),n) for n,i in graph.arrs_by_city[dest["representative_city"]] if distance[n]!=float("inf")]
                if terminals:
                    value,_,terminal=min(terminals)
                    path,elapsed,wait=graph.itinerary(terminal,parents)
                    assert value==elapsed
                    row.update(time_min=elapsed,running_min=elapsed-wait,wait_min=wait,
                               transfers=sum(service(a)!=service(b) for a,b in zip(path,path[1:])),first_departure=path[0]["departure_at"],final_arrival=path[-1]["arrival_at"],
                               status="minimum_in_observed_and_published_dated_timetable_model")
                    count+=1
                    for index,r in enumerate(path):
                        legs.append(dict(scenario=scenario,from_node=origin["node_id"],to_node=dest["node_id"],leg_index=index+1,edge_id=r["edge_id"],
                                         train_code=r["train_code"],train_no=r["train_no"],origin_service_date=r["origin_service_date"],from_name=r["from_name"],to_name=r["to_name"],
                                         departure_at=r["departure_at"],arrival_at=r["arrival_at"],duration_min=r["duration_min"],
                                         wait_before_min=0 if index==0 else graph.minute(r["departure_at"])-graph.minute(path[index-1]["arrival_at"]),
                                         same_service_as_previous=False if index==0 else service(r)==service(path[index-1]),raw_file=r["raw_file"],raw_row_index=r["raw_row_index"]))
                old=previous[scenario,row["from_node"],row["to_node"]]["time_min"]
                if old!="":
                    if row["time_min"]=="" or row["time_min"]>float(old):raise ValueError("Adding source edges worsened an existing route")
                    shorter+=row["time_min"]<float(old)
                elif row["time_min"]!="":newly+=1
                route_rows.append(row)
        coverage.append(dict(scenario=scenario,before_finite=sum(r["scenario"]==scenario and r["time_min"]!="" for r in previous.values()),after_finite=count,missing=992-count,newly_found=newly,shorter=shorter))
        print(scenario,f"{count}/992", "缺失",992-count,flush=True)
    # Validate transfer-threshold nesting for every direction, including missing.
    lookup={(r["scenario"],r["from_node"],r["to_node"]):r for r in route_rows}
    for a in core:
        for b in core:
            if a==b:continue
            values=[lookup["observed_group_"+str(t),a["node_id"],b["node_id"]]["time_min"] for t in (30,60,90)]
            v=[float(x) if x!="" else float("inf") for x in values]
            if not v[0]<=v[1]<=v[2]:raise ValueError("Transfer-threshold monotonicity failed")
    write_csv(out/"coverage_before_after.csv",coverage,list(coverage[0]))
    write_csv(out/"route_pairs.csv",route_rows,list(route_rows[0]))
    write_csv(out/"route_legs_with_sources.csv",legs,PATH_FIELDS)
    base={(r["from_node"],r["to_node"]):r for r in route_rows if r["scenario"]=="observed_group_60"}
    all_ids=[n["node_id"] for n in nodes]; core_ids=[n["node_id"] for n in core]
    wide=[dict(node_id=a,**{b:0 if a==b else base[a,b]["time_min"] if (a,b) in base else "" for b in all_ids}) for a in all_ids]
    statuses=[dict(node_id=a,**{b:"diagonal" if a==b else base[a,b]["status"] if (a,b) in base else "special_region_connection_review_pending" for b in all_ids}) for a in all_ids]
    write_csv(out/"raw_directed_time_34.csv",wide,["node_id"]+all_ids)
    write_csv(out/"raw_status_34.csv",statuses,["node_id"]+all_ids)
    write_csv(out/"nodes_34.csv",nodes,list(nodes[0]))
    a32=np.array([[0 if a==b else float(base[a,b]["time_min"]) if base[a,b]["time_min"]!="" else np.nan for b in core_ids] for a in core_ids])
    complete=bool(np.isfinite(a32).all())
    write_csv(out/"core32_directed_minutes.csv",[dict(node_id=a,**{b:float(a32[i,j]) if np.isfinite(a32[i,j]) else "" for j,b in enumerate(core_ids)}) for i,a in enumerate(core_ids)],["node_id"]+core_ids)
    write_csv(out/"core32_nodes.csv",core,list(core[0]))
    if complete:
        symmetric,diag=matrix_diagnostics(a32)
        write_csv(out/"core32_symmetric_mean_minutes.csv",[dict(node_id=a,**{b:float(symmetric[i,j]) for j,b in enumerate(core_ids)}) for i,a in enumerate(core_ids)],["node_id"]+core_ids)
        write_json(out/"core32_matrix_diagnostics.json",diag)
    missing=[r for r in route_rows if r["scenario"]=="observed_group_60" and r["time_min"]==""]
    write_csv(out/"remaining_core_missing.csv",missing,list(route_rows[0]))
    targets={"N06","N11","N14","N21","N22"}
    selected=[r for r in route_rows if r["scenario"]=="observed_group_60" and r["from_node"]=="N26" and r["to_node"] in targets]
    write_csv(out/"five_residual_routes.csv",selected,list(route_rows[0]))
    write_csv(out/"five_residual_route_legs.csv",[r for r in legs if r["scenario"]=="observed_group_60" and r["from_node"]=="N26" and r["to_node"] in targets],PATH_FIELDS)
    result=dict(actor=actor,input=metadata,source_conflicts=0,scenarios=coverage,core32_complete=complete,core32_algorithm_input_ready=complete,
                full34_algorithm_ready=False,raw34_missing=sum(r[b]=="" for r in wide for b in all_ids),threshold_monotonicity_passed=True,
                penalties_applied=False,imputation_applied=False,new_network_requests_in_analysis=0,software=software_versions(),
                scripts_sha256={n:sha(ROOT/"scripts"/n) for n in ("stage1k_matrix.py","stage1k_residual.py","stage1d_routes.py")},output_dir=str(out),
                note="A complete observed core32 matrix does not establish global timetable completeness or replace the full34 Macau/Taipei analysis. All missing and special-region states remain explicit.")
    write_json(out/"matrix_acceptance_summary.json",result)
    return result


def run(actor="user"):
    rows,_,metadata=combined_after_six()
    return evaluate(rows,metadata,actor)
