"""Spotify por voz.

Sem configurar nada: "toca X" abre a busca no app do Spotify (ele clica no play), e pausar,
continuar, próxima e anterior funcionam pelas teclas de mídia (servem para qualquer player).

Para tocar sozinho: criar um app em developer.spotify.com (uma vez), pôr o Client ID em
spotify.json e abrir http://127.0.0.1:8765/spotify/conectar. Tocar pela API exige conta Premium.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

RAIZ = Path(__file__).parent
ARQUIVO_APP = RAIZ / "spotify.json"
ARQUIVO_TOKEN = RAIZ / "spotify-token.json"
RETORNO = "http://127.0.0.1:8765/spotify/retorno"
# tocar e controlar + ver as playlists e as curtidas dele ("toca minha playlist de treino")
ESCOPOS = ("user-modify-playback-state user-read-playback-state playlist-read-private playlist-read-collaborative "
           "user-library-read")
_verificador = {}

PEDIDO_DE_MUSICA = re.compile(
    r"^(?:(?P<verbo>toca|tocar|toque|play|coloca|colocar|coloque|bota|botar|p[oõ]e|quero ouvir|solta)\s+)"
    r"(?:(?:a|uma|um|o|umas|uns)\s+)?(?P<o_que>.+?)(?:\s+(?:no|pelo)\s+spotify)?[.!]*$", re.I)
SO_COM_PALAVRA_DE_MUSICA = re.compile(
    r"m[uú]sica|playlist|[aá]lbum|som d|spotify|banda|cantor|sertanejo|pagode|rock|funk|samba|mpb|ga[uú]cha|"
    r"gauchesca|nativista|forr[oó]|jazz|eletr[oô]nica|rap|trap|gospel|ax[eé]|reggae|blues|cl[aá]ssica|lo-?fi", re.I)

# "passa", "passa essa", "passa a música", "passa essa faixa": o artigo e o nome são opcionais
MUSICA = r"(?:\s+(?:a|o|essa|esse|esta|uma|pra|pro))?(?:\s+(?:m[uú]sica|som|faixa|spotify|pr[oó]xima))?"
TECLAS = [  # (regra, ação no Spotify, fala) — "pode", "jarvis", "aí" já saíram antes (vocabulario.limpar)
    (r"^(?:pode\s+)?(?:pausa|pausar|pause|para|parar|pare|segura)" + MUSICA + "$", "pausar", "Pausado."),
    (r"^(?:pode\s+)?(?:continua|continuar|continua tocando|despausa|retoma|volta a tocar|play|solta o som(?: de novo)?|"
     r"bota (?:pra )?tocar(?: de novo)?|toca de novo a m[uú]sica)" + MUSICA + "$", "continuar", "Continuando."),
    (r"^(?:pode\s+)?(?:passa|passar|pula|pular|pr[oó]xima|avan[cç]a|avan[cç]ar|troca|muda)" + MUSICA + "$", "proxima", "Próxima."),
    (r"^tira (?:essa|esta|a)(?: m[uú]sica| faixa)?$", "proxima", "Próxima."),  # "tira o som" é silenciar, não pular
    (r"^(?:m[uú]sica anterior|anterior|volta(?: uma| a| essa)?(?: m[uú]sica| faixa)|volta uma|volta(?: a| pra| na)? anterior)$",
     "anterior", "Voltando."),
    (r"^(?:repete|repetir|recome[cç]a|do come[cç]o|toca de novo)" + MUSICA + "$", "repetir", "Do começo."),
]


def tecla_de_midia(texto):
    """"pausa a música", "próxima" → (tecla, fala); senão None."""
    t = texto.lower().strip(" .!")
    for regra, tecla, fala in TECLAS:
        if re.search(regra, t):
            return tecla, fala
    return None


CONTINUACOES = [  # depois de falar de música, frases curtas que só fazem sentido nesse assunto
    (r"^(?:toca |bota |coloca |p[oõ]e )?(?:outra|outra m[uú]sica|muda|troca|muda a m[uú]sica|troca a m[uú]sica)$", ("tecla", ("proxima", "Próxima."))),
    (r"^(?:mais alto|aumenta|sobe(?: o som)?|aumenta a[ií])$", ("tecla", (0xAF, "Mais alto."))),
    (r"^(?:mais baixo|abaixa|diminui|baixa(?: o som)?|abaixa a[ií])$", ("tecla", (0xAE, "Mais baixo."))),
]
E_AGORA = re.compile(r"^(?:e\s+)?(?:agora\s+)?(?:(?:a|o|uma|um)\s+)?(?:d[oa]s?\s+)?(?P<o_que>.+)$", re.I)


def continuacao(texto):
    """No assunto música: ("tecla", (tecla, fala)) ou ("tocar", busca) para "e agora Legião Urbana"; senão None."""
    t = texto.lower().strip(" .!?")
    for regra, resultado in CONTINUACOES:
        if re.search(regra, t):
            return resultado
    if re.match(r"^(?:e\s+agora|agora|e\s+(?:a|o|uma|um)\s+d[oa]s?|e\s+d[oa]s?)\s+", t):
        o_que = E_AGORA.match(t).group("o_que")
        if re.match(r"(?:abre|abrir|fecha|minimiza|maximiza|pesquisa|procura|manda|me |mostra|qual|quanto|quantos|"
                    r"que |quem|como|onde|cria|faz|liga|desliga|bloqueia|passa|muda (?:a|o) (?!m[uú]sica)|vai|vamos|"
                    r"t[oô] |eu |tu |voc[eê]|ele|ela|n[aã]o|sim|ok|beleza|valeu|obrigad)", o_que):
            return None  # "agora abre o VS Code" é outro pedido, não busca no Spotify
        return "tocar", o_que
    return None


TECLA_DA_ACAO = {"pausar": 0xB3, "continuar": 0xB3, "proxima": 0xB0, "anterior": 0xB1, "repetir": 0xB1}
CHAMADA_DA_ACAO = {"pausar": ("PUT", "/me/player/pause"), "continuar": ("PUT", "/me/player/play"),
                   "proxima": ("POST", "/me/player/next"), "anterior": ("POST", "/me/player/previous"),
                   "repetir": ("PUT", "/me/player/seek?position_ms=0")}


def apertar(acao):
    """Ação de música: pela conta do Spotify (certeiro) e, se não der, pela tecla de mídia (qualquer player).
    Número = tecla direta (volume)."""
    if isinstance(acao, str) and configurado():
        try:
            metodo, caminho = CHAMADA_DA_ACAO[acao]
            r = _api(metodo, caminho)
            if r.status_code < 300 or r.status_code in (403, 404):
                # 403 = já estava pausado/tocando (ou sem Premium); 404 = nenhum aparelho. Tecla aqui
                # seria play/pause às cegas: "pausa" com a música parada LIGAVA a música. Não aperta.
                return
        except Exception:
            pass  # sem internet: aí sim a tecla de mídia
    tecla = TECLA_DA_ACAO.get(acao, acao) if isinstance(acao, str) else acao
    _tecla(tecla)


def _tecla(tecla):
    import ctypes
    ctypes.windll.user32.keybd_event(tecla, 0, 0, 0)
    ctypes.windll.user32.keybd_event(tecla, 0, 2, 0)


def pedido(texto):
    """"toca Legião Urbana" → "Legião Urbana"; None se não for pedido de música."""
    m = PEDIDO_DE_MUSICA.match(texto.strip())
    if not m:
        return None
    o_que = m.group("o_que").strip()
    if re.fullmatch(r"(?:outra|outra m[uú]sica|a pr[oó]xima|pr[oó]xima)", o_que, re.I):
        return None  # "toca outra" é trocar de faixa (continuacao), não buscar "outra"
    if o_que.lower() in ("spotify", "o spotify", "musica", "música") or re.match(r"^(o |a )?(vs code|zap|whatsapp)", o_que, re.I):
        return None
    # "bota Evidências do Chitãozinho": sem artigo + "do/da <artista>" é jeito de pedir música
    musica_de_alguem = re.match(r"^\S+\s+(?!(?:o|a|os|as|um|uma|meu|minha)\s)\S.*\s(?:do|da|dos|das)\s+\S", texto.strip(), re.I)
    if m.group("verbo").lower() not in ("toca", "tocar", "toque", "play", "quero ouvir", "solta") \
            and not SO_COM_PALAVRA_DE_MUSICA.search(texto) and not musica_de_alguem:
        return None  # "coloca o modo escuro", "bota o vs code": não é música
    return re.sub(r"^(?:m[uú]sica|m[uú]sicas|som)\s+(?:d[oa]s?\s+)?", "", o_que, flags=re.I)


# ------------------------------------------------------------- conta (PKCE: sem senha nem segredo no PC)

def configurado():
    return ARQUIVO_APP.exists() and ARQUIVO_TOKEN.exists()


def endereco_de_login():
    client_id = json.loads(ARQUIVO_APP.read_text(encoding="utf-8"))["client_id"]
    verificador = secrets.token_urlsafe(64)
    _verificador["v"] = verificador
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    return "https://accounts.spotify.com/authorize?" + urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": RETORNO, "scope": ESCOPOS,
        "code_challenge_method": "S256", "code_challenge": desafio})


def _guardar(dados):
    dados["expira"] = time.time() + dados.get("expires_in", 3600)
    antigo = json.loads(ARQUIVO_TOKEN.read_text(encoding="utf-8")) if ARQUIVO_TOKEN.exists() else {}
    ARQUIVO_TOKEN.write_text(json.dumps({**antigo, **dados}), encoding="utf-8")


def concluir_login(codigo):
    client_id = json.loads(ARQUIVO_APP.read_text(encoding="utf-8"))["client_id"]
    r = httpx.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "authorization_code", "code": codigo, "redirect_uri": RETORNO,
        "client_id": client_id, "code_verifier": _verificador.get("v", "")}, timeout=10)
    r.raise_for_status()
    _guardar(r.json())


def _token():
    dados = json.loads(ARQUIVO_TOKEN.read_text(encoding="utf-8"))
    if time.time() < dados["expira"] - 60:
        return dados["access_token"]
    client_id = json.loads(ARQUIVO_APP.read_text(encoding="utf-8"))["client_id"]
    r = httpx.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "refresh_token", "refresh_token": dados["refresh_token"], "client_id": client_id}, timeout=10)
    r.raise_for_status()
    _guardar(r.json())
    return json.loads(ARQUIVO_TOKEN.read_text(encoding="utf-8"))["access_token"]


def _api(metodo, caminho, **kw):
    return httpx.request(metodo, "https://api.spotify.com/v1" + caminho,
                         headers={"Authorization": f"Bearer {_token()}"}, timeout=10, **kw)


# ------------------------------------------------------------- aprendizado: o que ele pede → o que tocou

ARQUIVO_APRENDIDAS = RAIZ / "musicas-aprendidas.json"
ultima = {"chave": None}


def _aprendidas():
    if ARQUIVO_APRENDIDAS.exists():
        try:
            return json.loads(ARQUIVO_APRENDIDAS.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def _chave(busca):
    return re.sub(r"\s+", " ", busca.lower().strip(" .!?"))


def esquecer_ultima():
    """"Essa não": a última música tocada sai do aprendido (da próxima vez ele procura de novo)."""
    aprendidas = _aprendidas()
    if ultima["chave"] in aprendidas:
        del aprendidas[ultima["chave"]]
        ARQUIVO_APRENDIDAS.write_text(json.dumps(aprendidas, ensure_ascii=False, indent=1), encoding="utf-8")
        apertar("pausar")  # pausa a errada
        return "Desculpa, chefe. Esqueci essa. Me fala o nome e o artista que eu acerto."
    return "Me fala o nome e o artista da música que eu procuro de novo, chefe."


def tocar(busca):
    """Toca de verdade (API) ou, sem conta conectada, abre a busca no app."""
    if not configurado():
        os.startfile("spotify:search:" + quote(busca))
        return f"Abri {busca} no Spotify, chefe. É só dar o play."
    chave = _chave(busca)
    # o nome de uma playlist DELE ganha de música com nome parecido ("toca Development" = a playlist dele)
    try:
        exata = next((p for p in _minhas_playlists() if _sem_acento(p["name"]).strip() == _sem_acento(busca).strip()), None)
    except Exception:
        exata = None
    if exata:
        return _dar_play({"context_uri": exata["uri"]}, f"a sua playlist {nome_falado(exata['name'])}", busca, chave)
    genero = genero_de(busca)
    if genero:  # "toca um funk", "algo pra treinar": escolhe uma playlist do gênero (as dele primeiro)
        return tocar_genero(genero)
    certa = musica_do_artista(busca)
    if certa:  # "Tempo Perdido da Legião Urbana": a música certa, daquele artista
        return _dar_play(certa[0], certa[1], busca, chave)
    aprendida = _aprendidas().get(chave)
    if aprendida:  # já tocou isso antes e ele não reclamou: vai direto, sem buscar
        return _dar_play(aprendida["corpo"], aprendida["nome"], busca, chave)
    especial = _playlist_ou_curtidas(busca)
    if especial:
        if isinstance(especial, str):  # uma pergunta ("qual delas?") ou um aviso
            return especial
        corpo, nome = especial
        return _dar_play(corpo, nome, busca, chave)
    playlist = re.match(r"^(?:a\s+|uma\s+)?playlist\s+(?:d[aeo]s?\s+)?(.+)", busca, re.I)
    tipo = "playlist" if playlist else "track,artist"
    termo = playlist.group(1) if playlist else busca
    achado = _api("GET", "/search", params={"q": termo, "type": tipo, "limit": 5, "market": "BR"}).json()
    artista = [a for a in (achado.get("artists") or {}).get("items") or [] if a]
    musica = [m for m in (achado.get("tracks") or {}).get("items") or [] if m]
    lista = [p for p in (achado.get("playlists") or {}).get("items") or [] if p]  # a API às vezes manda itens vazios
    # "toca Legião Urbana" (nome de artista) toca o artista; "toca Tempo Perdido" toca a música
    if lista:
        corpo, nome = {"context_uri": lista[0]["uri"]}, f"a playlist {lista[0]['name']}"
    elif artista and artista[0]["name"].lower() == termo.lower():
        corpo, nome = {"context_uri": artista[0]["uri"]}, artista[0]["name"]
    elif musica:
        corpo, nome = {"uris": [musica[0]["uri"]]}, f"{musica[0]['name']}, de {musica[0]['artists'][0]['name']}"
    else:
        return f"Não achei {busca} no Spotify, chefe."
    return _dar_play(corpo, nome, busca, chave)


MINHAS = re.compile(r"^(?:a\s+|as\s+|uma\s+)?(?P<minha>minhas?\s+|meus?\s+)?(?P<o_que>playlists?|m[uú]sicas curtidas|curtidas|favoritas|"
                    r"m[uú]sicas favoritas|liked songs|liked|(?:m[uú]sicas\s+)?mais (?:tocadas|ouvidas))\b"
                    r"\s*(?:d[aeo]s?\s+|chamada\s+)?(?P<nome>.*)$", re.I)
CURTIDAS = re.compile(r"^(?:as\s+|minhas\s+)?(?:m[uú]sicas\s+)?(?:curtidas|favoritas|liked(?: songs)?|que eu curti)$", re.I)

# Ele fala em português; as playlists dele têm nome em inglês (ou abreviado). Palavra dita → palavras do nome.
SINONIMOS = {
    "trabalho": ["work", "office", "trabalho"], "trabalhar": ["work", "office"], "escritorio": ["office", "work"],
    "desenvolvimento": ["development", "dev"], "programar": ["development", "dev", "code"], "programacao": ["development", "dev"],
    "codigo": ["development", "code", "dev"], "dev": ["development", "dev"],
    "top": ["top"], "mais tocadas": ["top"], "mais ouvidas": ["top"], "preferidas": ["top"],
    "gospel": ["gospel", "crista", "cristã"], "louvor": ["gospel", "crista"], "crista": ["crista", "gospel"],
    "evangelica": ["gospel", "crista"], "ingles": ["english"], "triste": ["depre", "sad"], "depre": ["depre"],
    "depressao": ["depre"], "relaxar": ["chill", "relax", "lounge"], "foco": ["chill", "focus", "work"],
    "estudar": ["chill", "study", "studying"], "calma": ["chill", "relax"], "cafe": ["cafe", "chill"],
    "cha de bebe": ["cha de bebe", "baby"], "secretaria": ["secretaria"],
}


def nome_falado(nome):
    """"Office Chill 2026 💻 Work Playlist for Working, Studying…" → "Office Chill 2026": sem emoji e curto pra voz."""
    limpo = re.sub(r"[^\w\s&'.-]", " ", nome).split("  ")[0]
    limpo = re.split(r"\s[-|]\s|,", limpo)[0].strip()
    if len(limpo) > 32:
        limpo = limpo[:32].rsplit(" ", 1)[0]
    return limpo or nome


def _sem_acento(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def playlist_parecida(dito, playlists):
    """"trabalho" acha "Work👨‍💻", "desenvolvimento" acha "Development": nome parecido OU palavra traduzida."""
    import difflib
    dito = _sem_acento(dito).strip()
    procurar = {dito, *dito.split()}
    for chave, traducoes in SINONIMOS.items():
        if chave in dito:
            procurar.update(traducoes)
    melhor, nota = None, 0.0
    for p in playlists:
        nome = _sem_acento(nome_falado(p["name"]))
        palavras = set(re.findall(r"\w+", nome))
        n = difflib.SequenceMatcher(None, dito, nome).ratio()
        if any(t in palavras or (len(t) > 4 and t in nome) for t in procurar if len(t) >= 3):
            n += 0.6  # bateu uma palavra (ou a tradução dela)
        if n > nota:
            melhor, nota = p, n
    return melhor if nota >= 0.6 else None


# ------------------------------------------------------------- gêneros e climas ("toca um funk", "algo pra treinar")
# gênero → (jeitos de falar, busca no Spotify, palavras que denunciam uma playlist DELE desse gênero)
GENEROS = {
    # vem antes de "gospel" e de "pagode": a primeira regra que bate é a que vale
    "pagode gospel": (r"pagode\s+(?:gospel|crist[aã]o|de\s+louvor|de\s+igreja|crente|evang[eé]lico)|pagode\s+restaura(?:dor)?|"
                      r"tardezinha\s+gospel|tardizinha\s+gospel|louvor\s+(?:em\s+|no\s+)?pagode|gospel\s+(?:em\s+|no\s+)?pagode",
                      "pagode gospel tardezinha restaura", ["pagode gospel", "restaura", "tardezinha gospel"]),
    "gospel": (r"gospel|louvor(?:es)?|adora[cç][aã]o|crist[aã]|evang[eé]lic[ao]|worship|hinos?|m[uú]sica de igreja",
               "gospel mais tocadas", ["gospel", "crista", "cristo", "louvor", "worship", "jesus", "deus"]),
    "funk": (r"funk(?:z[aã]o)?|baile funk|mandel[aã]o|funk carioca|funk paulista", "funk mais tocadas", ["funk"]),
    "pagode": (r"pagode(?:zinho|ira)?|pagod[aã]o|samba e pagode", "pagode mais tocadas", ["pagode"]),
    "sertanejo": (r"sertanejo(?: universit[aá]rio| raiz)?|sertanej[aã]o|mod[aã]o|sofr[eê]ncia", "sertanejo mais tocadas",
                  ["sertanejo", "modao"]),
    "samba": (r"samba(?: de raiz)?|sambinha", "samba de raiz", ["samba"]),
    "mpb": (r"mpb|m[uú]sica popular brasileira|bossa nova", "mpb as melhores", ["mpb", "bossa"]),
    "rock": (r"rock(?: nacional| internacional| cl[aá]ssico| antigo)?|rockzinho|classic rock", "rock classico", ["rock"]),
    "metal": (r"metal|heavy metal|metalcore", "metal", ["metal"]),
    "rap": (r"rap(?: nacional)?|hip ?hop", "rap nacional", ["rap", "hip hop"]),
    "trap": (r"trap(?: nacional)?", "trap brasil", ["trap"]),
    "eletrônica": (r"eletr[oô]nica|eletr[oô]nico|house|techno|edm|rave|psytrance|psy", "eletronica house", ["eletronica", "house", "edm"]),
    "lo-fi": (r"lo-?fi|lofi", "lofi beats", ["lofi", "lo-fi"]),
    "gaúcha": (r"ga[uú]ch[ao]|gauchesca|nativista|tradicionalista|m[uú]sica do sul|vanera|vaneira|chamam[eé]",
               "musica gaucha tradicionalista", ["gaucha", "gaucho", "nativista", "vanera"]),
    "forró": (r"forr[oó]|piseiro|pisadinha|xote|bai[aã]o", "forro piseiro", ["forro", "piseiro"]),
    "axé": (r"ax[eé]|pagode baiano|arrocha", "axe music", ["axe"]),
    "reggae": (r"reggae|reggaeton", "reggae", ["reggae"]),
    "jazz": (r"jazz|blues|soul", "jazz classics", ["jazz", "blues", "soul"]),
    "clássica": (r"cl[aá]ssica|m[uú]sica cl[aá]ssica|orquestra|piano cl[aá]ssico", "classical essentials", ["classica", "classical"]),
    "k-pop": (r"k-?pop", "kpop hits", ["kpop", "k-pop"]),
    "pop": (r"pop(?: internacional| nacional)?|hits do momento|as do momento|top hits", "top hits brasil", ["pop", "hits"]),
    "anos 80": (r"anos 80|oitenta|flashback|80s", "anos 80 flashback", ["80", "flashback"]),
    "anos 90": (r"anos 90|noventa|90s", "anos 90", ["90"]),
    "anos 2000": (r"anos 2000|2000s", "anos 2000 hits", ["2000"]),
    "romântica": (r"rom[aâ]ntic[ao]s?|love songs|pra namorar", "musicas romanticas", ["romantic", "love"]),
    # climas: o que ele vai FAZER
    "treino": (r"(?:pra |para )?(?:treinar|treino|academia|malhar|correr|corrida)|workout|gym", "treino academia",
               ["treino", "gym", "workout"]),
    "foco": (r"(?:pra |para )?(?:estudar|focar|foco|concentrar|trabalhar|programar)|concentra[cç][aã]o", "foco concentracao",
             ["work", "office", "development", "focus"]),
    "relaxar": (r"(?:pra |para )?(?:relaxar|descansar|dormir|acalmar)|calm[ao]|tranquil[ao]|chill", "relaxar chill",
                ["chill", "relax", "lounge"]),
    "festa": (r"(?:pra |para )?(?:festa|balada|animar|churrasco|sextou)|animad[ao]|agitad[ao]", "festa churrasco",
              ["festa", "churras"]),
    "triste": (r"tristes?|depre|sofrid[ao]|fossa", "musicas tristes", ["depre", "sad", "triste"]),
}
_ENFEITES = (r"(?:(?:um|uma|uns|umas|algo|alguma coisa|algum|alguma|o|a|os|as|musicas?|som|sons|playlist|estilo|genero)\s+)*"
             r"(?:(?:de|do|da|dos|das|pra|para)\s+)?")
_DEPOIS = (r"(?:\s+(?:bom|boa|bons|boas|top|atual|atualizado|das antigas|antig[ao]s?|nov[ao]s?|do momento|"
           r"mais tocad[ao]s|famos[ao]s?|nacional|internacional|ai|pra mim|no spotify))*")
_ULTIMA_DO_GENERO = {}


def genero_de(busca):
    """"um funkzão", "algo pra treinar", "gospel" → nome do gênero; None se não for SÓ um gênero/clima
    ("funk do MC Ryan" é artista: segue a busca normal)."""
    t = _sem_acento(busca).strip(" .!?")
    for nome, (jeitos, _, _) in GENEROS.items():
        if re.fullmatch(_ENFEITES + f"(?:{_sem_acento(jeitos)})" + _DEPOIS, t):
            return nome
    return None


def tocar_genero(nome):
    """Primeiro as playlists DELE daquele gênero (varia entre elas); se não tiver, uma das melhores do Spotify,
    sem repetir a última que tocou."""
    import random
    _, busca, marcas = GENEROS[nome]
    try:
        minhas = [p for p in _minhas_playlists() if any(m in _sem_acento(p["name"]) for m in marcas)]
    except Exception:
        minhas = []
    if minhas:
        p = random.choice([x for x in minhas if x["uri"] != _ULTIMA_DO_GENERO.get(nome)] or minhas)
        _ULTIMA_DO_GENERO[nome] = p["uri"]
        return _dar_play({"context_uri": p["uri"]}, f"a sua playlist {nome_falado(p['name'])}", nome, None)
    achadas = [p for p in (_api("GET", "/search", params={"q": busca, "type": "playlist", "limit": 8, "market": "BR"})
                           .json().get("playlists") or {}).get("items") or [] if p]
    if not achadas:
        return f"Não achei playlist de {nome} agora, chefe."
    p = random.choice([x for x in achadas[:4] if x["uri"] != _ULTIMA_DO_GENERO.get(nome)] or achadas[:4])
    _ULTIMA_DO_GENERO[nome] = p["uri"]
    _api("PUT", "/me/player/shuffle", params={"state": "true"})
    return _dar_play({"context_uri": p["uri"]}, f"{nome}, playlist {nome_falado(p['name'])}", nome, None)


def musica_do_artista(busca):
    """"<música> do/da/dos/das/de <artista>" → (corpo, nome) da faixa certa, ou None.
    O título pode ter "de" no meio ("Garota de Ipanema do Tom Jobim"): testa cada corte, do último pro primeiro,
    e só aceita quando o Spotify acha a faixa com aquele nome E o artista bate."""
    import difflib
    for corte in reversed(list(re.finditer(r"\s+(?:d[oa]s?|de)\s+", busca, re.I))):
        musica, artista = busca[:corte.start()].strip(" ,"), busca[corte.end():].strip(" ,.!?")
        if not musica or len(artista) < 2:
            continue
        try:
            achado = _api("GET", "/search", params={"q": f'track:"{musica}" artist:"{artista}"', "type": "track",
                                                    "limit": 5, "market": "BR"}).json()
        except Exception:
            continue
        for faixa in (achado.get("tracks") or {}).get("items") or []:
            if not faixa:
                continue
            nomes = [a["name"] for a in faixa.get("artists", [])]
            bate_artista = any(_sem_acento(artista) in _sem_acento(n) or
                               difflib.SequenceMatcher(None, _sem_acento(artista), _sem_acento(n)).ratio() >= 0.7 for n in nomes)
            titulo = _sem_acento(faixa["name"].split(" - ")[0])
            bate_musica = _sem_acento(musica) in titulo or difflib.SequenceMatcher(None, _sem_acento(musica), titulo).ratio() >= 0.6
            if bate_artista and bate_musica:
                return {"uris": [faixa["uri"]]}, f"{faixa['name']}, de {nomes[0]}"
    # 2ª tentativa: busca livre "música artista" e confere só o título (o artista pode ter outro nome lá:
    # "Tom Jobim" no Spotify é "Antônio Carlos Jobim")
    for corte in reversed(list(re.finditer(r"\s+(?:d[oa]s?|de)\s+", busca, re.I))):
        musica, artista = busca[:corte.start()].strip(" ,"), busca[corte.end():].strip(" ,.!?")
        if not musica or len(artista) < 2:
            continue
        try:
            achado = _api("GET", "/search", params={"q": f"{musica} {artista}", "type": "track", "limit": 5, "market": "BR"}).json()
        except Exception:
            continue
        for faixa in (achado.get("tracks") or {}).get("items") or []:
            if faixa and difflib.SequenceMatcher(None, _sem_acento(musica), _sem_acento(faixa["name"].split(" - ")[0].split(" (")[0])).ratio() >= 0.8:
                return {"uris": [faixa["uri"]]}, f"{faixa['name']}, de {faixa['artists'][0]['name']}"
    return None


def _minhas_playlists():
    j = _api("GET", "/me/playlists", params={"limit": 50})
    if j.status_code == 403:
        raise PermissionError
    return [p for p in j.json().get("items", []) if p]


def _playlist_ou_curtidas(busca):
    """Playlists e curtidas DELE. Devolve (corpo, nome) pra tocar, uma frase (pergunta/aviso) ou None (busca normal)."""
    m = MINHAS.match(busca.strip())
    if not m:
        return None
    o_que, nome, minha = m.group("o_que").lower(), m.group("nome").strip(), bool(m.group("minha"))
    if CURTIDAS.match(nome):  # "a playlist curtidas", "playlist liked songs": são as curtidas
        o_que, nome = "curtidas", ""
    if "mais " in o_que:  # "minhas mais tocadas" é o nome de uma playlist (My top tracks)
        o_que, nome = "playlist", o_que
    try:
        if "curtid" in o_que or "favorit" in o_que or "liked" in o_que:
            # pela coleção (context_uri) e em modo aleatório: tocar por lista de faixas parou de funcionar no app do PC
            eu = _api("GET", "/me").json().get("id")
            if not eu:
                return "Não consegui abrir as suas curtidas agora, chefe."
            return {"context_uri": f"spotify:user:{eu}:collection", "aleatorio": True}, "as suas músicas curtidas"
        playlists = _minhas_playlists()
    except PermissionError:
        return "Preciso de permissão pra ver as suas playlists. Abre o endereço spotify conectar que eu te mostro, chefe."
    if nome:
        p = playlist_parecida(nome, playlists)
        if p:
            return {"context_uri": p["uri"]}, f"a sua playlist {nome_falado(p['name'])}"
        return None if not minha else f"Não achei a playlist {nome} entre as suas, chefe."  # "playlist de rock": busca pública
    if not playlists:
        return "Você ainda não tem playlists, chefe. Quer que eu toque uma de rock, pagode, sertanejo?"
    if len(playlists) == 1:
        return {"context_uri": playlists[0]["uri"]}, f"a sua playlist {nome_falado(playlists[0]['name'])}"
    nomes = ", ".join(nome_falado(p["name"]) for p in playlists[:5])
    return f"Qual delas, chefe? Você tem: {nomes}."


def _como_contexto(corpo):
    """Música avulsa ({"uris": [faixa]}) vira "o álbum dela, começando nela".
    Bug de 21/10: o app do PC aceita o play por lista de faixas (204) mas não toca nada (fica "tocando" vazio);
    por álbum/playlist/artista (context_uri) toca normal. De quebra, quando a faixa acaba, segue o álbum."""
    uris = corpo.get("uris") or []
    if not uris or "context_uri" in corpo:
        return corpo
    try:
        faixa = uris[0].rsplit(":", 1)[-1]
        album = _api("GET", f"/tracks/{faixa}").json()["album"]["uri"]
        return {"context_uri": album, "offset": {"uri": uris[0]}}
    except Exception:
        return corpo


def _tocou():
    """Confere de verdade (até ~3 s) se o Spotify começou a tocar alguma coisa."""
    for _ in range(4):
        time.sleep(0.8)
        try:
            r = _api("GET", "/me/player")
            if r.status_code == 200 and r.json().get("is_playing") and r.json().get("item"):
                return True
        except Exception:
            pass
    return False


def _dar_play(corpo, nome, busca, chave):
    corpo = _como_contexto(dict(corpo))
    aleatorio = corpo.pop("aleatorio", False)
    if aleatorio:
        _api("PUT", "/me/player/shuffle", params={"state": "true"})
    r = _api("PUT", "/me/player/play", json=corpo)
    if r.status_code == 404:  # nenhum aparelho ativo: acorda o PC como aparelho e manda tocar nele
        aparelhos = _api("GET", "/me/player/devices").json().get("devices", [])
        if not aparelhos:
            os.startfile("spotify:")
            time.sleep(5)
            aparelhos = _api("GET", "/me/player/devices").json().get("devices", [])
        if aparelhos:
            _api("PUT", "/me/player", json={"device_ids": [aparelhos[0]["id"]], "play": False})
            time.sleep(0.8)
            r = _api("PUT", f"/me/player/play?device_id={aparelhos[0]['id']}", json=corpo)
    if r.status_code < 400 and not _tocou():
        # o app aceitou e não tocou: abre direto no app, que toca sozinho ao abrir o link
        alvo = (corpo.get("offset") or {}).get("uri") or corpo.get("context_uri") or (corpo.get("uris") or [None])[0]
        if alvo:
            os.startfile(alvo)
            time.sleep(2.5)
            if not _tocou():
                _api("PUT", "/me/player/play")  # ainda parado: dá o play no que abriu
    if r.status_code == 403:
        os.startfile("spotify:search:" + quote(busca))
        return "O Spotify só deixa eu dar o play com conta Premium, chefe. Abri a busca pra você."
    if r.status_code >= 400:
        return f"O Spotify recusou: {r.text[:100]}"
    if not chave:  # gênero: não decora (da próxima vez escolhe outra playlist)
        return f"Tocando {nome}."
    aprendidas = _aprendidas()
    aprendidas[chave] = {"corpo": corpo, "nome": nome}
    ARQUIVO_APRENDIDAS.write_text(json.dumps(aprendidas, ensure_ascii=False, indent=1), encoding="utf-8")
    ultima["chave"] = chave
    return f"Tocando {nome}."


_tocando = {"em": 0, "dados": None}


def tocando():
    """O que está tocando agora no Spotify (guarda 5 s pra não perguntar a cada frase): {nome, artista} ou None."""
    if not configurado():
        return None
    if time.time() - _tocando["em"] < 5:
        return _tocando["dados"]
    dados = None
    try:
        r = _api("GET", "/me/player/currently-playing")
        if r.status_code == 200:
            j = r.json()
            item = j.get("item") or {}
            if j.get("is_playing") and item:
                dados = {"nome": item.get("name"), "artista": ", ".join(a["name"] for a in item.get("artists", []))}
    except Exception:
        pass
    _tocando.update(em=time.time(), dados=dados)
    return dados


QUE_MUSICA = re.compile(r"\b(?:que|qual)\s+(?:m[uú]sica|som)\b|\bquem\s+canta\b|\bnome\s+d(?:essa|esta|a)\s+(?:m[uú]sica|banda)\b|"
                        r"\b(?:que|qual(?: [eé])?(?: a)?)\s+banda\b|\bo que (?:t[aá]|est[aá]) tocando\b", re.I)


def que_musica():
    agora = tocando()
    if not agora:
        return "Não tem nada tocando no Spotify agora, chefe."
    return f"Tá tocando {agora['nome']}, de {agora['artista']}."


ESSA_NAO = re.compile(r"^(?:n[aã]o[, ]+)?(?:essa n[aã]o|n[aã]o [eé] essa|m[uú]sica errada|errou a m[uú]sica|"
                      r"tocou errado|n[aã]o era essa)\b", re.I)
