"""Three dated official stop-table probes, derived from saved unknown services.

Uses the endpoint and parameter names found in the official saved front-end JS.
This script preserves candidate evidence only; it does not fill any time matrix.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from stage1_collect import ROOT, TZ, BASE, INIT_URL, SourceClient, SourceError, write_csv, write_json, now, software_versions

PRIMARY="user_stage1c_v2_20261113_132207_325427"
STOP_FIELDS=["probe_id","requested_train","requested_date","row_index","station_name","station_no","station_train_code","start_time","arrive_time","arrive_day_str","stopover_time","all_fields_json"]


def probe_plan():
    cp=json.loads((ROOT/"data/raw"/PRIMARY/"checkpoints/N26_N29.json").read_text(encoding="utf-8"))
    payload=json.loads((ROOT/cp["source"]["raw_file"]).read_bytes())
    wanted=("Z22","Z166","Z266")
    selected=[]
    for code in wanted:
        matches=[r.split("|") for r in payload["data"]["result"] if r.split("|")[3]==code]
        if len(matches)!=1:
            raise ValueError("Expected one authentic saved service for "+code)
        f=matches[0]
        if f[6:8]!=["LSO","XNO"] or f[8:11]!=["24:00","24:00","99:59"]:
            raise ValueError("Probe no longer matches reviewed missing-time record")
        selected.append(dict(probe_id="S"+str(len(selected)+1),train_code=code,train_no=f[2],
                             requested_date=cp["query"]["date"],origin_date=f[13],from_code=f[6],to_code=f[7],
                             primary_source_file=cp["source"]["raw_file"]))
    return selected


def inspect_body(body,plan):
    try:
        obj=json.loads(body)
    except ValueError as error:
        raise SourceError("Stop-table response is not JSON") from error
    if not isinstance(obj,dict) or obj.get("status") is not True:
        raise SourceError("Stop-table source did not declare success")
    outer=obj.get("data")
    if not isinstance(outer,dict) or not isinstance(outer.get("data"),list):
        raise SourceError("Stop-table schema differs; preserve response for review")
    stops=outer["data"]
    if not all(isinstance(row,dict) for row in stops):
        raise SourceError("Unexpected stop-table row type")
    clock=lambda value:isinstance(value,str) and bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",value))
    start=[row for row in stops if row.get("station_name")=="拉萨"]
    target=[row for row in stops if row.get("station_name")=="西宁"]
    candidate=bool(start and target and any(clock(row.get("start_time")) for row in start) and any(clock(row.get("arrive_time")) for row in target))
    rows=[]
    for index,row in enumerate(stops):
        rows.append(dict(probe_id=plan["probe_id"],requested_train=plan["train_code"],requested_date=plan["requested_date"],row_index=index,
                         station_name=row.get("station_name",""),station_no=row.get("station_no",""),station_train_code=row.get("station_train_code",""),
                         start_time=row.get("start_time",""),arrive_time=row.get("arrive_time",""),arrive_day_str=row.get("arrive_day_str",""),
                         stopover_time=row.get("stopover_time",""),all_fields_json=json.dumps(row,ensure_ascii=False)))
    return rows,dict(returned_stops=len(stops),lhasa_and_xining_clocks_present=candidate,
                     assessment="candidate_timetable_needs_date_service_and_day_offset_review" if candidate else "no_complete_usable_lhasa_xining_clocks",
                     matrix_fill_permitted=False,response_data_keys=json.dumps(list(outer),ensure_ascii=False))


def run(actor="user"):
    if actor not in ("user","assistant"):
        raise ValueError("Invalid actor")
    plans=probe_plan()
    today=datetime.now(TZ).date()
    if any(not 0<=(date.fromisoformat(p["requested_date"])-today).days<15 for p in plans):
        raise ValueError("Frozen requested date no longer queryable; do not silently redate")
    old_meta=json.loads((ROOT/"data/raw"/PRIMARY/"job_metadata.json").read_text(encoding="utf-8"))
    from datetime import timedelta
    deadline=datetime.fromisoformat(old_meta["started_at"])+timedelta(hours=48)
    if datetime.now(TZ)>=deadline:
        raise ValueError("Snapshot deadline passed; retain data and review another version")
    name=actor+"_stop_table_probe_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f")
    raw,out=ROOT/"data/raw"/name,ROOT/"data/processed"/name
    raw.mkdir(exist_ok=False);out.mkdir(exist_ok=False)
    write_json(raw/"probe_plan.json",plans)
    (raw/"stage1h_stop_table_probe.py").write_bytes(Path(__file__).read_bytes())
    client=SourceClient(raw,actor,3)
    rows,quality=[],[]
    error_message=None
    current="initialization"
    try:
        page,_=client.get("query_page",INIT_URL)
        link=re.search(r'src=["\']([^"\']*/queryLeftTicket_end_js\.js[^"\']*)',page)
        if not link:raise SourceError("Official stop-table frontend link absent")
        js_url=urljoin(INIT_URL,link.group(1))
        if urlparse(js_url).netloc!="kyfw.12306.cn":raise SourceError("Unexpected source host")
        js,_=client.get("stop_table_frontend",js_url)
        endpoint=re.search(r'url\s*:\s*ctx\s*\+\s*["\'](czxx/queryByTrainNo)["\']',js)
        if not endpoint or any(token not in js for token in ("train_no:","from_station_telecode:","to_station_telecode:","depart_date:")):
            raise SourceError("Stop-table endpoint or parameter names not verified from official client")
        for plan in plans:
            current=plan["probe_id"]
            if datetime.now(TZ)>=deadline:raise SourceError("Snapshot deadline reached")
            text,source=client.get(current,urljoin(BASE,endpoint.group(1)),{
                "train_no":plan["train_no"],"from_station_telecode":plan["from_code"],
                "to_station_telecode":plan["to_code"],"depart_date":plan["requested_date"]})
            if datetime.fromisoformat(source["accessed_at"])>=deadline:raise SourceError("Source accessed beyond agreed snapshot deadline")
            parsed,result=inspect_body(text,plan)
            rows.extend(parsed)
            quality.append(dict(probe_id=current,train_code=plan["train_code"],requested_date=plan["requested_date"],
                                returned_stops=result["returned_stops"],lhasa_and_xining_clocks_present=result["lhasa_and_xining_clocks_present"],
                                assessment=result["assessment"],matrix_fill_permitted=False,raw_file=source["raw_file"],sha256=source["sha256"]))
            print(plan["train_code"],plan["requested_date"],"stops=",result["returned_stops"],"候选时刻字段=",result["lhasa_and_xining_clocks_present"],flush=True)
    except SourceError as error:
        error_message=str(error)
        write_json(raw/"stopped.json",dict(probe_id=current,error=error_message,at=now(),automatic_retry=False))
    finally:
        client.close()
        done={q["probe_id"] for q in quality}
        for plan in plans:
            if plan["probe_id"] not in done:
                quality.append(dict(probe_id=plan["probe_id"],train_code=plan["train_code"],requested_date=plan["requested_date"],returned_stops="",
                                    lhasa_and_xining_clocks_present=False,assessment="request_failed_or_not_attempted",matrix_fill_permitted=False,raw_file="",sha256=""))
        write_csv(out/"stop_table_rows.csv",rows,STOP_FIELDS)
        write_csv(out/"stop_table_probe_quality.csv",quality,list(quality[0]))
        result=dict(actor=actor,requested_date="2026-11-18",planned_services=3,completed_services=len(done),
                    candidate_services=sum(q["lhasa_and_xining_clocks_present"] for q in quality),error=error_message,
                    output_dir=str(out),raw_dir=str(raw),matrix_fill_permitted=False,software=software_versions(),
                    note="This is an explicit-date official source probe, not validated replacement data or permission to infer date offsets.")
        write_json(out/"probe_summary.json",result)
    return result
