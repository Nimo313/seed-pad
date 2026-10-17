@echo off
cd /d "%~dp0"
python -c "import hid" 2>nul
if errorlevel 1 (
    echo Erster Start: installiere hidapi...
    python -m pip install hidapi
)
python seed_pad.py
pause
