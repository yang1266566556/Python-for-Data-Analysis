$ErrorActionPreference = "Stop"

$conda = "D:\anaconda\condabin\conda.bat"
if (-not (Test-Path $conda)) {
    throw "Conda was not found at D:\anaconda\condabin\conda.bat."
}

Set-Location "D:\Python for Data Analysis"
& $conda run -n pda312 --no-capture-output jupyter notebook --notebook-dir "D:\Python for Data Analysis\notebooks"
