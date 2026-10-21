# Fecha e abre o Jarvis de novo (depois de uma atualização, ou pelo botão das Configurações).
# Só mexe nos processos DESTA pasta: o servidor, o ouvido de fundo e as janelas do Chrome/Edge com o perfil do Jarvis.
param([int]$Atraso = 0)
$ErrorActionPreference = 'SilentlyContinue'
$raiz = $PSScriptRoot
if ($Atraso -gt 0) { Start-Sleep -Seconds $Atraso }
$pasta = [regex]::Escape($raiz)
Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -match 'pythonw?\.exe' -and $_.CommandLine -match "$pasta\\(server|palmas)\.py") -or
    ($_.Name -match '^(chrome|msedge)\.exe$' -and $_.CommandLine -match "$pasta\\\.perfil-(navegador|extensao)")
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 2
$pythonw = Join-Path $raiz '.venv\Scripts\pythonw.exe'
Start-Process -FilePath $pythonw -ArgumentList "`"$raiz\server.py`"" -WorkingDirectory $raiz
Start-Process -FilePath $pythonw -ArgumentList "`"$raiz\palmas.py`"" -WorkingDirectory $raiz
$porta = (Get-Content (Join-Path $raiz 'config.json') -Raw | ConvertFrom-Json).porta
if (-not $porta) { $porta = 8765 }
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try { Invoke-RestMethod -Uri "http://127.0.0.1:$porta/api/status" -TimeoutSec 2 | Out-Null; break } catch {}
}
Start-Process -FilePath $pythonw -ArgumentList '-c "import palmas; palmas.abrir_jarvis()"' -WorkingDirectory $raiz
