# %% [markdown]
# # 公共初始化与问题1｜v1.1
# **建议配置，尚待学生采用并核验。** 本文件与同目录 Notebook 的代码一致。
# 选择内核 **Python for Data Analysis (pda312)**，按单元自上而下运行。
# 每次运行初始化会新建一个输出目录，不覆盖以前的实验；修改参数后应从头运行。
# 本阶段只运行Python生成数据、核验分层划分并导出结果，不训练分类器。
# 你只需运行Python；生成图片由助手通过 r-academic-plots 技能完成，无需你运行R。

# %%
# 公共初始化代码｜依赖：无；输出：解释器、版本、运行目录
from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import sys
import uuid
import importlib.metadata as metadata
import numpy as np
import pandas as pd
from IPython.display import display
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split, StratifiedKFold

PROJECT_DIR = Path(r"D:\Python for Data Analysis\notebooks\imbalanced_classification")
EXPECTED_PYTHON = Path(r"D:\anaconda\envs\pda312\python.exe")
assert Path(sys.executable).resolve() == EXPECTED_PYTHON.resolve(), "请切换到 pda312 内核"
OUTPUT_BASE = Path(os.environ.get("ML_Q1_OUTPUT", str(PROJECT_DIR / "runs")))
RUN_DIR = OUTPUT_BASE / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
for folder in ("data", "results", "figures"):
    (RUN_DIR / folder).mkdir(parents=True, exist_ok=False)
VERSIONS = {p: metadata.version(p) for p in ("scikit-learn", "numpy", "pandas", "ipykernel")}
print("代码版本：v1.1；运行身份：", os.environ.get("ML_Q1_ACTOR", "学生运行，待学生核验"))
print("解释器：", sys.executable)
print("Python：", sys.version.split()[0], "；依赖：", VERSIONS)
print("本次输出目录：", RUN_DIR)

# %% [markdown]
# ## 问题1—核心代码（1/3）：确定实验设置
# 前置：公共初始化。截图建议：本单元完整代码与下一单元的核验输出。
# 建议理由：最小目标类约96个样本，分层后可支持五折验证；24个特征控制计算量。
# 权重是生成前的目标比例，加入噪声后实际计数通常不同。
# `flip_y=0.015` 表示随机重新分配标签的比例；新标签可能等于原标签，不能称为实际错误率。
# 14个信息特征满足 10×2≤2^14；14+6+0≤24，另有4个随机无用特征。
# 默认不人为放大特征尺度；后续标准化的收益需要实际实验判断。

# %%
# 问题1—核心代码（1/3）｜输出：完整建议参数；修改后从头运行
LABELS = np.arange(10)
DATA_SEED, SPLIT_SEED, CV_SEED, MODEL_SEED = 1637, 20261020, 20261021, 20261022
TEST_SIZE, N_SPLITS = 0.25, 5
DATA_CONFIG = dict(
    n_samples=4800, n_features=24, n_informative=14,
    n_redundant=6, n_repeated=0, n_classes=10, n_clusters_per_class=2,
    weights=[0.32, 0.19, 0.13, 0.095, 0.075, 0.06, 0.045, 0.035, 0.03, 0.02],
    flip_y=0.015, class_sep=1.2, hypercube=True,
    shift=0.0, scale=1.0, shuffle=True, random_state=DATA_SEED,
)
assert len(DATA_CONFIG["weights"]) == 10 and np.isclose(sum(DATA_CONFIG["weights"]), 1)
assert min(DATA_CONFIG["weights"]) > 0
assert sum(DATA_CONFIG[k] for k in ("n_informative", "n_redundant", "n_repeated")) <= DATA_CONFIG["n_features"]
assert DATA_CONFIG["n_classes"] * DATA_CONFIG["n_clusters_per_class"] <= 2 ** DATA_CONFIG["n_informative"]
print(json.dumps(DATA_CONFIG, ensure_ascii=False, indent=2))

# %%
# 问题1—核心代码（2/3）｜依赖：参数单元；输出：数据及训练/测试计数
X, y = make_classification(**DATA_CONFIG)
assert np.array_equal(np.unique(y), LABELS), "生成数据未包含全部10类"
assert np.isfinite(X).all(), "特征存在非有限值"
# 先划分行号，便于保存并确保后续各题使用同一批样本。
train_idx, test_idx = train_test_split(
    np.arange(len(y)), test_size=TEST_SIZE, stratify=y, random_state=SPLIT_SEED
)
X_train, X_test = X[train_idx], X[test_idx]
y_train, y_test = y[train_idx], y[test_idx]
train_counts = np.bincount(y_train, minlength=10)
test_counts = np.bincount(y_test, minlength=10)
assert (train_counts >= N_SPLITS).all() and (test_counts > 0).all()
assert len(np.intersect1d(train_idx, test_idx)) == 0
assert len(train_idx) + len(test_idx) == len(y)
print("完整数据形状：", X.shape, "；训练/测试样本数：", len(y_train), len(y_test))
print("训练集逐类计数：", train_counts)
print("测试集逐类计数：", test_counts)
print("10类齐全、样本划分无重叠、满足五折分层验证计数条件。")

# %%
# 问题1—核心代码（3/3）｜依赖：数据划分；输出：逐类分布与不平衡比
distribution_parts = []
for split_name, split_y in (("all", y), ("train", y_train), ("test", y_test)):
    counts = np.bincount(split_y, minlength=10)
    distribution_parts.append(pd.DataFrame({
        "split": split_name, "class_label": LABELS,
        "count": counts, "proportion": counts / len(split_y),
        "target_weight": DATA_CONFIG["weights"],
    }))
distribution = pd.concat(distribution_parts, ignore_index=True)
train_distribution = distribution.query("split == 'train'").copy()
train_distribution["percent"] = train_distribution["proportion"] * 100
majority_class = int(np.flatnonzero(train_counts == train_counts.max())[0])
imbalance_ratio = float(train_counts.max() / train_counts.min())
display(train_distribution[["class_label", "count", "percent", "target_weight"]].round(4))
print(f"训练集不平衡比（最大计数/最小计数）：{imbalance_ratio:.4f}")
print(f"训练集多数类：{majority_class}；并列时选标签最小者")
print(f"训练集多数类占比：{train_counts.max() / len(y_train):.4%}")
print("以上是实际生成结果；目标权重不能替代实际计数。")

# %% [markdown]
# ## 辅助代码：交叉验证可行性与结果留存
# 前置：全部核心单元。检查五折各类计数，不训练模型；保存数据、固定行号、参数及哈希。
# 截图建议：核心代码分成三张，统计表和核验输出单独截；本辅助单元只需保留核验输出。
# `MODEL_SEED` 留给后续支持 random_state 的模型；当前没有训练任何模型。

# %%
# 辅助代码｜输出：五折计数表、CSV、NPZ、JSON；后续题复用本次数据
cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=CV_SEED)
cv_rows, fold_indices = [], {}
for fold, (fit_idx, val_idx) in enumerate(cv.split(X_train, y_train), start=1):
    fold_indices[f"fold_{fold}_fit"] = fit_idx
    fold_indices[f"fold_{fold}_validation"] = val_idx
    for role, indices in (("fit", fit_idx), ("validation", val_idx)):
        counts = np.bincount(y_train[indices], minlength=10)
        assert (counts > 0).all(), "某个交叉验证折缺少类别"
        cv_rows.extend({"fold": fold, "role": role, "class_label": int(c), "count": int(n)}
                       for c, n in zip(LABELS, counts))
cv_counts = pd.DataFrame(cv_rows)
display(cv_counts.groupby(["fold", "role"])["count"].min().unstack().rename_axis(columns=None))
print("表内为各折最少类别计数；五折的拟合部分和验证部分均包含10类。")

distribution.to_csv(RUN_DIR / "results/class_distribution.csv", index=False, encoding="utf-8-sig")
cv_counts.to_csv(RUN_DIR / "results/cv_class_counts.csv", index=False, encoding="utf-8-sig")
np.savez_compressed(RUN_DIR / "data/dataset_and_split.npz", X=X, y=y,
                    train_idx=train_idx, test_idx=test_idx, **fold_indices)
features = pd.DataFrame(X, columns=[f"feature_{i:02d}" for i in range(X.shape[1])])
features.insert(0, "sample_id", np.arange(len(y)))
features["label"] = y
features["split"] = np.where(np.isin(np.arange(len(y)), train_idx), "train", "test")
features.to_csv(RUN_DIR / "data/dataset.csv", index=False, encoding="utf-8-sig")
data_hash = hashlib.sha256(X.tobytes() + y.tobytes() + train_idx.tobytes() + test_idx.tobytes()).hexdigest()
manifest = dict(
    code_version="1.1", configuration_status="建议配置；学生采用与理解待确认",
    run_actor=os.environ.get("ML_Q1_ACTOR", "学生运行，待学生核验"),
    created_at=datetime.now().astimezone().isoformat(), python=sys.version,
    executable=sys.executable, versions=VERSIONS, make_classification=DATA_CONFIG,
    test_size=TEST_SIZE, split_seed=SPLIT_SEED, cv_seed=CV_SEED, model_seed=MODEL_SEED,
    cv_folds=N_SPLITS, labels=LABELS.tolist(), zero_division=0,
    future_metrics=["accuracy", "macro_f1"], train_majority_class=majority_class,
    train_imbalance_ratio=imbalance_ratio, data_split_sha256=data_hash,
    cv_index_basis="positions within X_train, not original X", output_dir=str(RUN_DIR),
)
(RUN_DIR / "results/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("数据与划分SHA256：", data_hash)
print("结果已保存到：", RUN_DIR)


# %% [markdown]
# ## 图片生成与材料交接
# 运行到上面的辅助代码即完成本阶段Python操作，无需安装或运行R。
# 将本次输出目录发给助手，或提供 results/class_distribution.csv、results/cv_class_counts.csv 和 results/manifest.json。
# 助手核验真实结果后，通过 r-academic-plots 技能生成带标题、坐标轴、图例的清晰图片，并更新分析与结论。
# 保留核心代码与输出截图；图片文件由助手交付。助手已生成的验证图不是学生运行截图。

# %% [markdown]
# ## 问题1：分析与结论
# 以下数字来自助手对v1.0相同数据生成逻辑的实际运行核验，不代表学生已经运行或核验。v1.1仅移除了学生端R调用并更新说明，未改变数据参数。自行修改参数或获得不同结果后，应以新结果更新本节。
#
# **实验结果。** 数据集共4800个样本、24个特征，实际包含全部10个类别。分层划分后训练集3600例、测试集1200例。训练集中类别0最多，为1137例，占31.58%；类别9最少，为78例，占2.17%。训练集不平衡比为1137/78≈14.58，说明不同类别的样本数量存在明显差异。类别0和类别1合计占训练集的50.33%，超过一半样本集中在两个类别。
#
# **进一步分析：训练影响。** 对采用等权逐样本损失的模型，多数类由于样本更多，对总体损失的贡献机会也更多。因此，降低多数类错误可能比改善少数类识别更容易降低整体训练损失。少数类样本较少也可能限制模型对其内部变化的学习。不过，不同算法受到不平衡的影响方式不同；当前尚未训练模型，不能据类别分布断言某模型已经偏向多数类，或少数类必然难以识别。
#
# **进一步分析：评价影响。** Accuracy中每个样本权重相同，各类对总体结果的影响随真实样本数变化，少数类表现不佳可能被总体指标掩盖。macro-F1先计算各类F1再等权平均，10个类别各占十分之一权重，因而更能暴露少数类性能不足。后续应同时报告Accuracy与macro-F1，并核对逐类Recall和F1；当前不能预判哪个模型最好，也不能预判两种指标的具体大小关系。
#
# **进一步分析：噪声与稳定性。** 类别0实际训练占比31.58%，低于目标32%；类别9实际占比2.17%，高于目标2%。目标权重、整数分配、标签随机重分配和分层划分共同决定最终计数，因此应使用实际计数分析。flip_y=0.015表示标签被随机重新分配的比例，新标签可能仍与原标签相同，不能直接当成实际错标率。五折验证的拟合部分与验证部分均保留全部10类，但单个验证折中最少类只有15或16例，样本充足条件并不等于评价稳定。测试集中类别9只有26例，其正确识别数每变化1例，Recall约变化3.85个百分点，说明少数类指标对少量预测变化较敏感。
#
# **结论与局限。** 本次建议配置已生成可供后续分层划分和五折验证使用的10类不平衡数据。后续应固定数据与划分，同时考察整体表现和逐类表现，并报告验证得分波动。图1-1可支持样本分布及不平衡程度的判断，不能证明模型性能或展示24维空间的完整决策边界；合成数据上的结果也不能直接推广至真实业务。

# %% [markdown]
# ## 本题AI使用记录（学生核验情况待补）
# 工具：OpenAI Codex；模型家族：GPT-6，精确产品版本未知；绘图技能：r-academic-plots。
# 原始作业请求见 request_original.txt；本次补充指令见 workflow_update.txt。
# AI辅助内容：Python数据生成、分层划分、计数核验、结果导出、技能绘图，以及基于实际验证数据的分析与结论。
# 助手验证：数据生成及分层检查通过；Python与R统计一致；中文图形已目视检查。
# 学生修改：待填写；学生运行时间与输出目录：待填写；对AI分析的核验及个人理解：待填写。
# 不得将助手验证记录标为学生已验证。
