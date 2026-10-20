# %% [markdown]
# # 问题2：常数预测基线｜v1.0
# 本题以理论分析为主。以下代码用于核对公式、提供真实运行输出和导出图表数据，不训练模型。
# 独立运行：选择 Python for Data Analysis (pda312) 内核，自上而下执行，无需重新运行第一题。
# 固定读取第一题已核验的数据，不重新生成或划分数据；只需要运行Python，绘图由助手完成。
# 截图建议：分别截取常数预测与逐类结果、平均指标、理论校验成功输出，代码与输出都要保留。

# %%
# 公共初始化代码｜输出：环境、数据来源、固定划分与输出目录
from pathlib import Path
from datetime import datetime
import hashlib
import json
import sys
import uuid
import numpy as np
import pandas as pd
import sklearn
from IPython.display import display
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

PROJECT_DIR = Path(r"D:\Python for Data Analysis\notebooks\imbalanced_classification")
SOURCE_DIR = PROJECT_DIR / "runs/20261020_221259_7f297c"
assert Path(sys.executable).resolve() == Path(r"D:\anaconda\envs\pda312\python.exe").resolve(), "请选择pda312内核"
source_manifest = json.loads((SOURCE_DIR / "results/manifest.json").read_text(encoding="utf-8"))
with np.load(SOURCE_DIR / "data/dataset_and_split.npz") as saved:
    X, y = saved["X"], saved["y"]
    train_idx, test_idx = saved["train_idx"], saved["test_idx"]
data_hash = hashlib.sha256(X.tobytes() + y.tobytes() + train_idx.tobytes() + test_idx.tobytes()).hexdigest()
assert data_hash == source_manifest["data_split_sha256"], "数据或划分与第一题记录不一致"
LABELS = np.arange(10)
y_train, y_test = y[train_idx], y[test_idx]
assert np.array_equal(np.unique(y_train), LABELS) and np.array_equal(np.unique(y_test), LABELS)
Q2_DIR = PROJECT_DIR / "q2_runs" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
Q2_DIR.mkdir(parents=True, exist_ok=False)
print("问题2 v1.0；Python", sys.version.split()[0], "；scikit-learn", sklearn.__version__)
print("第一题数据来源：", SOURCE_DIR)
print("训练/测试样本数：", len(y_train), len(y_test))
print("本题输出目录：", Q2_DIR)

# %%
# 问题2—核心代码（1/2）｜依赖：初始化；输出：常数预测类别及逐类指标
train_counts = np.bincount(y_train, minlength=10)
# 仅根据训练集选择常数类别；flatnonzero升序返回标签，明确处理并列。
constant_class = int(np.flatnonzero(train_counts == train_counts.max())[0])
y_pred = np.full_like(y_test, constant_class)
precision, recall, f1, support = precision_recall_fscore_support(
    y_test, y_pred, labels=LABELS, average=None, zero_division=0
)
per_class = pd.DataFrame({
    "class_label": LABELS, "support": support,
    "precision": precision, "recall": recall, "f1": f1,
})
accuracy = accuracy_score(y_test, y_pred)
print("训练集确定的常数预测类别：", constant_class)
print("测试集全部预测为该类，测试集真实计数如下：")
display(per_class.round(6))
print(f"Accuracy = {accuracy:.6f}（{accuracy:.4%}）")

# %%
# 问题2—核心代码（2/2）｜依赖：常数预测；输出：macro/micro/weighted
average_rows = []
for average in ("macro", "micro", "weighted"):
    p_score, r_score, f_score, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=LABELS, average=average, zero_division=0
    )
    average_rows.append({"average": average, "precision": p_score,
                         "recall": r_score, "f1": f_score})
averages = pd.DataFrame(average_rows)
display(averages.round(6))
print("口径：全部10类、zero_division=0；Accuracy单独报告，不当成Precision。")

# %% [markdown]
# ## 理论推导
# 设常数类别为 $c$，测试集总数为 $N$，该类真实样本数为 $n_c$，$p=n_c/N$，类别数 $K=10$。
# 对类别 $c$：$TP_c=n_c, FP_c=N-n_c, FN_c=0$，因此 $P_c=p, R_c=1, F1_c=2p/(1+p)$。
# 对其他类 $j$：$TP_j=FP_j=0, FN_j=n_j$。Precision的零分母按0处理，因此三个指标均为0。
# 本次所有类别在测试集中均有样本；上述 $R_c=1$ 的推导使用了 $n_c>0$。
# Accuracy=$p$；macro的Precision、Recall、F1分别为 $p/K,1/K,2p/[K(1+p)]$。
# micro汇总计数：$TP=n_c, FP=FN=N-n_c$，故Precision、Recall、F1均为 $p$。
# weighted按真实类别占比加权，三个指标分别为 $p^2,p,2p^2/(1+p)$。
# 平均F1是先逐类计算F1再平均；一般不能把平均Precision与平均Recall的调和平均当成平均F1。

# %%
# 辅助代码：理论值与sklearn输出交叉核对｜输出：代入数值及核验状态
N, K = len(y_test), len(LABELS)
n_c = int(np.count_nonzero(y_test == constant_class))
p = n_c / N
theory_averages = pd.DataFrame([
    {"average": "macro", "precision": p/K, "recall": 1/K, "f1": 2*p/(K*(1+p))},
    {"average": "micro", "precision": p, "recall": p, "f1": p},
    {"average": "weighted", "precision": p**2, "recall": p, "f1": 2*p**2/(1+p)},
])
theory_per_class = np.zeros((K, 3))
theory_per_class[constant_class] = [p, 1.0, 2*p/(1+p)]
np.testing.assert_allclose(per_class[["precision", "recall", "f1"]], theory_per_class, atol=1e-12)
np.testing.assert_allclose(averages[["precision", "recall", "f1"]],
                           theory_averages[["precision", "recall", "f1"]], atol=1e-12)
assert np.isclose(accuracy, p)
print(f"代入：K={K}, c={constant_class}, N={N}, n_c={n_c}, p={p:.9f}")
print("公式与sklearn逐类指标、三种平均指标及Accuracy一致。")

# %%
# 辅助代码：保存真实运行结果｜输出：CSV和来源记录；将此目录发给助手绘图
per_class.to_csv(Q2_DIR / "q2_per_class.csv", index=False, encoding="utf-8-sig")
averages.to_csv(Q2_DIR / "q2_averages.csv", index=False, encoding="utf-8-sig")
pd.DataFrame({"sample_id": test_idx, "y_true": y_test, "y_pred": y_pred}).to_csv(
    Q2_DIR / "q2_predictions.csv", index=False, encoding="utf-8-sig"
)
record = dict(code_version="1.0", source_dir=str(SOURCE_DIR), data_split_sha256=data_hash,
              python=sys.version, sklearn=sklearn.__version__, executable=sys.executable,
              created_at=datetime.now().astimezone().isoformat(), constant_class=constant_class,
              N=N, n_c=n_c, accuracy=float(accuracy), labels=LABELS.tolist(), zero_division=0,
              formula_check="passed", output_dir=str(Q2_DIR))
(Q2_DIR / "q2_manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print("保存完成：", Q2_DIR)
print("请保留两段核心代码与输出截图，以及公式核验和保存完成输出。")

# %% [markdown]
# ## 分析与图表
# 完整公式和基于第一题实际测试计数的分析见 `问题2_推导与分析.md`。
# 本题尚无学生运行截图时，公式代入值应标注为理论计算，不标为学生已运行的sklearn结果。
# 你无需运行R；助手用技能生成图片。你发送的代码与结果截图也会纳入最终报告。
#
# ## AI使用记录
# 工具：OpenAI Codex，模型家族GPT-6，精确版本未知；绘图使用r-academic-plots技能。
# 提示词：原作业请求中的问题2及统一协议（request_original.txt），本次请求原文“继续第二题”；
# 前序要求：只需Python代码，助手生成图片并直接提供分析与结论，分析与进一步分析合并。
# AI辅助：公式推导、Python数值核验代码、图表和基于第一题真实计数的分析。
# 学生运行情况、修改、对推导的核验及理解：待据实际情况填写，不将理论计算冒充运行输出。
