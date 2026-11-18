@echo off
echo ========================================
echo   StockShield 2.0 - Backend Server
echo ========================================
echo.
cd /d "%~dp0"
set PYTHONPATH=src

if exist "%~dp0.venv\Scripts\uvicorn.exe" (
    echo Using virtual environment at .venv...
    "%~dp0.venv\Scripts\uvicorn.exe" stockshield.api.main:app --app-dir src --host 0.0.0.0 --port 8000 --reload
) else (
    echo Using system uvicorn with --app-dir src...
    uvicorn stockshield.api.main:app --app-dir src --host 0.0.0.0 --port 8000 --reload
)
pause
