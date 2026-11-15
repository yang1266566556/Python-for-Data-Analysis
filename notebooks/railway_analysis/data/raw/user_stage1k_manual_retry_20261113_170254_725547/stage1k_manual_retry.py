"""One reviewed manual retry branch after an initialization-only timeout.

The failed job, old marker and frozen parser remain unchanged. Each HTTP
request has no automatic retry; repeated execution reuses this branch.
"""
import hashlib
import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from stage1_collect import (ROOT, TZ, BASE, INIT_URL, SourceClient, SourceError, now,
    parse_station_dictionary, verify_client_field_map, write_json, software_versions)
from stage1c_parser_v2 import parse_train_response, PARSER_VERSION
from stage1e_followups import atomic_json, ACCEPTED, verify_checkpoint
from stage1k_residual import make_plan, inspect, validated_j_records
from stage1i_dated_schedule import sha
from stage1k_matrix import evaluate

FAILED_JOB = "user_stage1k_20261113_164250_874496"
RETRY_MARKER = ROOT / "evidence/stage1k_manual_retry_current_job.json"
TIMEOUT = (30, 45)
CODE_FILES = ["stage1k_manual_retry.py", "stage1k_residual.py", "stage1k_matrix.py",
              "stage1j_restore.py", "stage1d_routes.py", "stage1c_parser_v2.py", "stage1_collect.py"]


def review_failure():
    job = ROOT / "data/raw" / FAILED_JOB
    if (job / "running.lock").exists() or list((job / "checkpoints").glob("*.json")):
        raise ValueError("Original branch has active work or train checkpoints; review reuse first")
    blocked = json.loads((job / "blocked.json").read_text(encoding="utf-8"))
    if blocked["query_id"] != "initialization" or not blocked["error"].startswith("ReadTimeout:"):
        raise ValueError("This retry only covers the reviewed initial-page timeout, not denials/schema errors")
    sources = []
    for path in (job / "sessions").glob("*/source_manifest.json"):
        sources.extend(json.loads(path.read_text(encoding="utf-8")))
    if len(sources) != 1 or sources[0]["source_id"] != "query_page" or sources[0]["url"] != INIT_URL or "http_status" in sources[0]:
        raise ValueError("Original failure is not the single reviewed page timeout")
    if not sources[0].get("error", "").startswith("ReadTimeout:"):
        raise ValueError("Original source failure differs")
    plan, _, protocol = make_plan()
    if json.loads((job / "plan.json").read_text(encoding="utf-8")) != plan or json.loads((job / "protocol.json").read_text(encoding="utf-8")) != protocol:
        raise ValueError("Original query plan/source version changed")
    meta = json.loads((job / "metadata.json").read_text(encoding="utf-8"))
    for filename, checksum in meta["code_hashes"].items():
        if sha(job / filename) != checksum or sha(ROOT / "scripts" / filename) != checksum:
            raise ValueError("Pinned original collector version changed")
    return dict(failed_job=FAILED_JOB, initialization_timeout_verified=True, old_completed_train_queries=0,
                failed_branch_unchanged=True, timeout_connect_seconds=30, timeout_read_seconds=45,
                automatic_retry=False, snapshot_deadline_exclusive=protocol["snapshot_deadline_exclusive"])


class LongerTimeoutClient(SourceClient):
    """Explicit timeout configuration; no global monkeypatch of the old client."""
    def get(self, source_id, url, params=None):
        if self.last_request is not None:
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
        record = dict(source_id=source_id, actor=self.actor, url=url, params=params, accessed_at=now(), publication_date=None,
                      method="HTTPS GET; default TLS verification; no login; no automatic retry; explicit timeout=(30,45)",
                      timeout_connect_seconds=30, timeout_read_seconds=45,
                      use_limit="Official public website endpoint; not a documented open-data API; bulk permission not established")
        self.manifest.append(record)
        try:
            self.last_request = time.monotonic()
            response = self.session.get(url, params=params, timeout=TIMEOUT, verify=True)
            path = self.raw_dir / (source_id + ".bin")
            path.write_bytes(response.content)
            record.update(http_status=response.status_code, final_url=response.url, content_type=response.headers.get("Content-Type"),
                          server_date=response.headers.get("Date"), raw_file=str(path.relative_to(ROOT)), bytes=len(response.content),
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


def collect_once(actor="user"):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    review = review_failure()
    plan, _, protocol = make_plan()
    if RETRY_MARKER.exists():
        job = Path(json.loads(RETRY_MARKER.read_text(encoding="utf-8"))["job_dir"]).resolve()
        if job.parent != (ROOT / "data/raw").resolve():
            raise ValueError("Invalid retry job directory")
        if json.loads((job / "plan.json").read_text(encoding="utf-8")) != plan or json.loads((job / "protocol.json").read_text(encoding="utf-8")) != protocol:
            raise ValueError("Retry query plan/source version changed")
        meta = json.loads((job / "metadata.json").read_text(encoding="utf-8"))
        if meta["actor"] != actor or any(sha(ROOT / "scripts" / n) != h for n, h in meta["code_hashes"].items()):
            raise ValueError("Retry actor or source code changed")
        if (job / "blocked.json").exists():
            print("手动重试分支也已暂停；未重复请求，请回传输出。", flush=True)
            return inspect(job)
    else:
        if datetime.now(TZ) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
            raise ValueError("Original 48-hour snapshot deadline passed; no silent extension")
        job = ROOT / "data/raw" / (actor + "_stage1k_manual_retry_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
        job.mkdir(exist_ok=False); (job / "checkpoints").mkdir(); (job / "sessions").mkdir()
        write_json(job / "plan.json", plan); write_json(job / "protocol.json", protocol)
        write_json(job / "manual_retry_review.json", review)
        for n in CODE_FILES:
            (job / n).write_bytes((ROOT / "scripts" / n).read_bytes())
        write_json(job / "metadata.json", dict(actor=actor, created_at=now(), software=software_versions(), parser_version=PARSER_VERSION,
                   manual_retry_of=FAILED_JOB, automatic_retry=False, timeout_seconds=list(TIMEOUT), code_hashes={n: sha(ROOT / "scripts" / n) for n in CODE_FILES}))
        atomic_json(RETRY_MARKER, dict(job_dir=str(job)))
    remaining = [p for p in plan if not (job / "checkpoints" / (p["query_id"] + ".json")).exists()]
    if not remaining:
        print("手动分支6组已有响应，直接复用。", flush=True)
        return inspect(job)
    if datetime.now(TZ) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]) or any(not 0 <= (date.fromisoformat(p["date"]) - datetime.now(TZ).date()).days < 15 for p in remaining):
        raise ValueError("Frozen acquisition/query-date window expired")
    lock = job / "running.lock"
    with lock.open("x", encoding="utf-8") as f:
        f.write(now())
    session = job / "sessions" / datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"); session.mkdir(exist_ok=False)
    client = LongerTimeoutClient(session, actor, 3); current = "initialization"
    try:
        print("正在读取官方首页；连接/读取超时上限30/45秒，无自动重试。", flush=True)
        page, _ = client.get("query_page", INIT_URL)
        endpoint = re.search(r"var\s+CLeftTicketUrl\s*=\s*['\"](leftTicket/query[A-Za-z]*)['\"]", page)
        station_link = re.search(r'src=["\x27]([^"\x27]*/station_name\.js[^"\x27]*)', page)
        field_link = re.search(r'src=["\x27]([^"\x27]*/queryLeftTicket_end_js\.js[^"\x27]*)', page)
        if not endpoint or not station_link or not field_link:
            raise SourceError("Official metadata missing or changed; no bypass")
        urls = [urljoin(INIT_URL, x[1]) for x in (station_link, field_link)]
        if any(urlparse(u).netloc != "kyfw.12306.cn" for u in urls):
            raise SourceError("Unexpected metadata host")
        text, station_source = client.get("station_dictionary", urls[0])
        stations = parse_station_dictionary(text)
        by_name = {s["station_name"]: s for s in stations}; by_code = {s["station_code"]: s for s in stations}
        js, _ = client.get("official_field_mapping", urls[1]); verify_client_field_map(js)
        for p in remaining:
            current = p["query_id"]
            if datetime.now(TZ) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
                raise SourceError("Snapshot deadline reached")
            if any(p[k] not in by_name for k in ("from_station", "to_station")):
                raise SourceError("Exact station absent from official dictionary")
            q = dict(p, from_code=by_name[p["from_station"]]["station_code"], to_code=by_name[p["to_station"]]["station_code"])
            body, source = client.get(current, urljoin(BASE, endpoint[1]), {"leftTicketDTO.train_date": q["date"], "leftTicketDTO.from_station": q["from_code"], "leftTicketDTO.to_station": q["to_code"], "purpose_codes": "ADULT"})
            if datetime.fromisoformat(source["accessed_at"]) >= datetime.fromisoformat(protocol["snapshot_deadline_exclusive"]):
                raise SourceError("Request outside source deadline")
            rows, issues, quality = parse_train_response(body, q, by_code, source)
            cp = dict(query=q, source=source, station_snapshot=station_source, records=rows, issues=issues, quality=quality, parser_version=PARSER_VERSION)
            if quality["status"] not in ACCEPTED:
                write_json(session / (current + "_quarantined.json"), cp)
                raise SourceError("Unreviewed records require inspection")
            atomic_json(job / "checkpoints" / (current + ".json"), cp)
            print(current, p["date"], p["from_station"] + "→" + p["to_station"], quality["status"], "valid=", quality["valid_count"], flush=True)
    except KeyboardInterrupt:
        print("正常中断，已保存请求保留。", flush=True)
    except SourceError as error:
        atomic_json(job / "blocked.json", dict(query_id=current, error=str(error), at=now(), automatic_retry=False))
        print("手动分支暂停：", str(error), flush=True)
    finally:
        client.close(); lock.unlink()
    return inspect(job)


def analyze(actor="user"):
    if not RETRY_MARKER.exists():
        raise ValueError("Run the manual retry branch first")
    job = Path(json.loads(RETRY_MARKER.read_text(encoding="utf-8"))["job_dir"])
    if job.resolve().parent != (ROOT / "data/raw").resolve() or (job / "running.lock").exists():
        raise ValueError("Invalid or running manual retry branch")
    summary = inspect(job)
    if summary["remaining_queries"] or summary["blocking_error"]:
        raise ValueError("Manual branch incomplete or blocked; no matrix completeness claim")
    meta = json.loads((job / "metadata.json").read_text(encoding="utf-8"))
    if meta["actor"] != actor or any(sha(ROOT / "scripts" / n) != h for n, h in meta["code_hashes"].items()):
        raise ValueError("Manual branch actor or frozen code version changed")
    plan, _, protocol = make_plan()
    if json.loads((job / "plan.json").read_text(encoding="utf-8")) != plan or json.loads((job / "protocol.json").read_text(encoding="utf-8")) != protocol:
        raise ValueError("Manual branch plan/version changed")
    original, _, directory = validated_j_records()
    new, cache = [], {}
    for p in plan:
        cp = json.loads((job / "checkpoints" / (p["query_id"] + ".json")).read_text(encoding="utf-8"))
        rows, _, q = verify_checkpoint(cp, cache)
        if q["rejected_count"]:
            raise ValueError("Unreviewed parser records")
        new.extend(rows)
    metadata = dict(base_job=directory.name, base_records=len(original), new_records=len(new), six_query_job=job.name,
                    all_six_requests_returned=True, manual_retry_of=FAILED_JOB, original_failure_preserved=True,
                    unavailable_timetable_rows=summary["unavailable_timetable_rows"], unresolved_station_rows=summary["unresolved_station_rows"],
                    manual_retry_script_sha256=sha(Path(__file__)), new_network_requests_in_analysis=0)
    return evaluate(original + new, metadata, actor)
