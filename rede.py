"""T.I de rede, pra acionar fácil: "acha os aparelhos da rede", "acha as câmeras", "lista de usuários da rede",
"diagnóstico da rede". Ele varre a rede local, identifica câmeras/DVR, lista usuários (deste PC e do domínio) e
mostra tudo no HUD, falando um resumo. Roda no PC onde o Jarvis está (ex.: o do colégio).

Pedido do Rafael (24/10/2026): "ensina a ele tudo sobre rede" (a teoria está em especialidades/redes.md, respondida
pelo especialista de suporte) e "tem que dar pra acionar fácil: acha as câmeras, acha a lista de usuários da rede".
Mostrar a IMAGEM da câmera precisa do login dela (guardado no cofre) — enquanto não tiver, ele só ACHA e explica como ligar.

Tudo aqui é pra administrar a rede que ELE cuida (a escola), defensivo. Nada de rede de terceiros.
"""
import json
import os
import re
import socket
import struct
import subprocess
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import cofre

DEMORA = True
SEM_JANELA = 0x08000000
_POOL = ThreadPoolExecutor(max_workers=120, thread_name_prefix="rede")

# portas que denunciam câmera/DVR/NVR (RTSP e os apps das marcas)
PORTAS_CAMERA = [554, 8000, 37777, 34567, 8899, 9000]
# portas que denunciam impressora (RAW/JetDirect, IPP, LPD) e PC Windows (SMB, NetBIOS, RDP)
PORTAS_IMPRESSORA = [9100, 631, 515]
PORTAS_PC = [445, 139, 3389]
# tudo que a varredura testa pra classificar cada aparelho
PROBE = PORTAS_CAMERA + PORTAS_IMPRESSORA + PORTAS_PC
TIPO_NOME = {"roteador": "roteador", "impressora": "impressora", "camera": "câmera/DVR", "pc": "PC", "aparelho": "aparelho"}
# fabricante pelos 3 primeiros pares do MAC (OUI). Foco no que aparece em escola; o que não estiver aqui fica sem nome.
OUI = {
    "BC-32-5F": "Intelbras", "3C-E1-A1": "Intelbras", "90-02-A9": "Hikvision", "C0-56-E3": "Hikvision",
    "44-19-B6": "Hikvision", "4C-11-BF": "Dahua", "90-02-79": "Dahua", "3C-EF-8C": "Dahua",
    "E0-50-8B": "Dahua", "00-23-63": "Axis", "AC-CC-8E": "Axis",
    "50-C7-BF": "TP-Link", "AC-84-C6": "TP-Link", "C4-6E-1F": "TP-Link", "E8-48-B8": "TP-Link",
    "D8-07-B6": "Mercusys", "74-AC-B9": "Ubiquiti", "FC-EC-DA": "Ubiquiti", "DC-9F-DB": "Ubiquiti",
    "48-8F-5A": "Mikrotik", "64-D1-54": "Mikrotik", "CC-2D-E0": "Mikrotik",
    "1C-BF-C0": "D-Link", "C8-D3-A3": "D-Link", "00-1C-F0": "Multilaser",
    "F4-F5-E8": "Google", "44-07-0B": "Amazon", "F0-27-2D": "Amazon",
    "A4-83-E7": "Apple", "DC-A6-32": "Raspberry Pi", "B8-27-EB": "Raspberry Pi",
    "F8-FF-C2": "Apple", "AC-DE-48": "Apple", "00-16-6C": "Samsung", "5C-0A-5B": "Samsung",
    "28-6C-07": "Xiaomi", "64-09-80": "Xiaomi", "18-59-36": "Huawei", "48-2C-A0": "Huawei",
    "00-1B-A9": "Brother", "30-05-5C": "Brother", "00-26-73": "Epson", "A4-5D-36": "HP",
    "00-1E-68": "Positivo", "D4-BE-D9": "Dell", "54-E1-AD": "Lenovo",
    "F4-6A-DD": "Motorola", "A0-39-F7": "LG",
}
CAMERA_MARCAS = {"Intelbras", "Hikvision", "Dahua", "Axis"}


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _ps(cmd, timeout=25):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, creationflags=SEM_JANELA)
        return r.stdout or ""
    except Exception as e:
        print("rede:", e)
        return ""


def _psjson(cmd, timeout=25):
    out = _ps(cmd, timeout).strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


def _lista(x):
    return x if isinstance(x, list) else [x] if x else []


def _fabricante(mac):
    if not mac:
        return ""
    return OUI.get(mac.upper().replace(":", "-")[:8], "")


def _tipo(portas, fab, ehgw):
    """Classifica o aparelho pelo que ele tem aberto (bem mais confiável que o MAC): roteador, impressora, câmera, PC."""
    s = set(portas)
    if ehgw:
        return "roteador", "📡"
    if s & set(PORTAS_IMPRESSORA):
        return "impressora", "🖨️"
    if s & set(PORTAS_CAMERA) or fab in CAMERA_MARCAS:
        return "camera", "📷"
    if s & set(PORTAS_PC):
        return "pc", "🖥️"
    return "aparelho", "•"


def _limpa_nome(n):
    """Deixa só o hostname (tira domínio e ponto final). Descarta quando o 'nome' é só o IP."""
    if not n:
        return None
    n = n.rstrip(".").split(".")[0].strip()
    if not n or n.replace("-", "").isdigit():
        return None
    return n


def _read_dns_name(data, off):
    """Lê um nome DNS (com ponteiros de compressão) a partir de um offset. Pra decodificar a resposta do LLMNR/mDNS."""
    labels = []
    for _ in range(128):
        if off >= len(data):
            break
        length = data[off]
        if length == 0:
            break
        if length & 0xC0 == 0xC0:  # ponteiro de compressão
            off = ((length & 0x3F) << 8) | data[off + 1]
            continue
        labels.append(data[off + 1:off + 1 + length].decode("ascii", "replace"))
        off += 1 + length
    return ".".join(labels)


def _resolver_porta(ip, porta, timeout=0.8):
    """Pergunta o nome do host por LLMNR (5355) ou mDNS (5353), unicast, consulta PTR reversa. O Windows responde o
    próprio nome mesmo com NetBIOS desligado — é assim que a gente pega o nome sem senha."""
    rev = ".".join(reversed(ip.split("."))) + ".in-addr.arpa"
    pkt = struct.pack(">HHHHHH", 0x1234, 0x0000, 1, 0, 0, 0)
    for parte in rev.split("."):
        pkt += bytes([len(parte)]) + parte.encode()
    pkt += b"\x00" + struct.pack(">HH", 12, 1)  # QTYPE=PTR, QCLASS=IN
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(pkt, (ip, porta))
        data, _ = s.recvfrom(2048)
    except Exception:
        return None
    finally:
        s.close()
    try:
        off = 12
        while off < len(data) and data[off] != 0:  # pula a pergunta
            if data[off] & 0xC0 == 0xC0:
                off += 1
                break
            off += data[off] + 1
        off += 1 + 4  # fim do nome + QTYPE + QCLASS
        if off + 12 > len(data):
            return None
        if data[off] & 0xC0 == 0xC0:  # nome da resposta
            off += 2
        else:
            while off < len(data) and data[off] != 0:
                off += data[off] + 1
            off += 1
        off += 10  # TYPE(2) CLASS(2) TTL(4) RDLEN(2)
        return _read_dns_name(data, off)
    except Exception:
        return None


def _llmnr(ip):
    return _resolver_porta(ip, 5355) or _resolver_porta(ip, 5353)


# ------------------------------------------------------------------ configuração da própria rede
def config():
    cmd = ("$g = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1;"
           "if(-not $g){ exit };"
           "$ipo = Get-NetIPAddress -InterfaceIndex $g.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {$_.IPAddress -notlike '169.254*'} | Select-Object -First 1;"
           "$dns = (Get-DnsClientServerAddress -InterfaceIndex $g.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses -join ', ';"
           "[pscustomobject]@{ ip=$ipo.IPAddress; pfx=$ipo.PrefixLength; gw=$g.NextHop; dns=$dns;"
           " adaptador=(Get-NetAdapter -InterfaceIndex $g.InterfaceIndex -ErrorAction SilentlyContinue).Name } | ConvertTo-Json -Compress")
    return _psjson(cmd, 20) or {}


def _wifi():
    out = _ps("netsh wlan show interfaces", 12)
    if "SSID" not in out:
        return None
    def pega(rotulos):
        for r in rotulos:
            m = re.search(rf"^\s*{r}\s*:\s*(.+?)\s*$", out, re.I | re.M)
            if m and m.group(1).strip():
                return m.group(1).strip()
        return None
    ssid = pega([r"SSID"])  # a 1ª linha "SSID" (não "BSSID")
    if ssid and ssid.upper().startswith("BSSID"):
        ssid = None
    return {"ssid": ssid, "sinal": pega([r"Sinal", r"Signal"]), "canal": pega([r"Canal", r"Channel"]),
            "velocidade": pega([r"Taxa de recep", r"Receive rate", r"Taxa de transmiss", r"Transmit rate"])} if ssid else None


def _ping_ms(alvo):
    try:
        r = subprocess.run(["ping", "-n", "1", "-w", "1500", alvo], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=4, creationflags=SEM_JANELA)
        if r.returncode != 0:
            return None
        m = re.search(r"(?:tempo|time)[=<]\s*(\d+)\s*ms", r.stdout, re.I)
        return int(m.group(1)) if m else 0
    except Exception:
        return None


# ------------------------------------------------------------------ varredura da rede
def _ping(ip):
    try:
        r = subprocess.run(["ping", "-n", "1", "-w", "350", ip], capture_output=True,
                           timeout=2, creationflags=SEM_JANELA)
        return ip if r.returncode == 0 else None
    except Exception:
        return None


def _vizinhos():
    """IP → MAC do cache de vizinhos (preenchido pelo ping sweep). Jeito moderno do arp -a."""
    cmd = ("Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
           "Where-Object { $_.State -in 'Reachable','Stale','Permanent' -and $_.LinkLayerAddress -and "
           "$_.LinkLayerAddress -ne '00-00-00-00-00-00' -and $_.LinkLayerAddress -ne 'FF-FF-FF-FF-FF-FF' } | "
           "Select-Object IPAddress,LinkLayerAddress | ConvertTo-Json -Compress")
    out = {}
    for v in _lista(_psjson(cmd, 15)):
        ip = v.get("IPAddress")
        if ip and not ip.startswith(("224.", "239.", "255.")):
            out[ip] = v.get("LinkLayerAddress")
    return out


def _nbt(ip):
    """Nome do PC, quem está logado e o grupo/domínio, sem senha (NetBIOS, porta 137). None se o PC não responde
    NetBIOS (desligado ou não é Windows). Códigos são universais: <00> UNIQUE=nome, <00> GROUP=grupo, <20>=compartilha,
    <03> UNIQUE (≠ nome)=usuário logado."""
    try:
        r = subprocess.run(["nbtstat", "-A", ip], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=4, creationflags=SEM_JANELA)
        out = r.stdout
    except Exception:
        return None
    nome = grupo = usuario = None
    shares = False
    for l in out.splitlines():
        m = re.match(r"\s*(\S.*?)\s+<([0-9A-Fa-f]{2})>\s+(UNIQUE|GROUP)", l)
        if not m:
            continue
        n, code, tipo = m.group(1).strip(), m.group(2).upper(), m.group(3)
        if code == "00" and tipo == "UNIQUE" and not nome:
            nome = n
        elif code == "00" and tipo == "GROUP" and not grupo:
            grupo = n
        elif code == "20":
            shares = True
        elif code == "03" and tipo == "UNIQUE" and n and n != nome:
            usuario = n
    if not (nome or grupo):
        return None
    return {"nome": nome, "grupo": grupo, "usuario": usuario, "shares": shares}


def pcs_da_rede():
    """Os PCs (Windows) na rede: nome, quem está logado, grupo e se compartilha pasta — tudo sem senha.
    Candidato a PC = tem SMB/NetBIOS/RDP aberto. O nome vem do DNS/LLMNR (varredura) e o nbtstat enriquece com o
    usuário logado quando o NetBIOS está ligado. Devolve (pcs, cfg, todos_aparelhos, outros)."""
    aparelhos, cfg = escanear()
    outros = [a for a in aparelhos if not a["eu"]]
    cand = [a for a in outros if a["tipo"] == "pc"]
    prazo = time.time() + 8
    futuros = {a["ip"]: _POOL.submit(_nbt, a["ip"]) for a in cand}
    pcs = []
    for a in cand:
        try:
            info = futuros[a["ip"]].result(timeout=max(0.1, prazo - time.time())) or {}
        except Exception:
            info = {}
        pcs.append({"ip": a["ip"], "fabricante": a["fabricante"], "nome": info.get("nome") or a["nome"],
                    "grupo": info.get("grupo"), "usuario": info.get("usuario"), "shares": info.get("shares", False)})
    return pcs, cfg, aparelhos, outros


def _remoto_usuarios(ip, user, senhas):
    """Lista os usuários locais de OUTRO PC (que é do Rafael/da escola), testando as senhas de admin que ele guardou.
    Usa WMI (DCOM, porta 135). A senha vai por variável de ambiente, nunca na linha de comando. Devolve (lista, senha_ok)
    ou (None, None). Para rápido se o 135 estiver fechado (acesso remoto desligado)."""
    if not _porta(ip, 135, 1.0):
        return None, None
    ps = ("$sec = ConvertTo-SecureString $env:JPW -AsPlainText -Force;"
          "$c = New-Object System.Management.Automation.PSCredential($env:JUSER, $sec);"
          "try { Get-WmiObject -ComputerName $env:JIP -Credential $c -Class Win32_UserAccount -Filter 'LocalAccount=True' -ErrorAction Stop |"
          " Select-Object Name,Disabled | ConvertTo-Json -Compress } catch { Write-Output ('ERRO:' + $_.Exception.Message) }")
    # conta local do PC remoto: "IP\Administrador" (o ".\" do Rafael vira o host remoto)
    u = user if "\\" in user else f"{ip}\\{user.lstrip('.').lstrip(chr(92)) or 'Administrador'}"
    prazo = time.time() + 22
    for senha in senhas:
        if time.time() > prazo:
            break
        env = dict(os.environ, JPW=senha or "", JUSER=u, JIP=ip)
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=18, creationflags=SEM_JANELA, env=env)
        except Exception:
            continue
        out = (r.stdout or "").strip()
        if not out or out.startswith("ERRO:"):
            continue
        try:
            return _lista(json.loads(out)), senha
        except Exception:
            continue
    return None, None


def _nome(ip, prazo):
    try:
        return _POOL.submit(lambda: socket.gethostbyaddr(ip)[0]).result(timeout=max(0.1, prazo - time.time()))
    except Exception:
        return None


def _porta(ip, porta, timeout=0.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, porta)) == 0
    finally:
        s.close()


def escanear(com_cameras=True):
    """Aparelhos na rede: [{ip,mac,nome,fabricante,portas,camera,tipo,icone,eu,roteador}]. Ordenado por IP.
    Sempre classifica cada aparelho (PC/câmera/impressora/roteador) pelas portas e busca o nome por DNS reverso +
    LLMNR/mDNS (pega o nome do Windows mesmo com NetBIOS desligado). `com_cameras` fica só por compatibilidade."""
    cfg = config()
    ip_meu, gw = cfg.get("ip"), cfg.get("gw")
    if not ip_meu:
        return [], cfg
    base = ip_meu.rsplit(".", 1)[0]
    prazo = time.time() + 10
    # 1) ping sweep (preenche o cache de vizinhos)
    futuros = {ip: _POOL.submit(_ping, ip) for ip in (f"{base}.{i}" for i in range(1, 255))}
    vivos = set()
    for ip, f in futuros.items():
        try:
            if f.result(timeout=max(0.1, prazo - time.time())):
                vivos.add(ip)
        except Exception:
            pass
    # 2) MACs do cache + inclui quem tem MAC mas não respondeu ping
    macs = _vizinhos()
    ips = sorted(vivos | set(macs), key=lambda x: tuple(int(o) for o in x.split(".")))
    # 3) portas abertas de cada um (classificação), em paralelo
    futp = {(ip, p): _POOL.submit(_porta, ip, p) for ip in ips for p in PROBE}
    abertas = {ip: [] for ip in ips}
    for (ip, p), fp in futp.items():
        try:
            if fp.result(timeout=1.6):
                abertas[ip].append(p)
        except Exception:
            pass
    # 4) nomes: DNS reverso primeiro, LLMNR/mDNS pra quem não resolveu
    prazo_nome = time.time() + 6
    fdns = {ip: _POOL.submit(socket.gethostbyaddr, ip) for ip in ips}
    nomes = {}
    for ip in ips:
        try:
            nomes[ip] = _limpa_nome(fdns[ip].result(timeout=max(0.1, prazo_nome - time.time()))[0])
        except Exception:
            nomes[ip] = None
    faltam = [ip for ip in ips if not nomes.get(ip)]
    fll = {ip: _POOL.submit(_llmnr, ip) for ip in faltam}
    for ip in faltam:
        try:
            nomes[ip] = _limpa_nome(fll[ip].result(timeout=1.6))
        except Exception:
            pass
    aparelhos = []
    for ip in ips:
        mac = macs.get(ip)
        fab = _fabricante(mac)
        portas = sorted(abertas.get(ip, []))
        tipo, icone = _tipo(portas, fab, ip == gw)
        aparelhos.append({"ip": ip, "mac": mac, "nome": nomes.get(ip), "fabricante": fab,
                          "portas": portas, "camera": tipo == "camera", "tipo": tipo, "icone": icone,
                          "eu": ip == ip_meu, "roteador": ip == gw})
    return aparelhos, cfg


# ------------------------------------------------------------------ usuários (deste PC e do domínio)
def usuarios():
    cmd = (
        "$cs = Get-CimInstance Win32_ComputerSystem;"
        "$r = [ordered]@{ dominio = [bool]$cs.PartOfDomain; nome_dominio = $cs.Domain; workgroup = $cs.Workgroup };"
        "$r.locais = @(Get-LocalUser -ErrorAction SilentlyContinue | Select-Object Name,Enabled,@{n='ultimo';e={ if($_.LastLogon){$_.LastLogon.ToString('dd/MM/yyyy')} }},Description);"
        "if ($cs.PartOfDomain) {"
        "  try { $r.dominio_users = @(Get-ADUser -Filter * -Properties LastLogonDate -ErrorAction Stop | "
        "        Select-Object @{n='Name';e={$_.Name}},@{n='login';e={$_.SamAccountName}},Enabled,"
        "        @{n='ultimo';e={ if($_.LastLogonDate){$_.LastLogonDate.ToString('dd/MM/yyyy')} }} | Select-Object -First 300) }"
        "  catch { $r.net = ((net user /domain) 2>$null | Out-String) }"
        "}"
        "[pscustomobject]$r | ConvertTo-Json -Depth 4 -Compress")
    return _psjson(cmd, 40) or {}


def _parse_net_user(saida):
    """Nomes de usuário do domínio quando não dá pra usar o Get-AD (sem RSAT): pega o miolo do 'net user /domain'."""
    linhas = (saida or "").splitlines()
    corpo, ligado = [], False
    for l in linhas:
        if re.match(r"^-{5,}", l):
            ligado = not ligado
            continue
        if ligado and l.strip():
            corpo += l.split()
    return [u for u in corpo if u and not u.startswith("---")]


# ------------------------------------------------------------------ compartilhamentos
def compartilhamentos():
    meus = [f"{s.get('Name')} → {s.get('Path')}" for s in _lista(_psjson(
        "Get-SmbShare -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '*$' } | Select-Object Name,Path | ConvertTo-Json -Compress", 12))]
    pcs = []
    out = _ps("net view", 6)  # net view costuma pendurar quando não há navegador de rede; teto curto
    for l in out.splitlines():
        m = re.match(r"\\\\(\S+)", l.strip())
        if m:
            pcs.append(m.group(1))
    return {"deste_pc": meus, "na_rede": pcs}


# ------------------------------------------------------------------ print (snapshot) da câmera — precisa do login no cofre
def _snapshot_bytes(ip, user, senha):
    """Tenta pegar um JPEG da câmera por HTTP (endpoints das marcas comuns). Devolve bytes ou None."""
    import httpx
    caminhos = [
        "/cgi-bin/snapshot.cgi?channel=1",            # Intelbras/Dahua
        "/ISAPI/Streaming/channels/101/picture",       # Hikvision
        "/onvif-http/snapshot?Profile_1",              # ONVIF genérico
        "/axis-cgi/jpg/image.cgi",                     # Axis
        "/snapshot.jpg", "/image/jpeg.cgi", "/tmpfs/auto.jpg", "/jpg/image.jpg",
    ]
    for caminho in caminhos:
        url = f"http://{ip}{caminho}"
        for auth in (httpx.DigestAuth(user, senha), httpx.BasicAuth(user, senha)):
            try:
                r = httpx.get(url, auth=auth, timeout=5)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                    return r.content
            except Exception:
                pass
    return None


def snapshot(ip, cred):
    import base64
    b = _snapshot_bytes(ip, cred.get("user", ""), cred.get("senha", ""))
    if not b:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(b).decode()


# ------------------------------------------------------------------ roteador do Jarvis
# explicação/teoria (vai pro especialista) — "como" só quando é how-to, não "como tá a rede"
SOBRE = (r"\b(?:como (?:eu )?(?:fa[çc]o|faz|acess\w*|entr\w*|configur\w*|descubr\w*|mape\w*|us[oa]r?|conect\w*|instal\w*|"
         r"recuper\w*|reset\w*|mex\w*|v[eê]jo|criar|cria)|explica\w*|ensina\w*|o que (?:e|é|sao|são)|pra que serve|"
         r"significa|diferen[çc]a|me (?:ensina|explica)|aprende\w*)\b")
CAMERA = r"\b(c[aâ]mera\w*|cftv|dvr|nvr|v[ií]deo\s?monitoramento|circuito\s+interno)\b"
VER = r"\b(mostra\w*|ver|vej\w*|olha\w*|exib\w*|imagem|imagens|print\w*|ao vivo|tela|abre|abrir|visualiz\w*|espia\w*|d[aá] uma olhada)\b"
REDE = r"\b(rede|wi-?fi|lan|intranet)\b"
# achar/listar de verdade (verbo forte) — não confundir com só mencionar o assunto
ACHAR = (r"\b(acha\w*|ach[aá]|procur\w*|busc\w*|lista\w*|list[aá]\w*|relacion\w*|cad[eê]|quais|quant\w*|tem|t[eê]m|existe\w*|"
         r"varre\w*|escane\w*|scane\w*|mape\w*|descobr\w*|localiz\w*|encontr\w*|detect\w*|enxerg\w*|v[eê]|me (?:d[aá]|mostra|lista|traz)|"
         r"quero (?:ver|saber|a lista)|quais s[aã]o|me diz quais|rastre\w*)\b")
USUARIO = r"\b(usu[aá]ri\w+|contas? (?:de usu[aá]rio|do (?:pc|dom[ií]nio|windows|computador)|da rede)|pessoas? (?:da|na) rede|quem (?:usa|acessa|tem (?:conta|acesso|login)))\b"
DIAG = r"\b(diagn[oó]stic\w+|informa\w+|info|status|situa[çc][aã]o|sa[uú]de|como (?:t[aá]|est[aá]|anda|v[aã]o|vai))\b"
AJUDA = r"\b(o que (?:voc[eê]|vc|tu)? ?(?:faz|sabe|pode|consegue)|ajuda|op[çc][oõ]es|op[cç]ao|menu|comandos?|o que d[aá] pra fazer|o que tem)\b"


def entender(texto):
    t = texto or ""
    sa = _sa(t)
    if re.search(SOBRE, sa):  # "como acesso a câmera", "o que é VLAN" → é explicação, deixa pro especialista
        return None
    cam = re.search(CAMERA, sa)
    # menu de rede: "o que você faz de rede", "opções de rede", "ajuda com rede"
    if re.search(AJUDA, sa) and (re.search(REDE, sa) or cam or re.search(USUARIO, sa) or "t.i" in sa or "ti " in sa):
        return {"acao": "menu_cam" if cam and not re.search(REDE, sa) else "menu"}
    # CÂMERAS
    if cam:
        if re.search(VER, sa):
            return {"acao": "cameras_ver"}
        if re.search(ACHAR, sa):
            return {"acao": "cameras"}
        return {"acao": "menu_cam"}  # só tocou no assunto "câmera" → ofereço as opções
    # IMPRESSORAS (achar/listar na rede) — "impressora não imprime" (suporte) cai fora: sem achar/rede/ver
    if re.search(r"\b(impressor\w*|printer\w*|multifuncion\w*)\b", sa) and (re.search(ACHAR, sa) or re.search(REDE, sa) or re.search(VER, sa)):
        return {"acao": "impressoras"}
    # USUÁRIOS DE UM PC ESPECÍFICO (por IP): "lista os usuários do 192.168.0.67"
    _ip = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", t)
    if _ip and re.search(r"usu[aá]ri|contas?", sa):
        return {"acao": "usuarios_pc", "alvo": _ip.group(1)}
    # OUTROS PCs DA REDE: "ver os outros pcs", "mostra os computadores da rede", "quais máquinas tem na rede"
    if re.search(r"\b(outros?|demais|todos os|os|esses)\s+(pcs?|computadores?|m[aá]quinas|notebooks?|esta[çc][oõ]es)\b", sa) \
       or (re.search(r"\b(pcs?|computadores?|m[aá]quinas|notebooks?|esta[çc][oõ]es)\b", sa) and re.search(REDE, sa) and re.search(ACHAR, sa)) \
       or re.search(r"\b(ver|ve|vê|olha\w*|espia\w*|mostra\w*|lista\w*)\s+(?:os\s+)?(?:outros?\s+)?(pcs?|computadores?|m[aá]quinas)\b", sa):
        return {"acao": "pcs"}
    # USUÁRIOS (deste PC / do domínio)
    if re.search(USUARIO, sa) and (re.search(r"\b(rede|dom[ií]nio|pc|computador|windows|cadastrad\w*)\b", sa) or re.search(ACHAR, sa)):
        return {"acao": "usuarios"}
    # DIAGNÓSTICO / INFO
    if (re.search(DIAG, sa) and re.search(REDE, sa)) \
       or re.search(r"\b(testa\w*|testar|checa\w*|verifica\w*)\b.{0,15}\b(internet|rede|conex[aã]o|dns|wi-?fi)\b", sa) \
       or re.search(r"\b(meu|qual (?:e |é )?(?:o )?)\s*ip\b", sa) or re.search(r"^\s*(?:qual|que)\s+.*\bip\b", sa) \
       or re.search(r"\b(compartilhament\w+|pastas? (?:de |da |compartilh\w+)|net view)", sa) \
       or re.search(r"\b(internet|wi-?fi|rede) (?:t[aá]|est[aá]) (?:boa|lenta|ca[ií]ndo|funcionando|ok|ruim|p[eé]ssima|instável|instavel)\b", sa):
        return {"acao": "diagnostico"}
    # DISPOSITIVOS / APARELHOS
    if re.search(ACHAR, sa) and (re.search(r"\b(aparelho\w*|dispositiv\w*|equipament\w*|m[aá]quinas?|ip\w*|host\w*|celular\w*)\b", sa) and re.search(REDE, sa)
                                 or re.search(r"\bquem (?:t[aá]|est[aá]|anda).{0,12}(?:na rede|conectad\w*)", sa)
                                 or re.search(r"\b(o que|oque)\b.{0,15}\b(na rede|conectad\w*)", sa)):
        return {"acao": "dispositivos"}
    if re.search(r"\bquem (?:t[aá]|est[aá]|anda).{0,8}(?:na rede|conectad\w*|ligad\w*)", sa) \
       or re.search(r"\b(escane\w*|scane\w*|varre\w*|mape\w*|rastre\w*)\s+(?:a\s+|minha\s+|toda\s+(?:a\s+)?)?rede\b", sa) \
       or re.search(r"\bmapa da rede\b", sa):
        return {"acao": "dispositivos"}
    return None


def _linha_aparelho(a):
    tag = " (este PC)" if a["eu"] else ""
    quem = a["nome"] or a["fabricante"] or TIPO_NOME.get(a["tipo"], "aparelho")
    extra = (f" · {a['fabricante']}" if a["fabricante"] and a["nome"] else "")
    return f"{a['icone']} {a['ip']}{tag} · {quem}{extra} · {a['mac'] or 'sem MAC'}"


def executar(p):
    acao = p["acao"]

    if acao == "menu":
        linhas = ["• \"acha os aparelhos da rede\" — quem está conectado (IP, nome, fabricante, MAC)",
                  "• \"ver todos os PCs da rede\" — os computadores, nome e quem está logado",
                  "• \"acha as câmeras\" — câmeras e DVRs na rede",
                  "• \"lista os usuários da rede\" — contas deste PC e do domínio",
                  "• \"lista os usuários do <IP>\" — usuários de outro PC (com teu login de admin)",
                  "• \"diagnóstico da rede\" — IP, Wi-Fi, internet, DNS e compartilhamentos"]
        return ("Na parte de rede eu acho os aparelhos, acho as câmeras, listo os usuários e faço o diagnóstico, chefe. Qual deles?",
                [{"titulo": "T.I de rede · o que eu faço", "destaque": "escolhe", "linhas": linhas}])

    if acao == "menu_cam":
        cred = cofre.pegar("cameras") if hasattr(cofre, "pegar") else None
        tem = isinstance(cred, dict) and bool(cred.get("user"))
        linhas = ["• \"acha as câmeras\" — varro a rede e listo as câmeras/DVR",
                  "• \"mostra as câmeras\" — print ao vivo no HUD" + ("" if tem else " (preciso do login — hoje não tenho)"),
                  "• \"como recupero a senha da câmera\" — te guio o reset (Intelbras)"]
        fala = ("Sobre as câmeras, chefe, eu posso: achar elas na rede, mostrar a imagem" +
                ("" if tem else " (quando eu tiver o login)") + ", ou te ajudar a recuperar a senha. O que você quer?")
        return fala, [{"titulo": "Câmeras · o que eu posso fazer", "destaque": "escolhe", "linhas": linhas}]

    if acao == "diagnostico":
        cfg = config()
        if not cfg.get("ip"):
            return "Não consegui ler a configuração de rede deste PC, chefe. Parece sem conexão.", []
        wifi = _wifi()
        g8 = _ping_ms("8.8.8.8")
        gd = _ping_ms("google.com")
        gw_ms = _ping_ms(cfg.get("gw")) if cfg.get("gw") else None
        sh = compartilhamentos()
        linhas = [f"IP: {cfg['ip']}/{cfg.get('pfx', '?')} · {cfg.get('adaptador', '')}",
                  f"Gateway (roteador): {cfg.get('gw', '?')}" + (f" · {gw_ms} ms" if gw_ms is not None else " · não responde"),
                  f"DNS: {cfg.get('dns') or '—'}"]
        if wifi:
            linhas.append(f"Wi-Fi: {wifi['ssid']}" + (f" · sinal {wifi['sinal']}" if wifi.get("sinal") else "") + (f" · canal {wifi['canal']}" if wifi.get("canal") else ""))
        linhas.append(f"Internet (8.8.8.8): {'ok, ' + str(g8) + ' ms' if g8 is not None else 'sem resposta'}")
        linhas.append(f"DNS (google.com): {'ok, ' + str(gd) + ' ms' if gd is not None else 'sem resposta'}")
        if sh["deste_pc"]:
            linhas.append("Compartilha deste PC: " + "; ".join(sh["deste_pc"][:4]))
        if sh["na_rede"]:
            linhas.append(f"PCs na rede (net view): {', '.join(sh['na_rede'][:8])}")
        # diagnóstico em linguagem (regra do suporte-ti)
        if cfg["ip"].startswith("169.254"):
            fala = "Atenção, chefe: este PC não pegou IP do DHCP (começa com 169.254). É cabo, switch ou o roteador."
        elif gw_ms is None:
            fala = "O roteador não responde, chefe. Checa cabo/Wi-Fi e se o roteador tá ligado."
        elif g8 is None:
            fala = "Chego no roteador mas não na internet, chefe — é o link da operadora ou o roteador."
        elif gd is None:
            fala = "A internet responde por IP mas o nome não resolve: é DNS, chefe. Troca pro 8.8.8.8 ou 1.1.1.1."
        else:
            fala = f"Rede ok, chefe. IP {cfg['ip']}, internet respondendo em {g8} milissegundos." + (f" Conectado no Wi-Fi {wifi['ssid']}." if wifi else " Conexão por cabo.")
        return fala, [{"titulo": "Diagnóstico de rede", "destaque": "Rede ok" if (gw_ms is not None and g8 is not None and gd is not None) else "Atenção", "linhas": linhas}]

    if acao == "pcs":
        pcs, cfg, aparelhos, outros = pcs_da_rede()
        if not cfg.get("ip"):
            return "Não consegui ler a rede deste PC, chefe. Parece sem conexão.", []
        imp = [a for a in outros if a["tipo"] == "impressora"]
        extra_imp = f" Também vi {len(imp)} impressora{'s' if len(imp) != 1 else ''}." if imp else ""
        if not pcs:
            # ninguém abriu porta de PC: mostro todos os aparelhos classificados pra você ver as máquinas
            linhas = [_linha_aparelho(a) for a in outros]
            return (f"Não separei nenhum PC com SMB aberto agora, chefe (pode estar com firewall/compartilhamento desligado), "
                    f"mas achei {len(outros)} aparelho{'s' if len(outros) != 1 else ''} na rede.{extra_imp} Aqui está tudo:",
                    [{"titulo": "Aparelhos na rede", "destaque": f"{len(outros)} na rede", "linhas": linhas}])
        linhas = []
        for pp in pcs:
            l = f"🖥️ {pp['nome'] or pp['ip']}" + (f" · {pp['ip']}" if pp.get("nome") else "")
            if pp.get("usuario"):
                l += f" · logado: {pp['usuario']}"
            if pp.get("grupo"):
                l += f" · {pp['grupo']}"
            if pp.get("shares"):
                l += " · compartilha"
            linhas.append(l)
        comnome = [pp for pp in pcs if pp.get("nome")]
        logados = [pp["usuario"] for pp in pcs if pp.get("usuario")]
        fala = (f"Achei {len(pcs)} PC{'s' if len(pcs) != 1 else ''} na rede, chefe"
                + (": " + ", ".join(pp["nome"] for pp in comnome[:6]) if comnome else " (sem nome por enquanto)")
                + ("." if len(pcs) <= 6 else f" e mais {len(pcs) - 6}.")
                + (f" Logados: {', '.join(logados[:4])}." if logados else "")
                + extra_imp)
        return fala, [{"titulo": "PCs na rede", "destaque": f"{len(pcs)} PCs", "linhas": linhas,
                       "copiar": "Usuários de um PC: \"lista os usuários do <IP>\"."}]

    if acao == "impressoras":
        aparelhos, cfg = escanear()
        if not aparelhos:
            return "Não achei nada na rede, chefe — este PC parece sem conexão ou a varredura foi bloqueada.", []
        imp = [a for a in aparelhos if a["tipo"] == "impressora"]
        if not imp:
            return ("Não achei impressora na rede agora, chefe. Pode estar desligada, ligada por USB direto num PC, "
                    "ou numa rede/VLAN separada.", [])
        linhas = [f"🖨️ {a['ip']} · {a['nome'] or a['fabricante'] or 'impressora'} · portas {', '.join(map(str, a['portas']))} · http://{a['ip']}"
                  for a in imp]
        return (f"Achei {len(imp)} impressora{'s' if len(imp) != 1 else ''} na rede, chefe.",
                [{"titulo": "Impressoras na rede", "destaque": f"{len(imp)}", "linhas": linhas}])

    if acao == "usuarios_pc":
        ip = p["alvo"]
        info = _nbt(ip)
        linhas = []
        if info:
            if info.get("nome"):
                linhas.append(f"PC: {info['nome']}")
            if info.get("grupo"):
                linhas.append(f"Grupo/domínio: {info['grupo']}")
            if info.get("usuario"):
                linhas.append(f"Logado agora: {info['usuario']}")
            if info.get("shares"):
                linhas.append("Compartilha pasta (SMB)")
        nome_pc = (info or {}).get("nome") or ip
        # lista completa: precisa das senhas de admin (do Rafael, guardadas no cofre)
        cred = cofre.pegar("admin_logins") if hasattr(cofre, "pegar") else None
        senhas = cred.get("senhas") if isinstance(cred, dict) else None
        user = (cred.get("user") if isinstance(cred, dict) else None) or "Administrador"
        if senhas:
            lista, ok = _remoto_usuarios(ip, user, senhas)
            if lista:
                for u in lista:
                    linhas.append(f"👤 {u.get('Name')}" + (" (desativado)" if u.get("Disabled") else ""))
                return (f"No PC {nome_pc} tem {len(lista)} usuário{'s' if len(lista) != 1 else ''}, chefe. Conectei como administrador.",
                        [{"titulo": f"Usuários · {nome_pc}", "destaque": f"{len(lista)} no PC", "linhas": linhas}])
            fim = (" Nenhuma das senhas de admin que você guardou entrou nesse PC (ou o acesso remoto/WMI está desligado nele)."
                   if _porta(ip, 135, 1.0) else " O acesso remoto (WMI) está desligado nesse PC, então não dá pra puxar a lista completa daqui.")
        else:
            fim = (" Pra ver TODOS os usuários desse PC eu uso o teu login de administrador. Salva tuas senhas no cofre uma vez "
                   "(Configurações, Privacidade) que eu testo elas sozinho — o usuário eu já assumo como .\\Administrador.")
        if info:
            quem = f"Quem está logado nele agora é {info['usuario']}. " if info.get("usuario") else ""
            return f"No {nome_pc}: {quem}".strip() + fim, [{"titulo": f"PC {nome_pc}", "destaque": info.get("usuario") or ip, "linhas": linhas or [nome_pc]}]
        return f"Não consegui falar com o PC {ip}, chefe — pode estar desligado, bloqueando, ou sem NetBIOS." + fim, []

    if acao == "usuarios":
        u = usuarios()
        locais = _lista(u.get("locais"))
        linhas = []
        reais = [x for x in locais if x.get("Name") not in ("DefaultAccount", "WDAGUtilityAccount", "Convidado", "Guest")]
        for x in reais:
            est = "ativo" if x.get("Enabled") else "desativado"
            ult = f" · último {x['ultimo']}" if x.get("ultimo") else ""
            linhas.append(f"👤 {x.get('Name')} ({est}){ult}")
        dom = _lista(u.get("dominio_users"))
        nomes_net = _parse_net_user(u.get("net")) if u.get("net") else []
        if dom:
            linhas.append(f"— Domínio {u.get('nome_dominio', '')} ({len(dom)}):")
            for x in dom[:40]:
                linhas.append(f"🏫 {x.get('Name')} · {x.get('login')}" + (f" · {x['ultimo']}" if x.get("ultimo") else ""))
            if len(dom) > 40:
                linhas.append(f"… e mais {len(dom) - 40} no domínio.")
        elif nomes_net:
            linhas.append(f"— Domínio {u.get('nome_dominio', '')} ({len(nomes_net)}): " + ", ".join(nomes_net[:60]))
        if u.get("dominio"):
            fala = f"Este PC está no domínio {u.get('nome_dominio', '')}, chefe. Tem {len(reais)} usuário{'s' if len(reais) != 1 else ''} local, e {len(dom) or len(nomes_net)} no domínio."
        else:
            fala = f"Este PC não está num domínio (é {u.get('workgroup') or 'grupo de trabalho'}), chefe. Tem {len(reais)} usuário{'s' if len(reais) != 1 else ''} do Windows: " + ", ".join(x.get("Name") for x in reais[:6]) + "."
        return fala, [{"titulo": "Usuários do Windows", "destaque": (f"domínio {u.get('nome_dominio')}" if u.get("dominio") else f"{len(reais)} locais"), "linhas": linhas or ["Nenhum usuário encontrado."]}]

    # achar aparelhos / câmeras
    com_cam = acao in ("cameras", "cameras_ver")
    aparelhos, cfg = escanear(com_cameras=com_cam)
    if not aparelhos:
        return "Não achei nada na rede, chefe — este PC parece sem conexão ou a varredura foi bloqueada.", []

    if acao == "dispositivos":
        # um quadro (cartão) por tipo: PCs, câmeras, impressoras, roteador, outros
        ordem = [("pc", "🖥️ PCs na rede", "PC"), ("camera", "📷 Câmeras / DVR", "câmera"),
                 ("impressora", "🖨️ Impressoras", "impressora"), ("roteador", "📡 Roteador", None),
                 ("aparelho", "• Outros aparelhos", None)]
        cartoes, resumo = [], []
        for chave, titulo, rotulo in ordem:
            grupo = [a for a in aparelhos if a["tipo"] == chave]
            if not grupo:
                continue
            cartoes.append({"titulo": titulo, "destaque": f"{len(grupo)}",
                            "linhas": [_linha_aparelho(a) for a in grupo]})
            if rotulo:
                resumo.append(f"{len(grupo)} {rotulo}{'s' if len(grupo) != 1 else ''}")
        fala = (f"Achei {len(aparelhos)} aparelho{'s' if len(aparelhos) != 1 else ''} na rede, chefe"
                + (": " + ", ".join(resumo) + "." if resumo else ".")
                + f" Separei em {len(cartoes)} quadro{'s' if len(cartoes) != 1 else ''} por tipo.")
        return fala, cartoes

    # câmeras (achar, e mostrar se tiver login)
    cams = [a for a in aparelhos if a["camera"]]
    if not cams:
        return "Não achei câmera nenhuma na rede agora, chefe. Elas podem estar numa rede/VLAN separada, ou com as portas de vídeo fechadas.", []
    linhas = [f"{a['ip']} · {a['fabricante'] or a['nome'] or 'câmera'} · portas {', '.join(map(str, a['portas'])) or '—'} · acessar: http://{a['ip']}" for a in cams]
    cred = cofre.pegar("cameras") if hasattr(cofre, "pegar") else None
    base_fala = f"Achei {len(cams)} câmera{'s' if len(cams) != 1 else ''} na rede, chefe."

    if acao == "cameras_ver" or (acao == "cameras" and cred):
        if not (isinstance(cred, dict) and cred.get("user")):
            return (base_fala + " Mas sem o login eu não consigo mostrar a imagem, chefe — câmera exige senha mesmo na "
                    "rede, não dá pra pular. Se esqueceu, dá pra recuperar: na Intelbras, na tela do DVR tem 'Esqueci a "
                    "senha' (perguntas ou QR code pelo app ISIC/Defense), ou o Intelbras IP Utility reseta a câmera avulsa. "
                    "Quando tiver o login novo, me passa que eu guardo e mostro o print."), \
                   [{"titulo": "Câmeras na rede", "destaque": f"{len(cams)} achada(s)", "linhas": linhas}]
        imagens, ok = [], 0
        for a in cams[:6]:
            img = snapshot(a["ip"], cred)
            if img:
                imagens.append(img)
                ok += 1
        if ok:
            return (base_fala + f" Puxei o print de {ok}.", [{"titulo": "Câmeras · ao vivo", "destaque": f"{ok} de {len(cams)}",
                    "linhas": linhas, "imagens": imagens}])
        return (base_fala + " Mas não consegui o print — o login das câmeras pode estar diferente, ou o modelo usa outro caminho. "
                "Me confirma marca, usuário e senha.", [{"titulo": "Câmeras na rede", "destaque": f"{len(cams)} achada(s)", "linhas": linhas}])

    return (base_fala + " Pra ver a imagem eu preciso do login da câmera (sem senha não tem como, é por segurança). "
            "Se esqueceu, recupera pelo 'Esqueci a senha' do DVR Intelbras ou pelo IP Utility; depois me passa que eu mostro o print.",
            [{"titulo": "Câmeras na rede", "destaque": f"{len(cams)} achada(s)", "linhas": linhas}])


def salvar_login_cameras(user, senha, marca=""):
    """Guarda o login das câmeras no cofre (criptografado). Chamado quando o Rafael passar as credenciais."""
    cofre.guardar("cameras", {"user": user, "senha": senha, "marca": marca})
    return True


def salvar_logins_admin(senhas, user="Administrador"):
    """Guarda as senhas de administrador dos PCs da escola no cofre (criptografado). 'senhas' é a lista de 3-4
    possíveis (varia de PC pra PC); o Jarvis testa cada uma ao consultar um PC. Usuário padrão: .\\Administrador."""
    if isinstance(senhas, str):
        senhas = [senhas]
    cofre.guardar("admin_logins", {"user": user, "senhas": [s for s in senhas if s]})
    return True
