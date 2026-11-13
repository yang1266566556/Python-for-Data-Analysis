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

# 脚本入口使用自身路径定位，支持在任意工作目录执行。
_location = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
for _parent in (_location, *_location.parents):
    _notebooks = _parent if _parent.name == "notebooks" else _parent / "notebooks"
    if (_notebooks / "imbalanced_classification" / "common.py").is_file():
        if str(_notebooks) not in sys.path:
            sys.path.insert(0, str(_notebooks))
        break
else:
    raise FileNotFoundError("未找到作业目录，请从仓库根目录或notebooks启动")
from imbalanced_classification.common import (
    PROJECT_DIR, check_environment
)
check_environment()
RUN_DIR = PROJECT_DIR / "runs" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
for folder in ("data", "results", "figures"):
    (RUN_DIR / folder).mkdir(parents=True, exist_ok=False)
VERSIONS = {p: metadata.version(p) for p in ("scikit-learn", "numpy", "pandas", "ipykernel")}
print("当前解释器：", sys.executable)
print("Python：", sys.version.split()[0], "；依赖：", VERSIONS)
print("输出目录已准备：", RUN_DIR)
print("现在重新运行原来报错的辅助单元；无需重新生成数据。")
