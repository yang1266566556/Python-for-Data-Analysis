# %% [markdown]
# # 问题7：用类别权重处理不平衡分类｜v1.0
# 独立运行：选择Python for Data Analysis (pda312)，按顺序运行全部代码单元。
# 选用SVC是因为它原生支持class_weight，能在同一模型上进行只改变类别权重的清晰对照。
# 两种策略：原始权重None与balanced；统一StandardScaler、C=1、gamma='scale'及第四题其余配置。
# 不把第五题不同扫描的推荐拼成联合最优，也不根据已经看过的测试结果调整权重强度。
# balanced在每次fit时按该训练部分计算 w_c=n/(K*n_c)，少数类获得更高误分类惩罚。
# SVC实际使用每类不同的C_c=C*w_c；不改变训练样本个数，不重采样验证集或测试集。
# 先用第一题保存的五折训练集内部验证比较，再按预定方案在完整训练集拟合两策略并展示测试结果。
# 本题不会反复据测试结果修改策略。CV部分10次拟合，最终部分2次拟合，共12次。
# 少数类组预先定义为训练样本数最少的5类（计数并列时标签较小者优先），多数类为最多类。
# 分组仅依据训练计数，用于描述结果；全部10类仍统一参与总体macro-F1。

# %%
# 公共初始化代码｜读取第一题固定数据与五折；输出：环境、来源与目录
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
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support, confusion_matrix

PROJECT_DIR = Path(r"D:\Python for Data Analysis\notebooks\imbalanced_classification")
SOURCE_DIR = PROJECT_DIR / "runs/20261020_221259_7f297c"
Q4_SOURCE = PROJECT_DIR / "q4_runs/20261021_122610_cb3b24"
assert Path(sys.executable).resolve() == Path(r"D:\anaconda\envs\pda312\python.exe").resolve(), "请选择pda312内核"
source = json.loads((SOURCE_DIR / "results/manifest.json").read_text(encoding="utf-8"))
assert sklearn.__version__ == source["versions"]["scikit-learn"], "请先核对sklearn版本"
with np.load(SOURCE_DIR / "data/dataset_and_split.npz") as saved:
    X, y = saved["X"], saved["y"]
    train_idx, test_idx = saved["train_idx"], saved["test_idx"]
    folds = [(saved[f"fold_{i}_fit"].copy(), saved[f"fold_{i}_validation"].copy()) for i in range(1, 6)]
data_hash = hashlib.sha256(X.tobytes() + y.tobytes() + train_idx.tobytes() + test_idx.tobytes()).hexdigest()
assert data_hash == source["data_split_sha256"]
X_train, X_test, y_train, y_test = X[train_idx], X[test_idx], y[train_idx], y[test_idx]
LABELS, MODEL_SEED = np.arange(10), source["model_seed"]
for fit_idx, val_idx in folds:
    assert not np.intersect1d(fit_idx, val_idx).size
    assert np.array_equal(np.unique(y_train[fit_idx]), LABELS)
    assert np.array_equal(np.unique(y_train[val_idx]), LABELS)
Q7_DIR = PROJECT_DIR / "q7_runs" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
Q7_DIR.mkdir(parents=True, exist_ok=False)
print("问题7 v1.0；Python", sys.version.split()[0], "；sklearn", sklearn.__version__)
print("训练/测试样本数：", len(y_train), len(y_test))
print("本题输出目录：", Q7_DIR)

# %%
# 问题7—核心代码（1/4）：仅改变类别权重，预先定义少数类组
train_counts = np.bincount(y_train, minlength=10)
majority_class = int(np.flatnonzero(train_counts == train_counts.max())[0])
minority_labels = sorted(sorted(LABELS.tolist(), key=lambda c: (train_counts[c], c))[:5])
strategies = {
    "none": Pipeline([("scale", StandardScaler()), ("model", SVC(random_state=MODEL_SEED))]),
    "balanced": Pipeline([("scale", StandardScaler()), ("model", SVC(class_weight="balanced", random_state=MODEL_SEED))]),
}
base_params = strategies["none"].named_steps["model"].get_params(deep=False)
q4_manifest = json.loads((Q4_SOURCE / "q4_manifest.json").read_text(encoding="utf-8"))
assert base_params == q4_manifest["model_parameters"]["SVC"]
balanced_params = strategies["balanced"].named_steps["model"].get_params(deep=False)
assert {k for k in base_params if base_params[k] != balanced_params[k]} == {"class_weight"}
weight_table = pd.DataFrame({"class_label": LABELS, "train_count": train_counts,
    "none_weight": 1.0, "balanced_weight": len(y_train)/(len(LABELS)*train_counts)})
display(weight_table.round(6))
print("多数类：", majority_class, "；训练样本最少的5类：", minority_labels)
print("上表为完整训练集权重；交叉验证中由每个训练折重新计算，禁止用完整训练集权重替代折内权重。")

# %%
# 辅助代码：拟合、预测与警告记录｜包含实际训练逻辑，截图时请保留
warning_rows, fit_records = [], []
def fit_and_predict(template, fit_X, fit_y, eval_X, strategy, phase, fold):
    fitted = clone(template)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fitted.fit(fit_X, fit_y)  # Pipeline只在本次fit_X上拟合标准化和类别权重。
        prediction = fitted.predict(eval_X)
    for item in caught:
        warning_rows.append(dict(strategy=strategy, phase=phase, fold=fold,
            category=item.category.__name__, message=str(item.message),
            is_convergence_warning=issubclass(item.category, ConvergenceWarning)))
        print(f"{phase}/{strategy}/fold={fold} [{item.category.__name__}]：{item.message}")
    estimator = fitted.named_steps["model"]
    fit_counts = np.bincount(fit_y, minlength=10)
    expected = np.ones(10) if strategy == "none" else len(fit_y)/(10*fit_counts)
    np.testing.assert_allclose(estimator.class_weight_, expected)
    fit_records.append(dict(strategy=strategy, phase=phase, fold=fold,
        fit_status=int(estimator.fit_status_), n_iter=estimator.n_iter_.tolist(),
        n_support=estimator.n_support_.tolist(), actual_class_weights=estimator.class_weight_.tolist(),
        fit_class_counts=fit_counts.tolist(), warning_count=len(caught)))
    return prediction, fitted

# %%
# 问题7—核心代码（2/4）：先进行训练集内部五折比较｜不调整权重强度
cv_rows, cv_prediction_parts = [], []
with threadpool_limits(limits=1):
    for name, template in strategies.items():
        for fold, (fit_idx, val_idx) in enumerate(folds, start=1):
            pred, _ = fit_and_predict(template, X_train[fit_idx], y_train[fit_idx],
                                     X_train[val_idx], name, "cv", fold)
            cv_rows.append(dict(strategy=name, fold=fold,
                accuracy=accuracy_score(y_train[val_idx], pred),
                macro_f1=f1_score(y_train[val_idx], pred, labels=LABELS, average="macro", zero_division=0)))
            cv_prediction_parts.append(pd.DataFrame(dict(strategy=name, fold=fold,
                sample_id=train_idx[val_idx], y_true=y_train[val_idx], y_pred=pred)))
        print(name, "的5折验证完成。", flush=True)
cv_scores = pd.DataFrame(cv_rows)
cv_summary = cv_scores.groupby("strategy")[["accuracy", "macro_f1"]].agg(["mean", "std"])
cv_summary.columns = [f"{m}_{stat}" for m, stat in cv_summary.columns]
cv_summary = cv_summary.reset_index()
print("训练集内部验证：均值与样本标准差（ddof=1）")
display(cv_summary.round(6))
cv_delta = cv_scores.query("strategy == 'balanced'").set_index("fold")[["accuracy", "macro_f1"]] - cv_scores.query("strategy == 'none'").set_index("fold")[["accuracy", "macro_f1"]]
print("同一验证折上balanced−none的差值：")
display(cv_delta.round(6))

# %%
# 问题7—核心代码（3/4）：完整训练集拟合，两种预定策略的测试集展示
test_rows, class_parts, prediction_parts, confusion_rows = [], [], [], []
with threadpool_limits(limits=1):
    for name, template in strategies.items():
        pred, fitted = fit_and_predict(template, X_train, y_train, X_test, name, "final", 0)
        test_rows.append(dict(strategy=name, accuracy=accuracy_score(y_test, pred),
            macro_f1=f1_score(y_test, pred, labels=LABELS, average="macro", zero_division=0)))
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, pred, labels=LABELS, average=None, zero_division=0)
        class_parts.append(pd.DataFrame(dict(strategy=name, class_label=LABELS,
            support=support, precision=precision, recall=recall, f1=f1)))
        prediction_parts.append(pd.DataFrame(dict(strategy=name, sample_id=test_idx, y_true=y_test, y_pred=pred)))
        cm = confusion_matrix(y_test, pred, labels=LABELS)
        confusion_rows.extend(dict(strategy=name, true_label=int(i), predicted_label=int(j), count=int(cm[i,j]))
                              for i in LABELS for j in LABELS)
test_summary, per_class = pd.DataFrame(test_rows), pd.concat(class_parts, ignore_index=True)
test_predictions = pd.concat(prediction_parts, ignore_index=True)
print("测试集总体指标：仅作预定最终展示，不据此反复调整权重或超参数。")
display(test_summary.round(6))
print("测试集逐类Recall与F1：")
display(per_class.pivot(index="class_label", columns="strategy", values=["recall", "f1"]).round(6))

# %%
# 问题7—核心代码（4/4）：少数类与多数类变化｜分组由训练计数预先确定
none_table = per_class.query("strategy == 'none'").set_index("class_label")
balanced_table = per_class.query("strategy == 'balanced'").set_index("class_label")
class_changes = (balanced_table[["precision", "recall", "f1"]] - none_table[["precision", "recall", "f1"]]).reset_index()
class_changes.columns = ["class_label", "precision_change", "recall_change", "f1_change"]
class_changes["train_minority_group"] = class_changes.class_label.isin(minority_labels)
print("逐类差值=balanced−none：")
display(class_changes.round(6))
group_rows = []
for name in strategies:
    pred = test_predictions.query("strategy == @name").y_pred.to_numpy()
    scores = per_class.query("strategy == @name").set_index("class_label")
    for group, labels in (("minority_5", minority_labels), ("majority_class", [majority_class])):
        mask = np.isin(y_test, labels)
        group_rows.append(dict(strategy=name, group=group, test_support=int(mask.sum()),
            mean_class_recall=scores.loc[labels, "recall"].mean(),
            mean_class_f1=scores.loc[labels, "f1"].mean(),
            group_accuracy=accuracy_score(y_test[mask], pred[mask])))
group_summary = pd.DataFrame(group_rows)
display(group_summary.round(6))
print("mean_class指标对组内类别等权；group_accuracy按组内样本计数，各自权重不同。")
print("组内F1来自全测试集one-vs-rest逐类F1再平均，不能先过滤样本后重算以遗漏外部误报。")

# %%
# 辅助代码：保存证据｜不新增训练；输出可供助手核验和绘图的真实文件
for filename, table in (("q7_cv_scores.csv", cv_scores), ("q7_cv_summary.csv", cv_summary),
    ("q7_cv_deltas.csv", cv_delta.reset_index()),
    ("q7_cv_predictions.csv", pd.concat(cv_prediction_parts, ignore_index=True)),
    ("q7_test_summary.csv", test_summary), ("q7_per_class.csv", per_class),
    ("q7_predictions.csv", test_predictions), ("q7_class_changes.csv", class_changes),
    ("q7_group_summary.csv", group_summary), ("q7_weights.csv", weight_table),
    ("q7_confusion_counts.csv", pd.DataFrame(confusion_rows))):
    table.to_csv(Q7_DIR / filename, index=False, encoding="utf-8-sig")
record = dict(code_version="1.0", source_dir=str(SOURCE_DIR), q4_source=str(Q4_SOURCE),
    data_split_sha256=data_hash, python=sys.version, sklearn=sklearn.__version__, executable=sys.executable,
    models={name: pipe.named_steps["model"].get_params(deep=False) for name, pipe in strategies.items()},
    preprocessing="StandardScaler in Pipeline; fit per CV training fold or full training set",
    labels=LABELS.tolist(), zero_division=0, minority_labels=minority_labels, majority_class=majority_class,
    folds=5, resampling=False, cv_seed=source["cv_seed"], model_seed=MODEL_SEED, thread_limit=1,
    warning_count=len(warning_rows), selection="fixed two-strategy comparison; no test-set tuning",
    confusion_matrix="raw counts; rows=true labels, columns=predicted labels",
    created_at=datetime.now().astimezone().isoformat(), output_dir=str(Q7_DIR))
for filename, content in (("q7_manifest.json", record), ("q7_warnings.json", warning_rows), ("q7_fit_diagnostics.json", fit_records)):
    (Q7_DIR / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
print("保存完成：", Q7_DIR)
print("警告总数：", len(warning_rows), "；求解失败记录数：", sum(row["fit_status"] != 0 for row in fit_records))
print("请发送四段核心代码和拟合函数的截图，以及代表性验证/测试输出；长表可由CSV整理，不必逐张截完。")

# %% [markdown]
# ## 图表、分析与截图
# 收到结果后助手使用技能生成总体指标和逐类变化图，结合五折得分判断是否存在一致趋势。
# 不预设balanced一定改善少数类或macro-F1。类别权重可能提高部分少数类召回、也增加误报或多数类损失。
# 代价权重不是重采样；数据分布不变。极少数类含噪声时，提高权重也可能放大噪声影响。
# 关键代码与代表性输出截图必须保留；完整长表从真实CSV整理为可编辑表格，不冒充运行截图。
# 本题无测试驱动的调参循环。出现异常先发送完整信息，不用反复尝试权重强度追求更好测试分数。
# 运行后助手核验、出图、合并分析并准备问题8；无需再次单独授权推进。
#
# ## AI使用记录
# OpenAI Codex，模型家族GPT-6，精确版本未知。原问题7及协议见request_original.txt。
# 根据用户“每题截图无问题就继续下一题”授权，从第五题结果核验和第六题理论分析推进到本题。
# AI辅助：预定权重对照方案、Pipeline折内拟合、五折验证、总体及逐类指标、分组比较与保存。
# 代码仅静态检查，未由助手代跑本题实验；学生修改、实际运行、验证与理解待据实补充。
