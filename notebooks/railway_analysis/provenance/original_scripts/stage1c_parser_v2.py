"""Stable parser v2. Unknown station rows remain excluded and auditable.
No module monkeypatching. Import this same function for collection and export.
"""
import json
from stage1_collect import parse_train_response as _legacy_parse
PARSER_VERSION = "stage1c-station-metadata-v2"


def parse_train_response(body, query, station_map, source):
    rows, issues, quality = _legacy_parse(body, query, station_map, source)
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
            _, remaining_issues, remaining_quality = _legacy_parse(json.dumps(one, ensure_ascii=False), query, temporary, source)
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

