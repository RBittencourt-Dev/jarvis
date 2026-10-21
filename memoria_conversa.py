"""Memória da conversa: o que sai do histórico curto vira um resumo, que fica guardado em disco.

Antes, depois de ~12 mensagens o começo da conversa sumia. Agora:
  - quando a conversa passa do limite, as mensagens que saem são resumidas pelo cérebro (em segundo plano)
    e o resumo entra logo depois do prompt, como "[Resumo da conversa até aqui]";
  - o resumo fica em dados/conversa.json: abrir o Jarvis de novo (ou outro dia) continua lembrando do assunto;
  - resumo antigo (mais de 3 dias) vira só uma linha, pra não pesar.
"""
import asyncio
import json
import time
from pathlib import Path

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "dados" / "conversa.json"
LIMITE = 24        # passou disso, resume a parte velha
FICAM = 12         # quantas mensagens recentes ficam inteiras
_tarefas = set()


def _ler():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"resumo": "", "quando": 0}


def _gravar(resumo):
    ARQUIVO.parent.mkdir(exist_ok=True)
    ARQUIVO.write_text(json.dumps({"resumo": resumo, "quando": time.time()}, ensure_ascii=False), encoding="utf-8")


def resumo_guardado():
    d = _ler()
    if not d.get("resumo"):
        return ""
    dias = (time.time() - d.get("quando", 0)) / 86400
    if dias > 3:
        return ""  # muito velho: o diário (ver_registro) cobre
    return d["resumo"]


def mensagem_de_resumo(resumo):
    return {"role": "system", "content": f"[Resumo da conversa até aqui — use para entender 'aquilo', 'de novo', 'o de antes']\n{resumo}"}


def eh_resumo(m):
    return m.get("role") == "system" and str(m.get("content", "")).startswith("[Resumo da conversa")


def _texto_das(mensagens):
    linhas = []
    for m in mensagens:
        conteudo = str(m.get("content") or "").split("\n\n[Anotações]")[0].split("\n\n[Assunto")[0].strip()
        if m["role"] == "user" and conteudo:
            linhas.append(f"Rafael: {conteudo[:300]}")
        elif m["role"] == "assistant":
            usou = ", ".join(c["function"]["name"] for c in m.get("tool_calls") or [])
            if conteudo or usou:
                linhas.append(f"Jarvis: {conteudo[:300]}" + (f" (usou: {usou})" if usou else ""))
        elif m["role"] == "tool":
            linhas.append(f"  resultado: {conteudo[:160]}")
    return "\n".join(linhas)


async def _resumir(antigo, saindo):
    import cerebro
    texto = _texto_das(saindo)
    if not texto:
        return antigo
    pedido = ("Atualize o resumo da conversa entre o Rafael e o Jarvis (assistente dele). Máximo 8 linhas curtas, "
              "em português, só fatos úteis pra continuar a conversa: assuntos, pedidos, o que foi feito, decisões, "
              "nomes, arquivos e números citados, e o que ficou pendente. Sem enfeite.\n\n"
              f"RESUMO ATUAL:\n{antigo or '(vazio)'}\n\nMENSAGENS NOVAS:\n{texto}\n\nRESUMO ATUALIZADO:")
    try:
        novo = await cerebro.completar([{"role": "user", "content": pedido}], temperatura=0.2, max_tokens=350)
    except Exception:
        return antigo
    return (novo or antigo).strip()


def cortar(sessao):
    """Chamado antes de cada pergunta ao cérebro. Corta o histórico e resume a parte que saiu (sem esperar)."""
    msgs = sessao["mensagens"]
    if len(msgs) <= LIMITE:
        return msgs
    prompt = msgs[0]
    corpo = [m for m in msgs[1:] if not eh_resumo(m)]
    resto = corpo[-FICAM:]
    while resto and resto[0]["role"] != "user":
        resto.pop(0)
    saindo = corpo[:len(corpo) - len(resto)]
    resumo = sessao.get("resumo") or ""
    sessao["mensagens"] = [prompt, *([mensagem_de_resumo(resumo)] if resumo else []), *resto]

    async def trabalho():
        novo = await _resumir(resumo, saindo)
        if novo and novo != resumo:
            sessao["resumo"] = novo
            _gravar(novo)
            # troca a mensagem de resumo pela nova (sem mexer no resto da conversa)
            m = sessao["mensagens"]
            m[:] = [m[0], mensagem_de_resumo(novo), *[x for x in m[1:] if not eh_resumo(x)]]
    try:
        t = asyncio.get_running_loop().create_task(trabalho())
        _tarefas.add(t)
        t.add_done_callback(_tarefas.discard)
    except RuntimeError:
        pass
    return sessao["mensagens"]


def comeco_da_sessao(prompt_sistema):
    """Mensagens iniciais de uma sessão nova: o prompt e, se tiver, o resumo das últimas conversas."""
    resumo = resumo_guardado()
    return [{"role": "system", "content": prompt_sistema}, *([mensagem_de_resumo(resumo)] if resumo else [])], resumo


def esquecer():
    _gravar("")
