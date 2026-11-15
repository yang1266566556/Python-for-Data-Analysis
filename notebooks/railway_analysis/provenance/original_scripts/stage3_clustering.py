"""User-run clustering with original-distance and embedding controls."""
import hashlib
import json
import time
import warnings
from datetime import datetime
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist,squareform
from stage1_collect import ROOT,TZ,write_csv,write_json,software_versions
from stage1b_transfer import read_csv
from stage1i_dated_schedule import sha
from stage2_inputs import current_inputs,read_matrix
from stage2_experiments import current_plan,canonical,read_coords
from stage2_geography import verify_results,current_reference
from stage3_algorithms import validate_distance,cluster_model,quality_metrics,partition_agreement

PLAN_MARKER=ROOT/"evidence/stage3_cluster_plan_current.json"
RUN_MARKER=ROOT/"evidence/stage3_cluster_current.json"


def code_hashes():return {n:sha(ROOT/"scripts"/n) for n in ("stage3_algorithms.py","stage3_clustering.py")}


def embedding_selection(spec):
    if spec["algorithm"]=="MDS":
        return spec["seed"]==42 and "representative_seeds" in spec["tags"] and bool(spec["parameters"].get("metric_mds",False))
    if spec["algorithm"]=="tSNE":return (spec["seed"]==42 and "tSNE_perplexity" in spec["tags"]) or "representative_seeds" in spec["tags"]
    if spec["algorithm"]=="UMAP":return (spec["seed"]==42 and "UMAP_neighbors" in spec["tags"]) or "representative_seeds" in spec["tags"]
    return False


def normalize_distance(distance):
    d=validate_distance(distance);v=d[np.triu_indices(len(d),1)];positive=v[v>0]
    if len(positive)==0:raise ValueError("No positive pairwise distances")
    scale=float(np.median(positive));return d/scale,scale


def build_specs(representations,distances):
    specs={}
    def add(rep,algorithm,params,tag,representative=False):
        run=rep["representation_id"]+"__"+algorithm+"_"+hashlib.sha256(canonical(params).encode()).hexdigest()[:12]
        if run not in specs:specs[run]=dict(run_id=run,representation_id=rep["representation_id"],dataset_id=rep["dataset_id"],algorithm=algorithm,parameters=params,tags=[],representative=False)
        if tag not in specs[run]["tags"]:specs[run]["tags"].append(tag)
        if representative:specs[run]["representative"]=True
    for rep in representations:
        d=distances[rep["representation_id"]];kd=np.sort(d,axis=1)[:,3]
        eps={q:float(np.quantile(kd,q)) for q in (.1,.25,.5,.75,.9)}
        if any(v<=0 for v in eps.values()):raise ValueError("DBSCAN epsilon quantile is not positive")
        rep["epsilon_quantiles"]=eps;main=rep["main_parameter_input"]
        for k in ((3,4,5) if main else (4,)):
            add(rep,"HAC_average",dict(k=k),"cluster_count" if main else "representative",k==4)
            add(rep,"PAM",dict(k=k,seed=42,max_iter=100,tol=1e-10),"cluster_count" if main else "representative",k==4)
        if main:
            for seed in (0,42,2026):add(rep,"PAM",dict(k=4,seed=seed,max_iter=100,tol=1e-10),"PAM_seed",seed==42)
        for q in ((.1,.25,.5,.75,.9) if main else (.5,)):
            add(rep,"DBSCAN",dict(eps=eps[q],min_samples=4),"DBSCAN_epsilon",q==.5)
        if main:
            for count in (3,4,5):add(rep,"DBSCAN",dict(eps=eps[.5],min_samples=count),"DBSCAN_min_samples",count==4)
    for s in specs.values():s["tags"].sort()
    return list(specs.values())


def prepare(actor="user"):
    if actor not in ("user","assistant"):raise ValueError("Invalid actor")
    geo=verify_results();ref,_,_,_=current_reference();inputs,_,inventory=current_inputs();_,q2,_,_,_=current_plan()
    experiment=Path(json.loads((ROOT/"evidence/stage2_experiment_current.json").read_text(encoding="utf-8"))["output_dir"])
    out=ROOT/"data/analysis"/(actor+"_stage3_cluster_plan_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True)
    main_ids={"access_60_alpha_5_n34","access_60_n33"};representations=[];distances={}
    raw={r["dataset_id"]:r for r in inventory if int(r["node_count"]) in (33,34)}
    def save_rep(rid,dataset,family,ids,d,features,source,main,source_spec=None):
        normalized,scale=normalize_distance(d)
        matrix=rid+"_distance.csv";pd.DataFrame(normalized,index=ids,columns=ids).to_csv(out/matrix,encoding="utf-8-sig")
        feature_file=""
        if features is not None:
            feature_file=rid+"_features.csv"
            write_csv(out/feature_file,[dict(node_id=n,x=float(features[i,0]/scale),y=float(features[i,1]/scale)) for i,n in enumerate(ids)],["node_id","x","y"])
        rep=dict(representation_id=rid,dataset_id=dataset,family=family,node_count=len(ids),matrix_file=matrix,features_file=feature_file,normalizing_positive_median=scale,
            source_file=str(source),source_sha256=sha(source),main_parameter_input=main,source_embedding_spec=source_spec,
            matrix_sha256=sha(out/matrix),features_sha256=sha(out/feature_file) if feature_file else "",
            normalized_unit="distance / own positive upper-triangle median; dimensionless",metric_definition="symmetric rail-time dissimilarity" if family=="rail_time" else "Euclidean distance on saved 2D embedding")
        representations.append(rep);distances[rid]=normalized
    for dataset,entry in raw.items():
        frame=read_matrix(inputs/entry["matrix_file"])
        save_rep("rail__"+dataset,dataset,"rail_time",list(frame.index),frame.to_numpy(dtype=float),None,inputs/entry["matrix_file"],dataset in main_ids)
    for spec in [s for s in q2["specs"] if embedding_selection(s)]:
        dataset=spec["dataset_id"];frame=read_matrix(inputs/raw[dataset]["matrix_file"]);ids=list(frame.index)
        source=experiment/(spec["run_id"]+"_coordinates.csv");coords=read_coords(source,ids)
        default=spec["seed"]==42 and "representative_seeds" in spec["tags"]
        save_rep(spec["algorithm"]+"__"+spec["run_id"],dataset,spec["algorithm"],ids,squareform(pdist(coords)),coords,source,default,source_spec=spec)
    specs=build_specs(representations,distances)
    protocol=dict(q2_experiment_protocol_sha256=sha(experiment/"protocol.json"),q2_experiment_dir=str(experiment),geographic_protocol_sha256=sha(Path(geo["output_dir"])/"protocol.json"),
        geographic_reference_manifest_sha256=sha(ref/"reference_manifest.json"),input_manifest_sha256=sha(inputs/"input_manifest.json"),code_hashes=code_hashes(),
        comparison_policy="Raw main34 and no-Taipei33; three clustering mechanisms, raw/embedding controls, fixed representatives, projection parameter/seed and special-region sensitivity",
        distance_policy="Each representation divided by own positive pairwise median. Matrix rows never used as features. CH/DB only on actual Euclidean embedding features.",
        dbscan_policy="epsilon from 3rd-other-neighbor distances (min_samples=4 includes self); quantiles 0.1/0.25/0.5/0.75/0.9. At median epsilon also compare min_samples3/4/5. Degenerate partitions retained with unavailable metrics.",
        noise_policy="silhouette/CH/DB exclude noise; report coverage. ARI/NMI all-node comparison treats noise as a label and also reports non-noise intersection with trivial-partition flags.",
        representative_policy="k=4, PAM seed42, DBSCAN median epsilon/min_samples4 fixed before scores; no automatic winner selection")
    write_json(out/"plan.json",dict(protocol=protocol,representations=representations,specs=specs))
    flat=[dict(run_id=s["run_id"],representation_id=s["representation_id"],dataset_id=s["dataset_id"],algorithm=s["algorithm"],representative=s["representative"],
        tags="|".join(s["tags"]),parameters=canonical(s["parameters"])) for s in specs]
    write_csv(out/"cluster_plan.csv",flat,list(flat[0]))
    reps=[{k:v for k,v in rep.items() if k not in ("source_embedding_spec","epsilon_quantiles")} for rep in representations]
    write_csv(out/"representation_inventory.csv",reps,list(reps[0]))
    result=dict(output_dir=str(out),representations=len(representations),main_parameter_representations=sum(r["main_parameter_input"] for r in representations),unique_cluster_runs=len(specs),
        algorithm_counts={a:sum(s["algorithm"]==a for s in specs) for a in ("HAC_average","PAM","DBSCAN")},representative_partitions=sum(s["representative"] for s in specs),
        data_only_preparation=True,course_clustering_executed=False,actor=actor,plan_sha256=sha(out/"plan.json"))
    write_json(out/"plan_summary.json",result)
    if actor=="user":write_json(PLAN_MARKER,dict(output_dir=str(out),plan_sha256=result["plan_sha256"]))
    return result


def current_cluster_plan():
    marker=json.loads(PLAN_MARKER.read_text(encoding="utf-8"));out=Path(marker["output_dir"])
    if sha(out/"plan.json")!=marker["plan_sha256"]:raise ValueError("Cluster plan changed")
    plan=json.loads((out/"plan.json").read_text(encoding="utf-8"))
    if plan["protocol"]["code_hashes"]!=code_hashes():raise ValueError("Cluster code changed")
    inputs,_,inventory=current_inputs();geo=verify_results();ref,_,_,_=current_reference()
    if plan["protocol"]["input_manifest_sha256"]!=sha(inputs/"input_manifest.json") or plan["protocol"]["geographic_protocol_sha256"]!=sha(Path(geo["output_dir"])/"protocol.json") or plan["protocol"]["geographic_reference_manifest_sha256"]!=sha(ref/"reference_manifest.json"):
        raise ValueError("Upstream input version changed")
    experiment=Path(plan["protocol"]["q2_experiment_dir"])
    if sha(experiment/"protocol.json")!=plan["protocol"]["q2_experiment_protocol_sha256"]:raise ValueError("Embedding protocol changed")
    for rep in plan["representations"]:
        if sha(Path(rep["source_file"]))!=rep["source_sha256"] or sha(out/rep["matrix_file"])!=rep["matrix_sha256"]:raise ValueError("Clustering representation changed")
        if rep["features_file"] and sha(out/rep["features_file"])!=rep["features_sha256"]:raise ValueError("Clustering Euclidean features changed")
    return out,plan,inputs,{r["dataset_id"]:r for r in inventory}


def load_representation(folder,rep,inputs,inventory):
    frame=read_matrix(folder/rep["matrix_file"]);ids=list(frame.index);d=validate_distance(frame.to_numpy(dtype=float));d.setflags(write=False)
    rail_frame=read_matrix(inputs/inventory[rep["dataset_id"]]["matrix_file"])
    if list(rail_frame.index)!=ids:raise ValueError("Raw/reference node order differs")
    rail=rail_frame.to_numpy(dtype=float);rail.setflags(write=False);features=None
    if rep["features_file"]:
        rows=read_csv(folder/rep["features_file"])
        if [r["node_id"] for r in rows]!=ids:raise ValueError("Feature node order differs")
        features=np.array([[float(r["x"]),float(r["y"])] for r in rows])
        if not np.allclose(squareform(pdist(features)),d,atol=1e-10,rtol=1e-8):raise ValueError("Embedding features and Euclidean distance differ")
    return ids,d,rail,features


def run(actor="user"):
    if actor!="user":raise ValueError("Course clustering must be run by the user")
    folder,plan,inputs,inventory=current_cluster_plan();protocol=dict(plan_sha256=sha(folder/"plan.json"),software=software_versions(),code_hashes=code_hashes())
    out=None
    if RUN_MARKER.exists():
        old=json.loads(RUN_MARKER.read_text(encoding="utf-8"));candidate=Path(old["output_dir"])
        if json.loads((candidate/"protocol.json").read_text(encoding="utf-8"))==protocol:out=candidate
    if out is None:
        out=ROOT/"data/analysis"/("user_stage3_clustering_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True)
        write_json(out/"protocol.json",protocol);write_json(RUN_MARKER,dict(output_dir=str(out)))
    reps={r["representation_id"]:r for r in plan["representations"]};nodes=read_csv(inputs/"nodes_34.csv");names={n["node_id"]:n["representative_city"] for n in nodes};records=[]
    for i,s in enumerate(plan["specs"],1):
        cp=out/(s["run_id"]+"_labels.csv");mp=out/(s["run_id"]+"_metrics.json")
        if mp.exists():
            saved=json.loads(mp.read_text(encoding="utf-8"))
            if sha(cp)!=saved["labels_sha256"]:raise ValueError("Saved labels changed")
            records.append(saved["record"]);print(f"{i}/{len(plan['specs'])} 复用本轮已完成",flush=True);continue
        rep=reps[s["representation_id"]];ids,d,rail,features=load_representation(folder,rep,inputs,inventory)
        started=time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always");labels,details=cluster_model(s["algorithm"],s["parameters"],d)
        elapsed=time.perf_counter()-started;values=quality_metrics(d,labels,rail,features)
        record=dict(run_id=s["run_id"],representation_id=s["representation_id"],dataset_id=s["dataset_id"],family=rep["family"],algorithm=s["algorithm"],
            node_count=len(ids),representative=s["representative"],tags="|".join(s["tags"]),k=s["parameters"].get("k",""),seed=s["parameters"].get("seed",""),
            eps=s["parameters"].get("eps",""),min_samples=s["parameters"].get("min_samples",""),seconds=elapsed,
            objective=details.get("objective"),accepted_swaps=details.get("accepted_swaps"),converged=details["converged"],stop_reason=details["stop_reason"],**values)
        write_csv(cp,[dict(node_id=n,city=names[n],cluster=int(labels[j]),is_noise=bool(labels[j]<0)) for j,n in enumerate(ids)],["node_id","city","cluster","is_noise"])
        if "medoid_indices" in details:details["medoid_node_ids"]=[ids[j] for j in details["medoid_indices"]]
        write_json(mp,dict(record=record,parameters=s["parameters"],details=details,warnings=[str(w.message) for w in caught],labels_sha256=sha(cp),
            representation_matrix_sha256=rep["matrix_sha256"],metric_notes="Scores exclude noise and report coverage. Original-rail silhouette uses same retained nodes. CH/DB only saved Euclidean embedding features; never distance-matrix rows."))
        records.append(record);write_csv(out/"cluster_metrics.csv",records,list(records[0]))
        print(f"{i}/{len(plan['specs'])} {s['algorithm']}；簇数={values['n_clusters']}；噪声={values['n_noise']}；评分状态={values['silhouette_status']}",flush=True)
    result=dict(output_dir=str(out),completed_runs=len(records),expected_runs=len(plan["specs"]),numeric_clustering_runs_complete=True,
        verification_and_stability_summary_complete=False,plots_created_by_python=False,external_interpretation_complete=False,
        unavailable_silhouette_runs=sum(r["silhouette_input"] is None for r in records))
    write_json(out/"cluster_summary.json",result);return result


def verify_and_summarize():
    folder,plan,inputs,inventory=current_cluster_plan();marker=json.loads(RUN_MARKER.read_text(encoding="utf-8"));out=Path(marker["output_dir"])
    protocol=json.loads((out/"protocol.json").read_text(encoding="utf-8"))
    if protocol["plan_sha256"]!=sha(folder/"plan.json") or protocol["code_hashes"]!=code_hashes():raise ValueError("Clustering run protocol differs")
    reps={r["representation_id"]:r for r in plan["representations"]};labels_by_run={};records=[];ids_by_rep={}
    for s in plan["specs"]:
        rep=reps[s["representation_id"]];ids,d,rail,features=load_representation(folder,rep,inputs,inventory);ids_by_rep[s["representation_id"]]=ids
        cp=out/(s["run_id"]+"_labels.csv");saved=json.loads((out/(s["run_id"]+"_metrics.json")).read_text(encoding="utf-8"))
        if sha(cp)!=saved["labels_sha256"] or saved["parameters"]!=s["parameters"] or saved["representation_matrix_sha256"]!=rep["matrix_sha256"]:raise ValueError("Saved clustering provenance differs")
        rows=read_csv(cp)
        if [r["node_id"] for r in rows]!=ids:raise ValueError("Label node order differs")
        labels=np.array([int(r["cluster"]) for r in rows]);calculated=quality_metrics(d,labels,rail,features);record=saved["record"]
        for key,value in calculated.items():
            if value is None:
                if record[key] is not None:raise ValueError("Unavailable score was filled")
            elif isinstance(value,(float,int)):
                if not np.isclose(value,record[key],atol=1e-8,rtol=1e-7):raise ValueError("Clustering quality does not reproduce")
            elif value!=record[key]:raise ValueError("Clustering status differs")
        if s["algorithm"]=="PAM":
            details=saved["details"];medoids=details["medoid_indices"];objective=float(np.min(d[:,medoids],axis=1).sum())
            expected_labels=np.argmin(d[:,medoids],axis=1)
            for j,m in enumerate(medoids):expected_labels[m]=j
            if not np.array_equal(expected_labels,labels):raise ValueError("PAM labels do not match saved medoids")
            if not np.isclose(objective,details["objective"]) or np.any(np.diff(details["objective_trace"])>1e-10):raise ValueError("PAM objective/trace differs")
            if details["converged"]:
                for old in medoids:
                    for new in range(len(d)):
                        if new in medoids:continue
                        trial=[new if m==old else m for m in medoids]
                        if np.min(d[:,trial],axis=1).sum()<objective-2e-10*max(1,abs(objective)):raise ValueError("PAM declared convergence before swap local optimum")
        labels_by_run[s["run_id"]]=labels;records.append(record)
    aggregate=read_csv(out/"cluster_metrics.csv")
    if len(aggregate)!=len(records) or {r["run_id"] for r in aggregate}!={r["run_id"] for r in records}:raise ValueError("Aggregate clustering table differs")
    for record in records:
        row=next(r for r in aggregate if r["run_id"]==record["run_id"])
        for key in calculated:
            value=record[key]
            if value is None:
                if row[key]!="":raise ValueError("Aggregate unavailable score filled")
            elif isinstance(value,(float,int)):
                if not np.isclose(float(row[key]),value,atol=1e-8,rtol=1e-7):raise ValueError("Aggregate numerical score differs")
            elif row[key]!=value:raise ValueError("Aggregate status differs")
    def compare(a,b,kind):
        ia=ids_by_rep[a["representation_id"]];ib=ids_by_rep[b["representation_id"]];common=[n for n in ia if n in ib]
        la=labels_by_run[a["run_id"]][[ia.index(n) for n in common]];lb=labels_by_run[b["run_id"]][[ib.index(n) for n in common]]
        return dict(comparison=kind,run_a=a["run_id"],run_b=b["run_id"],algorithm=a["algorithm"],**partition_agreement(la,lb))
    stability=[]
    for rep in plan["representations"]:
        for tag in ("cluster_count","PAM_seed","DBSCAN_epsilon","DBSCAN_min_samples"):
            for algorithm in ("HAC_average","PAM","DBSCAN"):
                members=[s for s in plan["specs"] if s["representation_id"]==rep["representation_id"] and s["algorithm"]==algorithm and tag in s["tags"]]
                stability.extend(compare(a,b,tag) for a,b in combinations(members,2))
    representatives=[s for s in plan["specs"] if s["representative"]];comparison=[]
    for s in representatives:
        rep=reps[s["representation_id"]]
        if rep["family"]!="rail_time":
            base=next(x for x in representatives if x["dataset_id"]==s["dataset_id"] and x["algorithm"]==s["algorithm"] and reps[x["representation_id"]]["family"]=="rail_time")
            comparison.append(compare(base,s,"original_rail_vs_embedding"))
            if not rep["main_parameter_input"]:
                baseline=next(x for x in representatives if x["dataset_id"]==s["dataset_id"] and x["algorithm"]==s["algorithm"] and reps[x["representation_id"]]["family"]==rep["family"] and reps[x["representation_id"]]["main_parameter_input"])
                comparison.append(compare(baseline,s,"projection_parameter_or_seed"))
        else:
            dataset=s["dataset_id"];parts=dataset.split("_");access=parts[1]
            if dataset.endswith("n34"):
                control=next(x for x in representatives if x["algorithm"]==s["algorithm"] and x["dataset_id"]=="access_"+access+"_n33" and reps[x["representation_id"]]["family"]=="rail_time")
                comparison.append(compare(control,s,"Taipei_vs_no_Taipei_common33"))
            if access!="60":
                target=dataset.replace("access_"+access+"_","access_60_",1)
                base=next(x for x in representatives if x["algorithm"]==s["algorithm"] and x["dataset_id"]==target and reps[x["representation_id"]]["family"]=="rail_time")
                comparison.append(compare(base,s,"Macao_access"))
            if dataset.endswith("n34") and "_alpha_5_" not in dataset:
                target=dataset.replace("_alpha_"+parts[3]+"_","_alpha_5_")
                base=next(x for x in representatives if x["algorithm"]==s["algorithm"] and x["dataset_id"]==target and reps[x["representation_id"]]["family"]=="rail_time")
                comparison.append(compare(base,s,"Taipei_penalty_magnitude"))
    write_csv(out/"partition_stability.csv",stability,list(stability[0]));write_csv(out/"representation_comparison.csv",comparison,list(comparison[0]))
    rep_records=[r for s,r in zip(plan["specs"],records) if s["representative"]]
    write_csv(out/"representative_cluster_quality.csv",rep_records,list(rep_records[0]))
    assignment=[]
    names={n["node_id"]:n["representative_city"] for n in read_csv(inputs/"nodes_34.csv")}
    for s in representatives:
        assignment.extend(dict(run_id=s["run_id"],representation_id=s["representation_id"],dataset_id=s["dataset_id"],family=reps[s["representation_id"]]["family"],algorithm=s["algorithm"],
            node_id=n,city=names[n],cluster=int(labels_by_run[s["run_id"]][j]),is_noise=bool(labels_by_run[s["run_id"]][j]<0)) for j,n in enumerate(ids_by_rep[s["representation_id"]]))
    write_csv(out/"representative_city_assignments.csv",assignment,list(assignment[0]))
    result=dict(output_dir=str(out),verified_runs=len(records),representative_partitions=len(representatives),label_hashes_passed=True,node_order_passed=True,
        quality_metrics_reproduced=True,PAM_swap_local_optima_verified=True,parameter_seed_stability_pairs=len(stability),representation_comparisons=len(comparison),
        unavailable_silhouette_runs=sum(r["silhouette_input"] is None for r in records),noise_excluded_from_scores=True,
        nonconverged_PAM_runs=sum(r["algorithm"]=="PAM" and not r["converged"] for r in records),
        geographic_cluster_R_figures_complete=False,external_interpretation_complete=False,report_started=False,
        note="No automatic winner. DBSCAN degenerate partitions retained; compare coverage and flags. ARI/NMI noise-as-label and common-assigned variants both reported.")
    write_json(out/"cluster_verification.json",result);return result
