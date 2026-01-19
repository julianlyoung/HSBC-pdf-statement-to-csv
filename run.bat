@echo off
echo ============================================================
echo HSBC Statement PDF to CSV Converter
echo ============================================================
echo.
echo Starting server...
echo.
cd /d "%~dp0"
call venv\Scripts\activate
python app.py
pause
