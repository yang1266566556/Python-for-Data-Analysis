"""Two shared dated rail links for the last three Macao directions."""

from railway_project_io import read_project_json, script_hash_matches
import json
import re
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urljoin,urlparse

from stage1_collect import ROOT,TZ,BASE,INIT_URL,TRAIN_FIELDS,SourceError,write_csv,write_json,now,software_versions,parse_station_dictionary,verify_client_field_map
from stage1b_transfer import read_csv
from stage1c_parser_v2 import parse_train_response,PARSER_VERSION
from stage1e_followups import verify_checkpoint,atomic_json,ACCEPTED
from stage1g_targeted import inspect as export_job
from stage1i_dated_schedule import sha
from stage1k_manual_retry import LongerTimeoutClient
from stage1l_access import combined_records as l_records
from stage1d_routes import prepare_records,TemporalGraph

L_RESULT="user_stage1l_special_20261113_174957_808129"
MARKER=ROOT/"evidence/stage1m_final_links_current_job.json"
CODE_FILES=["stage1m_final_links.py","stage1m_matrix.py","stage1l_access.py","stage1l_matrix.py","stage1d_routes.py","stage1c_parser_v2.py","stage1_collect.py","stage1k_manual_retry.py"]


def verified_l():
    rows,core_dir,protocol,info=l_records()
    out=ROOT/"data/processed"/L_RESULT
    result=read_project_json(out / 'special_region_matrix_summary.json')
    if result["input"]!=info or result["protocol"]!=protocol:raise ValueError("L output refers to a different source version")
    for name,digest in result["analysis_code_sha256"].items():
        if not script_hash_matches(ROOT / 'scripts' / name, digest):raise ValueError("L analysis source changed")
    if [{k:str(r[k]) for k in TRAIN_FIELDS} for r in rows]!=read_csv(out/"combined_records_with_sources.csv"):raise ValueError("L CSV differs from authenticated raw replay")
    missing=read_csv(out/"ordinary_missing_pairs.csv")
    if {(r["from_city"],r["to_city"]) for r in missing if r["access_assumption_min"]=="60"}!={(c,"澳门") for c in ("海口","拉萨","乌鲁木齐")}:raise ValueError("Reviewed residual directions changed")
    return rows,core_dir,protocol,info


def plan_with_evidence():
    rows,_,protocol,info=verified_l()
    cfg=read_project_json(ROOT / 'data/raw/user_stage1c_v2_20261113_132207_325427/protocol.json')
    cities=set(cfg["anchor_stations"])|{"珠海"}
    records=prepare_records(rows,cities,set(),"observed_group",cfg["future_latest_arrival_exclusive"])
    graph=TemporalGraph(records,cfg["query_date"],60,cfg["future_latest_arrival_exclusive"],cfg["future_elapsed_limit_minutes"])
    plan=[dict(query_id="F01",role="final_macao_link",primary_query_id="",date="2026-11-20",from_city="北京",to_city="广州",from_station="北京西",to_station="广州南",purpose="Shared dated link after verified arrival; no station substitution"),
          dict(query_id="F02",role="final_macao_link",primary_query_id="",date="2026-11-20",from_city="郑州",to_city="广州",from_station="郑州",to_station="广州南",purpose="Shared dated link after verified arrival; no station substitution")]
    proofs,legs=[],[]
    for city in ("海口","拉萨","乌鲁木齐"):
        dist,parents=graph.shortest(city)
        for q in plan:
            hits=[(records[i]["arrival_at"],dist[n],n,i) for n,i in graph.arrs_by_city[q["from_city"]]
                  if records[i]["to_name"]==q["from_station"] and dist[n]!=float("inf")]
            if not hits:raise ValueError("No authentic arrival at the planned station")
            when,elapsed,node,i=min(hits);path,value,wait=graph.itinerary(node,parents)
            if not datetime.fromisoformat(when).date()<=date.fromisoformat(q["date"]):raise ValueError("Query precedes actual arrival")
            patterns=[r for r in rows if r["from_name"]==q["from_station"] and r["to_name"]=="广州南" and r["query_date"]=="2026-11-18"]
            if not patterns:raise ValueError("No observed exact-station pattern supporting query selection")
            proofs.append(dict(query_id=q["query_id"],origin_city=city,actual_hub_station=q["from_station"],arrival_at=when,
                               first_departure_at=path[0]["departure_at"],rail_elapsed_to_hub_min=value,query_date=q["date"],
                               earlier_date_pattern_count=len(patterns),pattern_is_not_new_date_confirmation=True))
            for j,r in enumerate(path):
                legs.append(dict(query_id=q["query_id"],origin_city=city,leg_index=j+1,train_code=r["train_code"],from_name=r["from_name"],to_name=r["to_name"],departure_at=r["departure_at"],arrival_at=r["arrival_at"],raw_file=r["raw_file"],raw_row_index=r["raw_row_index"]))
    protocol=dict(protocol,prior_access_query_count=protocol["query_count"],query_count=2,link_base_job=L_RESULT,
                  link_base_csv_sha256=sha(ROOT/"data/processed"/L_RESULT/"combined_records_with_sources.csv"),additional_link_queries=2)
    return plan,proofs,legs,protocol


def preview(actor="user"):
    plan,proofs,legs,protocol=plan_with_evidence()
    out=ROOT/"data/processed"/(actor+"_stage1m_plan_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(exist_ok=False)
    for name,data in (("two_query_plan.csv",plan),("actual_hub_arrivals.csv",proofs),("hub_arrival_legs.csv",legs)):
        write_csv(out/name,data,list(data[0]))
    write_json(out/"protocol.json",protocol)
    return dict(output_dir=str(out),query_count=2,affected_directions=3)


def inspect(job):
    job=Path(job);protocol=read_project_json(job / 'protocol.json')
    for p in (job/"checkpoints").glob("*.json"):
        cp=read_project_json(p)
        if datetime.fromisoformat(cp["source"]["accessed_at"])>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):raise ValueError("Link source outside snapshot")
    return export_job(job)


def collect(actor="user"):
    if actor not in ("user","assistant"):raise ValueError("Invalid actor")
    plan,proofs,_,protocol=plan_with_evidence()
    if MARKER.exists():
        job=Path(read_project_json(MARKER)["job_dir"]).resolve()
        if job.parent!=(ROOT/"data/raw").resolve():raise ValueError("Invalid link directory")
        if read_project_json(job / 'plan.json')!=plan or read_project_json(job / 'protocol.json')!=protocol:raise ValueError("Link plan/source changed")
        meta=read_project_json(job / 'metadata.json')
        if meta["actor"]!=actor or any(not script_hash_matches(ROOT / 'scripts' / n, h) for n,h in meta["code_hashes"].items()):raise ValueError("Frozen actor/code changed")
        if (job/"blocked.json").exists():print("本分支已暂停，未自动重试。",flush=True);return inspect(job)
    else:
        if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):raise ValueError("Original snapshot deadline passed")
        job=ROOT/"data/raw"/(actor+"_stage1m_links_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
        job.mkdir(exist_ok=False);(job/"checkpoints").mkdir();(job/"sessions").mkdir()
        write_json(job/"plan.json",plan);write_json(job/"protocol.json",protocol)
        write_csv(job/"actual_hub_arrivals.csv",proofs,list(proofs[0]))
        for n in CODE_FILES:(job/n).write_bytes((ROOT/"scripts"/n).read_bytes())
        write_json(job/"metadata.json",dict(actor=actor,created_at=now(),software=software_versions(),parser_version=PARSER_VERSION,code_hashes={n:sha(ROOT/"scripts"/n) for n in CODE_FILES}))
        atomic_json(MARKER,dict(job_dir=str(job)))
    remaining=[q for q in plan if not (job/"checkpoints"/(q["query_id"]+".json")).exists()]
    if not remaining:return inspect(job)
    if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]) or any(not 0<=(date.fromisoformat(q["date"])-datetime.now(TZ).date()).days<15 for q in remaining):raise ValueError("Frozen query window expired")
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
        if any(urlparse(u).netloc!="kyfw.12306.cn" for u in urls):raise SourceError("Unexpected metadata host")
        text,station_source=client.get("station_dictionary",urls[0]);stations=parse_station_dictionary(text)
        by_name={s["station_name"]:s for s in stations};by_code={s["station_code"]:s for s in stations}
        js,_=client.get("official_field_mapping",urls[1]);verify_client_field_map(js)
        for p in remaining:
            current=p["query_id"]
            if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):raise SourceError("Snapshot deadline reached")
            if any(p[k] not in by_name for k in ("from_station","to_station")):raise SourceError("Exact planned station absent")
            q=dict(p,from_code=by_name[p["from_station"]]["station_code"],to_code=by_name[p["to_station"]]["station_code"])
            body,source=client.get(current,urljoin(BASE,endpoint[1]),{"leftTicketDTO.train_date":q["date"],"leftTicketDTO.from_station":q["from_code"],"leftTicketDTO.to_station":q["to_code"],"purpose_codes":"ADULT"})
            if datetime.fromisoformat(source["accessed_at"])>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):raise SourceError("Source outside snapshot")
            records,issues,quality=parse_train_response(body,q,by_code,source)
            cp=dict(query=q,source=source,station_snapshot=station_source,records=records,issues=issues,quality=quality,parser_version=PARSER_VERSION)
            if quality["status"] not in ACCEPTED:write_json(session/(current+"_quarantined.json"),cp);raise SourceError("Unreviewed source rows")
            atomic_json(job/"checkpoints"/(current+".json"),cp)
            print(current,q["date"],q["from_station"]+"→"+q["to_station"],quality["status"],"valid=",quality["valid_count"],flush=True)
    except KeyboardInterrupt:print("正常中断，检查点已保留。",flush=True)
    except SourceError as error:
        atomic_json(job/"blocked.json",dict(query_id=current,error=str(error),at=now(),automatic_retry=False));print("连接查询暂停：",str(error),flush=True)
    finally:client.close();lock.unlink()
    return inspect(job)


def combined_records_for_m():
    if not MARKER.exists():raise ValueError("Run two-link collection first")
    job=Path(read_project_json(MARKER)["job_dir"]).resolve()
    if job.parent!=(ROOT/"data/raw").resolve() or (job/"running.lock").exists():raise ValueError("Invalid or active link branch")
    summary=inspect(job)
    if summary["remaining_queries"] or summary["blocking_error"]:raise ValueError("Two-link collection incomplete/blocked")
    plan,_,_,protocol=plan_with_evidence()
    if read_project_json(job / 'plan.json')!=plan or read_project_json(job / 'protocol.json')!=protocol:raise ValueError("Saved link plan differs")
    meta=read_project_json(job / 'metadata.json')
    if any(not script_hash_matches(ROOT / 'scripts' / n, h) for n,h in meta["code_hashes"].items()):raise ValueError("Saved link code changed")
    rows,core_dir,_,old_info=verified_l();new=[];cache={}
    for q in plan:
        cp=read_project_json(job / 'checkpoints' / (q['query_id'] + '.json'))
        parsed,_,quality=verify_checkpoint(cp,cache)
        if quality["rejected_count"]:raise ValueError("Unreviewed parsed rows")
        new.extend(parsed)
    return rows+new,core_dir,protocol,dict(previous_access_input=old_info,link_job=job.name,new_link_queries=2,new_link_records=len(new),
             unavailable_timetable_rows=summary["unavailable_timetable_rows"],unresolved_station_rows=summary["unresolved_station_rows"])
