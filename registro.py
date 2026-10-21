"""Diário de tudo que o Jarvis fez: cada pedido, o que ele respondeu e as ferramentas que usou.

Serve pra três coisas:
  - "faz aquilo de ontem" / "repete o que você fez de manhã": o cérebro lê o diário (ferramenta ver_registro);
  - o painel de Configurações mostra o log completo (Privacidade → O que eu fiz);
  - desfazer: ações que dá pra voltar (arquivo criado, movido, renomeado) guardam como desfazer.
Fica em dados/registro.jsonl (uma linha por ação, só neste PC, fora do git).
"""
import json
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).parent
PASTA = RAIZ / "dados"
ARQUIVO = PASTA / "registro.jsonl"
_trava = threading.Lock()


def anotar(pedido, resposta="", ferramentas=(), desfazer=None, tipo="pedido"):
    """Grava uma linha. desfazer = {"tipo": "mover", "de": ..., "para": ...} | {"tipo": "apagar", "caminho": ...}."""
    PASTA.mkdir(exist_ok=True)
    linha = {"id": uuid.uuid4().hex[:10], "quando": time.time(), "tipo": tipo, "pedido": (pedido or "")[:400],
             "resposta": (resposta or "")[:400], "ferramentas": list(ferramentas)[:12]}
    if desfazer:
        linha["desfazer"] = desfazer
    with _trava, ARQUIVO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha["id"]


def todas():
    if not ARQUIVO.exists():
        return []
    saida = []
    for linha in ARQUIVO.read_text(encoding="utf-8").splitlines():
        try:
            saida.append(json.loads(linha))
        except ValueError:
            pass
    return saida


def ultimas(n=50):
    return todas()[-n:][::-1]


def _dia(texto):
    """'hoje', 'ontem', 'anteontem', 'segunda'… ou '21/10' → date."""
    t = (texto or "hoje").strip().lower()
    hoje = datetime.now().date()
    if t in ("", "hoje"):
        return hoje
    if t == "ontem":
        return hoje - timedelta(days=1)
    if t == "anteontem":
        return hoje - timedelta(days=2)
    dias = ["segunda", "terça", "terca", "quarta", "quinta", "sexta", "sábado", "sabado", "domingo"]
    indice = {"segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sábado": 5, "sabado": 5, "domingo": 6}
    for d in dias:
        if t.startswith(d):
            atras = (hoje.weekday() - indice[d]) % 7 or 7
            return hoje - timedelta(days=atras)
    for formato in ("%d/%m/%Y", "%d/%m", "%Y-%m-%d"):
        try:
            data = datetime.strptime(t, formato).date()
            return data.replace(year=hoje.year) if formato == "%d/%m" else data
        except ValueError:
            pass
    return hoje


def ver_registro(dia: str = "hoje", busca: str = ""):
    """Ferramenta do cérebro: o que foi pedido e feito num dia (e, se quiser, só o que contém uma palavra)."""
    alvo = _dia(dia)
    busca = (busca or "").lower()
    linhas = []
    for r in todas():
        quando = datetime.fromtimestamp(r["quando"])
        if quando.date() != alvo or r.get("tipo") == "aviso":
            continue
        if busca and busca not in (r["pedido"] + " " + r["resposta"]).lower():
            continue
        extra = f" [ferramentas: {', '.join(r['ferramentas'])}]" if r.get("ferramentas") else ""
        linhas.append(f"{quando:%H:%M} pediu: {r['pedido']} → {r['resposta'][:160]}{extra}")
    if not linhas:
        return f"Nada registrado em {alvo:%d/%m}."
    return f"Registro de {alvo:%d/%m} ({len(linhas)} itens):\n" + "\n".join(linhas[-40:])


def desfazer_ultimo():
    """Volta a última ação que dá pra voltar. Devolve a frase pra falar."""
    for r in reversed(todas()):
        d = r.get("desfazer")
        if not d or r.get("desfeito"):
            continue
        try:
            if d["tipo"] == "mover":  # moveu/renomeou: volta pro lugar
                shutil.move(d["para"], d["de"])
                fala = f"Desfeito: voltei {Path(d['de']).name} pro lugar."
            elif d["tipo"] == "apagar":  # criou arquivo: manda pra lixeira
                import controle_pc
                controle_pc.para_lixeira(d["caminho"])
                fala = f"Desfeito: mandei {Path(d['caminho']).name} pra lixeira."
            else:
                continue
        except Exception as e:
            return f"Não consegui desfazer: {e}"
        _marcar_desfeito(r["id"])
        anotar("desfazer", fala, tipo="desfazer")
        return fala
    return "Não tenho nada recente que dê pra desfazer, chefe."


def _marcar_desfeito(id_):
    with _trava:
        linhas = []
        for r in todas():
            if r["id"] == id_:
                r["desfeito"] = True
            linhas.append(json.dumps(r, ensure_ascii=False))
        ARQUIVO.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def limpar():
    if ARQUIVO.exists():
        ARQUIVO.unlink()
