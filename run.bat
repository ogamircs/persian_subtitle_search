@echo off
title Persian Subtitle Search

:: Change to script directory
cd /d "%~dp0"

:: Activate virtual environment
call .venv311\Scripts\activate.bat

:: Open browser after short delay (in background)
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8501"

:: Run Streamlit app
streamlit run src/ui/app.py --server.headless=true
