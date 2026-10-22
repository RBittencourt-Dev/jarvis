"""Falas programadas: num horário, o Jarvis FALA sozinho uma frase (mesmo com a tela fechada).

Pedido dele (22/10): "nas configs, programar falas em horários… tal horário ele fala sozinho tal coisa mesmo fechado".
Na tela: Configurações → Falas programadas. Por voz: "todo dia às 18h fala hora de ir embora",
"de segunda a sexta às 7 e meia diz bom dia, chefe", "amanhã às 9 anuncia reunião com o Rihan".
A frase pode ter {hora}, {data} e {dia} ("São {hora}, chefe" → "São 18:00, chefe").
Quem fala: a tela, se aberta; senão o segundo plano (palmas.falar_avisos) pela caixa de som. Fica em falas-programadas.json.
"""
import json
import re
import unicodedata
import uuid
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "falas-programadas.json"
DEMORA = False
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def todas():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(lista):
    ARQUIVO.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def limpar(f):
    texto = (f.get("texto") or "").strip()
    hora = (f.get("hora") or "").strip()
    if not texto:
        raise ValueError("Escreva o que ele vai falar.")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hora):
        raise ValueError("Horário no formato 08:30.")
    data = (f.get("data") or "").strip() or None  # só uma vez, nesse dia (AAAA-MM-DD)
    if data and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
        raise ValueError("Data inválida.")
    dias = sorted({int(d) for d in (f.get("dias") or range(7)) if str(d).isdigit() and 0 <= int(d) <= 6}) or list(range(7))
    return {"id": f.get("id") or uuid.uuid4().hex[:8], "hora": hora, "dias": dias, "data": data, "texto": texto,
            "ativa": bool(f.get("ativa", True))}


def salvar(f):
    f = limpar(f)
    _gravar([x for x in todas() if x["id"] != f["id"]] + [f])
    return f


def apagar(id_):
    _gravar([x for x in todas() if x["id"] != id_])


def preencher(texto, agora=None):
    agora = agora or datetime.now()
    return (texto.replace("{hora}", f"{agora:%H:%M}").replace("{data}", f"{agora:%d/%m}")
            .replace("{dia}", DIAS[agora.weekday()]))


def do_minuto(agora=None):
    """As falas deste minuto. As de uma vez só se apagam depois de faladas."""
    agora = agora or datetime.now()
    saida, sobra = [], []
    for f in todas():
        bate = f["ativa"] and f["hora"] == f"{agora:%H:%M}" and (
            f["data"] == f"{agora:%Y-%m-%d}" if f.get("data") else agora.weekday() in f["dias"])
        if bate:
            saida.append(f)
        if not (bate and f.get("data")):
            sobra.append(f)
    if len(sobra) != len(todas()):
        _gravar(sobra)
    return saida


# ------------------------------------------------------------------ por voz
FALAR = r"(?:fala|falar|diz|dizer|diga|fale|anuncia|anunciar|avisa\s+falando|me\s+fala|me\s+diz)"
QUANDO_DIAS = re.compile(
    r"\b(?P<todo>todo\s+dia|todos\s+os\s+dias|diariamente|sempre)\b|\b(?P<uteis>de\s+segunda\s+a\s+sexta|dias?\s+[uú]teis|durante\s+a\s+semana)\b|"
    r"\b(?P<fds>(?:no|nos|todo)\s+fins?\s+de\s+semana|s[aá]bado\s+e\s+domingo)\b|\b(?P<amanha>amanh[aã])\b|\b(?P<hoje>hoje)\b|"
    r"\b(?:toda|todo|nas?|nos?)\s+(?P<dia>segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)s?(?:-feira)?s?\b", re.I)
HORA = re.compile(r"\b(?:[aà]s|a|ao)\s+(?P<h>\d{1,2})(?:\s*(?:h|horas?|:)\s*(?P<m>\d{2})?)?(?:\s+e\s+(?P<meia>meia|\d{1,2}))?"
                  r"(?:\s+(?:da|de)\s+(?P<p>manh[aã]|tarde|noite|madrugada))?\b|\b(?P<meiodia>meio-?dia|meia-?noite)\b", re.I)
PEDIDO = re.compile(r"^(?:jarvis[ ,]*)?(?:(?:programa|agenda|cria|marca)\s+(?:uma\s+)?fala\b|.*\b" + FALAR + r"\b)", re.I)
LISTAR = re.compile(r"^(?:jarvis[ ,]*)?(?:quais|me\s+(?:fala|diz|mostra))\s+(?:s[aã]o\s+)?(?:as\s+)?(?:minhas\s+)?falas\s+programadas", re.I)
APAGAR = re.compile(r"^(?:jarvis[ ,]*)?(?:apaga|cancela|tira|remove)\s+(?:a\s+|as\s+)?(?:todas\s+as\s+)?falas?\s+programadas?"
                    r"(?:\s+(?:d[ao]s?|das)\s+(?P<h>\d{1,2})(?:\s*(?:h|:)\s*(?P<m>\d{2})?)?)?", re.I)


def _hora(m):
    if m.group("meiodia"):
        return "12:00" if "dia" in m.group("meiodia").lower() else "00:00"
    h = int(m.group("h"))
    mi = int(m.group("m") or 0)
    if m.group("meia"):
        mi = 30 if m.group("meia").lower() == "meia" else int(m.group("meia"))
    p = _sa(m.group("p") or "")
    if p in ("tarde", "noite") and h < 12:
        h += 12
    return f"{h % 24:02d}:{mi:02d}" if mi < 60 else None


def entender(texto):
    t = texto.strip()
    if LISTAR.match(t):
        return {"acao": "listar"}
    m = APAGAR.match(t)
    if m:
        return {"acao": "apagar", "hora": f"{int(m.group('h')):02d}:{int(m.group('m') or 0):02d}" if m.group("h") else None}
    if not PEDIDO.match(t) or re.search(r"\bme\s+lembr|\blembrete|\balarme", t, re.I):
        return None  # "me lembra às 15h" é lembrete (uma vez, com pop-up); aqui é fala repetida/agendada
    d = QUANDO_DIAS.search(t)
    h = HORA.search(t)
    if not (d and h):
        return None  # sem dia E hora não é fala programada ("fala pro Rihan que…" é WhatsApp)
    hora = _hora(h)
    if not hora:
        return None
    # o que falar: o que vem depois do verbo (tirando o "que" e o "às X" se vieram depois)
    resto = re.split(r"\b" + FALAR + r"\b", t, maxsplit=1, flags=re.I)
    frase = resto[-1] if len(resto) > 1 else ""
    frase = HORA.sub("", QUANDO_DIAS.sub("", frase))
    frase = re.sub(r"^[\s,:]*(?:que\s+|isso:?\s*|assim:?\s*|pra\s+mim\s+)?", "", frase).strip(" ,.\"'")
    if not frase:
        return None
    hoje = datetime.now()
    dias, data = list(range(7)), None
    if d.group("uteis"):
        dias = [0, 1, 2, 3, 4]
    elif d.group("fds"):
        dias = [5, 6]
    elif d.group("dia"):
        dias = [[_sa(x) for x in DIAS].index(_sa(d.group("dia")).replace("terca", "terca"))]
    elif d.group("amanha"):
        data = f"{hoje + timedelta(days=1):%Y-%m-%d}"
    elif d.group("hoje"):
        data = f"{hoje:%Y-%m-%d}"
    return {"acao": "criar", "hora": hora, "dias": dias, "data": data, "texto": frase[0].upper() + frase[1:]}


def _quando(f):
    if f.get("data"):
        return f"no dia {f['data'][8:10]}/{f['data'][5:7]} às {f['hora']}"
    if f["dias"] == list(range(7)):
        return f"todo dia às {f['hora']}"
    if f["dias"] == [0, 1, 2, 3, 4]:
        return f"de segunda a sexta às {f['hora']}"
    return ", ".join(DIAS[i] for i in f["dias"]) + f" às {f['hora']}"


def executar(p):
    if p["acao"] == "listar":
        lista = [f for f in todas() if f["ativa"]]
        if not lista:
            return ("Não tem nenhuma fala programada, chefe.",)
        return (f"Tem {len(lista)} fala{'s' if len(lista) > 1 else ''} programada{'s' if len(lista) > 1 else ''}.",
                [{"titulo": "Falas programadas", "linhas": [f"{_quando(f)}: {f['texto']}" for f in lista][:10]}])
    if p["acao"] == "apagar":
        antes = todas()
        fica = [f for f in antes if p["hora"] and f["hora"] != p["hora"]]
        _gravar(fica)
        n = len(antes) - len(fica)
        return (f"Apaguei {n} fala{'s' if n != 1 else ''} programada{'s' if n != 1 else ''}, chefe.",)
    f = salvar(p)
    return (f"Combinado: {_quando(f)} eu falo \"{f['texto']}\".",)
