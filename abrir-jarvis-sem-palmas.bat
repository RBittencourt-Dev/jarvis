@echo off
rem Abre a janela direto, sem palmas (liga o servidor se precisar).
cd /d "%~dp0"
".venv\Scripts\python.exe" -c "import palmas; palmas.abrir_jarvis()"
