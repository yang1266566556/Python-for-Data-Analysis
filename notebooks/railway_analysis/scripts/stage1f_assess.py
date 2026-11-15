"""Offline, provenance-preserving assessment before asking for more queries."""

from railway_project_io import read_project_json
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from stage1_collect import ROOT, TZ, TRAIN_FIELDS, write_csv, write_json
from stage1b_transfer import read_csv
from stage1e_followups import verify_checkpoint, PRIMARY, ROUTING
from stage1d_routes import TemporalGraph, prepare_records, service

SUPPLEMENT_JOB = "user_stage1e_20261113_143455_080165"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def consistency_conflicts(rows):
    identities = defaultdict(set)
    event_times = defaultdict(set)
    for row in rows:
        for side in ("from", "to"):
            identities[row[side+"_code"]].add((row[side+"_name"],row[side+"_dictionary_city"]))
        for side, clock, phase in (("from","departure_at","departure"),("to","arrival_at","arrival")):
            key = (row["train_no"],row["origin_service_date"],row[side+"_code"],phase)
            event_times[key].add(row[clock])
    conflicts=[]
    for code, labels in identities.items():
        if len(labels)>1:
            conflicts.append(dict(kind="station_identity_conflict",key=code,values=json.dumps(sorted(labels),ensure_ascii=False)))
    for key, times in event_times.items():
        if len(times)>1:
            conflicts.append(dict(kind="same_service_event_time_conflict",key=json.dumps(key,ensure_ascii=False),values=json.dumps(sorted(times))))
    return conflicts


def merge_authenticated():
    primary_raw=ROOT/"data/raw"/PRIMARY
    primary_file=ROOT/"data/processed"/PRIMARY/"train_records.csv"
    routing_dir=ROOT/"data/processed"/ROUTING
    old_summary=read_project_json(routing_dir / 'routing_summary.json')
    audited=read_project_json(Path(old_summary['audit_dir']) / 'audit_summary.json')
    if sha(primary_file)!=audited["train_csv_sha256"]:
        raise ValueError("Primary data changed after its audited user run")
    job=ROOT/"data/raw"/SUPPLEMENT_JOB
    if (job/"running.lock").exists():
        raise ValueError("Supplement still running; do not analyze an actively changing snapshot")
    plan=read_project_json(job / 'plan.json')
    protocol=read_project_json(job / 'protocol.json')
    all_records, refresh_rows, later_rows, issues, completed, refreshed=[],[],[],[],[],set()
    station_cache={}
    source_times=[]
    for query in plan:
        p=job/"checkpoints"/(query["query_id"]+".json")
        if not p.exists():
            continue
        cp=read_project_json(p)
        if not all(cp["query"][k]==v for k,v in query.items()):
            raise ValueError("Supplement checkpoint differs from its frozen plan")
        rows, row_issues, q=verify_checkpoint(cp,station_cache)
        if q["rejected_count"]:
            raise ValueError("Unresolved parser errors prevent merge")
        all_records.extend(rows);issues.extend(row_issues)
        source_times.append(cp["source"]["accessed_at"])
        completed.append(query)
        if query["role"]=="refresh_primary_unknown":
            refreshed.add(query["primary_query_id"]);refresh_rows.extend(rows)
        else:
            later_rows.extend(rows)
    csv_file=ROOT/"data/processed"/SUPPLEMENT_JOB/"supplement_train_records.csv"
    if [{k:str(r[k]) for k in TRAIN_FIELDS} for r in all_records]!=read_csv(csv_file):
        raise ValueError("Supplement CSV differs from saved authentic responses")
    if any(datetime.fromisoformat(t)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]) for t in source_times):
        raise ValueError("Supplement source falls outside agreed snapshot window")
    primary_rows=read_csv(primary_file)
    retained=[r for r in primary_rows if r["query_id"] not in refreshed]
    merged=retained+refresh_rows+later_rows
    # Full-query refresh replaces the old query in this analysis version only.
    # Old raw responses and exports are not changed; unknown data never falls back
    # to another date or silently inherits a now-absent prior service.
    stats=dict(primary_records=len(primary_rows),old_records_replaced=len(primary_rows)-len(retained),
               refreshed_records=len(refresh_rows),later_date_records=len(later_rows),merged_records=len(merged),
               completed_supplement_queries=len(completed),uncollected_supplement_queries=len(plan)-len(completed),
               train_csv_sha256=sha(primary_file),supplement_csv_sha256=sha(csv_file),
               unknown_source_issues=len(issues),source_deadline=protocol["snapshot_deadline_exclusive"])
    return merged, stats, completed, plan, protocol


def assess(actor="user"):
    if actor not in ("user","assistant"):
        raise ValueError("Invalid actor")
    rows, merge_stats, completed, original_plan, supplement_protocol=merge_authenticated()
    primary=ROOT/"data/raw"/PRIMARY
    config=read_project_json(primary / 'protocol.json')
    nodes=read_csv(primary/"nodes.csv")
    core=[n for n in nodes if n["representative_city"] in config["anchor_stations"]]
    cities={n["representative_city"] for n in core}
    candidates={s["station_code"] for s in read_csv(primary/"candidate_stations.csv")}
    baseline=read_csv(ROOT/"data/processed"/ROUTING/"route_scenarios.csv")
    base_by_pair={(r["scenario"],r["from_node"],r["to_node"]):r for r in baseline}
    out=ROOT/"data/processed"/(actor+"_stage1f_assessment_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    conflicts=consistency_conflicts(rows)
    write_csv(out/"source_consistency_conflicts.csv",conflicts,["kind","key","values"])
    if conflicts:
        write_json(out/"assessment_summary.json",dict(actor=actor,source_conflicts=len(conflicts),routing_permitted=False,output_dir=str(out),matrix_ready=False))
        raise ValueError(f"Source consistency conflicts need review; saved at {out}")
    write_csv(out/"merged_known_train_records.csv",rows,TRAIN_FIELDS)
    comparisons, route_rows, missing_rows, targeted, frontier_rows=[],[],[],{},[]
    completed_keys={(q["date"],q["from_station"],q["to_station"]) for q in completed}
    completed_keys|={(q["date"],q["from_station"],q["to_station"]) for q in read_project_json(primary / 'plan.json')}
    for policy,threshold in [("draft83",60),("observed_group",30),("observed_group",60),("observed_group",90)]:
        scenario=policy+"_"+str(threshold)
        records=prepare_records(rows,cities,candidates,policy,config["future_latest_arrival_exclusive"])
        graph=TemporalGraph(records,config["query_date"],threshold,config["future_latest_arrival_exclusive"],config["future_elapsed_limit_minutes"])
        counts=Counter()
        initial_unavailable=[]
        for origin in core:
            origin_city=origin["representative_city"]
            distances,parents=graph.shortest(origin_city)
            if not graph.deps_by_city[origin_city]:
                initial_unavailable.append(origin_city)
            for dest in core:
                if origin["node_id"]==dest["node_id"]:
                    continue
                terminals=[(distances[n],graph.minute(records[i]["arrival_at"]),n) for n,i in graph.arrs_by_city[dest["representative_city"]] if distances[n]!=float("inf")]
                old=base_by_pair[(scenario,origin["node_id"],dest["node_id"])]
                old_time=int(float(old["model_time_min"])) if old["model_time_min"]!="" else None
                value=None
                if terminals:
                    value,_,terminal=min(terminals)
                    path,elapsed,waits=graph.itinerary(terminal,parents)
                    assert value==elapsed
                change=("newly_found" if old_time is None else "shorter" if value<old_time else "same" if value==old_time else "longer_after_source_refresh") if value is not None else ("still_missing" if old_time is None else "lost_after_source_refresh")
                counts[change]+=1
                entry=dict(scenario=scenario,from_node=origin["node_id"],from_city=origin_city,to_node=dest["node_id"],to_city=dest["representative_city"],
                           previous_min_min=old_time if old_time is not None else "",current_model_min=value if value is not None else "",change=change,
                           status="minimum_in_audited_observed_timetable_only" if value is not None else "initial_departure_timetable_missing" if not graph.deps_by_city[origin_city] else "not_found_in_collected_timetable_not_physical_unreachable")
                route_rows.append(entry)
                if value is None and scenario=="observed_group_60":
                    missing_rows.append(entry)
                    # Query exact known arrival stations which already have
                    # verified train services to this destination in saved data.
                    # Arrival day and following day are planning candidates only.
                    hub_codes={r["from_code"]:(r["from_name"],r["from_dictionary_city"]) for r in records if r["to_dictionary_city"]==dest["representative_city"]}
                    for code,(station_name,city) in hub_codes.items():
                        arrivals=[(graph.minute(records[i]["arrival_at"]),n,i) for n,i in graph.arrs_by_city[city] if records[i]["to_code"]==code and distances[n]!=float("inf")]
                        if not arrivals:
                            continue
                        _,event,i=min(arrivals)
                        via_path,via_elapsed,_=graph.itinerary(event,parents)
                        arrival=records[i]["arrival_at"]
                        frontier_rows.append(dict(from_city=origin_city,to_city=dest["representative_city"],hub_city=city,actual_hub_station=station_name,
                                                  actual_hub_code=code,known_arrival_at=arrival,first_departure=via_path[0]["departure_at"],elapsed_to_hub_min=via_elapsed))
                        for delta in (0,1):
                            day=(datetime.fromisoformat(arrival).date()+timedelta(days=delta)).isoformat()
                            if day>=config["future_latest_arrival_exclusive"][:10]:
                                continue
                            key=(day,station_name,config["anchor_stations"][dest["representative_city"]])
                            if key in completed_keys:
                                continue
                            if key not in targeted:
                                targeted[key]=dict(date=day,from_city=city,to_city=dest["representative_city"],from_station=station_name,
                                                   to_station=key[2],reason="exact known arrival station to unresolved destination; arrival day or next day",
                                                   affected_pairs=set())
                            targeted[key]["affected_pairs"].add(origin_city+"→"+dest["representative_city"])
        old_finite=sum(r["scenario"]==scenario and r["model_time_min"]!="" for r in baseline)
        now_finite=sum(v for k,v in counts.items() if k not in ("still_missing","lost_after_source_refresh"))
        comparisons.append(dict(scenario=scenario,before_finite=old_finite,after_finite=now_finite,currently_missing=992-now_finite,
                                newly_found=counts["newly_found"],shorter=counts["shorter"],unchanged=counts["same"],longer=counts["longer_after_source_refresh"],
                                lost=counts["lost_after_source_refresh"],origins_without_known_first_departure=";".join(initial_unavailable)))
        print(f"{scenario}: {old_finite} → {now_finite}/992",flush=True)
    target_plan=[]
    for i,t in enumerate(sorted(targeted.values(),key=lambda x:(x["date"],x["from_city"],x["from_station"])),1):
        target_plan.append(dict(query_id=f"T{i:03d}",role="followup_date",primary_query_id="",date=t["date"],from_city=t["from_city"],to_city=t["to_city"],
                                from_station=t["from_station"],to_station=t["to_station"],reason=t["reason"],affected_pairs=";".join(sorted(t["affected_pairs"]))))
    write_csv(out/"coverage_before_after.csv",comparisons,list(comparisons[0]))
    write_csv(out/"updated_route_pairs.csv",route_rows,list(route_rows[0]))
    write_csv(out/"remaining_missing_pairs.csv",missing_rows,list(missing_rows[0]) if missing_rows else list(route_rows[0]))
    write_csv(out/"actual_arrival_station_frontier.csv",frontier_rows,["from_city","to_city","hub_city","actual_hub_station","actual_hub_code","known_arrival_at","first_departure","elapsed_to_hub_min"])
    target_fields=["query_id","role","primary_query_id","date","from_city","to_city","from_station","to_station","reason","affected_pairs"]
    write_csv(out/"targeted_station_query_plan.csv",target_plan,target_fields)
    summary=dict(actor=actor,primary_run=PRIMARY,supplement_run=SUPPLEMENT_JOB,baseline_user_routing_run=ROUTING,merge=merge_stats,
                  source_conflicts=0,comparisons=comparisons,targeted_query_count=len(target_plan),target_plan_sha256=sha(out/"targeted_station_query_plan.csv"),
                  merged_csv_sha256=sha(out/"merged_known_train_records.csv"),output_dir=str(out),matrix_ready=False,
                  collection_scope="Initial 385 supplement responses only; remaining 119 remain unqueried, not assumed unnecessary for all faster-path searches",
                  next_action="Target exact arrived stations; do not repeatedly refresh unavailable Lhasa departures",
                  limits=["Known first-departure-day records remain mandatory","No geometric or static-time substitutes","Node/station scope, unknown timetables and regional connectivity still need final review"])
    write_json(out/"assessment_summary.json",summary)
    return summary


def plan_for_assessment(assessment_dir):
    out=Path(assessment_dir).resolve()
    if not out.is_relative_to((ROOT/"data/processed").resolve()):
        raise ValueError("Invalid assessment directory")
    summary=read_project_json(out / 'assessment_summary.json')
    if summary["source_conflicts"] or summary["supplement_run"]!=SUPPLEMENT_JOB:
        raise ValueError("Assessment does not cover this reviewed source")
    if sha(out/"targeted_station_query_plan.csv")!=summary["target_plan_sha256"]:
        raise ValueError("Targeted query plan changed")
    plan=read_csv(out/"targeted_station_query_plan.csv")
    if not plan:
        raise ValueError("No targeted queries planned; no further collection is required by this assessment")
    protocol=dict(primary_run=PRIMARY,assessment_dir=str(out),assessment_sha256=sha(out/"assessment_summary.json"),
                  first_departure_date="2026-11-18",snapshot_deadline_exclusive=summary["merge"]["source_deadline"],
                  total_queries=len(plan),parser_version="stage1c-station-metadata-v2",
                  automatic_retries=0,request_interval_seconds=3,
                  limit="Exact-station diagnostic queries, not all-route completeness; original 119 requests preserved as pending")
    return plan,protocol
