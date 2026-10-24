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
import datetime
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
ACHADOS = RAIZ / "achados_seguranca"  # tudo que as varreduras acharem, guardado aqui pra ver/corrigir depois


def _salvar_achado(nome, chave, fonte, texto, achou=None):
    """Grava o resultado de uma varredura num .md por projeto/dia, pra não se perder (pedido do Rafael 24/10)."""
    try:
        ACHADOS.mkdir(exist_ok=True)
        arq = ACHADOS / f"{chave}_{datetime.date.today().isoformat()}.md"
        cabecalho = "" if arq.exists() else f"# Achados de segurança — {nome}\n\n(só defensivo, cópia local)\n\n"
        marca = {True: " · ACHOU falhas", False: " · limpo"}.get(achou, "")
        ts = datetime.datetime.now().strftime("%d/%m %H:%M")
        with open(arq, "a", encoding="utf-8") as f:
            f.write(f"{cabecalho}## {fonte} — {ts}{marca}\n\n{(texto or '').strip() or '(sem saída)'}\n\n---\n\n")
        return arq
    except Exception:
        return None

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
def _strix_bin():
    """Caminho do strix.exe — pelo PATH ou direto no diretório do pipx (o Jarvis em execução não vê PATH novo)."""
    achado = shutil.which("strix")
    if achado:
        return achado
    base = Path(os.path.expanduser("~")) / ".local" / "bin"
    for nome in ("strix.exe", "strix"):
        if (base / nome).exists():
            return str(base / nome)
    return None


def _docker_rodando():
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=12,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
    except Exception:
        return False


def _strix_disponivel():
    return bool(_strix_bin()) and _docker_rodando()


def _guardar_revisao(tid, nome, chave):
    """Espera a revisão de AppSec do Claude terminar e guarda em arquivo (não some se o HUD não for consultado)."""
    for _ in range(360):  # até ~30 min (o claude_ponte tem timeout de 15 min)
        t = claude_ponte.tarefas.get(tid)
        if not t:
            return
        if t.get("estado") and t["estado"] != "trabalhando":
            if t["estado"] == "pronto":
                _salvar_achado(nome, chave, "Claude (revisão AppSec)", t.get("resposta", ""),
                               _achou_vuln(t.get("resposta", "")))
            return
        time.sleep(5)


def _ambientes_strix():
    """Lista de (provedor, env) pro Strix, em ordem de preferência. Ele tenta um; se der cota/erro de conexão,
    cai pro próximo (descoberto 24/10: a cota grátis do Gemini estoura em 20 req/dia). Groq primeiro porque é o
    modelo que o cérebro usa por padrão e aguenta mais; Gemini e o FreeLLMAPI local como reserva."""
    if os.environ.get("STRIX_LLM") and os.environ.get("LLM_API_KEY"):
        return [("ambiente", dict(os.environ))]
    try:
        import cerebro
    except Exception:
        return []
    envs = []
    if cerebro.chave("groq"):
        e = dict(os.environ); e.update(STRIX_LLM="groq/openai/gpt-oss-120b", LLM_API_KEY=cerebro.chave("groq"))
        envs.append(("groq", e))
    if cerebro.chave("gemini"):
        e = dict(os.environ); e.update(STRIX_LLM="gemini/gemini-3.5-flash", LLM_API_KEY=cerebro.chave("gemini"))
        envs.append(("gemini", e))
    if cerebro.chave("freellmapi"):
        e = dict(os.environ); e.update(STRIX_LLM="openai/auto", LLM_API_KEY=cerebro.chave("freellmapi"),
                                       LLM_API_BASE=cerebro.PROVEDORES["freellmapi"]["url"])
        envs.append(("freellmapi", e))
    return envs


def _ambiente_strix():
    """Compat: só diz se HÁ alguma chave de IA pro Strix (usado na mensagem do executar)."""
    envs = _ambientes_strix()
    return envs[0][1] if envs else None


# Sinais FORTES de que o Strix FALHOU por IA (cota/conexão/credencial), não que achou vulnerabilidade.
# (sinais específicos do banner de erro do Strix/litellm — evita confundir com um achado que cite "429/quota")
_FALHA_LLM = re.compile(
    r"LLM CONNECTION FAILED|Could not establish connection to the language model|RateLimitError|"
    r"RESOURCE_EXHAUSTED|AuthenticationError|invalid api key|exceeded your current quota|"
    r"BadRequestError|invalid_request_error|invalid JSON schema|Error during penetration test", re.I)


_scans = {}      # tid -> {projeto, nome, estado, inicio, fim, avisado, resumo}  (corridas do Strix)
_revisoes = {}   # tid (do claude_ponte) -> {projeto, nome, avisado}  (revisões de AppSec do Claude)

# Palavras que indicam que a varredura REALMENTE achou algo que vale corrigir (pra só então oferecer o conserto).
_ACHOU = re.compile(
    r"\b(?:vulnerab\w*|idor|xss|csrf|sql\s*injection|inje[cç]\w*|exposi[cç]\w*|expost[oa]s?|"
    r"cr[ií]tic[oa]s?|grav[ei]\w*|alto\s+risco|risco\s+alto|segredo\w*\s+(?:no|em)\s+c[oó]digo|"
    r"chave\w*\s+expost\w*|senha\w*\s+expost\w*|falha\w*\s+de\s+seguran\w*)\b", re.I)
_NADA = re.compile(r"\b(?:nenhuma?\s+vulnerab\w*|sem\s+(?:vulnerab\w*|achados?|falhas?)|"
                   r"n[aã]o\s+(?:encontre\w*|achei|h[aá]|identifiquei)\s+\w*\s*(?:vulnerab\w*|falhas?|problemas?))\b", re.I)


def _achou_vuln(texto):
    t = texto or ""
    return bool(_ACHOU.search(t)) and not _NADA.search(t)


def _oferta_de_correcao(chave, nome):
    """Monta o 'pendente' do tipo claude em modo FAZER: no "sim" do Rafael, o server roda claude_ponte.executar
    e abre o Claude Code pra corrigir, aprovando cada passo. SÓ a pasta local, nunca produção."""
    pedido = (f"Atue como especialista em segurança de aplicações (AppSec), DEFENSIVO. No projeto {nome}, CORRIJA as "
              "vulnerabilidades apontadas na revisão de segurança (autenticação, autorização/IDOR, injeção, exposição "
              "de dados, segredo no código, LGPD). Mostre cada alteração e PEÇA minha aprovação antes de aplicar. "
              "Não toque em produção nem no Supabase.")
    return {
        "claude": {"modo": "fazer", "projeto": chave, "nome": nome, "pedido": pedido},
        "nome": f"pedir ao Claude pra corrigir o {nome}",
        "args": {"pedido": pedido},
        "fala": f"Quer que eu peça pro Claude corrigir essas falhas no {nome}, chefe? Diz sim que eu mando ele consertar.",
    }


def _rodar_strix(tid, pasta, nome):
    s = _scans[tid]
    envs = _ambientes_strix()
    if not envs:
        s.update(estado="erro", resumo="Falta a chave de IA do Strix (STRIX_LLM/LLM_API_KEY).", fim=time.time())
        return
    instrucao = ("Teste de segurança DEFENSIVO, autorizado pelo dono, na cópia LOCAL deste app. Ache e valide "
                 "vulnerabilidades (autenticação, autorização/IDOR, injeção, exposição de dados, LGPD) e descreva a "
                 "correção. Não ataque sistemas de terceiros.")
    ultimo_erro = ""
    for provedor, env in envs:   # tenta cada IA; se uma recusar por cota/conexão, cai pra próxima
        try:
            r = subprocess.run(
                [_strix_bin(), "-n", "--target", str(pasta), "--scan-mode", "quick", "--instruction", instrucao],
                cwd=str(pasta), capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30 * 60, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            s.update(estado="erro", resumo="O Strix passou de 30 min e eu parei.", fim=time.time())
            return
        except Exception as e:
            ultimo_erro = f"{provedor}: {str(e)[:150]}"
            continue
        saida = (r.stdout or r.stderr or "").strip()
        if _FALHA_LLM.search(saida):   # não achou nada: a IA recusou (ex.: cota do Gemini). Tenta a próxima.
            linha = next((l.strip() for l in saida.splitlines() if _FALHA_LLM.search(l)), "falha de IA")
            ultimo_erro = f"{provedor}: {linha[:150]}"
            continue
        # sucesso de verdade: o strix -n sai != 0 QUANDO ACHA vulnerabilidade.
        achou = r.returncode != 0
        resumo = saida.splitlines()[-1] if saida else ("Encontrou achados." if achou else "Sem achados.")
        _salvar_achado(nome, s["projeto"], f"Strix (pentest · {provedor})", saida or resumo, achou)
        s.update(estado="pronto", achou=achou, resumo=resumo[:400], provedor=provedor, fim=time.time())
        return
    # todas as IAs recusaram
    _salvar_achado(nome, s["projeto"], "Strix (pentest · não rodou)", ultimo_erro or "Nenhuma IA respondeu.", None)
    s.update(estado="erro", resumo=f"O Strix não conseguiu rodar: a IA recusou em todos os provedores. {ultimo_erro}",
             fim=time.time())


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
            tid = claude_ponte.iniciar_pergunta(
                {"projeto": chave, "nome": nome, "pedido": pedido_claude}, dono="seguranca")
            _revisoes[tid] = {"projeto": chave, "nome": nome, "avisado": False}
            threading.Thread(target=_guardar_revisao, args=(tid, nome, chave), daemon=True).start()
            claude_ok = True
    except Exception:
        claude_ok = False

    # 2) Strix (opcional): pentest com agentes, na pasta local. Só se instalado + chave.
    strix_msg = ""
    if not pasta.exists():
        strix_msg = ""
    elif not _strix_bin():
        strix_msg = " O Strix ainda não está instalado neste PC — quando instalar, eu disparo ele junto."
    elif not _docker_rodando():
        strix_msg = (" O Strix já está instalado, mas o Docker não está rodando — ele precisa do Docker pra varrer. "
                     "Abre o Docker Desktop que na próxima eu disparo junto.")
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
    """Varreduras que terminaram e ainda não foram faladas — do Claude (revisão de AppSec) e do Strix (pentest).
    Quando ACHOU vulnerabilidade, o bloco lista as falhas e carrega uma 'oferta': o server arma o pendente e o HUD
    pergunta se pode acionar o Claude em modo FAZER pra corrigir. O server lê 'oferta' e não a repassa ao HUD."""
    prontas = []
    ja_ofereci = False  # só um pendente por rodada (um pedido de "sim" de cada vez)

    # 1) Revisões de AppSec do Claude (plan mode, só leu). Leem o resultado direto da tarefa do claude_ponte.
    for tid, r in _revisoes.items():
        if r["avisado"]:
            continue
        t = claude_ponte.tarefas.get(tid)
        if not t or t.get("estado") == "trabalhando":
            continue
        r["avisado"] = True
        ok = t.get("estado") == "pronto"
        resposta = (t.get("resposta") or "").strip()
        achou = ok and _achou_vuln(resposta)
        linhas = [l for l in resposta.splitlines() if l.strip()][:8]
        if ok:
            estado = "Achei falhas pra corrigir" if achou else "Sem falhas aparentes"
            fala = (f"Chefe, terminei a revisão de segurança do {r['nome']}. "
                    + (claude_ponte.resumo_falado(resposta) if achou else "Não vi nada grave por ali."))
        else:
            estado, fala = "Problema", f"Chefe, a revisão de segurança do {r['nome']} teve um problema. {resposta[:200]}"
        bloco = {"fala": fala, "cartao": {"titulo": f"Segurança · {r['nome']}", "destaque": estado,
                                          "linhas": linhas or [resposta[:200] or "Sem resposta."]}}
        if achou and not ja_ofereci:
            bloco["oferta"] = _oferta_de_correcao(r["projeto"], r["nome"])
            ja_ofereci = True
        prontas.append(bloco)

    # 2) Corridas do Strix (pentest com agentes, validou com prova de conceito).
    for s in _scans.values():
        if s["estado"] == "trabalhando" or s["avisado"]:
            continue
        s["avisado"] = True
        ok = s["estado"] == "pronto"
        achou = bool(s.get("achou"))
        titulo_estado = ("achou vulnerabilidades" if achou else "não achou vulnerabilidades") if ok else "teve um problema"
        bloco = {
            "fala": f"Chefe, o Strix terminou de varrer o {s['nome']} e {titulo_estado}. {s.get('resumo','')}",
            "cartao": {"titulo": f"Strix · {s['nome']}",
                       "destaque": ("Achados" if achou else "Limpo") if ok else "Problema",
                       "linhas": [s.get("resumo", ""), "Resultado completo em strix_runs (rode: strix view)."]},
        }
        if ok and achou and not ja_ofereci:
            bloco["oferta"] = _oferta_de_correcao(s["projeto"], s["nome"])
            ja_ofereci = True
        prontas.append(bloco)
    return prontas
