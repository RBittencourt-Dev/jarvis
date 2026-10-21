"""Pesquisa que aparece DENTRO do Jarvis: painel com título, tópicos, galeria de fotos e fontes, lido em voz alta.

"Pesquisa X" / "me fala sobre X" / o cérebro usando pesquisar_e_mostrar:
  1. ao mesmo tempo: busca na web (DuckDuckGo), Wikipédia em português e fotos livres (Wikimedia Commons,
     Openverse; NASA quando as outras não acham);
  2. lê as 3 primeiras páginas (texto limpo);
  3. o cérebro resume em JSON: 2-3 frases pra falar + 4-7 tópicos, citando as fontes que usou;
  4. o painel vai pra extensão (ou pro HUD) e a voz lê os tópicos, com o tópico da vez aceso.
O navegador só abre se ele pedir ("no Google", "no navegador", "abre a fonte 2 no navegador").
Cache de 6 h por termo em dados/cache-pesquisa.json (a mesma pesquisa de novo sai na hora).
"""
import asyncio
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx

import extensao
import ferramentas_extra

RAIZ = Path(__file__).parent
CACHE = RAIZ / "dados" / "cache-pesquisa.json"
CABECALHO = {"User-Agent": "JarvisAssistente/1.0 (https://7sevencode.com.br; uso pessoal)"}
_ultimo = {}  # o último painel: "mostra mais fotos", "aprofunda isso", "lê a fonte 2"


def _cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar(termo, dados):
    c = {k: v for k, v in _cache().items() if time.time() - v.get("em", 0) < 6 * 3600}
    c[termo.lower()] = {**dados, "em": time.time()}
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ fontes

def resultados(consulta, n=6):
    r = httpx.post("https://html.duckduckgo.com/html/", data={"q": consulta, "kl": "br-pt"},
                   headers=ferramentas_extra.NAVEGADOR, timeout=10, follow_redirects=True)
    saida = []
    for bloco in r.text.split('class="result__a"')[1:n + 3]:
        link = re.search(r'href="([^"]+)"[^>]*>(.*?)</a>', bloco, re.S)
        if not link:
            continue
        href, titulo = link.groups()
        resumo = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', bloco, re.S)
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if "duckduckgo.com/y.js" in href or not href.startswith("http"):
            continue
        saida.append({"titulo": ferramentas_extra._texto_de(titulo), "url": href,
                      "resumo": ferramentas_extra._texto_de(resumo.group(1) if resumo else "")})
    return saida[:n]


def wikipedia(termo):
    try:
        busca = httpx.get("https://pt.wikipedia.org/w/api.php", headers=CABECALHO, timeout=8, params={
            "action": "query", "list": "search", "srsearch": termo, "format": "json", "srlimit": 1}).json()
        achados = busca.get("query", {}).get("search", [])
        if not achados:
            return None
        titulo = achados[0]["title"]
        s = httpx.get(f"https://pt.wikipedia.org/api/rest_v1/page/summary/{titulo.replace(' ', '_')}",
                      headers=CABECALHO, timeout=8, follow_redirects=True).json()
        if s.get("type") == "disambiguation" or not s.get("extract"):
            return None
        return {"titulo": s.get("title", titulo), "texto": s["extract"],
                "url": s.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "foto": (s.get("originalimage") or s.get("thumbnail") or {}).get("source")}
    except Exception:
        return None


def _limpo(termo):
    return re.sub(r"\b(?:de|do|da|dos|das|o|a|os|as|um|uma|sobre)\b\s*", "", termo, flags=re.I).strip() or termo


def fotos_commons(termo, n=8, pular=0):
    try:
        j = httpx.get("https://commons.wikimedia.org/w/api.php", headers=CABECALHO, timeout=10, params={
            "action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{_limpo(termo)} filetype:bitmap",
            "gsrlimit": n, "gsroffset": pular, "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": 900,
            "format": "json"}).json()
    except Exception:
        return []
    saida = []
    for p in sorted(j.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99)):
        info = (p.get("imageinfo") or [{}])[0]
        if not info.get("mime", "").startswith("image/") or not info.get("thumburl"):
            continue
        meta = info.get("extmetadata") or {}
        autor = ferramentas_extra._texto_de((meta.get("Artist") or {}).get("value", ""))[:60]
        licenca = (meta.get("LicenseShortName") or {}).get("value", "")
        legenda = ferramentas_extra._texto_de((meta.get("ImageDescription") or {}).get("value", ""))[:140] or \
            p.get("title", "").removeprefix("File:").rsplit(".", 1)[0]
        saida.append({"url": info["thumburl"], "grande": info.get("url"), "legenda": legenda,
                      "credito": " · ".join(x for x in (autor, licenca, "Wikimedia Commons") if x),
                      "pagina": info.get("descriptionurl")})
    return saida


def fotos_openverse(termo, n=8, pagina=1):
    try:
        j = httpx.get("https://api.openverse.org/v1/images/", headers=CABECALHO, timeout=7,
                      params={"q": _limpo(termo), "page_size": n, "page": pagina, "mature": "false"}).json()
    except Exception:
        return []
    return [{"url": r.get("thumbnail") or r["url"], "grande": r["url"], "legenda": (r.get("title") or "")[:140],
             "credito": " · ".join(x for x in (r.get("creator") or "", (r.get("license") or "").upper(),
                                               r.get("source") or "Openverse") if x),
             "pagina": r.get("foreign_landing_url")} for r in j.get("results", []) if r.get("url")]


def fotos_nasa(termo, n=6):
    try:
        j = httpx.get("https://images-api.nasa.gov/search", params={"q": termo, "media_type": "image"}, timeout=10).json()
    except Exception:
        return []
    saida = []
    for item in j.get("collection", {}).get("items", [])[:n]:
        dados = (item.get("data") or [{}])[0]
        link = next((l["href"] for l in item.get("links", []) if l.get("render") == "image"), None)
        if link:
            saida.append({"url": link, "grande": link, "legenda": dados.get("title", "")[:140], "credito": "NASA",
                          "pagina": f"https://images.nasa.gov/details/{dados.get('nasa_id', '')}"})
    return saida


def fotos(termo, n=8, mais=0):
    """Junta Commons + Openverse (e NASA se faltar), sem repetir."""
    with ThreadPoolExecutor(2) as ex:
        a = ex.submit(fotos_commons, termo, n, mais * n)
        b = ex.submit(fotos_openverse, termo, n, mais + 1)
        lista = a.result() + b.result()
    if len(lista) < 3:
        lista += fotos_nasa(termo)
    vistos, saida = set(), []
    for f in lista:
        if f["url"] not in vistos:
            vistos.add(f["url"])
            saida.append(f)
    # intercala as fontes: as primeiras fotos não ficam todas do mesmo lugar
    return saida[:n]


def ler(url, limite=3500):
    try:
        r = httpx.get(url, headers=ferramentas_extra.NAVEGADOR, timeout=4, follow_redirects=True)
        return ferramentas_extra._texto_de(r.text)[:limite]
    except Exception:
        return ""


# ------------------------------------------------------------------ montar o painel

async def _resumir(termo, wiki, achados, textos, foco=""):
    import cerebro
    fontes = []
    if wiki:
        fontes.append(f"[0] Wikipédia — {wiki['titulo']}: {wiki['texto'][:2500]}")
    for i, (a, t) in enumerate(zip(achados, textos), 1):
        fontes.append(f"[{i}] {a['titulo']} ({a['url']}): {(t or a['resumo'])[:3000]}")
    pedido = (
        f"Pesquisa do Rafael: \"{termo}\".{(' Foco: ' + foco) if foco else ''}\n"
        "Use SÓ as fontes abaixo. Se elas não responderem, diga isso (não invente). Responda em JSON:\n"
        '{"titulo": "título curto", "fala": "2 ou 3 frases curtas pra falar em voz alta, tom de conversa", '
        '"topicos": ["4 a 7 tópicos curtos e informativos, cada um com no máximo 25 palavras"], '
        '"fontes": [números das fontes usadas], "mapa": "nome de um lugar se o assunto for um lugar, senão vazio"}\n\n'
        + "\n\n".join(fontes))
    try:
        bruto = await cerebro.completar([{"role": "user", "content": pedido}], json_mode=True, temperatura=0.2,
                                        max_tokens=900)
        return json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1])
    except Exception:
        if wiki:
            frases = re.split(r"(?<=[.!?])\s+", wiki["texto"])
            return {"titulo": wiki["titulo"], "fala": " ".join(frases[:2]), "topicos": frases[2:7], "fontes": [0]}
        return {"titulo": termo, "fala": "Achei alguns resultados, chefe. Tão na tela.",
                "topicos": [a["resumo"] for a in achados[:5] if a["resumo"]], "fontes": list(range(1, len(achados) + 1))}


async def pesquisar(termo, foco="", usar_cache=True):
    """Monta o painel. Devolve (fala, painel)."""
    chave = (termo + "|" + foco).lower()
    if usar_cache:
        guardado = _cache().get(chave)
        if guardado and time.time() - guardado.get("em", 0) < 6 * 3600:
            painel = {**guardado["painel"], "id": "p" + uuid.uuid4().hex[:8]}
            _ultimo.update({"termo": termo, "painel": painel, "fotos_pagina": 0})
            return guardado["fala"], painel
    consulta = f"{termo} {foco}".strip()
    # as fotos são o mais lento (Openverse): correm em paralelo e NÃO seguram o painel; se não chegarem a tempo,
    # entram no painel depois (evento painel_fotos)
    fotos_t = asyncio.ensure_future(asyncio.to_thread(fotos, termo))
    achados, wiki = await asyncio.gather(asyncio.to_thread(resultados, consulta), asyncio.to_thread(wikipedia, termo),
                                         return_exceptions=True)
    achados = achados if isinstance(achados, list) else []
    wiki = wiki if isinstance(wiki, dict) else None
    # Wikipédia só entra se o artigo é mesmo do assunto (todas as palavras do termo no título)
    if wiki:
        pedidas = set(re.findall(r"\w{3,}", _limpo(termo).lower()))
        if pedidas and not pedidas <= set(re.findall(r"\w{3,}", wiki["titulo"].lower())):
            wiki = None if achados else wiki
    textos = await asyncio.gather(*[asyncio.to_thread(ler, a["url"]) for a in achados[:3]])
    textos = list(textos) + [""] * (len(achados) - len(textos))
    r = await _resumir(termo, wiki, achados, textos, foco)
    try:
        imagens = await asyncio.wait_for(asyncio.shield(fotos_t), timeout=0.4)
    except Exception:
        imagens = []
    fontes = []
    if wiki and 0 in (r.get("fontes") or [0]):
        fontes.append({"titulo": f"Wikipédia · {wiki['titulo']}", "url": wiki["url"]})
    for i, a in enumerate(achados, 1):
        if fontes and "wikipedia.org" in a["url"] and fontes[0]["titulo"].startswith("Wikipédia"):
            continue  # a Wikipédia já está na lista
        if i in (r.get("fontes") or []) or len(fontes) < 3:
            fontes.append({"titulo": a["titulo"], "url": a["url"]})
    if wiki and wiki.get("foto") and not any(f["url"] == wiki["foto"] for f in imagens):
        imagens.insert(0, {"url": wiki["foto"], "grande": wiki["foto"], "legenda": wiki["titulo"], "credito": "Wikipédia"})
    painel = {"id": "p" + uuid.uuid4().hex[:8], "titulo": r.get("titulo") or termo, "termo": termo,
              "resumo": r.get("fala", ""), "topicos": [t for t in (r.get("topicos") or []) if t][:7],
              "imagens": imagens[:8], "fontes": fontes[:6], "mapa": r.get("mapa") or ""}
    fala = r.get("fala") or "Tá na tela, chefe."
    if not fotos_t.done():
        def chegaram(t, pid=painel["id"]):
            try:
                lista = t.result()
            except Exception:
                return
            if lista:
                painel["imagens"] = lista[:8]
                _guardar(chave, {"fala": fala, "painel": painel})
                extensao.publicar_tela({"painel_fotos": {"id": pid, "imagens": lista[:8]}})
        fotos_t.add_done_callback(chegaram)
    _guardar(chave, {"fala": fala, "painel": painel})
    _ultimo.update({"termo": termo, "painel": painel, "fotos_pagina": 0})
    return fala, painel


def publicar(painel, ler_topicos=True):
    """Manda o painel pra tela. Devolve as frases que a voz vai ler (o painel acende cada uma)."""
    extensao.com_id({"id": painel["id"], "titulo": painel["titulo"], "texto": painel.get("termo", "")})
    extensao.publicar_tela({"painel": painel})
    return painel["topicos"] if ler_topicos else []


async def mais_fotos():
    if not _ultimo.get("termo"):
        return None
    _ultimo["fotos_pagina"] = _ultimo.get("fotos_pagina", 0) + 1
    novas = await asyncio.to_thread(fotos, _ultimo["termo"], 8, _ultimo["fotos_pagina"])
    if not novas:
        return "Não achei mais fotos livres disso, chefe."
    extensao.publicar_tela({"painel_fotos": {"id": _ultimo["painel"]["id"], "imagens": novas}})
    return f"Mais {len(novas)} fotos na tela, chefe."


def leitura(url):
    """Modo leitura: o texto limpo de uma página, pra mostrar dentro do Jarvis (sem abrir o navegador)."""
    try:
        r = httpx.get(url, headers=ferramentas_extra.NAVEGADOR, timeout=12, follow_redirects=True)
        bruto = r.text
    except Exception as e:
        return {"titulo": url, "paragrafos": [f"Não consegui abrir: {e}"], "url": url}
    titulo = re.search(r"(?is)<title[^>]*>(.*?)</title>", bruto)
    corpo = re.search(r"(?is)<(article|main)\b.*?</\1>", bruto)
    html_ = corpo.group(0) if corpo else bruto
    html_ = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav|aside|form|button|figure)\b.*?</\1>", " ", html_)
    blocos = re.findall(r"(?is)<(h[1-4]|p|li|blockquote|pre)\b[^>]*>(.*?)</\1>", html_)
    paragrafos = []
    for tag, conteudo in blocos:
        t = ferramentas_extra._texto_de(conteudo)
        if len(t) < 25 and not tag.startswith("h"):
            continue
        paragrafos.append(("## " if tag.startswith("h") else "• " if tag == "li" else "") + t)
    if not paragrafos:
        paragrafos = [ferramentas_extra._texto_de(html_)[:6000]]
    return {"titulo": ferramentas_extra._texto_de(titulo.group(1)) if titulo else url,
            "paragrafos": paragrafos[:120], "url": url}


def fonte_do_ultimo(n):
    fontes = (_ultimo.get("painel") or {}).get("fontes") or []
    return fontes[n - 1] if 0 < n <= len(fontes) else None
