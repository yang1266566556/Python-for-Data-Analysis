"""Authenticate final course matrices and freeze precomputed-distance inputs."""

from railway_project_io import read_project_json, script_hash_matches
import json
import shutil
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from stage1_collect import ROOT,TZ,TRAIN_FIELDS,write_csv,write_json
from stage1b_transfer import read_csv
from stage1n_supplement import combined_records_for_n
from stage1i_dated_schedule import sha

FINAL_JOB="user_stage1n_special_20261114_140146_715895"
MARKER=ROOT/"evidence/stage2_inputs_current.json"


def read_matrix(path):
    frame=pd.read_csv(path,index_col=0,encoding="utf-8-sig")
    if list(frame.index)!=list(frame.columns):raise ValueError("Matrix row/column labels differ")
    return frame


def verify_final():
    rows,_,protocol,_=combined_records_for_n()
    folder=ROOT/"data/processed"/FINAL_JOB
    summary=read_project_json(folder / 'special_region_matrix_summary.json')
    if not summary["full34_algorithm_ready"] or summary["generated_full34_matrices"]!=9:raise ValueError("Final34 prerequisites not complete")
    if summary["protocol"]!=protocol:raise ValueError("Final source protocol changed")
    if [{k:str(r[k]) for k in TRAIN_FIELDS} for r in rows]!=read_csv(folder/"combined_records_with_sources.csv"):raise ValueError("Final source CSV differs from raw replay")
    for name,digest in summary["analysis_code_sha256"].items():
        if not script_hash_matches(ROOT / 'scripts' / name, digest):raise ValueError("Final analysis code changed")
    nodes=read_csv(folder/"nodes_34.csv");ids=[n["node_id"] for n in nodes]
    mask=read_matrix(folder/"taipei_structural_unreachable_mask.csv").to_numpy().astype(bool)
    expected=np.array([[a!=b and "N34" in (a,b) for b in ids] for a in ids])
    if not np.array_equal(mask,expected) or mask.sum()!=66:raise ValueError("Taipei structural mask differs")
    catalog=read_csv(folder/"matrix_input_catalog.csv")
    if len(catalog)!=9:raise ValueError("Expected nine full34 configurations")
    for access in (30,60,90):
        raw=read_matrix(folder/f"raw34_access_{access}.csv").to_numpy()
        if np.isnan(raw).any() or not np.array_equal(np.isinf(raw),mask):raise ValueError("Ordinary missing or unexpected structural cells")
        if not np.allclose(np.diag(raw),0):raise ValueError("Nonzero diagonal")
        sub=read_matrix(folder/f"directed33_access_{access}.csv").to_numpy()
        sym=read_matrix(folder/f"symmetric33_access_{access}.csv").to_numpy()
        if not np.isfinite(sub).all() or not np.allclose(sym,(sub+sub.T)/2):raise ValueError("33-node control check failed")
        for entry in [c for c in catalog if int(c["access_assumption_min"])==access]:
            if entry["algorithm_ready"]!="True":raise ValueError("Catalog entry not ready")
            direct=read_matrix(folder/entry["directed_csv"]).to_numpy()
            transformed=raw.copy();transformed[mask]=float(entry["penalty_min"])
            symmetric=read_matrix(folder/entry["symmetric_csv"]).to_numpy()
            if not np.allclose(direct,transformed) or not np.allclose(symmetric,(direct+direct.T)/2):raise ValueError("Penalty/symmetrization mismatch")
            if not np.isfinite(symmetric).all() or (symmetric<0).any():raise ValueError("Invalid algorithm input")
            share=direct[mask].sum()/direct.sum()
            if not np.isclose(share,float(entry["penalty_share_of_pairwise_sum"])):raise ValueError("Penalty share mismatch")
    return folder,summary,catalog,nodes,len(rows)


def prepare(actor="user"):
    if actor not in ("user","assistant"):raise ValueError("Invalid actor")
    source,summary,catalog,nodes,count=verify_final()
    out=ROOT/"data/analysis"/(actor+"_stage2_inputs_"+datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True,exist_ok=False)
    inventory=[]
    for c in catalog:
        name=c["matrix_id"]
        src=source/c["symmetric_csv"];dest=out/(name+"_n34.csv");shutil.copy2(src,dest)
        inventory.append(dict(dataset_id=name+"_n34",node_count=34,access_min=int(c["access_assumption_min"]),alpha=int(c["penalty_alpha"]),
                              matrix_file=dest.name,sha256=sha(dest),baseline=name=="access_60_alpha_5",role="full34_with_structural_penalty"))
    for access in (30,60,90):
        dest=out/f"access_{access}_n33.csv";shutil.copy2(source/f"symmetric33_access_{access}.csv",dest)
        inventory.append(dict(dataset_id=f"access_{access}_n33",node_count=33,access_min=access,alpha="",matrix_file=dest.name,
                              sha256=sha(dest),baseline=access==60,role="no_Taipei_control_with_explicit_Macao_access"))
    base=read_matrix(out/"access_60_n33.csv")
    positive=base.to_numpy()[np.triu_indices(33,1)]
    scale=float(np.median(positive))
    if scale<=0:raise ValueError("Invalid common distance scale")
    subset=base.drop(index="N33",columns="N33");dest=out/"access_60_n32.csv";subset.to_csv(dest,encoding="utf-8-sig")
    inventory.append(dict(dataset_id="access_60_n32",node_count=32,access_min="",alpha="",matrix_file=dest.name,sha256=sha(dest),baseline=False,
                          role="no_Macao_no_Taipei_control_from_same_final_version"))
    write_csv(out/"matrix_inventory.csv",inventory,list(inventory[0]))
    write_csv(out/"nodes_34.csv",nodes,list(nodes[0]))
    finite_count=33*32
    qc=[dict(check="final_source_and_derived_rows",value=count),dict(check="ordinary_missing_in_raw34",value=0),
        dict(check="finite_directed_pairs_33",value=finite_count),dict(check="Taipei_structural_directed_cells",value=66),
        dict(check="ready_full34_variants",value=9),dict(check="source_conflicts",value=summary["source_conflicts"]),
        dict(check="common_positive_distance_scale_minutes",value=scale)]
    write_csv(out/"final_quality_summary.csv",qc,["check","value"])
    result=dict(actor=actor,source_job=FINAL_JOB,source_summary_sha256=sha(source/"special_region_matrix_summary.json"),input_node_counts=[34,33,32],
                matrix_count=len(inventory),baseline_datasets=[x["dataset_id"] for x in inventory if x["baseline"]],
                common_scale_minutes=scale,scale_rule="all algorithms receive D/median(reference33 positive upper-triangle D); same constant for every variant",
                matrix_rows_are_features=False,metric_closure_applied=False,baseline_seed=42,planned_seeds=[0,42,2026],
                source_record_count=count,ordinary_missing=0,structural_penalty_cells=66,full34_verified=True,
                output_dir=str(out),notes=["Symmetric input is explicit mean of source directions","Non-Euclidean and triangle violations are retained",
                    "Macao access assumption and Taipei finite penalty remain separate from observed service times","No embedding or clustering run in preparation"])
    write_json(out/"input_manifest.json",result)
    if actor=="user":write_json(MARKER,dict(output_dir=str(out),manifest_sha256=sha(out/"input_manifest.json")))
    return result


def current_inputs():
    if not MARKER.exists():raise ValueError("Run problem2 core1 to freeze inputs first")
    marker=read_project_json(MARKER);folder=Path(marker["output_dir"])
    if sha(folder/"input_manifest.json")!=marker["manifest_sha256"]:raise ValueError("Input manifest changed")
    manifest=read_project_json(folder / 'input_manifest.json')
    inventory=read_csv(folder/"matrix_inventory.csv")
    for row in inventory:
        if sha(folder/row["matrix_file"])!=row["sha256"]:raise ValueError("Frozen matrix changed")
    return folder,manifest,inventory
