"""Jarvis professor particular (ensino médio): dá aula, passa exercício e ajuda com o dever/prova.

Pedido dele (23/10/2026): "ensina ele a me dar aulas de ensino médio, ser meu professor particular pra me ajudar no
colégio". Usa a mesma IA (Groq/Gemini) com persona de professor. Dispara SÓ em pedido claro de aula/estudo (aula,
ensina, aprender, matéria, exercício, dever, prova) — NÃO rouba o "me explica X" comum nem a anatomia 3D (que já é tratada
antes). Pra assunto visual (corpo, geografia...), lembra que dá pra ver em 3D.
"""
import asyncio
import re
import unicodedata

import cerebro

DEMORA = True

PROFESSOR = """Você é um professor particular brasileiro paciente e didático, do ensino médio, ajudando o Rafael a
estudar. Explique no nível do ensino médio, em português do Brasil, com linguagem simples e um exemplo concreto do dia a
dia. Nada de enrolação nem termos difíceis sem explicar. Seja encorajador. Currículo brasileiro. NUNCA invente fato,
fórmula, data ou número — se não tiver certeza, diga. Mostre o passo a passo quando for conta ou processo."""

MATERIAS = (r"matematica|portugues|fisica|quimica|biologia|historia|geografia|filosofia|sociologia|ingles|espanhol|"
            r"literatura|redacao|gramatica|ciencias|artes|educacao fisica|enem|vestibular")

AULA = re.compile(r"\b(?:me\s+(?:d[aáê]|ensina|ensine)\s+(?:uma\s+)?aula|(?:me\s+)?ensina(?:r|me)?\b|quero\s+aprender|"
                  r"(?:me\s+)?explica\s+a\s+mat[eé]ria|aula\s+(?:de|sobre)|preciso\s+(?:estudar|aprender)|"
                  r"me\s+ajuda\s+a\s+(?:estudar|entender)|como\s+(?:se\s+)?(?:faz|calcula|resolve))\b", re.I)
EXERCICIO = re.compile(r"\b(?:me\s+(?:passa|d[aá]|faz|d[eê])\s+(?:um|uns|uma|umas)?\s*(?:exerc[ií]cios?|quest[aã]o|quest[oõ]es|"
                       r"problemas?|pergunta)|(?:um|me\s+faz\s+um)\s+exerc[ií]cio|quero\s+(?:um\s+)?exerc[ií]cio|"
                       r"me\s+testa|me\s+d[aá]\s+uma\s+quest[aã]o)\b", re.I)
AJUDA_ESCOLA = re.compile(r"\b(?:me\s+ajuda|ajuda|preciso\s+de\s+ajuda)\b.{0,30}?\b(?:dever|li[cç][aã]o|tema|prova|trabalho|"
                          r"tarefa\s+(?:de|da)\s+escola|col[eé]gio|escola|redacao)\b", re.I)
VISUAL = re.compile(r"\b(?:corpo|cora[cç][aã]o|cerebro|esqueleto|musculos?|sistema\s+nervoso|cranio|"
                    r"c[eé]lula|[aá]tomo|sistema\s+solar|camadas\s+d[ae]\s+terra|vulc[aã]o|dna)\b", re.I)
ASSUNTO = re.compile(r"\b(?:de|do|da|das|dos|sobre|com)\s+(?P<q>.+)$", re.I)


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _assunto(texto):
    m = ASSUNTO.search(texto)
    return (m.group("q").strip(" .!?") if m else "").strip()


def entender(texto):
    t = texto or ""
    sa = _sa(t)
    tem_materia = bool(re.search(MATERIAS, sa))
    if EXERCICIO.search(t):
        return {"modo": "exercicio", "assunto": _assunto(t), "texto": t}
    if AJUDA_ESCOLA.search(t):
        return {"modo": "aula", "assunto": _assunto(t), "texto": t}
    if AULA.search(t):
        # "como se faz/calcula/resolve" só vira aula se tiver cara de matéria ou assunto claro
        if (re.search(r"como\s+(?:se\s+)?(?:faz|calcula|resolve)", sa) and not tem_materia and not _assunto(t)):
            return None
        return {"modo": "aula", "assunto": _assunto(t), "texto": t}
    return None


PEDIDO = {
    "aula": ("Dê uma mini-aula para o Rafael sobre: \"{texto}\". Estruture assim, curto: (1) o que é, em 1-2 frases; "
             "(2) como funciona / os pontos principais, em tópicos; (3) um exemplo do dia a dia; (4) termine com UMA "
             "pergunta rápida pra ele fixar. Comece pela resposta, sem 'claro, vou explicar'."),
    "exercicio": ("Crie UM exercício de ensino médio para o Rafael sobre: \"{texto}\" (se não disser a matéria, escolha "
                  "uma comum). Dê o enunciado claro. Depois de uma linha em branco, escreva 'Resposta:' com a solução "
                  "passo a passo. Assim ele tenta antes de olhar."),
}


def executar(p):
    assunto = p.get("assunto") or p.get("texto") or ""
    pedido = PEDIDO[p["modo"]].format(texto=assunto)
    try:
        texto = asyncio.run(cerebro.completar(
            [{"role": "system", "content": PROFESSOR}, {"role": "user", "content": pedido}],
            temperatura=0.5, max_tokens=700, dificil=True)).strip()
    except Exception:
        texto = ""
    if not texto:
        return "Não consegui preparar agora, chefe. Tenta de novo?", []

    dica_3d = bool(VISUAL.search(p.get("texto", "")))
    if p["modo"] == "exercicio":
        fala = "Separei um exercício pra você, chefe. Tenta resolver antes de ver a resposta."
        titulo = "Exercício"
    else:
        fala = "Bora estudar, chefe. Preparei a aula aí na tela." + (" Se quiser, posso te mostrar em 3D também." if dica_3d else "")
        titulo = "Aula"
    limpo = re.sub(r"[*`#]+", "", texto)  # tira markdown pro popup ficar limpo
    cartao = {"titulo": f"{titulo}" + (f" · {assunto[:40]}" if assunto else ""),
              "linhas": [l.strip() for l in limpo.split("\n") if l.strip()][:16], "copiar": texto}
    return fala, [cartao]
