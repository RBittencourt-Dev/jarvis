"""Jarvis vendedor do Porthon: ajuda em prospecção, abordagem, qualificação de lead, quebra de objeção e ideias.

Pedido dele (23/10/2026): "treina o Jarvis pra me auxiliar com vendas, prospecção, ideias". Encaixa no Radar de Leads
que ele já tem (o Jarvis consulta leads em consultas.py/radar). Aqui é o CÉREBRO DE VENDAS: usa a mesma IA (Groq/Gemini)
com o conhecimento do Porthon pra gerar, na hora, o que ele precisa falar pra vender.

O que ele fala:
  - "como eu abordo um síndico" / "escreve uma mensagem de prospecção pra administradora" → mensagem de 1º contato.
  - "qualifica esse lead" / "esse lead presta?" → as perguntas certas pra saber se vale a pena (e o que descobrir).
  - "o cara falou que tá caro, o que respondo?" / "quebra a objeção do já tenho sistema" → resposta pra objeção.
  - "me dá argumentos pra vender o Porthon" → os pontos fortes, do jeito que convence síndico.
  - "ideias pra conseguir mais clientes" / "como eu prospecto condomínio" → ideias de prospecção.

Gera o texto, salva em conteudo/vendas/, copia pra área de transferência e (quando é mensagem) oferece mandar no
WhatsApp. NÃO envia nada sozinho — mensagem sai com o "sim" dele, como todo o resto.
"""
import asyncio
import json
import re
import time
import unicodedata
from datetime import date
from pathlib import Path

import cerebro

DEMORA = True
RAIZ = Path(__file__).parent
PASTA = RAIZ / "conteudo" / "vendas"

# ---------------------------------------------------------------- o conhecimento de vendas do Porthon
# É isto que faz o Jarvis "pensar" como vendedor do Porthon. Só o que é real — nada de número ou preço inventado.
VENDAS = """Você é o braço de vendas do PORTHON, um sistema de portaria e gestão para condomínios. Ajuda o Rafael (dono)
a vender. Fala português do Brasil, direto, humano, sem jargão e sem cara de robô.

QUEM COMPRA (cliente ideal):
- Síndicos moradores de prédios com portaria e muita encomenda/visitante.
- Síndicos profissionais e administradoras que cuidam de vários condomínios (dor de organizar tudo).
- Condomínios cansados de caderno na portaria e grupo de WhatsApp que ninguém lê.

A DOR que o Porthon resolve: "cadê minha encomenda?", portaria sem registro, aviso que não chega, reserva no grito,
carro bloqueando a saída sem saber de quem é, ocorrência que vira a palavra de um contra a do outro.

DIFERENCIAIS REAIS (não prometa além disto):
- Roda no celular do porteiro e no navegador, SEM instalar aplicativo.
- Encomenda com foto, aviso na hora pro morador, retirada com assinatura/código.
- Avisos do síndico que chegam a todos (ou a um bloco/unidade) e mostram quem leu.
- Cada condomínio isolado no banco; porteiro, síndico e morador veem coisas diferentes.
- Síndico profissional troca entre condomínios numa conta só.
- Cadastro em até 24h, moradores por planilha, suporte humano no WhatsApp, sem taxa de instalação.

COMO VENDER: fala da dor primeiro, mostra o alívio concreto, usa prova real (nunca invente depoimento/número).
Preço: não cite valor; conduza para uma conversa/demonstração. Objeções se respondem com empatia + um fato real + um
próximo passo pequeno (uma demonstração de 15 min, um teste num condomínio)."""


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _slug(t):
    return (re.sub(r"[^a-z0-9]+", "-", _sa(t)).strip("-") or "vendas")[:40]


# ---------------------------------------------------------------- entender o pedido
ABORDAGEM = re.compile(r"\b(?:abord(?:o|ar|agem)|prospec(?:to|tar|[cç][aã]o)|primeiro contato|mensagem de venda|"
                       r"mensagem de prospec|cold|script de venda|como (?:eu )?(?:falo|chego) (?:com|no))\b", re.I)
QUALIFICAR = re.compile(r"\b(?:qualifica(?:r)?|qualifica[cç][aã]o|esse lead presta|vale a pena esse|"
                        r"esse (?:cliente|lead) (?:[eé] bom|presta)|perguntas? (?:pro|para o) lead)\b", re.I)
OBJECAO = re.compile(r"\b(?:obje[cç][aã]o|quebra(?:r)? a obje|t[aá] caro|[eé] caro|j[aá] tenho (?:sistema|um)|"
                     r"vou pensar|n[aã]o tenho (?:tempo|verba|dinheiro)|o que (?:eu )?respondo|como respondo|rebate)\b", re.I)
ARGUMENTOS = re.compile(r"\b(?:argumentos?|por que (?:comprar|escolher|contratar)|pontos? forte|benef[ií]cios?|"
                        r"vantagens?|me ajuda a (?:vender|convencer)|como conven[cç])\b", re.I)
IDEIAS = re.compile(r"\b(?:ideias?|como (?:eu )?(?:consigo|acho|arrumo) (?:mais )?clientes?|onde (?:acho|encontro) cliente|"
                    r"como prospectar|dicas de venda|estrat[eé]gia de venda)\b", re.I)
# precisa falar de venda/cliente/lead/Porthon pra o módulo agir (evita pegar frase solta de "ideia").
# Sem \b no fim: "objec"/"prospec"/"aborda" são radicais (pegam objeção, prospecção, abordar).
CONTEXTO = re.compile(r"\b(?:vend[ae]|vender|cliente|clientes|lead|leads|prospec|porthon|s[ií]ndico|condom[ií]nio|"
                      r"administradora|objec|aborda)", re.I)
# Objeção inequívoca: dispensa a palavra de contexto ("o cara falou que tá caro, o que respondo?").
OBJECAO_FORTE = re.compile(r"\b(?:obje[cç][aã]o|quebra(?:r)? a obje|j[aá] tenho (?:sistema|um)|"
                           r"o que (?:eu )?respondo|como (?:eu )?respondo|rebate|rebater)\b", re.I)
ALVO = re.compile(r"\b(?:pra|para|com|no|na|de|do|da)\s+(?:um |uma |o |a )?"
                  r"(s[ií]ndico\w*|administradora\w*|condom[ií]nio\w*|zelador\w*|cliente\w*|lead\w*)\b", re.I)


def _alvo(texto):
    m = ALVO.search(texto)
    return (m.group(1) if m else "").strip()


# Mexer no que ele acabou de gerar (pedido dele 24/10: "tem que dar pra manipular, não ficar só o que ele escolheu"):
# logo depois de uma mensagem/objeção, "deixa mais curta", "mais formal", "tira o emoji", "troca o nome pra Carlos"
# reescreve AQUELE texto em vez de gerar outro do zero.
_ULTIMO = {"modo": None, "alvo": "", "texto": "", "quando": 0.0}
RECENTE = 900
AJUSTE = re.compile(r"\b(?:deix[ae]|fa[zc]a?|mud[ae]|troc[ae]|tir[ae]|coloc[ae]|bot[ae]|p[oõ]e|reescrev[ae]|ajust[ae]|"
                    r"encurt[ae]|aument[ae]|diminu[ia]|acrescent[ae]|adicion[ae]|corrig[ea]|refaz|refa[cç]a)\b.{0,40}?"
                    r"\b(?:mais|menos|curt[ao]|long[ao]|formal|informal|simples|direto|direta|emojis?|nome|frase|"
                    r"mensagem|texto|tom|isso|ela|ele|pergunta|final|come[cç]o|in[ií]cio|educad[ao]|agressiv[ao]|"
                    r"amig[aá]vel|s[eé]ri[ao])\b", re.I)
NAO_E_TEXTO = re.compile(r"\b(?:volume|som|m[uú]sica|brilho|tela|luz|janela|aba|microfone|mic|alto|baixo)\b", re.I)


def entender(texto):
    t = texto or ""
    if (_ULTIMO["texto"] and time.time() - _ULTIMO["quando"] < RECENTE and AJUSTE.search(t)
            and not NAO_E_TEXTO.search(t)):
        return {"modo": "ajustar", "texto": t}
    tem_ctx = bool(CONTEXTO.search(t))
    # Objeção primeiro: a inequívoca age mesmo sem palavra de contexto.
    if OBJECAO.search(t) and (tem_ctx or OBJECAO_FORTE.search(t)):
        return {"modo": "objecao", "alvo": _alvo(t), "texto": t}
    if not tem_ctx:
        return None
    if QUALIFICAR.search(t):
        return {"modo": "qualificar", "alvo": _alvo(t), "texto": t}
    if ABORDAGEM.search(t):
        return {"modo": "abordagem", "alvo": _alvo(t) or "síndico", "texto": t}
    if ARGUMENTOS.search(t):
        return {"modo": "argumentos", "alvo": _alvo(t), "texto": t}
    if IDEIAS.search(t):
        return {"modo": "ideias", "alvo": _alvo(t), "texto": t}
    return None


# ---------------------------------------------------------------- gerar (IA)
PROMPTS = {
    "abordagem": ("Escreva uma mensagem curta de primeiro contato (prospecção) para {alvo}, no tom de quem ajuda, não de "
                  "quem empurra. Comece por uma dor real da portaria, apresente o Porthon em uma frase e termine "
                  "convidando para uma demonstração rápida. Até 5 frases, pronta para mandar no WhatsApp. Só a mensagem."),
    "qualificar": ("Liste as perguntas certas para qualificar este lead ({alvo}) e dizer se vale a pena investir tempo. "
                   "Para cada pergunta, diga em uma linha o que a resposta revela. Pedido dele: \"{texto}\". "
                   "Responda em tópicos curtos."),
    "objecao": ("O cliente levantou esta objeção: \"{texto}\". Escreva como responder: uma linha de empatia, um fato real "
                "do Porthon que endereça a objeção, e um próximo passo pequeno. Tom humano, sem ser defensivo. "
                "Dê também uma versão de UMA frase para falar na hora."),
    "argumentos": ("Liste os argumentos mais fortes para vender o Porthon{para_alvo}, do jeito que convence um síndico. "
                   "Cada argumento: o ponto forte + a dor que ele mata. Tópicos curtos, sem exagero."),
    "ideias": ("Dê ideias práticas de prospecção para o Rafael conseguir mais clientes para o Porthon{para_alvo}: onde "
               "encontrar síndicos e administradoras, como abordar e o que oferecer primeiro. Tópicos acionáveis, nada genérico."),
}


def _gerar(p):
    modo, alvo, texto = p["modo"], p.get("alvo") or "", p.get("texto") or ""
    pedido = PROMPTS[modo].format(alvo=alvo or "um síndico", texto=texto,
                                  para_alvo=(f" para {alvo}" if alvo else ""))
    return asyncio.run(cerebro.completar(
        [{"role": "system", "content": VENDAS}, {"role": "user", "content": pedido}],
        temperatura=0.6, max_tokens=600, dificil=True)).strip()


def _salvar(modo, alvo, texto):
    PASTA.mkdir(parents=True, exist_ok=True)
    arq = PASTA / f"{date.today().isoformat()}-{modo}-{_slug(alvo or modo)}.txt"
    arq.write_text(texto, encoding="utf-8")
    return arq


def _copiar(texto):
    try:
        import controle_pc
        controle_pc.area_de_transferencia("copiar", texto)
        return True
    except Exception:
        return False


FALA = {
    "abordagem": "Escrevi a mensagem de prospecção, chefe.",
    "qualificar": "Aqui vão as perguntas pra qualificar esse lead, chefe.",
    "objecao": "Isso aqui responde a objeção, chefe.",
    "argumentos": "Separei os melhores argumentos, chefe.",
    "ideias": "Tenho umas ideias de prospecção pra você, chefe.",
}
TITULO = {"abordagem": "Prospecção", "qualificar": "Qualificar lead", "objecao": "Quebra de objeção",
          "argumentos": "Argumentos de venda", "ideias": "Ideias de prospecção"}


def _ajustar(instrucao):
    pedido = (f"Este é o texto que você escreveu:\n\"\"\"\n{_ULTIMO['texto']}\n\"\"\"\n\nO Rafael pediu esta mudança: "
              f"\"{instrucao}\". Reescreva aplicando EXATAMENTE isso — a mudança tem que dar pra notar de cara — e mantendo o resto do conteúdo. "
              "Responda só com o texto novo.")
    return asyncio.run(cerebro.completar(
        [{"role": "system", "content": VENDAS}, {"role": "user", "content": pedido}],
        temperatura=0.5, max_tokens=600, dificil=True)).strip().strip('"')


def executar(p):
    if p["modo"] == "ajustar":
        try:
            texto = _ajustar(p.get("texto") or "")
        except Exception:
            texto = ""
        if not texto:
            return "Não consegui mexer no texto agora, chefe. Tenta de novo?", []
        p = {"modo": _ULTIMO["modo"], "alvo": _ULTIMO["alvo"]}
        fala_ajuste = "Ajustei do jeito que você pediu, chefe."
    else:
        fala_ajuste = None
        try:
            texto = _gerar(p)
        except Exception:
            return "Não consegui montar agora, chefe. Tenta de novo?", []
    if not texto:
        return "Não consegui montar agora, chefe. Tenta de novo?", []
    _ULTIMO.update(modo=p["modo"], alvo=p.get("alvo") or "", texto=texto, quando=time.time())
    alvo = p.get("alvo") or ""
    arq = _salvar(p["modo"], alvo, texto)
    copiou = _copiar(texto)

    fala = fala_ajuste or FALA[p["modo"]]
    if p["modo"] == "abordagem" and copiou:
        fala += " Já copiei; se quiser, é só mandar no WhatsApp."
    elif copiou:
        fala += " Copiei pra você."
    cartao = {"titulo": f"{TITULO[p['modo']]}" + (f" · {alvo}" if alvo else ""),
              "linhas": [l for l in texto.split("\n") if l.strip()][:14],
              "copiar": texto}
    return fala, [cartao]
