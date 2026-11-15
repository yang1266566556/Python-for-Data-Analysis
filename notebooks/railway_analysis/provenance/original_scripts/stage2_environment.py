"""User-run, approved UMAP installation with existing analysis packages pinned."""
import importlib.metadata as metadata
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[1]
PIN_PACKAGES=["numpy","scipy","scikit-learn","pandas","matplotlib"]


def install_umap_user():
    if Path(sys.executable).resolve()!=Path(r"D:\anaconda\envs\pda312\python.exe").resolve():raise ValueError("Use pda312")
    before={p:metadata.version(p) for p in PIN_PACKAGES}
    try:
        version=metadata.version("umap-learn")
        print("umap-learn已安装：",version,"；未运行安装。")
        return dict(already_installed=True,version=version,restart_kernel=False)
    except metadata.PackageNotFoundError:pass
    out=ROOT/"environment"/("user_umap_install_"+datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S_%f"));out.mkdir(parents=True)
    constraints=out/"existing_versions_constraints.txt"
    constraints.write_text("\n".join(p+"=="+v for p,v in before.items())+"\n",encoding="utf-8")
    command=[sys.executable,"-m","pip","install","--disable-pip-version-check","--constraint",str(constraints),"umap-learn"]
    (out/"install_plan.json").write_text(json.dumps(dict(user_approved=True,package="umap-learn",dependency_install_expected=True,
        command=command,pinned_existing_versions=before),ensure_ascii=False,indent=2),encoding="utf-8")
    print("正在安装UMAP及其依赖；现有numpy/scipy/sklearn/pandas/matplotlib版本已约束。",flush=True)
    with (out/"pip_output.txt").open("w",encoding="utf-8") as log:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace")
        for line in process.stdout:
            log.write(line);log.flush();print(line,end="",flush=True)
        returncode=process.wait()
    if returncode:raise RuntimeError("UMAP安装未成功；保留日志回传，不移除版本约束。日志："+str(out/"pip_output.txt"))
    after={p:metadata.version(p) for p in PIN_PACKAGES}
    if after!=before:raise RuntimeError("基础分析库版本发生变化，请先回传，暂不继续实验")
    result=dict(already_installed=False,version=metadata.version("umap-learn"),base_versions_unchanged=True,restart_kernel=True,output_dir=str(out))
    (out/"installation_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("安装完成。请重启pda312内核，再从问题2—核心代码1开始。",flush=True)
    return result
