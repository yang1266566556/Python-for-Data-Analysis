# 铁路网络降维与聚类作业

本目录保存第二次作业的业务脚本、来源数据、固定矩阵及已有实验结果。与第一次作业的 `imbalanced_classification/` 对应：Notebook是阅读和分步执行入口，专题目录集中保存公共模块、依赖与实验材料。题目分为铁路时间矩阵、降维与地理对齐、聚类与稳定性三个部分。

## 题目与入口

| 原文件 | 推荐Notebook入口 | 内容 | 主要脚本 |
|---|---|---|---|
| 2homework1 | [hw02_01_environment_check.ipynb](../hw02_01_environment_check.ipynb) | 环境与读写能力核验 | `common.py` |
| 2homework2 | [hw02_02_direct_collection.ipynb](../hw02_02_direct_collection.ipynb) | 旧来源复核与直达采集 | `stage1_collect.py`、`stage1c_collect.py` |
| 2homework3 | [hw02_03_collection_resume.ipynb](../hw02_03_collection_resume.ipynb) | 固定解析版本与断点续采 | `stage1c_collect_v2.py`、`stage1c_resume_v2.py` |
| 2homework4 | [hw02_04_source_audit_and_routes.ipynb](../hw02_04_source_audit_and_routes.ipynb) | 来源审计与日期行程搜索 | `stage1d_audit.py`、`stage1d_routes.py` |
| 2homework5 | [hw02_05_followup_collection.ipynb](../hw02_05_followup_collection.ipynb) | 定向补采与覆盖检查 | `stage1e_followups.py`、`stage1f_assess.py` |
| 2homework6 | [hw02_06_time_matrix.ipynb](../hw02_06_time_matrix.ipynb) | 日期恢复、澳门接驳与完整时间矩阵 | `stage1g_*`至`stage1n_*` |
| 2homework7 | [hw02_07_dimensionality_reduction.ipynb](../hw02_07_dimensionality_reduction.ipynb) | MDS、t-SNE、UMAP和地理对齐 | `stage2_*.py` |
| 2homework8 | [hw02_08_clustering.ipynb](../hw02_08_clustering.ipynb) | HAC、PAM、DBSCAN及稳定性 | `stage3_algorithms.py`、`stage3_clustering.py` |

01至08沿用原文件的序号对应关系，保留题目顺序和已有输出。第06份末尾核心代码35是最终矩阵入口；其中较早的失败、补采和恢复分支作为历史过程保留，不是阅读最终结果的必经步骤。

## 目录说明

```text
notebooks/
├─ hw02_01_*.ipynb ... hw02_08_*.ipynb  # 分步阅读入口
└─ railway_analysis/
   ├─ common.py                        # 公共路径、环境和固定来源检查
   ├─ requirements.txt                 # 原实验主要版本及配套环境版本
   ├─ scripts/                         # 原阶段脚本与绘图辅助脚本
   ├─ config/                          # 34节点、站名匹配和采集协议
   ├─ data/
   │  ├─ raw/                          # 原始响应、检查点及采集协议
   │  ├─ processed/                    # 解析记录、日期行程和时间矩阵
   │  ├─ analysis/                     # 降维、地理对齐和聚类结果
   │  └─ diagnostics/                  # 历史诊断证据
   ├─ evidence/                        # 来源凭据、授权和当前批次标记
   ├─ environment/                     # 原依赖安装记录
   ├─ docs/                            # 原阶段说明与历史项目README
   └─ provenance/
      ├─ original_scripts/             # 原脚本逐字快照，用于历史代码哈希核验
      └─ migration_manifest.json       # 文件哈希及路径适配改动记录
```

原外部项目保留原位。报告、PDF、排版备份及报告构建脚本未迁入；Word交付不属于这个代码目录。已有实验CSV和坐标、标签、矩阵等结果位于 `data/`。Python阶段脚本保留原名及算法结构，不为统一题号额外增加一层包装。

## 环境与启动

原降维和聚类protocol均记录Python 3.12.13、NumPy 2.5.0、pandas 3.0.3、SciPy 1.18.0、scikit-learn 1.9.0、umap-learn 0.6.0及requests 2.34.2。公共检查约束Python 3.12和这六个主要包的版本，不限定解释器安装盘符。`requirements.txt` 的其余版本来自2026年11月15日对现有环境的只读核对，不是原实验完整依赖锁文件。

建议在独立Python 3.12环境中安装。在仓库根目录执行：

```powershell
python -m pip install -r notebooks/railway_analysis/requirements.txt
python -m notebook --notebook-dir notebooks
```

打开上表Notebook，先运行“公共初始化”，再按题目顺序运行需要的步骤。支持从仓库根目录或 `notebooks/` 启动；本组不再要求 `D:\anaconda` 或原课程目录存在。不要在同一内核混用旧外部项目与当前仓库的同名阶段模块，切换来源后应重启内核。

第01份保留原环境诊断清单，其中 `networkx`、`pyproj` 在整理时未安装；当前业务脚本没有引用这两个包，因此未把它们增加为核心依赖。第07份的UMAP安装步骤属于历史可选入口，已有依赖无需再安装。本次整理未执行任何依赖安装。

## 固定来源与已有结果

`common.py` 列出以下原作业批次，读取已有结果时不按“最新目录”自动选择：

| 用途 | 固定路径（相对本目录） |
|---|---|
| 最终33节点与9组34节点矩阵 | `data/processed/user_stage1n_special_20261114_140146_715895` |
| 13份降维输入 | `data/analysis/user_stage2_inputs_20261114_143755_625472` |
| 6次基线 | `data/analysis/user_stage2_baseline_20261114_145338_648190` |
| 82组参数、种子和情景实验 | `data/analysis/user_stage2_experiments_20261114_151354_734440` |
| 地理对齐 | `data/analysis/user_stage2_geographic_analysis_20261114_165132_458783` |
| 198组聚类 | `data/analysis/user_stage3_clustering_20261114_171710_794272` |

原采集截止时间保持为2026年11月13日21:28:30.987887（UTC+8），11月14日的两组查询是独立补充版本。原始响应及采集日期未改写；窗口已结束，不应修改历史时间戳以重新采集。查看保存结果不需要联网或重新训练。

澳门接驳30/60/90分钟是情景假设，主情景60分钟；台北66个有向单元格使用结构惩罚，不代表真实旅行时间。34节点主情景包含这些处理，33节点对照不含台北，相关区别继续保留。结果不能被解释为已核验余票或实际运行保证。

完整执行分析Notebook会生成新批次，并可能更新当前批次标记。已有输出是原实验记录，不是本次重新计算的结果。开启新实验前应明确输入、参数和版本方案，避免覆盖或混用固定来源。

## 来源与路径完整性

原数据、CSV和JSON逐字复制，保留其中原有盘符、来源时间、代码哈希和数据哈希。`scripts/railway_project_io.py` 只在读取时把原项目路径解释为当前项目位置，不回写历史记录，也不回退到外部项目读取文件。相对Windows路径按当前系统转换。

路径适配导致部分运行脚本与原文件字节不同。原脚本存于 `provenance/original_scripts/`，迁入记录同时保存原版和运行版SHA256；历史代码检查同时核对原快照及已记录的运行适配版本。原始数据、矩阵、坐标和标签的哈希仍按真实文件字节核对，没有放宽。新实验记录实际运行脚本的哈希。

仅检查环境、脚本及固定结果位置，可在仓库根目录执行：

```powershell
python -B -c "import sys; sys.path.insert(0, 'notebooks'); from railway_analysis.common import initialize_project, fixed_result_directories; print(initialize_project()); print(fixed_result_directories())"
```

该命令不采集、不训练、不创建实验结果。若之后有意修改算法脚本，应明确新实验版本并复核迁入记录；不要删除来源检查或直接覆盖原数据来消除错误。

## 图表与Git范围

保留原R绘图脚本及Python绘图输入辅助脚本。R脚本仍可能需要原机器的R环境和本地绘图主题，本次不声称其已完成跨机器运行验证；Python实验与读取已有结果不要求运行R。报告用成品图片及报告排版过程留在原外部项目。

作业级 `.gitignore` 明确保留迁入的已有数据批次，覆盖根规则对 `data/raw`、`data/processed` 的默认忽略；缓存及未来新生成的批次仍被忽略。本次没有Git暂存、提交或推送。原Notebook历史输出中的本机路径作为实验记录保留。
