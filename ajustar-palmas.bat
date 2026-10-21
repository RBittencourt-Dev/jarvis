@echo off
rem Mostra o volume do microfone. Bata palmas e veja o numero que aparece;
rem a "sensibilidade" no config.json precisa ficar abaixo dele e acima do barulho normal.
cd /d "%~dp0"
".venv\Scripts\python.exe" palmas.py --medir
