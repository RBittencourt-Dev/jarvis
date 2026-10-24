"""Notícias do dia (Google Notícias, RSS grátis): "notícias do dia", "notícias de tecnologia", "notícias do Grêmio",
"o que tá rolando sobre inteligência artificial". Fala as 3 primeiras manchetes; a lista com links vai pro pop-up."""
import html
import re

import httpx

DEMORA = True
TEMAS = {  # como ele fala → busca
    "tecnologia": "tecnologia", "tech": "tecnologia", "negocios": "negócios empresas", "negócios": "negócios empresas",
    "economia": "economia Brasil", "futebol": "futebol", "esporte": "esportes", "esportes": "esportes",
    "politica": "política Brasil", "política": "política Brasil", "porto alegre": "Porto Alegre", "rs": "Rio Grande do Sul",
    "rio grande do sul": "Rio Grande do Sul", "ia": "inteligência artificial", "inteligencia artificial": "inteligência artificial",
}
NOTICIAS = re.compile(r"\b(?:not[ií]cias?|manchetes?|o que (?:t[aá]|est[aá]) rolando|novidades do mundo|jornal)\b"
                      r"(?:\s+(?:de\s+hoje|do\s+dia))?(?:\s+(?:de|do|da|dos|das|sobre|em)\s+(?P<tema>.+?))?[?.!]*$", re.I)


def entender(texto):
    m = NOTICIAS.search(texto)
    if not m:
        return None
    tema = (m.group("tema") or "").strip()
    tema = re.sub(r"^(?:hoje|do dia|o|a|os|as)\s*", "", tema, flags=re.I).strip()
    return {"tema": tema}


def executar(p):
    tema = p["tema"]
    busca = TEMAS.get(tema.lower(), tema)
    url = ("https://news.google.com/rss/search?q=" + httpx.QueryParams({"q": busca + " when:1d"})["q"]
           + "&hl=pt-BR&gl=BR&ceid=BR:pt-419") if busca else "https://news.google.com/rss?hl=pt-BR&gl=BR&ceid=BR:pt-419"
    try:
        xml = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}).text
    except Exception:
        return "Não consegui puxar as notícias agora, chefe.", []
    itens = []
    for bloco in re.findall(r"<item>(.*?)</item>", xml, re.S)[:8]:
        titulo = html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", (re.search(r"<title>(.*?)</title>", bloco, re.S) or [None, ""])[1]))
        link = (re.search(r"<link>(.*?)</link>", bloco, re.S) or [None, ""])[1].strip()
        fonte = html.unescape((re.search(r"<source[^>]*>(.*?)</source>", bloco, re.S) or [None, ""])[1])
        titulo = re.sub(r"\s+-\s+[^-]+$", "", titulo).strip()  # o Google põe " - Fonte" no fim
        if titulo:
            itens.append({"titulo": titulo, "fonte": fonte, "link": link})
    if not itens:
        return f"Não achei notícias{' de ' + tema if tema else ''} agora, chefe.", []
    sobre = f" de {tema}" if tema else " do dia"
    fala = f"As principais notícias{sobre}: " + " ".join(f"{i['titulo']}." for i in itens[:3])
    cartao = {"titulo": "Notícias" + (f" · {tema}" if tema else ""), "destaque": f"{len(itens)} manchetes",
              "links": [{"texto": f"{i['titulo']} ({i['fonte']})" if i["fonte"] else i["titulo"], "url": i["link"]} for i in itens]}
    ultimo.update(itens=itens, lida=min(3, len(itens)), tema=tema)  # pra o "lê o resto"
    return fala, [cartao]


# memória da última leitura de notícias, pra "continua lendo" / "lê o resto"
ultimo = {"itens": [], "lida": 0, "tema": ""}


def resto(n=3):
    """Lê as próximas n manchetes que ainda não foram lidas (contexto: "lê o resto das notícias")."""
    itens = ultimo["itens"]
    i = ultimo["lida"]
    if not itens:
        return "Não tem lista de notícias aberta, chefe. Pede as notícias primeiro.", []
    if i >= len(itens):
        return "Já li todas, chefe. Essas eram as últimas.", []
    proximos = itens[i:i + n]
    ultimo["lida"] = i + len(proximos)
    faltam = len(itens) - ultimo["lida"]
    fala = "Continuando: " + " ".join(f"{x['titulo']}." for x in proximos)
    if faltam > 0:
        fala += f" Ainda tem mais {faltam}, é só falar continua."
    cartao = {"titulo": "Notícias" + (f" · {ultimo['tema']}" if ultimo["tema"] else ""),
              "destaque": f"{ultimo['lida']} de {len(itens)}",
              "links": [{"texto": f"{x['titulo']} ({x['fonte']})" if x["fonte"] else x["titulo"], "url": x["link"]} for x in proximos]}
    return fala, [cartao]
