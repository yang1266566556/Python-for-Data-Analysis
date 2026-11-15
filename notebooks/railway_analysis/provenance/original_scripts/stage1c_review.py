"""Offline review of the completed user pilot; no new network or imputation."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from stage1_collect import ROOT, TZ, TRAIN_FIELDS, parse_station_dictionary, parse_train_response, write_csv, write_json
from stage1b_transfer import read_csv, load_verified_parent, build_pairs

RUN = "user_stage1b_20261105_234442_790924"


def conservative_bound(missing_day, latest_first_departure):
    """Earliest possible second departure minus latest actual first departure.

    Assume zero second-leg duration to make the bound deliberately optimistic.
    No use of unknown clock or duration. Applies only to this fixed first-leg set.
    """
    earliest = datetime.fromisoformat(missing_day + "T00:00:00+08:00")
    return max(0, (earliest - latest_first_departure).total_seconds() / 60)


def review(actor="user"):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    raw = ROOT / "data/raw" / RUN
    processed = ROOT / "data/processed" / RUN
    config = json.loads((raw / "stage1b_protocol.json").read_text(encoding="utf-8"))
    first_run, _, _, _ = load_verified_parent(config)
    manifest = json.loads((raw / "source_manifest.json").read_text(encoding="utf-8"))
    entries = {e["source_id"]: e for e in manifest}
    for e in manifest:
        if hashlib.sha256((ROOT / e["raw_file"]).read_bytes()).hexdigest() != e["sha256"]:
            raise ValueError("Original response hash mismatch")
    stations = parse_station_dictionary((ROOT / entries["station_dictionary"]["raw_file"]).read_text(encoding="utf-8"))
    station_map = {s["station_code"]: s for s in stations}
    rows, missing = [], []
    for q in read_csv(processed / "new_query_quality.csv"):
        e = entries[q["query_id"]]
        query = dict(q, from_code=e["params"]["leftTicketDTO.from_station"], to_code=e["params"]["leftTicketDTO.to_station"])
        parsed, issues, quality = parse_train_response((ROOT / e["raw_file"]).read_text(encoding="utf-8"), query, station_map, e)
        assert quality["rejected_count"] == 0
        assert quality["valid_count"] == int(q["valid_count"])
        rows.extend(parsed)
        missing.extend(dict(json.loads(i["details"]), query_id=q["query_id"]) for i in issues if i["issue"] == "timetable_unavailable_adjustment")
    normalized = [{k: str(r[k]) for k in TRAIN_FIELDS} for r in rows]
    assert normalized == read_csv(processed / "new_train_records.csv"), "CSV differs from authentic saved payloads"
    first = [r for r in first_run if r["query_id"] == "P05" and r["from_dictionary_city"] == "北京" and r["to_name"] == "西宁"]
    second = [r for r in first_run if r["query_id"] == "P06"] + [r for r in rows if r["query_id"].startswith("X")]
    pairs = build_pairs(first, second, config)
    assert [{k: str(v) for k, v in r.items()} for r in pairs] == read_csv(processed / "all_same_station_pairs.csv")
    latest_first = max(datetime.fromisoformat(r["departure_at"]) for r in first)
    proof_rows = []
    for m in missing:
        proof_rows.append(dict(train_code=m["train_code"], query_date=m["query_date"],
                               latest_first_departure=latest_first.isoformat(),
                               lower_bound_min=conservative_bound(m["query_date"], latest_first),
                               actual_time_known=False, raw_file=m["raw_file"]))
    scenarios = []
    for threshold in (30, 60, 90):
        valid = [p for p in pairs if p["classification"] == "time_ordered_transfer_candidate" and p["wait_min"] >= threshold]
        best = min(valid, key=lambda p: (p["total_min"], p["departure_at"], p["first_train"], p["second_train"])) if valid else None
        bounded = best is not None and all(p["lower_bound_min"] > best["total_min"] for p in proof_rows)
        scenarios.append(dict(
            threshold_min=threshold, known_candidate_count=len(valid),
            known_subset_min_min=best["total_min"] if best else "",
            named_missing_rows_cannot_improve=bounded,
            minimum_missing_lower_bound_min=min((p["lower_bound_min"] for p in proof_rows), default=""),
            first_train=best["first_train"] if best else "", second_train=best["second_train"] if best else "",
            from_station=best["from_station"] if best else "", wait_min=best["wait_min"] if best else "",
            departure_at=best["departure_at"] if best else "", arrival_at=best["arrival_at"] if best else "",
            scope="only saved first legs and two distinct train services via Xining; not all-network optimality",
            actual_transfer_verified=False,
        ))
    endpoint_summary = []
    for qid in ("A01", "A02", "A03"):
        group = [r for r in rows if r["query_id"] == qid]
        endpoint_summary.append(dict(query_id=qid, returned_records=len(group),
                                     exact_requested_endpoints=sum(r["same_as_requested_stations"] for r in group),
                                     other_endpoints=sum(not r["same_as_requested_stations"] for r in group)))
    endpoint_pairs = [dict(query_id=qid, from_station=a, to_station=b, count=n)
                      for (qid, a, b), n in Counter((r["query_id"], r["from_name"], r["to_name"]) for r in rows if r["query_id"].startswith("A")).items()]
    # An actual-station example; not a route through all returned city-equivalent stations.
    access_first = [r for r in rows if r["query_id"] == "A01" and r["from_name"] == "广州南" and r["to_name"] == "珠海"]
    access_second = [r for r in rows if r["query_id"] == "A02" and r["from_name"] == "珠海" and r["to_name"] == "横琴"]
    access_pairs = build_pairs(access_first, access_second, config)
    access_scenarios = []
    for threshold in (30, 60, 90):
        valid = [r for r in access_pairs if r["classification"] == "time_ordered_transfer_candidate" and r["wait_min"] >= threshold]
        best = min(valid, key=lambda r: (r["total_min"], r["departure_at"])) if valid else None
        access_scenarios.append(dict(threshold_min=threshold, known_candidate_count=len(valid),
                                     known_subset_min_min=best["total_min"] if best else "",
                                     first_train=best["first_train"] if best else "", second_train=best["second_train"] if best else "",
                                     wait_min=best["wait_min"] if best else "", scope="same-day Guangzhou South-Zhuhai-Hengqin records; not Macau"))
    out = ROOT / "data/processed" / (actor + "_offline_review_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    for name, data in [("bounded_transfer_scenarios", scenarios), ("missing_time_lower_bounds", proof_rows),
                       ("access_endpoint_quality", endpoint_summary), ("actual_access_station_pairs", endpoint_pairs),
                       ("access_transfer_scenarios", access_scenarios)]:
        write_csv(out / (name + ".csv"), data, list(data[0]))
    summary = dict(actor=actor, reviewed_run=RUN, original_hashes_verified=len(manifest),
                   validated_records=len(rows), missing_records=len(missing), paired_records_verified=len(pairs),
                   missing_times_still_unknown=True, matrix_ready=False, output_dir=str(out),
                   provenance="offline computation from original user data; execution actor explicitly recorded")
    write_json(out / "review_summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", choices=["user", "assistant"], default="user")
    print(json.dumps(review(parser.parse_args().actor), ensure_ascii=False, indent=2))
