from pathlib import Path
from datetime import datetime
import json, hashlib, shutil
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

P=Path(r'D:\Python for Data Analysis\notebooks\imbalanced_classification')
R=P/'q8_runs/20261021_132220_50e07c'; Q5=P/'q5_runs/20261021_124751_b53362'
def js(path): return json.loads(path.read_text(encoding='utf-8'))
def close(a,b): np.testing.assert_allclose(a,b,rtol=1e-10,atol=1e-12)
def read(name): return pd.read_csv(R/(name+'.csv'))
d=np.load(P/'runs/20261020_221259_7f297c/data/dataset_and_split.npz')
X,y,tr,te=[d[k] for k in ['X','y','train_idx','test_idx']]
m=js(R/'q8_manifest.json');sel=js(R/'q8_selection_before_test.json')
assert m['data_split_sha256']==sel['data_split_sha256']==hashlib.sha256(X.tobytes()+y.tobytes()+tr.tobytes()+te.tobytes()).hexdigest()
for f,h in sel['source_sha256'].items(): assert hashlib.sha256((Q5/f).read_bytes()).hexdigest()==h
plan=js(Q5/'q5_plan.json');assert m['base_parameters']==sel['model_parameters']==plan['base_parameters']['SVC']
gammas=next(s[3] for s in plan['scans'] if s[0]=='svc_gamma')
assert gammas==m['gamma_candidates']==sel['gamma_candidates']
for name,source in [('q8_reused_cv_summary','q5_summary.csv'),('q8_reused_cv_scores','q5_fold_scores.csv')]:
    orig=pd.read_csv(Q5/source).query("scan_id == 'svc_gamma'").reset_index(drop=True)
    pd.testing.assert_frame_equal(read(name),orig)
cv=read('q8_reused_cv_summary');folds=read('q8_reused_cv_scores')
best=cv.validation_macro_f1_mean.max()
idx=min(cv.loc[(cv.validation_macro_f1_mean-best).abs()<=1e-12,'candidate_index'],key=lambda i:gammas[i])
assert idx==sel['candidate_index'] and gammas[idx]==m['selected_gamma']==sel['selected_gamma']
winners=[]
for fold,g in folds.groupby('fold'):
    v=g.validation_macro_f1.max()
    winners.append(int(min(g.loc[(g.validation_macro_f1-v).abs()<=1e-12,'candidate_index'],key=lambda i:gammas[i])))
assert sel['fold_winner_indices']==winners and sel['wins']==winners.count(idx)
assert datetime.fromisoformat(sel['selected_at']) < datetime.fromisoformat(m['created_at'])
pred=read('q8_predictions');scores=read('q8_scores').set_index('candidate_index')
assert len(pred)==33600 and len(scores)==7
assert set(pred.subset)=={'train','test'}
assert set(pred.candidate_index)==set(range(7))
for (i,subset),g in pred.groupby(['candidate_index','subset']):
    ids=tr if subset=='train' else te
    assert np.array_equal(g.sample_id,ids) and np.array_equal(g.y_true,y[ids])
    assert np.isin(g.y_pred,np.arange(10)).all()
    close(g.gamma,gammas[i]);close(scores.loc[i,'gamma'],gammas[i])
    close(scores.loc[i,f'{subset}_accuracy'],accuracy_score(g.y_true,g.y_pred))
    close(scores.loc[i,f'{subset}_macro_f1'],f1_score(g.y_true,g.y_pred,labels=np.arange(10),average='macro',zero_division=0))
close(scores.train_test_gap,scores.train_macro_f1-scores.test_macro_f1)
assert np.array_equal(scores.selected_by_cv,scores.index==idx)
expected=scores.reset_index().merge(cv[['candidate_index','train_macro_f1_mean','validation_macro_f1_mean','validation_macro_f1_std','generalization_gap']],on='candidate_index',validate='one_to_one').rename(columns={'train_macro_f1_mean':'cv_train_macro_f1_mean','generalization_gap':'cv_train_validation_gap'})
pd.testing.assert_frame_equal(read('q8_comparison'),expected)
diags=js(R/'q8_fit_diagnostics.json');assert len(diags)==7
assert {r['candidate_index'] for r in diags}==set(range(7))
for r in diags:
    i=r['candidate_index'];assert r['parameters']=={**m['base_parameters'],'gamma':gammas[i]}
    assert r['scaler_n_samples_seen']==len(tr) and r['fit_status']==r['warning_count']==0
assert scores.fit_status.eq(0).all() and scores.warning_count.eq(0).all()
assert js(R/'q8_warnings.json')==[] and m['warning_count']==0
previous=pd.read_csv(P/'q7_runs/20261021_130908_69c906/q7_predictions.csv').query("strategy == 'none'")
assert np.array_equal(pred.query("candidate_index == @idx and subset == 'test'").y_pred,previous.y_pred)
assert pred.query("candidate_index == 6 and subset == 'test'").y_pred.eq(0).all()
uids=['f4db75f3-78c6-4341-bd10-685c1582bb76','a237ed4c-3f84-44f7-9518-5b9c572eccc6','ce2c1818-29e6-484a-afff-8fa88e2fc97c','bf0eaa0a-18ee-44e5-b1fd-412a82fe49b0']
dest=P/'materials/q8/batch_01';dest.mkdir(parents=True,exist_ok=True)
for uid in uids:
    src=Path(r'C:\Users\yang\AppData\Local\Temp')/f'codex-clipboard-{uid}.png';dst=dest/src.name
    if not dst.exists(): shutil.copy2(src,dst)
    assert src.read_bytes()==dst.read_bytes()
record=dict(status='passed',train_predictions_checked=25200,test_predictions_checked=8400,
    reused_cv_rows_checked=35,new_fit_diagnostics_checked=7,screenshots_archived=4,
    checks=['data and Q5 source hashes','original train/test ids and true labels','all 14 subset scores','CV selection and 5/5 fold winners','reused CV files and comparison merge','parameters and solver diagnostics','gamma=1 test predictions all class 0','recommended setting test predictions equal Q7 none'],
    limits='No model refit. Selection-before-test supported by source code and saved timestamps, not an independent execution trace. Q5 CV previously independently verified. No training-curve timing conclusions.')
(R/'assistant_verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))
print('gamma=1 test prediction counts:',pred.query("candidate_index == 6 and subset == 'test'").y_pred.value_counts().to_dict())
print('paired CV advantage gamma=1/24 vs .1:',(folds.query('candidate_index == 3').set_index('fold').validation_macro_f1-folds.query('candidate_index == 4').set_index('fold').validation_macro_f1).to_list())
