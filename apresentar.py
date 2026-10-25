"""Apresentar (25/10): resposta com informação vira uma APRESENTAÇÃO na tela — imagens e animações.

Pedido dele: "sempre que ele for me passar informações ou respostas tem que ser com imagens e animações, como se ele
estivesse me apresentando algo literalmente".

O cérebro não escreve HTML (sairia feio ou quebrado): ele manda BLOCOS e aqui vira a apresentação, sempre no mesmo
padrão bonito do Jarvis. As fotos ele pede por BUSCA ("bmw x1 2024") e eu acho (Wikimedia/Openverse, livres).

    blocos = [
      {"tipo": "capa", "titulo": "BMW X1 2024", "subtitulo": "SUV compacto", "imagem": "bmw x1 2024"},
      {"tipo": "numeros", "itens": [{"valor": "204", "rotulo": "cavalos"}, {"valor": "7,4", "sufixo": "s", "rotulo": "0 a 100"}]},
      {"tipo": "pontos", "titulo": "Destaques", "itens": ["Tela curva", "Tração integral"]},
      {"tipo": "imagens", "busca": "bmw x1 interior", "quantas": 3},
      {"tipo": "comparacao", "colunas": [{"titulo": "X1", "imagem": "bmw x1", "itens": ["..."]}, {...}]},
      {"tipo": "texto", "texto": "Parágrafo curto."},
      {"tipo": "etapas", "itens": ["Passo 1", "Passo 2"]},
    ]

Mostra num iframe isolado (mesmo do painel ao vivo, web/extensao.html). As animações são CSS (leves pro PC dele).
"""
import html as html_
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import extensao


def _e(t):
    return html_.escape(str(t or ""))


def _fotos(busca, n=1):
    """URLs de fotos livres pra uma busca (ou a própria URL, se já for uma)."""
    busca = str(busca or "").strip()
    if not busca:
        return []
    if re.match(r"^https://", busca):
        return [busca]
    try:
        import pesquisa_painel
        return [f["url"] for f in pesquisa_painel.fotos(busca, n=max(n, 2))][:n]
    except Exception:
        return []


def _numero(valor):
    """"48,4" → 48.4 pra animar a contagem (texto que não é número só aparece)."""
    t = str(valor).strip().replace(".", "").replace(",", ".")
    return t if re.fullmatch(r"-?\d+(?:\.\d+)?", t) else None


def _bloco(b, fotos):
    tipo = (b.get("tipo") or "texto").lower()
    if tipo == "capa":
        img = fotos.get(id(b), [None])[0] if fotos.get(id(b)) else None
        fundo = f'<img class="ap-capa-img" src="{_e(img)}" alt="">' if img else ""
        return (f'<section class="ap-capa ap-entra">{fundo}<div class="ap-capa-texto">'
                f'<h1>{_e(b.get("titulo"))}</h1><p>{_e(b.get("subtitulo"))}</p></div></section>')
    if tipo == "numeros":
        itens = "".join(
            f'<div class="ap-num ap-entra"><div class="ap-valor">{_e(i.get("prefixo"))}'
            f'<span {"data-contar=" + chr(34) + _numero(i.get("valor")) + chr(34) if _numero(i.get("valor")) else ""}>'
            f'{_e(i.get("valor"))}</span>{_e(i.get("sufixo"))}</div><div class="ap-rotulo">{_e(i.get("rotulo"))}</div></div>'
            for i in (b.get("itens") or [])[:6])
        return f'<section class="ap-numeros">{itens}</section>'
    if tipo in ("pontos", "etapas"):
        tag = "ol" if tipo == "etapas" else "ul"
        itens = "".join(f'<li class="ap-entra">{_e(i)}</li>' for i in (b.get("itens") or [])[:10])
        titulo = f'<h2 class="ap-entra">{_e(b.get("titulo"))}</h2>' if b.get("titulo") else ""
        return f'<section class="ap-pontos">{titulo}<{tag}>{itens}</{tag}></section>'
    if tipo == "imagens":
        imgs = "".join(f'<figure class="ap-entra"><img src="{_e(u)}" alt=""></figure>' for u in fotos.get(id(b), []))
        legenda = f'<div class="ap-rotulo">{_e(b.get("legenda"))}</div>' if b.get("legenda") else ""
        return f'<section class="ap-galeria">{imgs}</section>{legenda}' if imgs else ""
    if tipo == "comparacao":
        cols = []
        for c in (b.get("colunas") or [])[:3]:
            img = (fotos.get(id(c)) or [None])[0]
            foto = f'<img class="ap-col-img" src="{_e(img)}" alt="">' if img else ""
            itens = "".join(f"<li>{_e(i)}</li>" for i in (c.get("itens") or [])[:8])
            cols.append(f'<div class="ap-col ap-entra">{foto}<h3>{_e(c.get("titulo"))}</h3><ul>{itens}</ul></div>')
        return f'<section class="ap-comparacao">{"".join(cols)}</section>'
    return f'<section class="ap-texto ap-entra"><p>{_e(b.get("texto") or b.get("titulo"))}</p></section>'


def montar(blocos):
    """HTML da apresentação (as fotos de todos os blocos são buscadas ao mesmo tempo)."""
    pedidos = []  # (objeto, busca, quantas)
    for b in blocos:
        tipo = (b.get("tipo") or "").lower()
        if tipo == "capa" and b.get("imagem"):
            pedidos.append((b, b["imagem"], 1))
        elif tipo == "imagens":
            pedidos.append((b, b.get("busca") or (b.get("urls") or [""])[0], min(int(b.get("quantas") or 3), 4)))
            if b.get("urls"):
                pedidos[-1] = (b, None, 0)
        elif tipo == "comparacao":
            pedidos += [(c, c.get("imagem"), 1) for c in (b.get("colunas") or []) if c.get("imagem")]
    fotos = {}
    with ThreadPoolExecutor(6) as ex:
        futuros = {id(o): ex.submit(_fotos, busca, n) for o, busca, n in pedidos if busca}
        for o, _busca, _n in pedidos:
            fotos[id(o)] = futuros[id(o)].result() if id(o) in futuros else list(o.get("urls") or [])[:4]
    return "".join(_bloco(b, fotos) for b in blocos)


def apresentar(titulo: str, blocos: str):
    """Ferramenta do cérebro: blocos = JSON (lista). Põe a apresentação na tela."""
    try:
        lista = json.loads(blocos) if isinstance(blocos, str) else list(blocos)
        assert isinstance(lista, list) and lista
    except Exception:
        return 'blocos tem que ser uma lista JSON, ex.: [{"tipo": "capa", "titulo": "...", "imagem": "busca da foto"}]'
    corpo = montar([b for b in lista if isinstance(b, dict)][:12])
    pid = "apres-" + uuid.uuid4().hex[:8]
    if not extensao.aberta() and not extensao.tem_palco():
        from server import CONFIG
        extensao.abrir(CONFIG["porta"])
    for canal in ("palco",) if extensao.tem_palco() else ("extensao",):
        extensao.publicar({"vivo": {"id": pid, "titulo": titulo, "html": corpo, "estatico": True,
                                    "hora": time.strftime("%H:%M")}}, canal)
    n_fotos = corpo.count("<img")
    return f"Apresentação '{titulo}' na tela ({len(lista)} blocos, {n_fotos} fotos). Na voz, fale só o resumo."
