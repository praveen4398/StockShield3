@echo off
echo ========================================
echo   StockShield 2.0 - Frontend Server
echo ========================================
echo.
echo Starting frontend on http://localhost:3000
echo.
echo Make sure the backend is running on http://localhost:8000
echo Run from Backend folder: uvicorn stockshield.api.main:app --reload --port 8000
echo.
cd /d "%~dp0"
python -m http.server 3000 --bind 127.0.0.1
pause
