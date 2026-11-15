"""Stage 1 pilot: authentic source snapshots, station mapping and train QA.

Run in Python for Data Analysis (pda312). Dependencies: stdlib + requests.
No route optimization, imputation, penalties, plots, or full matrix here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
BASE = "https://kyfw.12306.cn/otn/"
INIT_URL = BASE + "leftTicket/init"
STATION_URL = BASE + "resources/js/framework/station_name.js"

# Research candidates, not a claim of complete station coverage or current service.
# node_id is an internal identifier; official 12306 station/city codes come from raw data.
NODE_SPECS = [
    ("北京市", "北京", "北京;北京南;北京西;北京丰台;北京朝阳;北京北"),
    ("天津市", "天津", "天津;天津西;天津南"),
    ("河北省", "石家庄", "石家庄;石家庄北"),
    ("山西省", "太原", "太原;太原南"),
    ("内蒙古自治区", "呼和浩特", "呼和浩特;呼和浩特东"),
    ("辽宁省", "沈阳", "沈阳;沈阳北;沈阳南"),
    ("吉林省", "长春", "长春;长春西"),
    ("黑龙江省", "哈尔滨", "哈尔滨;哈尔滨西;哈尔滨东"),
    ("上海市", "上海", "上海;上海虹桥;上海南;上海松江"),
    ("江苏省", "南京", "南京;南京南"),
    ("浙江省", "杭州", "杭州;杭州东;杭州西"),
    ("安徽省", "合肥", "合肥;合肥南"),
    ("福建省", "福州", "福州;福州南"),
    ("江西省", "南昌", "南昌;南昌西;南昌东"),
    ("山东省", "济南", "济南;济南西;济南东"),
    ("河南省", "郑州", "郑州;郑州东"),
    ("湖北省", "武汉", "武汉;汉口;武昌"),
    ("湖南省", "长沙", "长沙;长沙南"),
    ("广东省", "广州", "广州;广州南;广州白云;广州东;广州北;广州新塘"),
    ("广西壮族自治区", "南宁", "南宁;南宁东"),
    ("海南省", "海口", "海口;海口东"),
    ("重庆市", "重庆", "重庆北;重庆西;重庆东;沙坪坝"),
    ("四川省", "成都", "成都;成都东;成都西;成都南"),
    ("贵州省", "贵阳", "贵阳;贵阳北;贵阳东"),
    ("云南省", "昆明", "昆明;昆明南"),
    ("西藏自治区", "拉萨", "拉萨"),
    ("陕西省", "西安", "西安;西安北"),
    ("甘肃省", "兰州", "兰州;兰州西"),
    ("青海省", "西宁", "西宁"),
    ("宁夏回族自治区", "银川", "银川"),
    ("新疆维吾尔自治区", "乌鲁木齐", "乌鲁木齐;乌鲁木齐南"),
    ("香港特别行政区", "香港", "香港西九龙"),
    ("澳门特别行政区", "澳门", ""),
    ("台湾地区", "台北", ""),
]

PILOT_SPECS = [
    ("P01", "北京南", "上海虹桥", "direct_and_related_stations"),
    ("P02", "上海虹桥", "北京南", "reverse_direction"),
    ("P03", "广州南", "香港西九龙", "cross_border"),
    ("P04", "香港西九龙", "广州南", "cross_border_reverse"),
    ("P05", "北京西", "西宁", "candidate_transfer_leg_1"),
    ("P06", "西宁", "拉萨", "candidate_transfer_leg_2_not_yet_connected"),
    ("P07", "广州", "海口", "train_ferry_scope_check"),
    ("P08", "广州南", "横琴", "mainland_access_candidate_not_Macau"),
]

TRAIN_FIELDS = [
    "query_id", "query_date", "train_no", "train_code", "origin_service_date",
    "requested_from", "requested_to", "from_code", "to_code", "from_name", "to_name",
    "same_as_requested_stations", "from_dictionary_city", "to_dictionary_city",
    "departure_clock", "arrival_clock", "duration_text", "duration_min",
    "departure_at", "arrival_at", "arrival_day_offset", "can_web_buy",
    "raw_row_index", "raw_file", "raw_sha256", "measurement_kind",
]
ISSUE_FIELDS = ["query_id", "raw_row_index", "severity", "issue", "details"]
QUERY_FIELDS = [
    "query_id", "date", "from_station", "to_station", "purpose", "status",
    "raw_count", "valid_count", "rejected_count", "duplicate_count", "unavailable_count", "raw_file", "error",
]


def now():
    return datetime.now(TZ).isoformat()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path, rows, fields):
    # UTF-8 BOM is intentional for Excel on Windows; pandas/R can read UTF-8.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def software_versions():
    result = {"python": platform.python_version(), "executable": sys.executable}
    for package in ["requests", "numpy", "pandas", "scipy", "scikit-learn", "umap-learn"]:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not installed / metadata unavailable"
    return result


class SourceError(RuntimeError):
    pass


class SourceClient:
    def __init__(self, raw_dir, actor, interval):
        self.raw_dir = Path(raw_dir)
        self.actor = actor
        self.session = requests.Session()
        self.manifest = []
        self.interval = interval
        self.last_request = None

    def get(self, source_id, url, params=None):
        if self.last_request is not None:
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
        record = dict(source_id=source_id, actor=self.actor, url=url, params=params,
                      accessed_at=now(), publication_date=None,
                      method="HTTPS GET; default TLS verification; no login; no automatic retry",
                      use_limit="Website endpoint, not a documented open-data API; availability and bulk-use permission not established")
        self.manifest.append(record)
        try:
            self.last_request = time.monotonic()
            response = self.session.get(url, params=params, timeout=(10, 20))
            path = self.raw_dir / (source_id + ".bin")
            path.write_bytes(response.content)
            record.update(http_status=response.status_code, final_url=response.url,
                          content_type=response.headers.get("Content-Type"),
                          server_date=response.headers.get("Date"),
                          raw_file=str(path.relative_to(ROOT)), bytes=len(response.content),
                          sha256=hashlib.sha256(response.content).hexdigest())
            if response.status_code != 200:
                raise SourceError(f"HTTP {response.status_code}; stopped without retry")
            if urlparse(response.url).netloc != urlparse(url).netloc:
                raise SourceError("Unexpected cross-domain redirect")
            response.encoding = "utf-8"
            return response.text, record
        except (requests.RequestException, SourceError) as error:
            record["error"] = f"{type(error).__name__}: {error}"
            raise SourceError(record["error"]) from error
        finally:
            write_json(self.raw_dir / "source_manifest.json", self.manifest)

    def close(self):
        self.session.close()


def parse_station_dictionary(text):
    match = re.search(r"var\s+station_names\s*=\s*(['\"])(.*?)\1", text, re.S)
    if not match:
        raise SourceError("Station dictionary schema changed or response is not station JavaScript")
    rows, seen = [], set()
    for entry in match.group(2).split("@"):
        if not entry:
            continue
        fields = entry.split("|")
        if len(fields) < 8 or not re.fullmatch(r"[A-Z]{3}", fields[2]):
            raise SourceError("Unexpected station dictionary record")
        if fields[2] in seen:
            raise SourceError(f"Duplicate station code: {fields[2]}")
        seen.add(fields[2])
        rows.append(dict(station_name=fields[1], station_code=fields[2], pinyin=fields[3],
                         source_city_code=fields[6], source_city_name=fields[7]))
    if len(rows) < 100:
        raise SourceError("Station dictionary unexpectedly small")
    return rows


def build_node_draft(stations):
    by_name = {row["station_name"]: row for row in stations}
    nodes, candidates = [], []
    for i, (province, city, names) in enumerate(NODE_SPECS, 1):
        node_id = f"N{i:02d}"
        for name in filter(None, names.split(";")):
            station = by_name.get(name, {})
            candidates.append(dict(node_id=node_id, city=city, station_name=name,
                                   station_code=station.get("station_code", ""),
                                   dictionary_city=station.get("source_city_name", ""),
                                   dictionary_city_code=station.get("source_city_code", ""),
                                   status="dictionary_match_service_unverified" if station else "not_in_dictionary",
                                   selected_for_final_network="pending"))
        if city == "香港":
            reason = "特别行政区代表；国铁查询接入候选为香港西九龙"
        elif city == "澳门":
            reason = "特别行政区代表；轻轨与内地城际接驳另行核验，不以珠海替代澳门"
        elif city == "台北":
            reason = "台湾地区代表性核心铁路枢纽；保留跨海结构性不可达标记"
        else:
            reason = "省会、自治区首府或直辖市代表"
        nodes.append(dict(node_id=node_id, province=province, representative_city=city,
                          city_code=node_id, city_code_system="internal research identifier, not administrative code",
                          longitude="", latitude="", coordinate_crs="pending", coordinate_source="pending",
                          candidate_stations=names or ("澳门轻轨接入点待选" if city == "澳门" else "台北站（台湾本地系统，待核验）"),
                          selection_basis=reason, status="draft_not_matrix_ready"))
    assert len(nodes) == 34 and len({r["province"] for r in nodes}) == 34
    return nodes, candidates


def verify_client_field_map(js):
    # Verify positional fields against 12306's downloaded rendering JavaScript.
    fields = {"train_no": 2, "station_train_code": 3, "from_station_telecode": 6,
              "to_station_telecode": 7, "start_time": 8, "arrive_time": 9,
              "lishi": 10, "canWebBuy": 11, "start_train_date": 13}
    for name, index in fields.items():
        expression = rf"\.{name}\s*=\s*[A-Za-z_$][\w$]*\[{index}\]"
        if not re.search(expression, js):
            raise SourceError(f"Official field mapping not verified: {name}[{index}]")
    return fields


def parse_train_response(body, query, station_by_code, source):
    try:
        obj = json.loads(body)
    except ValueError as error:
        raise SourceError("Train endpoint did not return JSON; no retry") from error
    if not isinstance(obj, dict) or obj.get("status") is not True:
        raise SourceError("Train query did not declare success")
    if obj.get("httpstatus") != 200:
        raise SourceError("Unexpected application HTTP status")
    data = obj.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("result"), list):
        raise SourceError("Train result schema changed")
    names = data.get("map", {})
    if not isinstance(names, dict):
        raise SourceError("Station name mapping schema changed")
    accepted, issues, seen = [], [], set()
    duplicates = rejected = unavailable = 0
    day = date.fromisoformat(query["date"])
    for index, raw in enumerate(data["result"]):
        try:
            if not isinstance(raw, str):
                raise ValueError("row is not pipe-delimited text")
            f = raw.split("|")
            if len(f) < 18:
                raise ValueError("too few fields")
            # Exact observed placeholder combination; never coerce these to real times.
            # Unrecognized 24:00 values still fail normal clock validation below.
            placeholder = (f[8:11] == ["24:00", "24:00", "99:59"]
                           and f[11] == "IS_TIME_NOT_BUY"
                           and "列车运行图调整" in f[1] and "暂停发售" in f[1])
            if placeholder:
                if not f[2] or not f[3] or any(code not in station_by_code for code in (f[6], f[7])):
                    raise ValueError("Unverified train/station identity in placeholder row")
                if not re.fullmatch(r"\d{8}", f[13]):
                    raise ValueError("Invalid origin date in placeholder row")
                if datetime.strptime(f[13], "%Y%m%d").date() > day:
                    raise ValueError("Placeholder origin date later than boarding date")
                unavailable += 1
                issues.append(dict(query_id=query["query_id"], raw_row_index=index,
                                   severity="missing_data", issue="timetable_unavailable_adjustment",
                                   details=json.dumps(dict(
                                       train_no=f[2], train_code=f[3], query_date=query["date"],
                                       from_code=f[6], to_code=f[7], source_message=f[1],
                                       raw_departure=f[8], raw_arrival=f[9], raw_duration=f[10],
                                       sale_status=f[11], raw_file=source["raw_file"],
                                       raw_sha256=source["sha256"]), ensure_ascii=False)))
                continue
            for clock in (f[8], f[9]):
                if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock):
                    raise ValueError(f"invalid clock: {clock}")
            if not re.fullmatch(r"\d{1,3}:[0-5]\d", f[10]):
                raise ValueError(f"invalid elapsed duration: {f[10]}")
            hours, minutes = map(int, f[10].split(":"))
            duration = hours * 60 + minutes
            if duration <= 0 or f[6] == f[7]:
                raise ValueError("nonpositive duration or identical endpoints")
            if not f[2] or not f[3]:
                raise ValueError("missing train identity")
            if not re.fullmatch(r"\d{8}", f[13]):
                raise ValueError("invalid origin service date")
            origin_day = datetime.strptime(f[13], "%Y%m%d").date()
            if origin_day > day:
                raise ValueError("train origin date after requested boarding date")
            # f[13] belongs to the train origin, NOT necessarily the boarding station.
            departure = datetime.fromisoformat(query["date"] + "T" + f[8]).replace(tzinfo=TZ)
            arrival = departure + timedelta(minutes=duration)
            if arrival.strftime("%H:%M") != f[9]:
                raise ValueError("departure + elapsed duration disagrees with arrival clock")
            for code in (f[6], f[7]):
                if code not in station_by_code:
                    raise ValueError(f"station code absent from saved dictionary: {code}")
                if code in names and names[code] != station_by_code[code]["station_name"]:
                    raise ValueError(f"station-name disagreement: {code}")
            key = (f[2], query["date"], f[6], f[7], f[8])
            if key in seen:
                duplicates += 1
                issues.append(dict(query_id=query["query_id"], raw_row_index=index,
                                   severity="warning", issue="duplicate", details=str(key)))
                continue
            seen.add(key)
            row = dict(
                query_id=query["query_id"], query_date=query["date"], train_no=f[2], train_code=f[3],
                origin_service_date=origin_day.isoformat(), requested_from=query["from_station"],
                requested_to=query["to_station"], from_code=f[6], to_code=f[7],
                from_name=station_by_code[f[6]]["station_name"], to_name=station_by_code[f[7]]["station_name"],
                same_as_requested_stations=(f[6] == query["from_code"] and f[7] == query["to_code"]),
                from_dictionary_city=station_by_code[f[6]]["source_city_name"],
                to_dictionary_city=station_by_code[f[7]]["source_city_name"],
                departure_clock=f[8], arrival_clock=f[9], duration_text=f[10], duration_min=duration,
                departure_at=departure.isoformat(), arrival_at=arrival.isoformat(),
                arrival_day_offset=(arrival.date() - day).days, can_web_buy=f[11],
                raw_row_index=index, raw_file=source["raw_file"], raw_sha256=source["sha256"],
                measurement_kind="queried_train_schedule_not_measured_actual_travel",
            )
            accepted.append(row)
            if duration > 2880:
                issues.append(dict(query_id=query["query_id"], raw_row_index=index,
                                   severity="review", issue="duration_over_48h_retained", details=str(duration)))
        except (ValueError, TypeError, IndexError) as error:
            rejected += 1
            issues.append(dict(query_id=query["query_id"], raw_row_index=index,
                               severity="error", issue="record_quarantined", details=str(error)))
    if rejected:
        status = "partial_parse_needs_review"
    elif unavailable:
        status = "partial_timetable_unavailable"
    elif not data["result"]:
        status = "no_direct_train_returned_not_unreachable"
    else:
        status = "validated_records"
    return accepted, issues, dict(status=status, raw_count=len(data["result"]),
                                  valid_count=len(accepted), rejected_count=rejected,
                                  duplicate_count=duplicates, unavailable_count=unavailable)


def collect_pilot(actor="user"):
    if actor not in ("user", "assistant"):
        raise ValueError("actor must be user or assistant")
    config_path = ROOT / "config/research_protocol.json"
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if len(PILOT_SPECS) > config["max_pilot_queries"]:
        raise ValueError("Pilot query count exceeds the configured limit")
    query_day = date.fromisoformat(config["query_date"])
    if query_day < datetime.now(TZ).date():
        raise ValueError("Frozen query date has passed. Review a new date explicitly; this script will not silently redate queries.")
    run_id = actor + "_pilot_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f")
    raw_dir, output_dir = ROOT / "data/raw" / run_id, ROOT / "data/processed" / run_id
    raw_dir.mkdir(parents=True, exist_ok=False)
    output_dir.mkdir(parents=True, exist_ok=False)
    (raw_dir / "research_protocol.json").write_bytes(config_bytes)
    (raw_dir / "stage1_collect.py").write_bytes(Path(__file__).read_bytes())
    metadata = dict(run_id=run_id, actor=actor, started_at=now(), query_date=config["query_date"],
                    protocol_sha256=hashlib.sha256(config_bytes).hexdigest(),
                    software=software_versions(), seed=config["seed"],
                    note="No stochastic algorithm executed. Pilot is not a full matrix or a shortest-route experiment.")
    client = SourceClient(raw_dir, actor, config["request_interval_seconds"])
    queries, records, issues, nodes, candidates = [], [], [], [], []
    fatal_error = None
    try:
        page, _ = client.get("query_page", INIT_URL)
        endpoint_match = re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]", page)
        if not endpoint_match:
            raise SourceError("Query endpoint not found in official page; stop, do not guess alternatives")
        endpoint = urljoin(BASE, endpoint_match.group(1))
        station_match = re.search(r'(?:src)=["\']([^"\']*/station_name\.js[^"\']*)', page)
        if not station_match:
            raise SourceError("Versioned station dictionary URL missing from official page")
        station_url = urljoin(INIT_URL, station_match.group(1))
        if urlparse(station_url).netloc != "kyfw.12306.cn":
            raise SourceError("Unexpected station dictionary host")
        station_js, _ = client.get("station_dictionary", station_url)
        stations = parse_station_dictionary(station_js)
        by_name = {r["station_name"]: r for r in stations}
        by_code = {r["station_code"]: r for r in stations}
        write_csv(output_dir / "station_dictionary.csv", stations, list(stations[0]))
        nodes, candidates = build_node_draft(stations)
        write_csv(output_dir / "nodes_34_draft.csv", nodes, list(nodes[0]))
        write_csv(output_dir / "station_candidates.csv", candidates, list(candidates[0]))
        js_match = re.search(r'src=["\']([^"\']*/queryLeftTicket_end_js\.js[^"\']*)', page)
        if not js_match:
            raise SourceError("Official parsing JavaScript link absent")
        js_url = urljoin(INIT_URL, js_match.group(1))
        if urlparse(js_url).netloc != "kyfw.12306.cn":
            raise SourceError("Unexpected client JavaScript host")
        js, _ = client.get("official_field_mapping", js_url)
        metadata["verified_field_mapping"] = verify_client_field_map(js)
        for query_id, a, b, purpose in PILOT_SPECS:
            if a not in by_name or b not in by_name:
                raise SourceError(f"Pilot station absent from dictionary: {a} / {b}")
            query = dict(query_id=query_id, date=config["query_date"], from_station=a,
                         to_station=b, purpose=purpose, from_code=by_name[a]["station_code"],
                         to_code=by_name[b]["station_code"])
            public = {k: v for k, v in query.items() if k not in ("from_code", "to_code")}
            try:
                body, source = client.get(query_id, endpoint, {
                    "leftTicketDTO.train_date": query["date"],
                    "leftTicketDTO.from_station": query["from_code"],
                    "leftTicketDTO.to_station": query["to_code"], "purpose_codes": "ADULT"})
                parsed, errors, quality = parse_train_response(body, query, by_code, source)
                records.extend(parsed)
                issues.extend(errors)
                public.update(quality, raw_file=source["raw_file"], error="")
                queries.append(public)
                print(f"{query_id} {a} → {b}: {quality['status']}, valid={quality['valid_count']}, rejected={quality['rejected_count']}", flush=True)
                if quality["rejected_count"]:
                    raise SourceError("Record validation failed; remaining pilot queries stopped for review")
            except SourceError as error:
                if not queries or queries[-1]["query_id"] != query_id:
                    public.update(status="request_or_schema_failed_not_unreachable", raw_count="", valid_count="",
                                  rejected_count="", duplicate_count="", raw_file="", error=str(error))
                    queries.append(public)
                raise
    except SourceError as error:
        fatal_error = str(error)
    finally:
        client.close()
        attempted = {q["query_id"] for q in queries}
        for query_id, a, b, purpose in PILOT_SPECS:
            if query_id not in attempted:
                queries.append(dict(query_id=query_id, date=config["query_date"], from_station=a, to_station=b,
                                    purpose=purpose, status="not_attempted", raw_count="", valid_count="",
                                    rejected_count="", duplicate_count="", raw_file="", error=""))
        write_csv(output_dir / "pilot_train_records.csv", records, TRAIN_FIELDS)
        write_csv(output_dir / "pilot_query_quality.csv", queries, QUERY_FIELDS)
        write_csv(output_dir / "cleaning_issues.csv", issues, ISSUE_FIELDS)
        summary = dict(run_id=run_id, actor=actor, query_date=config["query_date"],
                       node_count=len(nodes), candidate_station_count=len(candidates),
                       missing_candidate_stations=sum(r["status"] == "not_in_dictionary" for r in candidates),
                       attempted_queries=sum(r["status"] != "not_attempted" for r in queries),
                       validated_queries=sum(r["status"] == "validated_records" for r in queries),
                       train_record_count=len(records), issue_count=len(issues), fatal_error=fatal_error,
                       raw_dir=str(raw_dir), output_dir=str(output_dir), matrix_ready=False)
        metadata.update(finished_at=now(), summary=summary)
        write_json(raw_dir / "run_metadata.json", metadata)
        write_json(output_dir / "pilot_summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", choices=["user", "assistant"], default="user")
    args = parser.parse_args()
    result = collect_pilot(actor=args.actor)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["fatal_error"]:
        raise SystemExit(2)
