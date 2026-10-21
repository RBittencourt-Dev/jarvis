"""Anotações por voz (anotacoes.json): "anota: ideia pro Porthon, botão de exportar", "lê minhas anotações",
"apaga a última anotação", "apaga minhas anotações". Pra mandar uma pro Claude: "pede pro Claude …" (ponte já existe)."""
import json
import re
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "anotacoes.json"
DEMORA = False

ANOTAR = re.compile(r"^(?:jarvis[ ,]*)?(?:anota|anote|anotar|toma nota|guarda (?:essa|uma) (?:nota|ideia)|"
                    r"cria uma (?:nota|anota[cç][aã]o))(?:\s+a[ií])?(?:\s+(?:que|isso|ai|isto))?[\s:,]+(?P<texto>.{3,})$", re.I)
LER = re.compile(r"\b(?:l[eê]|ler|mostra|quais s[aã]o|me fala)\s+(?:as\s+)?(?:minhas\s+)?(?:anota[cç][oõ]es|notas)\b|"
                 r"^(?:minhas\s+)?anota[cç][oõ]es\??$", re.I)
APAGAR_ULTIMA = re.compile(r"\b(?:apaga|apagar|remove|tira|exclui)\s+a\s+[uú]ltima\s+(?:anota[cç][aã]o|nota)\b", re.I)
APAGAR_TUDO = re.compile(r"\b(?:apaga|apagar|limpa|limpar|exclui)\s+(?:todas\s+)?(?:as\s+)?(?:minhas\s+)?(?:anota[cç][oõ]es|notas)\b", re.I)


def _ler():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _gravar(lista):
    ARQUIVO.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def entender(texto):
    m = ANOTAR.match(texto.strip())
    if m:
        return {"acao": "anotar", "texto": m.group("texto").strip(" .")}
    if APAGAR_ULTIMA.search(texto):
        return {"acao": "apagar_ultima"}
    if APAGAR_TUDO.search(texto):
        return {"acao": "apagar_tudo"}
    if LER.search(texto):
        return {"acao": "ler"}
    return None


def executar(p):
    lista = _ler()
    if p["acao"] == "anotar":
        texto = p["texto"][0].upper() + p["texto"][1:]
        _gravar([*lista, {"texto": texto, "quando": time.time()}])
        return "Anotado, chefe.", [{"titulo": "Anotação", "destaque": texto[:60], "texto": texto if len(texto) > 60 else "",
                                    "rapido": True}]
    if p["acao"] == "apagar_ultima":
        if not lista:
            return "Não tem anotação nenhuma, chefe.", []
        _gravar(lista[:-1])
        return f"Apaguei: {lista[-1]['texto']}.", []
    if p["acao"] == "apagar_tudo":
        _gravar([])
        return f"Apaguei as {len(lista)} anotações, chefe." if lista else "Já não tinha nenhuma, chefe.", []
    if not lista:
        return "Você não tem anotação nenhuma, chefe. É só dizer 'anota' e o que quiser.", []
    ultimas = lista[-12:]
    linhas = [f"{datetime.fromtimestamp(a['quando']):%d/%m %H:%M} · {a['texto']}" for a in reversed(ultimas)]
    fala = f"Você tem {len(lista)} anotaç{'ões' if len(lista) > 1 else 'ão'}. " + \
           " ".join(f"{i + 1}: {a['texto']}." for i, a in enumerate(reversed(lista[-3:])))
    return fala, [{"titulo": "Anotações", "destaque": f"{len(lista)} no total", "linhas": linhas}]
