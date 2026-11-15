"""User-run OFAT, selected combinations, seed and special-region sensitivity."""

from railway_project_io import read_project_json, script_hashes_match
import hashlib
import importlib.metadata as metadata
import json
import time
import warnings
from datetime import datetime
from pathlib import Path
from itertools import combinations

import numpy as np
from scipy.spatial import procrustes
from scipy.spatial.distance import pdist,squareform
from scipy.stats import spearmanr
from sklearn.manifold import TSNE

from stage1_collect import ROOT,TZ,write_csv,write_json,software_versions
from stage1b_transfer import read_csv
from stage1i_dated_schedule import sha
from stage2_inputs import current_inputs,read_matrix
from stage2_baseline import make_model,make_mds,external_metrics,fit_precomputed_isolated,verify_saved

PLAN_MARKER=ROOT/"evidence/stage2_experiment_plan_current.json"
RUN_MARKER=ROOT/"evidence/stage2_experiment_current.json"
SEEDS=(0,42,2026)
METRICS=("external_scale_fitted_stress1","distance_spearman","neighbor_overlap_k5","trustworthiness_k5")


def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True)


def parameters_for(algorithm,seed=42,**overrides):
    if algorithm=="MDS":
        model,params=make_mds(seed=seed,metric=overrides.pop("metric_mds",True),
                             n_init=overrides.pop("n_init",4),max_iter=overrides.pop("max_iter",1000))
        if overrides:raise ValueError("Unknown MDS overrides")
        return params
    if algorithm=="UMAP":
        # Plan generation must not import UMAP/Numba or trigger JIT compilation.
        # These are the same explicit defaults used in the authenticated baseline.
        params=dict(n_components=2,n_neighbors=10,min_dist=.1,n_epochs=500,metric="precomputed",init="random",random_state=seed,transform_seed=seed,n_jobs=1)
    else:_,params=make_model(algorithm,seed)
    params.update(overrides)
    return params


def estimator_for(spec):
    p=spec["parameters"].copy();a=spec["algorithm"]
    if a=="MDS":
        from sklearn.manifold import MDS
        return MDS(**p)
    if a=="tSNE":return TSNE(**p)
    if a=="UMAP":
        from umap import UMAP
        return UMAP(**p)
    raise ValueError("Unknown algorithm")


def model_label(spec):
    p=spec["parameters"]
    if spec["algorithm"]=="MDS" and not p.get("metric_mds",p.get("metric")):return "MDS_nonmetric"
    return spec["algorithm"]


def build_specs(inventory):
    """One row per unique fit; tags preserve membership in multiple comparisons."""
    specs={}
    baselines=[x for x in inventory if x["baseline"]=="True"]
    def add(dataset,algorithm,tag,seed=42,**overrides):
        params=parameters_for(algorithm,seed,**overrides)
        key=dataset["dataset_id"]+"_"+algorithm+"_"+hashlib.sha256(canonical(params).encode()).hexdigest()[:12]
        if key not in specs:
            specs[key]=dict(run_id=key,dataset_id=dataset["dataset_id"],algorithm=algorithm,seed=seed,
                            node_count=int(dataset["node_count"]),parameters=params,tags=[])
        if tag not in specs[key]["tags"]:specs[key]["tags"].append(tag)
    for d in baselines:
        for metric in (True,False):add(d,"MDS","MDS_metric",metric_mds=metric)
        for n in (1,4,8):add(d,"MDS","MDS_n_init",n_init=n)
        for perplexity in (5.,10.,20.):add(d,"tSNE","tSNE_perplexity",perplexity=perplexity)
        for iterations in (500,1000,2000):add(d,"tSNE","tSNE_iterations",max_iter=iterations)
        for perplexity,iterations in ((5.,500),(20.,2000)):
            add(d,"tSNE","tSNE_selected_combinations",perplexity=perplexity,max_iter=iterations)
        for neighbors in (5,10,20):add(d,"UMAP","UMAP_neighbors",n_neighbors=neighbors)
        for min_dist in (0.,.1,.5):add(d,"UMAP","UMAP_min_dist",min_dist=min_dist)
        for neighbors,min_dist in ((5,0.),(20,.5)):
            add(d,"UMAP","UMAP_selected_combinations",n_neighbors=neighbors,min_dist=min_dist)
        for seed in SEEDS:
            for alg in ("MDS","tSNE","UMAP"):add(d,alg,"representative_seeds",seed=seed)
            add(d,"MDS","representative_seeds",seed=seed,metric_mds=False)
    for d in inventory:
        if int(d["node_count"]) not in (33,34):continue
        for alg in ("MDS","tSNE","UMAP"):add(d,alg,"special_region_sensitivity")
    result=list(specs.values())
    for s in result:
        p=s["parameters"];n=s["node_count"]
        if s["algorithm"]=="tSNE" and not 0<p["perplexity"]<n:raise ValueError("Invalid perplexity")
        if s["algorithm"]=="UMAP" and not 1<p["n_neighbors"]<n:raise ValueError("Invalid neighbor count")
        s["tags"].sort()
    return result


def flat_spec(s):
    p=s["parameters"]
    return dict(run_id=s["run_id"],dataset_id=s["dataset_id"],algorithm=s["algorithm"],model=model_label(s),node_count=s["node_count"],seed=s["seed"],
        metric_mds=p.get("metric_mds",p.get("metric") if s["algorithm"]=="MDS" else ""),
        n_init=p.get("n_init",""),max_iter=p.get("max_iter",""),perplexity=p.get("perplexity",""),
        n_neighbors=p.get("n_neighbors",""),min_dist=p.get("min_dist",""),n_epochs=p.get("n_epochs",""),tags="|".join(s["tags"]))


def code_hashes():return {n:sha(ROOT/"scripts"/n) for n in ("stage2_experiments.py","stage2_baseline.py","stage2_inputs.py")}


def preview(actor="user"):
    if actor not in ("user","assistant"):raise ValueError("Invalid actor")
    base=verify_saved();baseline=Path(base["output_dir"])
    folder,manifest,inventory=current_inputs();specs=build_specs(inventory)
    out=ROOT/"data/analysis"/(actor+"_stage2_experiment_plan_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True)
    protocol=dict(input_manifest_sha256=sha(folder/"input_manifest.json"),baseline_protocol_sha256=sha(baseline/"protocol.json"),
        baseline_dir=str(baseline),code_hashes=code_hashes(),seeds=list(SEEDS),fit_input_policy="independent writable fit copy; read-only reference",
        common_scale_minutes=manifest["common_scale_minutes"],quality_reference="same frozen symmetric D for all methods; D/common_scale",
        comparison_policy="OFAT with baseline held fixed; two selected TSNE/UMAP combinations; fixed representative three-seed groups; all 9 full34 + 3 no-Taipei33 scenarios")
    rows=[flat_spec(s) for s in specs];write_csv(out/"experiment_plan.csv",rows,list(rows[0]))
    write_json(out/"plan.json",dict(protocol=protocol,specs=specs))
    result=dict(output_dir=str(out),total_unique_runs=len(specs),reusable_baseline_runs=6,new_model_fits=len(specs)-6,
        main_datasets=manifest["baseline_datasets"],seeds=list(SEEDS),tag_counts={tag:sum(tag in s["tags"] for s in specs) for tag in sorted({tag for s in specs for tag in s["tags"]})},
        plan_sha256=sha(out/"plan.json"),actor=actor,course_experiments_executed=False)
    write_json(out/"plan_summary.json",result)
    if actor=="user":write_json(PLAN_MARKER,dict(output_dir=str(out),plan_sha256=result["plan_sha256"]))
    return result


def current_plan():
    if not PLAN_MARKER.exists():raise ValueError("Run problem2 core4 first")
    marker=read_project_json(PLAN_MARKER);folder=Path(marker["output_dir"])
    if sha(folder/"plan.json")!=marker["plan_sha256"]:raise ValueError("Experiment plan changed")
    plan=read_project_json(folder / 'plan.json');protocol=plan["protocol"]
    inputs,manifest,inventory=current_inputs()
    if sha(inputs/"input_manifest.json")!=protocol["input_manifest_sha256"]:raise ValueError("Frozen input version changed; preserve existing plan")
    if not script_hashes_match(code_hashes(), protocol['code_hashes']):raise ValueError("Experiment code changed; inspect before creating a new plan")
    base=verify_saved()
    if str(Path(base["output_dir"]))!=str(Path(protocol["baseline_dir"])) or sha(Path(base["output_dir"])/"protocol.json")!=protocol["baseline_protocol_sha256"]:
        raise ValueError("Baseline version changed")
    return folder,plan,inputs,manifest,inventory


def metric_values(reference,coords,ids):
    values=external_metrics(reference,coords)
    network=np.array([n!="N34" for n in ids])
    values.update({"network_only_"+k:v for k,v in external_metrics(reference[np.ix_(network,network)],coords[network]).items()})
    if not all(np.isfinite(v) for v in values.values()):raise ValueError("Nonfinite quality metric")
    return values


def read_coords(path,ids):
    rows=read_csv(path)
    if [r["node_id"] for r in rows]!=ids:raise ValueError("Coordinate node order differs")
    coords=np.array([[float(r["embedding_1"]),float(r["embedding_2"])] for r in rows])
    if coords.shape!=(len(ids),2) or not np.isfinite(coords).all():raise ValueError("Invalid coordinates")
    return coords


def reusable_baseline(spec,baseline):
    if spec["seed"]!=42 or spec["dataset_id"] not in ("access_60_alpha_5_n34","access_60_n33"):return None
    run=spec["dataset_id"]+"_"+spec["algorithm"]+"_seed42"
    path=baseline/(run+"_metrics.json")
    saved=read_project_json(path)
    if canonical(saved["parameters"])!=canonical(spec["parameters"]):return None
    coords=baseline/(run+"_coordinates.csv")
    if sha(coords)!=saved["coordinates_sha256"]:raise ValueError("Baseline coordinates changed")
    return coords,saved


def run(actor="user"):
    if actor!="user":raise ValueError("Course experiments must be run by the user")
    plan_dir,plan,inputs,manifest,inventory=current_plan()
    versions=software_versions();versions["umap-learn"]=metadata.version("umap-learn")
    protocol=dict(plan_sha256=sha(plan_dir/"plan.json"),software=versions,code_hashes=code_hashes())
    out=None
    if RUN_MARKER.exists():
        old=read_project_json(RUN_MARKER);candidate=Path(old["output_dir"])
        if read_project_json(candidate / 'protocol.json')==protocol:out=candidate
    if out is None:
        out=ROOT/"data/analysis"/("user_stage2_experiments_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True)
        write_json(out/"protocol.json",protocol);write_json(RUN_MARKER,dict(output_dir=str(out)))
    index={r["dataset_id"]:r for r in inventory};nodes=read_csv(inputs/"nodes_34.csv");names={n["node_id"]:n["representative_city"] for n in nodes}
    baseline=Path(plan["protocol"]["baseline_dir"]);records=[]
    for i,s in enumerate(plan["specs"],1):
        mp=out/(s["run_id"]+"_metrics.json");cp=out/(s["run_id"]+"_coordinates.csv")
        if mp.exists():
            saved=read_project_json(mp)
            if sha(cp)!=saved["coordinates_sha256"]:raise ValueError("Completed coordinates changed")
            records.append(saved["record"]);print(f"{i}/{len(plan['specs'])} 复用本轮已完成：{s['run_id']}",flush=True);continue
        frame=read_matrix(inputs/index[s["dataset_id"]]["matrix_file"]);ids=list(frame.index)
        reference=frame.to_numpy(dtype=float)/manifest["common_scale_minutes"];reference.setflags(write=False)
        reuse=reusable_baseline(s,baseline)
        if reuse:
            source,old=reuse;coords=read_coords(source,ids);origin="reused_user_baseline";elapsed=0.
            native={k:old["metrics"][k] for k in ("native_loss","native_loss_definition","native_n_iter_attribute")}
            messages=old["warnings"];original_seconds=old["metrics"]["seconds"]
        else:
            print(f"{i}/{len(plan['specs'])} 正在拟合：{s['run_id']}",flush=True)
            estimator=estimator_for(s);started=time.perf_counter()
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always");coords=fit_precomputed_isolated(estimator,reference)
            elapsed=time.perf_counter()-started;origin="new_user_fit";original_seconds="";messages=[str(w.message) for w in caught]
            native_loss=float(estimator.stress_) if s["algorithm"]=="MDS" else float(estimator.kl_divergence_) if s["algorithm"]=="tSNE" else ""
            native_name=("normalized_stress1_disparities" if model_label(s)=="MDS_nonmetric" else "normalized_stress1") if s["algorithm"]=="MDS" else "KL_divergence" if s["algorithm"]=="tSNE" else "not_exposed"
            native=dict(native_loss=native_loss,native_loss_definition=native_name,native_n_iter_attribute=getattr(estimator,"n_iter_",""))
        values=metric_values(reference,coords,ids)
        record=dict(**flat_spec(s),fit_origin=origin,new_fit_seconds=elapsed,reused_original_fit_seconds=original_seconds,
                    convergence_trace_available=False,**native,**values)
        write_csv(cp,[dict(node_id=n,city=names[n],embedding_1=float(coords[j,0]),embedding_2=float(coords[j,1])) for j,n in enumerate(ids)],
                  ["node_id","city","embedding_1","embedding_2"])
        write_json(mp,dict(record=record,parameters=s["parameters"],warnings=messages,coordinates_sha256=sha(cp),reference_matrix_sha256=index[s["dataset_id"]]["sha256"],
            baseline_source=str(reuse[0]) if reuse else "",reference_unmodified=True,
            convergence_note="n_iter_ is raw implementation-specific output. No iteration trace recorded; native losses differ between algorithms and metric/nonmetric MDS."))
        records.append(record);write_csv(out/"experiment_metrics.csv",records,list(records[0]))
        print(f"{i}/{len(plan['specs'])} 完成：{model_label(s)}；stress={values[METRICS[0]]:.4f}；rank={values[METRICS[1]]:.4f}",flush=True)
    result=dict(output_dir=str(out),completed_runs=len(records),expected_runs=len(plan["specs"]),reused_baseline_runs=sum(r["fit_origin"]=="reused_user_baseline" for r in records),
                new_fits=sum(r["fit_origin"]=="new_user_fit" for r in records),parameter_runs_complete=True,verification_and_stability_summary_complete=False,
                geographic_comparison_complete=False,clustering_complete=False,plots_created_by_python=False)
    write_json(out/"experiment_summary.json",result)
    return result


def geometry_comparison(a,b,k=5):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    if a.shape!=b.shape or a.shape[1]!=2 or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError("Invalid comparison coordinates")
    _,_,disparity=procrustes(a,b)
    da=pdist(a);db=pdist(b);aa=squareform(da);bb=squareform(db)
    np.fill_diagonal(aa,np.inf);np.fill_diagonal(bb,np.inf)
    na=np.argsort(aa,axis=1,kind="stable")[:,:k];nb=np.argsort(bb,axis=1,kind="stable")[:,:k]
    return dict(procrustes_disparity=float(disparity),embedding_distance_spearman=float(spearmanr(da,db).statistic),
                embedding_neighbor_overlap_k5=float(np.mean([len(set(x)&set(y))/k for x,y in zip(na,nb)])))


def verify_and_summarize():
    plan_dir,plan,inputs,manifest,inventory=current_plan()
    marker=read_project_json(RUN_MARKER);out=Path(marker["output_dir"])
    protocol=read_project_json(out / 'protocol.json')
    if protocol["plan_sha256"]!=sha(plan_dir/"plan.json") or not script_hashes_match(code_hashes(), protocol['code_hashes']):raise ValueError("Run protocol differs")
    index={r["dataset_id"]:r for r in inventory};records=[];coordinates={};ids_by_dataset={}
    for s in plan["specs"]:
        frame=read_matrix(inputs/index[s["dataset_id"]]["matrix_file"]);ids=list(frame.index);ids_by_dataset[s["dataset_id"]]=ids
        ref=frame.to_numpy(dtype=float)/manifest["common_scale_minutes"];ref.setflags(write=False)
        mp=out/(s["run_id"]+"_metrics.json");cp=out/(s["run_id"]+"_coordinates.csv")
        saved=read_project_json(mp)
        if saved["parameters"]!=s["parameters"] or sha(cp)!=saved["coordinates_sha256"] or saved["reference_matrix_sha256"]!=index[s["dataset_id"]]["sha256"]:
            raise ValueError("Saved run provenance differs")
        coords=read_coords(cp,ids);calc=metric_values(ref,coords,ids)
        record=saved["record"]
        for k,v in calc.items():
            if not np.isclose(v,float(record[k]),atol=1e-8,rtol=1e-7):raise ValueError("Saved metric does not reproduce: "+s["run_id"]+" "+k)
        records.append(record);coordinates[s["run_id"]]=coords
    aggregate=read_csv(out/"experiment_metrics.csv")
    if len(aggregate)!=len(records) or {r["run_id"] for r in aggregate}!={r["run_id"] for r in records}:raise ValueError("Aggregate rows differ")
    for r in records:
        row=next(x for x in aggregate if x["run_id"]==r["run_id"])
        for k in calc:
            if not np.isclose(float(row[k]),float(r[k]),atol=1e-8,rtol=1e-7):raise ValueError("Aggregate metric differs")
    stable=[]
    datasets=sorted({s["dataset_id"] for s in plan["specs"] if "representative_seeds" in s["tags"]})
    for dataset in datasets:
        for model in ("MDS","MDS_nonmetric","tSNE","UMAP"):
            members=[s for s in plan["specs"] if s["dataset_id"]==dataset and model_label(s)==model and "representative_seeds" in s["tags"]]
            if sorted(s["seed"] for s in members)!=sorted(SEEDS):raise ValueError("Seed group incomplete")
            mask=np.array([n!="N34" for n in ids_by_dataset[dataset]])
            for a,b in combinations(members,2):
                ca=coordinates[a["run_id"]];cb=coordinates[b["run_id"]]
                stable.append(dict(dataset_id=dataset,model=model,seed_a=a["seed"],seed_b=b["seed"],
                    **geometry_comparison(ca,cb),**{"network_only_"+k:v for k,v in geometry_comparison(ca[mask],cb[mask]).items()}))
    scenario=[]
    sensitivity=[s for s in plan["specs"] if "special_region_sensitivity" in s["tags"]]
    for s in sensitivity:
        dataset=s["dataset_id"];entry=index[dataset];ids=ids_by_dataset[dataset];mask=np.array([n!="N34" for n in ids])
        c=coordinates[s["run_id"]][mask]
        control_id=f"access_{entry['access_min']}_n33"
        control=next(x for x in sensitivity if x["dataset_id"]==control_id and x["algorithm"]==s["algorithm"])
        comparison=geometry_comparison(coordinates[control["run_id"]],c)
        scenario.append(dict(dataset_id=dataset,algorithm=s["algorithm"],access_min=entry["access_min"],alpha=entry["alpha"],
            control_dataset=control_id,**{"vs_same_access_no_Taipei_"+k:v for k,v in comparison.items()}))
    # OFAT tables preserve the comparison label; a baseline belongs to several tables.
    comparison_rows=[]
    for s,r in zip(plan["specs"],records):
        for tag in s["tags"]:
            if tag not in ("representative_seeds","special_region_sensitivity"):
                comparison_rows.append(dict(comparison=tag,**r))
    write_csv(out/"seed_stability_pairs.csv",stable,list(stable[0]))
    write_csv(out/"special_region_embedding_comparison.csv",scenario,list(scenario[0]))
    write_csv(out/"parameter_comparison.csv",comparison_rows,list(comparison_rows[0]))
    # Mean/SD summarize only the fixed representative setting across exactly three seeds.
    seed_quality=[]
    for dataset in datasets:
        for model in ("MDS","MDS_nonmetric","tSNE","UMAP"):
            group=[r for s,r in zip(plan["specs"],records) if s["dataset_id"]==dataset and model_label(s)==model and "representative_seeds" in s["tags"]]
            row=dict(dataset_id=dataset,model=model,seed_count=len(group))
            for key in (*METRICS,*("network_only_"+k for k in METRICS)):
                values=[float(r[key]) for r in group];row[key+"_mean"]=float(np.mean(values));row[key+"_sd"]=float(np.std(values,ddof=1))
            seed_quality.append(row)
    write_csv(out/"representative_seed_quality.csv",seed_quality,list(seed_quality[0]))
    result=dict(output_dir=str(out),verified_runs=len(records),coordinate_hashes_passed=True,node_order_passed=True,external_metrics_reproduced=True,
        three_seeds=list(SEEDS),seed_stability_pairs=len(stable),scenario_comparisons=len(scenario),parameter_comparison_rows=len(comparison_rows),
        parameter_runs_complete=True,representative_three_seed_stability_complete=True,geographic_comparison_complete=False,clustering_complete=False,
        note="Seed stability uses translation/rotation/reflection/scale-adjusted Procrustes disparity plus distance rank and neighbor overlap; not geographical alignment. No causal or final ranking inference from a single score.")
    write_json(out/"experiment_verification.json",result)
    return result
