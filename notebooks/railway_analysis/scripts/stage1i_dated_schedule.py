"""Validate user H outputs and request three explicit-date cumulative timetables.

Clock-only stop tables never supply an inferred day rollover. This module does
not change a matrix: dated cumulative times are checked and saved for review.
"""

from railway_project_io import read_project_json
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

from stage1_collect import ROOT, TZ, BASE, SourceClient, SourceError, write_csv, write_json, software_versions
from stage1b_transfer import read_csv
from stage1h_matrix import verified_input, matrix_diagnostics
from stage1h_stop_table_probe import probe_plan, inspect_body, STOP_FIELDS

H_JOB = "user_stage1h_matrix_20261113_155821_569495"
STOP_JOB = "user_stop_table_probe_20261113_160214_460368"
PRIMARY = "user_stage1c_v2_20261113_132207_325427"
MARKER = ROOT / "evidence/stage1i_current_job.json"
DETAIL_FIELDS = ["probe_id", "train_code", "requested_date", "station_name", "station_no",
                 "start_time", "arrive_time", "running_time", "arrive_day_str",
                 "published_elapsed_min", "published_arrival_at", "date_evidence", "raw_fields_json"]
QUALITY_FIELDS = ["probe_id", "train_code", "requested_date", "returned_stops",
                  "clock_tables_match", "dated_cumulative_validation_passed",
                  "lhasa_start", "xining_arrival", "lhasa_xining_min", "assessment", "raw_file", "sha256"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def authenticated_manifest(directory):
    entries = read_project_json(directory / 'source_manifest.json')
    by_id = {}
    for item in entries:
        if item["source_id"] in by_id:
            raise ValueError("Duplicate source ID")
        if "error" in item or item.get("http_status") != 200:
            raise ValueError("Source collection has an error; no silent retry")
        if urlparse(item["url"]).netloc != "kyfw.12306.cn":
            raise ValueError("Unexpected timetable source host")
        if sha(ROOT / item["raw_file"]) != item["sha256"]:
            raise ValueError("Raw response hash mismatch")
        by_id[item["source_id"]] = item
    return by_id


def prior_stop_evidence():
    directory = ROOT / "data/raw" / STOP_JOB
    sources = authenticated_manifest(directory)
    plans = read_project_json(directory / 'probe_plan.json')
    if plans != probe_plan():
        raise ValueError("Saved probe plan differs from authentic primary records")
    parsed = []
    stops = {}
    for plan in plans:
        source = sources[plan["probe_id"]]
        expected = dict(train_no=plan["train_no"], from_station_telecode=plan["from_code"],
                        to_station_telecode=plan["to_code"], depart_date=plan["requested_date"])
        if source["params"] != expected:
            raise ValueError("Saved stop-table date/service request differs")
        body = (ROOT / source["raw_file"]).read_text(encoding="utf-8")
        rows, result = inspect_body(body, plan)
        if not result["lhasa_and_xining_clocks_present"]:
            raise ValueError("Three complete clock-table candidates expected")
        parsed.extend(rows)
        stops[plan["probe_id"]] = json.loads(body)["data"]["data"]
    saved = read_csv(ROOT / "data/processed" / STOP_JOB / "stop_table_rows.csv")
    if [{k: str(row[k]) for k in STOP_FIELDS} for row in parsed] != saved:
        raise ValueError("Stop-table CSV differs from raw response replay")
    return plans, stops, sources


def audit_h(actor="user"):
    import numpy as np
    import pandas as pd
    rows, info = verified_input()
    directory = ROOT / "data/processed" / H_JOB
    summary = read_project_json(directory / 'matrix_freeze_summary.json')
    if info != summary["input"]:
        raise ValueError("H result refers to different authenticated data")
    saved = read_csv(directory / "known_train_records_with_sources.csv")
    if [{k: str(v) for k, v in row.items()} for row in rows] != saved:
        raise ValueError("H source records differ from raw replay")
    raw = pd.read_csv(directory / "raw_directed_time_34.csv", index_col=0, encoding="utf-8-sig")
    subset = pd.read_csv(directory / "comparison_subset_directed_minutes.csv", index_col=0, encoding="utf-8-sig")
    sym = pd.read_csv(directory / "comparison_subset_symmetric_mean_minutes.csv", index_col=0, encoding="utf-8-sig")
    expected, diagnostics = matrix_diagnostics(subset.to_numpy())
    if not (raw.shape == (34, 34) and list(raw.index) == list(raw.columns)
            and np.allclose(np.diag(raw.to_numpy()), 0) and np.allclose(expected, sym.to_numpy())):
        raise ValueError("H matrix identity/diagonal/symmetrization validation failed")
    if diagnostics != read_project_json(directory / 'subset_matrix_diagnostics.json'):
        raise ValueError("H matrix diagnostics differ from saved matrix")
    plans, stops, sources = prior_stop_evidence()
    witnesses = []
    for plan in plans:
        same = [row for row in rows if row["train_no"] == plan["train_no"]]
        clocks = {s["station_name"]: s for s in stops[plan["probe_id"]]}
        for row in same:
            if row["from_name"] not in clocks or row["to_name"] not in clocks:
                raise ValueError("Historical witness is outside the returned stop list")
            match = (row["departure_clock"] == clocks[row["from_name"]]["start_time"]
                     and row["arrival_clock"] == clocks[row["to_name"]]["arrive_time"])
            if not match:
                raise ValueError("Historical service clocks conflict; review before any use")
            witnesses.append(dict(train_code=plan["train_code"], witness_origin_date=row["origin_service_date"],
                                  requested_origin_date=plan["requested_date"], from_name=row["from_name"], to_name=row["to_name"],
                                  clocks_match=match, proves_nov18_day_offset=False, raw_file=row["raw_file"]))
    out = ROOT / "data/processed" / (actor + "_stage1i_source_audit_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    write_csv(out / "historical_clock_witnesses.csv", witnesses, list(witnesses[0]))
    result = dict(actor=actor, h_raw_replay_passed=True, combined_records=len(rows), stop_requests_verified=len(plans),
                  returned_stop_rows=sum(map(len, stops.values())), historical_clock_witnesses=len(witnesses),
                  all_historical_clocks_match=True, original34_missing=int(raw.isna().sum().sum()),
                  direct_fill_permitted=False, full34_algorithm_ready=False, output_dir=str(out),
                  note="Older origin dates provide clock corroboration only, not evidence for Nov18 day offsets. No matrix was modified.")
    write_json(out / "source_audit_summary.json", result)
    return result


def clock_minutes(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("Expected a published 00:00..23:59 clock")
    hh, mm = map(int, value.split(":"))
    return hh * 60 + mm


def elapsed_minutes(value):
    """Recognize explicit source durations; never treat a clock as a day offset."""
    value = str(value).strip()
    match = re.fullmatch(r"(\d{1,3}):([0-5]\d)", value)
    if match:
        return int(match[1]) * 60 + int(match[2])
    match = re.fullmatch(r"(?:(\d+)天)?(?:(\d+)小时)?(?:(\d+)分(?:钟)?)?", value)
    if match and any(x is not None for x in match.groups()):
        d, h, m = (int(x or 0) for x in match.groups())
        if m >= 60:
            raise ValueError("Unsupported duration minutes")
        return d * 1440 + h * 60 + m
    raise ValueError("Unrecognized published running_time; no inferred rollover")


def published_day(value):
    value = str(value).strip()
    known = {"当日": 0, "当日到达": 0, "当天": 0, "次日": 1, "次日到达": 1}
    if value in known:
        return known[value]
    match = re.fullmatch(r"第([一二三四五六七八九十]|\d+)[日天](?:到达)?", value)
    if match:
        chinese = dict(zip("一二三四五六七八九十", range(1, 11)))
        n = chinese.get(match[1], int(match[1]) if match[1].isdigit() else -1)
        if n > 0:
            return n - 1
    raise ValueError("Unrecognized published arrive_day_str")


def validate_full_table(body, plan, previous):
    obj = json.loads(body)
    outer = obj.get("data")
    if obj.get("status") is not True or not isinstance(outer, dict) or outer.get("message"):
        raise ValueError("Official dated timetable rejected the request or requires verification")
    rows = outer.get("data")
    if not isinstance(rows, list) or len(rows) != len(previous) or not all(isinstance(x, dict) for x in rows):
        raise ValueError("Dated table stop schema/count differs; preserve raw source for review")
    if rows[0].get("station_name") != "拉萨" or rows[0].get("station_train_code") != plan["train_code"]:
        raise ValueError("Dated table origin/service does not match saved authentic service")
    for index, (old, new) in enumerate(zip(previous, rows)):
        # An origin has no arrival and a terminal has no departure. The two
        # official endpoints can use different placeholders for those fields.
        keys = ["station_name"]
        if index < len(rows) - 1:
            keys.append("start_time")
        if index > 0:
            keys.append("arrive_time")
        for key in keys:
            if old.get(key) != new.get(key):
                raise ValueError("Dated table and clock-only table disagree at " + str(new.get("station_name")))
    origin = datetime.fromisoformat(plan["requested_date"] + "T" + rows[0]["start_time"] + ":00+08:00")
    origin_clock = clock_minutes(rows[0]["start_time"])
    result, last_elapsed = [], -1
    for index, row in enumerate(rows):
        if index == 0:
            total, arrival, evidence = 0, "", "explicit_request_date_and_origin_start_clock"
        else:
            arrival_clock = clock_minutes(row.get("arrive_time"))
            running = row.get("running_time", "")
            day_str = row.get("arrive_day_str", "")
            have_running = str(running).strip() not in ("", "----", "--", "None")
            have_day = str(day_str).strip() not in ("", "----", "--", "None")
            if not have_running and not have_day:
                raise ValueError("Official row lacks both cumulative duration and arrival day")
            total = elapsed_minutes(running) if have_running else published_day(day_str) * 1440 + arrival_clock - origin_clock
            arrival_dt = origin + timedelta(minutes=total)
            if not 0 < total <= 7 * 1440 or clock_minutes(arrival_dt.strftime("%H:%M")) != arrival_clock:
                raise ValueError("Published duration does not reproduce the arrival clock")
            if have_day and (arrival_dt.date() - origin.date()).days != published_day(day_str):
                raise ValueError("Published duration and arrival-day label conflict")
            if total <= last_elapsed:
                raise ValueError("Cumulative arrival times are not strictly chronological")
            arrival = arrival_dt.isoformat()
            evidence = "published_running_time" + ("_and_arrival_day" if have_day else "") if have_running else "published_arrival_day"
        last_elapsed = total
        result.append(dict(probe_id=plan["probe_id"], train_code=plan["train_code"], requested_date=plan["requested_date"],
                           station_name=row["station_name"], station_no=row.get("station_no", str(index + 1)),
                           start_time=row.get("start_time", ""), arrive_time=row.get("arrive_time", ""),
                           running_time=row.get("running_time", ""), arrive_day_str=row.get("arrive_day_str", ""),
                           published_elapsed_min=total, published_arrival_at=arrival, date_evidence=evidence,
                           raw_fields_json=json.dumps(row, ensure_ascii=False)))
    xining = [x for x in result if x["station_name"] == "西宁"]
    if len(xining) != 1:
        raise ValueError("Exactly one Xining arrival is required")
    return result, dict(returned_stops=len(rows), clock_tables_match=True,
                        dated_cumulative_validation_passed=True, lhasa_start=origin.isoformat(),
                        xining_arrival=xining[0]["published_arrival_at"], lhasa_xining_min=xining[0]["published_elapsed_min"],
                        assessment="published_dated_timetable_validated_not_ticket_availability")


def run(actor="user"):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    plans, stops, _ = prior_stop_evidence()
    if MARKER.exists():
        old = read_project_json(MARKER)
        if old["actor"] == actor:
            result = replay(Path(old["raw_dir"]))
            print("复用本批已保存响应；未发起新的列车请求。", flush=True)
            return result
    meta = read_project_json(ROOT / 'data/raw' / PRIMARY / 'job_metadata.json')
    deadline = datetime.fromisoformat(meta["started_at"]) + timedelta(hours=48)
    if datetime.now(TZ) >= deadline:
        raise ValueError("Original snapshot deadline passed; no re-dating or silent extension")
    if any(not 0 <= (date.fromisoformat(p["requested_date"]) - datetime.now(TZ).date()).days < 15 for p in plans):
        raise ValueError("Original departure date is outside normal query range")
    name = actor + "_stage1i_dated_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f")
    raw, out = ROOT / "data/raw" / name, ROOT / "data/processed" / name
    raw.mkdir(exist_ok=False); out.mkdir(exist_ok=False)
    write_json(raw / "protocol.json", dict(plans=plans, previous_stop_job=STOP_JOB, deadline=deadline.isoformat(), actor=actor,
                                           output_dir=str(out), matrix_fill_permitted=False))
    (raw / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    write_json(MARKER, dict(actor=actor, raw_dir=str(raw)))
    client = SourceClient(raw, actor, 3)
    try:
        page, _ = client.get("traininfo_page", BASE + "queryTrainInfo/init")
        captcha = re.search(r"\bvar\s+openRandCodeCheck\s*=\s*['\"]([YN])['\"]", page)
        if not captcha or captcha[1] != "N":
            raise SourceError("Official page requires verification or changed; stop without bypass")
        link = re.search(r"src=['\"]([^'\"]*/queryTrainInfo_js\.js[^'\"]*)", page)
        if not link:
            raise SourceError("Official dated-query frontend link missing")
        js_url = urljoin(BASE + "queryTrainInfo/init", link[1])
        if urlparse(js_url).netloc != "kyfw.12306.cn":
            raise SourceError("Unexpected frontend source host")
        js, _ = client.get("traininfo_frontend", js_url)
        if not re.search(r"url\s*:\s*ctx\s*\+\s*['\"]queryTrainInfo/query['\"]", js) or any(
            token not in js for token in ("leftTicketDTO.train_no", "leftTicketDTO.train_date", "running_time", "arrive_day_str")):
            raise SourceError("Dated cumulative query endpoint/fields not verified from official frontend")
        for p in plans:
            if datetime.now(TZ) >= deadline:
                raise SourceError("Snapshot deadline reached")
            body, source = client.get(p["probe_id"], BASE + "queryTrainInfo/query", {
                "leftTicketDTO.train_no": p["train_no"], "leftTicketDTO.train_date": p["requested_date"], "rand_code": ""})
            if datetime.fromisoformat(source["accessed_at"]) >= deadline:
                raise SourceError("Response outside source snapshot deadline")
            try:
                _, quality = validate_full_table(body, p, stops[p["probe_id"]])
            except (ValueError, TypeError, KeyError) as error:
                raise SourceError(str(error)) from error
            print(p["train_code"], "官方累计历时核验：", quality["lhasa_xining_min"], "分钟；西宁到达：", quality["xining_arrival"], flush=True)
    except SourceError as error:
        write_json(raw / "stopped.json", dict(error=str(error), at=datetime.now(TZ).isoformat(), automatic_retry=False))
        print("本批暂停：", str(error), flush=True)
    finally:
        client.close()
    return replay(raw)


def replay(raw):
    protocol = read_project_json(raw / 'protocol.json')
    plans, stops, _ = prior_stop_evidence()
    if protocol["plans"] != plans:
        raise ValueError("Dated schedule request plan changed")
    manifest = read_project_json(raw / 'source_manifest.json') if (raw / "source_manifest.json").exists() else []
    sources = {x["source_id"]: x for x in manifest}
    rows, quality = [], []
    for p in plans:
        q = dict(probe_id=p["probe_id"], train_code=p["train_code"], requested_date=p["requested_date"], returned_stops="",
                 clock_tables_match=False, dated_cumulative_validation_passed=False, lhasa_start="", xining_arrival="",
                 lhasa_xining_min="", assessment="not_attempted_or_unavailable", raw_file="", sha256="")
        source = sources.get(p["probe_id"])
        if source:
            q.update(raw_file=source.get("raw_file", ""), sha256=source.get("sha256", ""))
            try:
                if source.get("error") or source.get("http_status") != 200:
                    raise ValueError("Official source request failed")
                if source["params"] != {"leftTicketDTO.train_no": p["train_no"], "leftTicketDTO.train_date": p["requested_date"], "rand_code": ""}:
                    raise ValueError("Dated request parameters differ")
                if source["url"] != BASE + "queryTrainInfo/query" or datetime.fromisoformat(source["accessed_at"]) >= datetime.fromisoformat(protocol["deadline"]):
                    raise ValueError("Dated request source/time outside protocol")
                if sha(ROOT / source["raw_file"]) != source["sha256"]:
                    raise ValueError("Dated raw response hash mismatch")
                parsed, checks = validate_full_table((ROOT / source["raw_file"]).read_text(encoding="utf-8"), p, stops[p["probe_id"]])
                rows.extend(parsed); q.update(checks)
            except (ValueError, TypeError, KeyError) as error:
                q["assessment"] = "needs_review: " + str(error)
        quality.append(q)
    out = Path(protocol["output_dir"])
    write_csv(out / "dated_schedule_rows.csv", rows, DETAIL_FIELDS)
    write_csv(out / "dated_schedule_quality.csv", quality, QUALITY_FIELDS)
    stopped = read_project_json(raw / 'stopped.json') if (raw / "stopped.json").exists() else {}
    summary = dict(actor=protocol["actor"], requested_services=3,
                   validated_services=sum(q["dated_cumulative_validation_passed"] for q in quality),
                   all_three_dated_tables_validated=all(q["dated_cumulative_validation_passed"] for q in quality),
                   matrix_fill_permitted=False, matrices_modified=False, ticket_availability_verified=False,
                   error=stopped.get("error"), raw_dir=str(raw), output_dir=str(out), software=software_versions(),
                   note="Only explicit source cumulative duration or source day label is accepted. No minimum clock rollover or copying older services. Review before matrix update.")
    write_json(out / "dated_schedule_summary.json", summary)
    return summary
