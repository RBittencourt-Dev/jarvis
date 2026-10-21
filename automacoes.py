"""Automações (rotinas) que o Rafael monta pelo botão ⚙ da tela.

Cada uma tem um gatilho e uma lista de ações. Ação = qualquer coisa que se fala pro Jarvis
("abre o VS Code", "toca Development", "quanto tem no caixa"), executada em ordem.
Gatilhos:
  frase    — quando ele disser a frase ("bom dia jarvis", "hora de trabalhar")
  horario  — todo dia (ou nos dias marcados) no horário
  ao_ligar — quando o PC liga (uma vez por ligada)
Fica em automacoes.json.
"""
import json
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "automacoes.json"
TIPOS = ("frase", "horario", "ao_ligar")


def _sem_acento(t):
    t = "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"\w+", t))


def todas():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(lista):
    ARQUIVO.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def limpar(a):
    """Confere o que veio da tela e devolve a automação arrumada (ou levanta ValueError)."""
    tipo = a.get("tipo")
    if tipo not in TIPOS:
        raise ValueError("Gatilho inválido.")
    acoes = [x.strip() for x in (a.get("acoes") or []) if str(x).strip()]
    if not acoes:
        raise ValueError("Coloque pelo menos uma ação.")
    nome = (a.get("nome") or "").strip() or acoes[0][:40]
    frase = (a.get("frase") or "").strip()
    hora = (a.get("hora") or "").strip()
    if tipo == "frase" and len(_sem_acento(frase)) < 3:
        raise ValueError("Escreva a frase que dispara.")
    if tipo == "horario" and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", hora):
        raise ValueError("Horário no formato 08:30.")
    dias = sorted({int(d) for d in (a.get("dias") or range(7)) if str(d).isdigit() and 0 <= int(d) <= 6}) or list(range(7))
    return {"id": a.get("id") or uuid.uuid4().hex[:8], "nome": nome, "tipo": tipo, "frase": frase, "hora": hora,
            "dias": dias, "acoes": acoes, "ativa": bool(a.get("ativa", True))}


def salvar(a):
    a = limpar(a)
    lista = [x for x in todas() if x["id"] != a["id"]]
    lista.append(a)
    _gravar(lista)
    return a


def apagar(id_):
    _gravar([x for x in todas() if x["id"] != id_])


def pela_frase(texto):
    """A automação cuja frase ele disse (frase inteira, ou a frase dentro de uma fala curta)."""
    dito = _sem_acento(re.sub(r"^\s*jarvis[\s,]*", "", texto, flags=re.I))
    for a in todas():
        if a["ativa"] and a["tipo"] == "frase":
            alvo = _sem_acento(a["frase"])
            if dito == alvo or (alvo in dito and len(dito.split()) <= len(alvo.split()) + 3):
                return a
    return None


def do_minuto(agora=None):
    """As automações de horário que batem com este minuto."""
    agora = agora or datetime.now()
    return [a for a in todas() if a["ativa"] and a["tipo"] == "horario"
            and a["hora"] == f"{agora:%H:%M}" and agora.weekday() in a["dias"]]


def ao_ligar():
    return [a for a in todas() if a["ativa"] and a["tipo"] == "ao_ligar"]
