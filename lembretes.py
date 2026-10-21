"""Lembretes e alarmes por voz (lembretes.json).

"me lembra às 15h de ligar pro Jesus", "me lembra em 20 minutos de tirar o bolo", "daqui a meia hora me avisa",
"me acorda em 20 minutos", "amanhã às 9 me lembra da reunião", "quais meus lembretes", "cancela o lembrete do bolo".
Na hora, o servidor pega os vencidos (vencidos()) e o Jarvis fala + mostra um pop-up que some sozinho.
"""
import json
import re
import time
import unicodedata
import uuid
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "lembretes.json"
DEMORA = False

NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
           "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14, "quinze": 15,
           "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20, "vinte e cinco": 25,
           "trinta": 30, "quarenta": 40, "quarenta e cinco": 45, "cinquenta": 50, "sessenta": 60, "noventa": 90}
NUM = r"(\d+(?:[.,]\d+)?|" + "|".join(sorted(NUMEROS, key=len, reverse=True)) + r"|meia|meio)"

GATILHO = re.compile(r"\b(?:me\s+lembr\w*|lembr[ae]\s+(?:de\s+)?me|me\s+avis\w*|avis[ae]\s+(?:-?me|eu)|me\s+acord\w*|"
                     r"alarme|despertador|timer|cron[oô]metro|lembrete)\b", re.I)
EM = re.compile(rf"\b(?:em|daqui\s+a|daqui|dentro\s+de|de|por)\s+{NUM}\s*(?P<unidade>segundos?|seg|minutos?|min|horas?|h)\b"
                rf"|\b(?:em|daqui\s+a|daqui)\s+(?P<meia>meia)\s+hora\b", re.I)
AS = re.compile(r"\b(?:[aà]s|pras?|para\s+as|ao?|meio-?dia)\s*(?P<h>\d{1,2}|" + "|".join(NUMEROS) + r")?"
                r"(?:\s*(?:h|horas?|:)\s*(?P<m>\d{2})?)?(?:\s+e\s+(?P<m2>\d{1,2}|meia|" + "|".join(NUMEROS) + r"))?"
                r"(?:\s+(?:da|de)\s+(?P<periodo>manh[aã]|tarde|noite|madrugada))?\b", re.I)
LISTAR = re.compile(r"\b(?:quais|que|me\s+(?:fala|diz|l[eê])|lista)\b.*\b(?:lembretes?|alarmes?)\b|^(?:meus\s+)?lembretes\??$", re.I)
CANCELAR = re.compile(r"\b(?:cancela|apaga|tira|remove|desliga)\w*\s+(?:o\s+|os\s+|a\s+|as\s+|todos\s+os\s+|meus\s+)?"
                      r"(?:lembretes?|alarmes?|timers?|despertador)(?:\s+(?:d[aeo]s?|pra|que)\s+(?P<o_que>.+))?$", re.I)


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _numero(t):
    if t is None:
        return None
    t = _sem_acento(t.strip())
    if t in ("meia", "meio"):
        return 0.5
    if t in NUMEROS:
        return NUMEROS[t]
    try:
        return float(t.replace(",", "."))
    except ValueError:
        return None


def _ler():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(lista):
    ARQUIVO.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def _quando(texto):
    """timestamp do lembrete, ou None se não deu pra entender a hora."""
    agora = datetime.now()
    m = EM.search(texto)
    if m:
        if m.group("meia"):
            return (agora + timedelta(minutes=30)).timestamp()
        n = _numero(m.group(1))
        un = _sem_acento(m.group("unidade"))
        if n is None:
            return None
        segundos = n * (3600 if un.startswith("h") else 1 if un.startswith("seg") else 60)
        return time.time() + segundos
    if re.search(r"\bmeio-?dia\b", texto, re.I):
        alvo = agora.replace(hour=12, minute=0, second=0, microsecond=0)
    else:
        m = AS.search(texto)
        if not m or not m.group("h"):
            return None
        h = int(_numero(m.group("h")))
        minuto = int(m.group("m") or 0)
        if m.group("m2"):
            minuto = 30 if _sem_acento(m.group("m2")) == "meia" else int(_numero(m.group("m2")) or 0)
        periodo = _sem_acento(m.group("periodo") or "")
        if periodo in ("tarde", "noite") and h < 12:
            h += 12
        if h > 23 or minuto > 59:
            return None
        alvo = agora.replace(hour=h, minute=minuto, second=0, microsecond=0)
        amanha = bool(re.search(r"\bamanh[aã]\b", texto, re.I))
        if not periodo and not amanha and h < 12 and alvo <= agora and agora.hour >= 12:
            alvo = alvo.replace(hour=h + 12)  # "às 3" depois do meio-dia = 15h
    if re.search(r"\bamanh[aã]\b", texto, re.I):
        alvo += timedelta(days=1)
    elif alvo <= agora:
        alvo += timedelta(days=1)
    return alvo.timestamp()


def _o_que(texto):
    """O assunto do lembrete: tira o gatilho e a hora; sobra "ligar pro Jesus"."""
    t = re.sub(r"^(?:jarvis[ ,]*)", "", texto.strip(), flags=re.I)
    t = EM.sub(" ", t)
    t = re.sub(r"\bamanh[aã]\b|\bhoje\b|\bmeio-?dia\b", " ", t, flags=re.I)
    t = AS.sub(lambda m: " " if m.group("h") else m.group(0), t)
    t = GATILHO.sub(" ", t)
    t = re.sub(r"^\W*(?:de|que|pra|para|do|da|disso|isso|a[ií])\b", " ", t.strip(), flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" ,.!?")
    return t


def entender(texto):
    if CANCELAR.search(texto):
        return {"acao": "cancelar", "o_que": (CANCELAR.search(texto).group("o_que") or "").strip()}
    if LISTAR.search(texto):
        return {"acao": "listar"}
    if not GATILHO.search(texto):
        return None
    quando = _quando(texto)
    if quando is None:
        return None if not re.search(r"\b(?:lembr|alarme|acord|timer)", texto, re.I) else {"acao": "sem_hora"}
    acorda = bool(re.search(r"\bacord|despertador\b", texto, re.I))
    return {"acao": "criar", "quando": quando, "o_que": _o_que(texto) or ("acordar" if acorda else ""), "alarme": acorda}


def _quando_falado(ts):
    alvo = datetime.fromtimestamp(ts)
    falta = ts - time.time()
    if falta < 3600:
        minutos = max(1, round(falta / 60))
        return f"daqui a {minutos} minuto{'s' if minutos > 1 else ''}" if falta >= 60 else f"daqui a {round(falta)} segundos"
    dia = "amanhã " if alvo.date() > datetime.now().date() else ""
    return f"{dia}às {alvo:%H:%M}"


def executar(p):
    lista = _ler()
    if p["acao"] == "sem_hora":
        return "Pra quando, chefe? Me diz a hora ou daqui a quantos minutos.", []
    if p["acao"] == "listar":
        futuros = sorted((l for l in lista if l["quando"] > time.time()), key=lambda l: l["quando"])
        if not futuros:
            return "Você não tem nenhum lembrete marcado, chefe.", []
        linhas = [f"{datetime.fromtimestamp(l['quando']):%d/%m %H:%M} · {l['texto'] or 'lembrete'}" for l in futuros[:10]]
        fala = f"Você tem {len(futuros)} lembrete{'s' if len(futuros) > 1 else ''}. O próximo é " \
               f"{futuros[0]['texto'] or 'um lembrete'}, {_quando_falado(futuros[0]['quando'])}."
        return fala, [{"titulo": "Lembretes", "destaque": f"{len(futuros)} marcados", "linhas": linhas}]
    if p["acao"] == "cancelar":
        alvo = _sem_acento(p["o_que"])
        fica = [l for l in lista if alvo and alvo not in _sem_acento(l["texto"])] if alvo else []
        if len(fica) == len(lista):
            return "Não achei esse lembrete, chefe.", []
        _gravar(fica)
        n = len(lista) - len(fica)
        return f"Cancelei {n} lembrete{'s' if n > 1 else ''}, chefe.", []
    novo = {"id": uuid.uuid4().hex[:8], "quando": p["quando"], "texto": p["o_que"], "alarme": p["alarme"],
            "criado": time.time()}
    _gravar([*lista, novo])
    sobre = f" de {p['o_que']}" if p["o_que"] and p["o_que"] != "acordar" else ""
    hora = f"{datetime.fromtimestamp(p['quando']):%H:%M}"
    return (f"Fechado, chefe. Te {'acordo' if p['alarme'] else 'lembro'}{sobre} {_quando_falado(p['quando'])}.",
            [{"titulo": "Lembrete marcado", "destaque": hora, "texto": p["o_que"] or "", "rapido": True}])


def vencidos():
    """[(fala, cartao)] dos lembretes que chegaram na hora; tira eles da lista."""
    lista = _ler()
    agora = time.time()
    chegaram = [l for l in lista if l["quando"] <= agora]
    if not chegaram:
        return []
    _gravar([l for l in lista if l["quando"] > agora])
    saida = []
    for l in chegaram:
        if agora - l["quando"] > 3 * 3600:
            continue  # o PC estava desligado na hora: aviso de 3 h atrás não serve mais
        if l.get("alarme"):
            fala = "Chefe, tá na hora! " + (f"Você pediu pra eu te acordar pra {l['texto']}." if l["texto"] != "acordar" else "Hora de acordar.")
        else:
            fala = f"Chefe, lembrete: {l['texto']}." if l["texto"] else "Chefe, deu a hora do seu lembrete."
        saida.append((fala, {"titulo": "Alarme" if l.get("alarme") else "Lembrete", "destaque": l["texto"] or "Hora!",
                             "texto": f"{datetime.fromtimestamp(l['quando']):%H:%M}", "rapido": True, "alerta": True}))
    return saida
