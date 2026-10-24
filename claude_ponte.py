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


def _ambiente_gratis():
    """Claude Code apontado pro FreeLLMAPI (as IAs grátis: Gemini, Groq…), igual ao `freellmapi launch`.
    None se o FreeLLMAPI não está instalado/ligado neste PC."""
    import os
    import cerebro
    chave = cerebro.chave("freellmapi")
    if not chave:
        return None
    cerebro.ligar_freellmapi()
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    env.update(ANTHROPIC_BASE_URL=cerebro.PROVEDORES["freellmapi"]["url"].removesuffix("/v1"), ANTHROPIC_AUTH_TOKEN=chave,
               ANTHROPIC_MODEL="auto", ANTHROPIC_DEFAULT_OPUS_MODEL="auto", ANTHROPIC_DEFAULT_SONNET_MODEL="auto",
               ANTHROPIC_DEFAULT_HAIKU_MODEL="auto", CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY="1")
    return env


def _rodar_claude(t, env=None):
    r = subprocess.run(["claude", "-p", t["pedido"], "--output-format", "json", "--permission-mode", "plan",
                        "--append-system-prompt", AVISO],
                       cwd=PROJETOS[t["projeto"]][1], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=15 * 60, creationflags=subprocess.CREATE_NO_WINDOW, env=env)
    dados = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    ok = bool(dados.get("result")) and not dados.get("is_error") and not r.returncode
    return ok, (dados.get("result") or r.stderr or "O Claude não devolveu resposta.").strip()


def _perguntar(tid):
    """Linha de frente: o Claude pago (assinatura dele). Se ele falhar (cota acabou, sem login, fora do ar), o
    Claude Code grátis assume o mesmo pedido pelo FreeLLMAPI (pedido dele de 24/10, pra segurança e programação)."""
    t = tarefas[tid]
    try:
        ok, resposta = _rodar_claude(t)
        if not ok and (env := _ambiente_gratis()):
            ok2, resposta2 = _rodar_claude(t, env)
            if ok2:
                ok, resposta = True, resposta2
                t["gratis"] = True
        t.update(estado="pronto" if ok else "erro", resposta=resposta)
    except Exception as e:
        t.update(estado="erro", resposta=str(e))
    t["fim"] = time.time()


def iniciar_pergunta(pedido, dono=None):
    """Como executar() em modo perguntar, mas DEVOLVE o tid e marca o 'dono' do resultado.
    Quando 'dono' está setado (ex.: "seguranca"), novidades() daqui NÃO conta esse resultado —
    quem lê tarefas[tid] e avisa é o módulo dono (o seguranca junta com o Strix e oferece a correção)."""
    ultimo_projeto["chave"] = pedido["projeto"]
    tid = str(uuid.uuid4())[:8]
    tarefas[tid] = {**pedido, "modo": "perguntar", "estado": "trabalhando",
                    "inicio": time.time(), "avisado": False, "dono": dono}
    threading.Thread(target=_perguntar, args=(tid,), daemon=True).start()
    return tid


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
        if t["estado"] == "trabalhando" or t["avisado"] or t.get("dono"):
            continue  # com 'dono' é o módulo dono (ex.: seguranca) que conta e oferece a correção
        t["avisado"] = True
        ok = t["estado"] == "pronto"
        prontas.append({
            "fala": f"Chefe, o Claude{' grátis' if t.get('gratis') else ''} {'respondeu' if ok else 'teve um problema'} "
                    f"sobre o {t['nome']}. {resumo_falado(t['resposta'])}",
            "cartao": {"titulo": f"Claude{' grátis' if t.get('gratis') else ''} · {t['nome']}",
                       "destaque": "Resposta" if ok else "Problema",
                       "linhas": [f"Pergunta: {t['pedido']}", *[l for l in t["resposta"].splitlines() if l.strip()][:6]]},
        })
    return prontas
