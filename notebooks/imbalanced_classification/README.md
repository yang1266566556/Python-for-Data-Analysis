# 有监督不平衡分类作业

本目录保存十分类不平衡数据实验的代码、原始结果和分析材料。主要阅读入口是上一级的 `homework*.ipynb`，沿用原有作业编号。数据生成配置为4800个样本、24个特征、10个类别；实验依据原始保存的数据及固定训练/测试划分进行比较。

## 题目与入口

| 题号 | 主要Notebook | 对应脚本 | 内容 |
| --- | --- | --- | --- |
| 1 | [homework1.ipynb](../homework1.ipynb) | [q1_initialization.py](q1_initialization.py) | 数据生成、分层划分和类别统计 |
| 2 | [homework2.ipynb](../homework2.ipynb) | [q2_constant_baseline.py](q2_constant_baseline.py) | 多数类常数预测与评价指标 |
| 3 | [homework3.ipynb](../homework3.ipynb) | [q3_default_classifiers.py](q3_default_classifiers.py) | 四类默认分类器比较 |
| 4 | [homework4.ipynb](../homework4.ipynb) | [q4_standardization_timing.py](q4_standardization_timing.py) | 标准化、预测质量与耗时 |
| 5 | [homework5.ipynb](../homework5.ipynb) | [q5_parameter_validation.py](q5_parameter_validation.py) | 单参数扫描与固定五折验证 |
| 6 | [问题6分析](问题6_极端参数分析.md) | 无独立训练脚本 | 极端参数下的模型行为 |
| 7 | [homework7.ipynb](../homework7.ipynb) | [q7_class_weight.py](q7_class_weight.py) | 类别权重与不平衡处理 |
| 8 | [homework8.ipynb](../homework8.ipynb) | [q8_gamma_curves.py](q8_gamma_curves.py) | gamma与拟合程度曲线 |
| 9 | [问题9分析](问题9_过拟合与欠拟合分析.md) | 无独立训练脚本 | 欠拟合、过拟合和数据条件 |

第6、9题为理论分析，因此现有Notebook编号没有6、9，并非文件缺失。表中的Python脚本为另一种执行入口，不必与Notebook重复运行。两种入口保留各自已有说明与输出方式，本次只同步公共初始化逻辑。

## 目录说明

```text
notebooks/
├─ homework1.ipynb ... homework8.ipynb  # 现有7份主要Notebook
└─ imbalanced_classification/
   ├─ common.py                       # 路径、环境、固定数据读取与哈希检查
   ├─ requirements.txt                # 实测依赖及版本来源
   ├─ q*.py                           # 对应题目的脚本入口
   ├─ q*_plot.R                       # 历史绘图脚本，保留原样
   ├─ runs/                           # 第一题数据和划分
   ├─ q2_runs/ ... q8_runs/            # 各题已保存的实验记录（无q6_runs）
   ├─ materials/                      # 原代码和结果截图
   ├─ 问题*_分析与结论.md 等           # 分析材料、推导及结果表
   └─ assistant_validation/            # 辅助核验记录，非学生实验结果
```

本目录中 `01_初始化与问题1.ipynb` 等7份带中文题名的Notebook是保留的旧入口，未经本次整理，不作为推荐运行入口；其绝对路径和环境检查可能仅适用于原机器。`q1_export_recovery.py` 用于在第一题数组仍存在的内核中补齐导出环境，不是独立的数据生成步骤。

## 环境与启动

原始第一题 `results/manifest.json` 记录Python 3.12.13，以及NumPy 2.5.0、pandas 3.0.3、scikit-learn 1.9.0、ipykernel 7.2.0。`requirements.txt` 的其余版本来自2026年11月13日对现有 `pda312` 环境的读取，并非原实验的完整依赖锁文件。当前整理没有执行依赖安装验证。

建议在独立的Python 3.12环境中安装依赖。在仓库根目录运行：

```powershell
python -m pip install -r notebooks/imbalanced_classification/requirements.txt
python -m notebook --notebook-dir notebooks
```

在Jupyter中选择该Python环境，打开上表中的Notebook并按单元顺序运行。若从仓库根目录或 `notebooks/` 启动，Notebook会自动定位本作业目录；无需保持原来的盘符或环境安装路径。环境检查保留Python主次版本及原始数值计算库版本约束。

也可从仓库根目录执行对应脚本，例如：

```powershell
python notebooks/imbalanced_classification/q3_default_classifiers.py
```

执行完整Notebook或实验脚本会创建新批次目录、训练模型并保存结果；这与下方仅检查现有输入的命令不同。已有Notebook输出仍为原运行记录，整理后未重新训练，计时结果也不应视为其他机器上的运行耗时。

## 固定来源与复现方式

`common.py` 明确引用以下原始实验批次：

| 用途 | 固定路径 |
| --- | --- |
| 各题共同数据、划分、五折索引 | `runs/20261020_221259_7f297c` |
| 第4题默认模型配置对照 | `q3_runs/20261021_111602_87b2fd` |
| 第7题标准化基线对照 | `q4_runs/20261021_122610_cb3b24` |
| 第8题复用的五折验证证据 | `q5_runs/20261021_124751_b53362` |

这些批次作为复现输入保留。第2、3、4、5、7、8题可以直接读取仓库中已有输入运行，无需重新生成第一题数据；第8题依赖已保存的第五题验证记录。公共读取函数会校验第一题数据与划分的SHA256，原有五折、模型配置和版本检查继续保留。

重新执行第1题会生成新的时间戳批次，但不会自动改变后续题目的固定来源。若要开展一套全新的实验，应先明确更新引用批次的方案，并同步复核第4、7、8题对照来源；不要混用不同批次或按“最新目录”自动取值。原实验参数、随机种子、标签0—9、`zero_division=0` 和先验证选参再评价测试集的流程均保持原样。

仅检查现有数据与环境，可在 `notebooks/` 下执行：

```powershell
python -B -c "from imbalanced_classification.common import check_environment, load_fixed_dataset; check_environment(); d = load_fixed_dataset(); print(d['X'].shape, d['y'].shape)"
```

此命令读取原始记录和NPZ、检查版本与哈希，不训练模型或创建实验结果。

## 图表、结果与Git范围

已有CSV、NPZ、截图、图表和分析材料均保留。图表由历史R脚本生成，核心Python实验不要求运行R；绘图脚本仍包含本机路径或本地主题依赖，本次未对R环境作迁移或复现验证。最终Word报告位于仓库外，不属于本次代码整理范围。

作业级 `.gitignore` 忽略缓存和未来新生成的批次，明确保留已有实验目录。忽略规则不会取消Git对已有文件的跟踪，也不会从既有提交中删除辅助校验记录或本机路径。原始manifest及Notebook历史输出中的路径和时间作为溯源记录保留。

提交时只选择本次明确改动的7份 `homework*.ipynb`、8份Python脚本及本目录新增的4个文件。铁路作业 `2homework*.ipynb`、根目录配置、旧Notebook、R脚本和原始结果不属于本次修改范围。
