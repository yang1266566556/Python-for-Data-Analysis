"""Create a separate unexecuted notebook; preserve stage1 user outputs."""
import json
from pathlib import Path

DEST = Path(r"D:\Python for Data Analysis\notebooks\railway_stage1b.ipynb")


def md(s):
    return dict(cell_type="markdown", metadata={}, source=s.splitlines(keepends=True))


def code(s):
    compile(s, "stage1b_notebook", "exec")
    return dict(cell_type="code", metadata={}, source=s.splitlines(keepends=True), execution_count=None, outputs=[])


cells = [
    md("""# 问题1：第一阶段 B——跨日中转与接入核验

使用 **Python for Data Analysis (pda312)**。依赖：标准库、requests、pandas，均已在先前环境中发现。
无需安装软件。按顺序运行，预计半分钟至数分钟；遇到查询错误会保存记录并停止后续请求，不自动重试。

输入：已核验的 `user_pilot_20261105_220920_089173` 原始数据及 `config/stage1b_protocol.json`。
仅补查7组列车数据，不重跑原来的8组，不改动已执行的 `railway_stage1.ipynb`。
输出：独立的 `data/raw/user_stage1b_*` 与 `data/processed/user_stage1b_*`。

研究范围限于北京候选站→西宁→拉萨的两段不同列车，以及珠海、横琴方向的查询测试。
30/60/90分钟换乘门槛是研究假设，不是已核实的官方最低换乘时间。
结果只能称为“已采集范围和假设下时间上能衔接的候选行程”，不能称为全国铁路最短行程或保证可实现的旅行。
"""),
    code('''# 问题1—辅助代码1：检查内核并加载本批代码
import sys, json, importlib
from pathlib import Path
import pandas as pd
ROOT = Path(r"D:\\yangz\\大三上\\机器学习\\第二次作业\\railway_analysis")
assert Path(sys.executable).resolve() == Path(r"D:\\anaconda\\envs\\pda312\\python.exe").resolve()
sys.path.insert(0, str(ROOT / "scripts"))
import stage1b_transfer
stage1b_transfer = importlib.reload(stage1b_transfer)
print("本批复用已保存数据，新增7组查询；不直接生成完整矩阵。")
'''),
    md("""## 问题1—核心代码4：补查实际中转日期

功能：先重建并核对原始数据与CSV，再查询西宁→拉萨11月11—14日的记录及3组珠海/横琴接入方向。
应截图：代码、每组查询状态和汇总输出。
保存：`new_query_quality.csv`、`new_train_records.csv`、`cleaning_issues.csv`、原始响应和元数据。
83站版本草案另外保存，新增清河站，原82站表保持原样。
"""),
    code('''# 问题1—核心代码4：核对原始记录，再补查中转日期
summary_b = stage1b_transfer.collect_stage1b(actor="user")
OUT_B = Path(summary_b["output_dir"])
quality_b = pd.read_csv(OUT_B / "new_query_quality.csv", encoding="utf-8-sig")
display(quality_b[["query_id", "date", "from_station", "to_station", "status", "valid_count"]])
print("新增列车记录：", summary_b["new_train_records"])
print("换乘所需查询日期均已成功返回：", summary_b["all_required_transfer_dates_queried_successfully"])
print("错误：", summary_b["fatal_error"])
print("输出目录：", OUT_B)
'''),
    md("""## 问题1—核心代码5：同站配对及换乘门槛对比

功能：按实际站码、完整日期和始发日期识别列车，加入中转等待，剔除赶不上的配对。
完整实现位于 `scripts/stage1b_transfer.py` 中的 `build_pairs` 和 `summarize_pairs`。
应截图：代码及三种门槛的结果；无候选或查询不完整时原样保留空结果。
保存：`all_same_station_pairs.csv`、`same_service_candidates.csv`、`transfer_scenarios.csv`。
"""),
    code('''# 问题1—核心代码5：检查等待时间只计入一次，再比较门槛
pairs_b = pd.read_csv(OUT_B / "all_same_station_pairs.csv", encoding="utf-8-sig")
scenarios_b = pd.read_csv(OUT_B / "transfer_scenarios.csv", encoding="utf-8-sig")
ordered_b = pairs_b.loc[pairs_b["time_order_ok"].astype(str).str.lower().eq("true")]
assert (ordered_b["total_min"] == ordered_b["first_duration_min"] +
        ordered_b["wait_min"] + ordered_b["second_duration_min"]).all()
display(scenarios_b[["transfer_threshold_min", "candidate_count", "status",
                     "total_min", "wait_min", "first_train", "second_train"]])
print("30/60/90分钟是筛选门槛；等待已计入总历时，不能再额外加一次门槛。")
print("官方换乘可行性已核验：", summary_b["official_transfer_feasibility_verified"])
'''),
    md("""## 问题1—核心代码6：核对代表行程的时间顺序

功能：仅在日期查询完整且60分钟假设下有候选时，展示已采集候选中的最小历时配对。
应截图：代码和代表行程时间表，或没有可报告候选的实际提示。
保存：代表行程可从 `all_same_station_pairs.csv` 重建；本格另外写入 `representative_transfer_60min.csv`。
这不是对所有路线、所有中转站或同车直达服务的最短性证明。
"""),
    code('''# 问题1—核心代码6：展示60分钟换乘假设下的候选
eligible_b = pairs_b.loc[(pairs_b["classification"] == "time_ordered_transfer_candidate") &
                         (pairs_b["wait_min"] >= 60)]
if summary_b["all_required_transfer_dates_queried_successfully"] and not eligible_b.empty:
    best_b = eligible_b.sort_values(["total_min", "departure_at", "first_train", "second_train"]).head(1)
    display(best_b[["first_train", "second_train", "from_station", "transfer_station", "to_station"]])
    display(best_b[["departure_at", "transfer_arrival_at", "transfer_departure_at", "arrival_at"]].T)
    display(best_b[["first_duration_min", "wait_min", "second_duration_min", "total_min"]])
    best_b.to_csv(OUT_B / "representative_transfer_60min.csv", index=False, encoding="utf-8-sig")
else:
    print("查询不完整或没有满足假设的候选；此时不能报告最短值或认定不可达。")
'''),
    md("""## 回传与理解说明

保存Notebook，回传核心代码4—6及对应输出截图。我会读取共享目录的CSV核验，无须把所有表格抄成截图。
若本地文件不在共享目录，补充 `stage1b_summary.json`、`new_query_quality.csv`、`transfer_scenarios.csv`、`all_same_station_pairs.csv`。

可先阅读作业目录 `docs/understanding_draft.md` 的解释草稿，再用自己的话核对、改写。草稿并不表示你已确认理解。
本阶段仍未生成完整矩阵，没有开始降维、聚类或DOCX制作。
"""),
]

if __name__ == "__main__":
    for i, cell in enumerate(cells):
        cell["id"] = f"railway-stage1b-{i:02d}"
    nb = dict(cells=cells, nbformat=4, nbformat_minor=5, metadata={
        "kernelspec": {"display_name": "Python for Data Analysis (pda312)", "language": "python", "name": "pda312"},
        "language_info": {"name": "python", "version": "3.12.13"}})
    with DEST.open("x", encoding="utf-8") as handle:
        json.dump(nb, handle, ensure_ascii=False, indent=2)
    print(DEST)
