@echo off
rem Liga o servidor e o ouvido das palmas, os dois escondidos.
cd /d "%~dp0"
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0server.py"
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0palmas.py"
echo Jarvis ligado. Bata duas palmas para abrir.
timeout /t 3 >nul
