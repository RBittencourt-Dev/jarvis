"""As peças DESTE PC como holograma, com os dados ao vivo do lado ("quanto de RAM tá usando", "me mostra o processador").

O que não muda (pentes de memória, nome do processador, placa de vídeo) vem do Windows uma vez e fica guardado;
o uso (RAM, CPU, disco) é lido na hora, e a tela atualiza a cada 2 s enquanto o holograma estiver aberto.
"""
import json
import re
import subprocess

import psutil

SEM_JANELA = 0x08000000
_fixo = {}


def _wmi():
    if _fixo:
        return _fixo
    cmd = ("$r=@{}; $r.ram=@(Get-CimInstance Win32_PhysicalMemory | Select DeviceLocator,BankLabel,Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber);"
           "$r.slots=(Get-CimInstance Win32_PhysicalMemoryArray | Measure-Object -Property MemoryDevices -Sum).Sum;"
           "$r.cpu=Get-CimInstance Win32_Processor | Select -First 1 Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize;"
           "$r.gpu=@(Get-CimInstance Win32_VideoController | Select Name,AdapterRAM,DriverVersion);"
           "$r.discos=@(Get-PhysicalDisk | Select FriendlyName,MediaType,Size,BusType); $r | ConvertTo-Json -Depth 4 -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=40, creationflags=SEM_JANELA)
        _fixo.update(json.loads(r.stdout))
    except Exception as e:
        print("hardware:", e)
    return _fixo


def _gb(b):
    return f"{(b or 0) / 1024 ** 3:.1f} GB".replace(".0 GB", " GB")


def _lista(x):
    return x if isinstance(x, list) else [x] if x else []


def _cor_uso(p):
    return "#ff3b3b" if p >= 85 else "#ff9b3d" if p >= 60 else "#2ee88a"


# ------------------------------------------------------------------ memória RAM

def dados_ram():
    w = _wmi()
    pentes = _lista(w.get("ram"))
    v = psutil.virtual_memory()
    canais = {(p.get("BankLabel") or p.get("DeviceLocator") or "")[-2:-1] or (p.get("DeviceLocator") or "?")[-2] for p in pentes}
    modo = "Dual channel" if len(pentes) >= 2 and len(canais) >= 2 else "Single channel" if len(pentes) == 1 else f"{len(pentes)} pentes"
    linhas = [("Total", _gb(v.total)), ("Em uso", f"{_gb(v.used)} ({v.percent:.0f}%)"), ("Livre", _gb(v.available)),
              ("Modo", modo)]
    for p in pentes:
        vel = p.get("ConfiguredClockSpeed") or p.get("Speed")
        linhas.append((p.get("DeviceLocator") or "pente", f"{_gb(p.get('Capacity'))} {(p.get('Manufacturer') or '').strip()} {vel} MHz".strip()))
    for p in pentes:  # pente de 3200 rodando a 2400: o perfil XMP/DOCP tá desligado na BIOS
        m = re.search(r"(\d{4})C\d", p.get("PartNumber") or "")
        vel = int(p.get("ConfiguredClockSpeed") or p.get("Speed") or 0)
        if m and vel and int(m.group(1)) > vel + 100:
            linhas.append(("Atenção", f"pente de {m.group(1)} MHz rodando a {vel} (XMP desligado)"))
            break
    return {"titulo": "MEMÓRIA RAM · AO VIVO", "linhas": linhas, "uso": v.percent}, pentes, modo, v


def cena_ram():
    d, pentes, modo, v = dados_ram()
    slots = max(int(_wmi().get("slots") or 0), 2, len(pentes))
    slots = 4 if slots > 2 else 2
    ocupados = {}
    for p in pentes:
        loc = (p.get("DeviceLocator") or "").upper().replace("DIMM", "").strip("_ -")
        ocupados[loc] = p
    nomes = ["A1", "A2", "B1", "B2"] if slots == 4 else ["A1", "B1"]
    if pentes and not any(n in ocupados for n in nomes):  # nome de slot diferente do padrão: ocupa em ordem
        ocupados = {nomes[i * (len(nomes) // max(1, len(pentes)))]: p for i, p in enumerate(pentes[:len(nomes)])}
    partes = [{"nome": "Placa-mãe", "forma": "placa", "tam": [4.2, 3.0, 0.08], "cor": "#2ee88a", "pos": [0, 0, -0.35], "explode": [0, 0, -0.6]}]
    cor_uso = _cor_uso(v.percent)
    for i, n in enumerate(nomes):
        x = -1.2 + i * (2.4 / max(1, len(nomes) - 1))
        p = ocupados.get(n)
        partes.append({"nome": f"Slot {n}", "forma": "caixa", "tam": [0.16, 2.6, 0.22], "cor": "#4fe3ff" if n[0] == "A" else "#c77dff",
                       "pos": [x, 0, -0.2], "explode": [0, 0, -0.2], "fantasma": True})
        if p:
            nome = f"{n} · {_gb(p.get('Capacity'))} {(p.get('Manufacturer') or '').strip()}"
            partes.append({"nome": nome, "forma": "placa", "tam": [0.06, 2.4, 0.9], "cor": "#ff9b3d", "pos": [x, 0, 0.35], "explode": [0, 0.3, 1.4],
                           "ancora": [0, 1.2, 0.45]})
            for c in range(4):  # os chips do pente
                partes.append({"nome": f"chip {n}{c}", "forma": "caixa", "tam": [0.09, 0.42, 0.42], "cor": cor_uso,
                               "pos": [x + 0.06, -0.85 + c * 0.57, 0.35], "explode": [0, 0.3, 1.4], "sem_rotulo": True})
    canal = ("Os dois canais trabalhando juntos: o dobro da largura de banda." if modo == "Dual channel" else
             "Só um canal: um pente sozinho. Um segundo pente igual no slot do outro canal dobraria a velocidade de acesso."
             if modo == "Single channel" else "")
    fala = (f"Memória RAM: {_gb(v.total)} no total, {_gb(v.used)} em uso, {v.percent:.0f} por cento. "
            f"{modo}, {len(pentes)} pente{'s' if len(pentes) != 1 else ''}. {canal}")
    for p in pentes:  # pente de 3200 rodando a 2400: o perfil XMP/DOCP tá desligado na BIOS
        m = re.search(r"(\d{4})C\d", p.get("PartNumber") or "")
        vel = int(p.get("ConfiguredClockSpeed") or p.get("Speed") or 0)
        if m and vel and int(m.group(1)) > vel + 100:
            fala += (f" Detalhe: teu pente é de {m.group(1)} megahertz mas tá rodando a {vel}. Ligando o XMP, ou DOCP, na BIOS, "
                     "ele roda na velocidade certa.")
            break
    return {"titulo": "Memória RAM", "subtitulo": modo.upper(), "partes": partes, "dados": d, "intro": fala, "zoom": 7,
            "passos": [{"fala": fala, "destaque": [x["nome"] for x in partes if x["cor"] == "#ff9b3d"], "explodir": True}]}, fala


# ------------------------------------------------------------------ processador

def dados_cpu():
    c = _wmi().get("cpu") or {}
    uso = psutil.cpu_percent(interval=0.4)
    nucleos = psutil.cpu_percent(interval=None, percpu=True)
    freq = psutil.cpu_freq()
    linhas = [("Modelo", (c.get("Name") or "?").strip()), ("Núcleos / threads", f"{c.get('NumberOfCores', '?')} / {c.get('NumberOfLogicalProcessors', '?')}"),
              ("Clock", f"{(freq.current if freq else c.get('MaxClockSpeed', 0)) / 1000:.2f} GHz"), ("Uso agora", f"{uso:.0f}%")]
    if c.get("L3CacheSize"):
        linhas.append(("Cache L3", f"{int(c['L3CacheSize']) // 1024} MB"))
    mais = sorted(range(len(nucleos)), key=lambda i: -nucleos[i])[:3]
    linhas.append(("Threads mais ocupadas", ", ".join(f"#{i} {nucleos[i]:.0f}%" for i in mais)))
    return {"titulo": "PROCESSADOR · AO VIVO", "linhas": linhas, "uso": uso}, c, uso


def cena_cpu():
    d, c, uso = dados_cpu()
    nome = (c.get("Name") or "Processador").strip()
    n = int(c.get("NumberOfCores") or 4)
    partes = [{"nome": "Substrato", "forma": "placa", "tam": [2.6, 0.08, 2.6], "cor": "#2ee88a", "pos": [0, -0.3, 0], "explode": [0, -0.9, 0]},
              {"nome": "Tampa (IHS)", "forma": "caixa", "tam": [2.2, 0.16, 2.2], "cor": "#9ad8ff", "pos": [0, -0.15, 0], "explode": [0, 1.6, 0]},
              {"nome": "Die", "forma": "caixa", "tam": [1.3, 0.08, 1.0], "cor": "#ffd23d", "pos": [0, -0.21, 0], "explode": [0, 0.5, 0]}]
    cols = 2 if n <= 4 else 3 if n <= 6 else 4
    linhas_ = -(-n // cols)
    for i in range(n):
        x = -0.4 + (i % cols) * (0.8 / max(1, cols - 1))
        z = -0.25 + (i // cols) * (0.5 / max(1, linhas_ - 1))
        partes.append({"nome": f"Núcleo {i + 1}", "forma": "caixa", "tam": [0.22, 0.14, 0.18], "cor": _cor_uso(uso) if i < 1 else "#ff7a2f",
                       "pos": [x, -0.12, z], "explode": [x * 0.8, 0.85, z * 0.8], "sem_rotulo": i > 0})
    fala = (f"{nome}: {c.get('NumberOfCores', '?')} núcleos e {c.get('NumberOfLogicalProcessors', '?')} threads, "
            f"rodando a {uso:.0f} por cento agora.")
    return {"titulo": nome, "subtitulo": f"{n} NÚCLEOS · {c.get('NumberOfLogicalProcessors', '?')} THREADS", "partes": partes, "dados": d,
            "intro": fala, "zoom": 6.5,
            "passos": [{"fala": fala, "destaque": ["Die"] + [f"Núcleo {i + 1}" for i in range(n)], "explodir": True}]}, fala


# ------------------------------------------------------------------ placa de vídeo e disco

def cena_gpu():
    g = (_lista(_wmi().get("gpu")) or [{}])[0]
    nome = (g.get("Name") or "Placa de vídeo").strip()
    integrada = any(x in nome.lower() for x in ("radeon(tm) graphics", "uhd", "iris", "vega"))
    linhas = [("Modelo", nome), ("Tipo", "Integrada no processador" if integrada else "Dedicada"),
              ("Memória reservada" if integrada else "VRAM", _gb(g.get("AdapterRAM"))), ("Driver", g.get("DriverVersion") or "?")]
    if integrada:
        partes = [{"nome": "Processador", "forma": "caixa", "tam": [2.2, 0.16, 2.2], "cor": "#9ad8ff", "pos": [0, 0, 0], "explode": [0, 1.2, 0]},
                  {"nome": "Gráficos integrados", "forma": "caixa", "tam": [0.8, 0.1, 0.6], "cor": "#ff3b3b", "pos": [0.4, -0.05, 0.3], "explode": [0.4, 0.4, 0.6]},
                  {"nome": "Núcleos de CPU", "forma": "caixa", "tam": [0.9, 0.1, 0.7], "cor": "#ff7a2f", "pos": [-0.45, -0.05, -0.2], "explode": [-0.4, 0.4, -0.4]}]
        fala = f"Seu vídeo é {nome}, integrado dentro do processador: ele usa uma parte da RAM como memória de vídeo."
    else:
        partes = [{"nome": "Placa (PCB)", "forma": "placa", "tam": [3.2, 1.2, 0.06], "cor": "#2ee88a", "pos": [0, 0, 0], "explode": [0, 0, -0.8]},
                  {"nome": "GPU", "forma": "caixa", "tam": [0.6, 0.6, 0.1], "cor": "#ff3b3b", "pos": [0, 0, 0.1], "explode": [0, 0, 0.6]},
                  {"nome": "Ventoinha 1", "forma": "cilindro", "tam": [0.48, 0.12], "cor": "#9ad8ff", "pos": [-0.8, 0, 0.45], "rot": [1.5708, 0, 0], "explode": [-0.4, 0, 1.6]},
                  {"nome": "Ventoinha 2", "forma": "cilindro", "tam": [0.48, 0.12], "cor": "#9ad8ff", "pos": [0.8, 0, 0.45], "rot": [1.5708, 0, 0], "explode": [0.4, 0, 1.6]}]
        fala = f"Sua placa de vídeo é {nome}, com {_gb(g.get('AdapterRAM'))} de memória."
    d = {"titulo": "VÍDEO", "linhas": linhas}
    return {"titulo": nome, "partes": partes, "dados": d, "intro": fala,
            "passos": [{"fala": fala, "destaque": [partes[1]["nome"]], "explodir": True}]}, fala


def dados_disco():
    linhas = []
    usos = []
    for p in psutil.disk_partitions():
        if "cdrom" in p.opts or not p.fstype:
            continue
        try:
            u = psutil.disk_usage(p.mountpoint)
        except OSError:
            continue
        usos.append(u.percent)
        linhas.append((p.mountpoint, f"{_gb(u.used)} de {_gb(u.total)} ({u.percent:.0f}%)"))
    for d in _lista(_wmi().get("discos")):
        linhas.append((d.get("FriendlyName", "disco").strip(), f"{d.get('MediaType') or ''} {d.get('BusType') or ''} {_gb(d.get('Size'))}".strip()))
    return {"titulo": "ARMAZENAMENTO · AO VIVO", "linhas": linhas, "uso": max(usos or [0])}


def cena_disco():
    d = dados_disco()
    principal = d["linhas"][0] if d["linhas"] else ("C:\\", "?")
    partes = [{"nome": "SSD", "forma": "placa", "tam": [2.8, 0.06, 0.9], "cor": "#ff9b3d", "pos": [0, 0, 0], "explode": [0, -0.4, 0]},
              {"nome": "Controlador", "forma": "caixa", "tam": [0.5, 0.1, 0.5], "cor": "#ff3b3b", "pos": [-0.9, 0.08, 0], "explode": [-0.3, 0.7, 0]},
              {"nome": "Chips de memória flash", "forma": "caixa", "tam": [1.2, 0.1, 0.6], "cor": _cor_uso(d.get("uso", 0)), "pos": [0.5, 0.08, 0], "explode": [0.3, 0.9, 0]}]
    fala = f"Disco {principal[0]}: {principal[1]}."
    return {"titulo": "Armazenamento", "partes": partes, "dados": d, "intro": fala,
            "passos": [{"fala": fala, "destaque": ["Chips de memória flash"], "explodir": True}]}, fala


def dados_tudo():
    r, pentes, modo, v = dados_ram()
    c, cpu, uso = dados_cpu()
    g = (_lista(_wmi().get("gpu")) or [{}])[0]
    d = dados_disco()
    linhas = [("Processador", (cpu.get("Name") or "?").strip().replace(" with Radeon Graphics", "")), ("Uso da CPU", f"{uso:.0f}%"),
              ("Memória RAM", f"{_gb(v.total)} · {modo}"), ("RAM em uso", f"{_gb(v.used)} ({v.percent:.0f}%)"),
              ("Vídeo", (g.get("Name") or "?").strip())]
    linhas += d["linhas"][:3]
    return {"titulo": "ESTE PC · AO VIVO", "linhas": linhas, "uso": max(uso, v.percent)}


def cena_tudo():
    """"Me mostra o hardware do meu PC": o gabinete aberto com cada peça e o dado dela do lado."""
    import apresentacoes
    d = dados_tudo()
    _, pentes, modo, v = dados_ram()
    _, cpu, uso = dados_cpu()
    g = (_lista(_wmi().get("gpu")) or [{}])[0]
    disco = dados_disco()
    nome_cpu = (cpu.get("Name") or "Processador").strip().replace(" with Radeon Graphics", "")
    integrada = any(x in (g.get("Name") or "").lower() for x in ("radeon(tm) graphics", "uhd", "iris", "vega"))
    rotulos = {"Processador": f"{nome_cpu} · {uso:.0f}%", "Memória RAM": f"RAM {_gb(v.total)} · {modo} · {v.percent:.0f}%",
               "Placa de vídeo": f"{(g.get('Name') or 'Vídeo').strip()}{' (integrada)' if integrada else ''}",
               "SSD": f"SSD · {disco['linhas'][0][1] if disco['linhas'] else ''}"}
    partes = []
    for p in apresentacoes.COMPUTADOR["partes"]:
        if p["nome"] == "Placa de vídeo" and integrada:
            continue  # vídeo integrado: não tem placa separada
        p = dict(p)
        p["nome"] = rotulos.get(p["nome"], p["nome"])
        if p["nome"].startswith("RAM"):
            p["cor"] = _cor_uso(v.percent) if v.percent >= 85 else p["cor"]
        partes.append(p)
    nomes = [p["nome"] for p in partes]
    pega = lambda prefixo: [n for n in nomes if n.startswith(prefixo)]
    passos = [{"fala": f"Processador {nome_cpu}, {cpu.get('NumberOfCores', '?')} núcleos, a {uso:.0f} por cento agora.",
               "destaque": pega(nome_cpu) + pega("Cooler"), "explodir": True},
              {"fala": f"Memória: {_gb(v.total)} em {modo.lower()}, {v.percent:.0f} por cento em uso.", "destaque": pega("RAM"), "explodir": True},
              {"fala": f"Vídeo: {rotulos['Placa de vídeo']}." + (" Ele usa um pedaço da RAM como memória de vídeo." if integrada else ""),
               "destaque": pega(nome_cpu) if integrada else pega(rotulos["Placa de vídeo"]), "explodir": True},
              {"fala": f"E o disco: {disco['linhas'][0][1] if disco['linhas'] else 'sem leitura'}.", "destaque": pega("SSD"), "explodir": True}]
    fala = "Teu PC por dentro, chefe, com os números ao vivo do lado."
    return {"titulo": "Este PC", "subtitulo": "HARDWARE AO VIVO", "partes": partes, "dados": d, "intro": fala, "passos": passos}, fala


CENAS = {"ram": cena_ram, "cpu": cena_cpu, "gpu": cena_gpu, "disco": cena_disco, "tudo": cena_tudo}
DADOS = {"ram": lambda: dados_ram()[0], "cpu": lambda: dados_cpu()[0], "disco": dados_disco, "tudo": dados_tudo}


# ------------------------------------------------------------------ temperatura e velocidade (filtros dentro do contexto)

def temperaturas():
    """O Windows não entrega temperatura sem programa de sensor. Lê do LibreHardwareMonitor (grátis) se estiver aberto:
    pelo servidor web dele (porta 8085) ou pelo WMI. Devolve [(nome, "57 °C")] ou None."""
    import httpx
    achadas = []
    try:
        dados = httpx.get("http://127.0.0.1:8085/data.json", timeout=1.5).json()

        def andar(no, caminho):
            for f in no.get("Children", []):
                andar(f, caminho + [no.get("Text", "")])
            if "°C" in str(no.get("Value", "")) and no.get("Text"):
                achadas.append((f"{caminho[-1] if caminho else ''} {no['Text']}".strip(), no["Value"]))
        andar(dados, [])
    except Exception:
        cmd = ("Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -ErrorAction Stop | "
               "Where-Object SensorType -eq 'Temperature' | Select Name,Value | ConvertTo-Json -Compress")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=15, creationflags=SEM_JANELA)
            achadas = [(x["Name"], f"{x['Value']:.0f} °C") for x in _lista(json.loads(r.stdout))]
        except Exception:
            return None
    return achadas[:8] or None


def velocidades(tipo):
    """Clock do processador, MHz da RAM, leitura/escrita do disco e rede (medidas em 1 s)."""
    linhas = []
    if tipo in ("cpu", "tudo"):
        f = psutil.cpu_freq()
        c = _wmi().get("cpu") or {}
        if f:
            linhas.append(("Clock agora", f"{f.current / 1000:.2f} GHz (máx. {(f.max or c.get('MaxClockSpeed', 0)) / 1000:.2f})"))
    if tipo in ("ram", "tudo"):
        for p in _lista(_wmi().get("ram")):
            m = re.search(r"(\d{4})C\d", p.get("PartNumber") or "")
            vel = p.get("ConfiguredClockSpeed") or p.get("Speed")
            linhas.append((p.get("DeviceLocator") or "pente", f"{vel} MHz" + (f" (de fábrica {m.group(1)})" if m and int(m.group(1)) > int(vel or 0) + 100 else "")))
    if tipo in ("disco", "tudo", "cpu", "ram", "gpu"):
        import time
        a, ra = psutil.disk_io_counters(), psutil.net_io_counters()
        time.sleep(1)
        b, rb = psutil.disk_io_counters(), psutil.net_io_counters()
        if tipo in ("disco", "tudo"):
            linhas.append(("Disco lendo", f"{(b.read_bytes - a.read_bytes) / 1024 ** 2:.1f} MB/s"))
            linhas.append(("Disco gravando", f"{(b.write_bytes - a.write_bytes) / 1024 ** 2:.1f} MB/s"))
        if tipo == "tudo":
            linhas.append(("Rede baixando", f"{(rb.bytes_recv - ra.bytes_recv) * 8 / 1e6:.1f} Mb/s"))
            linhas.append(("Rede enviando", f"{(rb.bytes_sent - ra.bytes_sent) * 8 / 1e6:.1f} Mb/s"))
    return linhas
