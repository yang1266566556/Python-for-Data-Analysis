# %% [markdown]
# # 问题3：四种默认分类器｜v1.0
# 独立Notebook：选择 Python for Data Analysis (pda312)，按顺序运行全部代码单元。
# 固定使用第一题数据与划分；不重新生成数据，不标准化，不调整默认超参数。
# 仅给支持random_state的模型设置第一题预留的MODEL_SEED。
# 本题只需Python。运行后发送核心代码及对应输出截图；助手检查真实结果后生成图表和分析。
# 无问题时助手自动继续准备下一题，不代替学生运行下一题，也不提前生成整份报告。

# %%
# 公共初始化代码｜依赖：第一题已保存的数据；输出：环境与本题输出目录
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
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support, confusion_matrix

PROJECT_DIR = Path(r"D:\Python for Data Analysis\notebooks\imbalanced_classification")
SOURCE_DIR = PROJECT_DIR / "runs/20261020_221259_7f297c"
assert Path(sys.executable).resolve() == Path(r"D:\anaconda\envs\pda312\python.exe").resolve(), "请选择pda312内核"
source_manifest = json.loads((SOURCE_DIR / "results/manifest.json").read_text(encoding="utf-8"))
assert sklearn.__version__ == source_manifest["versions"]["scikit-learn"], "sklearn版本与第一题不同，请先核对环境"
with np.load(SOURCE_DIR / "data/dataset_and_split.npz") as saved:
    X, y = saved["X"], saved["y"]
    train_idx, test_idx = saved["train_idx"], saved["test_idx"]
data_hash = hashlib.sha256(X.tobytes() + y.tobytes() + train_idx.tobytes() + test_idx.tobytes()).hexdigest()
assert data_hash == source_manifest["data_split_sha256"], "第一题数据或划分发生变化"
X_train, X_test, y_train, y_test = X[train_idx], X[test_idx], y[train_idx], y[test_idx]
LABELS, MODEL_SEED = np.arange(10), source_manifest["model_seed"]
assert np.array_equal(np.unique(y_train), LABELS) and np.array_equal(np.unique(y_test), LABELS)
Q3_DIR = PROJECT_DIR / "q3_runs" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
Q3_DIR.mkdir(parents=True, exist_ok=False)
print("问题3 v1.0；Python", sys.version.split()[0], "；scikit-learn", sklearn.__version__)
print("数据：", X_train.shape, X_test.shape, "；模型种子：", MODEL_SEED)
print("本题输出目录：", Q3_DIR)

# %%
# 问题3—核心代码（1/3）｜输出：四个模型的实际完整配置
# 不手工填入网上示例中的参数，以当前内核安装版本的默认值为准。
models = {
    "LogisticRegression": LogisticRegression(random_state=MODEL_SEED),
    "DecisionTree": DecisionTreeClassifier(random_state=MODEL_SEED),
    "KNN": KNeighborsClassifier(),
    "SVC": SVC(random_state=MODEL_SEED),
}
model_parameters = {name: model.get_params(deep=False) for name, model in models.items()}
for name, parameters in model_parameters.items():
    print(name)
    print(json.dumps(parameters, ensure_ascii=False, sort_keys=True))
print("以上除random_state外均为默认参数；本题不做标准化。")

# %% [markdown]
# 本机scikit-learn 1.9.0部分默认值会显示为字符串 `deprecated`，这是库的默认参数表示。
# 不应为了让配置看起来熟悉而手动改成旧版值。本题保留实际默认行为，并记录运行警告。
# 下一单元需要训练四个模型，请等待其完成。即使出现收敛警告，也先保留本次默认基线并发送警告全文；
# 不要直接改大max_iter后覆盖它。必要时后续单独设置补充实验。

# %%
# 问题3—核心代码（2/3）｜依赖：模型配置；输出：训练状态、预测和警告
predictions, warning_rows, fit_diagnostics = {}, [], {}
for name, model in models.items():
    print(f"开始训练：{name}", flush=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")  # 记录并在下方完整输出，不忽略收敛问题。
        model.fit(X_train, y_train)
        predictions[name] = model.predict(X_test)
    for item in caught:
        warning_rows.append({"model": name, "category": item.category.__name__,
                             "message": str(item.message),
                             "is_convergence_warning": issubclass(item.category, ConvergenceWarning)})
        print(f"警告 [{item.category.__name__}]：{item.message}")
    fit_diagnostics[name] = {
        "n_iter": np.asarray(model.n_iter_).tolist() if hasattr(model, "n_iter_") else None,
        "fit_status": int(model.fit_status_) if hasattr(model, "fit_status_") else None,
    }
    print(f"{name}：预测{len(predictions[name])}例；捕获警告{len(caught)}条")
    print("迭代/求解状态：", fit_diagnostics[name])

# %%
# 问题3—核心代码（3/3）｜依赖：预测；输出：测试集Accuracy、macro-F1及逐类指标
summary_rows, class_parts = [], []
for name, y_pred in predictions.items():
    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, labels=LABELS, average="macro", zero_division=0)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, labels=LABELS, average=None, zero_division=0
    )
    summary_rows.append({"model": name, "accuracy": acc, "macro_f1": macro_f1})
    class_parts.append(pd.DataFrame({
        "model": name, "class_label": LABELS, "support": support,
        "precision": precision, "recall": recall, "f1": f1,
    }))
summary = pd.DataFrame(summary_rows)
summary["accuracy_rank"] = summary["accuracy"].rank(ascending=False, method="min").astype(int)
summary["macro_f1_rank"] = summary["macro_f1"].rank(ascending=False, method="min").astype(int)
per_class = pd.concat(class_parts, ignore_index=True)
print("测试集总体指标（排名仅描述本次结果，不用测试集调参）：")
display(summary.round(6))
print("测试集逐类F1（标签0—9全部保留）：")
display(per_class.pivot(index="class_label", columns="model", values="f1").round(6))
print("测试集逐类Recall：")
display(per_class.pivot(index="class_label", columns="model", values="recall").round(6))

# %% [markdown]
# ## 辅助代码：保存证据
# 前置：三段核心代码均成功运行。本单元不重新训练模型。
# 输出总体指标、逐类指标、每个样本预测、未归一化混淆矩阵、模型配置、完整警告和来源记录。
# 保存后发送核心代码与对应结果截图。总体指标、逐类表若太长可分图截，警告全文不要省略。
# 助手会检查本题输出目录；如果能直接读到文件，不需要重复上传同一份CSV。

# %%
# 辅助代码｜输出：本题结果文件、警告计数和保存路径
summary.to_csv(Q3_DIR / "q3_summary.csv", index=False, encoding="utf-8-sig")
per_class.to_csv(Q3_DIR / "q3_per_class.csv", index=False, encoding="utf-8-sig")
prediction_table = pd.DataFrame({"sample_id": test_idx, "y_true": y_test, **predictions})
prediction_table.to_csv(Q3_DIR / "q3_predictions.csv", index=False, encoding="utf-8-sig")
confusion_rows = []
for name, y_pred in predictions.items():
    cm = confusion_matrix(y_test, y_pred, labels=LABELS)
    assert cm.sum() == len(y_test)
    confusion_rows.extend({"model": name, "true_label": int(i), "predicted_label": int(j),
                           "count": int(cm[i, j])} for i in LABELS for j in LABELS)
pd.DataFrame(confusion_rows).to_csv(Q3_DIR / "q3_confusion_counts.csv", index=False, encoding="utf-8-sig")
for filename, content in (("q3_model_parameters.json", model_parameters),
                          ("q3_warnings.json", warning_rows), ("q3_fit_diagnostics.json", fit_diagnostics)):
    (Q3_DIR / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
record = dict(code_version="1.0", source_dir=str(SOURCE_DIR), data_split_sha256=data_hash,
              python=sys.version, sklearn=sklearn.__version__, executable=sys.executable,
              model_seed=MODEL_SEED, models=list(models), preprocessing="none",
              labels=LABELS.tolist(), zero_division=0, train_samples=len(y_train), test_samples=len(y_test),
              warning_count=len(warning_rows), created_at=datetime.now().astimezone().isoformat(),
              confusion_matrix="raw counts; rows=true labels, columns=predicted labels",
              output_dir=str(Q3_DIR))
(Q3_DIR / "q3_manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print("保存完成：", Q3_DIR)
print("总警告数：", len(warning_rows), "；收敛警告数：", sum(x["is_convergence_warning"] for x in warning_rows))
print("请发送核心代码和运行输出截图；有警告也保留，先不要修改默认参数。")

# %% [markdown]
# ## 后续图表与分析安排
# 尚未收到本题实际结果，不预填模型排名、分数或实验结论。
# 收到后由助手通过r-academic-plots技能绘制Accuracy/macro-F1对比图，并结合逐类F1或Recall解释差异。
# 分析、进一步分析和结论合并成连贯文字，区分实际现象与机制解释。
# 本题是单次固定划分的默认基线，不将单次差异当成统计显著差异，也不据测试集调整参数。
# 收敛警告可能影响结果解释；捕获警告本身不等于模型已收敛，默认基线应完整保留。
# 若截图与文件核验无问题，助手自动继续准备问题4；若存在影响有效性的错误，先排查再推进。
#
# ## AI使用记录
# 工具：OpenAI Codex；模型家族GPT-6，精确版本未知。
# 原作业要求见request_original.txt；本轮请求原文：“继续第三题我发给你每个题的截图之后没什么问题你就自己继续下一题的”。
# AI辅助内容：默认分类器代码、参数与警告记录、测试集指标计算、逐类结果与预测导出。
# 当前仅核对了本机模型API、Notebook结构和Python语法，未代替学生训练模型，尚无本题性能结论。
# 学生运行、修改、核验及理解：待根据实际情况填写。后续使用绘图技能后补记相应用途。
