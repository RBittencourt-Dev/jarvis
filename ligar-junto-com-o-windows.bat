@echo off
rem Faz o Jarvis ligar sozinho quando o Windows inicia (fica esperando as palmas).
rem Para desfazer: apague "Jarvis.lnk" em shell:startup.
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Jarvis.lnk'); $s.TargetPath='%~dp0ligar-jarvis.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.IconLocation='%~dp0web\marca\jarvis.ico,0'; $s.Save()"
echo Pronto: o Jarvis vai ligar junto com o Windows.
pause
