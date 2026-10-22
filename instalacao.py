"""Instalação em outro PC, assistente de primeira vez e atualizações.

- itens(): o que o Jarvis precisa e se já tem (bibliotecas, navegador, microfone, chave do Groq, ouvido de ativação,
  Ollama + modelo local, Node, Git). Cada item diz o tamanho e se dá pra instalar sozinho ("auto"), se é só colar
  uma chave ("chave") ou se precisa instalar à mão ("manual", com o link oficial).
- instalar(id): baixa/instala em segundo plano com progresso, velocidade e log. Download interrompido continua de
  onde parou (Range no arquivo, e o `ollama pull` já retoma sozinho).
- hardware() + recomendado(): RAM, CPU e GPU (VRAM) → o modelo local que essa máquina aguenta.
- autoinicio(): ligar junto com o Windows (atalho na pasta Inicializar).
- verificar_atualizacao() / atualizar(): git fetch / git pull --ff-only. Os dados dele (memória, chaves, config,
  aprendizados) estão fora do git: atualizar nunca apaga nada. Depois reinicia com reiniciar.ps1.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

import httpx
import psutil

RAIZ = Path(__file__).parent
MARCA = RAIZ / "dados" / "instalacao.json"
DOWNLOADS = RAIZ / "dados" / "downloads"
VOSK_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
VOSK_PASTA = RAIZ / "modelos" / "vosk-model-small-en-us-0.15"
SEM_JANELA = 0x08000000  # CREATE_NO_WINDOW
MODELOS = [  # (nome, tamanho GB, precisa: ("vram", GB) ou ("ram", GB))
    ("qwen3:8b", 5.2, ("vram", 8)), ("qwen3:4b", 2.5, ("vram", 4)), ("qwen2.5:3b", 1.9, ("ram", 12)),
    ("qwen2.5:1.5b", 1.0, ("ram", 7)), ("qwen2.5:0.5b", 0.4, ("ram", 0)),
]
tarefas = {}  # id → {"estado": rodando|ok|erro, "pct": 0-100 ou None, "velocidade": "", "log": [..]}


def _config():
    return json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ máquina

_hw = {}


def hardware():
    """RAM/CPU/GPU. Perguntar ao Windows leva ~4 s: guarda o resultado (a máquina não muda com ele aberto)."""
    if _hw:
        return dict(_hw)
    gpus = []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json"],
                           capture_output=True, text=True, timeout=15, creationflags=SEM_JANELA)
        dados = json.loads(r.stdout or "[]")
        for g in dados if isinstance(dados, list) else [dados]:
            gpus.append({"nome": g.get("Name", ""), "vram_gb": round((g.get("AdapterRAM") or 0) / 2**30, 1)})
    except Exception:
        pass
    if shutil.which("nvidia-smi"):  # AdapterRAM trava em 4 GB; a NVIDIA diz o valor certo
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=10, creationflags=SEM_JANELA)
            gpus = [{"nome": l.split(",")[0].strip(), "vram_gb": round(int(l.split(",")[1]) / 1024, 1)}
                    for l in r.stdout.strip().splitlines() if "," in l] or gpus
        except Exception:
            pass
    cpu = platform.processor()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                           capture_output=True, text=True, timeout=10, creationflags=SEM_JANELA)
        cpu = r.stdout.strip() or cpu
    except Exception:
        pass
    dedicadas = [g for g in gpus if re.search(r"nvidia|geforce|rtx|gtx|radeon rx|arc a", g["nome"], re.I)]
    _hw.update({"cpu": cpu, "nucleos": psutil.cpu_count(logical=True), "ram_gb": round(psutil.virtual_memory().total / 2**30),
                "gpus": gpus, "vram_gb": max((g["vram_gb"] for g in dedicadas), default=0),
                "disco_livre_gb": round(psutil.disk_usage(str(RAIZ.anchor)).free / 2**30)})
    return dict(_hw)


def recomendado(hw=None):
    hw = hw or hardware()
    for nome, tamanho, (tipo, minimo) in MODELOS:
        if (tipo == "vram" and hw["vram_gb"] >= minimo) or (tipo == "ram" and hw["ram_gb"] >= minimo):
            return {"modelo": nome, "tamanho_gb": tamanho,
                    "porque": (f"placa de vídeo com {hw['vram_gb']} GB" if tipo == "vram"
                               else f"{hw['ram_gb']} GB de RAM, sem placa de vídeo dedicada")}
    return {"modelo": "qwen2.5:0.5b", "tamanho_gb": 0.4, "porque": "máquina leve"}


# ------------------------------------------------------------------ o que falta

def _internet():
    try:
        httpx.get("https://api.groq.com", timeout=4)
        return True
    except Exception:
        return False


def _ollama_modelos():
    try:
        return [m["name"] for m in httpx.get(_config()["ollama_url"] + "/api/tags", timeout=3).json().get("models", [])]
    except Exception:
        return None


def _libs_faltando():
    import importlib.util
    nomes = {"fastapi": "fastapi", "uvicorn": "uvicorn", "httpx": "httpx", "edge_tts": "edge-tts", "vosk": "vosk",
             "sounddevice": "sounddevice", "psutil": "psutil", "numpy": "numpy", "PIL": "pillow", "openpyxl": "openpyxl",
             "sgp4": "sgp4", "uiautomation": "uiautomation", "mcp": "mcp", "feedparser": "feedparser"}
    return [pacote for modulo, pacote in nomes.items() if importlib.util.find_spec(modulo) is None]


def _navegador():
    import navegadores
    return navegadores.executavel("chrome") or navegadores.executavel("edge")


def itens():
    import cerebro
    net = _internet()
    modelos = _ollama_modelos()
    rec = recomendado()
    escolhido = _config().get("modelo") or rec["modelo"]
    libs = _libs_faltando()
    try:
        import sounddevice as sd
        mic = sd.query_devices(kind="input")["name"]
    except Exception:
        mic = None
    navegador = _navegador()
    lista = [
        {"id": "internet", "nome": "Internet", "ok": net, "tipo": "info", "obrigatorio": False,
         "descricao": "ok" if net else "sem internet agora: dá pra continuar depois (os downloads retomam de onde pararam)"},
        {"id": "bibliotecas", "nome": "Bibliotecas do Jarvis", "ok": not libs, "tipo": "auto", "obrigatorio": True,
         "tamanho": "~150 MB", "descricao": "todas instaladas" if not libs else "faltando: " + ", ".join(libs)},
        {"id": "navegador", "nome": "Navegador (Chrome ou Edge)", "ok": bool(navegador), "tipo": "manual", "obrigatorio": True,
         "link": "https://www.google.com/chrome/", "descricao": str(navegador) if navegador else "a tela do Jarvis abre num Chrome/Edge"},
        {"id": "microfone", "nome": "Microfone", "ok": bool(mic), "tipo": "manual", "obrigatorio": False,
         "link": "ms-settings:privacy-microphone", "descricao": mic or "nenhum microfone achado (dá pra digitar)"},
        {"id": "groq", "nome": "Chave do Groq (cérebro rápido + ouvido)", "ok": bool(cerebro.chave("groq")), "tipo": "chave",
         "obrigatorio": True, "link": "https://console.groq.com/keys",
         "descricao": "configurada" if cerebro.chave("groq") else "grátis: entre no site, crie a chave (gsk_…) e cole aqui"},
        {"id": "vosk", "nome": "Ouvido do “Jarvis” (palavra de ativação)", "ok": VOSK_PASTA.exists(), "tipo": "auto",
         "obrigatorio": True, "tamanho": "40 MB", "descricao": "baixado" if VOSK_PASTA.exists() else "modelo offline Vosk"},
        {"id": "ollama", "nome": "Ollama (cérebro offline)", "ok": modelos is not None, "tipo": "manual",
         "obrigatorio": False, "link": "https://ollama.com/download/windows", "tamanho": "~1 GB",
         "descricao": "rodando" if modelos is not None else "sem ele, sem internet o Jarvis não pensa (com internet usa o Groq)"},
        {"id": "modelo", "nome": f"Modelo local {escolhido}", "ok": bool(modelos and escolhido in modelos), "tipo": "auto",
         "obrigatorio": False, "tamanho": f"{next((t for n, t, _ in MODELOS if n == escolhido), rec['tamanho_gb'])} GB",
         "depende": "ollama", "descricao": f"recomendado pra esta máquina: {rec['modelo']} ({rec['porque']})"},
        {"id": "git", "nome": "Git (pra receber atualizações)", "ok": bool(shutil.which("git")), "tipo": "manual",
         "obrigatorio": False, "link": "https://git-scm.com/download/win", "descricao": "ok" if shutil.which("git") else "sem ele, sem atualização automática"},
        {"id": "node", "nome": "Node.js (conectores MCP locais)", "ok": bool(shutil.which("node")), "tipo": "manual",
         "obrigatorio": False, "link": "https://nodejs.org", "descricao": "ok" if shutil.which("node") else "só pra servidores MCP do tipo programa"},
    ]
    for item in lista:
        if item["id"] in tarefas:
            item["tarefa"] = tarefas[item["id"]]
    return lista


def concluida():
    try:
        return json.loads(MARCA.read_text(encoding="utf-8")).get("concluida", False)
    except (OSError, ValueError):
        return False


def marcar_concluida():
    MARCA.parent.mkdir(exist_ok=True)
    MARCA.write_text(json.dumps({"concluida": True, "quando": time.time()}), encoding="utf-8")


def precisa_assistente():
    """Rápido (sem internet, sem hardware): decide na hora se a tela abre com o assistente."""
    if concluida():
        return False
    import cerebro
    return (not _config().get("nome_do_usuario") or not cerebro.chave("groq") or not VOSK_PASTA.exists()
            or bool(_libs_faltando()) or not _navegador())


# ------------------------------------------------------------------ instalar (segundo plano, com progresso)

def _tarefa(id_):
    t = {"estado": "rodando", "pct": 0, "velocidade": "", "log": [], "inicio": time.time()}
    tarefas[id_] = t
    return t


def _log(t, linha):
    t["log"] = (t["log"] + [linha.strip()])[-40:]


def _baixar(url, destino, t):
    """Download com retomada: se já tem parte do arquivo, pede só o resto (Range)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".parcial")
    ja = parcial.stat().st_size if parcial.exists() else 0
    cab = {"Range": f"bytes={ja}-"} if ja else {}
    with httpx.stream("GET", url, headers=cab, timeout=30, follow_redirects=True) as r:
        if r.status_code == 416:  # já estava completo
            parcial.rename(destino)
            return
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0) + (ja if r.status_code == 206 else 0)
        if r.status_code != 206:
            ja = 0
        _log(t, f"baixando {url.rsplit('/', 1)[-1]} ({total / 2**20:.0f} MB)" + (f", continuando de {ja / 2**20:.0f} MB" if ja else ""))
        inicio, feito = time.time(), ja
        with parcial.open("ab" if ja else "wb") as f:
            for pedaco in r.iter_bytes(256 * 1024):
                f.write(pedaco)
                feito += len(pedaco)
                dt = max(0.5, time.time() - inicio)
                t["pct"] = round(100 * feito / total) if total else None
                t["velocidade"] = f"{(feito - ja) / dt / 2**20:.1f} MB/s"
    parcial.replace(destino)


def _vosk(t):
    zipado = DOWNLOADS / "vosk.zip"
    if not zipado.exists():
        _baixar(VOSK_URL, zipado, t)
    _log(t, "descompactando…")
    with zipfile.ZipFile(zipado) as z:
        z.extractall(RAIZ / "modelos")
    zipado.unlink(missing_ok=True)


def _bibliotecas(t):
    t["pct"] = None
    py = RAIZ / ".venv" / "Scripts" / "python.exe"
    py = py if py.exists() else Path(sys.executable)
    proc = subprocess.Popen([str(py), "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=SEM_JANELA)
    for linha in proc.stdout:
        if linha.strip():
            _log(t, linha)
    if proc.wait() != 0:
        raise RuntimeError("o pip falhou (veja o log)")


def _modelo(t):
    nome = _config().get("modelo") or recomendado()["modelo"]
    with httpx.stream("POST", _config()["ollama_url"] + "/api/pull", json={"name": nome, "stream": True}, timeout=None) as r:
        ultimo, ultimo_t = 0, time.time()
        for linha in r.iter_lines():
            if not linha:
                continue
            j = json.loads(linha)
            if j.get("error"):
                raise RuntimeError(j["error"])
            if j.get("total") and j.get("completed") is not None:
                t["pct"] = round(100 * j["completed"] / j["total"])
                agora = time.time()
                if agora - ultimo_t > 1:
                    t["velocidade"] = f"{(j['completed'] - ultimo) / (agora - ultimo_t) / 2**20:.1f} MB/s"
                    ultimo, ultimo_t = j["completed"], agora
            status = j.get("status", "")
            if status and (not t["log"] or not t["log"][-1].startswith(status[:20])):
                _log(t, status)


def instalar(id_):
    if tarefas.get(id_, {}).get("estado") == "rodando":
        return
    fazer = {"vosk": _vosk, "bibliotecas": _bibliotecas, "modelo": _modelo}.get(id_)
    if not fazer:
        return
    t = _tarefa(id_)

    def rodar():
        try:
            fazer(t)
            t.update(estado="ok", pct=100, velocidade="")
            _log(t, "pronto")
        except Exception as e:
            t["estado"] = "erro"
            _log(t, f"erro: {e} — dá pra tentar de novo (continua de onde parou)")
    threading.Thread(target=rodar, daemon=True).start()


# ------------------------------------------------------------------ ligar junto com o Windows

def _atalho_inicio():
    return Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup" / "Jarvis.lnk"


def _alvo_do_atalho(atalho):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"(New-Object -ComObject WScript.Shell).CreateShortcut('{atalho}').TargetPath"],
                           capture_output=True, text=True, timeout=15, creationflags=SEM_JANELA)
        return r.stdout.strip()
    except Exception:
        return ""


CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _comando_de_inicio():
    return f'"{RAIZ / ".venv" / "Scripts" / "pythonw.exe"}" "{RAIZ / "iniciar.py"}"'


def autoinicio(ligar=None):
    """Ligar junto com o Windows, o mais cedo possível: entrada "Executar" do usuário (roda logo no login, antes da
    pasta Inicializar), sem o atraso que o Windows põe nos programas de início, e já abrindo a tela.
    Só mexe no que aponta pra ESTA pasta (outro Jarvis no mesmo PC não é tocado)."""
    import winreg
    atalho = _atalho_inicio()
    atalho_meu = atalho.exists() and Path(_alvo_do_atalho(atalho) or "x").resolve().parent == RAIZ.resolve()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN) as k:
            atual = winreg.QueryValueEx(k, "Jarvis")[0]
    except OSError:
        atual = ""
    meu = str(RAIZ).lower() in atual.lower()
    if ligar is None:
        return meu or atalho_meu
    if atalho_meu:
        atalho.unlink(missing_ok=True)  # o jeito antigo (pasta Inicializar, mais lento): sai pra não ligar duas vezes
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN, 0, winreg.KEY_SET_VALUE) as k:
        if ligar:
            winreg.SetValueEx(k, "Jarvis", 0, winreg.REG_SZ, _comando_de_inicio())
        elif meu:
            winreg.DeleteValue(k, "Jarvis")
    if ligar:  # tira o atraso de ~10 s dos programas de início (só deste usuário)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize") as k:
            winreg.SetValueEx(k, "StartupDelayInMSec", 0, winreg.REG_DWORD, 0)
    return bool(ligar)


# ------------------------------------------------------------------ atualizações (GitHub)

def _git(*args, timeout=60):
    r = subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, creationflags=SEM_JANELA)
    return r.returncode, (r.stdout + r.stderr).strip()


def verificar_atualizacao():
    if not shutil.which("git") or not (RAIZ / ".git").exists():
        return {"ok": False, "texto": "Sem Git nesta pasta: instale o Git e baixe o Jarvis com git clone pra receber atualizações."}
    codigo, saida = _git("fetch", "--quiet")
    if codigo != 0:
        return {"ok": False, "texto": f"Não consegui falar com o GitHub: {saida[:160]}"}
    _, n = _git("rev-list", "--count", "HEAD..@{u}")
    n = int(n) if n.isdigit() else 0
    _, novidades = _git("log", "--format=%s", "HEAD..@{u}")
    return {"ok": True, "novas": n, "novidades": [l for l in novidades.splitlines() if l][:15],
            "texto": f"{n} atualização(ões) disponível(is)." if n else "O Jarvis já está na versão mais nova."}


def atualizar():
    antes = _git("rev-parse", "HEAD")[1]
    codigo, saida = _git("pull", "--ff-only", timeout=180)
    if codigo != 0:
        return {"ok": False, "texto": f"A atualização não entrou: {saida[:300]}"}
    _, mudou = _git("diff", "--name-only", antes, "HEAD")
    if "requirements.txt" in mudou:  # bibliotecas novas: instala antes de reiniciar
        t = _tarefa("bibliotecas")
        try:
            _bibliotecas(t)
            t.update(estado="ok", pct=100)
        except Exception as e:
            return {"ok": False, "texto": f"Atualizei o código, mas as bibliotecas falharam: {e}"}
    return {"ok": True, "texto": "Atualizado.", "arquivos": mudou.splitlines()}


def reiniciar(atraso=0):
    """Fecha e abre o Jarvis de novo (reiniciar.ps1), sem segurar quem pediu."""
    script = RAIZ / "reiniciar.ps1"
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(script),
                      "-Atraso", str(int(atraso))], cwd=RAIZ, creationflags=0x00000008 | SEM_JANELA)  # DETACHED
