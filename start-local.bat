@echo off
REM CrackTheDeck local: RAG + backend + frontend
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0start-local.ps1"
pause
