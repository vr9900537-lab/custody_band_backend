@echo off
cd /d "%~dp0backend"
echo ===================================================
echo Starting Custody Watch Platform Backend...
echo ===================================================
if exist "..\venv\Scripts\python.exe" (
    "..\venv\Scripts\python.exe" run_server.py
) else (
    python run_server.py
)
pause

