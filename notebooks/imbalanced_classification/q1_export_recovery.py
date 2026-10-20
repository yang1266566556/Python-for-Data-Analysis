# 在当前Notebook的新代码单元中运行，然后重新运行原来报错的辅助单元。
# 只补齐导出环境；不重新生成X、y，也不修改训练/测试划分。
from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import sys
import uuid
import importlib.metadata as metadata

assert Path(sys.executable).resolve() == Path(r"D:\anaconda\envs\pda312\python.exe").resolve(), "请先核对当前内核，应为pda312"
PROJECT_DIR = Path(r"D:\Python for Data Analysis\notebooks\imbalanced_classification")
RUN_DIR = PROJECT_DIR / "runs" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
for folder in ("data", "results", "figures"):
    (RUN_DIR / folder).mkdir(parents=True, exist_ok=False)
VERSIONS = {p: metadata.version(p) for p in ("scikit-learn", "numpy", "pandas", "ipykernel")}
print("当前解释器：", sys.executable)
print("Python：", sys.version.split()[0], "；依赖：", VERSIONS)
print("输出目录已准备：", RUN_DIR)
print("现在重新运行原来报错的辅助单元；无需重新生成数据。")
