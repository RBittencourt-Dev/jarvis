"""Explorar vulnerabilidades dos apps DELE, de forma DEFENSIVA, com duas cabeças ao mesmo tempo: o Claude Code
(revisão de AppSec, lê e explica como corrigir) e o Strix (pentest com agentes de IA, acha e valida a falha com prova
de conceito). Pedido dele (24/10/2026): "se o Jarvis for explorar vulnerabilidade, põe pra ele usar o Claude e o Strix".

SEGURANÇA / LIMITES (duros, não dá pra driblar por voz):
  - SÓ DEFENSIVO e SÓ nos projetos DELE: o alvo é sempre a PASTA LOCAL do projeto (claude_ponte.PROJETOS), nunca uma
    URL, nunca o Supabase/produção. Nada de mirar sistema de terceiro.
  - O Claude roda em plan mode (só lê). O Strix roda no sandbox dele (Docker), na cópia local do código.
  - Strix é opcional: só dispara se estiver instalado (strix + Docker) e com chave de IA; senão o Jarvis avisa que falta
    instalar e segue só com o Claude.

Como o aviso de "terminou" chega: igual ao claude_ponte — o server lê novidades() em /api/novidades e fala. O Claude é
disparado pelo próprio claude_ponte (entra na fila de novidades dele); o Strix entra na fila daqui.
"""
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

import claude_ponte

DEMORA = True
RAIZ = Path(__file__).parent

PROJETOS = claude_ponte.PROJETOS  # mesma lista (porthon, painel, radar, site, planner, jarvis)

# "explora/acha/varre/escaneia as vulnerabilidades [no/do <projeto>]", "faz um pentest", "roda o strix"
GATILHO = re.compile(
    r"\b(?:explora\w*|acha\w*|encontra\w*|procura\w*|varre\w*|escane\w*|audita\w*|ca[çc]a\w*|testa\w*)\b.{0,45}?"
    r"\b(?:vulnerab\w*|falhas?\s+de\s+seguran\w*|brechas?|seguran[çc]a)\b"
    r"|\bfaz\w*\s+(?:um\s+)?pentest\b|\bpentest\w*\b|\broda\w*\s+o\s+strix\b|\busa\w*\s+o\s+strix\b", re.I)


def entender(texto):
    t = (texto or "").strip()
    if not GATILHO.search(t):
        return None
    chave = next((k for k in PROJETOS if re.search(rf"\b(?:n[oa]|d[oa]|pro|para o|o|a)\s+{k}\b", t, re.I)),
                 claude_ponte.ultimo_projeto["chave"])
    return {"projeto": chave, "pedido": t}


# ------------------------------------------------------------------ Strix
def _strix_disponivel():
    return bool(shutil.which("strix")) and bool(shutil.which("docker"))


def _ambiente_strix():
    """Monta STRIX_LLM + LLM_API_KEY a partir do que ele já tem no cérebro (ou de STRIX_LLM/LLM_API_KEY no ambiente).
    None se não há chave de IA pra dar ao Strix."""
    if os.environ.get("STRIX_LLM") and os.environ.get("LLM_API_KEY"):
        return dict(os.environ)
    try:
        import cerebro
    except Exception:
        return None
    env = dict(os.environ)
    # gemini é o preferido (litellm aceita "gemini/<modelo>"); senão groq; senão o FreeLLMAPI local (OpenAI-compatível)
    if cerebro.chave("gemini"):
        env.update(STRIX_LLM="gemini/gemini-3.5-flash", LLM_API_KEY=cerebro.chave("gemini"))
        return env
    if cerebro.chave("groq"):
        env.update(STRIX_LLM="groq/openai/gpt-oss-120b", LLM_API_KEY=cerebro.chave("groq"))
        return env
    if cerebro.chave("freellmapi"):
        env.update(STRIX_LLM="openai/auto", LLM_API_KEY=cerebro.chave("freellmapi"),
                   LLM_API_BASE=cerebro.PROVEDORES["freellmapi"]["url"])
        return env
    return None


_scans = {}  # tid -> {projeto, nome, estado, inicio, fim, avisado, resumo}


def _rodar_strix(tid, pasta, nome):
    s = _scans[tid]
    env = _ambiente_strix()
    if not env:
        s.update(estado="erro", resumo="Falta a chave de IA do Strix (STRIX_LLM/LLM_API_KEY).", fim=time.time())
        return
    instrucao = ("Teste de segurança DEFENSIVO, autorizado pelo dono, na cópia LOCAL deste app. Ache e valide "
                 "vulnerabilidades (autenticação, autorização/IDOR, injeção, exposição de dados, LGPD) e descreva a "
                 "correção. Não ataque sistemas de terceiros.")
    try:
        r = subprocess.run(
            ["strix", "-n", "--target", str(pasta), "--scan-mode", "quick", "--instruction", instrucao],
            cwd=str(pasta), capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30 * 60, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        # strix -n sai != 0 QUANDO ACHA vulnerabilidade — isso é sucesso, não erro.
        achou = r.returncode != 0
        saida = (r.stdout or r.stderr or "").strip()
        resumo = saida.splitlines()[-1] if saida else ("Encontrou achados." if achou else "Sem achados.")
        s.update(estado="pronto", achou=achou, resumo=resumo[:400], fim=time.time())
    except subprocess.TimeoutExpired:
        s.update(estado="erro", resumo="O Strix passou de 30 min e eu parei.", fim=time.time())
    except Exception as e:
        s.update(estado="erro", resumo=str(e)[:200], fim=time.time())


def executar(p):
    chave = p["projeto"]
    nome, pasta = PROJETOS[chave]
    claude_ponte.ultimo_projeto["chave"] = chave

    # 1) Claude Code em plan mode (só lê), cabeça de AppSec defensiva — entra na fila de novidades do claude_ponte.
    pedido_claude = ("Atue como especialista em segurança de aplicações (AppSec), DEFENSIVO. Faça uma varredura de "
                     "segurança DESTE projeto: ache vulnerabilidades (autenticação, autorização/IDOR, injeção, "
                     "exposição de dados, segredo no código, LGPD) e explique, em passos, como corrigir cada uma. "
                     "NÃO oriente atacar nem mexa em nada; só leia e relate.")
    claude_ok = False
    try:
        if shutil.which("claude") and pasta.exists():
            claude_ponte.executar({"modo": "perguntar", "projeto": chave, "nome": nome, "pedido": pedido_claude})
            claude_ok = True
    except Exception:
        claude_ok = False

    # 2) Strix (opcional): pentest com agentes, na pasta local. Só se instalado + chave.
    strix_msg = ""
    if not pasta.exists():
        strix_msg = ""
    elif not _strix_disponivel():
        strix_msg = (" O Strix ainda não está instalado neste PC (precisa do Strix e do Docker) — quando instalar, eu "
                     "disparo ele junto.")
    elif not _ambiente_strix():
        strix_msg = " O Strix está instalado, mas falta a chave de IA dele (STRIX_LLM/LLM_API_KEY)."
    else:
        tid = uuid.uuid4().hex[:8]
        _scans[tid] = {"projeto": chave, "nome": nome, "estado": "trabalhando", "inicio": time.time(), "avisado": False}
        threading.Thread(target=_rodar_strix, args=(tid, pasta, nome), daemon=True).start()
        strix_msg = " E soltei o Strix pra varrer de verdade (prova de conceito) — te aviso quando ele terminar."

    if not claude_ok and not strix_msg.strip():
        return (f"Pra explorar vulnerabilidade eu preciso do projeto {nome} aqui no PC, chefe, e dele pelo menos o "
                "Claude ou o Strix — nenhum tá disponível agora.", [])
    parte_claude = (f"Pus o Claude pra revisar a segurança do {nome} (só lendo, modo defensivo)."
                    if claude_ok else f"Não consegui acionar o Claude no {nome} agora.")
    fala = f"Deixa comigo, chefe. {parte_claude}{strix_msg} Te conto o que cada um achar."
    cartao = {"titulo": f"Segurança · {nome}", "destaque": "Explorando vulnerabilidades (defensivo)",
              "linhas": ["Claude Code: revisão de AppSec (plan mode, só lê)" if claude_ok else "Claude: indisponível",
                         "Strix: pentest com agentes" + ("" if _scans else " — " + strix_msg.strip()),
                         "Só nos seus apps, na cópia local. Nunca em produção nem em terceiros."]}
    return fala, [cartao]


def novidades():
    """Scans do Strix que terminaram e ainda não foram falados (o server junta com os do Claude em /api/novidades)."""
    prontas = []
    for s in _scans.values():
        if s["estado"] == "trabalhando" or s["avisado"]:
            continue
        s["avisado"] = True
        ok = s["estado"] == "pronto"
        achou = s.get("achou")
        titulo_estado = ("achou vulnerabilidades" if achou else "não achou vulnerabilidades") if ok else "teve um problema"
        prontas.append({
            "fala": f"Chefe, o Strix terminou de varrer o {s['nome']} e {titulo_estado}. {s.get('resumo','')}",
            "cartao": {"titulo": f"Strix · {s['nome']}",
                       "destaque": ("Achados" if achou else "Limpo") if ok else "Problema",
                       "linhas": [s.get("resumo", ""), "Resultado completo em strix_runs (rode: strix view)."]},
        })
    return prontas
