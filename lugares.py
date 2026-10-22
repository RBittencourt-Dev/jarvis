"""Lugares no globo da extensão: países, cidades, e também restaurantes, lojas, pontos turísticos…

"me mostra o Japão", "onde fica Gramado", "onde fica o restaurante X", "aponta a Torre Eiffel no globo",
"restaurantes japoneses aqui perto".
Acha a coordenada no OpenStreetMap (Nominatim, grátis, pede identificação no User-Agent) e guarda em
lugares-conhecidos.json: o mesmo lugar de novo vai direto, sem internet. O OpenStreetMap não tem TUDO que o
Google tem: o que ele não acha vira busca no Google Maps.
"me mostra X" sem falar de lugar só vira globo se X for país/estado/cidade; "me mostra uma BMW" continua sendo foto.
"""
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote_plus

import httpx

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "lugares-conhecidos.json"
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
CASA = CONFIG.get("casa") or {"lat": -30.03, "lng": -51.23, "cidade": "Porto Alegre"}
CABECALHO = {"User-Agent": "JarvisAssistente/1.0 (https://7sevencode.com.br; uso pessoal)", "Accept-Language": "pt-BR,pt"}
TIPOS = {"country", "state", "region", "province", "city", "town", "village", "municipality", "county", "island",
         "continent", "archipelago", "administrative", "suburb", "city_district", "hamlet", "islet", "peninsula",
         "bay", "sea", "ocean", "mountain_range", "peak", "volcano", "national_park", "lake",
         "neighbourhood", "quarter", "borough"}
# quanto o globo chega perto (altitude em raios da Terra); estabelecimento e ponto turístico: 0,6
ZOOM = {"continent": 2.8, "ocean": 2.8, "sea": 2.0, "country": 1.7, "state": 1.15, "region": 1.15, "province": 1.15,
        "archipelago": 1.15, "county": 0.95}
ZOOM_PONTO = 0.6

ART = r"(?:o\s+|a\s+|os\s+|as\s+|um\s+|uma\s+)?"
EXPLICITO = re.compile(
    r"^(?:jarvis[ ,]*)?(?:(?:me\s+)?(?:mostra|mostre|mostrar|aponta|acha|localiza|marca|procura)\s+(?:no\s+(?:globo|mapa)\s+)?"
    rf"(?:onde\s+fica\s+)?{ART}(?P<lugar>.+?)\s+no\s+(?:globo|mapa)|"
    rf"onde\s+(?:fica|[eé]|est[aá])\s+{ART}(?P<lugar2>.+?)|"
    rf"(?:vai|leva|gira|roda)\s+(?:o\s+globo\s+)?(?:pra|para|at[eé])\s+{ART}(?P<lugar3>.+?)|"
    rf"(?:me\s+)?mostra\s+no\s+(?:globo|mapa)\s+{ART}(?P<lugar4>.+?)|"
    rf"(?:aponta|localiza|acha\s+no\s+mapa)\s+{ART}(?P<lugar5>.+?))[?.!]*$", re.I)
# "restaurantes japoneses aqui perto", "farmácia perto de mim": isso é pro Google Maps (o globo aponta a cidade)
PERTO = re.compile(
    r"^(?:jarvis[ ,]*)?(?:(?:me\s+)?(?:mostra|acha|procura|tem|quero|onde\s+tem|onde\s+(?:fica|[eé])\s+(?:o|a)\s+mais\s+perto)\s+)?"
    rf"{ART}(?P<o_que>(?:restaurantes?|lanchonetes?|farm[aá]cias?|mercados?|supermercados?|postos?|hot[eé]is|hotel|bares?|"
    r"padarias?|academias?|pizzarias?|hamburguerias?|shoppings?|hospitais?|hospital|cafeterias?|caf[eé]s?|lojas?|"
    r"churrascarias?|sorveterias?|oficinas?|bancos?|caixas? eletr[oô]nicos?|cinemas?|parques?|petshops?|pet shops?)"
    r"(?:\s+[^,]+?)?)\s+(?:aqui\s+)?(?:perto(?:\s+de\s+mim|\s+daqui)?|por\s+aqui|na\s+regi[aã]o|aqui\s+na\s+volta)[?.!]*$", re.I)
# "me mostra o Japão": só vira globo se o OpenStreetMap disser que é país/estado/cidade
TALVEZ = re.compile(r"^(?:jarvis[ ,]*)?(?:me\s+)?(?:mostra|mostre|acha|ache|localiza|localize)\s+(?:pra mim\s+)?(?:o\s+|a\s+|os\s+|as\s+)?(?P<lugar>[^\d]+?)[?.!]*$", re.I)
NAO_E_LUGAR = re.compile(r"\b(?:foto|fotos|imagem|imagens|carro|bmw|audi|caixa|lead|leads|reuni|tela|janela|m[uú]sica|"
                         r"porthon|painel|radar|planilha|arquivo|pasta|c[oó]digo|como|isso|aquilo|ela|ele)\b", re.I)
NAO_E_LUGAR_NUNCA = re.compile(r"\b(?:tela|monitor|extens[aã]o|janela|aba|caixa|lead|leads|reuni[aã]o|erro|arquivo|pasta|"
                               r"bot[aã]o|configura[cç][aã]o|op[cç][aã]o|senha|planilha)\b", re.I)


# os 27 estados (centro aproximado): "onde fica o Rio Grande do Sul" / "mostra SC" vão direto, sem internet
ESTADOS = {
    "acre": ("Acre", -9.0, -70.5), "alagoas": ("Alagoas", -9.6, -36.6), "amapa": ("Amapá", 1.4, -51.8),
    "amazonas": ("Amazonas", -4.2, -64.6), "bahia": ("Bahia", -12.5, -41.7), "ceara": ("Ceará", -5.2, -39.5),
    "distrito federal": ("Distrito Federal", -15.8, -47.8), "espirito santo": ("Espírito Santo", -19.6, -40.6),
    "goias": ("Goiás", -15.9, -49.8), "maranhao": ("Maranhão", -5.4, -45.4), "mato grosso": ("Mato Grosso", -12.9, -55.9),
    "mato grosso do sul": ("Mato Grosso do Sul", -20.5, -54.8), "minas gerais": ("Minas Gerais", -18.5, -44.5),
    "para": ("Pará", -3.8, -52.5), "paraiba": ("Paraíba", -7.2, -36.6), "parana": ("Paraná", -24.6, -51.6),
    "pernambuco": ("Pernambuco", -8.4, -37.9), "piaui": ("Piauí", -7.6, -42.7), "rio de janeiro": ("Rio de Janeiro", -22.3, -42.7),
    "rio grande do norte": ("Rio Grande do Norte", -5.8, -36.6), "rio grande do sul": ("Rio Grande do Sul", -29.8, -53.3),
    "rondonia": ("Rondônia", -10.9, -62.8), "roraima": ("Roraima", 2.0, -61.3), "santa catarina": ("Santa Catarina", -27.3, -50.4),
    "sao paulo": ("São Paulo", -22.3, -48.6), "sergipe": ("Sergipe", -10.6, -37.4), "tocantins": ("Tocantins", -10.2, -48.3),
}
SIGLAS = {"ac": "acre", "al": "alagoas", "ap": "amapa", "am": "amazonas", "ba": "bahia", "ce": "ceara", "df": "distrito federal",
          "es": "espirito santo", "go": "goias", "ma": "maranhao", "mt": "mato grosso", "ms": "mato grosso do sul",
          "mg": "minas gerais", "pa": "para", "pb": "paraiba", "pr": "parana", "pe": "pernambuco", "pi": "piaui",
          "rj": "rio de janeiro", "rn": "rio grande do norte", "rs": "rio grande do sul", "ro": "rondonia", "rr": "roraima",
          "sc": "santa catarina", "sp": "sao paulo", "se": "sergipe", "to": "tocantins"}


def estado(nome):
    chave = re.sub(r"^(?:o|a|estado d[eo]|estado)\s+", "", _sem_acento(nome)).strip()
    chave = SIGLAS.get(chave, chave)
    if chave in ESTADOS and not (chave in ("rio de janeiro", "sao paulo") and "estado" not in _sem_acento(nome)):
        nome_, lat, lng = ESTADOS[chave]  # "Rio de Janeiro"/"São Paulo" sem "estado" ficam pra cidade (OpenStreetMap)
        sigla = next(k for k, v in SIGLAS.items() if v == chave).upper()
        return {"nome": nome_, "completo": f"{nome_}, Brasil", "lat": lat, "lng": lng, "tipo": "state", "ponto": False,
                "altitude": 1.15, "cidade": None, "bairro": None, "sigla": sigla, "iso": "BR"}
    return None


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def _conhecidos():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _nominatim(nome, perto_de_casa=False, varios=False):
    params = {"q": nome, "format": "jsonv2", "limit": 6 if varios else 1, "addressdetails": 1, "namedetails": 1}
    if perto_de_casa:  # restaurante sem cidade: primeiro procura na região dele (ou onde o celular está)
        c = perto_de()
        params.update(viewbox=f"{c['lng'] - 1.5},{c['lat'] + 1.5},{c['lng'] + 1.5},{c['lat'] - 1.5}", bounded=1)
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/search", headers=CABECALHO, timeout=6, params=params)
        return (r.json() or []) if varios else (r.json() or [None])[0]
    except Exception:
        return [] if varios else None


def procurar(nome, qualquer=False):
    """{nome, completo, lat, lng, tipo, altitude, ponto} ou None.
    qualquer=False: só país/estado/cidade (pra "me mostra X" não pegar carro nem fruta).
    qualquer=True: também restaurante, loja, monumento… (ele disse "onde fica", "no globo", "localiza")."""
    chave = ("*" if qualquer else "") + _sem_acento(nome)
    conhecidos = _conhecidos()
    if chave in conhecidos:
        return conhecidos[chave]
    achado = None
    if qualquer:
        achado = _nominatim(nome, perto_de_casa=True)
    achado = achado or _nominatim(nome)
    lugar = _montar(achado, nome, qualquer)
    conhecidos[chave] = lugar  # guarda também o "não achei": não pergunta de novo
    ARQUIVO.write_text(json.dumps(conhecidos, ensure_ascii=False, indent=1), encoding="utf-8")
    return lugar


def _montar(achado, nome, qualquer=True):
    lugar = None
    if achado:
        tipo = achado.get("addresstype") or achado.get("type")
        e_regiao = tipo in TIPOS or achado.get("type") in TIPOS
        if (e_regiao and float(achado.get("importance") or 0) >= 0.3) or qualquer:
            partes = [p.strip() for p in achado.get("display_name", nome).split(",")]
            endereco = achado.get("address") or {}
            cidade = endereco.get("city") or endereco.get("town") or endereco.get("village") or endereco.get("state")
            if e_regiao:
                completo = partes[0] if len(partes) == 1 else f"{partes[0]}, {partes[-1]}"
            else:  # estabelecimento: nome + rua + cidade
                rua = " ".join(x for x in (endereco.get("road"), endereco.get("house_number")) if x)
                completo = ", ".join(x for x in (achado.get("name") or partes[0], rua, cidade) if x)
            lugar = {"nome": achado.get("name") or partes[0], "completo": completo, "lat": float(achado["lat"]),
                     "lng": float(achado["lon"]), "tipo": tipo, "ponto": not e_regiao,
                     "altitude": ZOOM.get(tipo, 0.85) if e_regiao else ZOOM_PONTO,
                     "cidade": cidade, "bairro": endereco.get("suburb") or endereco.get("neighbourhood"),
                     "iso": (endereco.get("country_code") or "").upper(),
                     "nome_en": (achado.get("namedetails") or {}).get("name:en")}
        if lugar and lugar["tipo"] in BAIRRO and cidade:
            lugar["completo"] = f"{lugar['nome']}, {cidade}"  # "Vila Nova, Porto Alegre" (não "…, Brasil")
    return lugar


def perto_de():
    """O "aqui" das buscas: o celular dele (localização de até 20 min), senão a casa."""
    import celular
    l = celular.aqui()
    return {**CASA, "lat": l["lat"], "lng": l["lng"], "cidade": l.get("cidade") or CASA.get("cidade")} if l else CASA


def _distancia(a, b):
    return ((a["lat"] - b["lat"]) ** 2 + (a["lng"] - b["lng"]) ** 2) ** 0.5


def _sem_repetidos(lugares):
    """O mesmo shopping às vezes vem duas vezes (o prédio e a loja): a menos de ~2 km conta como um só."""
    saida = []
    for l in lugares:
        if all(_distancia(l, o) > 0.02 for o in saida):
            saida.append(l)
    return saida


BAIRRO = {"suburb", "neighbourhood", "quarter", "city_district", "borough", "residential"}


def opcoes(nome):
    """Pra saber se precisa perguntar: ("um", lugar) | ("varios_perto", [lugares]) | ("varias_cidades", [lugares]) | None.
    Ordem: estado do Brasil (gravado) → bairro/cidade aqui na região → país/estado/cidade no mundo →
    estabelecimento (rede com vários = pergunta)."""
    if estado(nome):
        return "um", estado(nome)
    era_bairro = bool(re.match(r"^\s*bairro\b", nome, re.I))
    nome = re.sub(r"^\s*bairro\s+(?:d[aeo]s?\s+)?", "", nome, flags=re.I).strip()
    alvo = _sem_acento(nome)
    mesmo_nome = lambda l: _sem_acento(l["nome"]) == alvo or _sem_acento(l["nome"]).startswith(alvo)
    # 1º: um bairro ou cidade aqui na região com esse nome ("Vila Nova", "Moinhos de Vento", "Canoas")
    perto = [x for x in (_montar(a, nome, True) for a in _nominatim(nome, perto_de_casa=True, varios=True)) if x]
    for l in perto:
        if (l["tipo"] in BAIRRO or not l["ponto"]) and mesmo_nome(l):
            return "um", {**l, "ponto": False, "altitude": 0.5 if l["tipo"] in BAIRRO else l["altitude"]}
    if era_bairro and perto:
        return "um", perto[0]
    # 2º: país, estado ou cidade no mundo (rua com nome de estado não conta)
    mundo = [x for x in (_montar(a, nome) for a in _nominatim(nome, varios=True)) if x]
    for l in mundo:
        if not l["ponto"] and (mesmo_nome(l) or l is mundo[0]):
            return "um", l
    # 3º: estabelecimento
    perto = _sem_repetidos([l for l in perto if l["ponto"]])
    if len(perto) == 1:
        return "um", perto[0]
    if len(perto) > 1:
        return "varios_perto", sorted(perto, key=lambda l: _distancia(l, perto_de()))
    longe = _sem_repetidos(mundo)
    if not longe:
        return None
    cidades = {(l.get("cidade") or "").lower() for l in longe if l["ponto"]}
    if not longe[0]["ponto"] or len(cidades) <= 1:
        return "um", longe[0]
    return "varias_cidades", longe


def escolher(nome, resposta, candidatos):
    """A resposta dele à pergunta "qual deles?": "o mais perto", "no Centro", "em Gramado"…"""
    r = _sem_acento(resposta)
    if re.search(r"mais perto|tanto faz|qualquer|o primeiro|daqui|esse mesmo|pode ser", r):
        return min(candidatos, key=lambda l: _distancia(l, perto_de())) if candidatos else None
    lugar_dito = r
    while True:
        menor = re.sub(r"^(?:perto\s+d[oa]|l[aá]\s+n[oa]|o|a|os|as|no|na|em|do|da|de|bairro|cidade|que\s+fica)\s+", "", lugar_dito).strip()
        if menor == lugar_dito:
            break
        lugar_dito = menor
    if candidatos and candidatos[0].get("tipo") == "endereco":
        cidade = next((c for c in candidatos if lugar_dito and lugar_dito in _sem_acento(c.get("cidade") or "")), None)
        return achar_endereco(f"{nome} em {cidade['cidade'] if cidade else lugar_dito}")
    batem = [c for c in candidatos  # bairro ou cidade de uma das opções
             if lugar_dito and lugar_dito in _sem_acento(f"{c.get('bairro') or ''} {c.get('cidade') or ''} {c['completo']}")]
    if batem:
        return min(batem, key=lambda l: _distancia(l, perto_de()))
    return procurar(f"{nome}, {lugar_dito}", qualquer=True)


# endereço: "acha Rua Amazonas 2500", "onde fica a Avenida Ipiranga, 1000 em Canoas"
LOGRADOURO = r"(?:rua|r\.|avenida|av\.?|travessa|tv\.?|estrada|rodovia|alameda|al\.|pra[cç]a|largo|beco|servid[aã]o|acesso)"
ENDERECO = re.compile(
    # o verbo é opcional: "Rua Amazonas 2500 Tramandaí" dito sozinho também é pra achar
    r"^(?:jarvis[ ,]*)?(?:(?:(?:me\s+)?(?:acha|ache|achar|procura|procure|localiza|localize|mostra|mostre|aponta)|onde\s+fica|"
    r"vai\s+(?:pra|para|at[eé])|leva\s+(?:pra|para))\s+)?(?:a\s+|o\s+|na\s+|no\s+)?"
    rf"(?P<end>{LOGRADOURO}\s+[^\d]+?[\s,]+(?:n[uú]mero\s+|n[ºo°]?\.?\s*)?\d+[a-z]?\b.*?)(?:\s+no\s+(?:globo|mapa))?[?.!]*$", re.I)
ABREVIACOES = [(r"^av\.?\s", "Avenida "), (r"^r\.\s", "Rua "), (r"^tv\.?\s", "Travessa "), (r"^al\.\s", "Alameda ")]


def endereco(texto):
    """O endereço dito ("Rua Amazonas 2500 em Canoas"), ou None."""
    m = ENDERECO.match(texto.strip())
    if not m:
        return None
    end = m.group("end").strip(" ,.")
    for velho, novo in ABREVIACOES:
        end = re.sub(velho, novo, end, flags=re.I)
    return end


def achar_endereco(end):
    """{…lugar, tipo: "endereco"} ou None. Sem cidade dita, primeiro na região de casa."""
    m = re.match(r"^(?P<rua>.+?)[\s,]+(?:n[uú]mero\s+|n[ºo°]?\.?\s*)?(?P<num>\d+[a-z]?)\b(?:[\s,]+(?:em|no|na|de|-)?\s*(?P<cidade>.+))?$", end, re.I)
    if not m:
        return None
    rua, num, cidade = m.group("rua").strip(" ,"), m.group("num"), (m.group("cidade") or "").strip(" ,")
    consulta = f"{rua}, {num}" + (f", {cidade}" if cidade else "")
    achado = None
    if not cidade:
        achado = _nominatim(consulta, perto_de_casa=True)
    achado = achado or _nominatim(consulta) or _nominatim(f"{rua}" + (f", {cidade}" if cidade else ""), perto_de_casa=not cidade)
    return _endereco_de(achado, rua, num)


def _endereco_de(achado, rua, num):
    if not achado:
        return None
    e = achado.get("address") or {}
    cidade_achada = e.get("city") or e.get("town") or e.get("village") or e.get("municipality") or ""
    rua_achada = e.get("road") or rua
    numero = e.get("house_number") or num
    completo = f"{rua_achada}, {numero}" + (f" · {e.get('suburb')}" if e.get("suburb") else "") + (f" · {cidade_achada}" if cidade_achada else "")
    return {"nome": f"{rua_achada}, {numero}", "completo": completo, "lat": float(achado["lat"]), "lng": float(achado["lon"]),
            "tipo": "endereco", "ponto": True, "altitude": 0.35, "cidade": cidade_achada, "bairro": e.get("suburb"),
            "numero_exato": bool(e.get("house_number"))}


def cidades_do_endereco(end):
    """Sem cidade dita: a mesma rua em mais de uma cidade da região? → [lugares] (um por cidade), senão None."""
    m = re.match(r"^(?P<rua>.+?)[\s,]+(?:n[uú]mero\s+|n[ºo°]?\.?\s*)?(?P<num>\d+[a-z]?)\b(?P<resto>.*)$", end, re.I)
    if not m or m.group("resto").strip(" ,"):
        return None  # disse a cidade: não precisa perguntar
    rua, num = m.group("rua").strip(" ,"), m.group("num")
    achados = _nominatim(f"{rua}, {num}", perto_de_casa=True, varios=True) or _nominatim(rua, perto_de_casa=True, varios=True)
    por_cidade = {}
    for a in achados:
        l = _endereco_de(a, rua, num)
        if l and l["cidade"] and l["cidade"] not in por_cidade:
            por_cidade[l["cidade"]] = l
    opcoes = sorted(por_cidade.values(), key=lambda l: _distancia(l, perto_de()))
    return opcoes if len(opcoes) > 1 else None


def satelite(lugar, metros=120):
    """Foto de satélite da quadra (Esri World Imagery, grátis pra uso pessoal), centrada no endereço."""
    import math
    d = metros / 111_320  # graus de latitude
    dl = d / max(0.2, math.cos(math.radians(lugar["lat"])))
    # 21/10: o "export" da Esri passou a dar erro 500; o servidor monta a vista com os ladrilhos (/api/vista)
    zoom = 19 if metros <= 100 else 18 if metros <= 250 else 17
    return f"/api/vista?lat={lugar['lat']:.6f}&lng={lugar['lng']:.6f}&z={zoom}"


def street_view_embutido(lat, lng, direcao=0):
    """Street View que abre DENTRO da extensão (iframe, sem chave): o Google redireciona pro /maps/embed."""
    return f"https://maps.google.com/maps?layer=c&cbll={lat},{lng}&cbp=11,{direcao % 360},0,0,0&output=svembed"


STREET = re.compile(
    r"^(?:jarvis[ ,]*)?(?:(?:abre|abra|mostra|me\s+mostra|quero\s+ver|ver)\s+(?:o\s+|a\s+)?(?:street\s*view|vis[aã]o\s+da\s+rua|rua)"
    r"(?:\s+(?:d[aeo]|na|no)\s+(?P<onde>.+?))?|(?:me\s+)?mostra\s+(?:como\s+[eé]\s+)?(?:a\s+)?(?:frente|fachada)(?:\s+d[aeo]\s+(?P<onde2>.+?))?)[?.!]*$", re.I)
FECHAR_STREET = re.compile(r"^(?:jarvis[ ,]*)?(?:fecha|fechar|tira|sai\s+d[oa]|some\s+com|esconde)\s+(?:o\s+|a\s+)?"
                           r"(?:street\s*view|vis[aã]o\s+da\s+rua|rua)[.!]*$", re.I)
GIRAR = re.compile(r"^(?:jarvis[ ,]*)?(?:vira|gira|olha|roda|mostra)\s+(?:a\s+c[aâ]mera\s+)?(?:pr[ao]|para\s+[ao]|a)?\s*"
                   r"(?P<lado>direita|esquerda|tr[aá]s|outro\s+lado|frente)[.!]*$", re.I)


def street_view(lugar):
    return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lugar['lat']},{lugar['lng']}"


# "Porto Alegre no Rio Grande do Sul", "Paris na França", "o Centro em Canoas", "Vila Nova que fica em Porto Alegre"
DENTRO = re.compile(r"\s+(?:que\s+fica\s+(?:no|na|em)|l[aá]\s+(?:no|na|em)|(?:no|na)\s+estado\s+d[eo]|no\s+pa[ií]s|"
                    r"no|na|nos|nas|em)\s+(?!frente|cima|baixo|volta|globo|mapa|tela)(?P<onde>.+)$", re.I)


def separar(nome):
    """"porto alegre no rio grande do sul" → "Porto Alegre, Rio Grande do Sul" (a busca entende "lugar, região").
    Só separa se o pedaço de fora for um lugar conhecido (estado do Brasil, país ou cidade): "Rio de Janeiro" fica inteiro."""
    m = DENTRO.search(nome)
    if not m:
        return nome
    dentro, onde = nome[:m.start()].strip(), m.group("onde").strip()
    uf = estado(onde)
    if uf:
        return f"{dentro}, {uf['nome']}"
    regiao = procurar(onde)  # país, estado ou cidade (cache: rápido na 2ª vez)
    # "Canela na serra gaúcha": "serra gaúcha" não é lugar oficial → procura só "Canela"
    return f"{dentro}, {regiao['nome']}" if regiao else dentro


def resolver(texto):
    """O que fazer com o pedido:
    ("lugar", lugar)  → globo vai até lá
    ("perto", termo)  → globo na cidade dele + Google Maps "termo perto de mim"
    ("busca", nome)   → falou de lugar mas o OpenStreetMap não achou: Google Maps procura
    None              → não é pedido de lugar"""
    t = texto.strip()
    end = endereco(t)
    if end:
        varias = cidades_do_endereco(end)
        if varias:  # "Rua Amazonas 2500" tem em Canoas e em Caxias: pergunta qual cidade
            return "perguntar", {"nome": end, "tipo": "varias_cidades", "opcoes": varias, "endereco": True}
        lugar = achar_endereco(end)
        return ("lugar", lugar) if lugar else ("busca", end)
    m = PERTO.match(t)
    if m:
        return "perto", m.group("o_que").strip()
    m = EXPLICITO.match(t)
    if m:
        nome = next(g for g in m.group("lugar", "lugar2", "lugar3", "lugar4", "lugar5") if g).strip()
        if NAO_E_LUGAR_NUNCA.search(nome):
            return None  # "vai pra outra tela", "onde fica o caixa"
        nome = separar(nome)
        achou = opcoes(nome)
        if not achou:
            return "busca", nome
        tipo, coisa = achou
        return ("lugar", coisa) if tipo == "um" else ("perguntar", {"nome": nome, "tipo": tipo, "opcoes": coisa})
    m = TALVEZ.match(t)
    if m and not NAO_E_LUGAR.search(m.group("lugar")) and len(m.group("lugar").split()) <= 9:
        nome = m.group("lugar").strip()
        separado = separar(nome)
        # disse onde fica ("o Centro em Canoas"): é lugar com certeza, vale até bairro pequeno
        lugar = estado(nome) or procurar(separado, qualquer=separado != nome) or procurar(nome)
        return ("lugar", lugar) if lugar else None
    return None


def entender(texto):
    """Só o nome (sem ir à internet): pro treino.py e pra rota."""
    t = texto.strip()
    if endereco(t):
        return endereco(t)
    m = PERTO.match(t)
    if m:
        return m.group("o_que").strip()
    m = EXPLICITO.match(t)
    if m:
        nome = next(g for g in m.group("lugar", "lugar2", "lugar3", "lugar4", "lugar5") if g).strip()
        return None if NAO_E_LUGAR_NUNCA.search(nome) else nome
    return None


SELECIONAR = re.compile(
    r"^(?:jarvis[ ,]*)?(?:seleciona|selecione|selecionar|destaca|destaque|destacar|pinta|pintar|real[cç]a|separa|isola|"
    r"acende|contorna|marca\s+o\s+territ[oó]rio)\s+(?:no\s+(?:globo|mapa)\s+)?(?:o\s+|a\s+|os\s+|as\s+)?"
    r"(?:territ[oó]rio\s+d[aeo]s?\s+|pa[ií]s\s+|estado\s+d[aeo]s?\s+)?(?P<lugar>.+?)(?:\s+(?:no|do)\s+(?:globo|mapa))?[.!]*$", re.I)
LIMPAR = re.compile(r"^(?:jarvis[ ,]*)?(?:tira|limpa|apaga|desmarca|remove)\s+(?:a\s+|as\s+)?(?:sele[cç](?:[aã]o|[oõ]es)|"
                    r"marca[cç](?:[aã]o|[oõ]es)|destaques?|o\s+globo)(?:\s+do\s+globo)?[.!]*$", re.I)


def selecionar(texto):
    """"seleciona o Brasil" → {"iso": "BR", "nome_en": "Brazil", "nome": "Brasil"}; estado → {"sigla": "RS", …}; None."""
    m = SELECIONAR.match(texto.strip())
    if not m or NAO_E_LUGAR_NUNCA.search(m.group("lugar")):
        return None
    nome = m.group("lugar").strip()
    uf = estado(nome)
    if uf:
        return {"sigla": uf["sigla"], "nome": uf["nome"], "lat": uf["lat"], "lng": uf["lng"]}
    l = procurar(nome)
    if l and l.get("tipo") in ("country", "state", "region", "province") and l.get("iso"):
        return {"iso": l["iso"], "nome_en": l.get("nome_en"), "nome": l["nome"], "lat": l["lat"], "lng": l["lng"]}
    return None


def maps(lugar):
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(lugar['completo'])}"


def maps_busca(termo, perto=False):
    import celular
    l = celular.aqui() if perto else None
    if l:  # com o celular: em volta de onde ele está, não do IP do PC
        return f"https://www.google.com/maps/search/{quote_plus(termo)}/@{l['lat']},{l['lng']},15z"
    return f"https://www.google.com/maps/search/{quote_plus(termo + (' perto de mim' if perto else ''))}"


def casa():
    c = perto_de()
    return {"nome": c.get("cidade", "Porto Alegre"), "completo": c.get("cidade", "Porto Alegre"),
            "lat": c["lat"], "lng": c["lng"], "tipo": "city", "ponto": False, "altitude": 0.85}


def foto(lugar):
    """Uma foto e uma frase do lugar (Wikipédia). None se não achar (restaurante quase nunca tem)."""
    try:
        s = httpx.get(f"https://pt.wikipedia.org/api/rest_v1/page/summary/{quote_plus(lugar['nome'].replace(' ', '_'))}",
                      headers=CABECALHO, follow_redirects=True, timeout=6).json()
    except Exception:
        return None
    imagem = (s.get("originalimage") or s.get("thumbnail") or {}).get("source")
    if not imagem or s.get("type") == "disambiguation":
        return None
    imagem = re.sub(r"/\d+px-", "/1280px-", imagem)  # a original chega a 4K: pesada à toa
    texto = re.split(r"(?<=[.!?])\s+", s.get("extract") or "")[0][:220]
    return {"imagem": imagem, "texto": texto}
