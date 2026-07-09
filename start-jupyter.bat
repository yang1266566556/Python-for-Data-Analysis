@echo off
cd /d "D:\Python for Data Analysis"
call "D:\anaconda\condabin\conda.bat" run -n pda312 --no-capture-output jupyter notebook --notebook-dir "D:\Python for Data Analysis\notebooks"
pause
