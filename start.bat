@echo off
cd /d "%~dp0"
echo Stopping old processes on 8000 and 5500...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5500') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul

start "CrackTheDeck Backend" cmd /k "cd /d %~dp0crackthedeck-backend\crackthedeck-backend && run_backend.bat"
timeout /t 3 /nobreak >nul

echo.
echo Frontend: http://localhost:5500
echo Backend:  http://localhost:8000 (in other window)
echo.
cd crackthedeck-deploy
python -m http.server 5500
pause
