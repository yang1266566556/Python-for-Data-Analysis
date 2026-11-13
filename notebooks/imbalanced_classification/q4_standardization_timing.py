# %% [markdown]
# # 问题4：标准化、预测质量与效率｜v1.0
# 使用pda312内核，独立自上而下运行。固定第一题数据，复用第三题实际默认配置。
# 每种设置先预热一次，再独立训练/预测5次；四模型×两种设置共48次拟合（含8次预热）。
# 仅比较无预处理与StandardScaler，不调参。请关闭其他高负载任务，运行期间尽量不操作电脑。
# StandardScaler按训练集各特征均值与标准差做z=(x-mean)/std，不保证范围为[0,1]；
# MinMaxScaler缩放到指定区间，Normalizer按每行样本范数缩放，含义不同。
# 预处理放入Pipeline，仅在训练集fit；测试集只transform。本题没有交叉验证。
# 未来如做交叉验证必须把整个Pipeline放入各训练折，不能预先标准化整个数据集。

# %%
# 公共初始化代码｜输出：数据来源、版本和独立输出目录
from pathlib import Path
from datetime import datetime
from time import perf_counter
import hashlib
import json
import platform
import sys
import uuid
import warnings
import numpy as np
import pandas as pd
import sklearn
from IPython.display import display
from threadpoolctl import threadpool_limits, threadpool_info
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from sklearn.exceptions import ConvergenceWarning

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
    PROJECT_DIR, check_environment, SOURCE_DIR, load_fixed_dataset, dataset_sha256, Q3_SOURCE
)
check_environment()
source = json.loads((SOURCE_DIR / "results/manifest.json").read_text(encoding="utf-8"))
assert sklearn.__version__ == source["versions"]["scikit-learn"], "环境版本已变化，请先核对"
saved = load_fixed_dataset(SOURCE_DIR)
X, y = saved["X"], saved["y"]
train_idx, test_idx = saved["train_idx"], saved["test_idx"]
data_hash = dataset_sha256(X, y, train_idx, test_idx)
assert data_hash == source["data_split_sha256"]
X_train, X_test = X[train_idx], X[test_idx]
y_train, y_test = y[train_idx], y[test_idx]
LABELS, MODEL_SEED = np.arange(10), source["model_seed"]
REPEATS, ORDER_SEED, THREAD_LIMIT = 5, 20261023, 1
Q4_DIR = PROJECT_DIR / "q4_runs" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
Q4_DIR.mkdir(parents=True, exist_ok=False)
print("问题4 v1.0；Python", sys.version.split()[0], "；sklearn", sklearn.__version__)
print("训练/测试：", X_train.shape, X_test.shape, "；每设置计时重复：", REPEATS)
print("本题目录：", Q4_DIR)

# %%
# 问题4—核心代码（1/3）｜依赖：初始化；输出：Pipeline和固定计时协议
models = {
    "LogisticRegression": LogisticRegression(random_state=MODEL_SEED),
    "DecisionTree": DecisionTreeClassifier(random_state=MODEL_SEED),
    "KNN": KNeighborsClassifier(),
    "SVC": SVC(random_state=MODEL_SEED),
}
model_parameters = {name: model.get_params(deep=False) for name, model in models.items()}
assert model_parameters == json.loads((Q3_SOURCE / "q3_model_parameters.json").read_text(encoding="utf-8"))
pipelines = {}
for name, model in models.items():
    for setting in ("raw", "standardized"):
        scaler = "passthrough" if setting == "raw" else StandardScaler()
        pipelines[(name, setting)] = Pipeline([("scale", scaler), ("model", clone(model))])
print("模型超参数与第三题一致。raw=原始特征；standardized=StandardScaler。")
print("训练计时包括标准化fit_transform和模型fit；预测计时包括测试集transform和predict。")
print("计时不包括克隆模型、指标计算、打印和文件保存；预测耗时对应整个1200例测试集。")
print("每设置预热1次不计入统计；重复5次均重新拟合。每轮随机顺序，固定顺序种子。")
print("计时期间BLAS/OpenMP线程上限为1，退出代码块后恢复；不修改模型超参数。")

# %%
# 辅助代码：一次测量封装｜供下一核心单元调用；定义本身不运行实验
measurements, warning_rows, prediction_parts, class_parts, diagnostic_rows = [], [], [], [], []
def measure_once(name, setting, repeat, phase, order):
    pipe = clone(pipelines[(name, setting)])  # 计时外新建模型，不复用上次已拟合对象。
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        start = perf_counter()
        pipe.fit(X_train, y_train)
        fit_seconds = perf_counter() - start
        start = perf_counter()
        pred = pipe.predict(X_test)
        predict_seconds = perf_counter() - start
    for item in caught:
        warning_rows.append(dict(model=name, setting=setting, repeat=repeat, phase=phase,
                                 category=item.category.__name__, message=str(item.message),
                                 is_convergence_warning=issubclass(item.category, ConvergenceWarning)))
    if phase == "warmup":
        return
    estimator = pipe.named_steps["model"]
    diagnostic_rows.append(dict(model=name, setting=setting, repeat=repeat,
        n_iter=np.asarray(estimator.n_iter_).tolist() if hasattr(estimator, "n_iter_") else None,
        fit_status=int(estimator.fit_status_) if hasattr(estimator, "fit_status_") else None))
    measurements.append(dict(model=name, setting=setting, repeat=repeat, order=order,
        fit_seconds=fit_seconds, predict_seconds=predict_seconds,
        accuracy=accuracy_score(y_test, pred),
        macro_f1=f1_score(y_test, pred, labels=LABELS, average="macro", zero_division=0)))
    prediction_parts.append(pd.DataFrame(dict(model=name, setting=setting, repeat=repeat,
        sample_id=test_idx, y_true=y_test, y_pred=pred)))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, pred, labels=LABELS, average=None, zero_division=0)
    class_parts.append(pd.DataFrame(dict(model=name, setting=setting, repeat=repeat,
        class_label=LABELS, support=support, precision=precision, recall=recall, f1=f1)))

# %%
# 问题4—核心代码（2/3）｜依赖：测量函数；输出：进度和逐次真实计时记录
# 重新运行本单元会重做计时实验；先清空本单元产生的内存列表，避免重复累加。
measurements.clear(); warning_rows.clear(); prediction_parts.clear(); class_parts.clear(); diagnostic_rows.clear()
keys, rng = list(pipelines), np.random.default_rng(ORDER_SEED)
with threadpool_limits(limits=THREAD_LIMIT):
    controlled_threadpools = threadpool_info()
    for order, index in enumerate(rng.permutation(len(keys)), start=1):
        measure_once(*keys[index], repeat=0, phase="warmup", order=order)
    print("8种设置预热完成，下面开始正式计时。", flush=True)
    for repeat in range(1, REPEATS + 1):
        for order, index in enumerate(rng.permutation(len(keys)), start=1):
            measure_once(*keys[index], repeat=repeat, phase="measured", order=order)
        print(f"第{repeat}/{REPEATS}轮完成。", flush=True)
records = pd.DataFrame(measurements)
assert len(records) == len(keys) * REPEATS
display(records.round(6))
print("警告总数（含预热）：", len(warning_rows))
for name, setting, category, message in sorted({(w["model"], w["setting"], w["category"], w["message"]) for w in warning_rows}):
    print(f"{name}/{setting} [{category}]：{message}")

# %%
# 问题4—核心代码（3/3）｜输出：质量、耗时和标准化前后差值；耗时单位秒
metrics = ["accuracy", "macro_f1", "fit_seconds", "predict_seconds"]
grouped = records.groupby(["model", "setting"])[metrics].agg(["mean", "std"])
grouped.columns = [f"{metric}_{stat}" for metric, stat in grouped.columns]
summary = grouped.reset_index()
print("测试集质量：均值与样本标准差（ddof=1）")
display(summary[["model", "setting", "accuracy_mean", "accuracy_std", "macro_f1_mean", "macro_f1_std"]].round(6))
print("训练与整批测试集预测耗时：秒，均值与样本标准差")
display(summary[["model", "setting", "fit_seconds_mean", "fit_seconds_std", "predict_seconds_mean", "predict_seconds_std"]].round(6))
raw = summary.query("setting == 'raw'").set_index("model")
scaled = summary.query("setting == 'standardized'").set_index("model")
changes = pd.DataFrame({
    "accuracy_change_pp": 100*(scaled.accuracy_mean-raw.accuracy_mean),
    "macro_f1_change": scaled.macro_f1_mean-raw.macro_f1_mean,
    "fit_speedup_raw_over_scaled": raw.fit_seconds_mean/scaled.fit_seconds_mean,
    "predict_speedup_raw_over_scaled": raw.predict_seconds_mean/scaled.predict_seconds_mean,
}).reset_index()
print("差值=标准化后−原始；耗时加速比>1表示标准化设置耗时更短。")
display(changes.round(6))
print("重复计时的标准差不是跨数据划分的泛化不确定性；质量标准差为0不代表模型无不确定性。")

# %%
# 辅助代码：保存结果与机制诊断｜依赖：全部核心单元；无需再次训练
all_predictions = pd.concat(prediction_parts, ignore_index=True)
all_per_class = pd.concat(class_parts, ignore_index=True)
same_predictions = all_predictions.groupby(["model", "setting", "sample_id"]).y_pred.nunique().max() == 1
feature_scale = pd.DataFrame({"feature": np.arange(X_train.shape[1]),
                              "train_mean": X_train.mean(axis=0), "train_std_ddof0": X_train.std(axis=0)})
print("重复运行各设置的预测是否完全一致：", bool(same_predictions))
print("原始训练特征标准差范围：", feature_scale.train_std_ddof0.min(), feature_scale.train_std_ddof0.max())
for filename, table in (("q4_records.csv", records), ("q4_summary.csv", summary),
    ("q4_changes.csv", changes), ("q4_predictions.csv", all_predictions),
    ("q4_per_class.csv", all_per_class), ("q4_feature_scale.csv", feature_scale)):
    table.to_csv(Q4_DIR / filename, index=False, encoding="utf-8-sig")
record = dict(code_version="1.0", source_dir=str(SOURCE_DIR), q3_source=str(Q3_SOURCE),
    data_split_sha256=data_hash, python=sys.version, sklearn=sklearn.__version__, executable=sys.executable,
    platform=platform.platform(), processor=platform.processor(), repeats=REPEATS,
    warmup_per_setting=1, order_seed=ORDER_SEED, thread_limit=THREAD_LIMIT,
    controlled_threadpools=controlled_threadpools, model_parameters=model_parameters,
    preprocessing_parameters=StandardScaler().get_params(), labels=LABELS.tolist(), zero_division=0,
    timing_unit="seconds", std_definition="sample standard deviation ddof=1",
    fit_timing="Pipeline.fit including scaler fit_transform", predict_timing="Pipeline.predict including scaler transform; full 1200-sample batch",
    predictions_identical_across_repeats=bool(same_predictions), output_dir=str(Q4_DIR),
    created_at=datetime.now().astimezone().isoformat())
for filename, content in (("q4_manifest.json", record), ("q4_warnings.json", warning_rows),
                          ("q4_fit_diagnostics.json", diagnostic_rows)):
    (Q4_DIR / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
print("保存完成：", Q4_DIR)
print("请发核心代码、质量表、耗时表和差值表截图；有警告请保留全文。")

# %% [markdown]
# ## 分析与截图说明
# 本题尚未运行，不预设标准化会提升分数或速度。助手收到真实结果后生成质量图和耗时图，分开量纲。
# 误差条为5次计时的样本标准差，并非置信区间。无需你运行R。
# 决策树一般不敏感于正的逐特征线性缩放，但有限精度和阈值计算仍可能造成预测差异。
# KNN距离、RBF核SVC以及逻辑回归的优化与正则化可能受尺度影响；本次收益需实际数据支持。
# SVC默认gamma='scale'的数值依赖输入方差，因此标准化会同时改变距离与自动计算的gamma。
# 测试分数只用于本题对照展示，不据此调整参数。计时在同一次运行内比较，不能与第三题未控制线程的运行时间混比。
# 本协议控制的是threadpoolctl可控制的数值库线程；操作系统调度及其他软件负载仍可能影响计时。
# 截图包含三段核心代码；测量函数定义也须截图，因为包含关键fit/predict计时逻辑，不能仅截图调用循环。
# 核心第3段输出可拆为质量、耗时、差值三张，保留表头与单位。原始40行计时记录完整保存在CSV，无需塞入单张截图。
# 分析、进一步分析和结论由助手结合结果合并撰写；你的原始代码及结果截图均会插入文档。
#
# ## AI使用记录
# 工具：OpenAI Codex；模型家族GPT-6，精确版本未知。原题目及协议见request_original.txt。
# 本轮用户原文：“第三题的核心代码和截图”；按前序“每个题的截图之后没什么问题你就自己继续下一题”的授权推进。
# AI辅助：第三题结果核验与技能绘图，以及本题Pipeline、预热、重复计时、指标计算和结果导出代码。
# 第四题代码仅静态检查，模型未由助手训练。学生运行、修改、核验和理解待实际填写。
