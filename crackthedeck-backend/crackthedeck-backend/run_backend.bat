@echo off
cd /d "%~dp0"
echo Killing old backend on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul
echo Starting backend. Presentations folder: %CD%\presentations
echo Open http://localhost:8000/api/health - must show "build": "no-mock"
python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
