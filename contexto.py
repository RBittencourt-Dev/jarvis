"""Memória curta da conversa: do que ele acabou de falar ("o foco"), pra entender a frase seguinte.

    "pesquisa BMW X1"  →  foco = "BMW X1"
    "me mostra fotos"  →  "me mostra fotos de BMW X1"   (no cartão da tela, não no navegador)
    "quanto custa ela" →  "pesquisa preço BMW X1"
    "e no youtube?"    →  "pesquisa BMW X1 no youtube"

O foco vale por 10 minutos e é trocado a cada assunto novo. Fica só na memória do servidor
(nada vai pro disco). Dado de morador do Porthon nunca vira foco.
"""
import re
import time

VALIDADE = 600  # segundos
PRONOME = r"(?:dela|dele|disso|desse|dessa|deste|desta|nisso|nela|nele|isso|ela|ele|esse(?: carro| a[ií])?|essa(?: a[ií])?)"
_MOSTRA = r"(?:me\s+)?(?:mostra|mostre|mostrar|bota|p[oõ]e|joga|deixa eu ver|quero ver|tem)"
_FOTOS = r"(?:umas?\s+|as\s+|a\s+)?(?:fotos?|imagens?|figuras?)"
_NA_TELA = r"(?:\s+(?:a[ií]|pra mim|na tela|no pop ?up|aqui))*"

REGRAS = [  # (padrão, como fica com o foco no lugar de {f})
    # "me mostra fotos", "mostra fotos dela", "tem foto?", "bota umas imagens na tela"
    (rf"^{_MOSTRA}\s+{_FOTOS}(?:\s+{PRONOME})?{_NA_TELA}[?.!]*$", "me mostra fotos de {f}"),
    # "me mostra", "mostra aí", "deixa eu ver", "mostra ela na tela"
    (rf"^(?:me\s+)?(?:mostra|mostre|deixa eu ver|quero ver)(?:\s+{PRONOME})?{_NA_TELA}[?.!]*$", "me mostra fotos de {f}"),
    # "fotos dela", "foto"
    (rf"^{_FOTOS}(?:\s+{PRONOME})?{_NA_TELA}[?.!]*$", "me mostra fotos de {f}"),
    # "quanto custa ela?", "e o preço?", "qual o valor dela"
    (rf"^(?:e\s+)?(?:quanto (?:custa|t[aá]|sai|vale)|qual (?:[eé] )?o (?:pre[cç]o|valor)|o pre[cç]o|pre[cç]o)(?:\s+{PRONOME})?[?.!]*$",
     "pesquisa preço {f}"),
    # "e no youtube?", "agora no opera", "pesquisa no chrome", "abre isso no opera gx"
    (r"^(?:e\s+|agora\s+|tamb[eé]m\s+)?(?:(?:pesquisa|procura|busca|abre|joga)(?:\s+" + PRONOME + r")?\s+)?"
     r"(?P<onde>(?:no|na|pelo)\s+(?:youtube|mercado livre|github|google|opera(?:\s*gx)?|chrome|edge|navegador|internet))[?.!]*$",
     "pesquisa {f} {onde}"),
    # "pesquisa isso", "joga no google", "pesquisa de novo"
    (rf"^(?:pesquisa|procura|busca|googla)(?:\s+(?:{PRONOME}|de novo|ent[aã]o))?[?.!]*$|^joga no google[?.!]*$", "pesquisa {f}"),
    # "o que é isso?", "me fala mais dela", "me conta sobre ele"
    (rf"^(?:o que [eé] {PRONOME}|me (?:fala|conta|explica)(?: mais)?(?:\s+(?:sobre|de|do|da))?(?:\s+{PRONOME})?)[?.!]*$",
     "me fala sobre {f}"),
]
REGRAS = [(re.compile(p, re.I), novo) for p, novo in REGRAS]
# frase comum que ganha o foco no lugar do pronome: "me mostra fotos do interior dela" → "…do interior de BMW X1"
TROCA_PRONOME = re.compile(rf"\b(?:dela|dele|disso|desse carro|dessa)\b", re.I)
PEDE_ALGO = re.compile(r"^(?:me\s+)?(?:mostra|pesquisa|procura|busca|quanto custa|qual o pre[cç]o)\b", re.I)


def guardar(sessao, termo):
    termo = (termo or "").strip(" .!?,")
    if termo and not re.fullmatch(PRONOME, termo, re.I):
        sessao["foco"] = {"termo": termo, "quando": time.time()}


def foco_atual(sessao):
    f = (sessao or {}).get("foco")
    if f and time.time() - f["quando"] < VALIDADE:
        return f["termo"]
    return None


def resolver(texto, foco):
    """A frase reescrita com o foco, ou None se ela não depende do que veio antes."""
    if not foco:
        return None
    t = re.sub(r"^(?:jarvis|e a[ií]|bah|tch[eê]|ent[aã]o)[\s,]+", "", texto.strip(), flags=re.I).strip()
    for padrao, novo in REGRAS:
        m = padrao.match(t)
        if m:
            onde = (m.groupdict().get("onde") or "").strip()
            return re.sub(r"\s{2,}", " ", novo.format(f=foco, onde=onde)).strip()
    if PEDE_ALGO.match(t) and TROCA_PRONOME.search(t):
        return TROCA_PRONOME.sub(f"de {foco}", t, count=1)
    return None
