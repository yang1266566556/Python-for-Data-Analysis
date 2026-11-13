"""不平衡分类作业的路径、环境检查与固定数据读取；导入时不创建输出。"""
from pathlib import Path
import hashlib
import json
import sys
from importlib.metadata import version

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
# 固定引用已核验的原始实验，避免不同题目误用新生成的批次。
SOURCE_DIR = PROJECT_DIR / "runs/20261020_221259_7f297c"
Q3_SOURCE = PROJECT_DIR / "q3_runs/20261021_111602_87b2fd"
Q4_SOURCE = PROJECT_DIR / "q4_runs/20261021_122610_cb3b24"
Q5_SOURCE = PROJECT_DIR / "q5_runs/20261021_124751_b53362"


def read_json(path):
    """读取原始实验记录，不改动其中的路径、时间或来源字段。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_environment():
    """检查Python主次版本及原实验记录的数值计算依赖，不限定安装位置。"""
    manifest = read_json(SOURCE_DIR / "results/manifest.json")
    expected_python = tuple(map(int, manifest["python"].split()[0].split(".")[:2]))
    if sys.version_info[:2] != expected_python:
        raise RuntimeError(f"请使用Python {expected_python[0]}.{expected_python[1]}，当前为{sys.version.split()[0]}")
    for package in ("numpy", "pandas", "scikit-learn"):
        actual = version(package)
        expected = manifest["versions"][package]
        if actual != expected:
            raise RuntimeError(f"{package}版本应为{expected}，当前为{actual}；请核对requirements.txt")


def dataset_sha256(X, y, train_idx, test_idx):
    """沿用原作业的数组拼接顺序计算哈希。"""
    return hashlib.sha256(X.tobytes() + y.tobytes() + train_idx.tobytes() + test_idx.tobytes()).hexdigest()


def load_fixed_dataset(source_dir=SOURCE_DIR):
    """读取固定数组和五折索引，关闭NPZ后校验原始数据哈希。"""
    source_dir = Path(source_dir)
    manifest = read_json(source_dir / "results/manifest.json")
    with np.load(source_dir / "data/dataset_and_split.npz", allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    actual = dataset_sha256(*(arrays[name] for name in ("X", "y", "train_idx", "test_idx")))
    if actual != manifest["data_split_sha256"]:
        raise ValueError("第一题数据或划分与原始记录不一致，请检查输入文件")
    return arrays
