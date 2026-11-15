"""Macao access source branch. Zhuhai station is never renamed Macao."""
import json
import re
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urljoin, urlparse

from stage1_collect import (ROOT, TZ, BASE, INIT_URL, TRAIN_FIELDS, write_csv, write_json, now,
                           parse_station_dictionary, verify_client_field_map, SourceError, software_versions)
from stage1b_transfer import read_csv
from stage1k_residual import validated_j_records, make_plan as six_plan
from stage1e_followups import verify_checkpoint, atomic_json, ACCEPTED
from stage1c_parser_v2 import parse_train_response, PARSER_VERSION
from stage1g_targeted import inspect as export_job
from stage1k_manual_retry import LongerTimeoutClient
from stage1i_dated_schedule import sha

CORE_JOB = "user_stage1k_matrix_20261113_171823_241363"
SIX_JOB = "user_stage1k_recovered_20261113_171730_784804"
MARKER = ROOT / "evidence/stage1l_access_current_job.json"
SOURCES = ROOT / "evidence/special_region_sources_20261113/source_registry.json"
CODE_FILES = ["stage1l_access.py", "stage1l_matrix.py", "stage1k_manual_retry.py", "stage1d_routes.py",
              "stage1c_parser_v2.py", "stage1_collect.py"]


def base_records():
    rows, _, _ = validated_j_records()
    matrix_dir = ROOT / "data/processed" / CORE_JOB
    summary = json.loads((matrix_dir / "matrix_acceptance_summary.json").read_text(encoding="utf-8"))
    if not summary["core32_complete"] or summary["source_conflicts"]:
        raise ValueError("Verified core32 prerequisite differs")
    for name, digest in summary["scripts_sha256"].items():
        if sha(ROOT / "scripts" / name) != digest:
            raise ValueError("Core32 analysis version changed")
    plan, _, protocol = six_plan(); cache = {}; new = []
    raw = ROOT / "data/raw" / SIX_JOB
    if (raw / "blocked.json").exists() or (raw / "running.lock").exists():
        raise ValueError("Six-query source is blocked or active")
    if json.loads((raw / "plan.json").read_text(encoding="utf-8")) != plan:
        raise ValueError("Six-query source plan differs")
    for q in plan:
        cp = json.loads((raw / "checkpoints" / (q["query_id"] + ".json")).read_text(encoding="utf-8"))
        if not all(cp["query"][k] == v for k,v in q.items()):
            raise ValueError("Six-query checkpoint differs")
        parsed, _, quality = verify_checkpoint(cp, cache)
        if quality["rejected_count"] or datetime.fromisoformat(cp["source"]["accessed_at"]) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
            raise ValueError("Six-query source not admissible")
        new.extend(parsed)
    if [{k:str(r[k]) for k in TRAIN_FIELDS} for r in new] != read_csv(ROOT / "data/processed" / SIX_JOB / "targeted_train_records.csv"):
        raise ValueError("Six-query CSV differs from raw replay")
    if len(rows) + len(new) != 27535:
        raise ValueError("Verified source record count changed")
    return rows + new, matrix_dir


def access_plan():
    _, core_dir = base_records()
    specs = [("2026-11-18", "珠海", "广州南", "珠海", "广州")]
    specs += [(f"2026-11-{d}", "广州南", "珠海", "广州", "珠海") for d in (19,20,21,22)]
    plan = [dict(query_id=f"M{i:02d}",role="special_region_access",primary_query_id="",date=d,
                 from_station=a,to_station=b,from_city=ac,to_city=bc,purpose="Rail access to separate Macao border node; no free city/station link")
            for i,(d,a,b,ac,bc) in enumerate(specs,1)]
    protocol = dict(core_job=CORE_JOB, core32_csv_sha256=sha(core_dir / "core32_directed_minutes.csv"),
                    source_registry_sha256=sha(SOURCES), query_count=5, rail_transfer_min=60,
                    access_minutes_scenarios=[30,60,90], access_minutes_are_assumptions=True,
                    macao_representative="澳门（关闸澳门侧）", mainland_access_station="珠海",
                    connection_mode="rail_plus_walking_and_border_clearance",
                    port_open_local="06:00", port_close_next_day_local="01:00",
                    taipei_rule="structural rail disconnection per assignment, supported by official planning sources; not query failure",
                    penalty_factors=[2,5,10], penalty_reference="maximum finite directed core32 timetable-model time",
                    snapshot_deadline_exclusive="2026-11-13T21:28:30.987887+08:00")
    return plan, protocol


def preview(actor="user"):
    import numpy as np
    import pandas as pd
    plan, protocol = access_plan()
    core_dir = ROOT / "data/processed" / CORE_JOB
    raw = pd.read_csv(core_dir / "raw_directed_time_34.csv",index_col=0,encoding="utf-8-sig")
    ids = list(raw.index)
    mask = np.array([[a!=b and "N34" in (a,b) for b in ids] for a in ids])
    assert int(mask.sum()) == 66
    core = pd.read_csv(core_dir / "core32_directed_minutes.csv",index_col=0,encoding="utf-8-sig")
    t_ref = float(core.to_numpy().max())
    out = ROOT / "data/processed" / (actor+"_stage1l_plan_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    write_csv(out / "macao_access_query_plan.csv",plan,list(plan[0]))
    write_csv(out / "taipei_structural_unreachable_mask.csv",[dict(node_id=a,**{b:int(mask[i,j]) for j,b in enumerate(ids)}) for i,a in enumerate(ids)],["node_id"]+ids)
    penalties = [dict(alpha=a,reference_max_core32_min=t_ref,penalty_min=a*t_ref,affected_directed_cells=66,
                      actual_travel_time=False,apply_only_to_structural_mask=True) for a in (2,5,10)]
    write_csv(out / "taipei_penalty_plan.csv",penalties,list(penalties[0]))
    write_json(out / "special_region_protocol.json",protocol)
    result = dict(actor=actor, query_count=5, taipei_structural_cells=66, remaining_macao_directed_cells=64,
                  reference_max_core32_min=t_ref, output_dir=str(out), protocol=protocol,
                  note="Penalty parameters are prepared; no incomplete full34 algorithm matrix is manufactured at this stage.")
    write_json(out / "plan_summary.json",result)
    return result


def inspect(job):
    job = Path(job)
    protocol = json.loads((job / "protocol.json").read_text(encoding="utf-8"))
    for p in (job / "checkpoints").glob("*.json"):
        cp = json.loads(p.read_text(encoding="utf-8"))
        if datetime.fromisoformat(cp["source"]["accessed_at"]) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
            raise ValueError("Access source outside frozen snapshot")
    return export_job(job)


def collect(actor="user"):
    if actor not in ("user","assistant"): raise ValueError("Invalid actor")
    plan, protocol = access_plan()
    if MARKER.exists():
        job = Path(json.loads(MARKER.read_text(encoding="utf-8"))["job_dir"]).resolve()
        if job.parent != (ROOT / "data/raw").resolve(): raise ValueError("Invalid access directory")
        if json.loads((job / "plan.json").read_text(encoding="utf-8")) != plan or json.loads((job / "protocol.json").read_text(encoding="utf-8")) != protocol:
            raise ValueError("Access plan/source version changed")
        meta = json.loads((job / "metadata.json").read_text(encoding="utf-8"))
        if meta["actor"] != actor or any(sha(ROOT / "scripts" / n)!=h for n,h in meta["code_hashes"].items()): raise ValueError("Actor/code changed")
        if (job / "blocked.json").exists():
            print("接入分支已暂停，未自动重试。",flush=True);return inspect(job)
    else:
        if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]): raise ValueError("Original snapshot deadline passed")
        job=ROOT/"data/raw"/(actor+"_stage1l_access_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
        job.mkdir(exist_ok=False);(job/"checkpoints").mkdir();(job/"sessions").mkdir()
        write_json(job/"plan.json",plan);write_json(job/"protocol.json",protocol)
        for n in CODE_FILES:(job/n).write_bytes((ROOT/"scripts"/n).read_bytes())
        write_json(job/"metadata.json",dict(actor=actor,created_at=now(),software=software_versions(),parser_version=PARSER_VERSION,code_hashes={n:sha(ROOT/"scripts"/n) for n in CODE_FILES}))
        atomic_json(MARKER,dict(job_dir=str(job)))
    remaining=[p for p in plan if not (job/"checkpoints"/(p["query_id"]+".json")).exists()]
    if not remaining:return inspect(job)
    if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]) or any(not 0<=(date.fromisoformat(p["date"])-datetime.now(TZ).date()).days<15 for p in remaining): raise ValueError("Frozen query window expired")
    lock=job/"running.lock"
    with lock.open("x",encoding="utf-8") as f:f.write(now())
    session=job/"sessions"/datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f");session.mkdir(exist_ok=False)
    client=LongerTimeoutClient(session,actor,3);current="initialization"
    try:
        page,_=client.get("query_page",INIT_URL)
        endpoint=re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]",page)
        station_link=re.search(r'src=["\x27]([^"\x27]*/station_name\.js[^"\x27]*)',page)
        field_link=re.search(r'src=["\x27]([^"\x27]*/queryLeftTicket_end_js\.js[^"\x27]*)',page)
        if not endpoint or not station_link or not field_link:raise SourceError("Official metadata unavailable")
        urls=[urljoin(INIT_URL,x[1]) for x in (station_link,field_link)]
        if any(urlparse(u).netloc!="kyfw.12306.cn" for u in urls):raise SourceError("Unexpected source host")
        text,station_source=client.get("station_dictionary",urls[0]);stations=parse_station_dictionary(text)
        by_name={s["station_name"]:s for s in stations};by_code={s["station_code"]:s for s in stations}
        js,_=client.get("official_field_mapping",urls[1]);verify_client_field_map(js)
        for p in remaining:
            current=p["query_id"]
            if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):raise SourceError("Snapshot deadline reached")
            if any(p[k] not in by_name for k in ("from_station","to_station")):raise SourceError("Planned station identity unavailable")
            q=dict(p,from_code=by_name[p["from_station"]]["station_code"],to_code=by_name[p["to_station"]]["station_code"])
            body,source=client.get(current,urljoin(BASE,endpoint[1]),{"leftTicketDTO.train_date":q["date"],"leftTicketDTO.from_station":q["from_code"],"leftTicketDTO.to_station":q["to_code"],"purpose_codes":"ADULT"})
            if datetime.fromisoformat(source["accessed_at"])>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):raise SourceError("Source outside snapshot")
            rows,issues,quality=parse_train_response(body,q,by_code,source)
            cp=dict(query=q,source=source,station_snapshot=station_source,records=rows,issues=issues,quality=quality,parser_version=PARSER_VERSION)
            if quality["status"] not in ACCEPTED:
                write_json(session/(current+"_quarantined.json"),cp);raise SourceError("Unreviewed records require review")
            atomic_json(job/"checkpoints"/(current+".json"),cp)
            print(current,q["date"],q["from_station"]+"→"+q["to_station"],quality["status"],"valid=",quality["valid_count"],flush=True)
    except KeyboardInterrupt:print("正常中断，检查点已保留。",flush=True)
    except SourceError as error:
        atomic_json(job/"blocked.json",dict(query_id=current,error=str(error),at=now(),automatic_retry=False));print("接入分支暂停：",str(error),flush=True)
    finally:client.close();lock.unlink()
    return inspect(job)


def combined_records():
    if not MARKER.exists():raise ValueError("Run access collection first")
    job=Path(json.loads(MARKER.read_text(encoding="utf-8"))["job_dir"]).resolve()
    if job.parent!=(ROOT/"data/raw").resolve() or (job/"running.lock").exists():raise ValueError("Invalid or active access branch")
    summary=inspect(job)
    if summary["remaining_queries"] or summary["blocking_error"]:raise ValueError("Access collection incomplete or blocked")
    plan,protocol=access_plan()
    if json.loads((job/"plan.json").read_text(encoding="utf-8"))!=plan or json.loads((job/"protocol.json").read_text(encoding="utf-8"))!=protocol:raise ValueError("Access source plan changed")
    meta=json.loads((job/"metadata.json").read_text(encoding="utf-8"))
    if any(sha(ROOT/"scripts"/n)!=h for n,h in meta["code_hashes"].items()):raise ValueError("Frozen access code changed")
    rows,core_dir=base_records();new=[];cache={}
    for q in plan:
        cp=json.loads((job/"checkpoints"/(q["query_id"]+".json")).read_text(encoding="utf-8"))
        parsed,_,quality=verify_checkpoint(cp,cache)
        if quality["rejected_count"]:raise ValueError("Unreviewed parsed records")
        new.extend(parsed)
    return rows+new, core_dir, protocol, dict(access_job=job.name,access_queries=5,new_source_records=len(new),base_source_records=len(rows),
                unavailable_timetable_rows=summary["unavailable_timetable_rows"],unresolved_station_rows=summary["unresolved_station_rows"])
