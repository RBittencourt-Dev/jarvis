"""Dados ao vivo dos painéis fixos do HUD (ref jarvis_hud.json): SISTEMA, REDE, HOJE (clima + notícias).

O servidor expõe em /api/hud; o web/hud-paineis.js busca e preenche. Tudo com cache/TTL e try/except: se uma fonte
falhar, aquele widget mostra "—" e o resto continua. Nada aqui bloqueia por muito tempo (o scan de rede roda numa
thread em segundo plano; clima e notícias têm cache de 10 min).

Reaproveita sistemas.py (CPU/RAM/disco) e rede.py (ping, escanear). GPU por nvidia-smi quando houver.
"""
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

import httpx
import psutil

import rede
import sistemas

# Porto Alegre (escolha do Rafael)
LAT, LON = -30.0346, -51.2177
RSS_G1 = "https://g1.globo.com/rss/g1/"

_cache = {}          # chave -> (valor, quando)
_net_antes = {}      # pra calcular download/upload por segundo
_dispositivos = {"n": None, "quando": 0}
_scan_rodando = False


def _fresco(chave, ttl):
    v = _cache.get(chave)
    return v[0] if v and (time.time() - v[1] < ttl) else None


def _guardar(chave, valor):
    _cache[chave] = (valor, time.time())
    return valor


def _gpu():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=4, creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.strip().splitlines()[0])
    except Exception:
        pass
    return None


_temp_cache = {"t": 0.0, "v": None}


def _temp_lhm():
    """Lê a temperatura do processador do LibreHardwareMonitor (se estiver aberto com o
    servidor web ligado, em http://localhost:8085). Windows não entrega °C pelo psutil;
    esse é o jeito que funciona sem o Jarvis precisar ser administrador."""
    try:
        import httpx
        d = httpx.get("http://localhost:8085/data.json", timeout=0.6).json()
    except Exception:
        return None
    achado = {"pkg": None, "qualquer": None}

    def anda(n):
        txt = (n.get("Text") or "").lower()
        val = (n.get("Value") or "")
        if "°c" in val.lower() and ("cpu" in txt or "package" in txt or "tctl" in txt or "core" in txt):
            try:
                g = round(float(val.lower().split("°")[0].replace(",", ".").strip()))
                if "package" in txt or "tctl" in txt:
                    achado["pkg"] = g
                elif achado["qualquer"] is None:
                    achado["qualquer"] = g
            except Exception:
                pass
        for c in n.get("Children", []):
            anda(c)

    anda(d)
    return achado["pkg"] if achado["pkg"] is not None else achado["qualquer"]


def _temperatura():
    # cache de ~5s pra não martelar o LHM a cada atualização do painel
    import time
    if time.time() - _temp_cache["t"] < 5 and _temp_cache["v"] is not None:
        return _temp_cache["v"]
    v = _temp_lhm()
    if v is None:
        try:
            temps = psutil.sensors_temperatures()  # funciona no Linux; no Windows volta vazio
            for chave in ("coretemp", "k10temp", "acpitz"):
                if temps.get(chave):
                    v = round(temps[chave][0].current); break
            if v is None:
                for lista in temps.values():
                    if lista:
                        v = round(lista[0].current); break
        except Exception:
            pass
    _temp_cache.update({"t": time.time(), "v": v})
    return v


def _bateria():
    try:
        b = psutil.sensors_battery()
        if b is not None:
            return {"pct": round(b.percent), "tomada": b.power_plugged}
    except Exception:
        pass
    return None


def sistema():
    n = sistemas.numeros_do_pc()  # cpu, ram, ram_gb, ram_total, disco
    return {"cpu": round(n["cpu"]), "ram": round(n["ram"]), "ram_gb": n["ram_gb"], "ram_total": n["ram_total"],
            "disco": round(n["disco"]), "gpu": _gpu(), "temp": _temperatura(), "bateria": _bateria()}


def rede_agora():
    agora = time.time()
    io = psutil.net_io_counters()
    down = up = 0.0
    if _net_antes:
        dt = max(0.001, agora - _net_antes["t"])
        down = max(0, (io.bytes_recv - _net_antes["r"]) / dt / 1048576)  # MB/s
        up = max(0, (io.bytes_sent - _net_antes["s"]) / dt / 1048576)
    _net_antes.update({"t": agora, "r": io.bytes_recv, "s": io.bytes_sent})
    ping = _fresco("ping", 5)
    if ping is None:
        try:
            ping = _guardar("ping", rede._ping_ms("1.1.1.1"))
        except Exception:
            ping = _guardar("ping", None)
    _agendar_scan()
    return {"down": round(down, 2), "up": round(up, 2), "ping": ping, "dispositivos": _dispositivos["n"]}


def _agendar_scan():
    """Escaneia a rede em segundo plano no máximo a cada 5 min (escanear() é lento)."""
    global _scan_rodando
    if _scan_rodando or (time.time() - _dispositivos["quando"] < 300):
        return
    _scan_rodando = True

    def tarefa():
        global _scan_rodando
        try:
            achados = rede.escanear(com_cameras=False)
            _dispositivos["n"] = len(achados) if isinstance(achados, (list, tuple)) else _dispositivos["n"]
        except Exception:
            pass
        finally:
            _dispositivos["quando"] = time.time()
            _scan_rodando = False

    threading.Thread(target=tarefa, daemon=True).start()


_WMO = {0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado", 45: "neblina", 48: "neblina",
        51: "garoa", 53: "garoa", 55: "garoa", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
        71: "neve", 73: "neve", 75: "neve", 80: "pancadas", 81: "pancadas", 82: "temporal",
        95: "tempestade", 96: "tempestade", 99: "tempestade"}


def clima():
    c = _fresco("clima", 600)
    if c is not None:
        return c
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
               "&current=temperature_2m,weather_code&hourly=precipitation_probability&forecast_days=1"
               "&timezone=America%2FSao_Paulo")
        r = httpx.get(url, timeout=8)
        d = r.json()
        atual = d.get("current", {})
        chuva = None
        probs = d.get("hourly", {}).get("precipitation_probability")
        if probs:
            chuva = probs[0]
        return _guardar("clima", {"temp": round(atual.get("temperature_2m")), "cond": _WMO.get(atual.get("weather_code"), "—"),
                                  "chuva": chuva})
    except Exception:
        return _guardar("clima", None)


def noticias():
    c = _fresco("noticias", 600)
    if c is not None:
        return c
    try:
        r = httpx.get(RSS_G1, timeout=8, headers={"User-Agent": "JarvisHUD/1.0"})
        raiz = ET.fromstring(r.content)
        titulos = [it.findtext("title", "").strip() for it in raiz.iter("item")]
        titulos = [t for t in titulos if t][:6]
        return _guardar("noticias", titulos)
    except Exception:
        return _guardar("noticias", [])


def visao():
    """Estado da VISÃO (câmera/gestos) pro painel do HUD."""
    try:
        import gestos
        return {"gestos": bool(gestos._estado.get("ligado")), "erro": gestos._estado.get("erro")}
    except Exception:
        return {"gestos": False, "erro": None}


def tudo():
    """Snapshot pros painéis. Rápido: sistema/rede na hora, clima/notícias do cache (10 min)."""
    return {"sistema": sistema(), "rede": rede_agora(), "clima": clima(), "noticias": noticias(), "visao": visao()}
