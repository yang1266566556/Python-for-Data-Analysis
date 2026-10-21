from pathlib import Path
import json, hashlib, shutil
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support, confusion_matrix

P = Path(r'D:\Python for Data Analysis\notebooks\imbalanced_classification')
R = P/'q7_runs/20261021_130908_69c906'
def read(name): return pd.read_csv(R/(name+'.csv'))
def js(path): return json.loads(path.read_text(encoding='utf-8'))
def close(a,b): np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-12)
d=np.load(P/'runs/20261020_221259_7f297c/data/dataset_and_split.npz')
X,y,tr,te=[d[k] for k in ['X','y','train_idx','test_idx']]
m=js(R/'q7_manifest.json'); labels=np.arange(10)
assert m['data_split_sha256']==hashlib.sha256(X.tobytes()+y.tobytes()+tr.tobytes()+te.tobytes()).hexdigest()
assert m['models']['none']==js(P/'q4_runs/20261021_122610_cb3b24/q4_manifest.json')['model_parameters']['SVC']
assert [k for k,v in m['models']['none'].items() if v!=m['models']['balanced'][k]]==['class_weight']
counts=np.bincount(y[tr],minlength=10)
assert m['minority_labels']==sorted(sorted(labels.tolist(),key=lambda c:(counts[c],c))[:5])
assert m['majority_class']==0
weights=read('q7_weights').sort_values('class_label')
close(weights.train_count,counts);close(weights.none_weight,1);close(weights.balanced_weight,len(tr)/(10*counts))
cv=read('q7_cv_predictions');cvscore=read('q7_cv_scores').set_index(['strategy','fold'])
assert len(cv)==7200 and len(cvscore)==10
for (strategy,fold),g in cv.groupby(['strategy','fold']):
    ids=tr[d[f'fold_{fold}_validation']]
    assert np.array_equal(g.sample_id,ids) and np.array_equal(g.y_true,y[ids])
    close(cvscore.loc[(strategy,fold)], [accuracy_score(g.y_true,g.y_pred),f1_score(g.y_true,g.y_pred,labels=labels,average='macro',zero_division=0)])
summary=cvscore.groupby('strategy').agg(['mean','std'])
summary.columns=[f'{a}_{b}' for a,b in summary.columns]
close(summary.sort_index(),read('q7_cv_summary').set_index('strategy').loc[summary.index])
close(cvscore.loc['balanced']-cvscore.loc['none'],read('q7_cv_deltas').set_index('fold'))
pred=read('q7_predictions');pcs=read('q7_per_class').set_index(['strategy','class_label'])
overall=read('q7_test_summary').set_index('strategy');groups=read('q7_group_summary').set_index(['strategy','group'])
assert len(pred)==2400
for strategy,g in pred.groupby('strategy'):
    assert np.array_equal(g.sample_id,te) and np.array_equal(g.y_true,y[te])
    close(overall.loc[strategy],[accuracy_score(g.y_true,g.y_pred),f1_score(g.y_true,g.y_pred,labels=labels,average='macro',zero_division=0)])
    p,r,f,s=precision_recall_fscore_support(g.y_true,g.y_pred,labels=labels,zero_division=0)
    close(pcs.loc[strategy][['precision','recall','f1','support']],np.array([p,r,f,s]).T)
    cm=read('q7_confusion_counts').query('strategy == @strategy').pivot(index='true_label',columns='predicted_label',values='count')
    close(cm,confusion_matrix(g.y_true,g.y_pred,labels=labels))
    for group,ids in [('minority_5',m['minority_labels']),('majority_class',[0])]:
        mask=np.isin(g.y_true,ids)
        close(groups.loc[(strategy,group)],[mask.sum(),r[ids].mean(),f[ids].mean(),accuracy_score(g.y_true[mask],g.y_pred[mask])])
changes=read('q7_class_changes').set_index('class_label')
close(changes[['precision_change','recall_change','f1_change']],pcs.loc['balanced'][['precision','recall','f1']]-pcs.loc['none'][['precision','recall','f1']])
assert np.array_equal(changes.train_minority_group,changes.index.isin(m['minority_labels']))
diags=js(R/'q7_fit_diagnostics.json'); assert len(diags)==12
assert len({(r['strategy'],r['phase'],r['fold']) for r in diags})==12
for row in diags:
    ids=tr if row['phase']=='final' else tr[d[f"fold_{row['fold']}_fit"]]
    ct=np.bincount(y[ids],minlength=10)
    close(row['fit_class_counts'],ct)
    close(row['actual_class_weights'],np.ones(10) if row['strategy']=='none' else len(ids)/(10*ct))
    assert row['fit_status']==0 and row['warning_count']==0
assert js(R/'q7_warnings.json')==[] and m['warning_count']==0
ids=['7efe1a43-f93b-4e32-82d3-ab602813635f','07f1f11a-cb0d-4ba4-96aa-23ab68f0dea1','7d5571c4-988b-4715-b260-3cddefa142ec','596f5cd8-bec2-4143-ade8-9c4332d91650','b456164d-5d5e-4824-bc1b-1341a06b008b','80b60b7c-2bc3-4849-8b03-04abebc802fe']
dest=P/'materials/q7/batch_01';dest.mkdir(parents=True,exist_ok=True)
for uid in ids:
    src=Path(r'C:\Users\yang\AppData\Local\Temp')/f'codex-clipboard-{uid}.png'
    dst=dest/src.name
    if not dst.exists(): shutil.copy2(src,dst)
    assert src.read_bytes()==dst.read_bytes()
record=dict(status='passed',cv_predictions_checked=len(cv),test_predictions_checked=len(pred),fit_diagnostics_checked=len(diags),screenshots_archived=6,
    checks=['data hash and original splits','Q4 parameters except class_weight','all CV/test scores','per-class and confusion counts','fold-specific weights','groups and deltas','warnings and solver status'],
    limits='No model refit. Fit/preprocessing execution supported by supplied code and diagnostics. Missing screenshot of fit_and_predict helper; CV delta code line clipped at right.')
(R/'assistant_verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False));print(overall.to_string());print(groups.to_string())
