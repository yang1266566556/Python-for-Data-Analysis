# 第二次作业 铁路数据分析

本组 Notebook 对应铁路时间矩阵、降维与聚类作业。文件编号沿用原 `2homework1` 至 `2homework8` 的对应关系；所有文件仍位于 `notebooks`，无需改变 Jupyter 工作目录。

## 文件入口

| 序号 | 文件 | 内容 |
|---|---|---|
| 01 | [hw02_01_environment_check.ipynb](hw02_01_environment_check.ipynb) | 环境与依赖核验 |
| 02 | [hw02_02_direct_collection.ipynb](hw02_02_direct_collection.ipynb) | 旧来源复核与直达采集 |
| 03 | [hw02_03_collection_resume.ipynb](hw02_03_collection_resume.ipynb) | 固定解析版本与断点续采 |
| 04 | [hw02_04_source_audit_and_routes.ipynb](hw02_04_source_audit_and_routes.ipynb) | 来源审计与日期行程搜索 |
| 05 | [hw02_05_followup_collection.ipynb](hw02_05_followup_collection.ipynb) | 定向补采计划与覆盖检查 |
| 06 | [hw02_06_time_matrix.ipynb](hw02_06_time_matrix.ipynb) | 日期恢复与完整时间矩阵 |
| 07 | [hw02_07_dimensionality_reduction.ipynb](hw02_07_dimensionality_reduction.ipynb) | 降维实验与地理对齐 |
| 08 | [hw02_08_clustering.ipynb](hw02_08_clustering.ipynb) | 聚类实验与稳定性评价 |

## 环境与本地依赖

- Notebook 内核：`pda312`；本机解释器默认配置为 `D:\anaconda\envs\pda312\python.exe`。
- 外部分析项目：`D:\yangz\大三上\机器学习\第二次作业\railway_analysis`。
- 第01份保留环境诊断；第02至08份的公共依赖和项目路径统一放在“环境初始化”中，移动到其他机器时从这里核对配置。
- 业务实现仍位于外部项目的 `scripts`；原始响应、处理结果、分析结果及当前版本标记分别由该项目的 `data/raw`、`data/processed`、`data/analysis`、`evidence` 等目录提供。模块以自身所在位置确定项目根目录，因此这些目录应保持配套。
- 主要依赖包括 NumPy、pandas、SciPy、scikit-learn、UMAP、IPython 和 requests；现有依赖环境未安装、升级或降级。
- 整理时第01份的环境清单报告 `networkx`、`pyproj` 未安装；当前外部 `scripts` 的静态搜索未发现这两个包的引用。本次保留原检查清单并记录此差异，不因此声称整个项目已完成执行验证。
- 仓库根目录的 `environment.yml` 是已有公共环境配置；本次未修改。它没有列出本组完整的 UMAP、网络采集等依赖，不能仅据此认为铁路作业依赖已齐全。

本组文件当前仍依赖本机的外部分析项目。只克隆此 GitHub 仓库不能独立得到完整铁路脚本和来源数据；本次未复制、移动或修改外部项目。

## 阅读与执行

1. 先阅读文件顶部导读。需要执行时，先选择 `pda312`；第01份运行环境核验，第02至08份先运行“环境初始化”，重启内核后同样先初始化。
2. 各题和步骤保留原顺序，节前列出的前置变量来自同一文件较早的步骤。保留实际日期、查询范围、随机种子、参数、核验条件和输出口径。
3. 第02、03、05、06份包含原采集、补采或诊断流程。原2026年11月的采集窗口已结束，相关截止条件保留，不通过改时间戳来重跑。阅读已有结果不需要重新采集。
4. 第06份保留初次查询、手动重试及网络恢复等不同来源分支。完整矩阵位于末尾核心代码35；这些历史分支并非当前最终结果的必经运行流程。
5. 第07份的 UMAP 安装单元格仅在缺少依赖时手动使用；新安装后按原说明重启内核，再运行初始化。不要为了阅读结果重复安装或重新拟合。
6. 第07份保留最后一次成功运行的基线及核验单元格，删除的早期一组与保留组源代码逐字相同；原件和历史失败输出在整理前备份中保留。第02份的历史失败输出仍随原步骤保留。
7. 所有保留输出、执行编号及耗时均来自原 Notebook。本次整理没有重新采集或运行82组降维、198组聚类，不把旧输出声称为本次运行结果。

## 整理边界

仅整理本组8份 Notebook，并同步根目录 README 的本组入口。原数据、第一份作业、课程示例和 `railway_stage*` 文件保持原样；原始 Notebook 已在仓库外备份。未执行 Git 提交或推送。
