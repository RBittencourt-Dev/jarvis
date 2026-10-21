"""Conectores: apps de fora que o Jarvis usa como ferramentas (MCP e plugins pela API oficial de cada app).

Dois tipos:
  - MCP (Model Context Protocol): o Jarvis é CLIENTE de qualquer servidor MCP que ele adicionar nas Configurações:
      · "stdio": um programa local (ex.: npx -y @modelcontextprotocol/server-filesystem C:\\pasta);
      · "http": um servidor remoto, com chave (Authorization: Bearer) ou com login OAuth no navegador (Notion, Canva).
  - Plugins nativos (API oficial, sem MCP): GitHub (token), Google Agenda/Gmail/Drive (OAuth com o app Google dele),
    Telegram (bot). Spotify e WhatsApp já são habilidades do Jarvis e só aparecem na lista.

Regras:
  - chaves e tokens SÓ no cofre (cofre.py, criptografado pelo Windows). Nunca senha de login.
  - permissão por conector: "leitura" (só ferramentas que leem) ou "escrita".
  - o que envia, publica, apaga, cria ou gasta pede o "sim" dele SEMPRE (precisa_autorizar).
  - modelo pequeno: as ferramentas de um conector só entram no contexto quando o cérebro carrega aquele conector
    (carregar_ferramentas com o nome dele) ou quando a frase cita o app.
Config em dados/conectores.json (sem segredos); lista de ferramentas de cada MCP em dados/conectores-cache.json.
"""
import asyncio
import json
import re
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

import cofre

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "dados" / "conectores.json"
CACHE = RAIZ / "dados" / "conectores-cache.json"
PORTA = json.loads((RAIZ / "config.json").read_text(encoding="utf-8")).get("porta", 8765)
RETORNO_OAUTH = f"http://127.0.0.1:{PORTA}/conectores/oauth/retorno"
RETORNO_GOOGLE = f"http://127.0.0.1:{PORTA}/conectores/google/retorno"

# o que existe e quanto custa (conferido em 21/10/2026; preço muda, confira na página de cada um)
CATALOGO = {
    # mcp.canva.com aceita cadastro automático do app (testado 21/10): é só Conectar e autorizar, igual no Claude
    "canva": {"titulo": "Canva", "tipo": "http", "url": "https://mcp.canva.com/mcp", "oauth": True,
              "custo": "MCP oficial do Canva: o plano grátis cobre criar, editar, buscar e exportar designs; redimensionar, "
                       "autofill e kit de marca pedem Canva Pro. Ações de IA gastam créditos de IA do Canva.",
              "como": "Clique em Conectar: abre o Canva no navegador, você autoriza o \"Jarvis (pessoal)\" e pronto."},
    "notion": {"titulo": "Notion", "tipo": "http", "url": "https://mcp.notion.com/mcp", "oauth": True,
               "custo": "Grátis (Notion MCP oficial, hospedado pelo Notion).",
               "como": "Clique em Conectar: abre o Notion no navegador, você escolhe as páginas e autoriza. Pronto."},
    "github": {"titulo": "GitHub", "tipo": "nativo",
               "custo": "Grátis (API do GitHub). O servidor MCP remoto do GitHub pede licença do Copilot (o Copilot Free serve).",
               "como": "Crie um token em github.com/settings/tokens (fine-grained, só os repositórios que quiser) e cole aqui."},
    "google": {"titulo": "Google (Agenda, Gmail, Drive)", "tipo": "nativo",
               "custo": "Grátis (APIs do Google, com um projeto seu no Google Cloud em modo de teste).",
               "como": "No console.cloud.google.com: crie um projeto, ative Calendar, Gmail e Drive API, crie uma credencial "
                       f"OAuth 'App para computador' ou 'Web' com o retorno {RETORNO_GOOGLE} e cole Client ID e Secret aqui."},
    "telegram": {"titulo": "Telegram", "tipo": "nativo", "custo": "Grátis (Bot API do Telegram).",
                 "como": "Fale com o @BotFather, crie um bot, cole o token aqui e mande uma mensagem pro bot uma vez."},
    "spotify": {"titulo": "Spotify", "tipo": "embutido", "custo": "Já conectado. Tocar pelo Jarvis exige Spotify Premium.",
                "como": "Já funciona por voz (\"toca…\")."},
    "whatsapp": {"titulo": "WhatsApp", "tipo": "embutido",
                 "custo": "Pelo app do WhatsApp no PC: grátis. A API oficial (WhatsApp Cloud API) é paga por conversa e "
                          "exige conta de empresa verificada na Meta.",
                 "como": "Já funciona por voz (\"manda pro Fulano…\"), pelo app do WhatsApp no PC."},
}
CITA_O_APP = {"canva": r"canva", "notion": r"notion", "github": r"github|reposit[oó]rio|issue|pull request|\bpr\b",
              "google": r"agenda|calend[aá]rio|compromisso|evento|gmail|e-?mail|drive|google",
              "telegram": r"telegram"}
LEITURA = re.compile(r"^(?:get|list|search|read|fetch|find|query|retrieve|view|describe|show|count|check|whoami|me|"
                     r"buscar|listar|ler|ver|procurar|agenda|emails|repos|issues|prs|notificacoes|ultimas|drive)", re.I)


# ------------------------------------------------------------------ config

def _config():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _salvar(c):
    ARQUIVO.parent.mkdir(exist_ok=True)
    ARQUIVO.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def _cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _salvar_cache(c):
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")


def _nome_ok(nome):
    return re.sub(r"[^a-z0-9_]", "_", nome.lower())[:24]


def lista():
    """Pra tela: catálogo + os que ele adicionou, com status (sem segredos)."""
    c = _config()
    saida = []
    for nome, info in {**{k: {} for k in CATALOGO}, **c}.items():
        cat, cfg = CATALOGO.get(nome, {}), c.get(nome, {})
        saida.append({
            "nome": nome, "titulo": cfg.get("titulo") or cat.get("titulo") or nome, "tipo": cfg.get("tipo") or cat.get("tipo", "http"),
            "url": cfg.get("url") or cat.get("url", ""), "comando": cfg.get("comando", ""), "args": cfg.get("args", []),
            "oauth": cfg.get("oauth", cat.get("oauth", False)), "permissao": cfg.get("permissao", "leitura"),
            "ligado": bool(cfg.get("ligado")) or cat.get("tipo") == "embutido", "custo": cat.get("custo", ""),
            "como": cat.get("como", ""), "precisa_cliente": cat.get("precisa_cliente", False) or nome == "google",
            "status": _status(nome, cfg, cat), "ferramentas": len(_cache().get(nome, [])) or len(NATIVOS.get(nome, {})),
            "personalizado": nome not in CATALOGO})
    return saida


def _status(nome, cfg, cat):
    if cat.get("tipo") == "embutido":
        return "embutido"
    if not cfg.get("ligado"):
        return "desligado"
    if nome in NATIVOS:
        return "conectado" if _tem_credencial(nome) else "falta credencial"
    if cfg.get("oauth"):
        return "conectado" if cofre.pegar(f"oauth:{nome}:tokens") else "falta login"
    return "conectado" if _cache().get(nome) else "não testado"


def salvar(dados):
    """Adiciona/atualiza um conector. Segredos (token, chave, client_secret) vão pro cofre."""
    nome = _nome_ok(dados.get("nome", ""))
    if not nome:
        raise ValueError("Falta o nome.")
    c = _config()
    atual = c.get(nome, {})
    cat = CATALOGO.get(nome, {})
    for campo in ("titulo", "tipo", "url", "comando", "permissao"):
        if dados.get(campo) is not None:
            atual[campo] = dados[campo]
    atual.setdefault("tipo", cat.get("tipo", "http"))
    atual.setdefault("url", cat.get("url", ""))
    if dados.get("args") is not None:
        atual["args"] = dados["args"] if isinstance(dados["args"], list) else [a for a in str(dados["args"]).split() if a]
    if dados.get("oauth") is not None:
        atual["oauth"] = bool(dados["oauth"])
    atual.setdefault("oauth", cat.get("oauth", False))
    if dados.get("ligado") is not None:
        atual["ligado"] = bool(dados["ligado"])
    for segredo in ("token", "client_id", "client_secret", "chat_id"):
        if dados.get(segredo):
            cofre.guardar(f"{segredo}:{nome}", dados[segredo].strip())
    if dados.get("env"):  # stdio: variáveis com segredo, "NOME=valor" por linha → cofre
        env = dict(l.split("=", 1) for l in str(dados["env"]).splitlines() if "=" in l)
        cofre.guardar(f"env:{nome}", env)
        atual["env_nomes"] = sorted(env)
    c[nome] = atual
    _salvar(c)
    return nome


def remover(nome):
    c = _config()
    c.pop(nome, None)
    _salvar(c)
    for k in cofre.nomes():
        if k.endswith(":" + nome) or f":{nome}:" in k:
            cofre.apagar(k)
    cache = _cache()
    cache.pop(nome, None)
    _salvar_cache(cache)


def nomes_ligados():
    return [n for n, cfg in _config().items() if cfg.get("ligado")]


# ------------------------------------------------------------------ MCP (cliente)

class _Armazem:
    """TokenStorage do SDK MCP: tokens e registro do cliente OAuth ficam no cofre."""
    def __init__(self, nome):
        self.nome = nome

    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken
        t = cofre.pegar(f"oauth:{self.nome}:tokens")
        return OAuthToken.model_validate(t) if t else None

    async def set_tokens(self, tokens):
        cofre.guardar(f"oauth:{self.nome}:tokens", tokens.model_dump(mode="json", exclude_none=True))

    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull
        info = cofre.pegar(f"oauth:{self.nome}:cliente")
        if not info and cofre.pegar(f"client_id:{self.nome}"):  # cliente pré-registrado (Canva: Developer Portal)
            info = {"client_id": cofre.pegar(f"client_id:{self.nome}"), "client_secret": cofre.pegar(f"client_secret:{self.nome}"),
                    "redirect_uris": [RETORNO_OAUTH], "token_endpoint_auth_method": "client_secret_post"
                    if cofre.pegar(f"client_secret:{self.nome}") else "none"}
        return OAuthClientInformationFull.model_validate(info) if info else None

    async def set_client_info(self, info):
        cofre.guardar(f"oauth:{self.nome}:cliente", info.model_dump(mode="json", exclude_none=True))


_esperando_oauth = {}  # state → Future com o código que volta do navegador


def receber_oauth(code, state):
    """O navegador voltou do login (rota /conectores/oauth/retorno)."""
    for chave, futuro in list(_esperando_oauth.items()):
        if not futuro.done():
            futuro.get_loop().call_soon_threadsafe(futuro.set_result, (code, state))
            _esperando_oauth.pop(chave, None)
            return True
    return False


def _auth(nome, cfg):
    if not cfg.get("oauth"):
        return None
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import AuthorizationCodeResult, OAuthClientMetadata

    async def abrir_login(url):
        # aqui abrir o navegador é o pedido dele (clicou em Conectar): o login do app só existe no site do app
        webbrowser.open(url)

    async def esperar_codigo():
        futuro = asyncio.get_running_loop().create_future()
        _esperando_oauth[nome] = futuro
        code, state = await asyncio.wait_for(futuro, timeout=300)
        return AuthorizationCodeResult(code=code, state=state)

    return OAuthClientProvider(
        server_url=cfg["url"],
        client_metadata=OAuthClientMetadata(client_name="Jarvis (pessoal)", redirect_uris=[RETORNO_OAUTH],
                                            grant_types=["authorization_code", "refresh_token"],
                                            response_types=["code"], token_endpoint_auth_method="none"),
        storage=_Armazem(nome), redirect_handler=abrir_login, callback_handler=esperar_codigo)


async def _com_sessao(nome, trabalho):
    """Abre uma sessão MCP com o conector, roda trabalho(sessao) e fecha."""
    from mcp import ClientSession, StdioServerParameters
    cfg = _config().get(nome) or {}
    if cfg.get("tipo") == "stdio":
        from mcp.client.stdio import stdio_client
        env = {**__import__("os").environ, **(cofre.pegar(f"env:{nome}") or {})}
        comando = cfg["comando"]
        if comando in ("npx", "npm", "node") and __import__("os").name == "nt":
            comando += ".cmd"  # no Windows o npx é um .cmd
        params = StdioServerParameters(command=comando, args=cfg.get("args") or [], env=env)
        async with stdio_client(params) as (leitura, escrita):
            async with ClientSession(leitura, escrita) as s:
                await s.initialize()
                return await trabalho(s)
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
    cabecalhos = {}
    token = cofre.pegar(f"token:{nome}")
    if token and not cfg.get("oauth"):
        cabecalhos["Authorization"] = f"Bearer {token}"
    async with create_mcp_http_client(headers=cabecalhos, auth=_auth(nome, cfg)) as cliente:
        async with streamable_http_client(cfg["url"], http_client=cliente) as transporte:
            leitura, escrita = transporte[0], transporte[1]
            async with ClientSession(leitura, escrita) as s:
                await s.initialize()
                return await trabalho(s)


async def atualizar_ferramentas(nome):
    """Conecta (faz o login OAuth se precisar), lista as ferramentas e guarda no cache."""
    async def listar(s):
        r = await s.list_tools()
        saida = []
        for t in r.tools:
            anot = getattr(t, "annotations", None)
            so_le = bool(anot and getattr(anot, "readOnlyHint", None)) or bool(LEITURA.match(t.name))
            saida.append({"name": t.name, "description": (t.description or "")[:400],
                          "inputSchema": t.inputSchema or {"type": "object", "properties": {}}, "leitura": so_le})
        return saida
    ferramentas = await _com_sessao(nome, listar)
    cache = _cache()
    cache[nome] = ferramentas
    _salvar_cache(cache)
    return ferramentas


# ------------------------------------------------------------------ plugins nativos

def _tem_credencial(nome):
    if nome == "google":
        return bool(cofre.pegar("oauth:google:tokens"))
    return bool(cofre.pegar(f"token:{nome}"))


def _gh(metodo, caminho, **kw):
    r = httpx.request(metodo, "https://api.github.com" + caminho, timeout=15, **kw,
                      headers={"Authorization": f"Bearer {cofre.pegar('token:github')}", "Accept": "application/vnd.github+json"})
    r.raise_for_status()
    return r.json()


def gh_repos():
    return "\n".join(f"{r['full_name']} · {'privado' if r['private'] else 'público'} · atualizado {r['pushed_at'][:10]}"
                     for r in _gh("GET", "/user/repos", params={"sort": "pushed", "per_page": 20}))


def gh_issues(repo, estado="open"):
    itens = _gh("GET", f"/repos/{repo}/issues", params={"state": estado or "open", "per_page": 20})
    return "\n".join(f"#{i['number']} {i['title']} ({'PR' if 'pull_request' in i else 'issue'}, {i['state']})" for i in itens) or "Nenhuma."


def gh_criar_issue(repo, titulo, texto=""):
    i = _gh("POST", f"/repos/{repo}/issues", json={"title": titulo, "body": texto})
    return f"Criei a issue #{i['number']}: {i['html_url']}"


def gh_notificacoes():
    return "\n".join(f"{n['repository']['full_name']}: {n['subject']['title']} ({n['reason']})"
                     for n in _gh("GET", "/notifications", params={"per_page": 20})) or "Nenhuma notificação."


def _tg(metodo, **dados):
    r = httpx.post(f"https://api.telegram.org/bot{cofre.pegar('token:telegram')}/{metodo}", json=dados, timeout=15)
    r.raise_for_status()
    return r.json()["result"]


def tg_ultimas():
    msgs = [u.get("message") for u in _tg("getUpdates", limit=20) if u.get("message")]
    if msgs and not cofre.pegar("chat_id:telegram"):
        cofre.guardar("chat_id:telegram", str(msgs[-1]["chat"]["id"]))  # a 1ª mensagem dele pro bot ensina o chat
    return "\n".join(f"{m['from'].get('first_name', '')}: {m.get('text', '(mídia)')}" for m in msgs[-10:]) or "Nada novo."


def tg_enviar(texto):
    chat = cofre.pegar("chat_id:telegram")
    if not chat:
        tg_ultimas()
        chat = cofre.pegar("chat_id:telegram")
    if not chat:
        return "Manda uma mensagem pro seu bot no Telegram primeiro (assim eu sei o seu chat)."
    _tg("sendMessage", chat_id=chat, text=texto)
    return "Mandei no Telegram."


ESCOPOS_GOOGLE = ("https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/gmail.modify "
                  "https://www.googleapis.com/auth/drive.readonly")


def google_endereco_de_login():
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": cofre.pegar("client_id:google"), "redirect_uri": RETORNO_GOOGLE, "response_type": "code",
        "scope": ESCOPOS_GOOGLE, "access_type": "offline", "prompt": "consent"})


def google_concluir(code):
    r = httpx.post("https://oauth2.googleapis.com/token", timeout=15, data={
        "code": code, "client_id": cofre.pegar("client_id:google"), "client_secret": cofre.pegar("client_secret:google"),
        "redirect_uri": RETORNO_GOOGLE, "grant_type": "authorization_code"})
    r.raise_for_status()
    t = r.json()
    t["expira"] = time.time() + t.get("expires_in", 3600)
    cofre.guardar("oauth:google:tokens", t)


def _google_token():
    t = cofre.pegar("oauth:google:tokens")
    if not t:
        raise PermissionError("Google não conectado (Configurações → Conectores).")
    if time.time() > t.get("expira", 0) - 60:
        r = httpx.post("https://oauth2.googleapis.com/token", timeout=15, data={
            "client_id": cofre.pegar("client_id:google"), "client_secret": cofre.pegar("client_secret:google"),
            "refresh_token": t["refresh_token"], "grant_type": "refresh_token"})
        r.raise_for_status()
        t = {**t, **r.json(), "expira": time.time() + r.json().get("expires_in", 3600)}
        cofre.guardar("oauth:google:tokens", t)
    return t["access_token"]


def _g(metodo, url, **kw):
    r = httpx.request(metodo, url, headers={"Authorization": f"Bearer {_google_token()}"}, timeout=15, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def g_agenda(dias="1"):
    agora = datetime.now(timezone.utc)
    itens = _g("GET", "https://www.googleapis.com/calendar/v3/calendars/primary/events", params={
        "timeMin": agora.isoformat(), "timeMax": (agora + timedelta(days=int(dias or 1))).isoformat(),
        "singleEvents": "true", "orderBy": "startTime", "maxResults": 20}).get("items", [])
    return "\n".join(f"{(e['start'].get('dateTime') or e['start'].get('date'))[:16].replace('T', ' ')} · {e.get('summary', '(sem título)')}"
                     for e in itens) or "Nada na agenda nesse período."


def g_criar_evento(titulo, inicio, fim=""):
    """inicio/fim em 'AAAA-MM-DD HH:MM' (horário de Brasília)."""
    ini = datetime.strptime(inicio.strip()[:16], "%Y-%m-%d %H:%M")
    f = datetime.strptime(fim.strip()[:16], "%Y-%m-%d %H:%M") if fim else ini + timedelta(hours=1)
    e = _g("POST", "https://www.googleapis.com/calendar/v3/calendars/primary/events", json={
        "summary": titulo, "start": {"dateTime": ini.isoformat(), "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": f.isoformat(), "timeZone": "America/Sao_Paulo"}})
    return f"Marquei '{titulo}' na agenda: {e.get('htmlLink', '')}"


def g_emails(busca="is:unread"):
    ids = _g("GET", "https://gmail.googleapis.com/gmail/v1/users/me/messages", params={"q": busca or "is:unread", "maxResults": 8}).get("messages", [])
    linhas = []
    for m in ids:
        d = _g("GET", f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}", params={"format": "metadata",
                                                                                                    "metadataHeaders": ["From", "Subject"]})
        h = {x["name"]: x["value"] for x in d.get("payload", {}).get("headers", [])}
        linhas.append(f"[{m['id']}] {h.get('From', '')[:40]} · {h.get('Subject', '')} — {d.get('snippet', '')[:120]}")
    return "\n".join(linhas) or "Nenhum e-mail."


def g_enviar_email(para, assunto, texto):
    import base64
    from email.mime.text import MIMEText
    msg = MIMEText(texto, "plain", "utf-8")
    msg["To"], msg["Subject"] = para, assunto
    _g("POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
       json={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()})
    return f"E-mail enviado pra {para}."


def g_drive(busca):
    itens = _g("GET", "https://www.googleapis.com/drive/v3/files", params={
        "q": f"name contains '{busca.replace(chr(39), '')}' and trashed = false", "pageSize": 15,
        "fields": "files(name,webViewLink,modifiedTime)"}).get("files", [])
    return "\n".join(f"{f['name']} · {f['modifiedTime'][:10]} · {f['webViewLink']}" for f in itens) or "Nada no Drive com esse nome."


def _p(**campos):
    return {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in campos.items()},
            "required": [k for k in campos if not k.startswith("_")]}


# nome → ferramenta → (função, só_leitura, descrição, parâmetros)
NATIVOS = {
    "github": {
        "repos": (gh_repos, True, "Lista os repositórios dele no GitHub.", _p()),
        "issues": (gh_issues, True, "Issues e PRs de um repositório (dono/repo).", _p(repo="dono/repo", estado="open|closed|all")),
        "notificacoes": (gh_notificacoes, True, "Notificações do GitHub dele.", _p()),
        "criar_issue": (gh_criar_issue, False, "Cria uma issue.", _p(repo="dono/repo", titulo="título", texto="descrição")),
    },
    "telegram": {
        "ultimas": (tg_ultimas, True, "Últimas mensagens que chegaram no bot dele.", _p()),
        "enviar": (tg_enviar, False, "Manda uma mensagem pra ele no Telegram (pelo bot).", _p(texto="mensagem")),
    },
    "google": {
        "agenda": (g_agenda, True, "Compromissos do Google Agenda dos próximos N dias.", _p(dias="quantos dias (1 = hoje)")),
        "criar_evento": (g_criar_evento, False, "Marca um compromisso no Google Agenda.",
                         _p(titulo="título", inicio="AAAA-MM-DD HH:MM", fim="AAAA-MM-DD HH:MM (opcional)")),
        "emails": (g_emails, True, "Procura e-mails no Gmail (busca do Gmail: is:unread, from:x, assunto…).", _p(busca="busca do Gmail")),
        "enviar_email": (g_enviar_email, False, "Envia um e-mail pelo Gmail dele.", _p(para="e-mail", assunto="assunto", texto="texto")),
        "drive": (g_drive, True, "Procura arquivos no Google Drive pelo nome.", _p(busca="parte do nome")),
    },
}
for _ferr in NATIVOS.values():  # campos opcionais
    for _k, (_f, _l, _d, _par) in _ferr.items():
        _par["required"] = [r for r in _par["required"] if r not in ("estado", "fim", "dias", "busca", "texto")
                            or _k in ("enviar", "enviar_email")]


# ------------------------------------------------------------------ o que o cérebro vê

def _ferramentas_de(nome):
    cfg = _config().get(nome) or {}
    so_leitura = cfg.get("permissao", "leitura") != "escrita"
    if nome in NATIVOS:
        itens = [{"name": k, "description": d, "inputSchema": p, "leitura": l} for k, (_, l, d, p) in NATIVOS[nome].items()]
    else:
        itens = _cache().get(nome, [])
    return [t for t in itens if t["leitura"] or not so_leitura]


def _id(nome, ferramenta):
    return f"con__{nome}__{re.sub(r'[^A-Za-z0-9_-]', '_', ferramenta)}"[:64]


def definicoes(grupos=()):
    """Definições das ferramentas dos conectores ligados que estão nos grupos carregados."""
    saida = []
    for nome in nomes_ligados():
        if nome not in grupos:
            continue
        titulo = (CATALOGO.get(nome) or {}).get("titulo") or nome
        for t in _ferramentas_de(nome)[:25]:
            saida.append({"type": "function", "function": {
                "name": _id(nome, t["name"]), "description": f"[{titulo}] {t['description']}"[:500],
                "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}}})
    return saida


def grupos_citados(texto):
    return {n for n in nomes_ligados() if re.search(CITA_O_APP.get(n, re.escape(n)), texto or "", re.I)}


def _separar(id_):
    _, nome, ferramenta = id_.split("__", 2)
    for t in _ferramentas_de(nome):
        if _id(nome, t["name"]) == id_:
            return nome, t
    return nome, None


def rotulo(id_):
    nome, t = _separar(id_)
    return f"{(CATALOGO.get(nome) or {}).get('titulo', nome)} · {t['name'] if t else id_}"


def precisa_autorizar(id_, args):
    _, t = _separar(id_)
    return not t or not t["leitura"]  # enviar, publicar, apagar, criar, gastar: sempre com o "sim"


async def chamar(id_, args):
    nome, t = _separar(id_)
    if not t:
        return "Essa ferramenta do conector não está liberada (veja a permissão nas Configurações)."
    try:
        if nome in NATIVOS:
            func = NATIVOS[nome][t["name"]][0]
            return str(await asyncio.to_thread(func, **(args or {})))[:6000]

        async def rodar(s):
            r = await s.call_tool(t["name"], args or {})
            partes = []
            for c in r.content or []:
                partes.append(getattr(c, "text", None) or f"[{getattr(c, 'type', 'conteúdo')}]")
            texto = "\n".join(partes) or "(sem resposta)"
            return ("Erro: " + texto) if getattr(r, "isError", False) else texto
        return (await asyncio.wait_for(_com_sessao(nome, rodar), timeout=90))[:6000]
    except Exception as e:
        return f"Erro no conector {nome}: {str(e)[:300]}"


async def testar(nome):
    """Botão Testar: conecta e conta as ferramentas (faz o login OAuth se faltar)."""
    cfg = _config().get(nome) or {}
    if CATALOGO.get(nome, {}).get("tipo") == "embutido":
        return {"ok": True, "texto": "Embutido no Jarvis: já funciona por voz."}
    if nome in NATIVOS:
        try:
            if nome == "github":
                eu = await asyncio.to_thread(_gh, "GET", "/user")
                return {"ok": True, "texto": f"GitHub ok: {eu.get('login')}."}
            if nome == "telegram":
                eu = await asyncio.to_thread(_tg, "getMe")
                return {"ok": True, "texto": f"Telegram ok: bot @{eu.get('username')}."}
            if nome == "google":
                if not cofre.pegar("oauth:google:tokens"):
                    if not cofre.pegar("client_id:google"):
                        return {"ok": False, "texto": "Cole o Client ID e o Client Secret do seu app Google primeiro."}
                    webbrowser.open(google_endereco_de_login())
                    return {"ok": False, "texto": "Abri o login do Google no navegador. Autorize e teste de novo."}
                await asyncio.to_thread(g_agenda, "1")
                return {"ok": True, "texto": "Google ok: agenda respondeu."}
        except Exception as e:
            return {"ok": False, "texto": f"Falhou: {str(e)[:200]}"}
    if not cfg:
        return {"ok": False, "texto": "Configure e ligue o conector primeiro."}
    try:
        ferramentas = await asyncio.wait_for(atualizar_ferramentas(nome), timeout=320)
        return {"ok": True, "texto": f"Conectado: {len(ferramentas)} ferramentas "
                                      f"({sum(1 for t in ferramentas if t['leitura'])} de leitura)."}
    except Exception as e:
        return {"ok": False, "texto": f"Falhou: {str(e)[:300]}"}
