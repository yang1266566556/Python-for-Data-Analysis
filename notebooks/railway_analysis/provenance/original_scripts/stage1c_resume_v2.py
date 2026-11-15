"""Replay and migrate authentic saved checkpoints to an explicit parser version.

No network during migration. Keep old jobs, blocked files and responses intact.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import stage1_collect as base
import stage1c_collect_v2 as engine
from stage1c_parser_v2 import parse_train_response, PARSER_VERSION

ROOT = base.ROOT
SOURCE_JOB = "user_stage1c_20261113_123705_523939_reviewed"
MARKER = ROOT / "evidence/stage1c_v2_current.json"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    if MARKER.exists():
        info = json.loads(MARKER.read_text(encoding="utf-8"))
        job = Path(info["job_dir"]).resolve()
        if job.parent != (ROOT / "data/raw").resolve() or info["parser_version"] != PARSER_VERSION:
            raise ValueError("Invalid fixed-version recovery pointer")
        return job
    source = ROOT / "data/raw" / SOURCE_JOB
    if (source / "running.lock").exists():
        raise ValueError("Old job may still be running; do not migrate concurrently")
    blocked = json.loads((source / "blocked.json").read_text(encoding="utf-8"))
    if blocked["query_id"] != "N22_N24":
        raise ValueError("Unexpected blocked query requires review")
    metadata = json.loads((source / "job_metadata.json").read_text(encoding="utf-8"))
    before_hash = _sha(source / "blocked.json")
    files = sorted((source / "checkpoints").glob("*.json"))
    quarantines = list((source / "sessions").glob("*/N22_N24_quarantined.json"))
    if len(quarantines) != 1:
        raise ValueError("Expected one saved N22_N24 response")
    replayed, changes, stations = [], [], {}
    for path in files + quarantines:
        old = json.loads(path.read_text(encoding="utf-8"))
        raw = ROOT / old["source"]["raw_file"]
        station = ROOT / old["station_snapshot"]["raw_file"]
        if _sha(raw) != old["source"]["sha256"] or _sha(station) != old["station_snapshot"]["sha256"]:
            raise ValueError("Original response or station snapshot modified")
        if str(station) not in stations:
            stations[str(station)] = {s["station_code"]: s for s in base.parse_station_dictionary(station.read_text(encoding="utf-8"))}
        text = raw.read_text(encoding="utf-8")
        rows, issues, quality = parse_train_response(text, old["query"], stations[str(station)], old["source"])
        if quality["rejected_count"]:
            raise ValueError("Unreviewed data errors in " + old["query"]["query_id"])
        if rows != old["records"]:
            raise ValueError("Previously accepted train records changed unexpectedly")
        legacy_rows, legacy_issues, legacy_q = base.parse_train_response(text, old["query"], stations[str(station)], old["source"])
        known_policy = (old["quality"] == quality and old["issues"] == issues)
        legacy_policy = (old["quality"] == legacy_q and old["issues"] == legacy_issues and old["records"] == legacy_rows)
        if not (known_policy or legacy_policy):
            raise ValueError("Stored checkpoint cannot be accounted for by legacy or reviewed parser")
        migrated = dict(old, records=rows, issues=issues, quality=quality, parser_version=PARSER_VERSION)
        replayed.append(migrated)
        if quality != old["quality"] or issues != old["issues"]:
            changes.append(dict(query_id=old["query"]["query_id"], old_quality=old["quality"], reviewed_quality=quality,
                                valid_records_unchanged=True, source_checkpoint=str(path.relative_to(ROOT))))
    if len({c["query"]["query_id"] for c in replayed}) != len(replayed):
        raise ValueError("Duplicate query snapshots need explicit review")
    job = ROOT / "data/raw" / ("user_stage1c_v2_" + datetime.now(base.TZ).strftime("%Y%m%d_%H%M%S_%f"))
    job.mkdir(exist_ok=False)
    (job / "checkpoints").mkdir()
    (job / "sessions").mkdir()
    for name in ("protocol.json", "plan.json", "nodes.csv", "candidate_stations.csv"):
        (job / name).write_bytes((source / name).read_bytes())
    code_hashes = {}
    for name in ("stage1c_collect_v2.py", "stage1c_parser_v2.py", "stage1_collect.py", "stage1b_transfer.py"):
        (job / name).write_bytes((ROOT / "scripts" / name).read_bytes())
        code_hashes[name] = _sha(ROOT / "scripts" / name)
    new_metadata = dict(metadata, code_hashes=code_hashes, parser_version=PARSER_VERSION,
                        migration_actor="assistant", migrated_at=base.now(), source_job=SOURCE_JOB,
                        original_started_at_preserved=True)
    base.write_json(job / "job_metadata.json", new_metadata)
    for checkpoint in replayed:
        base.write_json(job / "checkpoints" / (checkpoint["query"]["query_id"] + ".json"), checkpoint)
    audit = dict(migration_actor="assistant", source_job=SOURCE_JOB, prepared_at=base.now(),
                 completed_source_checkpoints=len(files), saved_quarantined_queries_replayed=len(quarantines),
                 migrated_checkpoints=len(replayed), source_records_retained=True, original_blocked_file_preserved=True,
                 changed_quality_records=changes, parser_version=PARSER_VERSION,
                 new_network_queries=0, original_started_at=metadata["started_at"], job_dir=str(job))
    base.write_json(job / "migration_audit.json", audit)
    summary = engine.export_job(job)
    assert _sha(source / "blocked.json") == before_hash
    engine.atomic_json(MARKER, dict(job_dir=str(job), parser_version=PARSER_VERSION))
    base.write_json(ROOT / "evidence/stage1c_v2_migration_audit.json", dict(audit, summary=summary))
    return job


def inspect_saved():
    return engine.export_job(prepare())


def collect(max_queries=995):
    return engine.collect(actor="user", job_dir=str(prepare()), max_queries=max_queries)
