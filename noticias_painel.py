"""Notícias contadas pelo Jarvis, com a foto e a página da fonte DENTRO dele.

"Notícias de hoje", "mostra as notícias", "notícias de economia", "o que tá rolando sobre o Lula":
  1. lê os feeds com foto (G1 por seção, Agência Brasil, BBC Brasil, ge) e escolhe as mais recentes, misturando
     as fontes e tirando o que não é notícia ("Assista ao…", "AO VIVO", resultado de loteria);
  2. a foto vem do próprio feed; se não vier (ou vier pequena), pega a foto da matéria (og:image);
  3. o cérebro escreve, pra cada notícia, 2 frases pra contar em voz alta (citando o site);
  4. o painel com as matérias vai pra tela vertical; enquanto ele conta, a matéria da vez acende lá e a FOTO
     dela aparece grande na tela principal, perto do núcleo (as duas telas trabalham juntas).
"Abre essa notícia" / "abre a notícia 2" / "mostra a página do G1": abre a página do site dentro do Jarvis
(se o site deixar ser embutido; senão, o modo leitura com o texto e as fotos da matéria).
Cache de 10 min dos feeds.
"""
import asyncio
import html
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

import httpx

NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
             "Accept-Language": "pt-BR,pt;q=0.9"}
FEEDS = {
    "geral": [("G1", "https://g1.globo.com/rss/g1/politica/"), ("G1", "https://g1.globo.com/rss/g1/economia/"),
              ("G1", "https://g1.globo.com/rss/g1/mundo/"), ("G1", "https://g1.globo.com/rss/g1/brasil/"),
              ("Agência Brasil", "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"),
              ("BBC Brasil", "https://feeds.bbci.co.uk/portuguese/rss.xml")],
    "politica": [("G1", "https://g1.globo.com/rss/g1/politica/"), ("BBC Brasil", "https://feeds.bbci.co.uk/portuguese/rss.xml")],
    "economia": [("G1", "https://g1.globo.com/rss/g1/economia/"), ("Agência Brasil", "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml")],
    "mundo": [("G1", "https://g1.globo.com/rss/g1/mundo/"), ("BBC Brasil", "https://feeds.bbci.co.uk/portuguese/rss.xml")],
    "tecnologia": [("G1", "https://g1.globo.com/rss/g1/tecnologia/")],
    "esportes": [("ge", "https://ge.globo.com/rss/ge/")],
    "rs": [("G1 RS", "https://g1.globo.com/rss/g1/rs/rio-grande-do-sul/")],
    "saude": [("G1", "https://g1.globo.com/rss/g1/ciencia-e-saude/")],
}
TEMAS = {"politica": "politica", "política": "politica", "eleicao": "politica", "eleição": "politica", "economia": "economia",
         "dinheiro": "economia", "mundo": "mundo", "internacional": "mundo", "tecnologia": "tecnologia", "tech": "tecnologia",
         "ia": "tecnologia", "inteligencia artificial": "tecnologia", "esporte": "esportes", "esportes": "esportes",
         "futebol": "esportes", "gremio": "esportes", "grêmio": "esportes", "inter": "esportes", "rs": "rs",
         "rio grande do sul": "rs", "porto alegre": "rs", "gaucho": "rs", "saude": "saude", "saúde": "saude", "ciencia": "saude"}
LIXO = re.compile(r"^(?:assista|ao vivo|v[ií]deo|veja|ouça|podcast|resultado d[ao]|mega-sena|quina|lotof[aá]cil|hor[oó]scopo|"
                  r"previs[aã]o do tempo)\b|\bAO VIVO\b", re.I)
_cache = {}
atual = {}  # o painel de notícias na tela: {"id", "itens", "lendo"}


def _feed(fonte, url):
    c = _cache.get(url)
    if c and time.time() - c[0] < 600:
        return c[1]
    try:
        xml = httpx.get(url, headers=NAVEGADOR, timeout=8, follow_redirects=True).text
    except Exception:
        return c[1] if c else []
    itens = []
    for bloco in re.findall(r"<item\b.*?>(.*?)</item>", xml, re.S)[:30]:
        def tag(nome):
            m = re.search(rf"<{nome}\b[^>]*>(.*?)</{nome}>", bloco, re.S)
            return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip() if m else ""
        titulo = re.sub(r"\s+", " ", tag("title"))
        link = tag("link") or (re.search(r'<guid[^>]*>(https?://[^<]+)', bloco) or [None, ""])[1]
        if not titulo or not link or LIXO.search(titulo):
            continue
        imagem = (re.search(r'<media:content[^>]*url="([^"]+)"', bloco) or re.search(r"<imagem-destaque>([^<]+)<", bloco)
                  or re.search(r'<enclosure[^>]*url="([^"]+)"[^>]*type="image', bloco)
                  or re.search(r'<media:thumbnail[^>]*url="([^"]+)"', bloco)
                  or re.search(r'&lt;img[^&]*src=&quot;([^&]+)&quot;', bloco) or re.search(r'<img[^>]*src="([^"]+)"', tag("description"))
                  or [None, None])[1]
        resumo = re.sub(r"<[^>]+>", " ", tag("atom:subtitle") or tag("description"))
        resumo = re.sub(r"\s+", " ", html.unescape(resumo)).strip()[:400]
        try:
            quando = parsedate_to_datetime(tag("pubDate")).timestamp()
        except Exception:
            quando = 0
        itens.append({"titulo": titulo, "url": link.strip(), "fonte": fonte, "imagem": imagem, "resumo": resumo,
                      "quando": quando, "foto_pequena": "/240/" in (imagem or "") or "thumbnail" in (imagem or "")})
    _cache[url] = (time.time(), itens)
    return itens


def _og_image(url):
    try:
        r = httpx.get(url, headers=NAVEGADOR, timeout=5, follow_redirects=True)
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', r.text) or \
            re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', r.text)
        return html.unescape(m.group(1)) if m else None
    except Exception:
        return None


def escolher(tema="", n=5):
    """As n notícias mais recentes do tema, misturando as fontes."""
    chave = TEMAS.get((tema or "").lower().strip(), "geral" if not tema else None)
    feeds = FEEDS.get(chave or "geral")
    with ThreadPoolExecutor(6) as ex:
        listas = list(ex.map(lambda f: _feed(*f), feeds))
    todas = [i for lista in listas for i in lista]
    if tema and not chave:  # assunto livre ("Lula", "dólar"): filtra pelas palavras
        palavras = [p for p in re.findall(r"\w{3,}", tema.lower())]
        with ThreadPoolExecutor(6) as ex:
            todas = [i for lista in ex.map(lambda f: _feed(*f), FEEDS["geral"] + FEEDS["esportes"] + FEEDS["tecnologia"])
                     for i in lista]
        todas = [i for i in todas if any(p in (i["titulo"] + " " + i["resumo"]).lower() for p in palavras)]
    vistos, unicas = set(), []
    for i in sorted(todas, key=lambda x: -x["quando"]):
        chave_t = re.sub(r"\W+", "", i["titulo"].lower())[:50]
        if chave_t not in vistos:
            vistos.add(chave_t)
            unicas.append(i)
    # mistura as fontes: uma de cada, na ordem de recência
    por_fonte, saida = {}, []
    for i in unicas:
        por_fonte.setdefault(i["fonte"], []).append(i)
    while len(saida) < n and any(por_fonte.values()):
        for fonte in list(por_fonte):
            if por_fonte[fonte] and len(saida) < n:
                saida.append(por_fonte[fonte].pop(0))
    # foto que faltou (ou miniatura) vem da própria matéria
    faltam = [i for i in saida if not i["imagem"] or i["foto_pequena"]]
    with ThreadPoolExecutor(5) as ex:
        for i, img in zip(faltam, ex.map(lambda x: _og_image(x["url"]), faltam)):
            i["imagem"] = img or i["imagem"]
    return saida


async def contar(tema=""):
    """Monta o painel e o que falar. Devolve (intro, painel, frases)."""
    import cerebro
    itens = await asyncio.to_thread(escolher, tema)
    if not itens:
        return f"Não achei notícias{(' sobre ' + tema) if tema else ''} agora, chefe.", None, []
    lista = "\n".join(f"[{n}] ({i['fonte']}) {i['titulo']} — {i['resumo']}" for n, i in enumerate(itens, 1))
    pedido = ("Você é o Jarvis contando as notícias pro Rafael, em voz alta, tom de conversa (português do Brasil). "
              "Para CADA notícia abaixo escreva 1 ou 2 frases curtas, dizendo o essencial e de qual site é "
              "(\"segundo o G1…\", \"a BBC conta que…\"). Só o que está no texto — não invente nada. "
              'Responda em JSON: {"falas": ["...", "..."]} na mesma ordem.\n\n' + lista)
    falas = []
    try:
        bruto = await cerebro.completar([{"role": "user", "content": pedido}], json_mode=True, temperatura=0.3, max_tokens=900)
        falas = json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1]).get("falas", [])
    except Exception:
        pass
    if len(falas) != len(itens):
        falas = [f"{i['titulo']}, segundo o {i['fonte']}." for i in itens]
    for i, f in zip(itens, falas):
        i["fala"] = f
    painel = {"id": "n" + uuid.uuid4().hex[:8], "tema": tema or "de hoje", "itens": itens}
    atual.clear()
    atual.update({"id": painel["id"], "itens": itens, "lendo": 0})
    intro = (f"As notícias {('sobre ' + tema) if tema and not TEMAS.get(tema.lower()) else ('de ' + tema) if tema else 'de agora'}, "
             f"chefe. Vou te contando.")
    return intro, painel, falas


def da_vez(n=None):
    """A notícia n (1…) ou a que está sendo contada agora."""
    itens = atual.get("itens") or []
    if not itens:
        return None
    if n is None:
        return itens[min(atual.get("lendo", 0), len(itens) - 1)]
    return itens[n - 1] if 0 < n <= len(itens) else (itens[-1] if n < 0 else None)


def embutivel(url):
    """O site deixa ser mostrado dentro do Jarvis (iframe)? Olha X-Frame-Options e CSP frame-ancestors."""
    try:
        r = httpx.get(url, headers=NAVEGADOR, timeout=6, follow_redirects=True)
    except Exception:
        return False
    xfo = (r.headers.get("x-frame-options") or "").lower()
    csp = (r.headers.get("content-security-policy") or "").lower()
    if xfo in ("deny", "sameorigin"):
        return False
    m = re.search(r"frame-ancestors([^;]*)", csp)
    if m and "*" not in m.group(1):
        return False
    return True
