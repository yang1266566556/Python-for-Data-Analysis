# %% [markdown]
# # 问题5：单参数变化与训练集内部验证｜v1.0
# 独立运行：选择pda312内核，按顺序执行全部代码单元。本题计算量比前几题大，逐候选打印进度。
# 只使用第一题的3600例训练数据，复用第一题保存的五折划分；不计算测试集分数，不用测试集选参。
# 每个模型研究两个参数，每次仅改变其中一个，另一个及其余配置固定在下表所列锚点。
# 这不是联合网格搜索；两个扫描各自的推荐值不能直接拼成“联合最优参数”。
#
# | 模型 | 扫描参数及取值 | 另一参数固定值与目的 |
# | --- | --- | --- |
# | 逻辑回归 | C：0.001,0.01,0.1,1,10,100 | l1_ratio=0；研究正则化强弱 |
# | 逻辑回归 | l1_ratio：0,0.25,0.5,0.75,1 | C=1；研究L2至L1的混合与稀疏性 |
# | 决策树 | max_depth：1,2,4,6,10,16,None | min_samples_leaf=1；控制树深 |
# | 决策树 | min_samples_leaf：1,2,5,10,20,50 | max_depth=None；控制叶节点最小样本量 |
# | KNN | n_neighbors：1,3,5,9,15,31,61 | p=2；从局部细拟合到更平滑投票 |
# | KNN | p：1,1.5,2,3 | n_neighbors=5；研究不同Minkowski距离几何 |
# | SVC | C：0.01,0.1,1,10,100 | gamma='scale'；研究间隔与训练误差权衡 |
# | SVC | gamma：0.001,0.005,0.01,1/24,0.1,0.5,1 | C=1；研究RBF核局部作用范围 |
#
# 逻辑回归本题固定solver='saga'、max_iter=2000，兼容L1/L2混合；与第三题默认基线分开记录。
# sklearn 1.9.0直接用l1_ratio控制L2(0)、Elastic Net(0到1之间)和L1(1)，不传已弃用penalty参数。
# 三个涉及距离或正则化尺度的模型（LR、KNN、SVC）固定用StandardScaler；树固定不标准化。
# 此设置依据算法机制预先固定，不按第四题测试分数挑选。所有缩放均在各折训练部分内fit。
# SVC标准化后若全部24维方差非零，gamma='scale'等于1/24；数值gamma扫描包含该参考值。
#
# 预定选参指标：五折验证macro-F1均值；同时报告Accuracy及各折得分。标准差用ddof=1。
# 得分在绝对容差1e-12内并列：C/gamma取小，max_depth取浅（None视为无限），叶样本量/k取大，
# l1_ratio取大（偏好更强稀疏倾向，实际稀疏性仍以系数记录为准）。p没有统一复杂度顺序，
# 并列时按预定顺序2、1、1.5、3选择，优先保留默认欧氏距离，不宣称p=2必然更简单。
# 只有五折完成且无收敛警告、求解失败状态的候选才参与推荐；其他候选仍保留结果及警告。
# 小于一个标准差的分数差不自动构成并列，也不自动意味着统计等价；均值选出的推荐不代表稳定胜出。

# %%
# 公共初始化代码｜读取训练集与固定五折，检查环境；不计算测试集指标
from pathlib import Path
from datetime import datetime
from time import perf_counter
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
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import accuracy_score, f1_score

# 脚本入口使用自身路径定位，支持在任意工作目录执行。
_location = Path(__file__).resolve().parent
for _parent in (_location, *_location.parents):
    _notebooks = _parent if _parent.name == "notebooks" else _parent / "notebooks"
    if (_notebooks / "imbalanced_classification" / "common.py").is_file():
        if str(_notebooks) not in sys.path:
            sys.path.insert(0, str(_notebooks))
        break
else:
    raise FileNotFoundError("未找到作业目录，请从仓库根目录或notebooks启动")
from imbalanced_classification.common import (
    PROJECT_DIR, check_environment, SOURCE_DIR, load_fixed_dataset, dataset_sha256
)
check_environment()
source = json.loads((SOURCE_DIR / "results/manifest.json").read_text(encoding="utf-8"))
assert sklearn.__version__ == source["versions"]["scikit-learn"], "sklearn版本与第一题不一致"
saved = load_fixed_dataset(SOURCE_DIR)
data_hash = dataset_sha256(saved["X"], saved["y"], saved["train_idx"], saved["test_idx"])
train_sample_ids = saved["train_idx"].copy()
X_train, y_train = saved["X"][train_sample_ids], saved["y"][train_sample_ids]
folds = [(saved[f"fold_{i}_fit"].copy(), saved[f"fold_{i}_validation"].copy()) for i in range(1, 6)]
assert data_hash == source["data_split_sha256"]
LABELS, MODEL_SEED = np.arange(10), source["model_seed"]
for fit_idx, val_idx in folds:
    assert not np.intersect1d(fit_idx, val_idx).size
    assert np.array_equal(np.sort(np.r_[fit_idx, val_idx]), np.arange(len(y_train)))
    assert np.array_equal(np.unique(y_train[fit_idx]), LABELS) and np.array_equal(np.unique(y_train[val_idx]), LABELS)
assert np.array_equal(np.sort(np.concatenate([v for _, v in folds])), np.arange(len(y_train)))
Q5_DIR = PROJECT_DIR / "q5_runs" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
Q5_DIR.mkdir(parents=True, exist_ok=False)
(Q5_DIR / "validation_predictions").mkdir()
print("问题5 v1.0；Python", sys.version.split()[0], "；sklearn", sklearn.__version__)
print("仅使用训练集：", X_train.shape, "；固定5折；模型种子：", MODEL_SEED)
print("本题输出目录：", Q5_DIR)

# %%
# 问题5—核心代码（1/4）｜固定模型、预处理、参数范围与锚点
base_models = {
    "LogisticRegression": LogisticRegression(solver="saga", max_iter=2000, random_state=MODEL_SEED),
    "DecisionTree": DecisionTreeClassifier(random_state=MODEL_SEED),
    "KNN": KNeighborsClassifier(),
    "SVC": SVC(random_state=MODEL_SEED),
}
base_pipelines = {name: Pipeline([
    ("scale", "passthrough" if name == "DecisionTree" else StandardScaler()),
    ("model", model),
]) for name, model in base_models.items()}
SCANS = [
    ("lr_C", "LogisticRegression", "C", [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]),
    ("lr_l1_ratio", "LogisticRegression", "l1_ratio", [0.0, 0.25, 0.5, 0.75, 1.0]),
    ("tree_max_depth", "DecisionTree", "max_depth", [1, 2, 4, 6, 10, 16, None]),
    ("tree_min_samples_leaf", "DecisionTree", "min_samples_leaf", [1, 2, 5, 10, 20, 50]),
    ("knn_n_neighbors", "KNN", "n_neighbors", [1, 3, 5, 9, 15, 31, 61]),
    ("knn_p", "KNN", "p", [1, 1.5, 2, 3]),
    ("svc_C", "SVC", "C", [0.01, 0.1, 1.0, 10.0, 100.0]),
    ("svc_gamma", "SVC", "gamma", [0.001, 0.005, 0.01, 1/24, 0.1, 0.5, 1.0]),
]
selection_rules = {"C": "smaller", "gamma": "smaller", "max_depth": "shallower_None_last",
    "min_samples_leaf": "larger", "n_neighbors": "larger", "l1_ratio": "larger",
    "p": "priority_2_1_1.5_3"}
plan = dict(scans=SCANS, base_parameters={k: v.get_params(deep=False) for k, v in base_models.items()},
    preprocessing={k: "none" if k == "DecisionTree" else "StandardScaler" for k in base_models},
    selection_metric="validation_macro_f1_mean", tie_atol=1e-12, tie_rules=selection_rules)
(Q5_DIR / "q5_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
print("候选总数：", sum(len(values) for _, _, _, values in SCANS), "；总拟合次数：", 5*sum(len(values) for _, _, _, values in SCANS))
display(pd.DataFrame(SCANS, columns=["scan_id", "model", "parameter", "values"]))
print("范围已预定并保存；每个扫描从base_pipelines重新克隆，不继承前一次扫描的推荐参数。")

# %%
# 问题5—核心代码（2/4）：单候选五折验证函数｜定义本身不训练
# 本函数包含实际拟合和评分逻辑，截图时与下一个调用单元一并保留。
fold_rows, warning_rows = [], []
def evaluate_candidate(scan_id, name, parameter, value, candidate_index):
    candidate = clone(base_pipelines[name]).set_params(**{f"model__{parameter}": value})
    oof_parts = []
    for fold, (fit_idx, val_idx) in enumerate(folds, start=1):
        model = clone(candidate)  # 每折全新Pipeline，缩放仅在该折训练部分拟合。
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            start = perf_counter()
            model.fit(X_train[fit_idx], y_train[fit_idx])
            fit_seconds = perf_counter() - start
            pred_val = model.predict(X_train[val_idx])
            pred_train = model.predict(X_train[fit_idx])
        estimator = model.named_steps["model"]
        convergence_warning = any(issubclass(w.category, ConvergenceWarning) for w in caught)
        fit_status = int(getattr(estimator, "fit_status_", 0))
        for item in caught:
            warning_rows.append(dict(scan_id=scan_id, candidate_index=candidate_index, fold=fold,
                category=item.category.__name__, message=str(item.message)))
        fold_rows.append(dict(scan_id=scan_id, model=name, parameter=parameter,
            candidate_index=candidate_index, value_label=str(value), fold=fold,
            train_accuracy=accuracy_score(y_train[fit_idx], pred_train),
            train_macro_f1=f1_score(y_train[fit_idx], pred_train, labels=LABELS, average="macro", zero_division=0),
            validation_accuracy=accuracy_score(y_train[val_idx], pred_val),
            validation_macro_f1=f1_score(y_train[val_idx], pred_val, labels=LABELS, average="macro", zero_division=0),
            convergence_warning=convergence_warning, fit_status=fit_status, fit_seconds=fit_seconds,
            max_n_iter=int(np.max(estimator.n_iter_)) if hasattr(estimator, "n_iter_") else None,
            nonzero_coefficients=int(np.count_nonzero(estimator.coef_)) if hasattr(estimator, "coef_") else None,
            tree_depth=estimator.get_depth() if hasattr(estimator, "get_depth") else None,
            support_vectors=int(np.sum(estimator.n_support_)) if hasattr(estimator, "n_support_") else None))
        oof_parts.append(pd.DataFrame(dict(fold=fold, sample_id=train_sample_ids[val_idx],
                                           y_true=y_train[val_idx], y_pred=pred_val)))
    # 每个候选完成后保存折外预测及累计折得分，不必等全部候选结束。
    pd.concat(oof_parts, ignore_index=True).to_csv(
        Q5_DIR / "validation_predictions" / f"{scan_id}_{candidate_index:02d}.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(fold_rows).to_csv(Q5_DIR / "q5_fold_scores.csv", index=False, encoding="utf-8-sig")
    (Q5_DIR / "q5_warnings.json").write_text(json.dumps(warning_rows, ensure_ascii=False, indent=2), encoding="utf-8")

# %%
# 问题5—核心代码（3/4）：运行8组单参数扫描｜输出：进度、验证均值与警告
fold_rows.clear(); warning_rows.clear()  # 重新运行本单元会重做全部235次拟合。
total = sum(len(values) for _, _, _, values in SCANS)
done = 0
with threadpool_limits(limits=1):
    for scan_id, name, parameter, values in SCANS:
        for candidate_index, value in enumerate(values):
            evaluate_candidate(scan_id, name, parameter, value, candidate_index)
            done += 1
            recent = fold_rows[-len(folds):]
            mean_f1 = np.mean([row["validation_macro_f1"] for row in recent])
            bad_folds = sum(row["convergence_warning"] or row["fit_status"] != 0 for row in recent)
            print(f"[{done}/{total}] {name} {parameter}={value}：验证macro-F1={mean_f1:.6f}；求解异常折数={bad_folds}", flush=True)
fold_scores = pd.DataFrame(fold_rows)
assert len(fold_scores) == total * len(folds)
print("全部候选完成；警告总数：", len(warning_rows))
for message in sorted({w["message"] for w in warning_rows}):
    print("警告全文：", message)

# %%
# 问题5—核心代码（4/4）：汇总与预定规则选参｜不使用测试集，不拼接两个最优参数
summary_rows, selections = [], []
score_columns = ["train_accuracy", "train_macro_f1", "validation_accuracy", "validation_macro_f1"]
def simplicity_key(parameter, value):
    if parameter in ("C", "gamma"): return value
    if parameter == "max_depth": return float("inf") if value is None else value
    if parameter in ("min_samples_leaf", "n_neighbors", "l1_ratio"): return -value
    return [2, 1, 1.5, 3].index(value)  # p没有统一复杂度排序，按预设默认优先规则。

for scan_id, name, parameter, values in SCANS:
    for index, value in enumerate(values):
        part = fold_scores.query("scan_id == @scan_id and candidate_index == @index")
        row = dict(scan_id=scan_id, model=name, parameter=parameter, candidate_index=index,
                   value_label=str(value), fold_count=len(part),
                   eligible=len(part)==5 and not part.convergence_warning.any() and part.fit_status.eq(0).all())
        for metric in score_columns:
            row[f"{metric}_mean"], row[f"{metric}_std"] = part[metric].mean(), part[metric].std(ddof=1)
        row["generalization_gap"] = row["train_macro_f1_mean"] - row["validation_macro_f1_mean"]
        summary_rows.append(row)
    candidates = [row for row in summary_rows if row["scan_id"] == scan_id and row["eligible"]]
    if not candidates:
        selections.append(dict(scan_id=scan_id, model=name, parameter=parameter, status="no_eligible_candidate"))
        continue
    best_score = max(row["validation_macro_f1_mean"] for row in candidates)
    tied = [row for row in candidates if abs(row["validation_macro_f1_mean"] - best_score) <= 1e-12]
    best = min(tied, key=lambda row: simplicity_key(parameter, values[row["candidate_index"]]))
    selections.append(dict(scan_id=scan_id, model=name, parameter=parameter, status="selected",
        selected_value=values[best["candidate_index"]], candidate_index=best["candidate_index"],
        validation_macro_f1_mean=best["validation_macro_f1_mean"], validation_macro_f1_std=best["validation_macro_f1_std"],
        validation_accuracy_mean=best["validation_accuracy_mean"], tie_count=len(tied)))
summary = pd.DataFrame(summary_rows)
for scan_id, _, _, _ in SCANS:
    print("扫描：", scan_id)
    display(summary.query("scan_id == @scan_id")[["value_label", "train_macro_f1_mean",
        "validation_macro_f1_mean", "validation_macro_f1_std", "validation_accuracy_mean",
        "validation_accuracy_std", "generalization_gap", "eligible"]].round(6))
print("按预定规则推荐：每行只对应一个扫描，不能将两行参数直接拼成联合最优。")
display(pd.DataFrame(selections).round(6))

# %%
# 辅助代码：折内赢家与保存｜用于判断推荐的稳定性，不用于额外挑选参数
fold_winners = []
for scan_id, name, parameter, values in SCANS:
    valid_indices = summary.query("scan_id == @scan_id and eligible").candidate_index.tolist()
    for fold in range(1, 6):
        part = fold_scores.query("scan_id == @scan_id and fold == @fold").copy()
        part = part[part.candidate_index.isin(valid_indices)]
        if part.empty: continue
        best_score = part.validation_macro_f1.max()
        tied = part.loc[(part.validation_macro_f1 - best_score).abs() <= 1e-12, "candidate_index"].tolist()
        winner = min(tied, key=lambda index: simplicity_key(parameter, values[index]))
        fold_winners.append(dict(scan_id=scan_id, fold=fold, candidate_index=winner, value_label=str(values[winner])))
winner_table = pd.DataFrame(fold_winners, columns=["scan_id", "fold", "candidate_index", "value_label"])
summary.to_csv(Q5_DIR / "q5_summary.csv", index=False, encoding="utf-8-sig")
winner_table.to_csv(Q5_DIR / "q5_fold_winners.csv", index=False, encoding="utf-8-sig")
(Q5_DIR / "q5_selections.json").write_text(json.dumps(selections, ensure_ascii=False, indent=2), encoding="utf-8")
manifest = dict(code_version="1.0", source_dir=str(SOURCE_DIR), data_split_sha256=data_hash,
    python=sys.version, sklearn=sklearn.__version__, executable=sys.executable,
    model_seed=MODEL_SEED, cv_seed=source["cv_seed"], folds=5, training_samples=len(y_train),
    labels=LABELS.tolist(), zero_division=0, std_definition="sample std ddof=1; not a confidence interval",
    source_fold_indices="saved folds from question 1; positions within training set",
    selection_metric="mean of 5 validation macro-F1 scores", test_set_evaluated=False,
    total_candidates=total, total_fits=len(fold_scores), warning_count=len(warning_rows),
    created_at=datetime.now().astimezone().isoformat(), output_dir=str(Q5_DIR))
(Q5_DIR / "q5_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("折内最优值出现次数（五折不是五次独立实验，次数仅作稳定性描述）：")
display(winner_table.groupby(["scan_id", "value_label"]).size().rename("fold_wins").reset_index())
print("保存完成：", Q5_DIR)
print("测试集未用于评分或选参；请发送核心代码、各扫描得分表、推荐表和警告（如有）。")

# %% [markdown]
# ## 截图、图表与分析
# 核心代码分四部分，验证函数包含关键fit/predict逻辑，也需截图，可拆成多张，不要缩成一张长图。
# 输出至少包含8组参数扫描表和推荐表；运行进度无需每行截图，原始逐折分数和预测均已保存。
# 每条曲线会报告训练集内部五折验证均值与±1样本标准差，分别绘制macro-F1与Accuracy，不伪造测试曲线。
# 收到后助手检查参数敏感区间、收益趋缓区间、边界最佳值、折间波动和推荐稳定性，不只列最优值。
# 不同折得分相关；均值±标准差不是置信区间。某个参数在边界最好只支持当前扫描范围内的结论。
# 未收敛候选保留并标记，不默默删除、不据测试集修补参数；若无可用候选，先说明问题再补充验证。
# 理论机制可解释趋势，但参数极端行为与过/欠拟合结论仍需区分实测范围和机制推断。
# 该题结果也将供问题6和9引用。问题6以理论为主，没有必要重复训练或伪造独立运行截图。
#
# ## AI使用记录
# OpenAI Codex，模型家族GPT-6，精确版本未知。原问题5与统一协议见request_original.txt。
# 本轮请求原文“第四题的截图”，按此前授权核验无问题后自动继续下一题。
# AI辅助：单参数扫描方案、Pipeline折内预处理、固定五折评分、选参规则、警告及预测导出。
# 代码仅做静态检查，助手未代跑第五题模型；当前尚无第五题分数或性能结论。
# 学生实际运行、修改、验证与理解待据实补充。截图将与后续skill生成的图片共同进入文档。
