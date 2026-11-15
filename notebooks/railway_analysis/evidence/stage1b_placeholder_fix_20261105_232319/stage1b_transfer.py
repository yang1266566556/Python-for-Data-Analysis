"""Stage 1B: reuse user pilot, query boarding dates, compare transfer scenarios.

Standard library + requests. No network at import. Run collect_stage1b() in pda312.
All route results are conditional candidate schedules, not guaranteed journeys.
"""
import csv
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

from stage1_collect import (
    ROOT, TZ, BASE, INIT_URL, SourceClient, SourceError, TRAIN_FIELDS, ISSUE_FIELDS,
    QUERY_FIELDS, parse_station_dictionary, parse_train_response,
    verify_client_field_map, software_versions, now, write_json, write_csv,
)

PAIR_FIELDS = [
    "first_query_id", "second_query_id", "first_train", "second_train",
    "first_train_no", "second_train_no", "first_origin_date", "second_origin_date",
    "from_station", "transfer_station", "to_station", "departure_at",
    "transfer_arrival_at", "transfer_departure_at", "arrival_at",
    "first_duration_min", "wait_min", "second_duration_min", "total_min",
    "same_service_identity", "time_order_ok", "within_window", "classification",
    "first_raw_file", "first_raw_row_index", "second_raw_file", "second_raw_row_index",
]
SUMMARY_FIELDS = [
    "transfer_threshold_min", "candidate_count", "status", "total_min", "wait_min",
    "first_train", "second_train", "from_station", "departure_at", "arrival_at",
    "all_required_queries_validated", "official_transfer_feasibility_verified",
]


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_verified_parent(config):
    run_id = config["parent_run_id"]
    if Path(run_id).name != run_id or not run_id.startswith("user_pilot_"):
        raise ValueError("Invalid parent run identifier")
    raw, processed = ROOT / "data/raw" / run_id, ROOT / "data/processed" / run_id
    summary = json.loads((processed / "pilot_summary.json").read_text(encoding="utf-8"))
    if summary["fatal_error"] or summary["query_date"] != config["first_departure_date"]:
        raise ValueError("Parent error or incompatible query date")
    manifest = json.loads((raw / "source_manifest.json").read_text(encoding="utf-8"))
    entries = {e["source_id"]: e for e in manifest}
    for e in manifest:
        if hashlib.sha256((ROOT / e["raw_file"]).read_bytes()).hexdigest() != e["sha256"]:
            raise ValueError(f"Parent raw hash mismatch: {e['source_id']}")
    # Reconstruct parent records from saved bytes, then compare to the user's CSV.
    stations = parse_station_dictionary((ROOT / entries["station_dictionary"]["raw_file"]).read_text(encoding="utf-8"))
    by_code = {s["station_code"]: s for s in stations}
    quality = read_csv(processed / "pilot_query_quality.csv")
    regenerated = []
    for q in quality:
        entry = entries[q["query_id"]]
        query = dict(q, from_code=entry["params"]["leftTicketDTO.from_station"],
                     to_code=entry["params"]["leftTicketDTO.to_station"])
        rows, _, result = parse_train_response((ROOT / entry["raw_file"]).read_text(encoding="utf-8"), query, by_code, entry)
        if result["rejected_count"]:
            raise ValueError("Parent records no longer pass parser validation")
        regenerated.extend(rows)
    stored = read_csv(processed / "pilot_train_records.csv")
    normalized = [{k: str(row[k]) for k in TRAIN_FIELDS} for row in regenerated]
    if stored != normalized:
        raise ValueError("Parent processed CSV differs from saved original responses")
    snapshots = {}
    for p in [processed / "pilot_train_records.csv", processed / "station_candidates.csv", raw / "source_manifest.json"]:
        snapshots[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return regenerated, stations, snapshots, processed


def build_pairs(first_legs, second_legs, config):
    """Join by actual station code and complete timestamps, not city or clock alone."""
    latest = datetime.fromisoformat(config["latest_arrival_exclusive"])
    pairs = []
    for first in first_legs:
        if first["query_date"] != config["first_departure_date"]:
            continue
        for second in second_legs:
            if first["to_code"] != second["from_code"]:
                continue  # Cross-station travel is not a free edge.
            start = datetime.fromisoformat(first["departure_at"])
            a1 = datetime.fromisoformat(first["arrival_at"])
            d2 = datetime.fromisoformat(second["departure_at"])
            end = datetime.fromisoformat(second["arrival_at"])
            wait = int((d2 - a1).total_seconds() / 60)
            total = int((end - start).total_seconds() / 60)
            same_service = (first["train_no"], first["origin_service_date"]) == (second["train_no"], second["origin_service_date"])
            time_ok = wait >= 0 and a1 >= start and end >= d2
            within = 0 < total <= config["max_elapsed_minutes"] and end < latest
            if not time_ok:
                classification = "departs_before_arrival"
            elif not within:
                classification = "outside_time_window"
            elif same_service:
                classification = "same_service_needs_direct_verification"
            else:
                classification = "time_ordered_transfer_candidate"
            if time_ok:
                assert total == int(first["duration_min"]) + wait + int(second["duration_min"])
            pairs.append(dict(
                first_query_id=first["query_id"], second_query_id=second["query_id"],
                first_train=first["train_code"], second_train=second["train_code"],
                first_train_no=first["train_no"], second_train_no=second["train_no"],
                first_origin_date=first["origin_service_date"], second_origin_date=second["origin_service_date"],
                from_station=first["from_name"], transfer_station=first["to_name"], to_station=second["to_name"],
                departure_at=first["departure_at"], transfer_arrival_at=first["arrival_at"],
                transfer_departure_at=second["departure_at"], arrival_at=second["arrival_at"],
                first_duration_min=int(first["duration_min"]), wait_min=wait,
                second_duration_min=int(second["duration_min"]), total_min=total,
                same_service_identity=same_service, time_order_ok=time_ok,
                within_window=within, classification=classification,
                first_raw_file=first["raw_file"], first_raw_row_index=first["raw_row_index"],
                second_raw_file=second["raw_file"], second_raw_row_index=second["raw_row_index"],
            ))
    return pairs


def summarize_pairs(pairs, config, coverage_validated):
    result = []
    for threshold in config["same_station_transfer_threshold_minutes"]:
        accepted = [r for r in pairs if r["classification"] == "time_ordered_transfer_candidate" and r["wait_min"] >= threshold]
        best = min(accepted, key=lambda r: (r["total_min"], r["departure_at"], r["first_train"], r["second_train"])) if accepted else None
        status = ("best_in_collected_candidates_under_assumption" if best else "no_candidate_in_collected_records_not_unreachable")
        if not coverage_validated:
            status = "incomplete_query_coverage_no_best_claim"
        result.append(dict(
            transfer_threshold_min=threshold, candidate_count=len(accepted), status=status,
            total_min=best["total_min"] if best and coverage_validated else "",
            wait_min=best["wait_min"] if best and coverage_validated else "",
            first_train=best["first_train"] if best and coverage_validated else "",
            second_train=best["second_train"] if best and coverage_validated else "",
            from_station=best["from_station"] if best and coverage_validated else "",
            departure_at=best["departure_at"] if best and coverage_validated else "",
            arrival_at=best["arrival_at"] if best and coverage_validated else "",
            all_required_queries_validated=coverage_validated,
            official_transfer_feasibility_verified=False,
        ))
    return result


def collect_stage1b(actor="user"):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    protocol_file = ROOT / "config/stage1b_protocol.json"
    config_bytes = protocol_file.read_bytes()
    config = json.loads(config_bytes)
    if date.fromisoformat(config["first_departure_date"]) < datetime.now(TZ).date():
        raise ValueError("Frozen query date passed; do not silently redate the experiment")
    parent, old_stations, parent_hashes, parent_dir = load_verified_parent(config)
    spec = [(f"X{day}", f"2026-11-{day}", "西宁", "拉萨", "arrival_date_extension") for day in (11, 12, 13, 14)]
    spec += [("A01", config["first_departure_date"], "广州南", "珠海", "mainland_access_probe"),
             ("A02", config["first_departure_date"], "珠海", "横琴", "mainland_access_probe"),
             ("A03", config["first_departure_date"], "横琴", "珠海", "mainland_access_reverse_probe")]
    if len(spec) > config["max_new_train_queries"]:
        raise ValueError("Configured query limit exceeded")
    # All departure days that can contribute under the exclusive latest-arrival bound.
    required_days = set()
    day = date.fromisoformat(config["first_departure_date"])
    while day < datetime.fromisoformat(config["latest_arrival_exclusive"]).date():
        required_days.add(day.isoformat())
        day += timedelta(days=1)
    planned_days = {config["first_departure_date"]} | {s[1] for s in spec if s[0].startswith("X")}
    if required_days != planned_days:
        raise ValueError("Query plan no longer matches the frozen date window")
    run_id = actor + "_stage1b_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f")
    raw, out = ROOT / "data/raw" / run_id, ROOT / "data/processed" / run_id
    raw.mkdir(exist_ok=False)
    out.mkdir(exist_ok=False)
    (raw / "stage1b_protocol.json").write_bytes(config_bytes)
    for name in ("stage1b_transfer.py", "stage1_collect.py"):
        (raw / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    metadata = dict(actor=actor, run_id=run_id, started_at=now(), software=software_versions(),
                    parent_run_id=config["parent_run_id"], parent_files_sha256=parent_hashes,
                    protocol_sha256=hashlib.sha256(config_bytes).hexdigest(),
                    official_transfer_feasibility_verified=False)
    new_records, queries, issues = [], [], []
    fatal = None
    client = SourceClient(raw, actor, config["request_interval_seconds"])
    try:
        page, _ = client.get("query_page", INIT_URL)
        endpoint = re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]", page)
        if not endpoint:
            raise SourceError("Current endpoint unavailable in official page")
        station_link = re.search(r'src=["\']([^"\']*/station_name\.js[^"\']*)', page)
        field_link = re.search(r'src=["\']([^"\']*/queryLeftTicket_end_js\.js[^"\']*)', page)
        if not station_link or not field_link:
            raise SourceError("Station dictionary or official field mapping link missing")
        links = [urljoin(INIT_URL, m.group(1)) for m in (station_link, field_link)]
        if any(urlparse(url).netloc != "kyfw.12306.cn" for url in links):
            raise SourceError("Unexpected source host")
        text, _ = client.get("station_dictionary", links[0])
        stations = parse_station_dictionary(text)
        field_text, _ = client.get("official_field_mapping", links[1])
        metadata["verified_field_mapping"] = verify_client_field_map(field_text)
        by_name = {r["station_name"]: r for r in stations}
        by_code = {r["station_code"]: r for r in stations}
        # Ensure the old and new response station identities agree before combining.
        old_by_code = {r["station_code"]: r for r in old_stations}
        for code in {r[k] for r in parent for k in ("from_code", "to_code")}:
            if code not in by_code or by_code[code]["station_name"] != old_by_code[code]["station_name"]:
                raise SourceError(f"Station identity changed between snapshots: {code}")
        write_csv(out / "station_dictionary.csv", stations, list(stations[0]))
        candidates = read_csv(parent_dir / "station_candidates.csv")
        qinghe = by_name.get(config["new_station_candidate"])
        if not qinghe or qinghe["source_city_name"] != "北京":
            raise SourceError("New station candidate did not pass dictionary identity check")
        if not any(c["station_name"] == "清河" for c in candidates):
            candidates.append(dict(node_id="N01", city="北京", station_name="清河", station_code=qinghe["station_code"],
                                   dictionary_city="北京", dictionary_city_code=qinghe["source_city_code"],
                                   status="observed_in_parent_and_dictionary_matched",
                                   selected_for_final_network="pending"))
        write_csv(out / "station_candidates_v2_draft.csv", candidates, list(candidates[0]))
        for qid, day, a, b, purpose in spec:
            if a not in by_name or b not in by_name:
                raise SourceError(f"Station absent from dictionary: {a}/{b}")
            query = dict(query_id=qid, date=day, from_station=a, to_station=b, purpose=purpose,
                         from_code=by_name[a]["station_code"], to_code=by_name[b]["station_code"])
            public = {k: v for k, v in query.items() if k not in ("from_code", "to_code")}
            try:
                body, source = client.get(qid, urljoin(BASE, endpoint.group(1)), {
                    "leftTicketDTO.train_date": day, "leftTicketDTO.from_station": query["from_code"],
                    "leftTicketDTO.to_station": query["to_code"], "purpose_codes": "ADULT"})
                rows, row_issues, quality = parse_train_response(body, query, by_code, source)
                new_records.extend(rows)
                issues.extend(row_issues)
                public.update(quality, raw_file=source["raw_file"], error="")
                queries.append(public)
                print(f"{qid} {day} {a} → {b}: {quality['status']}, valid={quality['valid_count']}", flush=True)
                if quality["rejected_count"]:
                    raise SourceError("Quarantined records require review; remaining queries stopped")
            except SourceError as error:
                if not queries or queries[-1]["query_id"] != qid:
                    public.update(status="request_or_schema_failed_not_unreachable", raw_count="", valid_count="",
                                  rejected_count="", duplicate_count="", raw_file="", error=str(error))
                    queries.append(public)
                raise
    except SourceError as error:
        fatal = str(error)
    finally:
        client.close()
        seen = {q["query_id"] for q in queries}
        for qid, day, a, b, purpose in spec:
            if qid not in seen:
                queries.append(dict(query_id=qid, date=day, from_station=a, to_station=b, purpose=purpose,
                                    status="not_attempted", raw_count="", valid_count="", rejected_count="",
                                    duplicate_count="", raw_file="", error=""))
        write_csv(out / "new_train_records.csv", new_records, TRAIN_FIELDS)
        write_csv(out / "new_query_quality.csv", queries, QUERY_FIELDS)
        write_csv(out / "cleaning_issues.csv", issues, ISSUE_FIELDS)
        first = [r for r in parent if r["query_id"] == "P05"]
        second = [r for r in parent if r["query_id"] == "P06"] + [r for r in new_records if r["query_id"].startswith("X")]
        # Explicitly limit to verified city grouping and the actual Xining station.
        first = [r for r in first if r["from_dictionary_city"] == "北京" and r["to_name"] == "西宁"]
        second = [r for r in second if r["from_name"] == "西宁" and r["to_name"] == "拉萨"]
        pairs = build_pairs(first, second, config)
        validated_statuses = {"validated_records", "no_direct_train_returned_not_unreachable"}
        coverage = all(q["status"] in validated_statuses for q in queries if q["query_id"].startswith("X"))
        scenarios = summarize_pairs(pairs, config, coverage)
        write_csv(out / "all_same_station_pairs.csv", pairs, PAIR_FIELDS)
        write_csv(out / "same_service_candidates.csv", [p for p in pairs if p["classification"] == "same_service_needs_direct_verification"], PAIR_FIELDS)
        write_csv(out / "transfer_scenarios.csv", scenarios, SUMMARY_FIELDS)
        result = dict(run_id=run_id, parent_run_id=config["parent_run_id"], actor=actor,
                      attempted_queries=sum(q["status"] != "not_attempted" for q in queries),
                      new_train_records=len(new_records), issue_count=len(issues), fatal_error=fatal,
                      all_required_transfer_dates_queried_successfully=coverage,
                      first_leg_records=len(first), second_leg_records=len(second),
                      same_station_pair_count=len(pairs), output_dir=str(out), raw_dir=str(raw),
                      matrix_ready=False, official_transfer_feasibility_verified=False,
                      scope="conditional two-service candidates via Xining only; not a complete railway matrix")
        metadata.update(finished_at=now(), summary=result)
        write_json(raw / "run_metadata.json", metadata)
        write_json(out / "stage1b_summary.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(collect_stage1b(), ensure_ascii=False, indent=2))
