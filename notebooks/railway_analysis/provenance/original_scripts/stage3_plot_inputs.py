"""Assistant-side preparation of verified plot tables; no model fitting."""
import csv
import json
import hashlib
import shutil
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.optimize import linear_sum_assignment
from stage1_collect import ROOT,write_csv,write_json
from stage1b_transfer import read_csv
from stage1i_dated_schedule import sha
from stage3_clustering import verify_and_summarize,current_cluster_plan
from stage2_geography import current_reference


def prepare():
    verified=verify_and_summarize();source=Path(verified["output_dir"])
    folder,plan,inputs,_=current_cluster_plan();ref,_,nodes,_=current_reference()
    out=ROOT/"data/analysis/assistant_stage3_plot_inputs_20261114";out.mkdir(exist_ok=True)
    for name in ("cluster_metrics.csv","partition_stability.csv","representation_comparison.csv","representative_city_assignments.csv","representative_cluster_quality.csv"):
        shutil.copy2(source/name,out/name)
    shutil.copy2(folder/"representation_inventory.csv",out/"representation_inventory.csv")
    shutil.copy2(ref/"nodes_34_geographic_reference.csv",out/"nodes_34_geographic_reference.csv")
    shutil.copy2(ref/"projected_graticule.csv",out/"projected_graticule.csv")
    reps={r["representation_id"]:r for r in plan["representations"]};specs={s["run_id"]:s for s in plan["specs"]}
    metrics=read_csv(source/"cluster_metrics.csv");metric_index={r["run_id"]:r for r in metrics}
    assignments=read_csv(source/"representative_city_assignments.csv");by_run={}
    for row in assignments:by_run.setdefault(row["run_id"],[]).append(row)
    colors={};mappings=[]
    for algorithm in ("HAC_average","PAM","DBSCAN"):
        reference=next(s for s in plan["specs"] if s["representative"] and s["algorithm"]==algorithm and s["dataset_id"]=="access_60_n33" and reps[s["representation_id"]]["family"]=="rail_time")
        ref_labels={r["node_id"]:int(r["cluster"]) for r in by_run[reference["run_id"]]}
        ref_clusters=sorted({c for c in ref_labels.values() if c>=0})
        for run,rows in by_run.items():
            if specs[run]["algorithm"]!=algorithm:continue
            cluster_ids=sorted({int(r["cluster"]) for r in rows if int(r["cluster"])>=0});counts=np.zeros((len(cluster_ids),len(ref_clusters)),dtype=int)
            for row in rows:
                a=int(row["cluster"]);b=ref_labels.get(row["node_id"],-1)
                if a>=0 and b>=0:counts[cluster_ids.index(a),ref_clusters.index(b)]+=1
            mapping={-1:"噪声"}
            if counts.size:
                ii,jj=linear_sum_assignment(-counts)
                for i,j in zip(ii,jj):
                    if counts[i,j]>0:mapping[cluster_ids[i]]="C"+str(j+1)
            next_id=len(ref_clusters)+1
            for a in cluster_ids:
                if a not in mapping:mapping[a]="C"+str(next_id);next_id+=1
            colors[run]=mapping;mappings.extend(dict(run_id=run,raw_label=a,display_cluster=b,reference_run_id=reference["run_id"]) for a,b in mapping.items())
    write_csv(out/"display_label_mapping.csv",mappings,list(mappings[0]))
    plot_rows=[];node_index={n["node_id"]:n for n in nodes}
    for row in assignments:
        rep=reps[row["representation_id"]];node=node_index[row["node_id"]]
        details=json.loads((source/(row["run_id"]+"_metrics.json")).read_text(encoding="utf-8"))["details"]
        plot_rows.append(dict(**row,display_cluster=colors[row["run_id"]][int(row["cluster"])],
            main_parameter_input=rep["main_parameter_input"],geo_x_km=node["aeqd_x_km"],geo_y_km=node["aeqd_y_km"],
            is_medoid=row["node_id"] in details.get("medoid_node_ids",[])))
    write_csv(out/"assignments_for_plot.csv",plot_rows,list(plot_rows[0]))
    mds_rows=[]
    for rep in reps.values():
        if rep["family"]=="MDS" and rep["main_parameter_input"]:
            mds_rows.extend(dict(dataset_id=rep["dataset_id"],**r) for r in read_csv(Path(rep["source_file"])))
    write_csv(out/"MDS_display_coordinates.csv",mds_rows,list(mds_rows[0]))
    enriched=[]
    for row in read_csv(source/"representation_comparison.csv"):
        extra={}
        for suffix in ("a","b"):
            metric=metric_index[row["run_"+suffix]];rep=reps[metric["representation_id"]];parts=rep["dataset_id"].split("_")
            extra.update({"dataset_"+suffix:rep["dataset_id"],"family_"+suffix:rep["family"],"main_"+suffix:rep["main_parameter_input"],
                "access_"+suffix:int(parts[1]),"alpha_"+suffix:int(parts[3]) if "alpha" in parts else ""})
        enriched.append(dict(**row,**extra))
    write_csv(out/"comparison_for_plot.csv",enriched,list(enriched[0]))
    stable=[]
    for row in read_csv(source/"partition_stability.csv"):
        metric=metric_index[row["run_a"]]
        stable.append(dict(**row,family=metric["family"],dataset_id=metric["dataset_id"],representation_id=metric["representation_id"]))
    write_csv(out/"stability_for_plot.csv",stable,list(stable[0]))
    segments=[];leaves=[];cuts=[]
    for dataset in ("access_60_alpha_5_n34","access_60_n33"):
        spec=next(s for s in plan["specs"] if s["dataset_id"]==dataset and s["algorithm"]=="HAC_average" and s["representative"] and reps[s["representation_id"]]["family"]=="rail_time")
        details=json.loads((source/(spec["run_id"]+"_metrics.json")).read_text(encoding="utf-8"))["details"]
        rows=by_run[spec["run_id"]];n=len(rows);children=details["children"];heights=details["merge_distances"];order=[]
        def visit(i):
            if i<n:order.append(i)
            else:
                for child in children[i-n]:visit(child)
        visit(2*n-2);positions={leaf:float(j+1) for j,leaf in enumerate(order)};height={j:0. for j in range(n)}
        for j,(a,b) in enumerate(children):
            parent=n+j;positions[parent]=(positions[a]+positions[b])/2;height[parent]=float(heights[j])
            for child in (a,b):segments.append(dict(dataset_id=dataset,x=positions[child],y=height[child],xend=positions[child],yend=height[parent]))
            segments.append(dict(dataset_id=dataset,x=positions[a],y=height[parent],xend=positions[b],yend=height[parent]))
        leaves.extend(dict(dataset_id=dataset,x=positions[j],city=rows[j]["city"],node_id=rows[j]["node_id"],display_cluster=colors[spec["run_id"]][int(rows[j]["cluster"])]) for j in range(n))
        lower=float(heights[n-4-1]);upper=float(heights[n-4])
        cuts.append(dict(dataset_id=dataset,cut_height=(lower+upper)/2,tie_at_cut=lower==upper))
    write_csv(out/"HAC_tree_segments.csv",segments,list(segments[0]));write_csv(out/"HAC_tree_leaves.csv",leaves,list(leaves[0]));write_csv(out/"HAC_tree_cuts.csv",cuts,list(cuts[0]))
    write_json(out/"provenance.json",dict(user_source_dir=str(source),verified=True,course_clusters_fit_by_assistant=False,
        color_policy="Display labels only: positive-overlap Hungarian matching to same-algorithm raw33 k4 reference; unmatched groups receive new colors, noise stays grey. Raw labels unchanged. Colors not semantically shared across algorithms.",
        code_sha256=sha(Path(__file__))))
    return dict(output_dir=str(out),representative_assignments=len(plot_rows),comparison_rows=len(enriched),stability_rows=len(stable))


if __name__=="__main__":print(json.dumps(prepare(),ensure_ascii=True))
