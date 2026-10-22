"""Timer (contagem regressiva) e cronômetro por voz, com a contagem aparecendo na tela (web/timers.js).

Pedido dele (22/10): "quando eu pedir pra iniciar um timer de tanto tempo, ele conta, me avisa, e a contagem fica na tela".
"inicia um timer de 5 minutos", "timer de 1 hora e meia pro forno", "contagem regressiva de 30 segundos",
"conta 10 minutos", "quanto falta no timer", "pausa o timer", "continua o timer", "cancela o timer (do forno)",
"cancela todos os timers", "inicia o cronômetro" (conta pra cima), "para o cronômetro" (fala quanto deu).
Cada timer é do aparelho que pediu (PC ou celular, os "2 Jarvis"): só aparece e só avisa lá. timers.json guarda pra
sobreviver a um reinício.
"""
import json
import re
import time
import unicodedata
import uuid
from pathlib import Path

import extensao
import pomodoro
from lembretes import NUMEROS

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "timers.json"
DEMORA = False
MOSTRA_FIM = 12  # segundos que o "ACABOU" fica na tela depois de avisar

PALAVRA = r"(?:timers?|temporizador(?:es)?|contagem\s+regressiva|cron[oô]metros?)"
UNIDADE = r"(?:horas?|h|minutos?|mins?|segundos?|segs?|s)"
CANCELAR = re.compile(rf"\b(?:cancela|cancelar|cancele|para|parar|pare|desliga|desligar|tira|tirar|remove|apaga|apagar|zera|zerar|"
                      rf"encerra|encerrar|termina|terminar|finaliza)\s+(?P<todos>todos\s+os\s+|os\s+)?(?:o\s+|a\s+|meu\s+|esse\s+)?{PALAVRA}"
                      r"(?:\s+(?:d[oa]s?|pr[oa]s?|de)\s+(?P<o_que>.+?))?[.!]*$", re.I)
PAUSAR = re.compile(rf"\b(?:pausa|pausar|pause|segura)\s+(?:o\s+|a\s+)?{PALAVRA}", re.I)
VOLTAR = re.compile(rf"\b(?:volta|voltar|continua|continuar|retoma|retomar|despausa|solta)\s+(?:o\s+|a\s+)?{PALAVRA}", re.I)
FALTA = re.compile(rf"\b(?:quanto\s+(?:tempo\s+)?(?:falta|resta|deu|t[aá])|como\s+(?:t[aá]|est[aá])|quais\s+(?:s[aã]o\s+)?(?:os\s+)?(?:meus\s+)?)"
                   rf".*{PALAVRA}|{PALAVRA}.*\bquanto\s+(?:tempo\s+)?(?:falta|resta|deu)", re.I)
FALTA_SOLTO = re.compile(r"^(?:jarvis[ ,]*)?(?:e\s+)?(?:quanto\s+(?:tempo\s+)?(?:falta|resta)|tempo\s+restante|falta\s+quanto(?:\s+tempo)?)[?!.]*$", re.I)
INICIAR = re.compile(r"\b(?:inicia|iniciar|inicie|come[cç]a|come[cç]ar|liga|ligar|p[oõ]e|coloca|colocar|bota|cria|criar|marca|"
                     r"marcar|faz|fazer|abre|dispara|start|soltar?)\w*\b", re.I)
CONTA = re.compile(rf"^(?:jarvis[ ,]*)?(?:conta|contar|cronometra|cronometrar|marca|marcar)\s+(?:a[ií]\s+|pra\s+mim\s+)?"
                   rf"(?=\S+\s*{UNIDADE}\b)", re.I)

_timers = []


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _carregar():
    try:
        _timers[:] = [t for t in json.loads(ARQUIVO.read_text(encoding="utf-8")) if isinstance(t, dict)]
    except (OSError, ValueError):
        pass


def _gravar():
    ARQUIVO.write_text(json.dumps(_timers, ensure_ascii=False), encoding="utf-8")


_carregar()


def _duracao(texto):
    """Segundos pedidos: "1 hora e meia", "2 minutos e 30 segundos", "um minuto e meio", "meia hora", "90 s"."""
    s = _sa(texto)
    s = re.sub(r"\bmeia\s+hora\b", "30 minutos", s)
    for palavra in sorted(NUMEROS, key=len, reverse=True):
        s = re.sub(rf"\b{_sa(palavra)}\b", str(NUMEROS[palavra]), s)
    s = re.sub(r"\b([2-9]0)\s+e\s+([1-9])\b", lambda m: str(int(m.group(1)) + int(m.group(2))), s)  # "vinte e dois"
    total = 0.0
    for m in re.finditer(rf"(\d+(?:[.,]\d+)?)\s*({UNIDADE})\b(\s+e\s+mei[oa]\b)?", s):
        n = float(m.group(1).replace(",", ".")) + (0.5 if m.group(3) else 0)
        un = m.group(2)
        total += n * (3600 if un.startswith("h") else 60 if un.startswith("m") else 1)
    return round(total) or None


def _assunto(texto):
    m = re.search(r"\b(?:pr[ao]|para(?:\s+[oa])?|do|da)\s+(?!(?:o\s+|a\s+)?" + PALAVRA + r")(?P<a>[^\d].*?)[.!?]*$", texto, re.I)
    if not m:
        return ""
    a = re.sub(rf"\b\d+\s*{UNIDADE}\b.*$", "", m.group("a"), flags=re.I).strip(" ,")
    a = re.sub(r"^(?:o|a|os|as|mim|eu)\b\s*", "", a, flags=re.I)
    a = re.sub(r"\s+(?:de|em|por|com)$", "", a.strip(), flags=re.I)
    return "" if re.fullmatch(r"(?:mim|eu|)", a, re.I) else a[:40]


def _falado(segundos):
    segundos = int(round(segundos))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    partes = [f"{h} hora{'s' if h > 1 else ''}" if h else "", f"{m} minuto{'s' if m > 1 else ''}" if m else "",
              f"{s} segundo{'s' if s > 1 else ''}" if s and not h else ""]
    partes = [p for p in partes if p]
    return " e ".join(partes) if partes else "0 segundos"


def _relogio(segundos):
    segundos = max(0, int(segundos + 0.999))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _restante(t):
    return max(0.0, t["restante"] if t["pausado"] else t["fim"] - time.time())


def _decorrido(t):
    return t["acumulado"] + (0 if t["pausado"] else time.time() - t["inicio"])


def _meus():
    """Os do aparelho que está pedindo agora (PC ou celular), sem os que já acabaram."""
    o = extensao.origem.get()
    return [t for t in _timers if t["origem"] == o and not t.get("avisado")]


def _nome(t):
    tipo = "cronômetro" if t["tipo"] == "cronometro" else "timer"
    return f"{tipo} {'do' if t['tipo'] == 'cronometro' else 'de'} {t['assunto']}" if t["assunto"] else tipo


def entender(texto):
    t = texto.strip()
    if re.search(r"pomodoro|timer\s+de\s+foco", t, re.I):
        return None  # é do pomodoro.py
    m = CANCELAR.search(t)
    if m:
        return {"acao": "cancelar", "todos": bool(m.group("todos")), "o_que": (m.group("o_que") or "").strip(),
                "cronometro": bool(re.search(r"cron[oô]metro", t, re.I))}
    if PAUSAR.search(t):
        return {"acao": "pausar"}
    if VOLTAR.search(t):
        return {"acao": "voltar"}
    if FALTA.search(t) or (FALTA_SOLTO.search(t) and _meus() and not pomodoro.ativo()):
        return {"acao": "falta"}
    tem_palavra = re.search(PALAVRA, t, re.I)
    if not tem_palavra and not CONTA.search(t):
        return None
    segundos = _duracao(t)
    if segundos:
        return {"acao": "criar", "segundos": min(max(segundos, 1), 24 * 3600), "assunto": _assunto(t)}
    if tem_palavra and re.search(r"cron[oô]metro", t, re.I) and (INICIAR.search(t) or re.fullmatch(r"(?:jarvis[ ,]*)?cron[oô]metro[.!]*", t, re.I)):
        return {"acao": "cronometro", "assunto": _assunto(t)}
    if tem_palavra and INICIAR.search(t):
        return {"acao": "sem_tempo"}
    return None


def executar(p):
    a = p["acao"]
    meus = _meus()
    if a == "sem_tempo":
        return "De quanto tempo, chefe? Fala, por exemplo: timer de 5 minutos.", []
    if a == "criar":
        novo = {"id": uuid.uuid4().hex[:8], "tipo": "timer", "origem": extensao.origem.get(), "assunto": p["assunto"],
                "duracao": p["segundos"], "fim": time.time() + p["segundos"], "restante": p["segundos"], "pausado": False}
        _timers.append(novo)
        _gravar()
        sobre = f" pra {p['assunto']}" if p["assunto"] else ""
        return (f"Timer de {_falado(p['segundos'])}{sobre} valendo, chefe. Te aviso quando acabar.",
                [{"titulo": "Timer", "destaque": _relogio(p["segundos"]), "texto": p["assunto"] or "contagem regressiva", "rapido": True}])
    if a == "cronometro":
        _timers.append({"id": uuid.uuid4().hex[:8], "tipo": "cronometro", "origem": extensao.origem.get(), "assunto": p["assunto"],
                        "inicio": time.time(), "acumulado": 0.0, "pausado": False})
        _gravar()
        return "Cronômetro rodando, chefe. Quando quiser, fala: para o cronômetro.", []
    if not meus:
        return "Não tem nenhum timer rodando, chefe.", []
    if a == "falta":
        frases = []
        for t in meus:
            if t["tipo"] == "cronometro":
                frases.append(f"o {_nome(t)} tá em {_falado(_decorrido(t))}")
            else:
                frases.append(f"faltam {_falado(_restante(t))} no {_nome(t)}{', pausado' if t['pausado'] else ''}")
        fala = "; ".join(frases)
        return fala[0].upper() + fala[1:] + ", chefe.", []
    if a == "pausar":
        rodando = [t for t in meus if not t["pausado"]]
        if not rodando:
            return "Já tá pausado, chefe.", []
        for t in rodando:
            if t["tipo"] == "cronometro":
                t.update(acumulado=_decorrido(t), pausado=True)
            else:
                t.update(restante=_restante(t), pausado=True)
        _gravar()
        return "Pausei, chefe. Fala continua o timer quando quiser.", []
    if a == "voltar":
        parados = [t for t in meus if t["pausado"]]
        if not parados:
            return "Tá rodando, chefe.", []
        for t in parados:
            if t["tipo"] == "cronometro":
                t.update(inicio=time.time(), pausado=False)
            else:
                t.update(fim=time.time() + t["restante"], pausado=False)
        _gravar()
        return "Voltando, chefe.", []
    # cancelar
    alvo = _sa(p["o_que"])
    if p["cronometro"]:
        escolhidos = [t for t in meus if t["tipo"] == "cronometro"]
    elif alvo:
        escolhidos = [t for t in meus if alvo in _sa(t["assunto"])]
    else:
        escolhidos = meus if (p["todos"] or len(meus) == 1) else meus[-1:]  # sem dizer qual: o último que ele pediu
    if not escolhidos:
        return "Não achei esse timer, chefe.", []
    ids = {t["id"] for t in escolhidos}
    _timers[:] = [t for t in _timers if t["id"] not in ids]
    _gravar()
    cron = [t for t in escolhidos if t["tipo"] == "cronometro"]
    if cron and len(escolhidos) == 1:
        return f"Parei o cronômetro: deu {_falado(_decorrido(cron[0]))}, chefe.", []
    n = len(escolhidos)
    return (f"Cancelei o {_nome(escolhidos[0])}, chefe." if n == 1 else f"Cancelei {n} timers, chefe."), []


def cancelar_por_id(id_):
    antes = len(_timers)
    _timers[:] = [t for t in _timers if t["id"] != id_]
    if len(_timers) != antes:
        _gravar()
    return len(_timers) != antes


def situacao(origem="pc"):
    """Pra tela (web/timers.js): os timers DESTE aparelho com o tempo que falta (ou que já passou, no cronômetro)."""
    agora = time.time()
    saida = []
    for t in _timers:
        if t["origem"] != origem:
            continue
        if t["tipo"] == "cronometro":
            saida.append({"id": t["id"], "tipo": "cronometro", "assunto": t["assunto"], "decorrido": _decorrido(t), "pausado": t["pausado"]})
        else:
            saida.append({"id": t["id"], "tipo": "timer", "assunto": t["assunto"], "duracao": t["duracao"], "restante": _restante(t),
                          "pausado": t["pausado"], "acabou": bool(t.get("avisado"))})
    return {"agora": agora, "timers": saida}


def vencidos():
    """[(fala, cartão, origem)] dos timers que zeraram. O "ACABOU" fica uns segundos na tela e depois some."""
    agora = time.time()
    saida, mudou = [], False
    for t in _timers:
        if t["tipo"] != "timer" or t["pausado"] or t.get("avisado") or agora < t["fim"]:
            continue
        t["avisado"] = agora
        mudou = True
        if agora - t["fim"] > 3 * 3600:
            continue  # o PC estava desligado: não adianta avisar agora
        sobre = f" pra {t['assunto']}" if t["assunto"] else ""
        fala = f"Chefe, deu o tempo! Acabou o timer de {_falado(t['duracao'])}{sobre}."
        saida.append((fala, {"titulo": "Timer", "destaque": "Acabou!", "texto": t["assunto"] or _falado(t["duracao"]),
                             "rapido": True, "alerta": True}, t["origem"]))
    velhos = [t for t in _timers if t.get("avisado") and agora - t["avisado"] > MOSTRA_FIM]
    if velhos:
        _timers[:] = [t for t in _timers if t not in velhos]
        mudou = True
    if mudou:
        _gravar()
    return saida
