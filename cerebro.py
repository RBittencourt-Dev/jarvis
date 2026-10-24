"""Cérebro do Jarvis: IAs grandes na nuvem (grátis), trocando sozinho quando uma bate o limite, e o Ollama local de reserva.

Provedores (cada um com a sua chave num arquivo da pasta):
  gemini.json {"chave": "AIza..."}  — Google AI Studio: o mais esperto na conversa e enxerga a tela
  groq.json   {"chave": "gsk_..."}  — Groq: o mais rápido; também é o ouvido (Whisper)
  freellmapi.json {"chave": "freellmapi-..."} — FreeLLMAPI local (porta 3001): reserva com ~30 provedores grátis
O plano grátis de cada um tem limite por minuto; quando um responde 429 ("calma"), o próximo assume na hora.
Sem nenhuma chave, ou sem internet, tudo cai no Ollama (qwen2.5:3b), como era antes.

As mensagens da conversa ficam num formato só (o do Ollama, com "id" nas chamadas de ferramenta);
a conversão para o formato OpenAI (que os dois provedores falam) é feita aqui na hora de mandar.
"""
import json
import re
import time
import uuid
from pathlib import Path

import httpx

RAIZ = Path(__file__).parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))

PROVEDORES = {  # na ordem de preferência; modelos do mais esperto pro mais leve
    "gemini": {"url": "https://generativelanguage.googleapis.com/v1beta/openai", "arquivo": "gemini.json", "prefixo": ("AIza", "AQ."),  # "AQ." = formato novo do AI Studio
               # conta nova (out/2026) não acessa mais o 2.5 ("no longer available to new users"); o 3.8 e o
               # flash-latest (que aponta pra ele) ficaram 30 s mudos no teste de 23/10: fora até o Google aliviar
               "modelos": ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite",
                           "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
               "visao": ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite",
                         "gemini-2.5-flash", "gemini-2.5-flash-lite"]},
    "groq": {"url": "https://api.groq.com/openai/v1", "arquivo": "groq.json", "prefixo": "gsk_",
             "modelos": CONFIG.get("modelos_nuvem") or ["openai/gpt-oss-120b", "moonshotai/kimi-k2-instruct-0905",
                                                         "llama-3.3-70b-versatile", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
             "visao": ["qwen/qwen3.8-27b", "meta-llama/llama-4-maverick-17b-128e-instruct",
                       "meta-llama/llama-4-scout-17b-16e-instruct"]},
    # FreeLLMAPI (github.com/tashfeenahmed/freellmapi) rodando neste PC: junta ~30 provedores grátis atrás de um
    # endereço só e troca sozinho quando um bate o limite. Fica DEPOIS dos dois diretos (que são mais rápidos sem o
    # desvio) e ANTES do Ollama: quando Gemini/Groq cansam, a conversa segue numa IA grande em vez do 3B do PC.
    "freellmapi": {"url": CONFIG.get("freellmapi_url", "http://127.0.0.1:3001/v1"), "arquivo": "freellmapi.json",
                   "prefixo": "freellmapi-", "sem_lista": True,  # "auto" é nome virtual: não aparece no /models
                   "modelos": CONFIG.get("modelos_freellmapi") or ["auto:fast", "auto"],
                   "visao": CONFIG.get("visao_freellmapi") or []},
}
URL_GROQ = PROVEDORES["groq"]["url"]
TRANSCRICOES = ["whisper-large-v3", "whisper-large-v3-turbo"]  # o completo erra menos em português
DICAS = ["Jarvis", "SevenCode", "Spotify", "playlist", "leads", "Radar", "CRM", "WhatsApp", "VS Code",
         "Opera", "Chrome", "caixa", "reunião", "condomínio", "commit", "deploy", "chefe", "Porthon"]

_listas = {}      # provedor -> (quando, [modelos])
_no_limite = {}   # (provedor, modelo) -> até quando está bloqueado (429)
_sem_raciocinio = set()  # (provedor, modelo) que recusaram reasoning_effort


def chave(provedor="groq"):
    p = PROVEDORES[provedor]
    k = ""
    try:
        import cofre  # chave protegida (Configurações → Privacidade) tem prioridade
        k = (cofre.pegar(f"chave:{provedor}") or "").strip()
    except Exception:
        pass
    if not k:
        try:
            k = json.loads((RAIZ / p["arquivo"]).read_text(encoding="utf-8")).get("chave", "").strip()
        except (OSError, ValueError):
            return None
    return k if k.startswith(p["prefixo"]) else None


def nuvem():
    return any(chave(p) for p in PROVEDORES)


def _cabecalho(provedor="groq"):
    return {"Authorization": f"Bearer {chave(provedor)}"}


def modelos_da_conta(provedor="groq"):
    """Modelos que a conta enxerga; guardado por 1 h."""
    quando, lista = _listas.get(provedor, (0, None))
    if lista is not None and time.time() - quando < 3600:
        return lista
    try:
        r = httpx.get(PROVEDORES[provedor]["url"] + "/models", headers=_cabecalho(provedor), timeout=8)
        r.raise_for_status()
        lista = [m["id"].removeprefix("models/") for m in r.json()["data"]]
    except Exception:
        lista = list(PROVEDORES[provedor]["modelos"])  # sem lista: tenta na ordem e deixa a API dizer não
    _listas[provedor] = (time.time(), lista)
    return lista


# Quem faz o quê (decisão dele, 24/10): Groq é o dia a dia (0,7 s, já acostumado com os pedidos dele); Gemini entra
# no que é DIFÍCIL — onde o Groq costuma errar: mexer em arquivo/PC, código, análise, texto longo, aula, marketing —
# e na visão (enxerga melhor a tela). FreeLLMAPI e o Ollama local são as reservas dos dois.
ORDEM = {"facil": ["groq", "gemini", "freellmapi"], "dificil": ["gemini", "groq", "freellmapi"],
         "visao": ["gemini", "groq", "freellmapi"]}

DIFICIL = re.compile(
    r"\b(explic\w*|analis\w*|compar\w*|por ?que|planej\w*|estrat[eé]g\w*|calcul\w*|resolv\w*|c[oó]digo|"
    r"program(?:a[cç]|ar|and|ador)\w*|erro|bug|resum\w*|traduz\w*|escrev\w*|redig\w*|reescrev\w*|melhor\w* (?:o|a|esse|essa) |"
    r"e-?mail|contrato|proposta|cri[ae] (?:um|uma)|edit\w*|mex\w*|alter\w*|organiz\w*|arquivo|pasta|comando|"
    r"configur\w*|instal\w*|script|planilha|document\w*|relat[oó]rio|passo a passo|detalh\w*|"
    r"vantage\w*|desvantage\w*|pr[oó]s e contras|diferen[cç]a)\b", re.I)


def e_dificil(mensagens_ou_texto):
    """Pedido que pede cabeça (ou mexe nas coisas): vai pro Gemini. O resto, Groq."""
    texto = mensagens_ou_texto
    if not isinstance(texto, str):
        texto = next((m.get("content") or "" for m in reversed(mensagens_ou_texto) if m.get("role") == "user"), "")
    texto = texto if isinstance(texto, str) else ""
    return len(texto) > 220 or bool(DIFICIL.search(texto))


def candidatos(tipo="modelos", dificil=False):
    """[(provedor, modelo)] na ordem de uso, sem os que estão no castigo do limite."""
    saida = []
    ordem = ORDEM["visao" if tipo == "visao" else "dificil" if dificil else "facil"]
    for prov in sorted(PROVEDORES, key=lambda x: ordem.index(x) if x in ordem else 99):
        p = PROVEDORES[prov]
        if not chave(prov):
            continue
        conta = p[tipo] if p.get("sem_lista") else modelos_da_conta(prov)
        saida += [(prov, m) for m in p[tipo] if m in conta and _no_limite.get((prov, m), 0) < time.time()]
    return saida


def nome_do_cerebro():
    c = candidatos()
    return f"{c[0][0]} · {c[0][1]}" if c else f"local · {CONFIG['modelo']}"


def _castigo(prov, modelo, r):
    espera = r.headers.get("retry-after")
    try:
        espera = float(espera) if espera else 30.0
    except ValueError:
        espera = 30.0
    _no_limite[(prov, modelo)] = time.time() + min(max(espera, 5), 3600)


def _corpo(prov, modelo, mensagens, temperatura, max_tokens, **extra):
    corpo = {"model": modelo, "messages": _para_openai(mensagens), "temperature": temperatura,
             "max_completion_tokens" if prov == "groq" else "max_tokens": max_tokens, **extra}
    if (prov, modelo) not in _sem_raciocinio and ("gpt-oss" in modelo or prov == "gemini"):
        corpo["reasoning_effort"] = "low"  # pensa pouco: a resposta sai rápido
    return corpo


# ------------------------------------------------------------------ conversão de mensagens

def _para_openai(mensagens):
    saida, pendentes = [], []
    for m in mensagens:
        if m["role"] == "assistant" and m.get("tool_calls"):
            chamadas = []
            for c in m["tool_calls"]:
                cid = c.get("id") or "c" + uuid.uuid4().hex[:10]
                c["id"] = cid
                args = c["function"].get("arguments") or {}
                chamadas.append({"id": cid, "type": "function", "function": {
                    "name": c["function"]["name"], "arguments": args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)}})
            pendentes = [c["id"] for c in chamadas]
            saida.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": chamadas})
        elif m["role"] == "tool":
            if not pendentes:
                continue  # resposta de ferramenta sem chamada (sobra de conversa cortada): a API recusaria
            saida.append({"role": "tool", "tool_call_id": m.get("tool_call_id") or pendentes.pop(0), "content": m["content"]})
            if m.get("tool_call_id") in pendentes:
                pendentes.remove(m["tool_call_id"])
        else:
            saida.append({"role": m["role"], "content": m.get("content") or ""})
    return saida


_para_groq = _para_openai  # nome antigo


def _para_ollama(mensagens):
    saida = []
    for m in mensagens:
        n = {"role": m["role"], "content": m.get("content") or ""}
        if m.get("tool_calls"):
            n["tool_calls"] = [{"function": {"name": c["function"]["name"], "arguments": _args(c["function"].get("arguments"))}}
                               for c in m["tool_calls"]]
        saida.append(n)
    return saida


def _args(a):
    if isinstance(a, dict):
        return a
    try:
        return json.loads(a or "{}")
    except ValueError:
        return {}


# ------------------------------------------------------------------ conversa com ferramentas (streaming)

async def conversar(mensagens, ferramentas, temperatura=0.5, dificil=None):
    """Gera ("texto", pedaço) aos poucos e, no fim, ("chamadas", [...]) — chamadas no formato Ollama com "id"."""
    if dificil is None:
        dificil = e_dificil(mensagens)
    for prov, modelo in candidatos(dificil=dificil):
        for _ in range(2):  # 2ª volta só se o modelo recusou o reasoning_effort
            try:
                async for e in _stream(prov, modelo, mensagens, ferramentas, temperatura):
                    yield e
                return
            except _Repetir:
                continue
            except (_Limite, _AntesDeFalar):
                break  # falhou antes de soltar texto: o próximo assume sem a fala sair duplicada
    async for e in _ollama_stream(mensagens, ferramentas, temperatura):
        yield e


class _Limite(Exception):
    pass


class _AntesDeFalar(Exception):
    pass


class _Repetir(Exception):
    pass


async def _stream(prov, modelo, mensagens, ferramentas, temperatura):
    corpo = _corpo(prov, modelo, mensagens, temperatura, 1500, stream=True)
    if ferramentas:
        corpo["tools"] = ferramentas
    soltou = False
    chamadas = {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5, read=12)) as cliente:  # 12 s mudo = trava, passa pro próximo
            async with cliente.stream("POST", PROVEDORES[prov]["url"] + "/chat/completions",
                                      headers=_cabecalho(prov), json=corpo) as r:
                if r.status_code == 429:
                    _castigo(prov, modelo, r)
                    raise _Limite()
                if r.status_code == 503:  # "high demand" do Gemini: tenta o próximo e deixa esse descansar 2 min
                    _no_limite[(prov, modelo)] = time.time() + 120
                    raise _Limite()
                if r.status_code != 200:
                    texto = (await r.aread()).decode(errors="replace")
                    if r.status_code == 400 and "reasoning" in texto and (prov, modelo) not in _sem_raciocinio:
                        _sem_raciocinio.add((prov, modelo))
                        raise _Repetir()
                    raise _AntesDeFalar(f"{r.status_code} {texto[:200]}")
                async for linha in r.aiter_lines():
                    if not linha.startswith("data: ") or linha.strip() == "data: [DONE]":
                        continue
                    escolhas = json.loads(linha[6:]).get("choices") or [{}]
                    delta = escolhas[0].get("delta") or {}
                    if delta.get("content"):
                        soltou = True
                        yield ("texto", delta["content"])
                    for i, c in enumerate(delta.get("tool_calls") or []):
                        atual = chamadas.setdefault(c.get("index", i), {"id": c.get("id"), "nome": "", "args": ""})
                        atual["id"] = c.get("id") or atual["id"]
                        atual["nome"] += c.get("function", {}).get("name") or ""
                        atual["args"] += c.get("function", {}).get("arguments") or ""
    except (_Limite, _AntesDeFalar, _Repetir):
        raise
    except Exception as e:
        if isinstance(e, httpx.ConnectError):  # programa desligado (FreeLLMAPI fechado): 1 min sem tentar de novo
            for m in PROVEDORES[prov]["modelos"] + PROVEDORES[prov]["visao"]:
                _no_limite[(prov, m)] = time.time() + 60
        if not soltou:
            raise _AntesDeFalar(str(e))
        raise
    yield ("chamadas", [{"id": c["id"] or "c" + uuid.uuid4().hex[:10],
                         "function": {"name": c["nome"], "arguments": _args(c["args"])}}
                        for _, c in sorted(chamadas.items())])


def _sem_pensar():
    """qwen3 "pensa" antes de responder (lento demais sem GPU): desliga."""
    return {"think": False} if str(CONFIG.get("modelo", "")).startswith("qwen3") else {}


async def _ollama_stream(mensagens, ferramentas, temperatura):
    chamadas = []
    async with httpx.AsyncClient(timeout=180) as cliente:
        async with cliente.stream("POST", f"{CONFIG['ollama_url']}/api/chat", json={
            "model": CONFIG["modelo"], "messages": _para_ollama(mensagens), "tools": ferramentas or None,
            "stream": True, "keep_alive": CONFIG.get("keep_alive", "2h"), **_sem_pensar(),
            "options": {"num_ctx": int(CONFIG.get("contexto", 4096)), "temperature": temperatura},
        }) as r:
            if r.status_code != 200:
                raise RuntimeError(f"Ollama respondeu {r.status_code}")
            async for linha in r.aiter_lines():
                if not linha:
                    continue
                msg = json.loads(linha).get("message", {})
                chamadas += msg.get("tool_calls") or []
                if msg.get("content"):
                    yield ("texto", msg["content"])
    yield ("chamadas", [{"id": "c" + uuid.uuid4().hex[:10], "function": {
        "name": c["function"]["name"], "arguments": _args(c["function"].get("arguments"))}} for c in chamadas])


# ------------------------------------------------------------------ pedido simples (sem streaming)

def _postar(prov, modelo, corpo, timeout=30):
    """POST síncrono com as mesmas regras (castigo no 429, sem reasoning se o modelo recusar). Texto ou None."""
    for _ in range(2):
        try:
            r = httpx.post(PROVEDORES[prov]["url"] + "/chat/completions", headers=_cabecalho(prov), json=corpo, timeout=timeout)
        except Exception:
            return None
        if r.status_code == 429:
            _castigo(prov, modelo, r)
            return None
        if r.status_code == 503:
            _no_limite[(prov, modelo)] = time.time() + 120
            return None
        if r.status_code == 400 and "reasoning" in r.text and "reasoning_effort" in corpo:
            _sem_raciocinio.add((prov, modelo))
            corpo = {k: v for k, v in corpo.items() if k != "reasoning_effort"}
            continue
        if r.status_code != 200:
            return None
        return (r.json()["choices"][0]["message"].get("content") or "").strip()
    return None


async def completar(mensagens, json_mode=False, temperatura=0.3, max_tokens=400, dificil=False):
    """Texto inteiro de uma vez (interpretação de comando, sugestão de mensagem). dificil=True: especialista, aula,
    marketing, vendas… (Gemini primeiro)."""
    import asyncio
    for prov, modelo in candidatos(dificil=dificil):
        corpo = _corpo(prov, modelo, mensagens, temperatura, max_tokens + (600 if "gpt-oss" in modelo or prov == "gemini" else 0))  # o raciocínio também gasta token
        if json_mode:
            corpo["response_format"] = {"type": "json_object"}
        texto = await asyncio.to_thread(_postar, prov, modelo, corpo)
        if texto is not None:
            return texto
    async with httpx.AsyncClient(timeout=120) as cliente:
        r = await cliente.post(f"{CONFIG['ollama_url']}/api/chat", json={
            "model": CONFIG["modelo"], "stream": False, "keep_alive": CONFIG.get("keep_alive", "2h"), **_sem_pensar(),
            "messages": _para_ollama(mensagens),
            **({"format": "json"} if json_mode else {}),
            "options": {"temperature": temperatura, "num_predict": max_tokens}})
    return r.json()["message"]["content"].strip()


# ------------------------------------------------------------------ olhos (visão)

def ver(imagens_b64, pergunta):
    """Manda prints (JPEG em base64) pro modelo de visão e devolve a resposta em texto."""
    n = len(imagens_b64)
    conteudo = [{"type": "text", "text": (
        f"{'Estas são as ' + str(n) + ' telas' if n > 1 else 'Esta é a tela'} do PC do Rafael agora "
        f"({'uma imagem por monitor; são exatamente ' + str(n) + ' monitores' if n > 1 else 'um monitor'}). "
        "Responda em português do Brasil, curto e direto, como um assistente falando em voz alta (sem listas nem "
        "markdown). Diga só o que dá pra ver de verdade; não invente nomes que não estão legíveis. Se houver texto "
        "relevante (erro, mensagem), leia o essencial. Pergunta dele: " + pergunta)}]
    conteudo += [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in imagens_b64[:5]]
    for prov, modelo in candidatos("visao"):
        corpo = {"model": modelo, "messages": [{"role": "user", "content": conteudo}], "temperature": 0.2,
                 "max_completion_tokens" if prov == "groq" else "max_tokens": 400}
        if prov == "gemini":
            corpo["reasoning_effort"] = "low"
        texto = _postar(prov, modelo, corpo, timeout=40)
        if texto:
            return texto
    return None


# ------------------------------------------------------------------ ouvido (transcrição)

def transcrever(wav: bytes, dica=None, extras=(), arquivo=("fala.wav", "audio/wav")):
    """Áudio WAV → texto em português, pelo Whisper grande da Groq. None se não der (sem chave/sem internet).
    dica="" = sem dica nenhuma (para conferir se ele disse mesmo "Jarvis", sem empurrar a palavra)."""
    if not chave("groq"):
        return None
    if dica is None:
        dica = ", ".join([*DICAS, *extras][:60]) + "."
    texto = None
    for modelo in TRANSCRICOES:
        if _no_limite.get(("groq", modelo), 0) > time.time():
            continue
        try:
            r = httpx.post(URL_GROQ + "/audio/transcriptions", headers=_cabecalho("groq"), timeout=20,
                           files={"file": (arquivo[0], wav, arquivo[1])},  # o celular manda .m4a/.webm
                           data={"model": modelo, "language": "pt", "temperature": "0", "response_format": "json",
                                 **({"prompt": dica} if dica else {})})
            if r.status_code == 429:
                _castigo("groq", modelo, r)
                continue
            r.raise_for_status()
            texto = r.json().get("text", "").strip()
            break
        except Exception:
            continue
    if texto is None:
        return None
    # só barulho: o Whisper "devolve" a lista de dicas ("Radar, CRM, WhatsApp, VS Code.")
    palavras_dica = {d.lower() for d in [*DICAS, *extras]}
    pedacos = [p.strip(" .!?").lower() for p in texto.split(",") if p.strip(" .!?")]
    if len(pedacos) >= 3 and sum(p in palavras_dica for p in pedacos) >= len(pedacos) - 1:
        return ""
    # o Whisper "ouve" frases de legenda quando só tem barulho
    if re.search(r"amara\.org|legendas? (pela|por)|inscreva-se|obrigado por assistir|^obrigad[oa][.!]?$", texto, re.I):
        return ""
    return texto


# ------------------------------------------------------------------ FreeLLMAPI: liga junto com o Jarvis

def ligar_freellmapi():
    """Se o FreeLLMAPI está instalado (pasta ao lado do Jarvis) e fechado, sobe ele escondido."""
    import subprocess
    if not chave("freellmapi"):
        return
    try:
        httpx.get(PROVEDORES["freellmapi"]["url"].removesuffix("/v1") + "/", timeout=1.5)
        return  # já está no ar
    except Exception:
        pass
    pasta = Path(CONFIG.get("freellmapi_pasta") or RAIZ.parent / "FreeLLMAPI") / "server"
    if not (pasta / "dist" / "index.js").exists():
        return
    log = open(pasta.parent / "freellmapi.log", "ab")
    subprocess.Popen(["node", "dist/index.js"], cwd=pasta, stdout=log, stderr=log,
                     creationflags=0x08000000 | 0x00000008)  # sem janela, separado do Jarvis
