"""Checkpointed targeted collection from an authenticated user routing plan.

436 later-date queries + 68 one-time source refreshes in the present plan.
No timetable guessing, source overwrite, automatic retry or date substitution.
"""

from railway_project_io import read_project_json, script_hash_matches
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

from stage1_collect import ROOT, TZ, BASE, INIT_URL, SourceClient, SourceError, TRAIN_FIELDS, ISSUE_FIELDS, parse_station_dictionary, verify_client_field_map, write_json, write_csv, software_versions, now
from stage1c_parser_v2 import parse_train_response, PARSER_VERSION
from stage1b_transfer import read_csv

PRIMARY = "user_stage1c_v2_20261113_132207_325427"
ROUTING = "user_stage1d_routes_20261113_141703_918913"
MARKER = ROOT / "evidence/stage1e_current_job.json"
ACCEPTED = {"validated_records", "no_direct_train_returned_not_unreachable", "partial_timetable_unavailable", "partial_station_metadata_unresolved"}
CODE_FILES = ["stage1e_followups.py", "stage1c_parser_v2.py", "stage1_collect.py"]
QUALITY_FIELDS = ["query_id", "role", "primary_query_id", "date", "from_city", "to_city", "status", "raw_count", "valid_count", "unavailable_count", "unresolved_station_count"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, obj):
    temporary = Path(path).with_suffix(".tmp")
    write_json(temporary, obj)
    temporary.replace(path)


def plan_followups():
    """Only builds the immutable plan, with no requests or task creation."""
    primary = ROOT / "data/raw" / PRIMARY
    routing_dir = ROOT / "data/processed" / ROUTING
    route_summary = read_project_json(routing_dir / 'routing_summary.json')
    audit_file = Path(route_summary["audit_dir"]) / "audit_summary.json"
    audited = read_project_json(audit_file)
    if not audited["passed"] or audited["source_run"] != PRIMARY:
        raise ValueError("Routing plan lacks a matching passed audit")
    if sha(ROOT / "data/processed" / PRIMARY / "train_records.csv") != audited["train_csv_sha256"]:
        raise ValueError("Primary data changed after user audit")
    original_plan = read_project_json(primary / 'plan.json')
    original_by_id = {q["query_id"]: q for q in original_plan}
    protocol = read_project_json(primary / 'protocol.json')
    meta = read_project_json(primary / 'job_metadata.json')
    pending = read_csv(routing_dir / "next_date_query_plan.csv")
    plan = []
    for q in original_plan:
        cp = read_project_json(primary / 'checkpoints' / (q['query_id'] + '.json'))
        if not (cp["quality"]["unavailable_count"] or cp["quality"].get("unresolved_station_count", 0)):
            continue
        plan.append(dict(query_id="R_" + q["query_id"], role="refresh_primary_unknown",
                         primary_query_id=q["query_id"], date=q["date"], from_city=q["from_city"], to_city=q["to_city"],
                         from_station=q["from_station"], to_station=q["to_station"],
                         reason="One source refresh for timetable/station metadata missing; no guarantee it has changed"))
    # Put the missing initial services first; the remaining original gaps follow.
    plan.sort(key=lambda q: (0 if q["primary_query_id"] == "N26_N29" else 1 if q["from_city"] == "拉萨" else 2, q["query_id"]))
    for i, p in enumerate(pending, 1):
        plan.append(dict(query_id=f"F{i:04d}", role="followup_date", primary_query_id="", date=p["query_date"],
                         from_city=p["from_city"], to_city=p["to_city"], from_station=p["from_anchor"], to_station=p["to_anchor"],
                         reason="User-produced missing-OD plan; earliest later arrival date, not an exhaustive network survey"))
    keys = [(p["date"], p["from_station"], p["to_station"]) for p in plan]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate planned requests need review")
    for q in plan:
        if q["role"] == "refresh_primary_unknown":
            assert q["primary_query_id"] in original_by_id
    end = datetime.fromisoformat(meta["started_at"]) + timedelta(hours=protocol["max_collection_span_hours"])
    info = dict(primary_run=PRIMARY, user_routing_run=ROUTING, first_departure_date=protocol["query_date"],
                snapshot_deadline_exclusive=end.isoformat(), snapshot_start=meta["started_at"],
                primary_train_csv_sha256=audited["train_csv_sha256"], user_plan_sha256=sha(routing_dir / "next_date_query_plan.csv"),
                parser_version=PARSER_VERSION, refresh_count=sum(q["role"] == "refresh_primary_unknown" for q in plan),
                followup_count=sum(q["role"] == "followup_date" for q in plan), total_queries=len(plan),
                plan_date_counts=dict(Counter(q["date"] for q in plan)),
                source_role="Refresh and later-date evidence preserved separately from primary queries",
                request_interval_seconds=3, automatic_retries=0,
                limit="Does not guarantee resolving missing schedules, all stations or all possible faster routes")
    return plan, info


def verify_checkpoint(cp, station_cache):
    if cp.get("parser_version") != PARSER_VERSION:
        raise ValueError("Parser version mismatch")
    for source in (cp["source"], cp["station_snapshot"]):
        if sha(ROOT / source["raw_file"]) != source["sha256"]:
            raise ValueError("Raw source hash mismatch")
    path = cp["station_snapshot"]["raw_file"]
    if path not in station_cache:
        station_cache[path] = {r["station_code"]: r for r in parse_station_dictionary((ROOT / path).read_text(encoding="utf-8"))}
    parsed = parse_train_response((ROOT / cp["source"]["raw_file"]).read_text(encoding="utf-8"), cp["query"], station_cache[path], cp["source"])
    if parsed != (cp["records"], cp["issues"], cp["quality"]):
        raise ValueError("Saved checkpoint differs from fixed-version raw replay")
    return parsed


def export(job_dir):
    job = Path(job_dir).resolve()
    if job.parent != (ROOT / "data/raw").resolve():
        raise ValueError("Invalid job directory")
    protocol = read_project_json(job / 'protocol.json')
    plan = read_project_json(job / 'plan.json')
    out = ROOT / "data/processed" / job.name
    out.mkdir(exist_ok=True)
    rows, issues, quality, snapshots = [], [], [], {}
    refresh_rows, new_rows, refresh_quality = [], [], []
    sources = []
    for query in plan:
        p = job / "checkpoints" / (query["query_id"] + ".json")
        if not p.exists():
            quality.append(dict(query_id=query["query_id"], role=query["role"], primary_query_id=query["primary_query_id"],
                                date=query["date"], from_city=query["from_city"], to_city=query["to_city"], status="not_collected",
                                raw_count="", valid_count="", unavailable_count="", unresolved_station_count=""))
            continue
        cp = read_project_json(p)
        assert all(cp["query"][k] == v for k, v in query.items())
        parsed, parsed_issues, q = verify_checkpoint(cp, snapshots)
        rows.extend(parsed)
        issues.extend(parsed_issues)
        quality.append(dict(query_id=query["query_id"], role=query["role"], primary_query_id=query["primary_query_id"],
                            date=query["date"], from_city=query["from_city"], to_city=query["to_city"], status=q["status"],
                            raw_count=q["raw_count"], valid_count=q["valid_count"], unavailable_count=q["unavailable_count"],
                            unresolved_station_count=q.get("unresolved_station_count", 0)))
        sources.append(dict(query_id=query["query_id"], role=query["role"], query_date=query["date"],
                            source_accessed_at=cp["source"]["accessed_at"], raw_file=cp["source"]["raw_file"], sha256=cp["source"]["sha256"]))
        if query["role"] == "refresh_primary_unknown":
            refresh_rows.extend(parsed)
            old = read_project_json(ROOT / 'data/raw' / PRIMARY / 'checkpoints' / (query['primary_query_id'] + '.json'))
            refresh_quality.append(dict(primary_query_id=query["primary_query_id"], from_city=query["from_city"], to_city=query["to_city"],
                                        before_valid=old["quality"]["valid_count"], after_valid=q["valid_count"],
                                        before_unknown_time=old["quality"]["unavailable_count"], after_unknown_time=q["unavailable_count"],
                                        before_unresolved_station=old["quality"].get("unresolved_station_count", 0),
                                        after_unresolved_station=q.get("unresolved_station_count", 0),
                                        original_source_accessed_at=old["source"]["accessed_at"], refreshed_at=cp["source"]["accessed_at"]))
        else:
            new_rows.extend(parsed)
    write_csv(out / "supplement_train_records.csv", rows, TRAIN_FIELDS)
    write_csv(out / "refreshed_primary_records.csv", refresh_rows, TRAIN_FIELDS)
    write_csv(out / "later_date_records.csv", new_rows, TRAIN_FIELDS)
    write_csv(out / "supplement_query_quality.csv", quality, QUALITY_FIELDS)
    write_csv(out / "cleaning_issues.csv", issues, ISSUE_FIELDS)
    write_csv(out / "source_register.csv", sources, ["query_id", "role", "query_date", "source_accessed_at", "raw_file", "sha256"])
    refresh_fields = ["primary_query_id", "from_city", "to_city", "before_valid", "after_valid", "before_unknown_time", "after_unknown_time", "before_unresolved_station", "after_unresolved_station", "original_source_accessed_at", "refreshed_at"]
    write_csv(out / "refresh_comparison.csv", refresh_quality, refresh_fields)
    finished = [q for q in quality if q["status"] != "not_collected"]
    summary = dict(actor=read_project_json(job / 'metadata.json')["actor"], primary_run=PRIMARY,
                   completed_queries=len(finished), total_queries=len(plan), remaining_queries=len(plan)-len(finished),
                   train_records=len(rows), later_date_records=len(new_rows), refreshed_valid_records=len(refresh_rows),
                   unavailable_timetable_records=sum(int(q["unavailable_count"]) for q in finished),
                   unresolved_station_records=sum(int(q["unresolved_station_count"]) for q in finished),
                   completed_refresh_queries=len(refresh_quality), completed_later_date_queries=sum(q["role"] == "followup_date" for q in finished),
                   blocking_error=read_project_json(job / 'blocked.json') if (job / "blocked.json").exists() else None,
                   source_deadline=protocol["snapshot_deadline_exclusive"], output_dir=str(out), job_dir=str(job), matrix_ready=False,
                   merge_policy="No automatic replacement or union into primary: query refreshes and later-date rows are separate until source/time consistency audit")
    write_json(out / "supplement_summary.json", summary)
    return summary


def _check_time(plan, protocol):
    current = datetime.now(TZ)
    if current >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
        raise ValueError("48-hour primary snapshot span ended. Do not change timestamps or silently extend; retain data and review snapshot policy.")
    for q in plan:
        if not 0 <= (date.fromisoformat(q["date"])-current.date()).days < 15:
            raise ValueError("A frozen query day is outside the typical 15-day window; do not silently redate")


def collect(actor="user", max_queries=None):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    plan, protocol = plan_followups()
    _check_time(plan, protocol)
    if max_queries is None:
        max_queries = len(plan)
    if not isinstance(max_queries, int) or not 0 <= max_queries <= len(plan):
        raise ValueError("max_queries must be an integer within this plan length")
    if MARKER.exists():
        marker = read_project_json(MARKER)
        job = Path(marker["job_dir"]).resolve()
        if job.parent != (ROOT / "data/raw").resolve():
            raise ValueError("Invalid checkpoint job pointer")
        if read_project_json(job / 'protocol.json') != protocol or read_project_json(job / 'plan.json') != plan:
            raise ValueError("Frozen supplement plan changed; review a separate dataset version")
        meta = read_project_json(job / 'metadata.json')
        if meta["actor"] != actor or any(not script_hash_matches(ROOT / 'scripts' / n, h) for n,h in meta["code_hashes"].items()):
            raise ValueError("Collector actor or code version changed")
        if (job / "blocked.json").exists():
            raise ValueError("A saved blocking error needs review; no automatic retry")
    else:
        job = ROOT / "data/raw" / (actor + "_stage1e_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
        job.mkdir(exist_ok=False); (job / "checkpoints").mkdir(); (job / "sessions").mkdir()
        write_json(job / "protocol.json", protocol)
        write_json(job / "plan.json", plan)
        for n in CODE_FILES:
            (job / n).write_bytes((ROOT / "scripts" / n).read_bytes())
        write_json(job / "metadata.json", dict(actor=actor, created_at=now(), parser_version=PARSER_VERSION,
                                               software=software_versions(), code_hashes={n:sha(ROOT/"scripts"/n) for n in CODE_FILES}))
        atomic_json(MARKER, dict(job_dir=str(job)))
    remaining = [q for q in plan if not (job / "checkpoints" / (q["query_id"] + ".json")).exists()]
    print("补采目录：", job, flush=True)
    if not remaining or not max_queries:
        return export(job)
    lock = job / "running.lock"
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(now())
    session = job / "sessions" / datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f")
    session.mkdir(exist_ok=False)
    client = SourceClient(session, actor, 3)
    current_query, count = "initialization", 0
    try:
        page, _ = client.get("query_page", INIT_URL)
        endpoint = re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]", page)
        station_link = re.search(r'src=["\']([^"\']*/station_name\.js[^"\']*)', page)
        field_link = re.search(r'src=["\']([^"\']*/queryLeftTicket_end_js\.js[^"\']*)', page)
        if not endpoint or not station_link or not field_link:
            raise SourceError("Official source metadata unavailable; no endpoint guessing")
        urls = [urljoin(INIT_URL, m.group(1)) for m in (station_link, field_link)]
        if any(urlparse(u).netloc != "kyfw.12306.cn" for u in urls):
            raise SourceError("Unexpected official metadata host")
        text, station_source = client.get("station_dictionary", urls[0])
        stations = parse_station_dictionary(text)
        by_name = {s["station_name"]:s for s in stations}; by_code={s["station_code"]:s for s in stations}
        js, _ = client.get("official_field_mapping", urls[1]); verify_client_field_map(js)
        for q in remaining[:max_queries]:
            current_query=q["query_id"]
            if datetime.now(TZ) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
                raise SourceError("Primary 48-hour snapshot deadline reached; remaining queries stopped")
            if q["from_station"] not in by_name or q["to_station"] not in by_name:
                raise SourceError("Planned station absent from current source dictionary")
            query=dict(q, from_code=by_name[q["from_station"]]["station_code"], to_code=by_name[q["to_station"]]["station_code"])
            body, source = client.get(current_query,urljoin(BASE,endpoint.group(1)),{
                "leftTicketDTO.train_date":q["date"],"leftTicketDTO.from_station":query["from_code"],
                "leftTicketDTO.to_station":query["to_code"],"purpose_codes":"ADULT"})
            if datetime.fromisoformat(source["accessed_at"]) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
                raise SourceError("Request began after snapshot deadline; raw response kept but not added to checkpoints")
            records, issues, quality = parse_train_response(body, query, by_code, source)
            cp=dict(query=query,source=source,station_snapshot=station_source,records=records,issues=issues,quality=quality,parser_version=PARSER_VERSION)
            if quality["status"] not in ACCEPTED:
                write_json(session/(current_query+"_quarantined.json"),cp)
                raise SourceError("Unexpected records need review; source and details saved")
            atomic_json(job/"checkpoints"/(current_query+".json"),cp)
            count+=1
            if count<=4 or count%25==0 or count==len(remaining[:max_queries]):
                print(f"{len(plan)-len(remaining)+count}/{len(plan)} {q['date']} {q['from_city']}→{q['to_city']}: {quality['status']}; valid={quality['valid_count']}",flush=True)
        atomic_json(job/"last_progress.json",dict(at=now(),completed_now=count,interrupted=False))
    except KeyboardInterrupt:
        atomic_json(job/"last_progress.json",dict(at=now(),completed_now=count,interrupted=True,query_id=current_query))
        print("已保存完成的请求；正常中断后可再次运行本段续采。",flush=True)
    except SourceError as error:
        atomic_json(job/"blocked.json",dict(at=now(),query_id=current_query,error=str(error),automatic_retry=False))
        print("补采暂停：",str(error),flush=True)
    finally:
        client.close(); lock.unlink()
    return export(job)
