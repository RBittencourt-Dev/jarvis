"""Modo "falar direto com o Claude": o Jarvis passa o microfone pro Claude Code.

Pedido do Rafael (24/10/2026): "quando o Claude estiver sendo executado, ele assume as respostas — quem me responde é
o Claude, não o Jarvis". Aqui quem fala com ele passa a ser o PRÓPRIO Claude (a resposta real dele, não um resumo do
Jarvis), com MEMÓRIA da conversa (mesma sessão do `claude`, via --session-id/--resume).

Segurança (o jeito que ele escolheu — "os dois, com um comando pra alternar"):
  - COMEÇA só LENDO (plan mode): o Claude lê o projeto e conversa, mas NÃO altera nada.
  - "pode editar" libera o Claude a mexer no código (acceptEdits: ele aplica as edições e cada resposta mostra o que
    mudou); "só conversa" trava de novo.
  - "volta pro Jarvis" / "tchau Claude" sai do modo.
  - SEMPRE na pasta LOCAL do projeto (claude_ponte.PROJETOS), nunca uma URL, nunca o Supabase/produção.
"""
import json
import re
import subprocess
import uuid

import claude_ponte

PROJETOS = claude_ponte.PROJETOS
AVISO = claude_ponte.AVISO  # mesmo aviso de voz (transcrição pode ter erro; resuma em 2 frases sem markdown)

# "fala/conversa com o Claude", "entra no modo Claude", "me passa pro Claude", "modo Claude"
ENTRAR = re.compile(
    r"\b(?:(?:quero\s+)?(?:fala\w*|conversa\w*|bate\w*\s+(?:um\s+)?papo)\s+(?:direto\s+)?com\s+o\s+claude"
    r"|entra\w*\s+(?:no\s+)?modo\s+claude|me\s+(?:passa\w*|liga\w*|conecta\w*|p[oõ]e)\s+(?:com\s+|no\s+|pro\s+)?o?\s*claude\b"
    r"|modo\s+claude)\b", re.I)
SAIR = re.compile(
    r"\b(?:volta\w*\s+(?:pro|para o)\s+jarvis|sai\w*\s+do\s+claude|tchau,?\s+claude|obrigad[oa],?\s+claude"
    r"|encerra\w*\s+(?:o\s+)?claude|fecha\w*\s+o\s+claude|chega,?\s+claude)\b", re.I)
LIBERAR = re.compile(
    r"\b(?:pode\s+(?:editar|mexer|alterar|corrigir|fazer|p[oõ]r\s+a\s+m[aã]o)|libera\w*\s+(?:a\s+)?edi\w*"
    r"|autoriz\w*\s+(?:a\s+)?edi\w*)\b", re.I)
TRAVAR = re.compile(
    r"\b(?:s[oó]\s+(?:conversa\w*|l[eê]\w*|leitura)|para\s+de\s+editar|n[aã]o\s+edita\w*|trava\w*\s+(?:a\s+)?edi\w*"
    r"|volta\w*\s+a\s+s[oó]\s+l[eê])\b", re.I)

_sessoes = {}  # sid do Jarvis -> {projeto, nome, claude_sid, modo ("lendo"/"editando"), primeira}


def entrar_pedido(texto):
    """Devolve a chave do projeto se for um pedido pra entrar no modo Claude; senão None."""
    t = (texto or "").strip()
    if not ENTRAR.search(t):
        return None
    return next((k for k in PROJETOS if re.search(rf"\b(?:n[oa]|d[oa]|pro|para o|o|a)\s+{k}\b", t, re.I)),
                claude_ponte.ultimo_projeto["chave"])


def ativo(sid):
    return sid in _sessoes


def entrar(sid, chave):
    """Abre a sessão do Claude pra esse projeto (começa só lendo) e devolve o nome falado."""
    nome, _pasta = PROJETOS[chave]
    claude_ponte.ultimo_projeto["chave"] = chave
    _sessoes[sid] = {"projeto": chave, "nome": nome, "claude_sid": str(uuid.uuid4()),
                     "modo": "lendo", "primeira": True}
    return nome


def sair(sid):
    _sessoes.pop(sid, None)


def _voz(resposta):
    """A resposta REAL do Claude, pronta pra falar: tira o markdown e fica no primeiro parágrafo (o resto vai no cartão)."""
    primeiro = re.split(r"\n\s*\n", resposta.strip())[0]
    txt = re.sub(r"[*#`_>]+", "", primeiro).strip()
    return (txt[:500].rstrip() + "… o resto tá na tela, chefe.") if len(txt) > 520 else txt


def _rodar(info, fala):
    pasta = PROJETOS[info["projeto"]][1]
    perm = "plan" if info["modo"] == "lendo" else "acceptEdits"
    args = ["claude", "-p", fala, "--output-format", "json", "--permission-mode", perm,
            "--append-system-prompt", AVISO]
    args += ["--session-id", info["claude_sid"]] if info["primeira"] else ["--resume", info["claude_sid"]]
    try:
        r = subprocess.run(args, cwd=pasta, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=10 * 60, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return False, "O Claude demorou demais e eu parei essa, chefe. Tenta de novo mais curto."
    info["primeira"] = False
    dados = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    ok = bool(dados.get("result")) and not dados.get("is_error")
    return ok, (dados.get("result") or r.stderr or "O Claude não me devolveu resposta.").strip()


def falar(sid, texto):
    """Processa uma fala DENTRO do modo. Devolve (fala, cartao|None, continua_no_modo)."""
    info = _sessoes.get(sid)
    if not info:
        return "Não estou no modo Claude agora, chefe.", None, False
    t = (texto or "").strip()
    if SAIR.search(t):
        sair(sid)
        return "Voltei, chefe. Agora é comigo de novo.", None, False
    if LIBERAR.search(t):
        info["modo"] = "editando"
        return ("Liberado, chefe. Agora o Claude pode editar o código — ele aplica e eu te mostro o que mudou. "
                "Pode mandar o que quer que ele faça."), None, True
    if TRAVAR.search(t):
        info["modo"] = "lendo"
        return "Travei a edição, chefe. O Claude volta a só ler e conversar.", None, True
    ok, resposta = _rodar(info, t)
    selo = "editando o código" if info["modo"] == "editando" else "só lendo"
    cartao = {"titulo": f"Claude · {info['nome']}", "destaque": selo,
              "linhas": [l for l in resposta.splitlines() if l.strip()][:8] or [resposta[:200]]}
    return (_voz(resposta) if ok else f"O Claude tropeçou, chefe: {resposta[:200]}"), cartao, True
