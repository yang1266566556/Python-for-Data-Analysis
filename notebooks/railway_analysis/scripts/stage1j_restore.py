"""Restore dated published schedule edges; keep queried data and missing flags.

Source clocks, explicit cumulative durations, explicit arrival days and stop
durations must agree. No extra timetable days are copied or synthesized.
"""

from railway_project_io import read_project_json
import json
import re
from datetime import datetime, timedelta

import numpy as np

from stage1_collect import ROOT, TZ, TRAIN_FIELDS, write_csv, write_json, software_versions, parse_station_dictionary
from stage1b_transfer import read_csv
from stage1h_matrix import verified_input, matrix_diagnostics
from stage1i_dated_schedule import (prior_stop_evidence, authenticated_manifest, validate_full_table,
                                    clock_minutes, sha, PRIMARY, BASE)
from stage1f_assess import consistency_conflicts
from stage1d_routes import TemporalGraph, prepare_records, service, PATH_FIELDS

DATED_JOB = "user_stage1i_dated_20261113_161818_255920"
H_JOB = "user_stage1h_matrix_20261113_155821_569495"


def restored_records():
    raw = ROOT / "data/raw" / DATED_JOB
    protocol = read_project_json(raw / 'protocol.json')
    plans, clock_tables, clock_sources = prior_stop_evidence()
    if protocol["plans"] != plans or (raw / "stopped.json").exists():
        raise ValueError("Dated source plan changed or contains a stop marker")
    sources = authenticated_manifest(raw)
    cp = read_project_json(ROOT / 'data/raw' / PRIMARY / 'checkpoints/N26_N29.json')
    station_source = cp["station_snapshot"]
    if sha(ROOT / station_source["raw_file"]) != station_source["sha256"]:
        raise ValueError("Station dictionary raw hash differs")
    stations = parse_station_dictionary((ROOT / station_source["raw_file"]).read_text(encoding="utf-8"))
    by_name = {}
    for s in stations:
        by_name.setdefault(s["station_name"], []).append(s)
    config = read_project_json(ROOT / 'data/raw' / PRIMARY / 'protocol.json')
    cities = set(config["anchor_stations"])
    records, links, station_rows = [], [], []
    for p in plans:
        source = sources[p["probe_id"]]
        expected = {"leftTicketDTO.train_no": p["train_no"], "leftTicketDTO.train_date": p["requested_date"], "rand_code": ""}
        if source["url"] != BASE + "queryTrainInfo/query" or source["params"] != expected:
            raise ValueError("Dated source URL/service/date does not match protocol")
        if datetime.fromisoformat(source["accessed_at"]) >= datetime.fromisoformat(protocol["deadline"]):
            raise ValueError("Dated source outside the frozen acquisition window")
        dated, quality = validate_full_table((ROOT / source["raw_file"]).read_text(encoding="utf-8"), p, clock_tables[p["probe_id"]])
        origin = datetime.fromisoformat(quality["lhasa_start"])
        if origin.date().isoformat() != p["requested_date"] or datetime.strptime(p["origin_date"], "%Y%m%d").date() != origin.date():
            raise ValueError("Primary service origin date does not match dated timetable")
        events = []
        for index, row in enumerate(dated):
            arrival = datetime.fromisoformat(row["published_arrival_at"]) if index else None
            departure, dwell = None, None
            if index == 0:
                departure = origin
            elif index < len(dated) - 1:
                stop = clock_tables[p["probe_id"]][index].get("stopover_time", "")
                match = re.fullmatch(r"(\d+)分钟", stop)
                if not match:
                    raise ValueError("Missing published stopover duration; no clock-based day inference")
                dwell = int(match[1])
                if not 0 <= dwell < 1440:
                    raise ValueError("Unexpected published station dwell")
                departure = arrival + timedelta(minutes=dwell)
                if clock_minutes(departure.strftime("%H:%M")) != clock_minutes(row["start_time"]):
                    raise ValueError("Official stopover duration does not reproduce departure clock")
            if index and events[-1]["departure"] >= arrival:
                raise ValueError("Adjacent dated timetable events overlap")
            identity = by_name.get(row["station_name"], [])
            # Exact saved official dictionary identity only. No name trimming,
            # coordinate guessing, or free same-city station interchange.
            if len(identity) != 1:
                raise ValueError("Stop name has no unique official station code: " + row["station_name"])
            station = identity[0]
            event = dict(index=index, arrival=arrival, departure=departure, station=station, row=row)
            events.append(event)
            station_rows.append(dict(train_code=p["train_code"], train_no=p["train_no"], origin_service_date=p["requested_date"],
                                     station_name=station["station_name"], station_code=station["station_code"], dictionary_city=station["source_city_name"],
                                     arrival_at=arrival.isoformat() if arrival else "", departure_at=departure.isoformat() if departure else "",
                                     cumulative_arrival_min=row["published_elapsed_min"], published_dwell_min=dwell if dwell is not None else "",
                                     raw_file=source["raw_file"], raw_stop_index=index))
        eligible = [e for e in events if e["station"]["source_city_name"] in cities]
        for a in eligible:
            for b in eligible:
                if a["index"] >= b["index"]:
                    continue
                start, end = a["station"], b["station"]
                departure, arrival = a["departure"], b["arrival"]
                duration = int((arrival - departure).total_seconds() // 60)
                assert duration > 0
                record = dict(query_id="SCHEDULE_"+p["probe_id"], query_date=departure.date().isoformat(), train_no=p["train_no"],
                              train_code=json.loads(a["row"]["raw_fields_json"])["station_train_code"],
                              origin_service_date=p["requested_date"], requested_from="拉萨", requested_to="全程时刻表",
                              from_code=start["station_code"], to_code=end["station_code"], from_name=start["station_name"], to_name=end["station_name"],
                              same_as_requested_stations=False, from_dictionary_city=start["source_city_name"], to_dictionary_city=end["source_city_name"],
                              departure_clock=departure.strftime("%H:%M"), arrival_clock=arrival.strftime("%H:%M"),
                              duration_text=f"{duration//60:02}:{duration%60:02}", duration_min=duration, departure_at=departure.isoformat(), arrival_at=arrival.isoformat(),
                              arrival_day_offset=(arrival.date()-departure.date()).days, can_web_buy="not_verified_from_schedule_source",
                              raw_row_index=a["index"], raw_file=source["raw_file"], raw_sha256=source["sha256"],
                              measurement_kind="derived_segment_from_verified_official_dated_schedule")
                records.append(record)
                links.append(dict(query_id=record["query_id"], train_no=p["train_no"], origin_service_date=p["requested_date"],
                                  from_code=start["station_code"], to_code=end["station_code"], from_stop_index=a["index"], to_stop_index=b["index"],
                                  raw_file=source["raw_file"], raw_sha256=source["sha256"],
                                  dwell_source_file=clock_sources[p["probe_id"]]["raw_file"], dwell_source_sha256=clock_sources[p["probe_id"]]["sha256"],
                                  station_dictionary_file=station_source["raw_file"], station_dictionary_sha256=station_source["sha256"],
                                  date_rule="origin_date + published cumulative arrival; departure uses published dwell; elapsed=end-start",
                                  copied_to_other_origin_dates=False, ticket_availability_verified=False))
    return records, links, station_rows


def run(actor="user"):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    original, original_info = verified_input()
    restored, links, stations = restored_records()
    combined = original + restored
    conflicts = consistency_conflicts(combined)
    if conflicts:
        raise ValueError("Source identity/time conflicts: " + str(conflicts[:3]))
    primary = ROOT / "data/raw" / PRIMARY
    config = read_project_json(primary / 'protocol.json')
    nodes = read_csv(primary / "nodes.csv")
    core = [n for n in nodes if n["representative_city"] in config["anchor_stations"]]
    cities = {n["representative_city"] for n in core}
    candidates = {s["station_code"] for s in read_csv(primary / "candidate_stations.csv")}
    old = {(r["scenario"],r["from_node"],r["to_node"]):r for r in read_csv(ROOT / "data/processed" / H_JOB / "route_pairs_after_targeted.csv")}
    out = ROOT / "data/processed" / (actor + "_stage1j_restored_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    write_csv(out / "restored_schedule_segments.csv", restored, TRAIN_FIELDS)
    write_csv(out / "restored_segment_provenance.csv", links, list(links[0]))
    write_csv(out / "dated_station_events.csv", stations, list(stations[0]))
    write_csv(out / "combined_records_with_sources.csv", combined, TRAIN_FIELDS)
    routes, path_rows, comparisons = [], [], []
    for policy, threshold in [("draft83",60), ("observed_group",30), ("observed_group",60), ("observed_group",90)]:
        scenario = policy + "_" + str(threshold)
        records = prepare_records(combined, cities, candidates, policy, config["future_latest_arrival_exclusive"])
        graph = TemporalGraph(records, config["query_date"], threshold, config["future_latest_arrival_exclusive"], config["future_elapsed_limit_minutes"])
        count, newly, shorter = 0, 0, 0
        for origin in core:
            distances, parents = graph.shortest(origin["representative_city"])
            for dest in core:
                if origin["node_id"] == dest["node_id"]:
                    continue
                row = dict(scenario=scenario, from_node=origin["node_id"], from_city=origin["representative_city"],
                           to_node=dest["node_id"], to_city=dest["representative_city"], time_min="", running_min="", wait_min="", transfers="",
                           first_departure="", final_arrival="", status="not_found_in_observed_window_not_physical_unreachable")
                terminals = [(distances[n], graph.minute(records[i]["arrival_at"]), n) for n,i in graph.arrs_by_city[dest["representative_city"]] if distances[n] != float("inf")]
                if terminals:
                    value, _, terminal = min(terminals)
                    path, elapsed, wait = graph.itinerary(terminal, parents)
                    assert value == elapsed
                    row.update(time_min=elapsed, running_min=elapsed-wait, wait_min=wait,
                               transfers=sum(service(a)!=service(b) for a,b in zip(path,path[1:])),
                               first_departure=path[0]["departure_at"], final_arrival=path[-1]["arrival_at"],
                               status="minimum_in_observed_and_published_dated_timetable_model")
                    count += 1
                    for index, r in enumerate(path):
                        path_rows.append(dict(scenario=scenario, from_node=origin["node_id"], to_node=dest["node_id"], leg_index=index+1,
                                              edge_id=r["edge_id"], train_code=r["train_code"], train_no=r["train_no"], origin_service_date=r["origin_service_date"],
                                              from_name=r["from_name"], to_name=r["to_name"], departure_at=r["departure_at"], arrival_at=r["arrival_at"],
                                              duration_min=r["duration_min"], wait_before_min=0 if index==0 else graph.minute(r["departure_at"])-graph.minute(path[index-1]["arrival_at"]),
                                              same_service_as_previous=False if index==0 else service(r)==service(path[index-1]), raw_file=r["raw_file"], raw_row_index=r["raw_row_index"]))
                before = old[scenario,origin["node_id"],dest["node_id"]]["time_min"]
                if before != "":
                    if row["time_min"] == "" or row["time_min"] > float(before):
                        raise ValueError("Adding authenticated edges must not worsen a known candidate")
                    shorter += row["time_min"] < float(before)
                elif row["time_min"] != "":
                    newly += 1
                routes.append(row)
        comparisons.append(dict(scenario=scenario, before_finite=sum(r["scenario"]==scenario and r["time_min"]!="" for r in old.values()),
                                after_finite=count, missing=992-count, newly_found=newly, shorter=shorter))
        print(scenario, f"{count}/992", "新增方向", newly, "缩短方向", shorter, flush=True)
    write_csv(out / "coverage_before_after.csv", comparisons, list(comparisons[0]))
    write_csv(out / "route_pairs.csv", routes, list(routes[0]))
    write_csv(out / "route_legs_with_sources.csv", path_rows, PATH_FIELDS)
    base = {(r["from_node"],r["to_node"]):r for r in routes if r["scenario"]=="observed_group_60"}
    ids = [n["node_id"] for n in nodes]
    raw_rows, statuses = [], []
    for a in ids:
        raw_rows.append(dict(node_id=a, **{b:0 if a==b else base[a,b]["time_min"] if (a,b) in base else "" for b in ids}))
        statuses.append(dict(node_id=a, **{b:"diagonal" if a==b else base[a,b]["status"] if (a,b) in base else "special_region_connection_review_pending" for b in ids}))
    write_csv(out / "raw_directed_time_34.csv", raw_rows, ["node_id"]+ids)
    write_csv(out / "raw_status_34.csv", statuses, ["node_id"]+ids)
    write_csv(out / "nodes_34.csv", nodes, list(nodes[0]))
    core_ids = [n["node_id"] for n in core]
    a32 = np.array([[0 if a==b else float(base[a,b]["time_min"]) if base[a,b]["time_min"]!="" else np.nan for b in core_ids] for a in core_ids])
    complete = bool(np.isfinite(a32).all())
    write_csv(out / "core32_directed_minutes.csv", [dict(node_id=a,**{b:a32[i,j] if np.isfinite(a32[i,j]) else "" for j,b in enumerate(core_ids)}) for i,a in enumerate(core_ids)], ["node_id"]+core_ids)
    write_csv(out / "core32_nodes.csv", core, list(core[0]))
    if complete:
        symmetric, diagnostics = matrix_diagnostics(a32)
        write_csv(out / "core32_symmetric_mean_minutes.csv", [dict(node_id=a,**{b:symmetric[i,j] for j,b in enumerate(core_ids)}) for i,a in enumerate(core_ids)], ["node_id"]+core_ids)
        write_json(out / "core32_matrix_diagnostics.json", diagnostics)
    lhasa = [r for r in routes if r["scenario"]=="observed_group_60" and r["from_node"]=="N26"]
    write_csv(out / "lhasa_outbound_summary.csv", lhasa, list(routes[0]))
    write_csv(out / "lhasa_outbound_legs.csv", [r for r in path_rows if r["scenario"]=="observed_group_60" and r["from_node"]=="N26"], PATH_FIELDS)
    missing = [r for r in routes if r["scenario"]=="observed_group_60" and r["time_min"]==""]
    write_csv(out / "remaining_core_missing.csv", missing, list(routes[0]))
    summary = dict(actor=actor, original_source_records=len(original), restored_schedule_segments=len(restored), combined_source_records=len(combined),
                   source_conflicts=0, dated_source_run=DATED_JOB, input=original_info, scenarios=comparisons,
                   core32_complete=complete, core32_algorithm_input_ready=complete, full34_algorithm_ready=False,
                   raw34_missing=sum(row[b]=="" for row in raw_rows for b in ids), raw34_nodes=34, lhasa_outbound_finite=sum(r["time_min"]!="" for r in lhasa),
                   penalties_applied=False, statistical_imputation_applied=False, synthetic_service_dates_added=False,
                   new_network_requests=0, ticket_availability_verified=False, software=software_versions(),
                   scripts_sha256={n:sha(ROOT/"scripts"/n) for n in ("stage1j_restore.py","stage1i_dated_schedule.py","stage1d_routes.py")},
                   output_dir=str(out), limitations=["Observed model minimum only; uncollected and unknown schedules can affect optima",
                       "Restored edges derive from published dated schedules, not ticket availability or guaranteed operation",
                       "No other origin date was synthesized; intermediate dates follow published arrival day and dwell",
                       "All actual stations retained; no cross-station free links",
                       "Macau access and Taiwan penalty branch still pending; 32 core nodes do not replace 34-node main scope",
                       "Same-station transfer threshold is an assumption; port access and terminal processing excluded"])
    write_json(out / "restoration_summary.json", summary)
    return summary
