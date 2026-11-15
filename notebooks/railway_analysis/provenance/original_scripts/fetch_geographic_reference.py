"""Archive public Natural Earth city-point source; no model fitting."""
from pathlib import Path
import hashlib
import json
from datetime import datetime,timezone,timedelta
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/raw/assistant_geographic_reference_20261114"


def fetch():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest_path=OUT/"source_manifest.json"
    if manifest_path.exists():
        saved=json.loads(manifest_path.read_text(encoding="utf-8"))
        if hashlib.sha256((OUT/"ne_10m_populated_places_simple.geojson").read_bytes()).hexdigest()!=saved["response_sha256"]:
            raise ValueError("Archived geographic source changed")
        return saved
    api="https://api.github.com/repos/nvkelso/natural-earth-vector/commits?path=geojson/ne_10m_populated_places_simple.geojson&per_page=1"
    session=requests.Session();session.headers["User-Agent"]="CourseworkGeographicReference/1.0 source archival"
    response=session.get(api,timeout=(8,30));response.raise_for_status();items=response.json();commit=items[0]["sha"]
    (OUT/"github_file_commit_response.json").write_bytes(response.content)
    url="https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"+commit+"/geojson/ne_10m_populated_places_simple.geojson"
    response=session.get(url,timeout=(8,30));response.raise_for_status();data=response.json()
    if data["type"]!="FeatureCollection":raise ValueError("Not a GeoJSON FeatureCollection")
    (OUT/"ne_10m_populated_places_simple.geojson").write_bytes(response.content)
    result=dict(source="Natural Earth 1:10m Populated Places simple",source_page="https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-populated-places/",
        license_page="https://www.naturalearthdata.com/about/terms-of-use/",license="Public domain",git_commit=commit,
        source_commit_date=items[0]["commit"]["committer"]["date"],download_url=url,
        accessed_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),response_sha256=hashlib.sha256(response.content).hexdigest(),
        bytes=len(response.content),feature_count=len(data["features"]),coordinate_use="City reference points; not railway station or border access point measurements")
    manifest_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


if __name__=="__main__":print(json.dumps(fetch(),ensure_ascii=True))
