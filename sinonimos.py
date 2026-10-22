"""Muitos jeitos de falar a mesma coisa → um jeito só, ANTES de qualquer regra do Jarvis.

Pedido dele (22/10): "me mostra", "deixa eu ver", "mostra aí", "quero ver", "bota na tela", "tu pode me mostrar",
"consegue mostrar", "mostre"… é tudo o mesmo pedido. Em vez de cada regra (globo, hardware, notícias, Spotify…)
aprender todas as formas, esta camada reescreve a frase no jeito que as regras já entendem:

    "tu pode me mostrar o processador"   → "me mostra o processador"
    "deixa eu ver as notícias de hoje"   → "me mostra as notícias de hoje"
    "será que tu consegue abrir o zap"   → "abre o zap"
    "eu queria que você tocasse Work"    → "toca Work"
    "abra o Spotify" / "abrir o Spotify" → "abre o Spotify"
    "deixa eu ver quanto tem no caixa"   → "quanto tem no caixa"
    "me mostra meu PC"                   → "me mostra as peças do meu pc"

Só mexe no COMEÇO da frase (o pedido); o resto (texto de mensagem, nome de música) fica como ele falou.
Pra ensinar um jeito novo: acrescente na lista certa aqui embaixo e um caso no treino.py.
"""
import re

# verbo no infinitivo / no "você" (abra, mostre) → no jeito "tu" que as regras usam (abre, mostra)
VERBOS = {
    "abrir": "abre", "abra": "abre", "mostrar": "mostra", "mostre": "mostra", "fechar": "fecha", "feche": "fecha",
    "tocar": "toca", "toque": "toca", "tocasse": "toca", "colocar": "coloca", "coloque": "coloca", "botar": "bota",
    "bote": "bota", "por": "põe", "pôr": "põe", "ponha": "põe", "pesquisar": "pesquisa", "pesquise": "pesquisa",
    "procurar": "procura", "procure": "procura", "buscar": "busca", "busque": "busca", "achar": "acha", "ache": "acha",
    "encontrar": "encontra", "encontre": "encontra", "ligar": "liga", "ligue": "liga", "desligar": "desliga",
    "desligue": "desliga", "aumentar": "aumenta", "aumente": "aumenta", "abaixar": "abaixa", "abaixe": "abaixa",
    "diminuir": "diminui", "diminua": "diminui", "mandar": "manda", "mande": "manda", "enviar": "envia", "envie": "envia",
    "falar": "fala", "fale": "fala", "dizer": "diz", "diga": "diz", "contar": "conta", "conte": "conta",
    "explicar": "explica", "explique": "explica", "pausar": "pausa", "pause": "pausa", "parar": "para", "pare": "para",
    "passar": "passa", "passe": "passa", "levar": "leva", "leve": "leva", "mover": "move", "mova": "move",
    "minimizar": "minimiza", "minimize": "minimiza", "maximizar": "maximiza", "maximize": "maximiza",
    "marcar": "marca", "marque": "marca", "agendar": "agenda", "agende": "agenda", "lembrar": "lembra",
    "lembre": "lembra", "anotar": "anota", "anote": "anota", "criar": "cria", "crie": "cria", "fazer": "faz",
    "faça": "faz", "faca": "faz", "ler": "lê", "leia": "lê", "selecionar": "seleciona", "selecione": "seleciona",
    "destacar": "destaca", "destaque": "destaca", "ativar": "ativa", "ative": "ativa", "desativar": "desativa",
    "desative": "desativa", "iniciar": "inicia", "inicie": "inicia", "voltar": "volta", "volte": "volta",
    "trocar": "troca", "troque": "troca", "mudar": "muda", "mude": "muda", "tirar": "tira", "tire": "tira",
    "limpar": "limpa", "limpe": "limpa", "apagar": "apaga", "apague": "apaga", "esconder": "esconde",
    "esconda": "esconde", "ocultar": "oculta", "oculte": "oculta", "trazer": "traz", "traga": "traz",
    "reiniciar": "reinicia", "reinicie": "reinicia", "bloquear": "bloqueia", "bloqueie": "bloqueia",
    "silenciar": "silencia", "silencie": "silencia", "mutar": "muta", "mute": "muta", "desmutar": "desmuta",
    "desmute": "desmuta", "salvar": "salva", "salve": "salva", "copiar": "copia", "copie": "copia",
    "digitar": "digita", "digite": "digita", "escrever": "escreve", "escreva": "escreve", "apertar": "aperta",
    "aperte": "aperta", "clicar": "clica", "clique": "clica", "continuar": "continua", "continue": "continua",
    "pular": "pula", "pule": "pula", "repetir": "repete", "repita": "repete", "localizar": "localiza",
    "localize": "localiza", "exibir": "mostra", "exiba": "mostra", "exibe": "mostra", "apresentar": "mostra",
    "apresente": "mostra", "apresenta": "mostra", "projetar": "mostra", "projete": "mostra",
    "abrisse": "abre", "mostrasse": "mostra", "fechasse": "fecha", "colocasse": "coloca", "pesquisasse": "pesquisa",
    "procurasse": "procura", "mandasse": "manda", "ligasse": "liga", "desligasse": "desliga",
    "ouvir": "toca", "escutar": "toca",  # "quero ouvir pagode" → "toca pagode"
    "ver": "me mostra", "visse": "me mostra",  # "tu pode ver quanto tem no caixa" → (VER) → "quanto tem no caixa"
}
VERBO = r"(?P<verbo>" + "|".join(sorted(map(re.escape, VERBOS), key=len, reverse=True)) + r")"

J = r"^(?P<j>jarvis[ ,]+)?"
VOCE = r"(?:voc[eê]|vc|tu|c[eê])"
# "tu pode", "você consegue", "será que tu podia", "dá pra tu", "tem como", "eu queria que você", "bora", "vamos"
EMBRULHO = re.compile(
    J + r"(?:(?:ser[aá]\s+que\s+)?(?:" + VOCE + r"\s+)?(?:pode|podes|poderia|podia|consegue|conseguiria|consegues|"
    r"daria\s+pra|dava\s+pra|vai|vais|tem\s+como|podia\s+s[oó])\s+(?:" + VOCE + r"\s+)?(?:s[oó]\s+)?"
    r"|(?:d[aá]|daria|tem\s+como)\s+(?:pra\s+)?(?:" + VOCE + r"\s+)?"
    r"|(?:eu\s+)?(?:quero|queria|gostaria|preciso|precisava)\s+(?:de\s+)?que\s+(?:" + VOCE + r"\s+)?"
    r"|(?:eu\s+)?(?:quero|queria|gostaria\s+de|preciso|precisava)\s+(?:que\s+)?"
    r"|(?:bora|vamos|vamo|vai\s+l[aá]\s+e|faz\s+o\s+favor\s+de|me\s+faz\s+o\s+favor\s+de|por\s+favor)\s+)"
    r"(?P<me>me\s+)?" + VERBO + r"\b", re.I)
SO_VERBO = re.compile(J + r"(?P<me>me\s+)?(?P<verbo>abra|mostre|feche|toque|coloque|bote|ponha|pesquise|procure|busque|ache|"
                      r"encontre|ligue|desligue|aumente|abaixe|diminua|mande|envie|fale|diga|conte|explique|pause|pare|passe|"
                      r"minimize|maximize|marque|agende|anote|crie|fa[cç]a|leia|selecione|destaque|ative|desative|volte|troque|"
                      r"mude|tire|limpe|apague|esconda|oculte|traga|reinicie|bloqueie|silencie|salve|copie|digite|escreva|"
                      r"aperte|clique|exiba|exibe|apresente|apresenta|projete|exibir)\b", re.I)

# "deixa eu ver X", "quero ver X", "mostra aí X", "bota na tela X" → "me mostra X"
VER = re.compile(
    J + r"(?:(?:me\s+)?deixa\s+eu\s+(?:ver|dar\s+uma\s+(?:olhada|espiada|olhadinha)(?:\s+n[oa]s?|\s+em)?)|me\s+deixa\s+ver|"
    r"(?:eu\s+)?(?:quero|queria|gostaria\s+de)\s+(?:ver|dar\s+uma\s+olhada\s+(?:n[oa]s?|em))|(?:bora|vamos|vamo)\s+ver|"
    r"(?:me\s+)?mostra\s+(?:a[ií]|l[aá])|(?:d[aá]|deixa)\s+uma\s+(?:olhada|espiada)\s+(?:n[oa]s?|em)|"
    r"(?:bota|coloca|p[oõ]e|joga|manda)\s+(?:a[ií]\s+)?na\s+tela|(?:me\s+)?mostra\s+pra\s+mim|me\s+mostra|mostra)"
    r"(?:\s+(?:a[ií]|pra\s+mim|rapidinho))?\s+(?P<resto>\S.*)$", re.I)
# "deixa eu ver quanto tem no caixa": aqui "ver" é "conferir", não "mostrar" → só a pergunta
# ("me mostra como é uma BMW X1" continua sendo mostrar: só "como tá/anda/ficou" é pergunta)
VER_PERGUNTA = re.compile(r"^(?:se|quanto|quantos|quantas|qual|quais|como\s+(?:t[aá]|est[aá]|anda|ficou|foi|vai)|o\s+que|quem|"
                          r"quando|onde|cad[eê])\b", re.I)
# "bota o processador na tela" → "me mostra o processador"
NA_TELA_NO_FIM = re.compile(J + r"(?:bota|coloca|p[oõ]e|joga|manda)\s+(?P<resto>.+?)\s+na\s+tela(?:\s+(?:a[ií]|pra\s+mim))?[.!]*$", re.I)

# "meu PC" sozinho depois de mostrar/como é = as peças dele (holograma do hardware)
MEU_PC = re.compile(
    r"^(?P<ini>(?:jarvis[ ,]+)?(?:me\s+mostra|como\s+(?:[eé]|t[aá]|est[aá])|qual\s+(?:[eé]\s+)?)\s+)"
    r"(?:o\s+)?(?:meu|teu|nosso|esse|este|o)\s+(?:pc|computador|micro|m[aá]quina|setup|hardware)"
    r"(?:\s+(?:inteiro|todo|completo|por\s+dentro|a[ií]|agora|gamer))*[.!?]*$", re.I)


def _verbo(v):
    return VERBOS.get(v.lower(), v)


def normalizar(texto):
    """A frase dele no jeito que as regras entendem. Sem nada pra trocar, devolve igual."""
    if not texto or not texto.strip():
        return texto
    t = texto.strip()
    for _ in range(2):  # "tu pode deixar eu ver…" passa duas vezes
        antes = t
        m = EMBRULHO.match(t)
        if m:
            v = _verbo(m.group("verbo"))
            resto = t[m.end():]
            t =(m.group("j") or "") + ((m.group("me") or "") if v != "me mostra" else "") + v + resto
        m = SO_VERBO.match(t)
        if m:
            t = (m.group("j") or "") + (m.group("me") or "") + _verbo(m.group("verbo")) + t[m.end():]
        m = NA_TELA_NO_FIM.match(t)
        if m:
            t = (m.group("j") or "") + "me mostra " + m.group("resto")
        m = VER.match(t)
        if m:
            resto = m.group("resto").strip()
            if re.match(r"se\s", resto, re.I):  # "deixa eu ver se tem lead novo" → "tem lead novo"
                resto = resto[3:]
            elif not VER_PERGUNTA.match(resto):
                resto = "me mostra " + resto
            t = (m.group("j") or "") + resto
        if t == antes:
            break
    m = MEU_PC.match(t)
    if m:
        t = (re.match(r"^(jarvis[ ,]+)?", t).group(0)) + "me mostra as peças do meu pc"
    return t
