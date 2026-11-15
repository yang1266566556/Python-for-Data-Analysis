"""Precomputed-distance clustering and explicit evaluation contracts."""
import numpy as np
from sklearn.cluster import AgglomerativeClustering,DBSCAN
from sklearn.metrics import (silhouette_score,calinski_harabasz_score,davies_bouldin_score,
                             adjusted_rand_score,normalized_mutual_info_score)


def validate_distance(distance):
    d=np.asarray(distance,dtype=float)
    if d.ndim!=2 or d.shape[0]!=d.shape[1] or len(d)<3 or not np.isfinite(d).all() or (d<0).any() or not np.allclose(d,d.T) or not np.allclose(np.diag(d),0):
        raise ValueError("Expected finite nonnegative symmetric distance with zero diagonal")
    return d


def pam_swap(distance,k,seed=42,max_iter=100,tol=1e-10):
    """Random distinct medoids followed by best exhaustive single-medoid SWAP.

    This transparent PAM-style implementation uses random initialization rather
    than the classical deterministic BUILD step; no global optimum is claimed.
    """
    d=validate_distance(distance);n=len(d)
    if not 2<=k<n:raise ValueError("Invalid medoid count")
    rng=np.random.default_rng(seed);medoids=sorted(int(v) for v in rng.choice(n,k,replace=False))
    initial=list(medoids)
    def objective(m):return float(np.min(d[:,m],axis=1).sum())
    cost=objective(medoids);trace=[cost];converged=False
    for iteration in range(max_iter):
        best_cost=cost;best=None
        for old in medoids:
            for new in range(n):
                if new in medoids:continue
                trial=sorted(new if x==old else x for x in medoids);candidate=objective(trial)
                if candidate<best_cost-tol*max(1.,abs(cost)):
                    best_cost=candidate;best=trial
        if best is None:converged=True;break
        medoids=best;cost=best_cost;trace.append(cost)
    labels=np.argmin(d[:,medoids],axis=1).astype(int)
    # A medoid owns its own point even if zero-distance duplicates create ties.
    for i,m in enumerate(medoids):labels[m]=i
    return labels,dict(initial_medoid_indices=initial,medoid_indices=medoids,objective=cost,objective_trace=trace,
        accepted_swaps=len(trace)-1,max_iter=max_iter,converged=converged,
        stop_reason="no improving single-medoid swap" if converged else "maximum swap iterations reached",
        initialization="seeded random distinct medoids; no deterministic BUILD",objective_definition="sum of distance to nearest medoid in normalized input units")


def cluster_model(algorithm,parameters,distance):
    d=validate_distance(distance)
    if algorithm=="PAM":return pam_swap(d,**parameters)
    if algorithm=="HAC_average":
        model=AgglomerativeClustering(n_clusters=parameters["k"],metric="precomputed",linkage="average",compute_distances=True)
        labels=model.fit_predict(d.copy())
        return labels,dict(children=model.children_.tolist(),merge_distances=model.distances_.tolist(),
            linkage="average",metric="precomputed",converged=True,stop_reason="hierarchy constructed; cut at requested cluster count",iteration_count=None)
    if algorithm=="DBSCAN":
        model=DBSCAN(eps=parameters["eps"],min_samples=parameters["min_samples"],metric="precomputed",n_jobs=1)
        labels=model.fit_predict(d.copy())
        return labels,dict(core_sample_indices=model.core_sample_indices_.tolist(),converged=True,
            stop_reason="density expansion completed",iteration_count=None,
            metric="precomputed",min_samples_includes_self=True)
    raise ValueError("Unknown clustering algorithm")


def quality_metrics(distance,labels,rail_distance,features=None):
    d=validate_distance(distance);rail=validate_distance(rail_distance);labels=np.asarray(labels,dtype=int)
    if labels.shape!=(len(d),) or rail.shape!=d.shape:raise ValueError("Label/reference shape differs")
    mask=labels>=0;assigned=int(mask.sum());clusters=len(np.unique(labels[mask]));noise=int((~mask).sum())
    sizes={int(c):int(np.sum(labels==c)) for c in sorted(np.unique(labels[mask]))}
    result=dict(n_clusters=clusters,n_noise=noise,assigned_count=assigned,assigned_fraction=assigned/len(labels),
        smallest_cluster=min(sizes.values()) if sizes else 0,largest_cluster=max(sizes.values()) if sizes else 0,
        silhouette_input=None,silhouette_original_rail=None,calinski_harabasz=None,davies_bouldin=None,
        silhouette_status="",euclidean_indices_status="not applicable to original dissimilarity matrix")
    if assigned<3:result["silhouette_status"]="too few non-noise points"
    elif clusters<2:result["silhouette_status"]="fewer than two non-noise clusters"
    elif clusters>=assigned:result["silhouette_status"]="each assigned point is its own cluster"
    else:
        result["silhouette_status"]="computed on non-noise points only"
        result["silhouette_input"]=float(silhouette_score(d[np.ix_(mask,mask)],labels[mask],metric="precomputed"))
        result["silhouette_original_rail"]=float(silhouette_score(rail[np.ix_(mask,mask)],labels[mask],metric="precomputed"))
        if features is not None:
            x=np.asarray(features,dtype=float)
            if x.shape!=(len(d),2) or not np.isfinite(x).all():raise ValueError("Invalid Euclidean features")
            result["calinski_harabasz"]=float(calinski_harabasz_score(x[mask],labels[mask]))
            result["davies_bouldin"]=float(davies_bouldin_score(x[mask],labels[mask]))
            result["euclidean_indices_status"]="computed on saved Euclidean embedding, non-noise points only"
    if features is not None and result["silhouette_input"] is None:
        result["euclidean_indices_status"]="not computed: "+result["silhouette_status"]
    for key in ("silhouette_input","silhouette_original_rail","calinski_harabasz","davies_bouldin"):
        if result[key] is not None and not np.isfinite(result[key]):result[key]=None
    return result


def partition_agreement(a,b):
    a=np.asarray(a,dtype=int);b=np.asarray(b,dtype=int)
    if a.shape!=b.shape or a.ndim!=1 or len(a)<3:raise ValueError("Partition node alignment differs")
    common=(a>=0)&(b>=0);n=int(common.sum());ka=len(np.unique(a[common]));kb=len(np.unique(b[common]))
    meaningful=n>=3 and ka>=2 and kb>=2
    return dict(common_nodes=len(a),common_assigned_count=n,common_assigned_fraction=n/len(a),
        ari_including_noise_as_label=float(adjusted_rand_score(a,b)),nmi_including_noise_as_label=float(normalized_mutual_info_score(a,b)),
        noise_membership_agreement=float(np.mean((a<0)==(b<0))),
        ari_common_assigned=float(adjusted_rand_score(a[common],b[common])) if meaningful else None,
        nmi_common_assigned=float(normalized_mutual_info_score(a[common],b[common])) if meaningful else None,
        common_partition_status="computed" if meaningful else "too few common assigned nodes or trivial common partition",
        nontrivial_all_nodes=bool(len(np.unique(a))>=2 and len(np.unique(b))>=2))
