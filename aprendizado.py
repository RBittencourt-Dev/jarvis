"""Como o Jarvis aprende sozinho e com o Rafael (habilidades-aprendidas.json).

Dois jeitos:
1. SOZINHO: quando ele resolve um pedido usando ferramentas e dá certo, guarda o caminho
   (pedido → ferramentas usadas). Num pedido parecido depois, o caminho vai junto pro cérebro
   como "da última vez deu certo assim", e ele repete direto em vez de quebrar a cabeça de novo.
2. ENSINADO: o Rafael fala "aprende que…" / "quando eu pedir X, faz Y" e o cérebro grava uma
   habilidade com nome, quando usar e como fazer. Essas vão SEMPRE no prompt (são as regras dele).
"Esquece a habilidade X" apaga. "Errado" logo depois de um pedido apaga o caminho que ele acabou de gravar.
"""
import json
import re
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "habilidades-aprendidas.json"
VAZIAS = {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "pra", "para", "pro", "me", "eu", "e", "que",
          "no", "na", "em", "jarvis", "chefe", "por", "favor", "ai", "aqui", "isso", "esse", "essa", "com", "tu", "voce"}
NAO_GRAVAR = {"lembrar", "aprender_habilidade", "esquecer_habilidade"}  # memória não é "caminho"


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def palavras(t):
    return set(re.findall(r"\w+", _sem_acento(t))) - VAZIAS


def _ler():
    try:
        d = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        return {"ensinadas": d.get("ensinadas", []), "caminhos": d.get("caminhos", [])}
    except (OSError, ValueError):
        return {"ensinadas": [], "caminhos": []}


def _gravar(d):
    ARQUIVO.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ 1. sozinho: caminhos que deram certo

def gravar_caminho(pedido, passos):
    """passos = [{"ferramenta": nome, "args": {...}}]. Mesmo pedido de novo: troca pelo caminho mais novo."""
    passos = [p for p in passos if p["ferramenta"] not in NAO_GRAVAR]
    if not passos or len(palavras(pedido)) < 2:
        return
    d = _ler()
    chave = sorted(palavras(pedido))
    antigo = next((c for c in d["caminhos"] if c["chave"] == chave), None)
    vezes = (antigo or {}).get("vezes", 0) + 1
    d["caminhos"] = [c for c in d["caminhos"] if c["chave"] != chave]
    d["caminhos"].append({"pedido": pedido, "chave": chave, "passos": passos, "vezes": vezes, "quando": time.strftime("%d/%m %H:%M")})
    d["caminhos"] = d["caminhos"][-300:]
    _gravar(d)


def caminho_parecido(pedido, minimo=0.6):
    """O caminho de um pedido parecido (Jaccard das palavras ≥ mínimo), ou None."""
    dele = palavras(pedido)
    if len(dele) < 2:
        return None
    melhor, nota = None, 0.0
    for c in _ler()["caminhos"]:
        outro = set(c["chave"])
        n = len(dele & outro) / len(dele | outro)
        if n > nota:
            melhor, nota = c, n
    return melhor if nota >= minimo else None


def esquecer_ultimo_caminho():
    d = _ler()
    if not d["caminhos"]:
        return None
    c = d["caminhos"].pop()
    _gravar(d)
    return c["pedido"]


def dica_do_caminho(pedido):
    c = caminho_parecido(pedido)
    if not c:
        return ""
    passos = "; ".join(f"{p['ferramenta']}({json.dumps(p['args'], ensure_ascii=False)[:300]})" for p in c["passos"])
    return (f"\n\n[Você já resolveu algo parecido (\"{c['pedido']}\", {c['vezes']}x) assim: {passos}. "
            "Se servir, repita direto, ajustando o que mudou.]")


# ------------------------------------------------------------------ 2. ensinado por ele

def aprender_habilidade(nome: str, quando_usar: str, como_fazer: str):
    d = _ler()
    d["ensinadas"] = [h for h in d["ensinadas"] if _sem_acento(h["nome"]) != _sem_acento(nome)]
    d["ensinadas"].append({"nome": nome.strip(), "quando": quando_usar.strip(), "como": como_fazer.strip(),
                           "desde": time.strftime("%d/%m/%Y")})
    _gravar(d)
    return f"Aprendi a habilidade '{nome}'."


def esquecer_habilidade(nome: str):
    d = _ler()
    antes = len(d["ensinadas"])
    alvo = palavras(nome)
    d["ensinadas"] = [h for h in d["ensinadas"] if not (alvo and alvo <= palavras(h["nome"] + " " + h["quando"]))]
    _gravar(d)
    return "Esqueci." if len(d["ensinadas"]) < antes else f"Não achei habilidade chamada '{nome}'."


def ensinadas_para_prompt():
    hs = _ler()["ensinadas"]
    if not hs:
        return "(nenhuma ainda)"
    return "\n".join(f"- {h['nome']}: quando {h['quando']} → {h['como']}" for h in hs[-40:])


def resumo():
    d = _ler()
    return len(d["ensinadas"]), len(d["caminhos"])


def listar():
    """Pra tela de Configurações → Memória: as habilidades que ele ensinou."""
    return _ler()["ensinadas"]
