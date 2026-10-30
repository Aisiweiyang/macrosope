@echo off
setlocal
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m streamlit run "%~dp0app.py" %*
if errorlevel 1 pause
