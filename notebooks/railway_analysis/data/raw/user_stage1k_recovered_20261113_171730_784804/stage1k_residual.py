"""Six evidence-based residual queries. No broad restart or date copying."""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import numpy as np

from stage1_collect import (ROOT, TZ, BASE, INIT_URL, SourceClient, SourceError, TRAIN_FIELDS,
    parse_station_dictionary, verify_client_field_map, write_csv, write_json, now, software_versions)
from stage1b_transfer import read_csv
from stage1c_parser_v2 import parse_train_response, PARSER_VERSION
from stage1e_followups import verify_checkpoint, atomic_json, ACCEPTED
from stage1g_targeted import inspect as export_checkpoints
from stage1h_matrix import verified_input
from stage1j_restore import restored_records
from stage1i_dated_schedule import sha

J_JOB = "user_stage1j_restored_20261113_162646_869372"
PRIMARY = "user_stage1c_v2_20261113_132207_325427"
MARKER = ROOT / "evidence/stage1k_current_job.json"
CODE_FILES = ["stage1k_residual.py", "stage1k_matrix.py", "stage1j_restore.py", "stage1d_routes.py", "stage1c_parser_v2.py", "stage1_collect.py"]
SPECS = [
    ("2026-11-19", "西宁", "重庆北", "重庆"),
    ("2026-11-20", "上海", "杭州东", "杭州"),
    ("2026-11-20", "武昌", "南昌", "南昌"),
    ("2026-11-20", "北京西", "沈阳北", "沈阳"),
    ("2026-11-20", "长沙", "海口", "海口"),
    ("2026-11-21", "广州白云", "海口", "海口"),
]


def validated_j_records():
    original, _ = verified_input()
    restored, _, _ = restored_records()
    combined = original + restored
    directory = ROOT / "data/processed" / J_JOB
    summary = json.loads((directory / "restoration_summary.json").read_text(encoding="utf-8"))
    for name, checksum in summary["scripts_sha256"].items():
        if sha(ROOT / "scripts" / name) != checksum:
            raise ValueError("J analysis source changed: " + name)
    if [{k:str(r[k]) for k in TRAIN_FIELDS} for r in combined] != read_csv(directory / "combined_records_with_sources.csv"):
        raise ValueError("User J records differ from authenticated sources")
    matrix = read_csv(directory / "raw_directed_time_34.csv")
    nodes = read_csv(directory / "nodes_34.csv")
    ids = [n["node_id"] for n in nodes]
    if len(matrix) != 34 or [r["node_id"] for r in matrix] != ids or any(float(row[row["node_id"]]) != 0 for row in matrix):
        raise ValueError("User J matrix labels/diagonal failed")
    if sum(row[k] == "" for row in matrix for k in ids) != 135:
        raise ValueError("User J missing count changed; reassess the residual plan")
    return combined, restored, directory


def make_plan():
    combined, restored, directory = validated_j_records()
    missing = read_csv(directory / "remaining_core_missing.csv")
    if {(r["from_city"],r["to_city"]) for r in missing} != {("拉萨",d) for d in ("沈阳","杭州","南昌","海口","重庆")}:
        raise ValueError("Residual directions differ from the reviewed five")
    plan, proofs = [], []
    for index, (day, station, target, city) in enumerate(SPECS, 1):
        first_legs = [r for r in restored if r["from_code"] == "LSO" and r["to_name"] == station]
        if not first_legs:
            raise ValueError("No source-grounded Lhasa arrival at " + station)
        first = min(first_legs, key=lambda r:r["arrival_at"])
        arrival = datetime.fromisoformat(first["arrival_at"])
        if not arrival.date() <= date.fromisoformat(day) <= arrival.date() + timedelta(days=1):
            raise ValueError("Residual query date is not the actual arrival date or next day")
        patterns = [r for r in combined if r["from_name"] == station and r["to_dictionary_city"] == city]
        if not patterns:
            raise ValueError("No observed exact-station service pattern for planning")
        query_id = f"K{index:02d}"
        plan.append(dict(query_id=query_id, role="followup_date", primary_query_id="", date=day,
                         from_city=first["to_dictionary_city"], to_city=city, from_station=station, to_station=target,
                         purpose="Residual Lhasa OD; actual arrival station/date; no cross-station link"))
        proofs.append(dict(query_id=query_id, affected_od="拉萨→"+city, first_train=first["train_code"],
                           actual_arrival_station=station, actual_arrival_at=first["arrival_at"],
                           ready_at_60min=(arrival+timedelta(minutes=60)).isoformat(), requested_date=day,
                           origin_departure_at=first["departure_at"], first_leg_raw_file=first["raw_file"],
                           first_leg_raw_sha256=first["raw_sha256"],
                           second_leg_pattern_count=len(patterns), pattern_dates=";".join(sorted({r["query_date"] for r in patterns})),
                           pattern_is_not_confirmed_for_query_date=True,
                           note="Earlier-date patterns select query only; never copied into the graph"))
    # Check completed requests, including successful empty responses, to avoid
    # repeating them merely because their parsed train table has no rows.
    wanted = {(p["date"],p["from_station"],p["to_station"]) for p in plan}
    for job in (PRIMARY,"user_stage1e_20261113_143455_080165","user_stage1g_20261113_153248_952115"):
        for path in (ROOT / "data/raw" / job / "checkpoints").glob("*.json"):
            q = json.loads(path.read_text(encoding="utf-8"))["query"]
            if (q["date"],q["from_station"],q["to_station"]) in wanted:
                raise ValueError("Planned exact query already has a checkpoint; review reuse first")
    return plan, proofs, dict(base_job=J_JOB, base_csv_sha256=sha(directory/"combined_records_with_sources.csv"),
                              snapshot_deadline_exclusive="2026-11-13T21:28:30.987887+08:00")


def plan_preview(actor="user"):
    plan, proofs, protocol = make_plan()
    out = ROOT / "data/processed" / (actor+"_stage1k_plan_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    write_csv(out/"six_query_plan.csv",plan,list(plan[0]))
    write_csv(out/"actual_arrival_evidence.csv",proofs,list(proofs[0]))
    result = dict(actor=actor,total_queries=6,affected_missing_directions=5,new_network_requests=0,
                  base_j_raw_replay_passed=True,output_dir=str(out),protocol=protocol)
    write_json(out/"plan_summary.json",result)
    return result


def inspect(job):
    job = Path(job)
    protocol = json.loads((job/"protocol.json").read_text(encoding="utf-8"))
    for path in (job/"checkpoints").glob("*.json"):
        cp=json.loads(path.read_text(encoding="utf-8"))
        if datetime.fromisoformat(cp["source"]["accessed_at"]) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
            raise ValueError("Source outside frozen collection deadline")
    result = export_checkpoints(job)
    return result


def collect(actor="user", max_queries=6):
    if actor not in ("user","assistant") or not isinstance(max_queries,int) or not 0<=max_queries<=6:
        raise ValueError("Invalid actor/query limit")
    plan, proofs, protocol = make_plan()
    if MARKER.exists():
        job = Path(json.loads(MARKER.read_text(encoding="utf-8"))["job_dir"]).resolve()
        if job.parent != (ROOT/"data/raw").resolve():
            raise ValueError("Invalid saved job directory")
        if json.loads((job/"plan.json").read_text(encoding="utf-8")) != plan or json.loads((job/"protocol.json").read_text(encoding="utf-8")) != protocol:
            raise ValueError("Source or six-query plan changed")
        meta = json.loads((job/"metadata.json").read_text(encoding="utf-8"))
        if meta["actor"] != actor or any(sha(ROOT/"scripts"/n)!=h for n,h in meta["code_hashes"].items()):
            raise ValueError("Actor or collector source version changed")
        if (job/"blocked.json").exists():
            print("本批已有暂停记录，未自动重试。",flush=True)
            return inspect(job)
    else:
        if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
            raise ValueError("Original 48-hour snapshot deadline passed; preserve sources, no silent extension")
        job = ROOT/"data/raw"/(actor+"_stage1k_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
        job.mkdir(exist_ok=False);(job/"checkpoints").mkdir();(job/"sessions").mkdir()
        write_json(job/"plan.json",plan);write_json(job/"protocol.json",protocol)
        write_csv(job/"actual_arrival_evidence.csv",proofs,list(proofs[0]))
        for name in CODE_FILES:(job/name).write_bytes((ROOT/"scripts"/name).read_bytes())
        write_json(job/"metadata.json",dict(actor=actor,created_at=now(),parser_version=PARSER_VERSION,software=software_versions(),code_hashes={n:sha(ROOT/"scripts"/n) for n in CODE_FILES}))
        atomic_json(MARKER,dict(job_dir=str(job)))
    remaining=[p for p in plan if not (job/"checkpoints"/(p["query_id"]+".json")).exists()]
    if not remaining or max_queries==0:
        return inspect(job)
    if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]) or any(not 0<=(date.fromisoformat(p["date"])-datetime.now(TZ).date()).days<15 for p in remaining):
        raise ValueError("Frozen collection time/query date window expired")
    lock=job/"running.lock"
    with lock.open("x",encoding="utf-8") as f:f.write(now())
    session=job/"sessions"/datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f");session.mkdir(exist_ok=False)
    client=SourceClient(session,actor,3); current="initialization"
    try:
        page,_=client.get("query_page",INIT_URL)
        endpoint=re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]",page)
        station_link=re.search(r'src=["\x27]([^"\x27]*/station_name\.js[^"\x27]*)',page)
        field_link=re.search(r'src=["\x27]([^"\x27]*/queryLeftTicket_end_js\.js[^"\x27]*)',page)
        if not endpoint or not station_link or not field_link:raise SourceError("Official metadata unavailable")
        urls=[urljoin(INIT_URL,m[1]) for m in (station_link,field_link)]
        if any(urlparse(u).netloc!="kyfw.12306.cn" for u in urls):raise SourceError("Unexpected metadata host")
        text,station_source=client.get("station_dictionary",urls[0])
        stations=parse_station_dictionary(text);by_name={s["station_name"]:s for s in stations};by_code={s["station_code"]:s for s in stations}
        js,_=client.get("official_field_mapping",urls[1]);verify_client_field_map(js)
        for p in remaining[:max_queries]:
            current=p["query_id"]
            if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):raise SourceError("Snapshot deadline reached")
            if any(p[k] not in by_name for k in ("from_station","to_station")):raise SourceError("Exact planned station absent from current dictionary")
            q=dict(p,from_code=by_name[p["from_station"]]["station_code"],to_code=by_name[p["to_station"]]["station_code"])
            body,source=client.get(current,urljoin(BASE,endpoint[1]),{"leftTicketDTO.train_date":q["date"],"leftTicketDTO.from_station":q["from_code"],"leftTicketDTO.to_station":q["to_code"],"purpose_codes":"ADULT"})
            if datetime.fromisoformat(source["accessed_at"])>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):raise SourceError("Query outside source deadline")
            records,issues,quality=parse_train_response(body,q,by_code,source)
            cp=dict(query=q,source=source,station_snapshot=station_source,records=records,issues=issues,quality=quality,parser_version=PARSER_VERSION)
            if quality["status"] not in ACCEPTED:
                write_json(session/(current+"_quarantined.json"),cp)
                raise SourceError("Unreviewed response records; inspect saved raw response")
            atomic_json(job/"checkpoints"/(current+".json"),cp)
            print(current,p["date"],p["from_station"]+"→"+p["to_station"],quality["status"],"valid=",quality["valid_count"],flush=True)
    except KeyboardInterrupt:
        print("正常中断，已完成请求保留。",flush=True)
    except SourceError as error:
        atomic_json(job/"blocked.json",dict(query_id=current,error=str(error),at=now(),automatic_retry=False))
        print("本批暂停：",str(error),flush=True)
    finally:
        client.close();lock.unlink()
    return inspect(job)


def combined_after_six():
    if not MARKER.exists():raise ValueError("Run the six-query collection first")
    job=Path(json.loads(MARKER.read_text(encoding="utf-8"))["job_dir"])
    summary=inspect(job)
    if summary["remaining_queries"] or summary["blocking_error"] or (job/"running.lock").exists():
        raise ValueError("Six-query batch incomplete or blocked; do not claim complete matrix")
    original,_,directory=validated_j_records()
    plan,_,protocol=make_plan()
    if json.loads((job/"plan.json").read_text(encoding="utf-8"))!=plan or json.loads((job/"protocol.json").read_text(encoding="utf-8"))!=protocol:
        raise ValueError("Saved six-query plan changed")
    cache={};new=[]
    for p in plan:
        cp=json.loads((job/"checkpoints"/(p["query_id"]+".json")).read_text(encoding="utf-8"))
        parsed,issues,q=verify_checkpoint(cp,cache)
        if q["rejected_count"]:raise ValueError("Unreviewed parsed records")
        new.extend(parsed)
    return original+new,new,dict(base_job=J_JOB,base_records=len(original),new_records=len(new),six_query_job=job.name,all_six_requests_returned=True,
                                unavailable_timetable_rows=summary["unavailable_timetable_rows"],unresolved_station_rows=summary["unresolved_station_rows"],
                                base_csv_sha256=sha(directory/"combined_records_with_sources.csv"))
