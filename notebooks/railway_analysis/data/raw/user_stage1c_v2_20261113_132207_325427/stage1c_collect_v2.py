"""Checkpointed first-pass direct-service screening; not a shortest-time matrix.

One fresh dataset version, no automatic retries, default TLS, 3-second spacing.
Each query commits its own raw reference + parsed checkpoint before proceeding.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from stage1_collect import (
    ROOT, TZ, BASE, INIT_URL, SourceClient, SourceError, TRAIN_FIELDS, ISSUE_FIELDS,
    parse_station_dictionary, verify_client_field_map,
    write_csv, write_json, software_versions, now,
)
from stage1b_transfer import read_csv
from stage1c_parser_v2 import parse_train_response, PARSER_VERSION

CONFIG_PATH = ROOT / "config/stage1c_collection_v20261118.json"
GOOD_STATES = {"validated_records", "no_direct_train_returned_not_unreachable", "partial_timetable_unavailable", "partial_station_metadata_unresolved"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary, value)
    temporary.replace(path)


def make_plan(config, nodes):
    core = [n for n in nodes if n["representative_city"] in config["anchor_stations"]]
    assert len(core) == 32 and len(nodes) == 34
    plan = []
    for a in core:
        for b in core:
            if a["node_id"] == b["node_id"]:
                continue
            plan.append(dict(query_id=a["node_id"] + "_" + b["node_id"], date=config["query_date"],
                             from_node=a["node_id"], to_node=b["node_id"],
                             from_city=a["representative_city"], to_city=b["representative_city"],
                             from_station=config["anchor_stations"][a["representative_city"]],
                             to_station=config["anchor_stations"][b["representative_city"]], role="core_direct_screen"))
    # Put informative, already understood routes first for the preflight.
    priority = ["N01_N09", "N09_N01", "N19_N32", "N29_N26"]
    plan.sort(key=lambda q: (priority.index(q["query_id"]) if q["query_id"] in priority else 99, q["query_id"]))
    for i, (a, b) in enumerate([("广州南", "珠海"), ("珠海", "横琴"), ("横琴", "珠海")], 1):
        plan.append(dict(query_id=f"ACCESS_{i}", date=config["query_date"], from_node="", to_node="",
                         from_city="广州" if i == 1 else "珠海", to_city="珠海",
                         from_station=a, to_station=b, role="auxiliary_access_only"))
    assert len(plan) == 995 and len({q["query_id"] for q in plan}) == 995
    return plan


def checkpoint_valid(job, checkpoint):
    if checkpoint.get("parser_version") != PARSER_VERSION:
        raise ValueError("Checkpoint parser version differs; migrate saved bytes before use")
    source = checkpoint["source"]
    if digest(ROOT / source["raw_file"]) != source["sha256"]:
        raise ValueError("Saved raw response was modified: " + checkpoint["query"]["query_id"])
    station_path = ROOT / checkpoint["station_snapshot"]["raw_file"]
    if digest(station_path) != checkpoint["station_snapshot"]["sha256"]:
        raise ValueError("Station dictionary snapshot was modified")
    # Full reconstruction is done once per export, not on every next query.
    return True


def export_job(job_dir):
    """Offline export; unfinished queries remain missing and 34 nodes stay present."""
    job = Path(job_dir).resolve()
    allowed = (ROOT / "data/raw").resolve()
    if not job.is_relative_to(allowed):
        raise ValueError("Job is not in project raw data")
    config = json.loads((job / "protocol.json").read_text(encoding="utf-8"))
    plan = json.loads((job / "plan.json").read_text(encoding="utf-8"))
    nodes = read_csv(job / "nodes.csv")
    candidates = read_csv(job / "candidate_stations.csv")
    allowed_by_node = {n["node_id"]: {c["station_name"] for c in candidates if c["node_id"] == n["node_id"]} for n in nodes}
    out = ROOT / "data/processed" / job.name
    out.mkdir(exist_ok=True)
    by_id = {}
    records, quality, issues, outside, minimum = [], [], [], [], {}
    unresolved = []
    station_cache = {}
    for query in plan:
        path = job / "checkpoints" / (query["query_id"] + ".json")
        if not path.exists():
            quality.append(dict(query_id=query["query_id"], from_city=query["from_city"], to_city=query["to_city"],
                                status="not_collected", raw_count="", valid_count="", unavailable_count="", unresolved_station_count="", accepted_candidate_rows=""))
            continue
        cp = json.loads(path.read_text(encoding="utf-8"))
        checkpoint_valid(job, cp)
        station_path = cp["station_snapshot"]["raw_file"]
        if station_path not in station_cache:
            station_cache[station_path] = {s["station_code"]: s for s in parse_station_dictionary((ROOT / station_path).read_text(encoding="utf-8"))}
        parsed, parsed_issues, q = parse_train_response((ROOT / cp["source"]["raw_file"]).read_text(encoding="utf-8"), cp["query"], station_cache[station_path], cp["source"])
        if parsed != cp["records"] or parsed_issues != cp["issues"] or q != cp["quality"]:
            raise ValueError("Parsed checkpoint differs from raw response: " + query["query_id"])
        by_id[query["query_id"]] = cp
        records.extend(parsed)
        issues.extend(parsed_issues)
        for issue in parsed_issues:
            if issue["issue"] == "station_metadata_unresolved":
                unresolved.append(dict(query_id=issue["query_id"], raw_row_index=issue["raw_row_index"], details=issue["details"]))
        accepted = []
        for r in parsed:
            if query["role"] == "core_direct_screen":
                matches = (r["from_dictionary_city"] == query["from_city"] and r["to_dictionary_city"] == query["to_city"]
                           and r["from_name"] in allowed_by_node[query["from_node"]] and r["to_name"] in allowed_by_node[query["to_node"]])
            else:
                matches = r["same_as_requested_stations"]
            if matches:
                accepted.append(r)
            else:
                outside.append(dict(query_id=query["query_id"], from_name=r["from_name"], to_name=r["to_name"],
                                    from_dictionary_city=r["from_dictionary_city"], to_dictionary_city=r["to_dictionary_city"],
                                    train_code=r["train_code"], raw_file=r["raw_file"], raw_row_index=r["raw_row_index"],
                                    reason="outside_draft_station_set_or_requested_auxiliary_endpoints"))
        quality.append(dict(query_id=query["query_id"], from_city=query["from_city"], to_city=query["to_city"],
                            status=q["status"], raw_count=q["raw_count"], valid_count=q["valid_count"],
                            unavailable_count=q["unavailable_count"], unresolved_station_count=q.get("unresolved_station_count", 0), accepted_candidate_rows=len(accepted)))
        if accepted:
            minimum[query["query_id"]] = min(r["duration_min"] for r in accepted)
    long_table = []
    for a in nodes:
        for b in nodes:
            qid = a["node_id"] + "_" + b["node_id"]
            cp = by_id.get(qid)
            value = ""
            if a["node_id"] == b["node_id"]:
                value, status = 0, "diagonal"
            elif a["representative_city"] in ("澳门", "台北") or b["representative_city"] in ("澳门", "台北"):
                status = "special_region_connection_review_pending"
            elif cp is None:
                status = "not_collected"
            elif qid in minimum:
                value, status = minimum[qid], "observed_direct_min_only_not_shortest_itinerary"
                if cp["quality"]["unavailable_count"]:
                    status += "_with_unknown_timetables"
            elif cp["quality"]["unavailable_count"]:
                status = "unknown_timetable_no_accepted_known_duration"
            elif cp["quality"]["valid_count"]:
                status = "returned_stations_outside_draft_set"
            else:
                status = "no_direct_record_returned_not_unreachable"
            if cp is not None and cp["quality"].get("unresolved_station_count", 0):
                status += "_with_unresolved_station_metadata"
            long_table.append(dict(from_node=a["node_id"], from_city=a["representative_city"],
                                   to_node=b["node_id"], to_city=b["representative_city"],
                                   observed_direct_min_minutes=value, status=status))
    write_csv(out / "nodes_34.csv", nodes, list(nodes[0]))
    write_csv(out / "query_quality.csv", quality, list(quality[0]))
    write_csv(out / "train_records.csv", records, TRAIN_FIELDS)
    write_csv(out / "cleaning_issues.csv", issues, ISSUE_FIELDS)
    write_csv(out / "unresolved_station_records.csv", unresolved, ["query_id", "raw_row_index", "details"])
    write_csv(out / "stations_to_review.csv", outside, ["query_id", "from_name", "to_name", "from_dictionary_city", "to_dictionary_city", "train_code", "raw_file", "raw_row_index", "reason"])
    write_csv(out / "direct_screen_34x34_long.csv", long_table, list(long_table[0]))
    summary = dict(dataset_id=config["dataset_id"], query_date=config["query_date"], job_dir=str(job), output_dir=str(out),
                   actor=json.loads((job / "job_metadata.json").read_text(encoding="utf-8"))["actor"],
                   total_planned_queries=len(plan), completed_queries=len(by_id), remaining_queries=len(plan) - len(by_id),
                   train_records=len(records), unavailable_timetable_records=sum(c["quality"]["unavailable_count"] for c in by_id.values()),
                   unresolved_station_record_count=len(unresolved), parser_version=PARSER_VERSION,
                   outside_candidate_record_count=len(outside), query_status_counts=dict(Counter(q["status"] for q in quality)),
                   matrix_ready=False,
                   blocking_error=json.loads((job / "blocked.json").read_text(encoding="utf-8")) if (job / "blocked.json").exists() else None,
                   scope="direct-service screening only; intermediate paths and complete station coverage still to be audited")
    write_json(out / "collection_summary.json", summary)
    return summary


def collect(actor="user", job_dir=None, max_queries=None):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    protocol_bytes = CONFIG_PATH.read_bytes()
    config = json.loads(protocol_bytes)
    query_date = date.fromisoformat(config["query_date"])
    today = datetime.now(TZ).date()
    if not 0 <= (query_date - today).days < 15:
        raise ValueError("Frozen date outside typical 15-day query window. Keep old results; review a new version explicitly.")
    if max_queries is None:
        max_queries = config["max_queries_per_call"]
    if not isinstance(max_queries, int) or max_queries < 0 or max_queries > 995:
        raise ValueError("max_queries must be an integer in 0..995")
    if job_dir:
        job = Path(job_dir).resolve()
        if not job.is_relative_to((ROOT / "data/raw").resolve()):
            raise ValueError("Job outside project")
        if (job / "protocol.json").read_bytes() != protocol_bytes:
            raise ValueError("Configuration changed; use a new version, not a mixed resume")
        meta = json.loads((job / "job_metadata.json").read_text(encoding="utf-8"))
        if meta["actor"] != actor:
            raise ValueError("Do not relabel assistant execution as user execution")
        if meta.get("parser_version") != PARSER_VERSION:
            raise ValueError("Job is not migrated to the fixed v2 parser")
        if (datetime.now(TZ) - datetime.fromisoformat(meta["started_at"])).total_seconds() > 3600 * config["max_collection_span_hours"]:
            raise ValueError("Collection spans over 48h; begin a separate snapshot version")
        for name, expected in meta["code_hashes"].items():
            if digest(ROOT / "scripts" / name) != expected:
                raise ValueError("Collector code changed; review resume compatibility first")
        if (job / "blocked.json").exists():
            raise ValueError("Previous attempt stopped on an error. Inspect blocked.json; automatic retry disabled.")
        plan = json.loads((job / "plan.json").read_text(encoding="utf-8"))
    else:
        job = ROOT / "data/raw" / (actor + "_stage1c_v2_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
        job.mkdir(exist_ok=False)
        (job / "checkpoints").mkdir()
        (job / "sessions").mkdir()
        (job / "protocol.json").write_bytes(protocol_bytes)
        (job / "nodes.csv").write_bytes((ROOT / config["node_file"]).read_bytes())
        (job / "candidate_stations.csv").write_bytes((ROOT / config["candidate_station_file"]).read_bytes())
        plan = make_plan(config, read_csv(job / "nodes.csv"))
        write_json(job / "plan.json", plan)
        code_hashes = {}
        for name in ("stage1c_collect_v2.py", "stage1c_parser_v2.py", "stage1_collect.py", "stage1b_transfer.py"):
            (job / name).write_bytes((ROOT / "scripts" / name).read_bytes())
            code_hashes[name] = digest(ROOT / "scripts" / name)
        write_json(job / "job_metadata.json", dict(actor=actor, started_at=now(), code_hashes=code_hashes, software=software_versions(), parser_version=PARSER_VERSION,
                                                   source_note="website interface; no claim of open-data API permission or exhaustive city station results"))
    print("采集目录：", job, flush=True)
    remaining = [q for q in plan if not (job / "checkpoints" / (q["query_id"] + ".json")).exists()]
    if max_queries == 0 or not remaining:
        return export_job(job)
    lock = job / "running.lock"
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(now())
    session = job / "sessions" / datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f")
    session.mkdir(exist_ok=False)
    client = SourceClient(session, actor, config["request_interval_seconds"])
    current = "initialization"
    completed_now = 0
    try:
        page, _ = client.get("query_page", INIT_URL)
        endpoint = re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]", page)
        station_link = re.search(r'src=["\']([^"\']*/station_name\.js[^"\']*)', page)
        field_link = re.search(r'src=["\']([^"\']*/queryLeftTicket_end_js\.js[^"\']*)', page)
        if not endpoint or not station_link or not field_link:
            raise SourceError("Official interface metadata unavailable; stop without guessing")
        urls = [urljoin(INIT_URL, m.group(1)) for m in (station_link, field_link)]
        if any(urlparse(u).netloc != "kyfw.12306.cn" for u in urls):
            raise SourceError("Unexpected metadata host")
        text, station_source = client.get("station_dictionary", urls[0])
        stations = parse_station_dictionary(text)
        by_name = {s["station_name"]: s for s in stations}
        by_code = {s["station_code"]: s for s in stations}
        js, _ = client.get("official_field_mapping", urls[1])
        verify_client_field_map(js)
        for q in remaining[:max_queries]:
            current = q["query_id"]
            if q["from_station"] not in by_name or q["to_station"] not in by_name:
                raise SourceError("Anchor station not found in current dictionary")
            query = dict(q, from_code=by_name[q["from_station"]]["station_code"], to_code=by_name[q["to_station"]]["station_code"])
            body, source = client.get(current, urljoin(BASE, endpoint.group(1)), {
                "leftTicketDTO.train_date": q["date"], "leftTicketDTO.from_station": query["from_code"],
                "leftTicketDTO.to_station": query["to_code"], "purpose_codes": "ADULT"})
            records, issues, quality = parse_train_response(body, query, by_code, source)
            cp = dict(query=query, source=source, station_snapshot=station_source, parser_version=PARSER_VERSION,
                      quality=quality, records=records, issues=issues)
            if quality["status"] not in GOOD_STATES:
                write_json(session / (current + "_quarantined.json"), cp)
                raise SourceError("Unexpected or invalid records; see quarantined checkpoint")
            atomic_json(job / "checkpoints" / (current + ".json"), cp)
            completed_now += 1
            if completed_now <= 4 or completed_now % 25 == 0 or completed_now == len(remaining[:max_queries]):
                print(f"{len(plan)-len(remaining)+completed_now}/{len(plan)} {q['from_city']}→{q['to_city']}: {quality['status']}; valid={quality['valid_count']}", flush=True)
        atomic_json(job / "last_progress.json", dict(at=now(), new_completed=completed_now, interrupted=False))
    except KeyboardInterrupt:
        atomic_json(job / "last_progress.json", dict(at=now(), new_completed=completed_now, interrupted=True, interrupted_query=current))
        print("已中断。完成的请求已保存，可使用此采集目录继续。", flush=True)
    except SourceError as error:
        atomic_json(job / "blocked.json", dict(at=now(), query_id=current, error=str(error), auto_retry=False))
        print("采集暂停：", str(error), flush=True)
    finally:
        client.close()
        lock.unlink()
    return export_job(job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", choices=["user", "assistant"], default="user")
    parser.add_argument("--job-dir")
    parser.add_argument("--max-queries", type=int)
    args = parser.parse_args()
    print(json.dumps(collect(args.actor, args.job_dir, args.max_queries), ensure_ascii=False, indent=2))
