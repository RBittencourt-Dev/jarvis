@echo off
rem Desliga o servidor e o ouvido das palmas.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*Jarvis*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Jarvis desligado.
timeout /t 2 >nul
