# Instalador do J.A.R.V.I.S. (Windows 10/11). Rode pelo instalar.bat (duplo clique).
# Faz: confere/instala Python e Git (sem precisar de administrador, pelo winget), cria o ambiente (.venv),
# instala as bibliotecas, cria o atalho "Jarvis" na área de trabalho e abre o Jarvis. O resto (chave do Groq,
# ouvido de ativação, modelo local…) o assistente de primeira vez resolve DENTRO do Jarvis, com barra de progresso.
param([switch]$Teste, [int]$Porta = 0)   # -Teste: não cria atalho nem abre (pra testar numa pasta separada)
$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
Set-Location $raiz
function Passo($t) { Write-Host ""; Write-Host "==> $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "    ok: $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "    atenção: $t" -ForegroundColor Yellow }
function TemWinget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }
function AtualizarPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}

Write-Host "J.A.R.V.I.S. - instalação" -ForegroundColor Cyan
Write-Host "Pasta: $raiz"

# ---------------------------------------------------------------- Python 3.11+
Passo "Python"
function Py([string]$cmd) {
    # "py -3.12" → exe "py" + argumento "-3.12"; "python" → só o exe
    $partes = $cmd.Split(' ')
    $resto = @(); if ($partes.Length -gt 1) { $resto = $partes[1..($partes.Length - 1)] }
    return @{ exe = $partes[0]; args = $resto }
}
function AcharPython {
    foreach ($c in @('py -3.13', 'py -3.12', 'py -3.11', 'python')) {
        try {
            $p = Py $c
            $v = & $p.exe @($p.args + @('-c', "import sys; print('%d.%d' % sys.version_info[:2])")) 2>$null
            if ($v -and [version]$v -ge [version]'3.11') { return $c }
        } catch {}
    }
    return $null
}
$py = AcharPython
if (-not $py) {
    if (TemWinget) {
        Write-Host "    instalando o Python 3.13 (só pro seu usuário, sem administrador)..."
        winget install -e --id Python.Python.3.13 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Host
        AtualizarPath
        $py = AcharPython
    }
    if (-not $py) {
        Aviso "não consegui instalar o Python sozinho. Baixe em https://www.python.org/downloads/ (marque 'Add to PATH') e rode o instalar.bat de novo."
        Start-Process "https://www.python.org/downloads/"
        Read-Host "Enter pra sair"; exit 1
    }
}
Ok "Python ($py)"

# ---------------------------------------------------------------- Git (atualizações)
Passo "Git (pra receber atualizações)"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (TemWinget) {
        winget install -e --id Git.Git --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Host
        AtualizarPath
    }
}
if (Get-Command git -ErrorAction SilentlyContinue) { Ok "Git" } else { Aviso "sem Git: o Jarvis funciona, só não se atualiza sozinho (https://git-scm.com/download/win)" }

# ---------------------------------------------------------------- navegador
Passo "Navegador"
$navs = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
          "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe")
$nav = $navs | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($nav) { Ok $nav } else { Aviso "nem Chrome nem Edge: instale o Chrome (https://www.google.com/chrome/)" }

# ---------------------------------------------------------------- ambiente e bibliotecas
Passo "Ambiente do Jarvis (.venv) e bibliotecas (alguns minutos na primeira vez)"
if (-not (Test-Path "$raiz\.venv\Scripts\python.exe")) {
    $p = Py $py
    & $p.exe @($p.args + @('-m', 'venv', "$raiz\.venv"))
}
& "$raiz\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$raiz\.venv\Scripts\python.exe" -m pip install -r "$raiz\requirements.txt"
if ($LASTEXITCODE -ne 0) { Aviso "o pip reclamou de algo acima; o assistente do Jarvis tenta de novo"; } else { Ok "bibliotecas" }

# ---------------------------------------------------------------- config deste PC (o assistente pergunta o resto)
& "$raiz\.venv\Scripts\python.exe" -c "import primeiro_uso"
if ($Porta -gt 0) {  # (pelo Python: o PowerShell 5 grava UTF-8 com BOM e o Python não lê)
    & "$raiz\.venv\Scripts\python.exe" -c "import json,pathlib; p=pathlib.Path('config.json'); c=json.loads(p.read_text(encoding='utf-8')); c['porta']=$Porta; p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf-8')"
}
Ok "config.json deste PC"

if ($Teste) { Write-Host ""; Ok "instalação de teste concluída (sem atalho e sem abrir)"; exit 0 }

# ---------------------------------------------------------------- atalho e abrir
Passo "Atalho na área de trabalho"
$atalho = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Jarvis.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($atalho)
$s.TargetPath = "$raiz\.venv\Scripts\pythonw.exe"
$s.Arguments = '-c "import palmas; palmas.abrir_jarvis()"'
$s.WorkingDirectory = $raiz
$s.IconLocation = "$raiz\web\marca\jarvis.ico"
$s.Save()
Ok $atalho

Passo "Abrindo o Jarvis"
Start-Process -FilePath "$raiz\.venv\Scripts\pythonw.exe" -ArgumentList "`"$raiz\server.py`"" -WorkingDirectory $raiz
Start-Process -FilePath "$raiz\.venv\Scripts\pythonw.exe" -ArgumentList "`"$raiz\palmas.py`"" -WorkingDirectory $raiz
Start-Sleep -Seconds 6
Start-Process -FilePath "$raiz\.venv\Scripts\pythonw.exe" -ArgumentList '-c "import palmas; palmas.abrir_jarvis()"' -WorkingDirectory $raiz
Write-Host ""
Write-Host "Pronto! O Jarvis abriu. Na primeira vez ele mostra o assistente de configuração (chave do Groq, downloads, etc.)." -ForegroundColor Green
Start-Sleep -Seconds 4
