"""Dated rail plus explicitly assumed Macao access, and Taipei-only penalties."""

from railway_project_io import read_project_json
import heapq
import json
from datetime import datetime, timedelta

import numpy as np

from stage1_collect import ROOT,TZ,TRAIN_FIELDS,write_csv,write_json,software_versions
from stage1b_transfer import read_csv
from stage1d_routes import TemporalGraph,prepare_records,service
from stage1f_assess import consistency_conflicts
from stage1h_matrix import matrix_diagnostics
from stage1i_dated_schedule import sha
from stage1n_supplement import combined_records_for_n as combined_records

PRIMARY="user_stage1c_v2_20261113_132207_325427"


def access_finish(arrival,minutes):
    """Conservative full access interval within the published 06:00..01:00 window."""
    for offset in (-1,0,1,2):
        day=arrival.date()+timedelta(days=offset)
        opening=datetime.combine(day,datetime.min.time(),tzinfo=TZ)+timedelta(hours=6)
        closing=opening+timedelta(hours=19)
        start=max(arrival,opening);end=start+timedelta(minutes=minutes)
        if start<closing and end<=closing:return end,int((start-arrival).total_seconds()/60)
    raise ValueError("No admissible port opening interval")


def origin_access_start(departure,minutes,query_date):
    start=departure-timedelta(minutes=minutes)
    if start.date().isoformat()!=query_date:return None
    finish,wait=access_finish(start,minutes)
    return start if wait==0 and finish==departure else None


def station_seed_shortest(graph,records,station_code,access_minutes):
    distances=[float("inf")]*len(graph.keys);parents=[None]*len(graph.keys);queue=[]
    for i,r in enumerate(records):
        departure=datetime.fromisoformat(r["departure_at"])
        if r["from_code"]==station_code and origin_access_start(departure,access_minutes,graph.query_date) is not None:
            node=graph.departures[i];distances[node]=access_minutes;heapq.heappush(queue,(access_minutes,node))
    while queue:
        distance,current=heapq.heappop(queue)
        if distance!=distances[current]:continue
        for target,cost,ride in graph.adj[current]:
            candidate=distance+cost
            if candidate<=graph.max_elapsed and candidate<distances[target]:
                distances[target]=candidate;parents[target]=(current,ride);heapq.heappush(queue,(candidate,target))
    return distances,parents


def taipei_penalty(raw,mask,value):
    raw=np.asarray(raw,dtype=float);mask=np.asarray(mask,dtype=bool)
    if raw.shape!=mask.shape or np.diag(mask).any() or np.isnan(raw).any():
        raise ValueError("Ordinary missing data cannot be filled with an unreachable penalty")
    if not np.array_equal(np.isinf(raw),mask):raise ValueError("Infinity must match only structural disconnection")
    finite=raw[np.isfinite(raw)]
    if value<=finite.max():raise ValueError("Penalty must exceed every finite time")
    result=raw.copy();result[mask]=value
    assert np.isfinite(result).all() and np.allclose(np.diag(result),0)
    assert np.array_equal(result[~mask],raw[~mask])
    return result


def write_matrix(path,array,ids):
    write_csv(path,[dict(node_id=a,**{b:float(array[i,j]) if not np.isnan(array[i,j]) else "" for j,b in enumerate(ids)}) for i,a in enumerate(ids)],["node_id"]+ids)


def run(actor="user"):
    if actor not in ("user","assistant"):raise ValueError("Invalid actor")
    rows,core_dir,protocol,source_info=combined_records()
    conflicts=consistency_conflicts(rows)
    if conflicts:raise ValueError("Source identity/event conflict: "+str(conflicts[:3]))
    primary=ROOT/"data/raw"/PRIMARY
    config=read_project_json(primary / 'protocol.json')
    nodes=read_csv(primary/"nodes.csv");ids=[n["node_id"] for n in nodes]
    core=[n for n in nodes if n["representative_city"] in config["anchor_stations"]]
    connected=core+[next(n for n in nodes if n["node_id"]=="N33")]
    connected_ids=[n["node_id"] for n in connected]
    cities={n["representative_city"] for n in core}|{"珠海"}
    records=prepare_records(rows,cities,set(),"observed_group",config["future_latest_arrival_exclusive"])
    codes={r[s+"_code"] for r in records for s in ("from","to") if r[s+"_name"]=="珠海"}
    if len(codes)!=1:raise ValueError("Zhuhai gateway station identity is not unique")
    gateway=next(iter(codes))
    graph=TemporalGraph(records,config["query_date"],60,config["future_latest_arrival_exclusive"],config["future_elapsed_limit_minutes"])
    shortest={n["node_id"]:graph.shortest(n["representative_city"]) for n in core}
    out=ROOT/"data/processed"/(actor+"_stage1n_special_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(exist_ok=False)
    write_csv(out/"combined_records_with_sources.csv",rows,TRAIN_FIELDS)
    core_matrix=read_csv(core_dir/"core32_directed_minutes.csv")
    old32=np.array([[float(r[n["node_id"]]) for n in core] for r in core_matrix])
    reference=max(float(v) for r in core_matrix for k,v in r.items() if k!="node_id")
    mask=np.array([[a!=b and "N34" in (a,b) for b in ids] for a in ids])
    assert mask.sum()==66
    write_matrix(out/"taipei_structural_unreachable_mask.csv",mask.astype(float),ids)
    write_csv(out/"nodes_34.csv",nodes,list(nodes[0]))
    definitions=[dict(node_id="N33",representative_city="澳门",representative_point="澳门关闸澳门侧",
                      mainland_rail_gateway="珠海站",connection_mode="铁路+步行及通关",observed_total_access_time=False,
                      treatment="30/60/90分钟接驳假设；口岸开放06:00至次日01:00"),
                 dict(node_id="N34",representative_city="台北",representative_point="台北",
                      mainland_rail_gateway="无直通大陆铁路物理连接",connection_mode="结构不可达",
                      observed_total_access_time=False,treatment="原始Inf与66格掩码；算法副本P=alpha*Tmax，alpha=2/5/10")]
    write_csv(out/"special_region_node_definitions.csv",definitions,list(definitions[0]))
    route_rows,leg_rows,coverage,catalog,missing=[],[],[],[],[]
    for access in protocol["access_minutes_scenarios"]:
        scenario=f"access_{access}_rail_transfer_60"
        array=np.full((34,34),np.nan);np.fill_diagonal(array,0);array[mask]=np.inf
        lookup_id={node:i for i,node in enumerate(ids)}
        for origin in connected:
            from_mac=origin["node_id"]=="N33"
            dist,parents=station_seed_shortest(graph,records,gateway,access) if from_mac else shortest[origin["node_id"]]
            for dest in connected:
                if origin["node_id"]==dest["node_id"]:continue
                to_mac=dest["node_id"]=="N33"
                terminal_options=[]
                candidates=[(graph.arrivals[i],i) for i,r in enumerate(records) if r["to_code"]==gateway] if to_mac else graph.arrs_by_city[dest["representative_city"]]
                for node,i in candidates:
                    if dist[node]==float("inf"):continue
                    arrival=datetime.fromisoformat(records[i]["arrival_at"])
                    final,port_wait=access_finish(arrival,access) if to_mac else (arrival,0)
                    total=dist[node]+(access+port_wait if to_mac else 0)
                    if final<graph.latest and total<=graph.max_elapsed:terminal_options.append((total,graph.minute(final.isoformat()),node,port_wait,final))
                row=dict(scenario=scenario,access_assumption_min=access,from_node=origin["node_id"],from_city=origin["representative_city"],
                         to_node=dest["node_id"],to_city=dest["representative_city"],time_min="",rail_running_min="",rail_wait_min="",access_min=access if from_mac or to_mac else 0,
                         port_closed_wait_min="",rail_transfers="",first_departure_at="",final_arrival_at="",status="ordinary_timetable_missing_not_unreachable")
                if terminal_options:
                    total,_,terminal,port_wait,final=min(terminal_options)
                    path,rail_elapsed,rail_wait=graph.itinerary(terminal,parents)
                    assert dist[terminal]==rail_elapsed+(access if from_mac else 0)
                    first=datetime.fromisoformat(path[0]["departure_at"])-timedelta(minutes=access if from_mac else 0)
                    assert (final-first).total_seconds()/60==total
                    row.update(time_min=total,rail_running_min=rail_elapsed-rail_wait,rail_wait_min=rail_wait,
                               port_closed_wait_min=port_wait,rail_transfers=sum(service(a)!=service(b) for a,b in zip(path,path[1:])),
                               first_departure_at=first.isoformat(),final_arrival_at=final.isoformat(),
                               status="rail_plus_assumed_walking_clearance" if from_mac or to_mac else "observed_timetable_model")
                    assert total==row["rail_running_min"]+rail_wait+row["access_min"]+port_wait
                    array[lookup_id[row["from_node"]],lookup_id[row["to_node"]]]=total
                    if from_mac or to_mac:
                        for j,r in enumerate(path):
                            leg_rows.append(dict(scenario=scenario,from_node=row["from_node"],to_node=row["to_node"],leg_index=j+1,train_code=r["train_code"],
                                                 from_name=r["from_name"],to_name=r["to_name"],departure_at=r["departure_at"],arrival_at=r["arrival_at"],duration_min=r["duration_min"],
                                                 wait_before_min=0 if j==0 else graph.minute(r["departure_at"])-graph.minute(path[j-1]["arrival_at"]),raw_file=r["raw_file"],raw_row_index=r["raw_row_index"]))
                else:missing.append(row)
                route_rows.append(row)
        sub=array[np.ix_([lookup_id[i] for i in connected_ids],[lookup_id[i] for i in connected_ids])]
        if not np.all(sub[:32,:32]<=old32+1e-9):raise ValueError("Adding verified access edges worsened the known core32 matrix")
        complete=bool(np.isfinite(sub).all())
        missing_count=int(np.isnan(sub).sum())
        coverage.append(dict(access_min=access,finite_connected33_pairs=1056-missing_count,missing_connected33_pairs=missing_count,
                             structural_taipei_cells=66,connected33_complete=complete,access_is_observed=False))
        write_matrix(out/f"raw34_access_{access}.csv",array,ids)
        write_matrix(out/f"directed33_access_{access}.csv",sub,connected_ids)
        statuses=[dict(node_id=a,**{b:"diagonal" if a==b else "structural_rail_disconnection_Taipei" if mask[i,j] else "ordinary_missing" if np.isnan(array[i,j]) else "rail_plus_assumed_access" if "N33" in (a,b) else "observed_timetable_model" for j,b in enumerate(ids)}) for i,a in enumerate(ids)]
        write_csv(out/f"status34_access_{access}.csv",statuses,["node_id"]+ids)
        if complete:
            symmetric,diag=matrix_diagnostics(sub)
            write_matrix(out/f"symmetric33_access_{access}.csv",symmetric,connected_ids)
            write_json(out/f"diagnostics33_access_{access}.json",diag)
        for alpha in protocol["penalty_factors"]:
            name=f"access_{access}_alpha_{alpha}"
            entry=dict(matrix_id=name,access_assumption_min=access,penalty_alpha=alpha,reference_max_core32_min=reference,penalty_min=alpha*reference,
                       node_count=34,algorithm_ready=complete,ordinary_missing_cells=missing_count,penalty_cells=66,
                       directed_csv="",symmetric_csv="",penalty_share_of_pairwise_sum="")
            if complete:
                transformed=taipei_penalty(array,mask,alpha*reference)
                symmetric=(transformed+transformed.T)/2
                directed_file=f"algorithm34_directed_{name}.csv";sym_file=f"algorithm34_symmetric_{name}.csv"
                write_matrix(out/directed_file,transformed,ids);write_matrix(out/sym_file,symmetric,ids)
                entry.update(directed_csv=directed_file,symmetric_csv=sym_file,penalty_share_of_pairwise_sum=float(transformed[mask].sum()/transformed.sum()))
            catalog.append(entry)
        print(f"接驳假设{access}分钟：{1056-missing_count}/1056，台北结构不可达66格",flush=True)
    write_csv(out/"macao_route_scenarios.csv",route_rows,list(route_rows[0]))
    write_csv(out/"macao_rail_legs_with_sources.csv",leg_rows,["scenario","from_node","to_node","leg_index","train_code","from_name","to_name","departure_at","arrival_at","duration_min","wait_before_min","raw_file","raw_row_index"])
    write_csv(out/"special_region_coverage.csv",coverage,list(coverage[0]))
    write_csv(out/"matrix_input_catalog.csv",catalog,list(catalog[0]))
    write_csv(out/"ordinary_missing_pairs.csv",missing,list(route_rows[0]))
    main_ready=all(c["algorithm_ready"] for c in catalog if c["access_assumption_min"]==60)
    result=dict(actor=actor,input=source_info,protocol=protocol,source_conflicts=0,coverage=coverage,baseline_access_minutes=60,
                full34_algorithm_ready=main_ready,penalty_factors=[2,5,10],structural_taipei_cells=66,ordinary_missing_never_penalized=True,
                access_time_is_assumed_not_measured=True,macau_gateway_is_not_macau_node=True,port_hours_checked=True,
                penalty_reference_max_core32_min=reference,generated_full34_matrices=sum(c["algorithm_ready"] for c in catalog),
                software=software_versions(),source_registry_sha256=protocol["source_registry_sha256"],output_dir=str(out),
                analysis_code_sha256={n:sha(ROOT/"scripts"/n) for n in ("stage1n_matrix.py","stage1n_supplement.py","stage1d_routes.py")},
                limitations=["Macao endpoint is Macau-side Border Gate, rail gateway is separate Zhuhai station; not whole-city door-to-door time",
                             "Access 30/60/90 minutes are sensitivity assumptions, not measured clearance times; full interval conservatively respects 06:00..01:00",
                             "Only Taipei structural mask receives finite algorithm penalties; all ordinary missing values remain missing",
                             "Scope minimum only in observed dated services, actual stations and window; no global optimum or ticket guarantee",
                             "Taipei disconnection follows assignment rule with current official planning corroboration; no invented railway timetable",
                             "No embedding/clustering or document generation was run; geographic coordinate provenance still pending"])
    write_json(out/"special_region_matrix_summary.json",result)
    return result
