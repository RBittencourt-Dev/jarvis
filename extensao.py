"""Extensão do Jarvis: uma segunda janela dele, em tela cheia na tela vertical, onde os pop-ups aparecem em tempo real.

O servidor empurra (SSE) cada cartão, cada fala dele e cada resposta do Jarvis. Enquanto ela está aberta,
o HUD da tela principal não põe cartão em volta do núcleo (vão todos pra cá).
"Vai pra outra tela" / "abre tua extensão" abrem; "volta pra tela principal" fecha e fica lembrado
(extensao.json): a próxima abertura do Jarvis respeita a última escolha.
Cada pop-up tem id e assunto: "fecha o pop-up da BMW" fecha só aquele (na extensão ou no HUD).
"""
import asyncio
import json
import re
import subprocess
import time
import unicodedata
import uuid
from pathlib import Path

import navegadores
import telas

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "extensao.json"
TITULO = "J.A.R.V.I.S. · Extensão"
URL = "http://127.0.0.1:{porta}/extensao"
PERFIL = RAIZ / ".perfil-extensao"  # perfil próprio: o Chrome respeita posição e tela cheia (janela nova num perfil já aberto ignora)

_ouvintes = {"extensao": set(), "hud": set(), "palco": set()}  # palco = o centro da tela principal (iframe no HUD)  # filas (asyncio.Queue) de quem está com a página aberta
_laco = {"loop": None}   # o loop do servidor, pra publicar de dentro de threads (ferramentas)
_sinal = {"em": 0.0}
_esperando = []          # (quando, evento) publicados com a extensão ainda abrindo
_cartoes = []            # [{id, assunto, em}] os pop-ups na tela agora, o mais novo no fim

ABRIR = re.compile(
    r"^(?:jarvis[ ,]*)?(?:abre|abra|abrir|liga|ativa|usa|vai|vem|passa|aparece)\s+"
    r"(?:a\s+|tua\s+|sua\s+|a\s+tua\s+|a\s+sua\s+|mais\s+uma\s+|outra\s+|uma\s+)?"
    r"(?:extens[aã]o(?:\s+(?:tua|sua|do jarvis))?|janela\s+(?:tua|sua)|"
    r"(?:janela\s+)?(?:pra|para|na|tamb[eé]m na)\s+(?:a\s+)?(?:outra|segunda)\s+tela(?:\s+tamb[eé]m)?|"
    r"(?:a\s+)?(?:outra|segunda)\s+tela(?:\s+tamb[eé]m)?|as\s+duas\s+telas|nas\s+duas\s+telas|duas\s+telas)[.!]*$", re.I)
FECHAR = re.compile(
    r"^(?:jarvis[ ,]*)?(?:volta|voltar|fica|ficar|fecha|fechar|feche|tira|tirar|sai|sair|some com|esconde|desliga|apaga)\s+"
    r"(?:(?:s[oó]\s+)?(?:pra|para|na|da)\s+(?:a\s+)?(?:tela\s+principal|primeira\s+tela|tela\s+da\s+frente|outra\s+tela)|"
    # "a extensão", "tua extensão", "a extensão da outra tela", "a extensão do Jarvis" ("extenção" = Chrome escrevendo errado)
    r"(?:a\s+|tua\s+|sua\s+|a\s+tua\s+|a\s+sua\s+|essa\s+)?extens[aã]o(?:\s+(?:tua|sua|do\s+jarvis|da\s+outra\s+tela|"
    r"da\s+tela\s+vertical|de\s+l[aá]|l[aá]))?|"
    r"(?:a\s+)?(?:outra|segunda)\s+tela|(?:a\s+)?tela\s+vertical|(?:a\s+)?tela\s+(?:da|na)\s+(?:outra\s+tela|vertical)|"
    r"ela\s+(?:da|na)\s+outra\s+tela|s[oó]\s+(?:numa|em uma|na)\s+tela)(?:\s+(?:a[ií]|s[oó]|pra mim))?[.!]*$", re.I)
# "fecha o pop-up da BMW", "tira o cartão do dólar", "some com a janelinha da previsão"
FECHAR_POPUP = re.compile(
    r"^(?:jarvis[ ,]*)?(?:fecha|fechar|feche|tira|tirar|some com|remove|apaga|esconde)\s+(?:o\s+|a\s+|os\s+|as\s+|esse\s+|essa\s+)?"
    r"(?:pop\s*-?\s*ups?|cart[aã]o|cart[oõ]es|janelinhas?|quadro|quadrinho|aviso)\s+(?:d[aeo]s?|sobre(?:\s+[ao]s?)?|com\s+[ao]s?)\s+"
    r"(?P<assunto>.+?)[.!]*$", re.I)


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def preferida():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8")).get("usar", True)
    except (OSError, ValueError):
        return True  # padrão dele: já abre com as duas telas


def lembrar_escolha(usar):
    ARQUIVO.write_text(json.dumps({"usar": bool(usar)}), encoding="utf-8")


def aberta():
    return time.time() - _sinal["em"] < 6


def sinal():
    _sinal["em"] = time.time()


# ------------------------------------------------------------------ tempo real

def guardar_loop(loop):
    _laco["loop"] = loop


def publicar(evento, canal="extensao"):
    """Manda um evento pra extensão (ou pro HUD) de qualquer thread."""
    loop = _laco["loop"]
    if not loop:
        return
    if canal == "extensao" and not _ouvintes["extensao"] and not aberta() and _ouvintes["palco"]:
        canal = "palco"  # sem a tela lateral (PC de um monitor, ou fechada): o globo e os painéis vão pro centro da principal
    if canal == "extensao" and not _ouvintes["extensao"]:
        # a página pode estar abrindo agora: guarda uns segundos pra ela pegar quando conectar
        _esperando[:] = [(t, e) for t, e in _esperando if time.time() - t < 20][-10:] + [(time.time(), evento)]
        return
    for fila in list(_ouvintes[canal]):
        loop.call_soon_threadsafe(fila.put_nowait, evento)


def tem_palco():
    return bool(_ouvintes["palco"])


def canal_grande():
    """Coisa pra LER (pesquisa, notícias, página, código, Radar, apresentação): no centro da tela PRINCIPAL quando o HUD
    está aberto (pedido dele: tudo aparece na principal, o núcleo encolhe); senão na lateral; senão em volta do núcleo."""
    if tem_palco():
        return "palco"
    return "extensao" if aberta() else "hud"


def publicar_tela(evento, canal=None):
    """Evento visual (painel, notícias, página, plano, passo…). O que é "mostrado" fica lembrado pra "passa isso pra
    outra tela", arrastar entre as telas e "pode fechar"."""
    canal = canal or canal_grande()
    publicar(evento, canal)
    for tipo in ("painel", "noticias", "pagina", "leitura_pagina", "radar", "apresentacao"):
        if tipo in evento:
            lembrar_mostrado(tipo, evento[tipo], canal)


# ------------------------------------------------------------------ as duas telas
# Regra (21/10, pedido dele: "variar entre as telas"): informação curta (cotação, tempo, hora, confirmação,
# resultado rápido) aparece na tela PRINCIPAL, em volta do núcleo; coisa pra ler/ver (pesquisa, notícias,
# página, código, fotos, listas longas) vai pra tela VERTICAL. "Passa isso pra outra tela" / "traz pra cá" move.
tela_principal_visivel = {"f": lambda: True}  # o servidor troca por "o HUD está aberto e visível?"
ultimo = {}  # o último item mostrado: tipo, dado, canal, id, quando
mostrados = {}  # id → mesmo formato (pra arrastar QUALQUER item de uma tela pra outra)


def lembrar_mostrado(tipo, dado, canal):
    ultimo.clear()
    ultimo.update(tipo=tipo, dado=dict(dado), canal=canal, id=dado.get("id"), quando=time.time())
    if dado.get("id"):
        mostrados[dado["id"]] = dict(ultimo)
        while len(mostrados) > 40:
            mostrados.pop(next(iter(mostrados)))


def e_pequeno(cartao):
    return (not cartao.get("imagens") and not cartao.get("links") and not cartao.get("codigo")
            and len(cartao.get("linhas") or []) <= 4 and len(str(cartao.get("texto") or "")) <= 300)


def tela_do_cartao(cartao):
    """'aqui' (em volta do núcleo), 'palco' (centro da principal) ou 'outra' (extensão)."""
    if e_pequeno(cartao) and (tela_principal_visivel["f"]() or not aberta()):
        return "aqui"
    if tem_palco():
        return "palco"
    return "outra" if aberta() else "aqui"


def canal_de(onde):
    return {"aqui": "hud", "palco": "palco", "outra": "extensao"}.get(onde, "extensao")


def publicar_cartao(cartao, onde=None):
    """Pop-up vindo de uma ferramenta (thread): escolhe a tela pela regra acima."""
    c = com_id(cartao)
    onde = onde or tela_do_cartao(c)
    c["onde"] = onde
    canal = canal_de(onde)
    publicar({"cartao": c}, canal)
    lembrar_mostrado("cartao", c, canal)
    return c


def tem_mostrado(janela_s=600):
    return bool(ultimo) and time.time() - ultimo.get("quando", 0) < janela_s


def _na_principal(item):
    """Na principal, coisa pequena fica em volta do núcleo; o resto vai pro centro (palco)."""
    if item["tipo"] == "cartao" and e_pequeno(item["dado"]):
        return "hud"
    return "palco" if tem_palco() else "hud"


def mover_item(item, destino, porta):
    """destino 'aqui' (principal), 'outra' (a tela oposta de onde está) ou 'extensao'."""
    principal = item["canal"] in ("hud", "palco")
    if destino == "aqui":
        alvo = _na_principal(item)
    elif destino == "extensao" or principal:
        alvo = "extensao"
    else:
        alvo = _na_principal(item)
    if alvo == "extensao" and not aberta() and not telas.monitor("outra"):
        alvo = _na_principal(item)  # PC com um monitor só: tudo fica na principal
        if alvo == item["canal"]:
            return "Só tem uma tela ligada, chefe. Já tá aqui."
    if alvo == item["canal"]:
        return "Já tá nessa tela, chefe."
    if alvo == "extensao" and not aberta():
        abrir(porta)
    if item.get("id"):
        publicar({"remover": [item["id"]]}, item["canal"])
    dado = dict(item["dado"])
    if item["tipo"] == "cartao":
        dado["onde"] = {"hud": "aqui", "palco": "palco"}.get(alvo, "outra")
    publicar({item["tipo"]: dado}, alvo)
    lembrar_mostrado(item["tipo"], dado, alvo)
    return "Passei pra outra tela, chefe." if alvo == "extensao" else "Passei pra tela principal, chefe."


def mover(destino, porta):
    """Voz: "passa isso pra outra tela" / "traz pra cá" (o último item mostrado)."""
    if not tem_mostrado(1800):
        return None
    return mover_item(dict(ultimo), destino, porta)


def mover_por_id(id_, de, porta, dado=None):
    """Arrastou um item até a borda da tela: ele vai pra outra."""
    item = mostrados.get(id_)
    if not item and dado:
        item = {"tipo": "cartao", "dado": dado, "canal": {"extensao": "extensao", "palco": "palco"}.get(de, "hud"), "id": id_}
    if not item:
        return None
    item = {**item, "canal": {"extensao": "extensao", "palco": "palco", "hud": "hud"}.get(de, item["canal"])}
    return mover_item(item, "outra", porta)


def fechar_mostrado():
    """"Pode fechar": fecha o que ele acabou de mostrar, nas duas telas."""
    for canal in ("extensao", "hud", "palco"):
        publicar({"fechar_painel": "ultimo"}, canal)
        if ultimo.get("id"):
            publicar({"remover": [ultimo["id"]]}, canal)
    ultimo.clear()
    return "Fechado, chefe."


def com_id(cartao):
    """Dá id ao pop-up e anota o assunto dele (título, destaque e texto) pra poder fechar pelo nome depois."""
    c = dict(cartao)
    c.setdefault("id", "c" + uuid.uuid4().hex[:8])
    assunto = " ".join(str(c.get(k) or "") for k in ("titulo", "destaque", "texto", "assunto"))
    _cartoes[:] = [x for x in _cartoes if time.time() - x["em"] < 3 * 3600][-60:]
    _cartoes.append({"id": c["id"], "assunto": _sem_acento(assunto), "em": time.time()})
    return c


async def eventos(canal="extensao"):
    fila = asyncio.Queue()
    _ouvintes[canal].add(fila)
    if canal == "extensao":
        for t, e in _esperando:
            if time.time() - t < 20:
                fila.put_nowait(e)
        _esperando.clear()
    try:
        yield ": conectado\n\n"
        while True:
            try:
                e = await asyncio.wait_for(fila.get(), timeout=20)
                yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": vivo\n\n"  # mantém a conexão aberta
    finally:
        _ouvintes[canal].discard(fila)


def fechar_popup(assunto):
    """Fecha o(s) pop-up(s) cujo assunto bate ("bmw"); se nenhum bater, tenta uma janela que o Jarvis abriu."""
    palavras = [p for p in re.findall(r"\w+", _sem_acento(assunto)) if len(p) > 1]
    if re.fullmatch(r"\s*(tud[oa]|tod[oa]s?)\s*", _sem_acento(assunto)):
        ids = [c["id"] for c in _cartoes]
    else:
        ids = [c["id"] for c in _cartoes if palavras and all(p in c["assunto"] for p in palavras)]
    if ids:
        _cartoes[:] = [c for c in _cartoes if c["id"] not in ids]
        for canal in ("extensao", "hud", "palco"):
            publicar({"remover": ids}, canal)
        return f"Fechei o pop-up {'de ' + assunto if len(ids) == 1 else 'de ' + assunto + f' ({len(ids)})'}, chefe."
    # pode ser uma janela que ele abriu (site, pesquisa) com esse nome no título
    for hwnd in [h for h in telas.ABERTAS if telas.u.IsWindow(h)][::-1]:
        titulo = _sem_acento(telas._titulo(hwnd))
        if palavras and all(p in titulo for p in palavras) and not titulo.startswith("j.a.r.v.i.s."):
            telas.u.PostMessageW(hwnd, 0x0010, 0, 0)
            telas.ABERTAS.remove(hwnd)
            return f"Fechei a janela de {assunto}, chefe."
    return f"Não achei pop-up de {assunto} aberto, chefe."


def mostrar(titulo: str, texto: str = "", itens=None):
    """Ferramenta do cérebro: põe um pop-up na extensão (abre ela se precisar)."""
    from server import CONFIG  # porta
    if not aberta():
        abrir(CONFIG["porta"])
    if isinstance(itens, str):
        itens = [i.strip() for i in re.split(r"\n|;", itens) if i.strip()]
    publicar({"cartao": com_id({"titulo": titulo, "texto": texto, "linhas": list(itens or [])[:30]})})
    return "Mostrei na outra tela." if aberta() else "Mostrei na tela."


# ------------------------------------------------------------------ janela

def abrir(porta):
    """Abre a extensão em tela cheia na tela vertical (se já estiver aberta, só lembra a escolha)."""
    lembrar_escolha(True)
    if aberta():
        return "A extensão já tá aberta na outra tela, chefe."
    mon = telas.monitor("outra")
    if not mon:
        return "Só achei um monitor ligado, chefe."
    exe = navegadores.executavel("chrome") or navegadores.executavel(None)
    if not exe:
        return "Não achei o Chrome pra abrir a extensão, chefe."
    x, y, larg, alt = mon["area"]
    subprocess.Popen([str(exe), f"--app={URL.format(porta=porta)}", f"--user-data-dir={PERFIL}",
                      "--no-first-run", "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required",
                      "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
                      f"--window-position={x},{y}",
                      f"--window-size={larg},{alt}", "--start-fullscreen"])
    _sinal["em"] = time.time()  # conta como aberta já: os pop-ups desta resposta vão pra lá
    return "Abri a minha extensão na outra tela, chefe. Os pop-ups vão aparecer lá."


def fechar_janela():
    """Fecha a janela da extensão SEM mudar a preferência (fechou junto com a principal)."""
    publicar({"fechar": True})
    _sinal["em"] = 0.0
    for hwnd in telas._janelas_em_ordem():
        if telas._titulo(hwnd).startswith(TITULO):
            telas.u.PostMessageW(hwnd, 0x0010, 0, 0)


def fechar():
    lembrar_escolha(False)
    publicar({"fechar": True})
    _sinal["em"] = 0.0
    for hwnd in telas._janelas_em_ordem():
        if telas._titulo(hwnd).startswith(TITULO):
            telas.u.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    return "Pronto, fico só na tela principal, chefe."
