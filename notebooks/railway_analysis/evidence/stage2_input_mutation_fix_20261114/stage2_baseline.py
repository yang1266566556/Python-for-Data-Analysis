"""Precomputed-distance baselines; common external metrics, no plotting."""
import importlib.metadata as metadata
import inspect
import json
import time
import warnings
from datetime import datetime

import numpy as np
from scipy.spatial.distance import pdist,squareform
from scipy.stats import spearmanr
from sklearn.manifold import MDS,TSNE,trustworthiness

from stage1_collect import ROOT,TZ,write_csv,write_json,software_versions
from stage1b_transfer import read_csv
from stage1i_dated_schedule import sha
from stage2_inputs import current_inputs,read_matrix

MARKER=ROOT/"evidence/stage2_baseline_current.json"


def make_mds(seed=42,metric=True,max_iter=1000,n_init=4):
    params=dict(n_components=2,n_init=n_init,max_iter=max_iter,eps=1e-6,random_state=seed,n_jobs=1,normalized_stress=True)
    signature=inspect.signature(MDS).parameters
    if "metric_mds" in signature:params.update(metric_mds=metric,metric="precomputed",init="random")
    else:params.update(metric=metric,dissimilarity="precomputed")
    return MDS(**params),params


def make_model(algorithm,seed=42):
    if algorithm=="MDS":return make_mds(seed)
    if algorithm=="tSNE":
        params=dict(n_components=2,perplexity=10.,max_iter=1000,init="random",metric="precomputed",random_state=seed,
                    learning_rate="auto",early_exaggeration=12.,method="exact",n_jobs=1)
        return TSNE(**params),params
    if algorithm=="UMAP":
        from umap import UMAP
        params=dict(n_components=2,n_neighbors=10,min_dist=0.1,n_epochs=500,metric="precomputed",init="random",random_state=seed,transform_seed=seed,n_jobs=1)
        return UMAP(**params),params
    raise ValueError("Unknown algorithm")


def external_metrics(reference,embedding,k=5):
    reference=np.asarray(reference,dtype=float);embedding=np.asarray(embedding,dtype=float)
    n=len(reference)
    if reference.shape!=(n,n) or embedding.shape!=(n,2) or not np.isfinite(embedding).all():raise ValueError("Invalid metric inputs")
    upper=np.triu_indices(n,1);target=reference[upper];distances=pdist(embedding)
    denom=float(np.dot(distances,distances))
    scale=float(np.dot(target,distances)/denom) if denom>0 else 0.
    stress=float(np.sqrt(np.sum((target-scale*distances)**2)/np.sum(target**2)))
    ed=squareform(distances)
    original=reference.copy();np.fill_diagonal(original,np.inf);np.fill_diagonal(ed,np.inf)
    a=np.argsort(original,axis=1,kind="stable")[:,:k];b=np.argsort(ed,axis=1,kind="stable")[:,:k]
    overlap=float(np.mean([len(set(x)&set(y))/k for x,y in zip(a,b)]))
    return dict(external_scale_fitted_stress1=stress,distance_spearman=float(spearmanr(target,distances).statistic),
                neighbor_overlap_k5=overlap,trustworthiness_k5=float(trustworthiness(reference,embedding,n_neighbors=k,metric="precomputed")))


def run(actor="user"):
    if actor!="user":raise ValueError("Course baselines must be run by the user")
    try:metadata.version("umap-learn")
    except metadata.PackageNotFoundError:raise RuntimeError("Install approved umap-learn step, restart kernel, then rerun core1/core2")
    # Import first so package incompatibility is visible before creating runs.
    from umap import UMAP
    folder,manifest,inventory=current_inputs();nodes=read_csv(folder/"nodes_34.csv")
    labels={n["node_id"]:n["representative_city"] for n in nodes}
    chosen=[r for r in inventory if r["baseline"]=="True"]
    if len(chosen)!=2:raise ValueError("Expected full34 and no-Taipei33 baselines")
    env=software_versions();env["umap-learn"]=metadata.version("umap-learn")
    code_hashes={n:sha(ROOT/"scripts"/n) for n in ("stage2_baseline.py","stage2_inputs.py")}
    protocol=dict(input_manifest_sha256=sha(folder/"input_manifest.json"),seed=42,software=env,code_hashes=code_hashes)
    out=None
    if MARKER.exists():
        old=json.loads(MARKER.read_text(encoding="utf-8"));candidate=ROOT/old["output_relative"]
        if json.loads((candidate/"protocol.json").read_text(encoding="utf-8"))==protocol:out=candidate
    if out is None:
        out=ROOT/"data/analysis"/("user_stage2_baseline_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True,exist_ok=False)
        write_json(out/"protocol.json",protocol);write_json(MARKER,dict(output_relative=str(out.relative_to(ROOT))))
    all_metrics=[]
    for entry in chosen:
        frame=read_matrix(folder/entry["matrix_file"]);ids=list(frame.index)
        reference=frame.to_numpy(dtype=float)/manifest["common_scale_minutes"]
        if not np.isfinite(reference).all() or not np.allclose(reference,reference.T):raise ValueError("Input is not finite symmetric")
        for algorithm in ("MDS","tSNE","UMAP"):
            run_id=entry["dataset_id"]+"_"+algorithm+"_seed42"
            metrics_file=out/(run_id+"_metrics.json");coords_file=out/(run_id+"_coordinates.csv")
            if metrics_file.exists():
                saved=json.loads(metrics_file.read_text(encoding="utf-8"))
                if sha(coords_file)!=saved["coordinates_sha256"]:raise ValueError("Saved coordinates changed")
                all_metrics.append(saved["metrics"]);print("复用已完成：",run_id,flush=True);continue
            print("正在运行：",run_id,flush=True)
            estimator,params=make_model(algorithm)
            started=time.perf_counter()
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                coordinates=estimator.fit_transform(reference)
            elapsed=time.perf_counter()-started
            if coordinates.shape!=(len(ids),2) or not np.isfinite(coordinates).all():raise ValueError("Nonfinite embedding")
            values=external_metrics(reference,coordinates)
            network=np.array([i!="N34" for i in ids]);network_values=external_metrics(reference[np.ix_(network,network)],coordinates[network])
            native_loss=float(estimator.stress_) if algorithm=="MDS" else float(estimator.kl_divergence_) if algorithm=="tSNE" else ""
            native_name="normalized_stress1" if algorithm=="MDS" else "KL_divergence" if algorithm=="tSNE" else "not_exposed"
            record=dict(run_id=run_id,dataset_id=entry["dataset_id"],algorithm=algorithm,node_count=len(ids),seed=42,seconds=elapsed,
                        native_loss=native_loss,native_loss_definition=native_name,native_n_iter_attribute=getattr(estimator,"n_iter_",""),
                        convergence_trace_available=False,**values,**{"network_only_"+k:v for k,v in network_values.items()})
            write_csv(coords_file,[dict(node_id=node,city=labels[node],embedding_1=float(coordinates[i,0]),embedding_2=float(coordinates[i,1])) for i,node in enumerate(ids)],
                      ["node_id","city","embedding_1","embedding_2"])
            write_json(metrics_file,dict(metrics=record,parameters=params,warnings=[str(w.message) for w in caught],coordinates_sha256=sha(coords_file),
                note="External stress fits one isotropic distance scale. Native losses are not comparable across algorithms. Stable node-order tie rule for neighbor overlap; Taipei equal-penalty ties limit interpretation. No convergence curve is fabricated."))
            all_metrics.append(record)
            write_csv(out/"baseline_metrics.csv",all_metrics,list(all_metrics[0]))
            print("完成：",algorithm,"；外部stress=",round(values["external_scale_fitted_stress1"],4),"；秩相关=",round(values["distance_spearman"],4),flush=True)
    result=dict(output_dir=str(out),completed_runs=len(all_metrics),expected_runs=6,baseline_seed=42,input_dir=str(folder),software=env,
                parameter_experiments_complete=False,three_seed_stability_complete=False,plots_created_by_python=False,
                note="These are baseline numerical runs only; parameter sensitivity, three-seed stability, R figures and geographical comparison follow actual review.")
    write_json(out/"baseline_summary.json",result)
    write_csv(out/"baseline_metrics.csv",all_metrics,list(all_metrics[0]))
    return result


def verify_saved():
    """Authenticate six user-run coordinate files against the frozen inputs."""
    if not MARKER.exists():raise ValueError("Run problem2 core2 first")
    folder,manifest,inventory=current_inputs()
    marker=json.loads(MARKER.read_text(encoding="utf-8"));out=ROOT/marker["output_relative"]
    summary=json.loads((out/"baseline_summary.json").read_text(encoding="utf-8"))
    protocol=json.loads((out/"protocol.json").read_text(encoding="utf-8"))
    if protocol["input_manifest_sha256"]!=sha(folder/"input_manifest.json"):raise ValueError("Baseline input version differs")
    for name,digest in protocol["code_hashes"].items():
        if sha(ROOT/"scripts"/name)!=digest:raise ValueError("Baseline code version differs")
    records=[]
    for entry in [r for r in inventory if r["baseline"]=="True"]:
        matrix=read_matrix(folder/entry["matrix_file"]);ids=list(matrix.index)
        reference=matrix.to_numpy(dtype=float)/manifest["common_scale_minutes"]
        for algorithm in ("MDS","tSNE","UMAP"):
            run_id=entry["dataset_id"]+"_"+algorithm+"_seed42"
            saved=json.loads((out/(run_id+"_metrics.json")).read_text(encoding="utf-8"))
            coords_file=out/(run_id+"_coordinates.csv")
            if sha(coords_file)!=saved["coordinates_sha256"]:raise ValueError("Saved coordinates changed")
            rows=read_csv(coords_file)
            if [r["node_id"] for r in rows]!=ids:raise ValueError("Coordinate node order differs")
            coords=np.array([[float(r["embedding_1"]),float(r["embedding_2"])] for r in rows])
            calculated=external_metrics(reference,coords)
            network=np.array([node!="N34" for node in ids])
            calculated.update({"network_only_"+k:v for k,v in external_metrics(reference[np.ix_(network,network)],coords[network]).items()})
            record=saved["metrics"]
            for key,value in calculated.items():
                if not np.isfinite(value) or not np.isclose(value,float(record[key]),atol=1e-8,rtol=1e-7):raise ValueError("Saved metric does not reproduce: "+key)
            records.append(record)
    if len(records)!=6 or summary["completed_runs"]!=6:raise ValueError("Six baseline runs are not complete")
    aggregate=read_csv(out/"baseline_metrics.csv")
    if len(aggregate)!=6 or {r["run_id"] for r in aggregate}!={r["run_id"] for r in records}:raise ValueError("Aggregate table differs")
    for row in aggregate:
        record=next(r for r in records if r["run_id"]==row["run_id"])
        for key in calculated:
            if not np.isclose(float(row[key]),float(record[key]),atol=1e-8,rtol=1e-7):raise ValueError("Aggregate metric differs")
    result=dict(output_dir=str(out),verified_runs=6,coordinate_hashes_passed=True,node_order_passed=True,external_metrics_reproduced=True,
                parameter_experiments_complete=False,three_seed_stability_complete=False)
    write_json(out/"baseline_verification.json",result)
    return result
