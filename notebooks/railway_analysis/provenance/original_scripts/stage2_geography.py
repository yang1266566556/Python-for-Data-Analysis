"""Audited city reference geometry and user-run geographical comparisons."""
import json
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata,spearmanr

from stage1_collect import ROOT,TZ,write_csv,write_json
from stage1b_transfer import read_csv
from stage1i_dated_schedule import sha
from stage2_inputs import current_inputs,read_matrix,FINAL_JOB
from stage2_experiments import current_plan,verify_and_summarize,model_label,read_coords
from stage2_baseline import external_metrics

SOURCE=ROOT/"data/raw/assistant_geographic_reference_20261114"
MATCH=ROOT/"config/geographic_node_match_34.csv"
REFERENCE_MARKER=ROOT/"evidence/stage2_geographic_reference_current.json"
RESULT_MARKER=ROOT/"evidence/stage2_geographic_analysis_current.json"
EARTH_RADIUS_KM=6371.0088
PROJECTION_LON=105.
PROJECTION_LAT=35.


def haversine_matrix(lonlat,radius=EARTH_RADIUS_KM):
    xy=np.asarray(lonlat,dtype=float)
    if xy.ndim!=2 or xy.shape[1]!=2 or not np.isfinite(xy).all():raise ValueError("Invalid lon/lat")
    if (abs(xy[:,0])>180).any() or (abs(xy[:,1])>90).any():raise ValueError("Invalid geographic range")
    lon,lat=np.deg2rad(xy).T
    dlon=lon[:,None]-lon[None,:];dlat=lat[:,None]-lat[None,:]
    a=np.sin(dlat/2)**2+np.cos(lat[:,None])*np.cos(lat[None,:])*np.sin(dlon/2)**2
    result=2*radius*np.arcsin(np.sqrt(np.clip(a,0,1)));np.fill_diagonal(result,0)
    return result


def project_aeqd(lonlat,lon0=PROJECTION_LON,lat0=PROJECTION_LAT,radius=EARTH_RADIUS_KM):
    """Spherical azimuthal equidistant projection, output kilometres."""
    xy=np.asarray(lonlat,dtype=float);lon,lat=np.deg2rad(xy).T;lam0,phi0=np.deg2rad([lon0,lat0])
    delta=lon-lam0;cosc=np.sin(phi0)*np.sin(lat)+np.cos(phi0)*np.cos(lat)*np.cos(delta)
    c=np.arccos(np.clip(cosc,-1,1))
    if (cosc<=-1+1e-12).any():raise ValueError("Projection undefined at antipode")
    k=np.ones_like(c);np.divide(c,np.sin(c),out=k,where=abs(c)>1e-10)
    return np.column_stack([radius*k*np.cos(lat)*np.sin(delta),radius*k*(np.cos(phi0)*np.sin(lat)-np.sin(phi0)*np.cos(lat)*np.cos(delta))])


def source_features():
    manifest=json.loads((SOURCE/"source_manifest.json").read_text(encoding="utf-8"))
    path=SOURCE/"ne_10m_populated_places_simple.geojson"
    if sha(path)!=manifest["response_sha256"]:raise ValueError("Geographic source bytes changed")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data["crs"]["properties"]["name"]!="urn:ogc:def:crs:OGC:1.3:CRS84":raise ValueError("Unexpected coordinate CRS")
    return manifest,{str(f["properties"]["ne_id"]):f for f in data["features"]}


def prepare_reference(actor="user"):
    if actor not in ("user","assistant"):raise ValueError("Invalid actor")
    inputs,input_manifest,_=current_inputs();nodes=read_csv(inputs/"nodes_34.csv");matches=read_csv(MATCH)
    source,features=source_features()
    if len(matches)!=34 or [r["node_id"] for r in matches]!=[n["node_id"] for n in nodes]:raise ValueError("Geographic node matching differs")
    special={r["node_id"]:r for r in read_csv(ROOT/"data/processed"/FINAL_JOB/"special_region_node_definitions.csv")}
    rows=[];selected=[]
    for node,match in zip(nodes,matches):
        if node["representative_city"]!=match["representative_city"]:raise ValueError("City match differs")
        feature=features[match["source_ne_id"]]
        if feature["properties"]["nameascii"]!=match["source_nameascii"]:raise ValueError("Feature name differs")
        if feature["geometry"]["type"]!="Point":raise ValueError("Reference is not a city point")
        lon,lat=feature["geometry"]["coordinates"]
        if not 73<lon<136 or not 18<lat<54:raise ValueError("City point outside expected broad range")
        detail=special.get(node["node_id"],{})
        row=dict(node);row.update(longitude=lon,latitude=lat,coordinate_crs="OGC:CRS84 / WGS84 lon-lat degrees",coordinate_source=source["download_url"],
            status="geographic_city_reference_ready",coordinate_role="generalized city reference point; not surveyed station/access coordinates",
            source_feature_id=match["source_ne_id"],source_feature_name=feature["properties"]["name"],source_commit_date=source["source_commit_date"],
            operational_network_point=detail.get("representative_point","city railway station set; see candidate_stations and audited source records"),
            mainland_rail_gateway=detail.get("mainland_rail_gateway",""),special_connection_mode=detail.get("connection_mode",""),
            reference_to_access_time_added=False)
        rows.append(row);selected.append(feature)
    xy=np.array([[r["longitude"],r["latitude"]] for r in rows]);projected=project_aeqd(xy);distance=haversine_matrix(xy)
    if len(np.unique(xy,axis=0))!=34 or not np.isfinite(projected).all():raise ValueError("Duplicate or invalid coordinates")
    for i,row in enumerate(rows):row.update(aeqd_x_km=float(projected[i,0]),aeqd_y_km=float(projected[i,1]))
    out=ROOT/"data/analysis"/(actor+"_stage2_geographic_reference_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True)
    write_csv(out/"nodes_34_geographic_reference.csv",rows,list(rows[0]));ids=[r["node_id"] for r in rows]
    pd.DataFrame(distance,index=ids,columns=ids).to_csv(out/"geographic_distance_km_34.csv",encoding="utf-8-sig")
    write_json(out/"selected_source_features_34.geojson",dict(type="FeatureCollection",features=selected))
    graticule=[]
    for lon in (80,90,100,110,120,130):
        ll=np.column_stack([np.full(81,lon),np.linspace(15,55,81)]);pts=project_aeqd(ll)
        graticule.extend(dict(line_id="lon_"+str(lon),longitude=float(ll[i,0]),latitude=float(ll[i,1]),x_km=float(p[0]),y_km=float(p[1])) for i,p in enumerate(pts))
    for lat in (20,30,40,50):
        ll=np.column_stack([np.linspace(75,135,121),np.full(121,lat)]);pts=project_aeqd(ll)
        graticule.extend(dict(line_id="lat_"+str(lat),longitude=float(ll[i,0]),latitude=float(ll[i,1]),x_km=float(p[0]),y_km=float(p[1])) for i,p in enumerate(pts))
    write_csv(out/"projected_graticule.csv",graticule,list(graticule[0]))
    result=dict(output_dir=str(out),actor=actor,node_count=34,source=source,source_manifest_sha256=sha(SOURCE/"source_manifest.json"),match_sha256=sha(MATCH),
        input_manifest_sha256=sha(inputs/"input_manifest.json"),reference_code_sha256=sha(Path(__file__)),earth_radius_km=EARTH_RADIUS_KM,
        projection=dict(method="spherical azimuthal equidistant",central_longitude=PROJECTION_LON,central_latitude=PROJECTION_LAT,unit="km",proj_equivalent="+proj=aeqd +lon_0=105 +lat_0=35 +R=6371008.8"),
        pairwise_method="haversine great-circle distances on sphere; not Euclidean longitude/latitude",
        geography_crs="OGC:CRS84 (WGS84 longitude, latitude order)",station_coordinates=False,rail_time_matrix_changed=False,
        limitations=["Generalized city-point source, not exact station/border positions or 2026 city boundaries","Source geometry coordinates used consistently; attribute latitude/longitude fields not mixed in",
            "Province and representative-city definitions retained from user34 list; external administrative metadata not adopted",
            "Macau point is for city geographical comparison, operational endpoint remains Macau-side Border Gate with stated access assumption",
            "Spherical approximation; projection preserves distances from center, not all intercity pairs","No extra time from city reference point to operational stations has been added"],
        files_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    write_json(out/"reference_manifest.json",result)
    if actor=="user":write_json(REFERENCE_MARKER,dict(output_dir=str(out),manifest_sha256=sha(out/"reference_manifest.json")))
    return result


def current_reference():
    marker=json.loads(REFERENCE_MARKER.read_text(encoding="utf-8"));out=Path(marker["output_dir"])
    if sha(out/"reference_manifest.json")!=marker["manifest_sha256"]:raise ValueError("Geographic reference manifest changed")
    manifest=json.loads((out/"reference_manifest.json").read_text(encoding="utf-8"))
    inputs,_,_=current_inputs()
    if manifest["input_manifest_sha256"]!=sha(inputs/"input_manifest.json") or manifest["reference_code_sha256"]!=sha(Path(__file__)):raise ValueError("Reference input or code changed")
    source_features()
    if manifest["source_manifest_sha256"]!=sha(SOURCE/"source_manifest.json") or manifest["match_sha256"]!=sha(MATCH):raise ValueError("Source mapping changed")
    for name,digest in manifest["files_sha256"].items():
        if sha(out/name)!=digest:raise ValueError("Reference output changed")
    nodes=read_csv(out/"nodes_34_geographic_reference.csv");ids=[r["node_id"] for r in nodes]
    distance=read_matrix(out/"geographic_distance_km_34.csv").to_numpy(dtype=float)
    if len(ids)!=34 or not np.allclose(distance,haversine_matrix([[float(r["longitude"]),float(r["latitude"])] for r in nodes])):raise ValueError("Geographic distances differ")
    return out,manifest,nodes,distance


def similarity_alignment(embedding,geography,fit_mask=None):
    """Fit isotropic scale + rotation/reflection + translation to projected km."""
    a=np.asarray(embedding,dtype=float);b=np.asarray(geography,dtype=float)
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=2 or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError("Invalid alignment coordinates")
    mask=np.ones(len(a),dtype=bool) if fit_mask is None else np.asarray(fit_mask,dtype=bool)
    if mask.shape!=(len(a),) or mask.sum()<3:raise ValueError("Not enough fitting nodes")
    ca=a[mask].mean(axis=0);cb=b[mask].mean(axis=0);aa=a[mask]-ca;bb=b[mask]-cb
    denom=float(np.sum(aa**2));reference_ss=float(np.sum(bb**2))
    if denom<=0 or reference_ss<=0:raise ValueError("Degenerate alignment")
    u,s,vt=np.linalg.svd(aa.T@bb);rotation=u@vt;scale=float(s.sum()/denom)
    aligned=(a-ca)@rotation*scale+cb;residual=np.sqrt(np.sum((aligned-b)**2,axis=1))
    stats=dict(projected_procrustes_disparity=float(np.sum(residual[mask]**2)/reference_ss),projected_rms_residual_km=float(np.sqrt(np.mean(residual[mask]**2))),
               projected_median_residual_km=float(np.median(residual[mask])),projected_max_residual_km=float(residual[mask].max()))
    transform=dict(embedding_center=ca.tolist(),projected_geographic_center=cb.tolist(),rotation_reflection=rotation.tolist(),scale_km_per_embedding_unit=scale,
                   reflection_used=bool(np.linalg.det(rotation)<0))
    return aligned,residual,stats,transform


def analyze(actor="user"):
    if actor!="user":raise ValueError("Geographical course analysis must be run by the user")
    verified=verify_and_summarize();experiment=Path(verified["output_dir"])
    _,plan,inputs,_,inventory=current_plan();ref_dir,ref_manifest,nodes,geodistance=current_reference()
    ids=[r["node_id"] for r in nodes];node_index={n:i for i,n in enumerate(ids)};node_rows={r["node_id"]:r for r in nodes};datasets={r["dataset_id"]:r for r in inventory}
    selected=[s for s in plan["specs"] if s["seed"]==42 and "representative_seeds" in s["tags"]]
    if len(selected)!=8:raise ValueError("Expected eight representative seed42 models")
    out=ROOT/"data/analysis"/("user_stage2_geographic_analysis_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True)
    protocol=dict(reference_manifest_sha256=sha(ref_dir/"reference_manifest.json"),experiment_protocol_sha256=sha(experiment/"protocol.json"),
        geographic_code_sha256=sha(Path(__file__)),seed=42,selection="Fixed representative baseline parameters; not selected by geographical fit or maximum score",source_reference_dir=str(ref_dir),experiment_dir=str(experiment))
    write_json(out/"protocol.json",protocol);quality=[];aligned_rows=[];transforms=[]
    for spec in selected:
        dsids=list(read_matrix(inputs/datasets[spec["dataset_id"]]["matrix_file"]).index);indices=[node_index[n] for n in dsids]
        embedding=read_coords(experiment/(spec["run_id"]+"_coordinates.csv"),dsids)
        geo=np.array([[float(node_rows[n]["aeqd_x_km"]),float(node_rows[n]["aeqd_y_km"])] for n in dsids])
        distances=geodistance[np.ix_(indices,indices)]
        scopes=("all34","network33") if "N34" in dsids else ("all33",)
        for scope in scopes:
            mask=np.array([n!="N34" if scope=="network33" else True for n in dsids])
            aligned,residual,stats,transform=similarity_alignment(embedding,geo,mask)
            metrics=external_metrics(distances[np.ix_(mask,mask)],embedding[mask])
            record=dict(run_id=spec["run_id"],dataset_id=spec["dataset_id"],model=model_label(spec),seed=42,fit_scope=scope,fitting_nodes=int(mask.sum()),
                **stats,geo_distance_spearman=metrics["distance_spearman"],geo_scale_fitted_stress=metrics["external_scale_fitted_stress1"],
                geo_neighbor_overlap_k5=metrics["neighbor_overlap_k5"],geo_trustworthiness_k5=metrics["trustworthiness_k5"])
            quality.append(record);transforms.append(dict(run_id=spec["run_id"],fit_scope=scope,fitting_node_ids=[n for n,keep in zip(dsids,mask) if keep],**transform))
            for i,n in enumerate(dsids):
                aligned_rows.append(dict(run_id=spec["run_id"],dataset_id=spec["dataset_id"],model=model_label(spec),fit_scope=scope,node_id=n,city=node_rows[n]["representative_city"],
                    used_in_alignment=bool(mask[i]),embedding_1=float(embedding[i,0]),embedding_2=float(embedding[i,1]),geo_x_km=float(geo[i,0]),geo_y_km=float(geo[i,1]),
                    aligned_x_km=float(aligned[i,0]),aligned_y_km=float(aligned[i,1]),projected_residual_km=float(residual[i])))
    write_csv(out/"geographic_alignment_quality.csv",quality,list(quality[0]));write_csv(out/"aligned_coordinates.csv",aligned_rows,list(aligned_rows[0]))
    write_json(out/"alignment_transforms.json",transforms)
    reference33=read_matrix(inputs/datasets["access_60_n33"]["matrix_file"]);netids=list(reference33.index);idx=[node_index[n] for n in netids]
    gd=geodistance[np.ix_(idx,idx)];time_minutes=reference33.to_numpy(dtype=float);upper=np.triu_indices(len(netids),1)
    gv=gd[upper];tv=time_minutes[upper];grank=rankdata(gv,method="average")/len(gv);trank=rankdata(tv,method="average")/len(tv)
    pairs=[]
    for k,(i,j) in enumerate(zip(*upper)):
        pairs.append(dict(node_a=netids[i],city_a=node_rows[netids[i]]["representative_city"],node_b=netids[j],city_b=node_rows[netids[j]]["representative_city"],
            geographic_great_circle_km=float(gv[k]),symmetric_time_min=float(tv[k]),time_distance_ratio_min_per_km=float(tv[k]/gv[k]),
            geographic_rank_fraction=float(grank[k]),time_rank_fraction=float(trank[k]),time_minus_geographic_rank=float(trank[k]-grank[k]),
            includes_assumed_Macao_access="N33" in (netids[i],netids[j])))
    write_csv(out/"time_geographic_city_pairs.csv",pairs,list(pairs[0]))
    eligible=[r for r in pairs if r["geographic_great_circle_km"]>=200]
    examples=[dict(example_group=group,**r) for group,subset in (("relatively_high_time_rank",sorted(eligible,key=lambda x:x["time_minus_geographic_rank"],reverse=True)[:10]),
                                                              ("relatively_low_time_rank",sorted(eligible,key=lambda x:x["time_minus_geographic_rank"])[:10])) for r in subset]
    write_csv(out/"candidate_city_pair_examples.csv",examples,list(examples[0]))
    mask32=np.array([n!="N33" for n in netids]);geo32=gd[np.ix_(mask32,mask32)];time32=time_minutes[np.ix_(mask32,mask32)];u32=np.triu_indices(32,1)
    result=dict(output_dir=str(out),alignment_count=len(quality),representative_models=8,source_city_count=34,
        connected33_unique_pairs=len(pairs),time_geography_spearman_33=float(spearmanr(gv,tv).statistic),time_geography_spearman_32=float(spearmanr(geo32[u32],time32[u32]).statistic),
        example_min_geographic_km=200,candidate_examples=len(examples),geographic_alignment_computed=True,geographic_alignment_verified=False,
        external_economic_causal_explanation_complete=False,clustering_complete=False,plots_created_by_python=False,
        limitations=["Geographic agreement is a descriptive comparison, not a criterion for selecting the best rail-time embedding",
            "Alignment residuals are projected shape discrepancies, not errors in travel time, track length or real city locations",
            "Time/geographic-distance ratio is not running speed; it includes waiting and assumed Macau access",
            "Taipei penalties excluded from actual time-geography city-pair analysis","Candidate pairs are descriptive leads requiring route evidence and external sources, not causal or construction recommendations"],
        output_files_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    write_json(out/"geographic_summary.json",result);write_json(RESULT_MARKER,dict(output_dir=str(out),summary_sha256=sha(out/"geographic_summary.json")))
    return result


def verify_results():
    ref_dir,_,nodes,distance=current_reference();marker=json.loads(RESULT_MARKER.read_text(encoding="utf-8"));out=Path(marker["output_dir"])
    if sha(out/"geographic_summary.json")!=marker["summary_sha256"]:raise ValueError("Geographical summary changed")
    summary=json.loads((out/"geographic_summary.json").read_text(encoding="utf-8"));protocol=json.loads((out/"protocol.json").read_text(encoding="utf-8"))
    if protocol["reference_manifest_sha256"]!=sha(ref_dir/"reference_manifest.json") or protocol["geographic_code_sha256"]!=sha(Path(__file__)):raise ValueError("Geography protocol changed")
    experiment=Path(verify_and_summarize()["output_dir"])
    if protocol["experiment_protocol_sha256"]!=sha(experiment/"protocol.json"):raise ValueError("Experiment version differs")
    for name,digest in summary["output_files_sha256"].items():
        if sha(out/name)!=digest:raise ValueError("Geographical output changed")
    quality=read_csv(out/"geographic_alignment_quality.csv");rows=read_csv(out/"aligned_coordinates.csv")
    node_index={n["node_id"]:i for i,n in enumerate(nodes)}
    for q in quality:
        data=[r for r in rows if r["run_id"]==q["run_id"] and r["fit_scope"]==q["fit_scope"]]
        ids=[r["node_id"] for r in data];original=read_coords(experiment/(q["run_id"]+"_coordinates.csv"),ids)
        a=np.array([[float(r["embedding_1"]),float(r["embedding_2"])] for r in data]);b=np.array([[float(r["geo_x_km"]),float(r["geo_y_km"])] for r in data])
        if not np.array_equal(original,a):raise ValueError("Original embedding differs")
        expected=np.array([[float(nodes[node_index[n]]["aeqd_x_km"]),float(nodes[node_index[n]]["aeqd_y_km"])] for n in ids])
        if not np.allclose(expected,b):raise ValueError("Projected reference differs")
        mask=np.array([r["used_in_alignment"]=="True" for r in data]);aligned,residual,stats,_=similarity_alignment(a,b,mask)
        if not np.allclose(aligned,[[float(r["aligned_x_km"]),float(r["aligned_y_km"])] for r in data]):raise ValueError("Aligned coordinates differ")
        idx=[node_index[n] for n in ids];gd=distance[np.ix_(idx,idx)];metrics=external_metrics(gd[np.ix_(mask,mask)],a[mask])
        stats.update(geo_distance_spearman=metrics["distance_spearman"],geo_scale_fitted_stress=metrics["external_scale_fitted_stress1"],
            geo_neighbor_overlap_k5=metrics["neighbor_overlap_k5"],geo_trustworthiness_k5=metrics["trustworthiness_k5"])
        for key,value in stats.items():
            if not np.isfinite(value) or not np.isclose(value,float(q[key]),atol=1e-8,rtol=1e-7):raise ValueError("Geographic metric does not reproduce: "+key)
    if len(quality)!=12 or len(rows)!=404:raise ValueError("Alignment table incomplete")
    result=dict(output_dir=str(out),verified_alignments=12,verified_coordinate_rows=404,hashes_passed=True,similarity_transforms_reproduced=True,geographic_metrics_reproduced=True,
                connected33_unique_pairs=528,geographic_comparison_computed_and_verified=True,external_economic_explanation_complete=False,clustering_complete=False)
    write_json(out/"geographic_verification.json",result)
    return result
