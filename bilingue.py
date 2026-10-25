"""Inglês → o jeito que o Jarvis entende. Pedido dele (25/10): "ele tem que entender o inglês e o português".

O reconhecimento é em português, mas o Rafael mistura (e está aprendendo inglês): "open VS Code", "play next song",
"what time is it". Esta camada traduz o PEDIDO em inglês pro comando em português que as regras já conhecem,
ANTES de tudo (é chamada pelo sinonimos.normalizar). O resto da frase (nome de música, assunto) fica como ele falou.

    "open vs code"              → "abre vs code"
    "jarvis, can you open the calculator" → "jarvis, abre a calculadora"
    "play legião urbana"        → "toca legião urbana"
    "next song" / "skip"        → "próxima música"
    "what time is it"           → "que horas são"
    "search for bmw x1 on opera" → "pesquisa bmw x1 no opera"

O Chrome em português escreve o inglês do jeito que soa ("ópen", "plêi", "nékst"): as variantes estão nas regras.
Pra ensinar uma frase nova: acrescente em FRASES (frase inteira) ou VERBOS (começo + resto) e um caso no treino.py.
O cérebro (nuvem) entende inglês sozinho; isto é pros caminhos rápidos, que não passam por ele.
"""
import re

J = r"^(?P<j>(?:hey\s+|ok\s+)?jarvis[ ,]+)?"
# "please", "can you", "could you", "would you", "i want you to", "i'd like to" — embrulho educado, sai
POR_FAVOR = (r"(?:(?:please|pl[ií]s|plis)[ ,]+)?(?:(?:can|could|would|will)\s+(?:you|u|i[uú])\s+|"
             r"i\s+(?:want|need)\s+(?:you\s+)?to\s+|i'?d\s+like\s+(?:you\s+)?to\s+|let'?s\s+)?(?:(?:please|plis)\s+)?")

# frases inteiras: em inglês → em português (sem o "jarvis", que volta na frente)
FRASES = [
    (r"(?:play\s+(?:the\s+)?|go\s+to\s+(?:the\s+)?|skip\s+(?:to\s+)?(?:the\s+)?)?n[eé](?:x|ks|kis)t\s+(?:song|track|music|m[uú]sica)|skip(?:\s+(?:this|the)\s+(?:song|track))?|n[eé](?:x|ks)t",
     "próxima música"),
    (r"(?:play\s+(?:the\s+)?|go\s+(?:back\s+)?to\s+(?:the\s+)?)?(?:previous|last)\s+(?:song|track)|go\s+back", "música anterior"),
    (r"pause(?:\s+(?:the\s+)?(?:music|song|it|spotify))?|stop\s+(?:the\s+)?(?:music|song)", "pausa a música"),
    (r"(?:resume|unpause|continue)(?:\s+(?:the\s+)?(?:music|song|it))?|play\s+(?:it\s+)?again|keep\s+playing", "continua a música"),
    (r"(?:turn|crank)\s+(?:it\s+|the\s+volume\s+)?up(?:\s+the\s+volume)?|volume\s+up|louder", "aumenta o volume"),
    (r"(?:turn)\s+(?:it\s+|the\s+volume\s+)?down(?:\s+the\s+volume)?|volume\s+down|lower\s+the\s+volume|quieter", "abaixa o volume"),
    (r"mute(?:\s+(?:the\s+)?(?:sound|audio|volume))?", "muta o som"),
    (r"lock\s+(?:the\s+|my\s+)?(?:screen|computer|pc)", "bloqueia a tela"),
    (r"what(?:'?s|\s+is)?\s+(?:the\s+)?time(?:\s+is\s+it)?(?:\s+now)?|what\s+time\s+is\s+it(?:\s+now)?", "que horas são"),
    (r"what(?:'?s|\s+is)?\s+(?:the\s+)?date(?:\s+today)?|what\s+day\s+is\s+(?:it|today)", "que dia é hoje"),
    (r"(?:what'?s|how'?s|how\s+is)\s+the\s+weather(?:\s+(?:today|like))?|is\s+it\s+(?:going\s+to|gonna)\s+rain(?:\s+today)?",
     "vai chover hoje"),
    (r"what(?:'?s|\s+is)\s+(?:this|that)\s+song|what\s+song\s+is\s+(?:this|that|playing)", "que música é essa"),
    (r"(?:thank\s+you|thanks|thank\s+u|tenk\s+i[uú]|t[eé]nkiu)(?:\s+(?:so\s+much|very\s+much|man|buddy))?", "valeu"),
    (r"good\s+night", "boa noite jarvis"),
    (r"(?:close|minimize)\s+(?:all\s+)?(?:the\s+)?pop\s*-?\s*ups", "fecha os popups"),
    (r"close\s+(?:this|it|that)(?:\s+window)?", "fecha isso"),
    (r"how\s+much\s+(?:money\s+)?(?:do\s+)?(?:we|i)\s+have(?:\s+in\s+the\s+(?:bank|cash))?", "quanto tem no caixa"),
    (r"(?:any\s+)?new\s+leads|how\s+many\s+new\s+leads", "quantos leads novos"),
    (r"do\s+i\s+have\s+(?:a\s+|any\s+)?meetings?\s+today", "tenho reunião hoje"),
    (r"stop\s+listening|mute\s+(?:the\s+)?mic(?:rophone)?", "muta o microfone"),
]

# verbo em inglês + resto → verbo em português + resto ("open X" → "abre X")
VERBOS = [
    (r"(?:open|[oó]u?pen|launch)", "abre"),  # "start"/"run" não: "dá um start no pomodoro" é português
    (r"(?:close|cl[oó]u?se|quit|kill)", "fecha"),
    (r"minimi[sz]e", "minimiza"),
    (r"maximi[sz]e", "maximiza"),
    (r"(?:play|pl[eê]i)", "toca"),
    (r"(?:search(?:\s+for)?|look\s+up|find(?:\s+me)?)", "pesquisa"),  # "google" não: "google agenda" é português
    (r"show\s+me", "me mostra"),  # só "show me": "show de bola" é português
    (r"(?:tell\s+me\s+about|what\s+(?:is|are)\s+(?:a|an|the)?)", "me fala sobre"),
    (r"send\s+(?:a\s+)?(?:message|text|msg)\s+to", "manda pro"),
    (r"(?:remind\s+me\s+to)", "me lembra de"),
]
ARTIGO = r"(?:(?:the|my|a|an)\s+)?"
# no RESTO só trocamos o que ajuda as regras: "on opera" → "no opera", "the calculator" → "a calculadora"
RESTO = [
    (r"\s+(?:on|in|using|with)\s+(?:the\s+)?(opera(?:\s+gx)?|chrome|edge|youtube|spotify|google)\b", r" no \1"),
    (r"\b(?:on|to|in)\s+the\s+other\s+(?:screen|monitor)\b", "na outra tela"),
    (r"\bfile\s+explorer\b", "explorador de arquivos"),
    (r"\bcalculator\b", "calculadora"), (r"\bnotepad\b", "bloco de notas"), (r"\btask\s+manager\b", "gerenciador de tarefas"),
    (r"\bsettings\b", "configurações"), (r"\bdownloads?\s+folder\b", "pasta downloads"),
    (r"\bmy\s+playlist\b", "minha playlist"), (r"\bsome\s+music\b", "uma playlist"), (r"\bmusic\b", "uma playlist"),
    (r"\bnews\b", "notícias"),
]


def _resto(t):
    for regra, troca in RESTO:
        t = re.sub(regra, troca, t, flags=re.I)
    return t.strip()


def parece_ingles(texto):
    """Ele falou em inglês? (pra o cérebro responder em inglês também, se ele quiser praticar)"""
    palavras = re.findall(r"[a-z']+", (texto or "").lower())
    if len(palavras) < 2:
        return False
    comuns = {"the", "is", "are", "what", "how", "you", "can", "please", "open", "play", "show", "me", "my", "i",
              "do", "does", "it", "this", "that", "to", "for", "and", "of", "with", "about", "tell", "why", "where",
              "when", "who", "your", "have", "has", "would", "could", "should", "want", "need", "know", "think"}
    return sum(p in comuns for p in palavras) / len(palavras) >= 0.4


def traduzir(texto):
    """O pedido em inglês no jeito que o Jarvis entende. Português (ou conversa em inglês) passa igual."""
    if not texto or not re.search(r"[a-z]", texto, re.I):
        return texto
    t = texto.strip()
    m = re.match(J + POR_FAVOR, t, re.I)
    j = (m.group("j") or "") if m else ""
    corpo = t[m.end():] if m else t
    corpo_limpo = re.sub(r"[\s,.!?]*(?:please|plis|for\s+me|jarvis|now|right\s+now)?[\s.!?]*$", "", corpo, flags=re.I)
    for regra, troca in FRASES:
        if re.fullmatch(regra, corpo_limpo, re.I):
            return j + troca
    for regra, troca in VERBOS:
        mv = re.match(regra + r"\s+" + ARTIGO + r"(?P<resto>\S.*)$", corpo_limpo, re.I)
        if mv:
            resto = _resto(mv.group("resto"))
            if troca == "manda pro":  # "send a message to Rihan saying I'm late" → "manda pro Rihan: I'm late"
                resto = re.sub(r"\s+(?:saying|that|telling\s+(?:him|her|them))\s+", ": ", resto, count=1, flags=re.I)
            return j + troca + " " + resto
    return texto
