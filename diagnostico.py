"""Diagnóstico do Jarvis: verificar a instalação e medir a velocidade dos cérebros.

- saude(): Ollama no ar? modelos baixados? chave da nuvem? ouvido (Vosk)? bibliotecas? disco? índice?
  É o botão "Verificar instalação" das Configurações (e a base do instalador da etapa 13, que fica pra depois).
- benchmark(): tokens por segundo de cada modelo local (sem GPU isso decide tudo) e o tempo até a 1ª palavra da
  nuvem. Escolhe sozinho o modelo local de reserva: o mais esperto que ainda passa de 7 tokens/s; se nenhum
  passar, o mais rápido. Resultado em dados/benchmark.json.
"""
import importlib.util
import json
import platform
import shutil
import time
from pathlib import Path

import httpx
import psutil

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "dados" / "benchmark.json"
# do mais esperto pro mais simples (pra escolher o local)
QUALIDADE = ["qwen3:8b", "qwen3:4b", "gemma3:4b", "qwen2.5:7b", "llama3.1:8b", "qwen2.5:3b", "llama3.2:3b", "qwen3:1.7b",
             "gemma3:1b", "qwen2.5:1.5b"]
MINIMO_TOKS = 7.0


def _config():
    return json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))


def modelos_locais():
    try:
        r = httpx.get(_config()["ollama_url"] + "/api/tags", timeout=4)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return None  # Ollama fora do ar


def saude():
    import cerebro
    itens = []

    def item(nome, ok, detalhe, como=""):
        itens.append({"nome": nome, "ok": bool(ok), "detalhe": detalhe, "como": como})

    item("Python", True, platform.python_version())
    faltando = [m for m in ("fastapi", "uvicorn", "httpx", "edge_tts", "vosk", "sounddevice", "psutil", "numpy", "PIL",
                            "openpyxl", "sgp4", "uiautomation", "mcp") if importlib.util.find_spec(m) is None]
    item("Bibliotecas", not faltando, "todas instaladas" if not faltando else "faltando: " + ", ".join(faltando),
         "pip install -r requirements.txt")
    modelos = modelos_locais()
    item("Ollama (cérebro local)", modelos is not None, f"{len(modelos)} modelos" if modelos is not None else "fora do ar",
         "https://ollama.com/download")
    escolhido = _config().get("modelo")
    if modelos is not None:
        item(f"Modelo local {escolhido}", escolhido in modelos, "baixado" if escolhido in modelos else "não baixado",
             f"ollama pull {escolhido}")
    nuvem = [p for p in cerebro.PROVEDORES if cerebro.chave(p)]
    item("Cérebro na nuvem", bool(nuvem), ", ".join(nuvem) or "sem chave (fica só o local, mais lento)",
         "Configurações → Privacidade → cofre: chave do Groq e/ou do Gemini")
    item("Ouvido (Whisper da Groq)", bool(cerebro.chave("groq")), "ok" if cerebro.chave("groq") else "sem chave do Groq")
    vosk = (RAIZ / "modelos" / "vosk-model-small-en-us-0.15").exists()
    item("Palavra de ativação (Vosk)", vosk, "modelo baixado" if vosk else "falta o modelo",
         "https://alphacephei.com/vosk/models (vosk-model-small-en-us-0.15) em modelos/")
    try:
        import sounddevice as sd
        entrada = sd.query_devices(kind="input")
        item("Microfone", True, entrada["name"])
    except Exception as e:
        item("Microfone", False, str(e)[:80], "Configurações do Windows → Privacidade → Microfone")
    item("Node (conectores MCP locais)", shutil.which("node") is not None, shutil.which("node") or "não instalado",
         "https://nodejs.org")
    livre = psutil.disk_usage(str(RAIZ.anchor)).free / 2**30
    item("Disco", livre > 5, f"{livre:.0f} GB livres")
    mem = psutil.virtual_memory()
    item("Memória", True, f"{mem.total / 2**30:.0f} GB no total, {mem.available / 2**30:.1f} GB livres agora")
    try:
        import indice
        s = indice.situacao()
        item("Índice dos seus arquivos", s["arquivos"] > 0, f"{s['arquivos']} arquivos" + (" (indexando…)" if s["indexando"] else ""))
    except Exception as e:
        item("Índice dos seus arquivos", False, str(e)[:80])
    try:
        httpx.get("https://api.groq.com", timeout=4)
        item("Internet", True, "ok")
    except Exception:
        item("Internet", False, "sem conexão (o Jarvis segue no cérebro local)")
    return {"itens": itens, "maquina": maquina()}


def maquina():
    return {"cpu": platform.processor() or platform.machine(), "nucleos": psutil.cpu_count(logical=True),
            "ram_gb": round(psutil.virtual_memory().total / 2**30), "sistema": f"{platform.system()} {platform.release()}"}


def _medir_local(modelo, url):
    corpo = {"model": modelo, "prompt": "Explique em duas frases o que é um assistente pessoal.", "stream": False,
             "keep_alive": "2m", "options": {"num_predict": 60, "num_ctx": 2048}}
    if modelo.startswith("qwen3"):
        corpo["think"] = False
    httpx.post(url + "/api/generate", json={**corpo, "options": {**corpo["options"], "num_predict": 1}}, timeout=300)  # carrega
    r = httpx.post(url + "/api/generate", json=corpo, timeout=300).json()
    toks = r.get("eval_count", 0) / max(1e-9, r.get("eval_duration", 1) / 1e9)
    primeira = r.get("prompt_eval_duration", 0) / 1e9
    return {"modelo": modelo, "tokens_s": round(toks, 1), "processar_pedido_s": round(primeira, 2)}


def benchmark(escolher=True):
    cfg = _config()
    resultado = {"quando": time.time(), "locais": [], "nuvem": None, "maquina": maquina()}
    for modelo in modelos_locais() or []:
        if "embed" in modelo:
            continue
        try:
            resultado["locais"].append(_medir_local(modelo, cfg["ollama_url"]))
        except Exception as e:
            resultado["locais"].append({"modelo": modelo, "erro": str(e)[:100]})
    try:
        import asyncio
        import cerebro
        if cerebro.nuvem():
            inicio = time.time()
            asyncio.run(cerebro.completar([{"role": "user", "content": "Diga só: ok"}], max_tokens=5))
            resultado["nuvem"] = {"cerebro": cerebro.nome_do_cerebro(), "resposta_s": round(time.time() - inicio, 2)}
    except Exception as e:
        resultado["nuvem"] = {"erro": str(e)[:100]}
    medidos = [m for m in resultado["locais"] if "tokens_s" in m]
    if medidos:
        bons = [m for m in medidos if m["tokens_s"] >= MINIMO_TOKS]
        ordem = lambda m: QUALIDADE.index(m["modelo"]) if m["modelo"] in QUALIDADE else 99
        melhor = min(bons, key=ordem) if bons else max(medidos, key=lambda m: m["tokens_s"])
        resultado["recomendado"] = melhor["modelo"]
        if escolher and cfg.get("modelo") != melhor["modelo"]:
            cfg["modelo"] = melhor["modelo"]
            (RAIZ / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            resultado["trocou"] = True
    ARQUIVO.parent.mkdir(exist_ok=True)
    ARQUIVO.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    return resultado


def ultimo_benchmark():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
