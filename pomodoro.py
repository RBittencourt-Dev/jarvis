"""Pomodoro por voz: foco de 25 min (ou o que ele pedir), pausa de 5 (15 a cada 4 focos).

"inicia um pomodoro", "bora focar 50 minutos", "pausa o pomodoro", "volta o pomodoro", "cancela o pomodoro",
"quanto tempo falta", "como tá o pomodoro". Ao entrar no modo caverna o Jarvis oferece um.
O estado fica na memória do servidor (pomodoro.json guarda só pra sobreviver a um reinício).
"""
import json
import re
import time
from pathlib import Path

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "pomodoro.json"
DEMORA = False
FOCO, PAUSA, PAUSA_LONGA = 25, 5, 15

POMO = r"(?:pomodoro|pomodoros|foco|focar|timer de foco|ciclo)"
INICIAR = re.compile(rf"\b(?:inicia|iniciar|inicie|come[cç]a|come[cç]ar|liga|bora|vamos|partiu|start)\w*\s+(?:um\s+|o\s+|uma\s+)?{POMO}"
                     r"(?:\s+(?:de\s+)?(?P<min>\d+)\s*(?:minutos?|min)?)?\b|\bbora\s+focar(?:\s+(?P<min2>\d+)\s*(?:minutos?|min))?", re.I)
PAUSAR = re.compile(rf"\b(?:pausa|pausar|pause|segura|para)\s+(?:o\s+)?{POMO}\b", re.I)
VOLTAR = re.compile(rf"\b(?:volta|voltar|continua|continuar|retoma|retomar|despausa)\s+(?:o\s+)?{POMO}\b", re.I)
CANCELAR = re.compile(rf"\b(?:cancela|cancelar|encerra|encerrar|termina|terminar|desliga|para\s+de\s+vez)\s+(?:o\s+)?{POMO}\b", re.I)
FALTA = re.compile(r"\b(?:quanto\s+(?:tempo\s+)?falta|quanto\s+(?:ainda\s+)?tem|como\s+(?:t[aá]|est[aá])\s+o\s+pomodoro|"
                   r"tempo\s+restante|falta\s+quanto)\b", re.I)

_estado = {"fase": None, "fim": 0.0, "restante": 0.0, "pausado": False, "duracao": FOCO, "ciclos": 0}


def _gravar():
    ARQUIVO.write_text(json.dumps(_estado), encoding="utf-8")


def _carregar():
    try:
        _estado.update(json.loads(ARQUIVO.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass


_carregar()


def ativo():
    return _estado["fase"] is not None


def restante():
    if not ativo():
        return 0
    return max(0, _estado["restante"] if _estado["pausado"] else _estado["fim"] - time.time())


def _mmss(segundos):
    m, s = divmod(int(segundos + 0.5), 60)
    if m and s:
        return f"{m} minuto{'s' if m > 1 else ''} e {s} segundos"
    return f"{m} minuto{'s' if m > 1 else ''}" if m else f"{s} segundos"


def situacao():
    """Pro painel da extensão: {fase, fim, restante, pausado, duracao, ciclos} ou None."""
    if not ativo():
        return None
    return {**_estado, "restante": restante()}


def entender(texto):
    m = INICIAR.search(texto)
    if m:
        return {"acao": "iniciar", "min": int(m.group("min") or m.group("min2") or FOCO)}
    if CANCELAR.search(texto):
        return {"acao": "cancelar"}
    if PAUSAR.search(texto):
        return {"acao": "pausar"}
    if VOLTAR.search(texto):
        return {"acao": "voltar"}
    if FALTA.search(texto) and ativo():
        return {"acao": "falta"}
    return None


def iniciar(minutos=FOCO, fase="foco"):
    _estado.update(fase=fase, fim=time.time() + minutos * 60, restante=minutos * 60, pausado=False, duracao=minutos)
    _gravar()


def executar(p):
    a = p["acao"]
    if a == "iniciar":
        iniciar(min(max(p["min"], 1), 180))
        return (f"Pomodoro de {p['min']} minutos valendo, chefe. Foco total; eu te aviso na hora da pausa.",
                [{"titulo": "Pomodoro", "destaque": f"{p['min']}:00", "texto": "Foco", "rapido": True}])
    if not ativo():
        return "Não tem pomodoro rodando, chefe. Quer que eu comece um?", []
    if a == "cancelar":
        _estado.update(fase=None, pausado=False)
        _gravar()
        return "Pomodoro cancelado, chefe.", []
    if a == "pausar":
        if _estado["pausado"]:
            return "Já tá pausado, chefe.", []
        _estado.update(pausado=True, restante=restante())
        _gravar()
        return f"Pausei. Faltavam {_mmss(_estado['restante'])}.", []
    if a == "voltar":
        if not _estado["pausado"]:
            return f"Tá rodando, chefe. Faltam {_mmss(restante())}.", []
        _estado.update(pausado=False, fim=time.time() + _estado["restante"])
        _gravar()
        return f"Voltando. Faltam {_mmss(_estado['restante'])}.", []
    fase = "de foco" if _estado["fase"] == "foco" else "de pausa"
    return f"Faltam {_mmss(restante())} {fase}{', pausado' if _estado['pausado'] else ''}, chefe.", []


def vencidos():
    """Troca de fase quando o tempo acaba: [(fala, cartão)]."""
    if not ativo() or _estado["pausado"] or time.time() < _estado["fim"]:
        return []
    if _estado["fase"] == "foco":
        _estado["ciclos"] += 1
        longa = _estado["ciclos"] % 4 == 0
        minutos = PAUSA_LONGA if longa else PAUSA
        iniciar(minutos, "pausa")
        fala = (f"Fim do foco, chefe. Bom trabalho! {'Agora uma pausa longa' if longa else 'Pausa'} de {minutos} minutos: "
                "levanta, toma uma água.")
        return [(fala, {"titulo": "Pomodoro", "destaque": "Pausa", "texto": f"{minutos} minutos", "rapido": True, "alerta": True})]
    _estado.update(fase=None)
    _gravar()
    return [("Fim da pausa, chefe. Bora pra mais um? É só dizer 'inicia o pomodoro'.",
             {"titulo": "Pomodoro", "destaque": "Pausa acabou", "texto": "Diga 'inicia o pomodoro'", "rapido": True, "alerta": True})]
