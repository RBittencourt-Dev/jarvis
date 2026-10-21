"""Mãos no PC, parte 2: arquivos (com desfazer), área de transferência, print, brilho, janelas e clicar pelo NOME.

Clicar por coordenada com modelo de visão erra a posição (e no CPU levaria dezenas de segundos), por isso o
clique aqui é pela árvore de acessibilidade do Windows (UI Automation): "clica em Salvar" acha o botão
chamado Salvar na janela da frente e clica nele, como um leitor de tela faria.

Tudo que mexe em arquivo anota no diário (registro.py) como desfazer: "desfaz isso" volta.
Apagar NUNCA apaga de vez: vai pra lixeira (e pede o "sim" dele antes, pelo servidor).
"""
import ctypes
import json
import os
import shutil
import subprocess
import time
from ctypes import wintypes as w
from datetime import datetime
from pathlib import Path

import registro

RAIZ = Path(__file__).parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
PASTA_PRINTS = Path.home() / "Pictures" / "Jarvis"


def _permitido(caminho: str) -> Path:
    p = Path(os.path.expandvars(caminho)).expanduser().resolve()
    bases = [Path(os.path.expandvars(b)).expanduser().resolve() for b in CONFIG["pastas_permitidas"]]
    if not any(p == b or b in p.parents for b in bases):
        raise PermissionError(f"Fora das pastas liberadas: {p}")
    nome = p.name.lower()
    if any(nome == x or nome.endswith(x) for x in CONFIG["arquivos_proibidos"]):
        raise PermissionError("Esse arquivo guarda senha ou chave; não mexo.")
    return p


# ------------------------------------------------------------------ arquivos

def para_lixeira(caminho):
    """Manda pra lixeira do Windows (dá pra recuperar), nunca apaga de vez."""
    p = str(Path(caminho).resolve())
    comando = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
               f"$p = '{p.replace(chr(39), chr(39) * 2)}'; "
               "if (Test-Path -LiteralPath $p -PathType Container) "
               "{ [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin') } "
               "else { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin') }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", comando], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200] or "falhou")


def mover_arquivo(origem: str, destino: str):
    """Move (ou renomeia) um arquivo ou pasta. Se o destino for uma pasta existente, vai pra dentro dela."""
    de, para = _permitido(origem), _permitido(destino)
    if not de.exists():
        return f"Não achei {de}."
    if para.is_dir():
        para = para / de.name
    if para.exists():
        return f"Já existe {para}; não sobrescrevo."
    para.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(de), str(para))
    registro.anotar(f"mover {de} → {para}", "feito", ["mover_arquivo"], desfazer={"tipo": "mover", "de": str(de), "para": str(para)},
                    tipo="acao")
    return f"Movi para {para}. (Dá pra desfazer.)"


def renomear_arquivo(caminho: str, novo_nome: str):
    de = _permitido(caminho)
    return mover_arquivo(str(de), str(de.with_name(novo_nome)))


def copiar_arquivo(origem: str, destino: str):
    de, para = _permitido(origem), _permitido(destino)
    if not de.exists():
        return f"Não achei {de}."
    if para.is_dir():
        para = para / de.name
    if para.exists():
        return f"Já existe {para}; não sobrescrevo."
    para.parent.mkdir(parents=True, exist_ok=True)
    (shutil.copytree if de.is_dir() else shutil.copy2)(str(de), str(para))
    registro.anotar(f"copiar {de} → {para}", "feito", ["copiar_arquivo"], desfazer={"tipo": "apagar", "caminho": str(para)},
                    tipo="acao")
    return f"Copiei para {para}."


def criar_pasta(caminho: str):
    p = _permitido(caminho)
    if p.exists():
        return f"{p} já existe."
    p.mkdir(parents=True)
    registro.anotar(f"criar pasta {p}", "feito", ["criar_pasta"], desfazer={"tipo": "apagar", "caminho": str(p)}, tipo="acao")
    return f"Criei a pasta {p}."


def apagar_arquivo(caminho: str):
    """Manda pra lixeira. O servidor pede o "sim" antes (é ação destrutiva)."""
    p = _permitido(caminho)
    if not p.exists():
        return f"Não achei {p}."
    para_lixeira(p)
    registro.anotar(f"apagar {p}", "mandei pra lixeira", ["apagar_arquivo"], tipo="acao")
    return f"Mandei {p.name} pra lixeira (dá pra recuperar de lá)."


def procurar_arquivo(nome: str, pasta: str = ""):
    """Acha arquivos pelo nome (parte do nome serve) nas pastas liberadas. Até 25 resultados."""
    bases = [_permitido(pasta)] if pasta else [Path(os.path.expandvars(b)).expanduser() for b in CONFIG["pastas_permitidas"]]
    alvo = nome.lower().strip("* ")
    pular = {"node_modules", ".git", ".next", ".venv", "venv", "__pycache__", "dist", "build", ".perfil-navegador", ".perfil-extensao"}
    achados = []
    for base in bases:
        for raiz, dirs, arquivos in os.walk(base):
            dirs[:] = [d for d in dirs if d not in pular and not d.startswith(".")]
            for a in [*dirs, *arquivos]:
                if alvo in a.lower():
                    achados.append(os.path.join(raiz, a))
                    if len(achados) >= 25:
                        return "\n".join(achados)
    return "\n".join(achados) or "Não achei nenhum arquivo com esse nome."


# ------------------------------------------------------------------ área de transferência

def area_de_transferencia(acao: str = "ler", texto: str = ""):
    """acao 'ler' devolve o que está copiado; 'escrever' copia o texto."""
    if acao.startswith("escrev") or acao.startswith("copi"):
        subprocess.run(["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"], input=texto, text=True,
                       encoding="utf-8", timeout=10)
        return "Copiei pra área de transferência."
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=10)
    conteudo = r.stdout.strip()
    return conteudo[:4000] if conteudo else "A área de transferência está vazia (ou tem imagem)."


# ------------------------------------------------------------------ print

def print_da_tela(tela: str = "todas"):
    """Salva um print em Imagens\\Jarvis e devolve o caminho (a tela do Jarvis mostra a imagem)."""
    import telas
    from PIL import ImageGrab
    PASTA_PRINTS.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA_PRINTS / f"print {datetime.now():%Y-%m-%d %H-%M-%S}.png"
    if tela in ("esta", "outra"):
        m = telas.monitor(tela)
        x, y, larg, alt = m["area"]
        img = ImageGrab.grab(bbox=(x, y, x + larg, y + alt), all_screens=True)
    else:
        img = ImageGrab.grab(all_screens=True)
    img.save(arquivo)
    return f"Print salvo em {arquivo}"


# ------------------------------------------------------------------ brilho (DDC/CI no monitor externo; WMI no notebook)

class _MONITOR(ctypes.Structure):
    _fields_ = [("hPhysicalMonitor", w.HANDLE), ("szPhysicalMonitorDescription", w.WCHAR * 128)]


def _monitores_fisicos():
    u, dxva = ctypes.windll.user32, ctypes.windll.dxva2
    alcas = []
    PROC = ctypes.WINFUNCTYPE(w.BOOL, w.HMONITOR, w.HDC, ctypes.POINTER(w.RECT), w.LPARAM)

    def cada(hmon, *_):
        n = w.DWORD()
        if dxva.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(n)) and n.value:
            arr = (_MONITOR * n.value)()
            if dxva.GetPhysicalMonitorsFromHMONITOR(hmon, n.value, arr):
                alcas.extend(arr)
        return True
    u.EnumDisplayMonitors(None, None, PROC(cada), 0)
    return alcas


def brilho(nivel: str = ""):
    """nivel: 0-100, '+10', '-10' ou vazio (só diz o atual)."""
    dxva = ctypes.windll.dxva2
    mons = _monitores_fisicos()
    feitos, atual = 0, None
    for m in mons:
        mn, cur, mx = w.DWORD(), w.DWORD(), w.DWORD()
        if not dxva.GetMonitorBrightness(m.hPhysicalMonitor, ctypes.byref(mn), ctypes.byref(cur), ctypes.byref(mx)):
            continue
        atual = round(100 * (cur.value - mn.value) / max(1, mx.value - mn.value))
        if nivel:
            s = str(nivel).strip().replace("%", "")
            alvo = atual + int(s) if s[0] in "+-" else int(s)
            alvo = max(0, min(100, alvo))
            if dxva.SetMonitorBrightness(m.hPhysicalMonitor, mn.value + round(alvo * (mx.value - mn.value) / 100)):
                feitos += 1
    if mons:
        dxva.DestroyPhysicalMonitors(len(mons), (_MONITOR * len(mons))(*mons))
    if feitos:
        return f"Brilho ajustado em {feitos} monitor(es)."
    if atual is not None and not nivel:
        return f"Brilho atual: {atual}%."
    # notebook: WMI
    if nivel:
        s = str(nivel).strip().replace("%", "")
        cmd = ("$m = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness; "
               f"$alvo = {('$m.CurrentBrightness ' + s[0] + ' ' + s[1:]) if s[0] in '+-' else s}; "
               "$alvo = [Math]::Max(0,[Math]::Min(100,$alvo)); "
               "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
               "Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{Timeout=1; Brightness=[byte]$alvo} | Out-Null; 'ok'")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=15)
        if "ok" in r.stdout:
            return "Brilho ajustado."
    return "Esse monitor não aceita mudar o brilho pelo PC (falta DDC/CI ligado no menu do monitor)."


# ------------------------------------------------------------------ janelas e clique pelo nome

def listar_janelas():
    import telas
    saida = []
    for hwnd in telas._janelas_em_ordem():
        t = telas._titulo(hwnd)
        if t and t not in ("Program Manager", "Windows Input Experience") and not t.startswith("J.A.R.V.I.S."):
            saida.append(t)
    return "\n".join(saida[:30]) or "Nenhuma janela aberta."


def clicar_em(nome: str, janela: str = ""):
    """Clica no botão/link/item chamado `nome` na janela da frente (ou na janela cujo título contém `janela`)."""
    import uiautomation as auto
    import telas
    import olhos_e_maos
    alvo_hwnd = None
    if janela:
        for hwnd in telas._janelas_em_ordem():
            if janela.lower() in telas._titulo(hwnd).lower() and not telas._titulo(hwnd).startswith("J.A.R.V.I.S."):
                alvo_hwnd = hwnd
                break
        if not alvo_hwnd:
            return f"Não achei janela com '{janela}' no título."
        telas._para_frente(alvo_hwnd)
    else:
        alvo_hwnd = olhos_e_maos.focar_janela_dele()
    if not alvo_hwnd:
        return "Não achei a janela pra clicar."
    time.sleep(0.25)
    raiz = auto.ControlFromHandle(alvo_hwnd)
    procurado = nome.lower().strip()
    melhor = None
    for controle, _ in auto.WalkControl(raiz, maxDepth=25):
        n = (controle.Name or "").strip().lower()
        if not n:
            continue
        if n == procurado:
            melhor = controle
            break
        if procurado in n and (melhor is None or len(n) < len(melhor.Name)):
            melhor = controle
    if not melhor:
        return f"Não achei nada chamado '{nome}' nessa janela."
    try:
        padrao = melhor.GetInvokePattern()
        if padrao:
            padrao.Invoke()
        else:
            melhor.Click(simulateMove=False)
    except Exception:
        melhor.Click(simulateMove=False)
    return f"Cliquei em '{melhor.Name}'."
