"""Run the standalone R quality figure script from the specified Python kernel."""

from railway_project_io import read_project_json
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from stage1_collect import ROOT, TZ, write_json
from stage1d_audit import RUN


def run(audit_dir, actor="user"):
    if actor not in ("user", "assistant"):
        raise ValueError("Invalid actor")
    audit_file = Path(audit_dir) / "audit_summary.json"
    verified = read_project_json(audit_file)
    if not verified["passed"] or verified["source_run"] != RUN:
        raise ValueError("A complete matching audit is required before plotting")
    rscript = Path(r"D:\R\R-4.6.0\bin\Rscript.exe")
    if not rscript.is_file():
        raise FileNotFoundError("Rscript not found at the verified location")
    out = ROOT / "figures" / (actor + "_stage1d_quality_" + datetime.now(TZ).strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    script = ROOT / "scripts/stage1d_quality_plots.R"
    # Remove stale POSIX locale overrides only in this child process.
    environment = dict(os.environ)
    for key in ("LC_ALL", "LC_CTYPE", "LC_COLLATE", "LC_MONETARY", "LC_TIME"):
        environment.pop(key, None)
    result = subprocess.run([str(rscript), "--vanilla", "--encoding=UTF-8", str(script), str(ROOT), str(Path(audit_dir)), str(out)],
                            capture_output=True, encoding="utf-8", errors="replace", env=environment)
    (out / "R_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out / "R_stderr.txt").write_text(result.stderr, encoding="utf-8")
    manifest = dict(actor=actor, executed_at=datetime.now(TZ).isoformat(), audit_dir=str(audit_dir),
                    returncode=result.returncode, source_script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
                    png_files=[str(p) for p in sorted(out.glob("*.png"))], pdf_files=[str(p) for p in sorted(out.glob("*.pdf"))],
                    helper_note="r-academic-plots helper reused; original private reference-library paths unavailable; titles retained per assignment")
    write_json(out / "plot_manifest.json", manifest)
    if result.returncode or len(manifest["png_files"]) != 3 or len(manifest["pdf_files"]) != 3 or "QUALITY_PLOTS_COMPLETED" not in result.stdout:
        raise RuntimeError(f"R plotting did not complete; retain diagnostics at {out}. {result.stderr[-1000:]}")
    return dict(output_dir=str(out), **manifest)
