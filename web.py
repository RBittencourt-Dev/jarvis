"""Respostas da internet que aparecem num cartão na tela do Jarvis (em vez de abrir o navegador).

Cotação (AwesomeAPI), tempo (Open-Meteo), "o que é X" (Wikipédia) e fotos (Wikimedia Commons).
Todas gratuitas e sem chave. Se não achar, quem chama abre a pesquisa no navegador.
"""
import re
import unicodedata

import httpx

CABECALHO = {"User-Agent": "JarvisAssistente/1.0 (https://7sevencode.com.br; uso pessoal)"}

COTACAO = re.compile(r"\b(?:d[oó]lar|euro|bitcoin|btc|libra|c[aâ]mbio|cota[cç][aã]o)\b", re.I)
MOEDAS = {"dolar": ("USD-BRL", "O dólar"), "euro": ("EUR-BRL", "O euro"), "bitcoin": ("BTC-BRL", "O bitcoin"),
          "btc": ("BTC-BRL", "O bitcoin"), "libra": ("GBP-BRL", "A libra")}
TEMPO = re.compile(r"\b(?:previs[aã]o do tempo|vai chover|como (?:t[aá]|est[aá]) o tempo|clima|temperatura|"
                   r"t[aá] (?:frio|calor)|quantos graus)\b", re.I)
IMAGEM = re.compile(r"\b(?:mostra|me mostra|quero ver|deixa eu ver|v[eê]|ver|abre|busca|procura|pesquisa)\s+(?:uma?s?\s+|as?\s+|os?\s+)?"
                    r"(?:imagem|imagens|fotos?|figuras?)\s+(?:de|do|da|dos|das)\s+(?:uma?\s+)?(?P<o_que>.+?)[?.!]*$", re.I)
SABER = re.compile(r"^(?:o que (?:[eé]|s[aã]o|significa)|quem (?:[eé]|foi|era|s[aã]o)|me (?:fala|conta) (?:sobre|de|do|da)|"
                   r"o que voc[eê] sabe sobre|me explica)\s+(?:o\s+|a\s+|os\s+|as\s+|um\s+|uma\s+)?"
                   r"(?P<o_que>.+?)[?.!]*$", re.I)
DAS_COISAS_DELE = re.compile(r"porthon|p[oó]rton|seven ?code|7 ?code|painel|radar|jarvis|\blead|crm|ventos do sul|jardim das palmeiras|"
                             r"reuni|caixa|meu |minha |nosso|nossa|sócio|socio|cliente|morador|placa|encomenda", re.I)
CODIGOS_DO_TEMPO = {0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado", 45: "neblina", 48: "neblina",
                    51: "garoa", 53: "garoa", 55: "garoa forte", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
                    80: "pancadas de chuva", 81: "pancadas de chuva", 82: "temporal", 95: "trovoada", 96: "trovoada com granizo"}


def reais(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cotacao(texto):
    t = texto.lower().replace("ó", "o")
    pedidas = [k for k in MOEDAS if k in t] or ["dolar"]
    pares = ",".join(dict.fromkeys(MOEDAS[k][0] for k in pedidas))
    dados = httpx.get(f"https://economia.awesomeapi.com.br/json/last/{pares}", timeout=8).json()
    falas, linhas = [], []
    for k in dict.fromkeys(pedidas):
        par, nome = MOEDAS[k]
        d = dados.get(par.replace("-", ""))
        if not d:
            continue
        valor, variacao = float(d["bid"]), float(d["pctChange"])
        falas.append(f"{nome} está {reais(valor)}")
        linhas.append(f"{nome[2:].capitalize()}: {reais(valor)} ({'+' if variacao >= 0 else ''}{variacao:.2f}% hoje)")
    falas = falas[:1] + [f[0].lower() + f[1:] for f in falas[1:]]  # "O dólar … e o euro …"
    fala = (" e ".join(falas) + " agora, chefe.") if falas else "Não consegui a cotação agora, chefe."
    return fala, [{"titulo": "Cotação", "destaque": linhas[0].split(": ")[1].split(" (")[0] if linhas else "—", "linhas": linhas}]


def tempo(cidade="Porto Alegre", lat=-30.03, lon=-51.23):
    j = httpx.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "America/Sao_Paulo", "forecast_days": 1}, timeout=8).json()
    agora, dia = j["current"], j["daily"]
    ceu = CODIGOS_DO_TEMPO.get(agora["weather_code"], "tempo variado")
    maxima, minima = round(dia["temperature_2m_max"][0]), round(dia["temperature_2m_min"][0])
    chuva = dia["precipitation_probability_max"][0] or 0
    fala = (f"Em {cidade} agora faz {round(agora['temperature_2m'])} graus, {ceu}. "
            f"Hoje a máxima é {maxima} e a mínima {minima}, com {chuva}% de chance de chuva.")
    return fala, [{"titulo": f"Tempo · {cidade}", "destaque": f"{round(agora['temperature_2m'])}°C · {ceu}",
                   "linhas": [f"Máxima {maxima}°C · mínima {minima}°C", f"Chance de chuva: {chuva}%"]}]


def palavras(x):
    x = "".join(c for c in unicodedata.normalize("NFD", x.lower()) if unicodedata.category(c) != "Mn")
    return set(re.findall(r"\w+", x))


def resumo(termo):
    """"o que é X" → resumo da Wikipédia em português, com foto quando tiver. None se não achar."""
    busca = httpx.get("https://pt.wikipedia.org/w/api.php", headers=CABECALHO, follow_redirects=True, timeout=8, params={
        "action": "query", "list": "search", "srsearch": termo, "format": "json", "srlimit": 1}).json()
    achados = busca.get("query", {}).get("search", [])
    if not achados:
        return None
    titulo = achados[0]["title"]
    # TODAS as palavras do pedido no título: "BMW X1" não pode virar o artigo da marca BMW
    pedidas = palavras(termo) - {"de", "do", "da", "dos", "das", "e", "o", "a", "os", "as", "um", "uma", "no", "na", "em"}
    if not pedidas or not pedidas <= palavras(titulo):
        return None  # o artigo não é exatamente o que ele pediu: melhor abrir a pesquisa do que falar de outra coisa
    s = httpx.get(f"https://pt.wikipedia.org/api/rest_v1/page/summary/{titulo.replace(' ', '_')}",
                  headers=CABECALHO, follow_redirects=True, timeout=8).json()
    texto = s.get("extract") or ""
    if not texto or s.get("type") == "disambiguation":
        return None
    primeira = re.split(r"(?<=[.!?])\s+", texto)[0]
    if len(primeira) > 260:  # corta numa palavra inteira, não no meio
        primeira = primeira[:260].rsplit(" ", 1)[0] + "…"
    cartao = {"titulo": "Wikipédia", "destaque": s.get("title", titulo), "texto": texto[:600]}
    if s.get("thumbnail", {}).get("source"):
        cartao["imagens"] = [s["thumbnail"]["source"]]
    return primeira, [cartao]


def imagens(termo, quantas=3):
    """Fotos livres (Wikimedia Commons) do que ele pediu. None se não achar nenhuma."""
    # "interior de bmw x1" → "interior bmw x1": o Commons procura melhor sem as palavrinhas
    termo = re.sub(r"\b(?:de|do|da|dos|das|o|a|os|as|um|uma)\b\s*", "", termo, flags=re.I).strip() or termo
    j = httpx.get("https://commons.wikimedia.org/w/api.php", headers=CABECALHO, follow_redirects=True, timeout=10, params={
        "action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{termo} filetype:bitmap",
        "gsrlimit": quantas * 2, "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": 520, "format": "json"}).json()
    paginas = sorted(j.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    urls = [p["imageinfo"][0]["thumburl"] for p in paginas
            if p.get("imageinfo") and p["imageinfo"][0].get("mime", "").startswith("image/")][:quantas]
    if not urls:
        return None
    return f"Aqui, chefe: {termo}.", [{"titulo": "Imagens", "destaque": termo, "imagens": urls, "linhas": []}]


def entender(texto):
    """("cotacao"|"tempo"|"imagem"|"saber", termo) ou None. Pesquisa com "no google/youtube" fica pro navegador."""
    t = texto.strip()
    if re.search(r"\b(?:no google|no youtube|na internet|no navegador|no github|no mercado livre|no opera|no chrome|no edge)\b", t, re.I):
        return None
    if re.search(r"\b(?:voc[eê]|vc|tu)\b", t, re.I) and not re.search(r"\bimage|foto", t, re.I):
        return None  # "quem é você" é sobre o Jarvis
    m = IMAGEM.search(t)
    if m:
        return "imagem", m.group("o_que").strip()
    m = re.match(r"^(?:me\s+)?(?:mostra|mostre)(?:\s+pra mim)?\s+(?:o|a|um|uma)\s+(?P<o_que>.+?)[?.!]*$", t, re.I)
    if m and not DAS_COISAS_DELE.search(t) and not re.search(r"\b(?:tela|monitor|janela|lista|resumo|agenda|m[uú]sica)\b", t, re.I):
        return "imagem", m.group("o_que").strip()  # "me mostra a BMW X1" = fotos no cartão da tela
    m = re.search(r"\b(?:me\s+)?mostra\s+como\s+(?:[eé]|era|fica)\s+(?:o\s+|a\s+|um\s+|uma\s+)?(?P<o_que>.+?)[?.!]*$", t, re.I)
    if m:  # "me mostra como é uma BMW X1"
        return "imagem", m.group("o_que").strip()
    if COTACAO.search(t) and re.search(r"\b(?:quanto|cota[cç][aã]o|c[aâ]mbio|t[aá]|est[aá]|valor|pre[cç]o)\b", t, re.I):
        return "cotacao", t
    if TEMPO.search(t):
        return "tempo", None
    m = SABER.match(t)
    if m and DAS_COISAS_DELE.search(t):
        return None  # é sobre as coisas dele: quem sabe é o conhecimento do Jarvis, não a Wikipédia
    if m and re.search(r"\b(?:pre[cç]os?|quanto custa|receitas?|hot[eé]is|hotel|restaurantes?|onde|como fazer|comprar|"
                       r"melhores?|perto|hor[aá]rios?|ingressos?|promo[cç][aã]o|voos?|passagens?|not[ií]cias?)\b", t, re.I):
        return None  # não é coisa de enciclopédia: vai pro navegador
    if m and len(m.group("o_que").split()) <= 8:
        return "saber", m.group("o_que").strip()
    return None


def responder(pedido):
    tipo, termo = pedido
    if tipo == "cotacao":
        return cotacao(termo)
    if tipo == "tempo":
        return tempo()
    if tipo == "imagem":
        return imagens(termo)
    return resumo(termo)
