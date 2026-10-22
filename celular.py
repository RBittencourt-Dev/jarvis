"""O celular dele (iPhone 15, 256 GB) pro Jarvis: holograma, o que dá pra saber dele e onde ele está.

Pedido dele (22/10): "holograma do iPhone 15 256, saber quanto de memória tô usando, e buscar com a localização do
celular, no PC e no celular".
O que uma página no iPhone consegue mandar (celular.html → POST /api/celular/estado): a LOCALIZAÇÃO (com a permissão
dele) e a versão do iOS. Bateria vem só por um Atalho da Siri (Ajustes do iPhone não deixa site ler). O espaço usado
nem Atalho lê: ele fala ("tô usando 180 giga no celular") e fica guardado.
A localização fresca (até 20 min) vira o "aqui" das buscas ("farmácia perto de mim", "onde eu tô") no PC e no celular.
"""
import json
import math
import re
import threading
import time
import unicodedata
from pathlib import Path

import httpx

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "celular.json"
DEMORA = False
FRESCA = 20 * 60  # localização mais velha que isso não vale como "aqui"
PI = math.pi

APARELHO = {"modelo": "iPhone 15", "armazenamento_gb": 256, "ram_gb": 6, "chip": "A16 Bionic",
            "tela": "6,1 polegadas Super Retina XDR OLED, 2556 por 1179, 60 Hz, com Dynamic Island",
            "camera": "principal de 48 MP e ultra-angular de 12 MP; frontal de 12 MP", "bateria_mah": 3349,
            "conector": "USB-C (velocidade USB 2)"}


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def estado():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(e):
    ARQUIVO.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")


def _km(a, b):
    dy = (a["lat"] - b["lat"]) * 111
    dx = (a["lng"] - b["lng"]) * 111 * math.cos(math.radians(a["lat"]))
    return (dx * dx + dy * dy) ** 0.5


def _cidade(lat, lng):
    """Bairro/cidade do ponto (Nominatim), só quando ele andou: "onde eu tô" fala o nome, não só número."""
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/reverse", timeout=8,
                      params={"lat": lat, "lon": lng, "format": "json", "zoom": 16, "accept-language": "pt-BR"},
                      headers={"User-Agent": "Jarvis-pessoal/1.0"}).json()
        a = r.get("address") or {}
        e = estado()
        if e.get("local") and abs(e["local"]["lat"] - lat) < 1e-6:
            e["local"].update(bairro=a.get("suburb") or a.get("neighbourhood") or a.get("quarter") or "",
                              cidade=a.get("city") or a.get("town") or a.get("village") or "",
                              rua=a.get("road") or "", completo=r.get("display_name", ""))
            _gravar(e)
    except Exception:
        pass


def receber(d):
    """O que a tela do celular (ou o Atalho da Siri) mandou: lat/lng/precisao, ios, bateria, carregando."""
    e = estado()
    agora = time.time()
    if isinstance(d.get("lat"), (int, float)) and isinstance(d.get("lng"), (int, float)):
        novo = {"lat": float(d["lat"]), "lng": float(d["lng"]), "precisao": float(d.get("precisao") or 0), "em": agora}
        antes = e.get("local")
        andou = not antes or _km(antes, novo) > 0.3
        if antes and not andou:
            novo.update({k: antes[k] for k in ("bairro", "cidade", "rua", "completo") if k in antes})
        e["local"] = novo
        _gravar(e)
        if andou:
            threading.Thread(target=_cidade, args=(novo["lat"], novo["lng"]), daemon=True).start()
        e = estado()
    if d.get("ios"):
        e["ios"] = str(d["ios"])[:12]
    if d.get("bateria") is not None:
        try:
            b = float(str(d["bateria"]).replace(",", ".").rstrip("%"))
            e["bateria"] = {"nivel": round(b * 100 if b <= 1 else b), "carregando": bool(d.get("carregando")), "em": agora}
        except ValueError:
            pass
    _gravar(e)
    return {"ok": True}


def aqui():
    """A localização do celular se for recente, senão None (quem chama cai na casa dele)."""
    l = estado().get("local")
    if l and time.time() - l.get("em", 0) < FRESCA:
        return l
    return None


def _ha(segundos):
    m = int(segundos // 60)
    return "agora há pouco" if m < 2 else f"há {m} minutos" if m < 60 else f"há {m // 60} hora{'s' if m >= 120 else ''}"


# ------------------------------------------------------------------ holograma do iPhone
def cena():
    e = estado()
    usado = e.get("usado_gb")
    bat = e.get("bateria")
    linhas = [("Modelo", f"{APARELHO['modelo']} · {APARELHO['armazenamento_gb']} GB"), ("Chip", f"{APARELHO['chip']} · 6 núcleos"),
              ("RAM", f"{APARELHO['ram_gb']} GB"), ("Tela", "6,1\" OLED · 60 Hz"), ("Câmeras", "48 MP + 12 MP · frontal 12 MP"),
              ("Bateria", f"{APARELHO['bateria_mah']} mAh" + (f" · {bat['nivel']}%{' carregando' if bat['carregando'] else ''} ({_ha(time.time() - bat['em'])})" if bat else "")),
              ("Armazenamento", f"{usado:g} de 256 GB usados" if usado else "256 GB (uso: me fala quanto)")]
    if e.get("ios"):
        linhas.append(("Sistema", f"iOS {e['ios']}"))
    dados = {"titulo": "TEU IPHONE", "linhas": linhas, "uso": round(usado / 256 * 100) if usado else (bat or {}).get("nivel", 0)}
    rot_arm = f"256 GB · {usado:g} usados" if usado else "Armazenamento 256 GB"
    partes = [
        {"nome": "Corpo de alumínio", "forma": "caixa", "tam": [1.5, 3.05, 0.16], "cor": "#4fe3ff", "pos": [0, 0, 0], "explode": [0, 0, -0.9], "fantasma": True},
        {"nome": "Tela OLED 6,1\"", "forma": "placa", "tam": [1.4, 2.95, 0.03], "cor": "#9ad8ff", "pos": [0, 0, 0.1], "explode": [0, 0, 1.5]},
        {"nome": "Dynamic Island", "forma": "caixa", "tam": [0.36, 0.1, 0.03], "cor": "#fff6b0", "pos": [0, 1.3, 0.13], "explode": [0, 0.35, 1.9]},
        {"nome": "Chip A16 Bionic", "forma": "caixa", "tam": [0.32, 0.32, 0.05], "cor": "#ffd23d", "pos": [0.25, 0.75, 0], "explode": [1.3, 0.5, 0.4]},
        {"nome": "RAM 6 GB", "forma": "caixa", "tam": [0.26, 0.2, 0.04], "cor": "#c77dff", "pos": [0.25, 0.45, 0], "explode": [1.4, 0.0, 0.5]},
        {"nome": rot_arm, "forma": "placa", "tam": [0.34, 0.24, 0.04], "cor": "#7cff6b", "pos": [0.25, 0.15, 0], "explode": [1.5, -0.5, 0.4]},
        {"nome": f"Bateria {APARELHO['bateria_mah']} mAh", "forma": "caixa", "tam": [1.05, 1.55, 0.07], "cor": "#2ee88a", "pos": [-0.12, -0.45, 0], "explode": [-1.3, -0.4, 0.3]},
        {"nome": "Câmeras 48 + 12 MP", "forma": "caixa", "tam": [0.62, 0.62, 0.06], "cor": "#ff5d8f", "pos": [-0.38, 1.05, -0.12], "explode": [-1.2, 0.9, -0.8]},
        {"nome": "USB-C", "forma": "caixa", "tam": [0.26, 0.06, 0.08], "cor": "#ff9b3d", "pos": [0, -1.53, 0], "explode": [0, -0.8, 0]},
    ]
    passos = [
        {"fala": "Na frente, a tela OLED de 6,1 polegadas, com a Dynamic Island lá em cima, onde aparecem os avisos.",
         "destaque": ["Tela OLED 6,1\"", "Dynamic Island"], "explodir": True},
        {"fala": "O cérebro é o chip A16 Bionic: 6 núcleos de processador, 5 de vídeo, e 6 giga de RAM do lado.",
         "destaque": ["Chip A16 Bionic", "RAM 6 GB"], "explodir": True},
        {"fala": (f"Armazenamento de 256 giga; você me disse que tá usando {usado:g}, sobra uns {256 - usado:g}."
                  if usado else "Armazenamento de 256 giga. Quanto tá usado eu não consigo ler daqui: me fala que eu guardo."),
         "destaque": [rot_arm], "explodir": True},
        {"fala": f"A bateria é de {APARELHO['bateria_mah']} miliampères" + (f", e da última vez tava em {bat['nivel']} por cento." if bat else "."),
         "destaque": [f"Bateria {APARELHO['bateria_mah']} mAh"], "explodir": True},
        {"fala": "Atrás, a câmera principal de 48 megapixels e a ultra-angular de 12. E embaixo, a entrada USB-C.",
         "destaque": ["Câmeras 48 + 12 MP", "USB-C"]},
    ]
    fala = "Teu iPhone 15 de 256 giga, chefe, desmontado."
    return {"titulo": "iPhone 15", "subtitulo": "256 GB", "zoom": 7.5, "partes": partes, "dados": dados, "intro": fala, "passos": passos}, fala


# ------------------------------------------------------------------ por voz
CEL = r"(?:celular|iphone|aifone|ai\s*fone|telefone)"
MEU = r"(?:o\s+)?(?:meu|teu|esse|este|o|do|no|d[oe]\s+meu|n[oe]\s+meu)\s+"
MOSTRAR = re.compile(r"^(?:jarvis[ ,]*)?(?:me\s+mostra|mostra|abre|como\s+(?:[eé]|t[aá])|desmonta)\s+(?:as\s+pe[cç]as\s+d[oe]\s+|o\s+holograma\s+d[oe]\s+)?"
                     + MEU + CEL + r"(?:\s+(?:por\s+dentro|inteiro|todo|em\s+3d|a[ií]))*[.!?]*$", re.I)
HOLO_CEL = re.compile(r"\bholograma\s+d[oe]\s+(?:meu\s+)?" + CEL + r"\b|\b" + CEL + r"\s+por\s+dentro\b", re.I)
ESPACO = re.compile(r"\b(?:mem[oó]ria|armazenamento|espa[cç]o|giga|gb)\b.*\b" + CEL + r"\b|\b" + CEL + r"\b.*\b(?:mem[oó]ria|armazenamento|espa[cç]o)\b", re.I)
GUARDAR_USO = re.compile(r"\b(?:t[oô]|estou|t[aá]|est[aá])\s+(?:usando|com|ocupad[oa]s?)\s+(?P<n>\d+(?:[.,]\d+)?)\s*(?:giga|gb|g)\b.*\b" + CEL
                         + r"|\b" + CEL + r"\b.*\b(?:t[aá]|est[aá]|tem|t[oô]\s+usando|uso)\s+(?:com\s+)?(?P<n2>\d+(?:[.,]\d+)?)\s*(?:giga|gb|g)\b(?:\s+usad[oa]s?)?", re.I)
BATERIA = re.compile(r"\bbateria\b.*\b" + CEL + r"\b|\b" + CEL + r"\b.*\bbateria\b", re.I)
ONDE = re.compile(r"^(?:jarvis[ ,]*)?(?:onde\s+(?:eu\s+)?(?:t[oô]|estou|que\s+eu\s+t[oô])|onde\s+(?:t[aá]|est[aá]|fica)\s+(?:o\s+)?meu\s+" + CEL +
                  r"|minha\s+localiza[cç][aã]o|me\s+mostra\s+onde\s+(?:eu\s+)?(?:t[oô]|estou))(?:\s+agora)?[?.!]*$", re.I)


def entender(texto):
    t = texto.strip()
    if ONDE.match(t):
        return {"acao": "onde"}
    m = GUARDAR_USO.search(t)
    if m:
        return {"acao": "guardar_uso", "gb": float((m.group("n") or m.group("n2")).replace(",", "."))}
    if MOSTRAR.match(t) or HOLO_CEL.search(t):
        return {"acao": "holograma"}
    if ESPACO.search(t) and re.search(r"\b(?:quanto|qual|tem|t[oô]\s+usando|sobra|livre)\b", t, re.I):
        return {"acao": "espaco"}
    if BATERIA.search(t) and re.search(r"\b(?:quanto|qual|como|tem|t[aá])\b", t, re.I):
        return {"acao": "bateria"}
    return None


def executar(p):
    import extensao
    e = estado()
    if p["acao"] == "holograma":
        c, fala = cena()
        c["id"] = f"holo{int(time.time() * 1000)}"
        extensao.publicar_tela({"apresentacao": c})
        return (" ".join([fala] + [s["fala"] for s in c["passos"]]),)
    if p["acao"] == "guardar_uso":
        gb = p["gb"]
        if not 0 < gb <= 256:
            return ("Teu iPhone tem 256 giga, chefe; esse número não fecha. Me fala de novo quanto tá usando.",)
        e["usado_gb"] = gb
        e["usado_em"] = time.time()
        _gravar(e)
        return (f"Guardado: {gb:g} de 256 giga usados no teu iPhone, sobram uns {256 - gb:g}.",)
    if p["acao"] == "espaco":
        if e.get("usado_gb"):
            dias = int((time.time() - e.get("usado_em", time.time())) // 86400)
            return (f"Teu iPhone tem 256 giga; da última vez você tava usando {e['usado_gb']:g}, sobrando uns {256 - e['usado_gb']:g}"
                    + (f". Isso foi há {dias} dias." if dias > 1 else "."),)
        return ("Teu iPhone tem 256 giga. Quanto tá usado o iPhone não deixa eu ler daqui: olha em Ajustes, Geral, Armazenamento "
                "do iPhone, e me fala \"tô usando tantos giga no celular\" que eu guardo.",)
    if p["acao"] == "bateria":
        b = e.get("bateria")
        if b and time.time() - b["em"] < 3 * 3600:
            return (f"Teu celular tava com {b['nivel']} por cento{', carregando' if b['carregando'] else ''}, {_ha(time.time() - b['em'])}.",)
        return ("A bateria o iPhone não deixa a página ler. Dá pra fazer um Atalho da Siri que me manda ela; se quiser eu te ensino.",)
    # onde eu tô
    l = aqui()
    if not l:
        return ("Não tenho a localização do teu celular agora. Abre o Jarvis no celular e deixa ele usar a localização.",)
    nome = ", ".join(x for x in (l.get("rua"), l.get("bairro"), l.get("cidade")) if x) or f"{l['lat']:.4f}, {l['lng']:.4f}"
    lugar = {"nome": l.get("bairro") or l.get("cidade") or "Teu celular", "completo": nome, "lat": l["lat"], "lng": l["lng"],
             "tipo": "endereco", "ponto": True, "altitude": 0.02}
    cid = extensao.com_id({"titulo": "Teu celular", "destaque": nome, "assunto": "localização"})["id"]
    extensao.publicar({"globo": {**lugar, "id": cid, "texto": f"Teu celular · {nome} · {_ha(time.time() - l['em'])}", "maps": True}})
    return (f"Teu celular tá em {nome}, chefe. Atualizado {_ha(time.time() - l['em'])}.",
            [{"titulo": "Teu celular", "destaque": l.get("bairro") or l.get("cidade") or "Aqui", "linhas": [nome],
              "links": [{"texto": "Abrir no Maps", "url": f"https://maps.google.com/?q={l['lat']},{l['lng']}"}]}])
