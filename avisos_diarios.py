"""Avisos diários por voz: entram no resumo do dia ("Todos os sistemas online…") deste PC.

Pedido dele (22/10): "como ensino ele a configurar os avisos diários?". Pela tela: Configurações → Abertura.
Por voz: "adiciona um aviso diário: conferir os Chromebooks carregando", "de segunda a sexta, aviso do dia: abrir o
auditório às 7h", "toda sexta aviso diário recolher os Chromebooks", "quais são os avisos diários",
"apaga o aviso dos Chromebooks", "apaga todos os avisos diários".
Ficam em config.json → abertura.avisos ([{texto, dias, ativo}]), o mesmo que a tela edita.
"""
import json
import re
import unicodedata
from pathlib import Path

ARQUIVO = Path(__file__).parent / "config.json"
DEMORA = False
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

AVISO = r"avisos?\s+(?:di[aá]rios?|do\s+dia|de\s+todo\s+dia|da\s+abertura)"
CRIAR = re.compile(r"^(?:jarvis[ ,]*)?(?P<antes>.*?)\b(?:adiciona|adicionar|cria|criar|coloca|colocar|p[oõ]e|bota|inclui|incluir|novo)\s+"
                   r"(?:um\s+|o\s+|mais\s+um\s+)?" + AVISO + r"[\s,:;-]*(?:que\s+|pra\s+|de\s+|dizendo\s+)?(?P<texto>.+?)[.!]*$", re.I)
CRIAR2 = re.compile(r"^(?:jarvis[ ,]*)?(?P<antes>.*?)\b" + AVISO + r"[\s,:;-]+(?:que\s+|pra\s+|de\s+)?(?P<texto>(?!d[eo]s?\b).+?)[.!]*$", re.I)
LISTAR = re.compile(r"^(?:jarvis[ ,]*)?(?:quais|me\s+(?:fala|diz|mostra)|lista|listar|ver|mostra)\s+(?:s[aã]o\s+|os\s+|meus\s+|os\s+meus\s+)*" + AVISO, re.I)
APAGAR = re.compile(r"^(?:jarvis[ ,]*)?(?:apaga|apagar|tira|tirar|remove|remover|cancela|exclui)\s+(?P<todos>todos\s+os\s+)?(?:o\s+|os\s+)?"
                    r"(?:" + AVISO + r"|aviso)(?:\s+(?:d[eoa]s?|sobre|que\s+fala\s+d[eoa]s?)\s+(?P<o_que>.+?))?[.!]*$", re.I)


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _ler():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def avisos():
    return [x for x in (_ler().get("abertura") or {}).get("avisos") or [] if isinstance(x, dict)]


def _gravar(lista):
    c = _ler()
    c["abertura"] = {**(c.get("abertura") or {}), "avisos": lista}
    ARQUIVO.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


def _dias(t):
    t = _sa(t)
    if re.search(r"segunda\s+a\s+sexta|dias?\s+uteis|durante\s+a\s+semana", t):
        return [0, 1, 2, 3, 4]
    if re.search(r"fins?\s+de\s+semana|sabado\s+e\s+domingo", t):
        return [5, 6]
    achados = [i for i, d in enumerate(_sa(x) for x in DIAS) if re.search(r"\b" + d[:5], t)]
    return achados or list(range(7))


def _quando(dias):
    if len(dias) == 7:
        return "todo dia"
    if dias == [0, 1, 2, 3, 4]:
        return "de segunda a sexta"
    return ", ".join(DIAS[i] for i in dias)


def entender(texto):
    t = texto.strip()
    if LISTAR.match(t):
        return {"acao": "listar"}
    m = APAGAR.match(t)
    if m:
        return {"acao": "apagar", "todos": bool(m.group("todos")), "o_que": (m.group("o_que") or "").strip()}
    m = CRIAR.match(t) or CRIAR2.match(t)
    if m and m.group("texto").strip():
        texto_ = m.group("texto").strip()
        # os dias podem vir antes ("de segunda a sexta, aviso do dia: …") ou no fim ("… de segunda a sexta")
        fim = re.search(r",?\s*(?:de\s+segunda\s+a\s+sexta|todo\s+dia|todos\s+os\s+dias|nos?\s+dias?\s+[uú]teis|"
                        r"(?:toda|todo|nas?|nos?)\s+(?:segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)s?(?:-feira)?s?)$", texto_, re.I)
        dias = _dias(m.group("antes") + " " + (fim.group(0) if fim else ""))
        if fim:
            texto_ = texto_[:fim.start()].strip(" ,")
        return {"acao": "criar", "texto": texto_[0].upper() + texto_[1:], "dias": dias}
    return None


def executar(p):
    lista = avisos()
    if p["acao"] == "listar":
        if not lista:
            return ("Nenhum aviso diário neste PC. Fala, por exemplo: adiciona um aviso diário: conferir os Chromebooks.",)
        return (f"{len(lista)} aviso{'s' if len(lista) > 1 else ''} diário{'s' if len(lista) > 1 else ''}: "
                + ". ".join(f"{x['texto']}, {_quando(x.get('dias') or list(range(7)))}" for x in lista) + ".",
                [{"titulo": "Avisos diários", "linhas": [f"{_quando(x.get('dias') or list(range(7)))}: {x['texto']}" for x in lista]}])
    if p["acao"] == "apagar":
        if p["todos"] or not p["o_que"]:
            if not p["todos"] and len(lista) > 1:
                return ("Qual deles, chefe? Fala: apaga o aviso dos Chromebooks. Ou: apaga todos os avisos diários.",)
            _gravar([])
            return ("Apaguei os avisos diários deste PC." if lista else "Não tinha nenhum aviso diário.",)
        palavras = [w for w in _sa(p["o_que"]).split() if len(w) > 2]
        fica = [x for x in lista if not all(w in _sa(x["texto"]) for w in palavras)]
        if len(fica) == len(lista):
            return (f"Não achei aviso sobre {p['o_que']}.",)
        _gravar(fica)
        return (f"Apaguei {len(lista) - len(fica)} aviso{'s' if len(lista) - len(fica) > 1 else ''}.",)
    lista.append({"texto": p["texto"], "dias": p["dias"], "ativo": True})
    _gravar(lista)
    return (f"Combinado: {_quando(p['dias'])}, quando eu abrir, aviso: {p['texto']}.",)
