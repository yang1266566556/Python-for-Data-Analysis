# Python for Data Analysis

This folder is configured for Jupyter Notebook with a dedicated Conda environment.

## Environment

- Project folder: `D:\Python for Data Analysis`
- Conda environment: `pda312`
- Python interpreter: `D:\anaconda\envs\pda312\python.exe`

## Start Jupyter

Run this in PowerShell:

```powershell
cd "D:\Python for Data Analysis"
.\start-jupyter.ps1
```

You can also start it manually:

```powershell
D:\anaconda\condabin\conda.bat run -n pda312 jupyter notebook --notebook-dir "D:\Python for Data Analysis\notebooks" --ServerApp.use_redirect_file=False
```

The launchers open the local HTTP address directly to avoid browser access errors
with Jupyter's temporary `jpserver-*-open.html` redirect file. Keep the launcher
window open while using Jupyter. If the browser does not open, use the HTTP URL
printed in that window (including its token, if present).

## Recreate The Environment

```powershell
D:\anaconda\condabin\conda.bat env create -f environment.yml
```
