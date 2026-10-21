"""Ponte Jarvis → Claude Code. Todo pedido passa pela confirmação falada do Rafael antes de sair.

- "pergunta pro Claude …": roda `claude -p` em modo plan (só lê e explica, não muda nada)
  em segundo plano e devolve a resposta falada.
- "pede pro Claude …" (fazer, mudar, criar…): abre o Claude Code numa janela de terminal,
  no projeto certo, com o pedido já digitado. Quem aprova cada passo é o Rafael, na janela.
"""
import json
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

RAIZ = Path(__file__).parent
DESKTOP = Path.home() / "Desktop"

PROJETOS = {  # palavra dita → (nome falado, pasta)
    "porthon": ("Porthon", DESKTOP / "Porthon-System"),
    "painel": ("Painel 7SevenCode", DESKTOP / "7 SevenCode" / "painel-7sevencode"),
    "radar": ("Radar de Leads", DESKTOP / "7code-radar-leads"),
    "site": ("site da 7SevenCode", DESKTOP / "7 SevenCode" / "7 SevenCode - Site"),
    "planner": ("7 Planner", DESKTOP / "7planner-system"),
    "jarvis": ("Jarvis", RAIZ),
}

PEDIDO = re.compile(
    r"^(?:jarvis[ ,]*)?(pergunta|pe[cç]a|pede|manda|fala|diz|avisa)\s+(?:pro|para o|pra o|ao|o)\s+claude[ ,:]+(.+)$", re.I)

AVISO = ("Esta pergunta chegou por VOZ, pelo assistente Jarvis do Rafael; a transcrição pode ter erros. "
         "Responda em português, começando por um resumo de no máximo 2 frases sem markdown: ele será falado em voz alta.")

tarefas = {}
ultimo_projeto = {"chave": "porthon"}


def entender(texto):
    """Devolve {modo, projeto, nome, pedido} se for um pedido para o Claude; senão None."""
    m = PEDIDO.match(texto.strip())
    if not m:
        return None
    verbo, pedido = m.group(1).lower(), m.group(2).strip()
    chave = next((k for k in PROJETOS if re.search(rf"\b(n[oa]|do|da|pro|para o)\s+{k}", pedido, re.I)),
                 ultimo_projeto["chave"])
    return {"modo": "perguntar" if verbo == "pergunta" else "fazer", "projeto": chave,
            "nome": PROJETOS[chave][0], "pedido": pedido}


def _perguntar(tid):
    t = tarefas[tid]
    try:
        r = subprocess.run(["claude", "-p", t["pedido"], "--output-format", "json", "--permission-mode", "plan",
                            "--append-system-prompt", AVISO],
                           cwd=PROJETOS[t["projeto"]][1], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=15 * 60, creationflags=subprocess.CREATE_NO_WINDOW)
        dados = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
        t.update(estado="erro" if dados.get("is_error") or r.returncode else "pronto",
                 resposta=(dados.get("result") or r.stderr or "O Claude não devolveu resposta.").strip())
    except Exception as e:
        t.update(estado="erro", resposta=str(e))
    t["fim"] = time.time()


def executar(pedido):
    """Chamado depois do "sim" do Rafael."""
    ultimo_projeto["chave"] = pedido["projeto"]
    pasta = PROJETOS[pedido["projeto"]][1]
    if pedido["modo"] == "fazer":
        # janela interativa: o Rafael acompanha e aprova cada passo
        subprocess.Popen(["cmd", "/c", "start", "Claude Code - " + pedido["nome"], "/d", str(pasta),
                          "claude", pedido["pedido"]])
        return f"Abri o Claude Code no {pedido['nome']} com o seu pedido. Acompanhe e aprove por lá, chefe."
    tid = str(uuid.uuid4())[:8]
    tarefas[tid] = {**pedido, "estado": "trabalhando", "inicio": time.time(), "avisado": False}
    threading.Thread(target=_perguntar, args=(tid,), daemon=True).start()
    return f"Perguntei ao Claude, no {pedido['nome']}. Te conto quando ele responder."


def resumo_falado(resposta):
    primeiro = re.split(r"\n\s*\n", resposta.strip())[0]
    frases = re.split(r"(?<=[.!?])\s+", re.sub(r"[*#`_>]", "", primeiro))
    return " ".join(frases[:2])[:400]


def novidades():
    """Respostas que chegaram e ainda não foram contadas (cada uma é contada uma vez)."""
    prontas = []
    for t in tarefas.values():
        if t["estado"] == "trabalhando" or t["avisado"]:
            continue
        t["avisado"] = True
        ok = t["estado"] == "pronto"
        prontas.append({
            "fala": f"Chefe, o Claude {'respondeu' if ok else 'teve um problema'} sobre o {t['nome']}. {resumo_falado(t['resposta'])}",
            "cartao": {"titulo": f"Claude · {t['nome']}", "destaque": "Resposta" if ok else "Problema",
                       "linhas": [f"Pergunta: {t['pedido']}", *[l for l in t["resposta"].splitlines() if l.strip()][:6]]},
        })
    return prontas
