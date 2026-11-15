"""Offline full-pair audit, before any routing or missing-value treatment."""

from railway_project_io import read_project_json
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from stage1_collect import ROOT, TZ, TRAIN_FIELDS, parse_station_dictionary, write_csv, write_json
from stage1c_parser_v2 import parse_train_response, PARSER_VERSION
from stage1b_transfer import read_csv

RUN = "user_stage1c_v2_20261113_132207_325427"


def audit(actor="user"):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    raw, processed = ROOT / "data/raw" / RUN, ROOT / "data/processed" / RUN
    plan = read_project_json(raw / 'plan.json')
    config = read_project_json(raw / 'protocol.json')
    nodes = read_csv(raw / "nodes.csv")
    candidates = read_csv(raw / "candidate_stations.csv")
    by_code, seen_hashes = {}, {}
    records, issues, quality, sources = [], [], [], []
    for query in plan:
        cp = read_project_json(raw / 'checkpoints' / (query['query_id'] + '.json'))
        assert cp["parser_version"] == PARSER_VERSION
        assert all(cp["query"][k] == v for k, v in query.items()), "Checkpoint query differs from frozen plan"
        for source in (cp["source"], cp["station_snapshot"]):
            path = source["raw_file"]
            if path not in seen_hashes:
                seen_hashes[path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            assert seen_hashes[path] == source["sha256"], "Original file hash mismatch"
        station_file = cp["station_snapshot"]["raw_file"]
        if station_file not in by_code:
            by_code[station_file] = {s["station_code"]: s for s in parse_station_dictionary((ROOT / station_file).read_text(encoding="utf-8"))}
        parsed, parsed_issues, q = parse_train_response((ROOT / cp["source"]["raw_file"]).read_text(encoding="utf-8"), cp["query"], by_code[station_file], cp["source"])
        assert (parsed, parsed_issues, q) == (cp["records"], cp["issues"], cp["quality"]), "Saved parse differs from raw replay"
        assert q["rejected_count"] == 0
        assert q["raw_count"] == q["valid_count"] + q["duplicate_count"] + q["unavailable_count"] + q.get("unresolved_station_count", 0)
        records.extend(parsed)
        issues.extend(parsed_issues)
        quality.append(dict(query_id=query["query_id"], from_city=query["from_city"], to_city=query["to_city"],
                            status=q["status"], raw_count=q["raw_count"], valid_count=q["valid_count"],
                            unavailable_count=q["unavailable_count"], unresolved_station_count=q.get("unresolved_station_count", 0)))
        sources.append(dict(query_id=query["query_id"], url=cp["source"]["url"], accessed_at=cp["source"]["accessed_at"],
                            query_date=query["date"], raw_file=cp["source"]["raw_file"], sha256=cp["source"]["sha256"]))
    stored = read_csv(processed / "train_records.csv")
    assert [{k: str(r[k]) for k in TRAIN_FIELDS} for r in records] == stored, "Exported train CSV differs from authenticated checkpoints"
    node_by_city = {n["representative_city"]: n["node_id"] for n in nodes}
    candidate_codes = {c["station_code"] for c in candidates if c["station_code"]}
    inventory, station_counts = {}, Counter()
    for row in records:
        for side in ("from", "to"):
            code, city, name = row[side + "_code"], row[side + "_dictionary_city"], row[side + "_name"]
            if city not in node_by_city:
                continue
            key = (code, city, name)
            station_counts[key] += 1
            inventory[key] = dict(node_id=node_by_city[city], city=city, station_code=code, station_name=name,
                                  in_original_candidate_set=code in candidate_codes,
                                  basis="saved 12306 city grouping; not verified administrative boundary",
                                  record_endpoint_appearances=0)
    for key, item in inventory.items():
        item["record_endpoint_appearances"] = station_counts[key]
    station_inventory = sorted(inventory.values(), key=lambda r: (r["node_id"], r["station_code"]))
    identities = {}
    for row in station_inventory:
        identity = row["city"], row["station_name"]
        assert row["station_code"] not in identities or identities[row["station_code"]] == identity, "Station identity changed across snapshots"
        identities[row["station_code"]] = identity
    direct = read_csv(processed / "direct_screen_34x34_long.csv")
    assert len(direct) == 34 * 34 and len({(r["from_node"], r["to_node"]) for r in direct}) == 34 * 34
    assert all(r["observed_direct_min_minutes"] == "0" for r in direct if r["from_node"] == r["to_node"])
    for row in records:
        dep, arr = datetime.fromisoformat(row["departure_at"]), datetime.fromisoformat(row["arrival_at"])
        assert dep.date().isoformat() == config["query_date"]
        assert (arr - dep).total_seconds() == row["duration_min"] * 60 > 0
    times = [datetime.fromisoformat(s["accessed_at"]) for s in sources]
    span = (max(times) - min(times)).total_seconds() / 3600
    assert span <= config["max_collection_span_hours"], "Collection exceeded frozen snapshot-span policy"
    result = dict(actor=actor, audited_at=datetime.now(TZ).isoformat(), source_run=RUN, query_date=config["query_date"],
                  planned_queries=len(plan), verified_queries=len(quality), train_records=len(records),
                  unknown_timetable_rows=sum(q["unavailable_count"] for q in quality),
                  unresolved_station_rows=sum(q["unresolved_station_count"] for q in quality),
                  raw_and_dictionary_files_hash_verified=len(seen_hashes),
                  original_station_candidates=len(candidates), observed_core_stations=len(station_inventory),
                  observed_stations_outside_draft=sum(not r["in_original_candidate_set"] for r in station_inventory),
                  collection_span_hours=span, source_access_start=min(times).isoformat(), source_access_end=max(times).isoformat(),
                  train_csv_sha256=hashlib.sha256((processed / "train_records.csv").read_bytes()).hexdigest(),
                  candidate_csv_sha256=hashlib.sha256((raw / "candidate_stations.csv").read_bytes()).hexdigest(),
                  query_status_counts=dict(Counter(q["status"] for q in quality)), passed=True,
                  matrix_ready=False, limit="Internal consistency audit; not proof of whole-city station coverage, complete timetables, connectivity or shortest travel")
    out = ROOT / "data/processed" / (actor + "_stage1d_audit_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    write_csv(out / "query_quality_verified.csv", quality, list(quality[0]))
    write_csv(out / "observed_station_inventory.csv", station_inventory, list(station_inventory[0]))
    write_csv(out / "source_register.csv", sources, list(sources[0]))
    result["output_dir"] = str(out)
    write_json(out / "audit_summary.json", result)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", choices=["user", "assistant"], default="user")
    print(json.dumps(audit(parser.parse_args().actor), ensure_ascii=False, indent=2))
