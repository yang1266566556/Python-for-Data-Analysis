# %% [markdown]
# # 问题8：SVC的gamma与拟合程度｜v1.0
# 在Python for Data Analysis (pda312)内核中从上到下运行全部单元；不必重跑前题。
# 复用第五题相同数据、标准化SVC及gamma扫描的五折验证，仅新增7次完整训练集拟合。
# 固定C=1、class_weight=None；第七题的balanced结果不改变本题已确定的参数方案。
# 推荐参数仅由第五题验证macro-F1确定，在读取本题测试预测之前锁定。
# 完整训练集与测试集曲线统一使用全部10类的macro-F1；同时保存Accuracy。
# 五折训练均值对应每折2880个拟合样本，完整训练分数对应3600个样本，不能混为同一条曲线。
# 完成后发核心代码与代表性输出截图，助手生成图表和合并分析；无需运行R。

# %%
# 公共初始化代码：读取固定数据和第五题验证证据
from pathlib import Path
from datetime import datetime
import hashlib
import json
import sys
import uuid
import warnings
import numpy as np
import pandas as pd
import sklearn
from IPython.display import display
from threadpoolctl import threadpool_limits
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import accuracy_score, f1_score

PROJECT_DIR = Path(r'D:\Python for Data Analysis\notebooks\imbalanced_classification')
SOURCE_DIR = PROJECT_DIR / 'runs/20261020_221259_7f297c'
Q5_DIR = PROJECT_DIR / 'q5_runs/20261021_124751_b53362'
assert Path(sys.executable).resolve() == Path(r'D:\anaconda\envs\pda312\python.exe').resolve(), '请选择pda312内核'
def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))
source = read_json(SOURCE_DIR / 'results/manifest.json')
q5_manifest = read_json(Q5_DIR / 'q5_manifest.json')
q5_plan = read_json(Q5_DIR / 'q5_plan.json')
assert sklearn.__version__ == q5_manifest['sklearn'] == source['versions']['scikit-learn']
with np.load(SOURCE_DIR / 'data/dataset_and_split.npz') as data:
    X, y = data['X'], data['y']
    train_idx, test_idx = data['train_idx'], data['test_idx']
    folds = [(data[f'fold_{i}_fit'].copy(), data[f'fold_{i}_validation'].copy()) for i in range(1,6)]
data_hash = hashlib.sha256(X.tobytes()+y.tobytes()+train_idx.tobytes()+test_idx.tobytes()).hexdigest()
assert data_hash == source['data_split_sha256'] == q5_manifest['data_split_sha256']
assert q5_manifest['cv_seed'] == source['cv_seed'] and not q5_manifest['test_set_evaluated']
X_train, y_train = X[train_idx], y[train_idx]
LABELS = np.arange(10)
cv_scores = pd.read_csv(Q5_DIR / 'q5_fold_scores.csv').query("scan_id == 'svc_gamma'").copy()
cv_summary = pd.read_csv(Q5_DIR / 'q5_summary.csv').query("scan_id == 'svc_gamma'").copy()
cv_summary = cv_summary.sort_values('candidate_index').reset_index(drop=True)
gamma_values = next(s[3] for s in q5_plan['scans'] if s[0] == 'svc_gamma')
base_params = q5_plan['base_parameters']['SVC'].copy()
assert base_params['C'] == 1 and base_params['class_weight'] is None
assert base_params['kernel'] == 'rbf' and q5_plan['preprocessing']['SVC'] == 'StandardScaler'
assert base_params == SVC(random_state=source['model_seed']).get_params(deep=False)
print('问题8 v1.0；Python',sys.version.split()[0], '；sklearn',sklearn.__version__)
print('复用第五题35次拟合的验证证据；本题新增完整训练拟合7次。')

# %%
# 辅助代码：核对复用的验证预测和汇总；本单元不训练，也不评价测试集
assert len(cv_scores) == 35 and len(cv_summary) == 7
assert cv_summary['eligible'].astype(str).str.lower().eq('true').all()
assert not cv_scores['convergence_warning'].astype(str).str.lower().eq('true').any()
assert cv_scores['fit_status'].eq(0).all()
for index, gamma in enumerate(gamma_values):
    row = cv_summary.loc[cv_summary.candidate_index == index].iloc[0]
    assert np.isclose(float(row.value_label), gamma, rtol=1e-12, atol=0)
    predictions = pd.read_csv(Q5_DIR / 'validation_predictions' / f'svc_gamma_{index:02d}.csv')
    part = cv_scores.loc[cv_scores.candidate_index == index].sort_values('fold')
    assert len(part) == 5 and len(predictions) == len(train_idx)
    for fold, (_, val_idx) in enumerate(folds, start=1):
        g = predictions.loc[predictions.fold == fold]
        assert np.array_equal(g.sample_id, train_idx[val_idx])
        assert np.array_equal(g.y_true, y_train[val_idx])
        expected = part.loc[part.fold == fold].iloc[0]
        score = f1_score(g.y_true,g.y_pred,labels=LABELS,average='macro',zero_division=0)
        np.testing.assert_allclose(score, expected.validation_macro_f1, atol=1e-12)
        np.testing.assert_allclose(accuracy_score(g.y_true,g.y_pred), expected.validation_accuracy, atol=1e-12)
    for metric in ['train_accuracy','train_macro_f1','validation_accuracy','validation_macro_f1']:
        np.testing.assert_allclose(part[metric].mean(),row[f'{metric}_mean'],atol=1e-12)
        np.testing.assert_allclose(part[metric].std(ddof=1),row[f'{metric}_std'],atol=1e-12)
print('复用验证证据核验通过；训练分数只核对汇总，未重算第五题训练预测。')

# %%
# 问题8—核心代码（1/3）：只按验证分数选择gamma，并先保存选择记录
best_score = cv_summary.validation_macro_f1_mean.max()
tied = cv_summary.loc[(cv_summary.validation_macro_f1_mean-best_score).abs() <= 1e-12]
selected_index = min(tied.candidate_index.tolist(), key=lambda i: gamma_values[i])
selected_gamma = gamma_values[selected_index]  # 并列时取更小gamma，沿用第五题规则
previous = next(s for s in read_json(Q5_DIR / 'q5_selections.json') if s['scan_id'] == 'svc_gamma')
assert previous['candidate_index'] == selected_index and previous['selected_value'] == selected_gamma
fold_winners = []
for fold, part in cv_scores.groupby('fold'):
    top = part.validation_macro_f1.max()
    candidates = part.loc[(part.validation_macro_f1-top).abs() <= 1e-12, 'candidate_index'].tolist()
    fold_winners.append(min(candidates,key=lambda i:gamma_values[i]))
Q8_DIR = PROJECT_DIR / 'q8_runs' / (datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
Q8_DIR.mkdir(parents=True, exist_ok=False)
source_files = ['q5_plan.json','q5_manifest.json','q5_summary.csv','q5_fold_scores.csv','q5_selections.json']
source_hashes = {name:hashlib.sha256((Q5_DIR/name).read_bytes()).hexdigest() for name in source_files}
selection = dict(selected_gamma=selected_gamma, candidate_index=int(selected_index),
    rule='maximum validation macro-F1 mean; ties within 1e-12 choose smaller gamma',
    selected_before_q8_test_evaluation=True, selected_at=datetime.now().astimezone().isoformat(),
    q5_source=str(Q5_DIR), source_sha256=source_hashes, data_split_sha256=data_hash,
    gamma_candidates=gamma_values, model_parameters=base_params,
    fold_winner_indices=fold_winners, wins=int(fold_winners.count(selected_index)))
(Q8_DIR/'q8_selection_before_test.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
cv_summary.to_csv(Q8_DIR/'q8_reused_cv_summary.csv',index=False,encoding='utf-8-sig')
cv_scores.to_csv(Q8_DIR/'q8_reused_cv_scores.csv',index=False,encoding='utf-8-sig')
print('已在本题测试评价前锁定gamma：',selected_gamma,'；各折独立推荐一致次数：',selection['wins'],'/5')
display(cv_summary[['value_label','train_macro_f1_mean','validation_macro_f1_mean','validation_macro_f1_std']].round(6))

# %%
# 问题8—核心代码（2/3）：完整训练/测试曲线；仅gamma变化，每次重新拟合Pipeline
result_rows, prediction_parts, warning_rows, diagnostics = [], [], [], []
X_test, y_test = X[test_idx], y[test_idx]
with threadpool_limits(limits=1):
    for index, gamma in enumerate(gamma_values):
        params = {**base_params, 'gamma': gamma}
        model = Pipeline([('scale',StandardScaler()),('model',SVC(**params))])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            model.fit(X_train,y_train)  # 标准化仅使用完整训练集拟合
            train_pred = model.predict(X_train)
            test_pred = model.predict(X_test)
        for item in caught:
            warning_rows.append(dict(candidate_index=index,gamma=gamma,
                category=item.category.__name__,message=str(item.message),
                convergence_warning=issubclass(item.category,ConvergenceWarning)))
            print('警告：',gamma,item.category.__name__,str(item.message))
        estimator = model.named_steps['model']
        diagnostics.append(dict(candidate_index=index,gamma=gamma,fit_status=int(estimator.fit_status_),
            n_iter=estimator.n_iter_.tolist(),n_support=estimator.n_support_.tolist(),
            scaler_n_samples_seen=int(model.named_steps['scale'].n_samples_seen_),
            parameters=estimator.get_params(deep=False),warning_count=len(caught)))
        row = dict(candidate_index=index,gamma=gamma,selected_by_cv=index==selected_index,
            fit_status=int(estimator.fit_status_),warning_count=len(caught))
        for subset,ids,truth,pred in [('train',train_idx,y_train,train_pred),('test',test_idx,y_test,test_pred)]:
            row[f'{subset}_accuracy'] = accuracy_score(truth,pred)
            row[f'{subset}_macro_f1'] = f1_score(truth,pred,labels=LABELS,average='macro',zero_division=0)
            prediction_parts.append(pd.DataFrame(dict(candidate_index=index,gamma=gamma,
                subset=subset,sample_id=ids,y_true=truth,y_pred=pred)))
        result_rows.append(row)
        print(f'gamma={gamma:.6g} 完成；fit_status={estimator.fit_status_}',flush=True)
results = pd.DataFrame(result_rows)
results['train_test_gap'] = results.train_macro_f1 - results.test_macro_f1
print('完整训练集与固定测试集指标；测试得分不用于改变已锁定推荐：')
display(results[['gamma','train_accuracy','test_accuracy','train_macro_f1','test_macro_f1','train_test_gap','selected_by_cv']].round(6))

# %%
# 问题8—核心代码（3/3）：合并验证证据、显示泛化差距；不根据测试排名选参
comparison = results.merge(cv_summary[['candidate_index','train_macro_f1_mean',
    'validation_macro_f1_mean','validation_macro_f1_std','generalization_gap']],
    on='candidate_index',validate='one_to_one')
comparison = comparison.rename(columns={'train_macro_f1_mean':'cv_train_macro_f1_mean',
    'generalization_gap':'cv_train_validation_gap'})
display(comparison[['gamma','cv_train_macro_f1_mean','validation_macro_f1_mean',
    'validation_macro_f1_std','cv_train_validation_gap','train_macro_f1','test_macro_f1']].round(6))
print('推荐gamma仍为：', selected_gamma)
print('拟合区域标注依据第五题折内训练/验证的共同变化；不把训练—测试差距本身当作选参规则。')
print('只对实际采样点给出证据判断；未采样区间不宣称存在精确分界。')

# %%
# 辅助代码：保存全部真实预测及诊断，供助手核验和R技能绘图
results.to_csv(Q8_DIR/'q8_scores.csv',index=False,encoding='utf-8-sig')
comparison.to_csv(Q8_DIR/'q8_comparison.csv',index=False,encoding='utf-8-sig')
pd.concat(prediction_parts,ignore_index=True).to_csv(Q8_DIR/'q8_predictions.csv',index=False,encoding='utf-8-sig')
manifest = dict(code_version='1.0',source_dir=str(SOURCE_DIR),q5_source=str(Q5_DIR),
    data_split_sha256=data_hash,python=sys.version,sklearn=sklearn.__version__,executable=sys.executable,
    gamma_candidates=gamma_values,selected_gamma=selected_gamma,base_parameters=base_params,
    preprocessing='StandardScaler in Pipeline; full training only for new fits; fold-fitted in reused Q5 CV',
    labels=LABELS.tolist(),zero_division=0,cv_seed=source['cv_seed'],model_seed=source['model_seed'],
    selection='locked from Q5 validation before Q8 test predictions; no test tuning',
    reused_cv_fits=35,new_full_training_fits=7,thread_limit=1,warning_count=len(warning_rows),
    created_at=datetime.now().astimezone().isoformat(),output_dir=str(Q8_DIR))
for filename,content in [('q8_manifest.json',manifest),('q8_warnings.json',warning_rows),('q8_fit_diagnostics.json',diagnostics)]:
    (Q8_DIR/filename).write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding='utf-8')
print('保存完成：',Q8_DIR)
print('警告数：',len(warning_rows),'；非零fit_status数：',int((results.fit_status!=0).sum()))
print('请截图：核心代码1及推荐值、核心代码2及结果、核心代码3及比较结果、保存成功信息。')
print('长表不必全部截图；收到后助手从CSV制作完整表格和训练/测试/验证曲线。')

# %% [markdown]
# ## 图形与分析安排
# 图8-1绘制完整训练与测试macro-F1曲线；图8-2为复用的五折训练/验证均值及±样本标准差。
# 在两图标出仅由验证确定的推荐值，针对有证据的采样点标注拟合状态。
# 低gamma若训练和验证得分均低，支持拟合不足；高gamma若训练得分高而验证崩落，支持过拟合。
# “合适”仅指当前候选集合与固定配置内验证表现较好，不等于消除过拟合或找到全局最优。
# 五折推荐一致也不保证对其他随机划分、新数据或其他C值保持最优。
# 目前本题新增训练/测试实验尚未运行，不预填测试曲线和结论。
# 原始截图将进入报告正文；本题收到并核验后自动继续第九题的理论分析。
#
# ## AI使用记录
# OpenAI Codex，GPT-6家族，精确版本未知。原题见request_original.txt。
# 本轮用户原文“第七题的截图”，依据持续授权自动推进到本题。
# AI辅助方案：复用第五题验证、预先锁定推荐、提供Python实验和预测导出代码。
# 助手只进行静态/API及读取验证证据的检查，没有代跑本题模型训练。
# 学生实际运行、修改、核验和理解情况待据实补充。
