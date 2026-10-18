@echo off
title Alumni AI Server
echo ========================================================
echo   Alumni AI - Advanced AI System
echo   Startup & Founder of Team Alum, Sudarshan & Soham
echo ========================================================
echo.
cd /d "%~dp0"
echo Starting Alumni AI Backend on http://0.0.0.0:8000 ...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
