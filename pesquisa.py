"""Pesquisa na internet: "pesquisa X" abre a busca de X INTEIRO no navegador, na hora.

Regras que o Rafael passou (19/10):
- "pesquisa BMW X1" é a BMW X1, não a marca BMW: nada de resumo da Wikipédia, abre o Google com tudo.
- "pesquisa no Opera GX tal coisa", "pesquisa tal coisa no chrome", "abre o opera e pesquisa tal coisa":
  é pra pesquisar NAQUELE navegador, não abrir o navegador e digitar o nome dele.
- Porthon só se ele falar do Porthon (isso é do porthon_busca, que roda antes).
"""
import re
from urllib.parse import quote_plus

import navegadores

NAVEGADOR = r"(?P<nav>opera(?:\s*gx)?|google chrome|chrome|edge|navegador)"
SITES = {  # onde pesquisar → endereço da busca
    "youtube": "https://www.youtube.com/results?search_query=",
    "mercado livre": "https://lista.mercadolivre.com.br/",
    "github": "https://github.com/search?q=",
    "google imagens": "https://www.google.com/search?tbm=isch&q=",
    "google": "https://www.google.com/search?q=",
    "internet": "https://www.google.com/search?q=",
}
SITE = r"(?P<site>youtube|mercado livre|github|google imagens|google|internet)"
ONDE_NAV = re.compile(rf"\s*\b(?:no|na|pelo|pela|com o|usando o|l[aá] no)\s+{NAVEGADOR}\b\s*", re.I)
ONDE_SITE = re.compile(rf"\s*\b(?:no|na|pelo|pela|l[aá] no)\s+{SITE}\b\s*", re.I)
# "abre o opera e pesquisa X", "entra no chrome e procura X", "vai no youtube e busca X"
ABRE_E = re.compile(rf"^(?:abre|abra|abrir|entra|entre|vai|vá)\s+(?:no|na|o|a)?\s*(?:{NAVEGADOR}|{SITE})\s+(?:e\s+|pra\s+|para\s+)?", re.I)
VERBO = re.compile(r"^(?:pesquis[ae]r?|procur[ae]r?|busc[ae]r?|googl[ae]r?|joga no google|"
                   r"d[aá] uma (?:pesquisada|procurada|olhada|googlada|buscada)|faz uma pesquisa|"
                   r"v[eê](?= ))\s*(?:(?:sobre|por|a respeito de|pra mim|em|no|na)\s+)?", re.I)
PRECO = re.compile(r"^(?:quanto (?:custa|t[aá]|est[aá]|sai|vale)|qual (?:[eé] )?o (?:pre[cç]o|valor)|pre[cç]o d[aeo]s?)\s+", re.I)
ENFEITES = re.compile(r"^(?:jarvis|bah|tch[eê]|a[ií]|ent[aã]o|por favor|me)[\s,]+|[\s,]+(?:pra mim|a[ií]|por favor|jarvis|tch[eê])[.!?]*$", re.I)
ARTIGO = re.compile(r"^(?:o|a|os|as|um|uma|uns|umas)\s+", re.I)
PORTHON = re.compile(r"p[oó]rth?on", re.I)


def _limpar(t):
    anterior = None
    while anterior != t:
        anterior, t = t, ENFEITES.sub("", t.strip()).strip()
    return t


def entender(texto):
    """{"termo", "nav", "site"} ou None. "pesquisa bmw x1 no opera gx" → termo "bmw x1", nav "opera"."""
    t = _limpar(texto)
    nav = site = None
    m = ABRE_E.match(t)
    if m:
        nav, site = m.group("nav"), m.group("site")
        t = t[m.end():]
        if not VERBO.match(t):
            return None  # "abre o chrome" sozinho é pra abrir, não pesquisar
    for _ in range(2):  # o navegador e o site podem vir no começo, no meio ou no fim
        m = ONDE_NAV.search(t)
        if m and not nav:
            nav, t = m.group("nav"), (t[:m.start()] + " " + t[m.end():]).strip()
        m = ONDE_SITE.search(t)
        if m and not site:
            site, t = m.group("site"), (t[:m.start()] + " " + t[m.end():]).strip()
    t = re.sub(r"\s{2,}", " ", t).strip()
    verbo = VERBO.match(t)
    if verbo:
        if verbo.group(0).lower().startswith(("v", "d")) and not (nav or site):
            return None  # "vê se…" / "dá uma olhada" sem dizer onde não é pesquisa
        termo = t[verbo.end():]
    elif PRECO.match(t):
        termo = t  # "quanto custa uma bmw x1": pesquisa a frase inteira, o Google entende
    else:
        return None
    if PORTHON.search(termo) and not (nav or site):
        return None  # falou do Porthon: quem pesquisa é o porthon_busca
    termo = ARTIGO.sub("", _limpar(termo.strip(" .!?,"))).strip()
    if not termo:
        return None
    nav = None if not nav or nav.lower() == "navegador" else nav.lower()
    return {"termo": termo, "nav": nav, "site": site.lower() if site else None}


def nome_do_navegador(nav):
    if not nav:
        return ""
    return "Opera GX" if "opera" in nav else "Chrome" if "chrome" in nav else "Edge"


def rota(p):
    """Texto curto que o treino.py confere."""
    partes = ["pesquisa " + p["termo"]]
    if p["site"] and p["site"] not in ("google", "internet"):
        partes.append("no " + p["site"])
    if p["nav"]:
        partes.append("no " + ("opera" if "opera" in p["nav"] else "chrome" if "chrome" in p["nav"] else "edge"))
    return " ".join(partes)


def executar(p):
    base = SITES.get(p["site"] or "google")
    nav = "opera" if p["nav"] and "opera" in p["nav"] else "chrome" if p["nav"] and "chrome" in p["nav"] else p["nav"]
    navegadores.abrir(base + quote_plus(p["termo"]), nav)
    onde = ""
    if p["site"] and p["site"] not in ("google", "internet"):
        onde = " no " + ("YouTube" if p["site"] == "youtube" else p["site"].title())
    if p["nav"]:
        onde += " no " + nome_do_navegador(p["nav"])
    return f"Pesquisando {p['termo']}{onde}, chefe."
