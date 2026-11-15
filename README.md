# Python 数据分析

这是一个基于 Jupyter Notebook 的数据分析学习项目，配置了专用的 Conda 环境。

## 项目简介

本项目包含数据分析相关的学习笔记和实践代码，涵盖以下主题：

- **NumPy** - 数值计算库
- **SciPy** - 科学计算库
- **Pandas** - 数据处理与分析
- **机器学习** - 线性回归、决策树、K近邻等算法
- **不平衡分类** - 类别不平衡问题的处理方法
- **铁路网络分析** - 日期约束行程、时间矩阵、降维与聚类
- **数据可视化** - 使用 Matplotlib/Seaborn 进行图表绘制

## 项目结构

```
.
├── environment.yml          # Conda 环境配置
├── start-jupyter.ps1        # Jupyter 启动脚本 (PowerShell)
├── start-jupyter.bat        # Jupyter 启动脚本 (批处理)
├── fix-open-design-dsh-credentials.ps1
├── notebooks/               # Jupyter 笔记目录
│   ├── Unit2-Numpy.ipynb
│   ├── Unit2-Scipy.ipynb
│   ├── Unit2-pandas.ipynb
│   ├── Unit3-*.ipynb
│   ├── homework*.ipynb
│   ├── hw02_*.ipynb          # 第二次作业：按原编号排列的8份Notebook
│   ├── railway_analysis/    # 第二次作业的脚本、数据及固定实验结果
│   │   ├── common.py
│   │   ├── requirements.txt
│   │   ├── scripts/
│   │   ├── data/
│   │   ├── evidence/
│   │   └── README.md
│   ├── MNIST.train.csv
│   ├── MNIST.test.csv
│   ├── imbalanced_classification/   # 不平衡分类专题
│   │   ├── q1_initialization.py
│   │   ├── q2_constant_baseline.py
│   │   ├── q3_default_classifiers.py
│   │   ├── q4_standardization_timing.py
│   │   ├── q5_parameter_validation.py
│   │   ├── q7_class_weight.py
│   │   ├── q8_gamma_curves.py
│   │   └── *.R            # R 语言绘图脚本
│   └── ...
└── selflove-work/           # 图像处理工作目录
    └── photo-8f431107/
        └── analyze.py      # 图像分析与色卡匹配
```

## 环境配置

### 环境要求

- Anaconda 或 Miniconda
- Python 3.11+

### 创建环境

```powershell
# 使用 conda 命令创建环境
conda env create -f environment.yml

# 或使用 conda.bat（Windows）
D:\anaconda\condabin\conda.bat env create -f environment.yml
```

### 激活环境

```powershell
conda activate pda312
```

## 启动 Jupyter Notebook

### 方法一：使用启动脚本

```powershell
cd "D:\Python for Data Analysis"
.\start-jupyter.ps1
```

### 方法二：手动启动

```powershell
D:\anaconda\condabin\conda.bat run -n pda312 jupyter notebook --notebook-dir "D:\Python for Data Analysis\notebooks" --ServerApp.use_redirect_file=False
```

启动后，浏览器会自动打开 Jupyter 界面。如果浏览器没有自动打开，请使用终端中显示的 HTTP 地址（含 token）访问。

## 主要内容

### 基础教程 (Unit2)

| 文件 | 说明 |
|------|------|
| `Unit2-Numpy.ipynb` | NumPy 数组操作与向量化计算 |
| `Unit2-Scipy.ipynb` | SciPy 科学计算基础 |
| `Unit2-pandas.ipynb` | Pandas 数据框操作 |

### 机器学习 (Unit3)

| 文件 | 说明 |
|------|------|
| `Unit3-Linear Regression & Decisiontree.ipynb` | 线性回归与决策树 |
| `Unit3-k Nearest.ipynb` | K近邻算法 |

### 作业练习

| 作业 | Notebook入口 | 专题说明 |
|---|---|---|
| 第一次：有监督不平衡分类 | `homework1`、`2`、`3`、`4`、`5`、`7`、`8` | [不平衡分类作业](notebooks/imbalanced_classification/README.md) |
| 第二次：铁路网络降维与聚类 | `hw02_01` 至 `hw02_08` | [铁路分析作业](notebooks/railway_analysis/README.md) |

两组作业均采用“Notebook阅读入口＋专题目录”的组织方式；具体环境、固定数据批次及运行限制以各专题说明为准。

### 不平衡分类专题

包含完整的类别不平衡问题分析流程：
- 数据探索与可视化
- 基准模型建立
- 特征标准化
- 超参数调优
- 类别权重调整
- 学习曲线分析

### 铁路网络分析专题

第二次作业按数据采集与矩阵构建、降维与地理对齐、聚类与稳定性评价展开。`notebooks/railway_analysis/` 保存脚本、原始响应、处理矩阵及已有实验结果，Notebook通过公共模块定位项目，不依赖原机器的盘符。

该作业使用Python 3.12，完整依赖见 [requirements.txt](notebooks/railway_analysis/requirements.txt)。根目录 `environment.yml` 是公共学习环境，不能替代各作业的专用依赖说明。原2026年11月采集窗口已结束；保留结果可直接阅读，运行实验会生成新批次，详见专题README。

## 依赖项

核心依赖（参见 `environment.yml`）：

- numpy
- scipy
- pandas
- scikit-learn
- matplotlib
- seaborn
- jupyter

## 注意事项

1. 确保已正确安装 Anaconda 并配置好环境变量
2. 启动脚本会直接在浏览器中打开 Jupyter，避免了临时重定向文件导致的问题
3. 使用完成后保持终端窗口开启

## 许可证

本项目仅供学习交流使用。