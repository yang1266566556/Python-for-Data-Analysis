"""Temporal routes in saved timetables: station identity and absolute time intact.

No new data, static duration summation, geographic guesses, or imputation.
The graph has boarding, arrival, station waiting and on-board continuation states.
"""
import hashlib
import heapq
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from stage1_collect import ROOT, TZ, write_csv, write_json
from stage1b_transfer import read_csv
from stage1d_audit import RUN

PATH_FIELDS = ["scenario", "from_node", "to_node", "leg_index", "edge_id", "train_code", "train_no",
               "origin_service_date", "from_name", "to_name", "departure_at", "arrival_at", "duration_min",
               "wait_before_min", "same_service_as_previous", "raw_file", "raw_row_index"]


def service(row):
    return row["train_no"], row["origin_service_date"]


class TemporalGraph:
    def __init__(self, records, query_date, threshold, latest_arrival, max_elapsed=5760):
        self.records = records
        self.threshold = threshold
        self.max_elapsed = max_elapsed
        self.zero = datetime.fromisoformat(query_date + "T00:00:00+08:00")
        self.query_date = query_date
        self.keys, self.adj, self.ids = [], [], {}
        self.departures, self.arrivals = [], []
        self.station_times = defaultdict(set)
        self.onboard_times = defaultdict(set)
        self.deps_by_city = defaultdict(list)
        self.arrs_by_city = defaultdict(list)
        self.latest = datetime.fromisoformat(latest_arrival)
        for i, r in enumerate(records):
            d, a = self.minute(r["departure_at"]), self.minute(r["arrival_at"])
            assert a > d and a - d == int(r["duration_min"])
            source, target, trip = r["from_code"], r["to_code"], service(r)
            dep, arr = self.vertex(("departure", i)), self.vertex(("arrival", i))
            self.departures.append(dep)
            self.arrivals.append(arr)
            self.edge(dep, arr, a - d, i)
            self.station_times[source].add(d)
            self.station_times[target].add(a + threshold)
            self.onboard_times[(source, trip)].add(d)
            self.onboard_times[(target, trip)].add(a)
            # Arrival is a terminal at the true clock time; buffer applies only
            # when boarding a different service, never at the final destination.
            self.edge(arr, self.vertex(("station", target, a + threshold)), threshold)
            self.edge(arr, self.vertex(("onboard", target, trip, a)), 0)
            self.edge(self.vertex(("station", source, d)), dep, 0)
            self.edge(self.vertex(("onboard", source, trip, d)), dep, 0)
            if datetime.fromisoformat(r["departure_at"]).date().isoformat() == query_date:
                self.deps_by_city[r["from_dictionary_city"]].append(dep)
            self.arrs_by_city[r["to_dictionary_city"]].append((arr, i))
        for station, values in self.station_times.items():
            times = sorted(values)
            for a, b in zip(times, times[1:]):
                self.edge(self.vertex(("station", station, a)), self.vertex(("station", station, b)), b - a)
        for (station, trip), values in self.onboard_times.items():
            times = sorted(values)
            for a, b in zip(times, times[1:]):
                self.edge(self.vertex(("onboard", station, trip, a)), self.vertex(("onboard", station, trip, b)), b - a)

    def minute(self, timestamp):
        value = (datetime.fromisoformat(timestamp) - self.zero).total_seconds() / 60
        assert value.is_integer()
        return int(value)

    def vertex(self, key):
        if key not in self.ids:
            self.ids[key] = len(self.keys)
            self.keys.append(key)
            self.adj.append([])
        return self.ids[key]

    def edge(self, a, b, cost, ride_index=-1):
        assert cost >= 0
        self.adj[a].append((b, cost, ride_index))

    def shortest(self, origin):
        # Seed actual first-train departure states, not waiting states: the
        # first train must leave on the frozen date, not a later day.
        distances = [float("inf")] * len(self.keys)
        parents = [None] * len(self.keys)
        queue = []
        for node in self.deps_by_city[origin]:
            distances[node] = 0
            heapq.heappush(queue, (0, node))
        while queue:
            distance, current = heapq.heappop(queue)
            if distance != distances[current]:
                continue
            for target, cost, ride in self.adj[current]:
                candidate = distance + cost
                if candidate <= self.max_elapsed and candidate < distances[target]:
                    distances[target] = candidate
                    parents[target] = (current, ride)
                    heapq.heappush(queue, (candidate, target))
        return distances, parents

    def itinerary(self, terminal, parents):
        rides = []
        cursor = terminal
        while parents[cursor] is not None:
            previous, ride = parents[cursor]
            if ride >= 0:
                rides.append(ride)
            cursor = previous
        rides.reverse()
        result = [self.records[i] for i in rides]
        assert result
        assert datetime.fromisoformat(result[0]["departure_at"]).date().isoformat() == self.query_date
        assert datetime.fromisoformat(result[-1]["arrival_at"]) < self.latest
        for a, b in zip(result, result[1:]):
            assert a["to_code"] == b["from_code"], "Cross-station transfer must not be free"
            wait = self.minute(b["departure_at"]) - self.minute(a["arrival_at"])
            assert wait >= (0 if service(a) == service(b) else self.threshold)
        elapsed = self.minute(result[-1]["arrival_at"]) - self.minute(result[0]["departure_at"])
        running = sum(int(r["duration_min"]) for r in result)
        waits = sum(self.minute(b["departure_at"]) - self.minute(a["arrival_at"]) for a, b in zip(result, result[1:]))
        assert elapsed == running + waits
        return result, elapsed, waits


def prepare_records(rows, core_cities, candidate_codes, policy, latest):
    by_key = {}
    for row in rows:
        if row["from_dictionary_city"] not in core_cities or row["to_dictionary_city"] not in core_cities:
            continue
        if policy == "draft83" and (row["from_code"] not in candidate_codes or row["to_code"] not in candidate_codes):
            continue
        if datetime.fromisoformat(row["arrival_at"]) >= datetime.fromisoformat(latest):
            continue
        key = (service(row), row["from_code"], row["to_code"], row["departure_at"], row["arrival_at"])
        if key not in by_key:
            by_key[key] = dict(row)
            by_key[key]["edge_id"] = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:20]
    return list(by_key.values())


def run(actor="user", audit_dir=None):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    if audit_dir is None:
        raise ValueError("Run core code 10 first and supply its audit output directory")
    audit_summary = json.loads((Path(audit_dir) / "audit_summary.json").read_text(encoding="utf-8"))
    if not audit_summary["passed"] or audit_summary["source_run"] != RUN:
        raise ValueError("Audit does not cover this data version")
    raw = ROOT / "data/raw" / RUN
    if hashlib.sha256((ROOT / "data/processed" / RUN / "train_records.csv").read_bytes()).hexdigest() != audit_summary["train_csv_sha256"]:
        raise ValueError("Train data changed after audit")
    if hashlib.sha256((raw / "candidate_stations.csv").read_bytes()).hexdigest() != audit_summary["candidate_csv_sha256"]:
        raise ValueError("Station policy changed after audit")
    config = json.loads((raw / "protocol.json").read_text(encoding="utf-8"))
    nodes = read_csv(raw / "nodes.csv")
    core = [n for n in nodes if n["representative_city"] in config["anchor_stations"]]
    cities = {n["representative_city"] for n in core}
    candidate_codes = {s["station_code"] for s in read_csv(raw / "candidate_stations.csv")}
    rows = read_csv(ROOT / "data/processed" / RUN / "train_records.csv")
    if len(rows) != audit_summary["train_records"]:
        raise ValueError("Record count changed since audit")
    out = ROOT / "data/processed" / (actor + "_stage1d_routes_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    route_rows, path_rows, scenario_summaries = [], [], []
    future_plan = {}
    for policy, threshold in [("draft83", 60), ("observed_group", 30), ("observed_group", 60), ("observed_group", 90)]:
        name = policy + "_" + str(threshold)
        print("时间图分析：", name, flush=True)
        started = time.perf_counter()
        records = prepare_records(rows, cities, candidate_codes, policy, config["future_latest_arrival_exclusive"])
        graph = TemporalGraph(records, config["query_date"], threshold, config["future_latest_arrival_exclusive"], config["future_elapsed_limit_minutes"])
        scenario_rows = []
        for origin in core:
            distances, parents = graph.shortest(origin["representative_city"])
            missing_destinations = []
            for dest in core:
                if dest["node_id"] == origin["node_id"]:
                    continue
                terminals = [(distances[node], graph.minute(records[i]["arrival_at"]), node) for node, i in graph.arrs_by_city[dest["representative_city"]] if distances[node] != float("inf")]
                entry = dict(scenario=name, from_node=origin["node_id"], from_city=origin["representative_city"],
                             to_node=dest["node_id"], to_city=dest["representative_city"],
                             model_time_min="", running_min="", wait_min="", transfers="", first_departure="", final_arrival="",
                             status="not_reached_in_saved_departure_days_not_physical_unreachable")
                if terminals:
                    distance, _, terminal = min(terminals)
                    path, elapsed, waits = graph.itinerary(terminal, parents)
                    assert distance == elapsed
                    transfers = sum(service(a) != service(b) for a, b in zip(path, path[1:]))
                    entry.update(model_time_min=elapsed, running_min=elapsed - waits, wait_min=waits, transfers=transfers,
                                 first_departure=path[0]["departure_at"], final_arrival=path[-1]["arrival_at"],
                                 status="minimum_in_saved_event_graph_only")
                    for i, record in enumerate(path):
                        path_rows.append(dict(scenario=name, from_node=origin["node_id"], to_node=dest["node_id"], leg_index=i + 1,
                                              edge_id=record["edge_id"], train_code=record["train_code"], train_no=record["train_no"],
                                              origin_service_date=record["origin_service_date"], from_name=record["from_name"], to_name=record["to_name"],
                                              departure_at=record["departure_at"], arrival_at=record["arrival_at"], duration_min=record["duration_min"],
                                              wait_before_min=0 if i == 0 else graph.minute(record["departure_at"]) - graph.minute(path[i-1]["arrival_at"]),
                                              same_service_as_previous=False if i == 0 else service(path[i-1]) == service(record),
                                              raw_file=record["raw_file"], raw_row_index=record["raw_row_index"]))
                else:
                    missing_destinations.append(dest)
                scenario_rows.append(entry)
            # An explicitly partial next-date plan: request the earliest observed
            # late arrival day at a possible transfer city for unconnected OD pairs.
            # This is a first follow-up pass, not proof that these are all needed queries.
            if policy == "observed_group" and threshold == 60:
                late = {}
                for arr_city, events in graph.arrs_by_city.items():
                    for node, i in events:
                        if distances[node] == float("inf"):
                            continue
                        day = records[i]["arrival_at"][:10]
                        if day > config["query_date"]:
                            late[arr_city] = min(late.get(arr_city, day), day)
                for dest in missing_destinations:
                    for transfer_city, day in late.items():
                        if transfer_city == dest["representative_city"]:
                            continue
                        key = (day, transfer_city, dest["representative_city"])
                        if key not in future_plan:
                            future_plan[key] = dict(query_date=day, from_city=transfer_city, to_city=dest["representative_city"],
                                                    from_anchor=config["anchor_stations"][transfer_city], to_anchor=config["anchor_stations"][dest["representative_city"]],
                                                    affected_od_pairs=set(), reason="late arrival after saved departure date; earliest-day follow-up only")
                        future_plan[key]["affected_od_pairs"].add(origin["representative_city"] + "→" + dest["representative_city"])
        route_rows.extend(scenario_rows)
        finite = [r for r in scenario_rows if r["model_time_min"] != ""]
        summary = dict(scenario=name, station_policy=policy, transfer_threshold_min=threshold,
                       unique_service_edges=len(records), graph_vertices=len(graph.keys),
                       finite_directed_city_pairs=len(finite), missing_directed_city_pairs=992-len(finite),
                       pairs_using_transfer=sum(r["transfers"] > 0 for r in finite), seconds=time.perf_counter()-started)
        scenario_summaries.append(summary)
        print("已采集时刻表中找到的城市对：", len(finite), "/992", flush=True)
    plan_rows = []
    for item in future_plan.values():
        plan_rows.append(dict(query_date=item["query_date"], from_city=item["from_city"], to_city=item["to_city"],
                              from_anchor=item["from_anchor"], to_anchor=item["to_anchor"],
                              affected_od_count=len(item["affected_od_pairs"]), affected_od_pairs=";".join(sorted(item["affected_od_pairs"])), reason=item["reason"]))
    plan_rows.sort(key=lambda r: (-r["affected_od_count"], r["query_date"], r["from_city"], r["to_city"]))
    write_csv(out / "route_scenarios.csv", route_rows, list(route_rows[0]))
    write_csv(out / "route_legs_with_sources.csv", path_rows, PATH_FIELDS)
    write_csv(out / "routing_quality_comparison.csv", scenario_summaries, list(scenario_summaries[0]))
    write_csv(out / "next_date_query_plan.csv", plan_rows, ["query_date", "from_city", "to_city", "from_anchor", "to_anchor", "affected_od_count", "affected_od_pairs", "reason"])
    matrix = []
    baseline = {(r["from_node"], r["to_node"]): r for r in route_rows if r["scenario"] == "observed_group_60"}
    for a in nodes:
        for b in nodes:
            pair = baseline.get((a["node_id"], b["node_id"]))
            value = 0 if a["node_id"] == b["node_id"] else pair["model_time_min"] if pair else ""
            status = "diagonal" if a["node_id"] == b["node_id"] else pair["status"] if pair else "special_region_review_pending"
            matrix.append(dict(from_node=a["node_id"], from_city=a["representative_city"], to_node=b["node_id"], to_city=b["representative_city"],
                               model_time_min=value, status=status))
    write_csv(out / "candidate_timetable_matrix_34_long.csv", matrix, list(matrix[0]))
    summary = dict(actor=actor, source_run=RUN, first_departure_date=config["query_date"], audit_dir=str(audit_dir),
                   scenarios=scenario_summaries, next_date_query_count=len(plan_rows), output_dir=str(out), matrix_ready=False,
                   limitations=["All current boarding records are from Nov 18; later-day departures still need real queries",
                                "30/60/90 minutes are transfer hypotheses, not official station minimums",
                                "observed_group includes saved 12306 city group stations, not verified administrative city boundaries",
                                "Unknown timetable and station records excluded but remain missing; no all-network optimality claim",
                                "No cross-station access, terminal security or border processing time included",
                                "Same train continuation requires both internal train ID and origin service date to match"])
    write_json(out / "routing_summary.json", summary)
    return summary
