# 铁路网络作业：第一阶段 A——来源测试与采集入口

**当前交付：** `第一阶段F_补采效果评估与16组关键查询_核心17至19.txt`。已完成385组补采的离线评估，60分钟情景覆盖934→960；剩32个缺口中31个是拉萨首程未知，1个是海口→拉萨。不直接重试剩余119组，优先16个实际站点/日期查询。R绘图由助手处理，采集过程在最终正文中简写。详见 `docs/stage1f_effect_assessment.md`。

**最新（用户核心代码10—12已回传核验）：** 继续使用 `第一阶段E_定向补采_核心代码14至16.txt`，504组计划由436组后续日期查询和68组原缺失查询复查组成。原995组无需重跑。当前图内934个城市对有候选、58个待补；拉萨出发首程时刻未知需单独处理。核心代码13的用户绘图要求已撤回，绘图由助手负责。详见 `docs/stage1d_user_verified_stage1e_ready.md`。

**2026-11-13最新进度：** 用户已完成全部995组采集，22,137条有效记录，88条时刻未知、10条站码待核验。请使用TXT `第一阶段D_核验中转与R绘图_核心代码10至13.txt` 继续离线核验、时刻表路径与R质量图；无需再跑核心代码8。详细状态见 `docs/stage1c_complete_stage1d_ready.md`。完整最短行程矩阵及降维仍待后续步骤。

**2026-11-11最新进度：** A和B续跑材料已保存，今天继续第一阶段C。请运行 `railway_stage1c.ipynb`：先离线复核旧批次，再采集独立的11月18日城市对数据（995组，可中断续采）。完整状态见 `docs/progress_20261111.md`。原11月10日已过期，不要重跑旧联网采集代码；旧数据继续作为先导实验保留。

**续跑提示：** B批次已发现11月14日两条“运行图调整、暂停发售”的未知时刻记录。解析与续跑已修复，当前请使用 `railway_stage1b_resume.ipynb`，详见 `docs/stage1b_placeholder_fix.md`，无需重跑A或原B。

**进度更新：** 用户已运行第一阶段A，249条记录与原始响应、3张截图及Notebook核验一致。下一批请运行独立的 `railway_stage1b.ipynb`，说明见 `docs/stage1b_instructions.md`；理解说明草稿见 `docs/understanding_draft.md`。下文为第一阶段A的原始运行说明，不需要重复采集A。

本目录创建于 2026-11-05。用户已确认：未指定日期；澳门采用纯铁路主方案与铁路加接驳对照；使用本目录及 Python 计算、R 优先绘图的分工。

**当前不是第一阶段全部完成，更不是可直接降维的铁路矩阵。** 目前完成了来源访问测试、34 城市草案、车站编码核验和可运行的小规模采集代码。所有经纬度尚待有来源地补齐。

## 你现在要做的操作

1. 在现有 Jupyter 页面打开 `railway_stage1.ipynb`。文件位于 `D:\Python for Data Analysis\notebooks`。
2. 选择 **Python for Data Analysis (pda312)**，从第一格按顺序运行。本批只需标准库和已安装的 requests；不安装软件。
3. 保存执行后的 Notebook。按其中标注，截图“问题1—核心代码1、2、3”及其紧随的输出。输出多时分两张，保留代码编号。
4. 回传输出末尾所列目录中的 `pilot_summary.json`、`pilot_query_quality.csv`、`pilot_train_records.csv`、`cleaning_issues.csv`，以及截图。CSV 比截图更适合核对数值。`source_manifest.json` 和原始 `.bin` 文件保留本地，必要时补充。
5. 如果提示停止、返回空结果或报错，请回传实际输出；不要把错误改成“不可达”，也不要反复重跑。

运行顺序和输入输出说明见 Notebook，每次执行会创建独立时间戳目录，不覆盖前次数据。预期耗时约半分钟至数分钟，取决于网络；遇到障碍会停止后续请求。

## 文件安排

| 位置 | 内容 |
| --- | --- |
| `config/research_protocol.json` | 冻结日期、窗口、当前范围、缺失及不可达政策 |
| `config/nodes_34_draft.csv` | 34 个代表城市及选择依据；坐标待补，内部编码明确标注 |
| `config/station_candidates_draft.csv` | 82 个候选国铁车站；字典匹配不等于最终纳入或当天运营 |
| `scripts/stage1_collect.py` | 完整采集和检查代码，依赖标准库及 requests |
| `scripts/check_r_environment.R` | 可选 R 环境诊断；不应当作 Python 执行 |
| `data/raw/assistant_*` | 助手实际访问的官方响应与时间记录；不是用户实验记录 |
| `data/raw/user_pilot_*` | 由你运行 Notebook 后产生的原始数据、配置及代码快照 |
| `data/processed/user_pilot_*` | 对应用户运行产生的车站表、列车表和质量记录 |
| `evidence/assistant_parser_verification.json` | 助手对真实已保存响应进行的离线解析检查 |
| `docs/source_findings.md` | 本轮来源核验结论、已知限制和未完成项 |
| `docs/protocol_stage1.md` | 本阶段研究口径和后续矩阵准入条件 |
| `evidence/user_request_original.txt` | 用户粘贴的原始任务要求，保留原文 |
| `evidence/ai_use_log.json` | 实际 AI 协作记录；用户修改及理解部分待用户填写 |
| `figures/`、`tables/`、`reports/` | 后续成果保留位置，当前未生成最终图表或报告 |

CSV 使用 UTF-8 BOM，便于 Windows Excel 打开。Python 可用 `encoding="utf-8-sig"`；R 可用 `readr::read_csv()`。所有时间采用 UTC+08:00。

## 如果需要从终端运行

以下是 **PowerShell** 命令，不要粘贴进普通 Python 单元格：

```powershell
& 'D:\anaconda\envs\pda312\python.exe' -X utf8 'D:\yangz\大三上\机器学习\第二次作业\railway_analysis\scripts\stage1_collect.py' --actor user
```

推荐使用 Notebook，因为需要保留实际代码和对应输出截图。

可选 R 诊断（PowerShell）：

```powershell
& 'D:\R\R-4.6.0\bin\Rscript.exe' --vanilla --encoding=UTF-8 'D:\yangz\大三上\机器学习\第二次作业\railway_analysis\scripts\check_r_environment.R'
```

## 当前已知边界

- 查询日期冻结为 **2026-11-10（周二）**，两组真实查询已验证能返回该日期的记录；这不是对全部城市或后续日期可查询性的保证。
- 查询接口来自 12306 网页自身的 `CLeftTicketUrl`，不是具有公开服务保证的开放 API。每次请求至少间隔 2 秒，最多 8 组列车查询，不登录、不下单、不自动重试。HTTP 401/403/429、非 JSON、字段变化或网络错误均停止；不能据此声称拥有批量使用许可。
- 首次港铁首页请求超时，但随后实际取得港铁时间表及乘车流程页；原始失败和成功记录都保留。
- 港澳通关不包含在“列车首发至末到”的时间指标中。研究结果须称为站到站时刻表成本，不能称为含全部通关时间的旅客全程。
- 当前 34 城市列表、车站候选、有限时间和查询返回结果不能直接作为算法矩阵；尚未解决全量覆盖、中转、车站接驳和地理坐标。
- 台湾没有跨海铁路连接是本研究任务已明确的前提；正式来源表仍需补充相应官方依据。澳门连接分类也不能仅凭当前网页或查询为空自动确定。
- R 4.6.0、ggplot2 4.0.3、readr 2.2.0 可读取；ggrepel、sf 未发现。R 技能的两处原私人源库路径缺失，助手脚本可读，绘图工作流尚未完成验证。
- R 启动时实际出现 `Setting LC_*=C.UTF-8 failed` 区域设置警告，工作目录中的中文显示为 Unicode 转义；包版本能读取不代表中文路径和绘图字体已验证。此项留待正式 R 绘图前处理，不影响本批 Python 采集。

下一步：核对你运行的查询质量，决定全量时刻表覆盖和中转扩展方式。矩阵质量审核通过后才进入 MDS、t-SNE、UMAP。生成 DOCX 必须等待你明确确认材料齐全且核验完成。
