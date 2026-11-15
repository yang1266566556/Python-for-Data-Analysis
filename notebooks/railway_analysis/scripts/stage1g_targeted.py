"""Small exact-station query branch, with fixed parsing and no legacy-job retry."""

from railway_project_io import read_project_json, script_hash_matches
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from stage1_collect import ROOT, TZ, BASE, INIT_URL, SourceClient, SourceError, TRAIN_FIELDS, ISSUE_FIELDS, parse_station_dictionary, verify_client_field_map, write_json, write_csv, now, software_versions
from stage1c_parser_v2 import parse_train_response, PARSER_VERSION
from stage1e_followups import verify_checkpoint, sha, atomic_json, ACCEPTED
from stage1f_assess import plan_for_assessment

MARKER=ROOT/"evidence/stage1g_current_job.json"
CODE_FILES=["stage1g_targeted.py","stage1f_assess.py","stage1d_routes.py","stage1e_followups.py","stage1c_parser_v2.py","stage1_collect.py"]
QUALITY_FIELDS=["query_id","date","from_city","to_city","from_station","to_station","status","raw_count","valid_count","unavailable_count","unresolved_station_count"]


def inspect(job_dir):
    job=Path(job_dir).resolve()
    if job.parent!=(ROOT/"data/raw").resolve():
        raise ValueError("Invalid target query job")
    plan=read_project_json(job / 'plan.json')
    rows,issues,quality,sources=[],[],[],[]
    station_cache={}
    for query in plan:
        p=job/"checkpoints"/(query["query_id"]+".json")
        if not p.exists():
            quality.append(dict(query_id=query["query_id"],date=query["date"],from_city=query["from_city"],to_city=query["to_city"],
                                from_station=query["from_station"],to_station=query["to_station"],status="not_collected",raw_count="",valid_count="",unavailable_count="",unresolved_station_count=""))
            continue
        cp=read_project_json(p)
        if not all(cp["query"][k]==v for k,v in query.items()):
            raise ValueError("Saved query differs from exact-station plan")
        parsed,pi,q=verify_checkpoint(cp,station_cache)
        rows.extend(parsed);issues.extend(pi)
        quality.append(dict(query_id=query["query_id"],date=query["date"],from_city=query["from_city"],to_city=query["to_city"],from_station=query["from_station"],to_station=query["to_station"],
                            status=q["status"],raw_count=q["raw_count"],valid_count=q["valid_count"],unavailable_count=q["unavailable_count"],unresolved_station_count=q.get("unresolved_station_count",0)))
        sources.append(dict(query_id=query["query_id"],raw_file=cp["source"]["raw_file"],sha256=cp["source"]["sha256"],accessed_at=cp["source"]["accessed_at"]))
    out=ROOT/"data/processed"/job.name
    out.mkdir(exist_ok=True)
    write_csv(out/"targeted_train_records.csv",rows,TRAIN_FIELDS)
    write_csv(out/"targeted_query_quality.csv",quality,QUALITY_FIELDS)
    write_csv(out/"cleaning_issues.csv",issues,ISSUE_FIELDS)
    write_csv(out/"source_register.csv",sources,["query_id","raw_file","sha256","accessed_at"])
    summary=dict(actor=read_project_json(job / 'metadata.json')["actor"],total_queries=len(plan),
                 completed_queries=len(sources),remaining_queries=len(plan)-len(sources),train_records=len(rows),
                 unavailable_timetable_rows=sum(int(q["unavailable_count"]) for q in quality if q["status"]!="not_collected"),
                 unresolved_station_rows=sum(int(q["unresolved_station_count"]) for q in quality if q["status"]!="not_collected"),
                 output_dir=str(out),job_dir=str(job),blocking_error=read_project_json(job / 'blocked.json') if (job/"blocked.json").exists() else None,
                 matrix_ready=False,original_119_queries_still_pending=True)
    write_json(out/"targeted_summary.json",summary)
    return summary


def collect(assessment_dir,actor="user",max_queries=None):
    if actor not in ("user","assistant"):
        raise ValueError("Invalid actor")
    plan,info=plan_for_assessment(assessment_dir)
    protocol={k:v for k,v in info.items() if k not in ("assessment_dir","assessment_sha256")}
    assessment=read_project_json(Path(assessment_dir) / 'assessment_summary.json')
    protocol.update(merged_csv_sha256=assessment["merged_csv_sha256"],target_plan_sha256=assessment["target_plan_sha256"])
    current=datetime.now(TZ)
    if current>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
        raise ValueError("Original 48-hour snapshot deadline passed; preserve data and review a separate version, do not change timestamps")
    if any(not 0<=(date.fromisoformat(q["date"])-current.date()).days<15 for q in plan):
        raise ValueError("A target date is outside the current typical query window")
    if max_queries is None:
        max_queries=len(plan)
    if not isinstance(max_queries,int) or not 0<=max_queries<=len(plan):
        raise ValueError("Invalid max_queries")
    if MARKER.exists():
        job=Path(read_project_json(MARKER)["job_dir"]).resolve()
        if job.parent!=(ROOT/"data/raw").resolve():
            raise ValueError("Invalid saved job directory")
        if read_project_json(job / 'protocol.json')!=protocol or read_project_json(job / 'plan.json')!=plan:
            raise ValueError("Plan or source version changed; do not silently mix")
        meta=read_project_json(job / 'metadata.json')
        if meta["actor"]!=actor or any(not script_hash_matches(ROOT / 'scripts' / n, h) for n,h in meta["code_hashes"].items()):
            raise ValueError("Actor or code version differs")
        if (job/"blocked.json").exists():
            raise ValueError("Blocked request requires review; automatic retry disabled")
    else:
        job=ROOT/"data/raw"/(actor+"_stage1g_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
        job.mkdir(exist_ok=False);(job/"checkpoints").mkdir();(job/"sessions").mkdir()
        write_json(job/"plan.json",plan);write_json(job/"protocol.json",protocol)
        for name in CODE_FILES:
            (job/name).write_bytes((ROOT/"scripts"/name).read_bytes())
        write_json(job/"metadata.json",dict(actor=actor,created_at=now(),assessment_dir=str(assessment_dir),software=software_versions(),
                                           code_hashes={n:sha(ROOT/"scripts"/n) for n in CODE_FILES},parser_version=PARSER_VERSION))
        atomic_json(MARKER,dict(job_dir=str(job)))
    remaining=[q for q in plan if not (job/"checkpoints"/(q["query_id"]+".json")).exists()]
    print("关键站点查询目录：",job,flush=True)
    if not remaining or not max_queries:
        return inspect(job)
    lock=job/"running.lock"
    with lock.open("x",encoding="utf-8") as handle:handle.write(now())
    session=job/"sessions"/datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f");session.mkdir(exist_ok=False)
    client=SourceClient(session,actor,3)
    current_query="initialization"
    try:
        page,_=client.get("query_page",INIT_URL)
        endpoint=re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]",page)
        station_link=re.search(r'src=["\']([^"\']*/station_name\.js[^"\']*)',page)
        field_link=re.search(r'src=["\']([^"\']*/queryLeftTicket_end_js\.js[^"\']*)',page)
        if not endpoint or not station_link or not field_link:
            raise SourceError("Official metadata unavailable")
        urls=[urljoin(INIT_URL,m.group(1)) for m in (station_link,field_link)]
        if any(urlparse(u).netloc!="kyfw.12306.cn" for u in urls):
            raise SourceError("Unexpected metadata host")
        text,station_source=client.get("station_dictionary",urls[0])
        stations=parse_station_dictionary(text)
        by_name={s["station_name"]:s for s in stations};by_code={s["station_code"]:s for s in stations}
        js,_=client.get("official_field_mapping",urls[1]);verify_client_field_map(js)
        for i,q in enumerate(remaining[:max_queries],1):
            current_query=q["query_id"]
            if datetime.now(TZ)>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
                raise SourceError("Snapshot deadline reached")
            if q["from_station"] not in by_name or q["to_station"] not in by_name:
                raise SourceError("Exact planned station absent from current dictionary")
            query=dict(q,from_code=by_name[q["from_station"]]["station_code"],to_code=by_name[q["to_station"]]["station_code"])
            body,source=client.get(current_query,urljoin(BASE,endpoint.group(1)),{
                "leftTicketDTO.train_date":q["date"],"leftTicketDTO.from_station":query["from_code"],"leftTicketDTO.to_station":query["to_code"],"purpose_codes":"ADULT"})
            if datetime.fromisoformat(source["accessed_at"])>=datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
                raise SourceError("Source began after snapshot deadline; raw kept for review")
            records,issues,quality=parse_train_response(body,query,by_code,source)
            cp=dict(query=query,source=source,station_snapshot=station_source,records=records,issues=issues,quality=quality,parser_version=PARSER_VERSION)
            if quality["status"] not in ACCEPTED:
                write_json(session/(current_query+"_quarantined.json"),cp)
                raise SourceError("Unreviewed response records require inspection")
            atomic_json(job/"checkpoints"/(current_query+".json"),cp)
            print(f"{len(plan)-len(remaining)+i}/{len(plan)} {q['date']} {q['from_station']}→{q['to_station']}: {quality['status']}; valid={quality['valid_count']}",flush=True)
    except KeyboardInterrupt:
        print("正常中断，已完成请求可续采。",flush=True)
    except SourceError as error:
        atomic_json(job/"blocked.json",dict(query_id=current_query,error=str(error),at=now(),automatic_retry=False))
        print("查询暂停：",str(error),flush=True)
    finally:
        client.close();lock.unlink()
    return inspect(job)
