"""Reviewed recovery of the existing user run; preserves original blocked job.

Only exact 'station code absent from saved dictionary' issues are reclassified as
unresolved station metadata. They remain excluded from valid train records.
Never invent station identity from a conflicting/absent response dictionary.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import stage1_collect as base
import stage1c_collect as engine
from stage1b_transfer import read_csv

ROOT = base.ROOT
PARENT_ID = "user_stage1c_20261111_212830_965817"
_original_parse = base.parse_train_response
_original_export = engine.export_job


def reviewed_parse(body, query, station_map, source):
    rows, issues, quality = _original_parse(body, query, station_map, source)
    response = json.loads(body)
    unresolved = 0
    revised = []
    for issue in issues:
        if (issue["issue"] == "record_quarantined"
                and issue["details"].startswith("station code absent from saved dictionary: ")):
            index = int(issue["raw_row_index"])
            raw = response["data"]["result"][index]
            fields = raw.split("|")
            missing_codes = [code for code in fields[6:8] if code not in station_map]
            # Run the unchanged parser with station identity supplied solely to check
            # all remaining fields. This temporary map never creates valid records.
            temporary = dict(station_map)
            for code in missing_codes:
                temporary[code] = dict(station_name=response["data"].get("map", {}).get(code, "UNKNOWN"),
                                       source_city_name="", source_city_code="", station_code=code, pinyin="")
            one = dict(response, data=dict(response["data"], result=[raw]))
            _, remaining_issues, remaining_quality = _original_parse(json.dumps(one, ensure_ascii=False), query, temporary, source)
            if remaining_quality["rejected_count"] or remaining_quality["unavailable_count"] or remaining_issues:
                revised.append(issue)
                continue
            unresolved += 1
            revised.append(dict(issue, severity="missing_data", issue="station_metadata_unresolved",
                                details=json.dumps(dict(
                                    missing_station_codes=missing_codes, train_code=fields[3],
                                    raw_from_code=fields[6], raw_to_code=fields[7],
                                    response_map_labels={code: response["data"].get("map", {}).get(code) for code in missing_codes},
                                    raw_file=source["raw_file"], raw_sha256=source["sha256"],
                                    treatment="preserved in raw response; excluded from valid records and minima; no inferred identity"),
                                    ensure_ascii=False)))
        else:
            revised.append(issue)
    if unresolved:
        quality = dict(quality, rejected_count=quality["rejected_count"] - unresolved,
                       unresolved_station_count=unresolved)
        if quality["rejected_count"] == 0:
            quality["status"] = "partial_station_metadata_unresolved"
    return rows, revised, quality


def reviewed_export(job_dir):
    summary = _original_export(job_dir)
    job = Path(job_dir)
    out = Path(summary["output_dir"])
    unresolved, affected = [], set()
    for cp_path in (job / "checkpoints").glob("*.json"):
        cp = json.loads(cp_path.read_text(encoding="utf-8"))
        for issue in cp["issues"]:
            if issue["issue"] == "station_metadata_unresolved":
                data = json.loads(issue["details"])
                unresolved.append(dict(query_id=issue["query_id"], raw_row_index=issue["raw_row_index"],
                                       details=json.dumps(data, ensure_ascii=False)))
                affected.add(issue["query_id"])
    base.write_csv(out / "unresolved_station_records.csv", unresolved, ["query_id", "raw_row_index", "details"])
    direct_path = out / "direct_screen_34x34_long.csv"
    direct = read_csv(direct_path)
    for row in direct:
        if row["from_node"] + "_" + row["to_node"] in affected:
            row["status"] += "_with_unresolved_station_metadata"
    base.write_csv(direct_path, direct, list(direct[0]))
    summary["unresolved_station_record_count"] = len(unresolved)
    summary["recovery_policy"] = "unverified station records excluded and retained for review"
    base.write_json(out / "collection_summary.json", summary)
    return summary


def install_policy():
    engine.parse_train_response = reviewed_parse
    engine.export_job = reviewed_export
    engine.GOOD_STATES = engine.GOOD_STATES | {"partial_station_metadata_unresolved"}


def prepare_recovery():
    """New checkpoint branch; no mutations to original responses or blocked state."""
    parent = ROOT / "data/raw" / PARENT_ID
    marker = ROOT / "evidence/stage1c_recovery_current.json"
    adapter_hash = engine.digest(Path(__file__))
    if marker.exists():
        previous = json.loads(marker.read_text(encoding="utf-8"))
        if previous["adapter_sha256"] != adapter_hash:
            raise ValueError("Recovery adapter changed; review before resuming")
        job = Path(previous["job_dir"])
        if job.parent.resolve() != (ROOT / "data/raw").resolve() or not job.is_dir():
            raise ValueError("Invalid recovery directory")
        return job
    metadata = json.loads((parent / "job_metadata.json").read_text(encoding="utf-8"))
    for name, expected in metadata["code_hashes"].items():
        if engine.digest(ROOT / "scripts" / name) != expected:
            raise ValueError("Underlying collector changed; review compatibility first")
    install_policy()
    checkpoints = sorted((parent / "checkpoints").glob("*.json"))
    for path in checkpoints:
        engine.checkpoint_valid(parent, json.loads(path.read_text(encoding="utf-8")))
    blocked = json.loads((parent / "blocked.json").read_text(encoding="utf-8"))
    if blocked["query_id"] != "N07_N06":
        raise ValueError("Unexpected blocked query; automatic reviewed recovery not applicable")
    quarantined_files = list((parent / "sessions").glob("*/N07_N06_quarantined.json"))
    if len(quarantined_files) != 1:
        raise ValueError("Expected exactly one saved quarantined response")
    cp = json.loads(quarantined_files[0].read_text(encoding="utf-8"))
    engine.checkpoint_valid(parent, cp)
    station_source = cp["station_snapshot"]
    stations = base.parse_station_dictionary((ROOT / station_source["raw_file"]).read_text(encoding="utf-8"))
    station_map = {s["station_code"]: s for s in stations}
    records, issues, quality = reviewed_parse((ROOT / cp["source"]["raw_file"]).read_text(encoding="utf-8"), cp["query"], station_map, cp["source"])
    if quality["rejected_count"] or quality.get("unresolved_station_count") != 2 or len(records) != 137:
        raise ValueError("Saved query differs from the reviewed case; stopped for inspection")
    job = ROOT / "data/raw" / ("user_stage1c_" + datetime.now(base.TZ).strftime("%Y%m%d_%H%M%S_%f") + "_reviewed")
    job.mkdir(exist_ok=False)
    (job / "checkpoints").mkdir()
    (job / "sessions").mkdir()
    for name in ["protocol.json", "plan.json", "nodes.csv", "candidate_stations.csv", "job_metadata.json", *metadata["code_hashes"]]:
        (job / name).write_bytes((parent / name).read_bytes())
    for path in checkpoints:
        (job / "checkpoints" / path.name).write_bytes(path.read_bytes())
    cp.update(records=records, issues=issues, quality=quality)
    base.write_json(job / "checkpoints/N07_N06.json", cp)
    (job / "stage1c_recovery.py").write_bytes(Path(__file__).read_bytes())
    base.write_json(job / "recovery_review.json", dict(
        prepared_by="assistant", parent_job=PARENT_ID, prepared_at=base.now(),
        original_blocked_state=blocked, original_job_unchanged=True,
        original_completed_queries=len(checkpoints), additional_saved_query_reprocessed="N07_N06",
        unknown_rows=2, reason="missing station dictionary code TAI; response name ambiguous, no identity inferred",
        adapter_sha256=adapter_hash, original_collection_start_retained=metadata["started_at"]))
    engine.atomic_json(marker, dict(job_dir=str(job), adapter_sha256=adapter_hash))
    return job


def collect_recovered(max_queries=995):
    install_policy()
    job = prepare_recovery()
    summary = engine.collect(actor="user", job_dir=str(job), max_queries=max_queries)
    return summary


def inspect_saved_recovery():
    install_policy()
    return reviewed_export(prepare_recovery())
