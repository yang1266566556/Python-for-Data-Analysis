# Python 数据分析

这是一个基于 Jupyter Notebook 的数据分析学习项目，配置了专用的 Conda 环境。

## 项目简介

本项目包含数据分析相关的学习笔记和实践代码，涵盖以下主题：

- **NumPy** - 数值计算库
- **SciPy** - 科学计算库
- **Pandas** - 数据处理与分析
- **机器学习** - 线性回归、决策树、K近邻等算法
- **不平衡分类** - 类别不平衡问题的处理方法
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
│   ├── MNIST.train.csv
│   ├── MNIST.test.csv
│   ├── imbalanced_classification/   # 不平衡分类专题
│   │   ├── q1_export_recovery.py
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

- `homework1.ipynb` ~ `homework8.ipynb` - 各单元作业
- `2homework1.ipynb` - 额外作业

### 不平衡分类专题

包含完整的类别不平衡问题分析流程：
- 数据探索与可视化
- 基准模型建立
- 特征标准化
- 超参数调优
- 类别权重调整
- 学习曲线分析

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