"""Instagram por voz, no navegador onde ele já está logado (nada de senha aqui, nada é postado nem enviado).

Pedido dele (22/10): "pesquisa uma conta, mostra o story, abre o direct… e saber o que eu tô pedindo depois".
O mapa do Instagram web (os endereços que abrem cada parte):
  perfil      instagram.com/<usuário>/              "abre o insta do porthon.app", "pesquisa a conta @fulano"
  busca       instagram.com/explore/search/keyword/?q=  quando ele fala um NOME (com espaço), não o @
  stories     instagram.com/stories/<usuário>/      "mostra o story dele" (dele = o último perfil aberto)
  direct      instagram.com/direct/inbox/           "abre o direct", "minhas mensagens do insta"
  reels       instagram.com/reels/   explorar  instagram.com/explore/   notificações  instagram.com/notifications/
  posts       instagram.com/<usuário>/ (a grade)    salvos  instagram.com/<eu>/saved/ (precisa do @ dele no config)
Memória curta: o último @ aberto fica em `ultimo` (10 min), pra "e o story dele?" / "abre o direct com ele".
"""
import re
import time
import unicodedata
from urllib.parse import quote

DEMORA = False
BASE = "https://www.instagram.com/"
ultimo = {"usuario": None, "em": 0.0}

INSTA = r"(?:insta(?:gram)?|ig|instagran)"
NO_INSTA = re.compile(r"\s*\b(?:no|do|pelo|na|da)\s+" + INSTA + r"\b\s*", re.I)
PERFIL = re.compile(
    r"^(?:jarvis[ ,]*)?(?:me\s+)?(?:pesquisa|procura|busca|acha|abre|mostra|entra\s+n[oa]|vai\s+n[oa]|olha)\s+"
    r"(?:a\s+|o\s+)?(?:(?:conta|perfil|instagram|insta|p[aá]gina)\b\s*|(?=@|arroba\s))(?:d[aoe]s?\s+)?(?P<quem>.+?)[.!?]*$", re.I)
STORY = re.compile(r"\b(?:story|storys|stories|st[oó]rie?s|hist[oó]rias?|status)\b", re.I)
DIRECT = re.compile(r"\b(?:direct|dire[ck]t|dm|dms|inbox|mensagens?\s+d[oe]\s+" + INSTA + r"|" + INSTA + r"\s+mensagens?)\b", re.I)
PARTES = [(re.compile(r"\breels?\b", re.I), "reels/", "os reels"),
          (re.compile(r"\bexplora(?:r)?\b|\bexplore\b", re.I), "explore/", "o explorar"),
          (re.compile(r"\bnotifica[cç](?:[aã]o|[oõ]es)\b|\bcurtidas\b|\batividade\b", re.I), "notifications/", "as notificações"),
          (re.compile(r"\bsalvos?\b", re.I), None, "os salvos"),
          (re.compile(r"\bfeed\b|\bin[ií]cio\b|\bp[aá]gina\s+inicial\b", re.I), "", "o feed")]
DELE = re.compile(r"^(?:dele|dela|desse|dessa|deste|desta|daquele|daquela|ele|ela|isso|esse|essa)$", re.I)
VERBO = re.compile(r"^(?:jarvis[ ,]*)?(?:me\s+)?(?:mostra|abre|v[eê]|ver|olha|entra|p[oõ]e|bota|quero\s+ver|deixa\s+eu\s+ver|"
                   r"pesquisa|procura|busca|acha|tem)\b", re.I)


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def usuario(dito):
    """"arroba porthon ponto app" / "@porthon.app" / "porthon.app" → "porthon.app"; nome com espaço → None (vira busca)."""
    t = _sa(dito).strip(" .!?")
    t = re.sub(r"^(?:a\s+|o\s+)?(?:conta|perfil)\s+(?:d[aoe]\s+)?", "", t)
    falado = re.match(r"^(?:arroba|@)\s*", t)
    t = re.sub(r"^(?:arroba|@)\s*", "", t)
    t = re.sub(r"\s+(?:ponto|dot)\s+", ".", t)
    t = re.sub(r"\s+(?:underline|underscore|tracinho\s+baixo|sublinhado)\s+", "_", t)
    if falado or re.fullmatch(r"[a-z0-9._]{2,30}", t):
        t = t.replace(" ", "")
        return t if re.fullmatch(r"[a-z0-9._]{2,30}", t) else None
    return None


def _quem(texto):
    """O perfil citado no pedido (ou o último aberto, com "dele")."""
    m = re.search(r"\b(?:d[aoe]s?|com\s+(?:o|a)?|pr[oa])\s+(?P<q>@?\S.*?)$", NO_INSTA.sub(" ", texto).strip(" .!?"), re.I)
    q = (m.group("q") if m else "").strip()
    q = re.sub(r"^(?:o|a)\s+", "", q)
    if not q or DELE.match(q):
        return ultimo["usuario"] if time.time() - ultimo["em"] < 600 else None, bool(q)
    return usuario(q) or q, True


def entender(texto):
    t = texto.strip()
    fala_do_insta = re.search(r"\b" + INSTA + r"\b|@\w|\barroba\s+\w", t, re.I)  # "@fulano" já é Instagram
    if STORY.search(t) and (fala_do_insta or VERBO.match(t)) and not re.search(r"\bwhats|\bzap\b", t, re.I):
        quem, citou = _quem(re.split(STORY, t, maxsplit=1)[-1])
        return {"parte": "story", "quem": quem, "citou": citou}
    if DIRECT.search(t) and (fala_do_insta or re.search(r"\bdirect|\bdm", t, re.I)) and VERBO.match(t):
        return {"parte": "direct"}
    if fala_do_insta:
        for regra, caminho, nome in PARTES:
            if regra.search(t) and VERBO.match(t):
                return {"parte": "pagina", "caminho": caminho, "nome": nome}
        m = PERFIL.match(NO_INSTA.sub(" ", t).strip())
        if m and m.group("quem").strip() and not re.match(r"(?:no|na|em|pelo|pela|numa?)\s", m.group("quem").strip(), re.I):
            return {"parte": "perfil", "quem": m.group("quem").strip()}
        # "pesquisa porthon.app no insta", "abre o fulano no instagram"
        m = re.match(r"^(?:jarvis[ ,]*)?(?:me\s+)?(?:pesquisa|procura|busca|acha|abre|mostra)\s+(?:o\s+|a\s+)?(?P<quem>.+?)\s+"
                     r"(?:no|pelo|na)\s+" + INSTA + r"[.!?]*$", t, re.I)
        if m:
            return {"parte": "perfil", "quem": m.group("quem").strip()}
    return None


def executar(p, abrir=None):
    if abrir is None:
        import navegadores
        abrir = navegadores.abrir
    if p["parte"] == "direct":
        abrir(BASE + "direct/inbox/")
        return ("Abri o seu direct do Instagram, chefe.",)
    if p["parte"] == "pagina":
        if p["caminho"] is None:  # salvos: precisa do @ dele
            import json
            from pathlib import Path
            try:
                eu = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8")).get("instagram")
            except (OSError, ValueError):
                eu = None
            if not eu:
                return ("Pra abrir os salvos eu preciso do seu @ do Instagram. Me fala: meu instagram é arroba tal.",)
            abrir(f"{BASE}{eu}/saved/")
        else:
            abrir(BASE + p["caminho"])
        return (f"Abri {p['nome']} do Instagram, chefe.",)
    if p["parte"] == "story":
        quem = p.get("quem")
        if not quem:
            return ("De quem, chefe? Me diz o @ ou pesquisa a conta primeiro.",)
        if " " in quem:  # nome, não @: abre a busca pra ele achar o @
            abrir(BASE + "explore/search/keyword/?q=" + quote(quem))
            return (f"Não sei o @ de {quem}. Abri a busca; me diz qual é que eu abro o story.",)
        _lembrar(quem)
        abrir(f"{BASE}stories/{quem}/")
        return (f"Abrindo os stories de {quem}. Se não abrir nada, é porque não tem story agora.",)
    quem = p["quem"]
    u = usuario(quem)
    if u:
        _lembrar(u)
        abrir(f"{BASE}{u}/")
        return (f"Abri o perfil {u} no Instagram, chefe.",)
    abrir(BASE + "explore/search/keyword/?q=" + quote(quem))
    return (f"Pesquisei {quem} no Instagram. Quando achar a conta, me fala o @ que eu guardo e abro story, perfil o que for.",)


def _lembrar(u):
    ultimo.update(usuario=u, em=time.time())
