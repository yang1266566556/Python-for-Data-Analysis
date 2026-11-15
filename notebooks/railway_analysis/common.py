"""第二次作业的公共路径、环境和固定来源检查；导入时不运行实验。"""
from importlib.metadata import version
from pathlib import Path
import sys

from .scripts.railway_project_io import check_runtime_sources

PROJECT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"
INPUT_BATCH = "user_stage2_inputs_20261114_143755_625472"
BASELINE_BATCH = "user_stage2_baseline_20261114_145338_648190"
EXPERIMENT_BATCH = "user_stage2_experiments_20261114_151354_734440"
GEOGRAPHY_BATCH = "user_stage2_geographic_analysis_20261114_165132_458783"
CLUSTER_BATCH = "user_stage3_clustering_20261114_171710_794272"
EXPECTED_VERSIONS = {
    "numpy": "2.5.0", "pandas": "3.0.3", "scipy": "1.18.0",
    "scikit-learn": "1.9.0", "umap-learn": "0.6.0", "requests": "2.34.2",
}


def check_environment():
    """检查原实验的Python主次版本和主要依赖版本，不限定安装盘符。"""
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(f"请使用Python 3.12，当前为{sys.version.split()[0]}")
    for package, expected in EXPECTED_VERSIONS.items():
        actual = version(package)
        if actual != expected:
            raise RuntimeError(f"{package}记录版本为{expected}，当前为{actual}；请核对requirements.txt")


def initialize_project(required_modules=(), *, check_versions=True):
    """检查当前仓库中的模块和代码快照，幂等设置旧脚本的导入路径。"""
    if check_versions:
        check_environment()
    missing = [name for name in required_modules if not (SCRIPTS_DIR / f"{name}.py").is_file()]
    if missing:
        raise FileNotFoundError(f"作业脚本缺失：{', '.join(missing)}")
    for name, module in list(sys.modules.items()):
        if name.startswith("stage") and getattr(module, "__file__", None):
            if Path(module.__file__).resolve().parent != SCRIPTS_DIR.resolve():
                raise RuntimeError("内核已加载另一位置的铁路模块。请重启内核，再运行当前文件的公共初始化。")
    check_runtime_sources()
    scripts_path = str(SCRIPTS_DIR)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    return PROJECT_DIR


def fixed_result_directories():
    """返回原作业已核验的分析批次；不按最新目录自动选择来源。"""
    return {
        "inputs": PROJECT_DIR / "data/analysis" / INPUT_BATCH,
        "baseline": PROJECT_DIR / "data/analysis" / BASELINE_BATCH,
        "experiments": PROJECT_DIR / "data/analysis" / EXPERIMENT_BATCH,
        "geography": PROJECT_DIR / "data/analysis" / GEOGRAPHY_BATCH,
        "clustering": PROJECT_DIR / "data/analysis" / CLUSTER_BATCH,
    }
