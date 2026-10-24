"""Marketing do Porthon por voz: o Jarvis cria o post (arte + legenda + hashtags) no padrão da marca e deixa pronto.

Pedido dele (23/10/2026): "quero que o Jarvis crie no Canva as postagens do Porthon de forma inteligente e dentro do
padrão, e poste; que ele seja meu assistente de vendas, prospecção e ideias".

Como funciona (o que SEMPRE funciona, com a chave de IA que ele já tem — Groq/Gemini):
  1. Ele fala "cria um post pro Porthon sobre encomendas" / "faz uma arte sobre LGPD" / "monta a pauta da semana".
  2. O cérebro escreve, na VOZ DO PORTHON (ver IDENTIDADE abaixo): o gancho da arte, a linha de apoio, a legenda
     pronta pro Instagram e as hashtags. Nada de número inventado, nada de preço, nada de cara de robô.
  3. Salva em conteudo/porthon/AAAA-MM-DD-assunto.(json|txt), mostra o cartão no HUD, copia a legenda pra área de
     transferência e abre o Canva no navegador pra ele montar a arte e aprovar.

Canva automático (opcional, opt-in): se o Canva estiver conectado (Configurações → Conectores) e ele ligar
"canva_autofill_automatico" no config com o id do brand template, o Jarvis usa o Autofill do Canva (pelo MCP
oficial) pra já preencher a arte e devolver o link de edição. Autofill/kit de marca pedem Canva Pro; sem isso, cai no
caminho manual acima (abrir o Canva com a legenda pronta), que é o padrão. Detalhes na função _canva_autofill.

NÃO posta sozinho no Instagram: publicação automática exige conta Business + app aprovado pela Meta. O Jarvis deixa
tudo pronto (arte + legenda copiada) pra ele publicar com um toque — decisão de produto: aprovação humana antes de ir ao ar.
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
PASTA = RAIZ / "conteudo" / "porthon"

# ---------------------------------------------------------------- a identidade da marca (o "padrão")
# É isto que mantém todo post com a mesma cara. Mexer aqui muda o tom de tudo que o Jarvis gera.
IDENTIDADE = """Você é o social media do PORTHON, um sistema de portaria e gestão para condomínios.

QUEM OUVE: síndicos (profissionais e moradores), administradoras de condomínio e porteiros. Gente ocupada, não técnica.
A MARCA: resolve a bagunça da portaria — encomendas, visitantes, ocorrências, reservas, avisos, veículos. Tudo no
celular do porteiro, roda no navegador, sem instalar aplicativo. Cada condomínio isolado, cada papel vê o que precisa.
O TOM: claro, humano e direto, como quem explica pra um amigo síndico. Zero jargão de tecnologia, zero "revolucione",
zero cara de robô. Fala da DOR real primeiro (o "cadê minha encomenda?", o grupo de WhatsApp que ninguém lê), e só
então mostra o alívio. Pode ter um toque de bom humor leve.
REGRAS DURAS: nunca invente número, estatística, depoimento ou preço. Nunca prometa o que não foi dito. Português do
Brasil. Sem emoji exagerado (no máximo 1 ou 2 na legenda, se combinar). Sem hashtag genérica demais."""

# Pilares de conteúdo: o Jarvis rodízia entre eles quando ele não diz o tema, pra não repetir assunto.
PILARES = [
    "controle de encomendas na portaria",
    "livro de ocorrências digital",
    "controle de visitantes e a LGPD no condomínio",
    "reserva de espaços sem grupo de WhatsApp",
    "avisos que chegam a todos os moradores",
    "controle de acesso de veículos",
    "o dia a dia do síndico profissional com vários condomínios",
    "portaria no celular, sem papel",
]

# Paleta e fontes da marca, pra quando ele for montar no Canva (e pro prompt saber a vibe).
PALETA = {"fundo": "#0b0f0f", "cartao": "#1a2020", "destaque": "#34d399", "texto": "#ffffff", "apoio": "#a1a1aa"}


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _slug(t):
    s = re.sub(r"[^a-z0-9]+", "-", _sa(t)).strip("-")
    return (s or "post")[:40]


# ---------------------------------------------------------------- entender o pedido
POST = re.compile(
    r"\b(?:cria?r?|faz(?:er)?|monta?r?|gera?r?|escreve[r]?|prepara?r?|bola?r?)\b.{0,30}?"
    r"\b(?:post(?:agem)?|posts|arte|publica[cç][aã]o|conte[uú]do|story|storys|stories|legenda|card)\b", re.I)
PAUTA = re.compile(r"\b(?:pauta|calend[aá]rio|agenda|planejamento|cronograma)\b.{0,20}?"
                   r"(?:de\s+)?(?:conte[uú]do|posts?|semana|m[eê]s)|\b(?:ideias?|sugest[oõ]es)\s+de\s+posts?\b", re.I)
IDEIA = re.compile(r"\b(?:ideia|ideias|sugest[aã]o|sugest[oõ]es|o que (?:eu )?posto|sobre o que (?:eu )?posto)\b", re.I)
DO_PORTHON = re.compile(r"\bporthon\b", re.I)
SOBRE = re.compile(r"\b(?:sobre|a respeito de|falando de|de|do|da|pra falar de|tema|assunto)\s+(?P<tema>.+?)[.!?]*$", re.I)
# "pro insta", "pro porthon" — ruído a tirar do tema
RUIDO = re.compile(r"\b(?:pr[oa]|para|no|na|do|d[oa])\s+(?:insta(?:gram)?|porthon|feed|story|post|instagram)\b", re.I)


def _tema(texto):
    t = RUIDO.sub(" ", texto)
    m = SOBRE.search(t)
    tema = (m.group("tema").strip() if m else "")
    tema = re.sub(r"^(?:o|a|os|as)\s+", "", tema, flags=re.I).strip()
    return tema if len(tema) >= 3 else ""


QUANDO = re.compile(r"\b(?:melhor(?:es)?\s+(?:hor[aá]rios?|dias?|hora|dia)|quando\s+(?:eu\s+)?post|que\s+(?:dia|hora)\s+"
                    r"(?:eu\s+)?post|hor[aá]rio\s+(?:bom|certo|ideal)\s+(?:pra|para)\s+post)\b", re.I)
DICAS = re.compile(r"\b(?:dicas?|estrat[eé]gia|como\s+(?:melhor|crescer|bomb|divulg|vender\s+mais))\b.{0,25}?"
                   r"\b(?:marketing|instagram|insta|conte[uú]do|post|redes?\s+sociais|porthon)\b|"
                   r"\bmarketing\b.{0,15}?\b(?:dicas?|estrat[eé]gia)\b", re.I)


PLANO = re.compile(r"\b(?:monta|montar|faz(?:er)?|cria|criar|me\s+(?:d[aá]|faz)|quero)\b.{0,20}?\bplano\b.{0,20}?"
                   r"\b(?:de\s+)?(?:marketing|conte[uú]do|posts?|divulga|insta)\b|\bplano\s+de\s+marketing\b", re.I)


# ---------------------------------------------------------------- mexer no que ele já gerou (pedido dele, 24/10)
# "Ele colocou 5 posts na semana, eu pedi pra ser só um e ele não conseguiu; tem que dar pra manipular, não ficar fixo
# no que ele escolheu." Então: o plano, a pauta e o último post ficam guardados (…-atual.json) e qualquer pedido de
# mudança ("deixa só um post", "tira o de quinta", "muda o de terça pra 20h", "troca o título") mexe NELES, em vez de
# gerar tudo de novo. Também dá pra editar à mão em Configurações → Marketing.
PLANO_ATUAL = PASTA / "plano-atual.json"
PAUTA_ATUAL = PASTA / "pauta-atual.json"
POST_ATUAL = PASTA / "post-atual.json"
_FOCO = {"tipo": None, "quando": 0.0}  # o último que ele gerou/mexeu: "deixa só um" logo depois vale pra ele
RECENTE = 900  # segundos

EDITA = re.compile(r"\b(?:mud[aeo]r?|troc[aeo]r?|alter[aeo]r?|deix[aeo]r?|bot[aeo]r?|coloc[aeo]r?|p[oõ]e|por|"
                   r"pass[aeo]r?|tir[aeo]r?|remov[aeo]r?|exclu[ia]r?|adicion[aeo]r?|acrescent[aeo]r?|aument[aeo]r?|"
                   r"diminu[aio]r?|reduz(?:ir)?|ajust[aeo]r?|corrig[ei]r?|mov[aeo]r?|joga|empurra|s[oó]|apenas|"
                   r"somente|em\s+vez|no\s+lugar|menos|reescrev[ae]r?|encurt[ae]r?|quero|prefiro)\b", re.I)
GERA_NOVO = re.compile(r"\b(?:monta|montar|faz|fazer|fa[cç]a|cria|criar|gera|gerar|refaz|refazer|refa[cç]a)\b.{0,15}?"
                       r"\b(?:(?:um|uma|outro|outra|novo|nova|o|a)\s+)?(?:novo\s+|nova\s+)?(?:plano|pauta)\b", re.I)
SO_PLANO = re.compile(r"\bplano\b", re.I)
SO_PAUTA = re.compile(r"\bpauta\b", re.I)
NAO_E_PLANO = re.compile(r"\b(?:segundo|primeiro)\s+plano\b|\bplano\s+de\s+(?:fundo|sa[uú]de|dados|internet|celular|"
                         r"aula|estudos?|treino)\b", re.I)
DO_PLANO = re.compile(r"\b(?:posts?|postage(?:m|ns)|postar|publica[cç](?:[aã]o|[oõ]es)|segunda|ter[cç]a|quarta|quinta|"
                      r"sexta|s[aá]bado|domingo|hor[aá]rios?|temas?|ganchos?|formatos?|reels?|stories)\b|"
                      r"\b\d{1,2}\s*(?:h|horas)\b|\bs[oó]\s+(?:um|uma|dois|duas|tr[eê]s|\d)\b", re.I)
CAMPO_POST = re.compile(r"\b(?:t[ií]tulo|gancho|subt[ií]tulo|apoio|legenda|cta|chamada|hashtags?|texto\s+do\s+post)\b", re.I)
DESSE_POST = re.compile(r"\b(?:ess[ea]|d[oa]|n[oa]|o|a)\s+(?:post|legenda|arte|ideia)\b", re.I)
APAGAR_PLANO = re.compile(r"\b(?:apag[ae]r?|exclu[ia]r?|cancel[ae]r?|remov[ae]r?|delet[ae]r?|limp[ae]r?|desfaz(?:er)?|"
                          r"jog[ae]\s+fora|esquece)\b.{0,20}?\b(?:o\s+|esse\s+|este\s+|meu\s+)?plano\b(?!\s+de\s+(?:fundo|sa[uú]de))|"
                          r"\b(?:apag[ae]r?|cancel[ae]r?|tir[ae]r?|remov[ae]r?|deslig[ae]r?)\b.{0,15}?\blembretes?\s+d[oe]s?\s+"
                          r"(?:plano|marketing|posts?|postar)\b", re.I)
VER_PLANO = re.compile(r"\b(?:mostra|me\s+mostra|qual\s+[eé]|como\s+(?:t[aá]|est[aá]|ficou)|l[eê]|me\s+fala|abre|v[eê])\b"
                       r".{0,12}?\b(?:o\s+|meu\s+)?plano\s+(?:de\s+marketing|de\s+posts?|do\s+porthon|atual)\b", re.I)
NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7}
QTD = re.compile(r"\b(\d{1,2}|um|uma|dois|duas|tr[eê]s|quatro|cinco|seis|sete)\s+(?:posts?|postage(?:m|ns)|"
                 r"publica[cç](?:[aã]o|[oõ]es)|reels?|vez(?:es)?|dias?)\b|\b(?:s[oó]|apenas|somente)\s+(\d{1,2}|um|uma|"
                 r"dois|duas|tr[eê]s|quatro|cinco)\b", re.I)


SOMA = re.compile(r"\b(?:adicion|acrescent|inclu|soma|mais\s+(?:um|uma|dois|duas|\d)|(?:coloc|bot|p[oõ]e)\w*\s+mais)", re.I)


def _qtd(texto):
    """Quantos posts ele quer NO TOTAL ("deixa só um", "dois posts por semana"); "adiciona um post" não é total."""
    if SOMA.search(texto or ""):
        return None
    m = QTD.search(texto or "")
    if not m:
        return None
    v = _sa(m.group(1) or m.group(2))
    n = int(v) if v.isdigit() else NUMEROS.get(v)
    return n if n and 1 <= n <= 14 else None


def _ler(arq):
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _gravar(arq, dados):
    PASTA.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _focar(tipo):
    _FOCO.update(tipo=tipo, quando=time.time())


def _alvo_da_edicao(t):
    """Qual coisa já gerada ele quer mexer ("plano", "pauta", "post") ou None se não é pedido de mudança."""
    t = NAO_E_PLANO.sub(" ", t)
    if not EDITA.search(t) or GERA_NOVO.search(t):
        return None
    recente = time.time() - _FOCO["quando"] < RECENTE
    if not _FOCO["tipo"] and time.time() - (_ler(PLANO_ATUAL) or {}).get("atualizado", 0) < RECENTE:
        _FOCO.update(tipo="plano", quando=(_ler(PLANO_ATUAL) or {})["atualizado"])  # o servidor reiniciou no meio
        recente = True
    if SO_PLANO.search(t) and _ler(PLANO_ATUAL):
        return "plano"
    if SO_PAUTA.search(t) and _ler(PAUTA_ATUAL):
        return "pauta"
    if recente and _FOCO["tipo"] in ("plano", "pauta") and DO_PLANO.search(t):
        return _FOCO["tipo"]
    if CAMPO_POST.search(t) and _ler(POST_ATUAL) and (
            (recente and _FOCO["tipo"] == "post") or DESSE_POST.search(t)):
        return "post"
    return None


def entender(texto):
    t = texto or ""
    if APAGAR_PLANO.search(NAO_E_PLANO.sub(" ", t)):
        return {"modo": "apagar_plano"}
    if VER_PLANO.search(t):
        return {"modo": "ver_plano"}
    alvo = _alvo_da_edicao(t)
    if alvo:
        return {"modo": "editar", "alvo": alvo, "texto": t}
    if SO_PLANO.search(NAO_E_PLANO.sub(" ", t)) and _qtd(t) and EDITA.search(t):
        return {"modo": "plano", "texto": t}  # "muda o plano pra dois posts" sem plano guardado = monta já com dois
    # Só age quando é claramente sobre conteúdo do Porthon, pra não colidir com o instagram.py ("abre o insta").
    if PLANO.search(t):
        return {"modo": "plano", "texto": t}
    if QUANDO.search(t):
        return {"modo": "quando"}
    if DICAS.search(t):
        return {"modo": "dicas"}
    if PAUTA.search(t) and (DO_PORTHON.search(t) or "conteudo" in _sa(t) or "pauta" in _sa(t)):
        return {"modo": "pauta"}
    if POST.search(t):
        return {"modo": "post", "tema": _tema(t)}
    if IDEIA.search(t) and DO_PORTHON.search(t):
        return {"modo": "pauta"}
    return None


# conhecimento de marketing (baked, boas práticas pro público do Porthon: síndicos/administradoras)
MELHORES_HORARIOS = {
    "fala": ("Pro público do Porthon, chefe — síndico e administradora, gente que olha o celular fora do horário comercial —, "
             "os melhores momentos no Instagram são: terça, quarta e quinta, por volta das 12h no almoço e das 19h às 21h à noite. "
             "Domingo à noite também pega bem, que é quando muita gente resolve a vida do condomínio. Segunda e sexta rendem menos."),
    "cartao": {"titulo": "Melhores horários pra postar", "destaque": "Ter/Qua/Qui · 12h e 19h-21h",
               "linhas": ["Melhores dias: terça, quarta e quinta", "Horários: 12h (almoço) e 19h às 21h (noite)",
                          "Domingo à noite também é bom", "Evitar: segunda de manhã e sexta à noite",
                          "Reels rendem mais alcance que foto estática"]},
}
DICAS_MARKETING = {
    "fala": ("Resumo da estratégia, chefe: poste de 3 a 5 vezes por semana, misturando dica útil pro síndico, bastidor e prova "
             "(depoimento, antes e depois). A primeira linha da legenda é o gancho, tem que fisgar. Use Reels mostrando a tela do "
             "sistema em ação. E sempre um convite no fim: chama no direct. Constância vale mais que perfeição."),
    "cartao": {"titulo": "Estratégia de marketing · Porthon", "destaque": "Constância + valor",
               "linhas": ["Poste 3 a 5x por semana, com constância", "Rodízio: dica útil, bastidor, prova social (depoimento)",
                          "Gancho forte na 1ª linha da legenda", "Reels mostrando o sistema em ação = mais alcance",
                          "Sempre um CTA no fim (chama no direct)", "Responda todo comentário e direct rápido"]},
}


# ---------------------------------------------------------------- gerar o conteúdo (IA que ele já tem)
PEDIDO_POST = """{identidade}

Crie UM post para o Instagram do Porthon sobre: {tema}.

Responda SÓ com um JSON, sem mais nada, neste formato exato:
{{
  "gancho": "o título da arte, curto e forte, no máximo 7 palavras — a dor ou a virada",
  "apoio": "uma linha de apoio para a arte, até 14 palavras",
  "legenda": "a legenda do post, 3 a 5 frases: começa pela dor, resolve, e termina com uma pergunta ou convite leve. Sem link.",
  "cta": "uma chamada curta para a ação, ex: 'Chama no direct pra conhecer o Porthon'",
  "hashtags": ["5 a 8 hashtags específicas de condomínio/síndico, sem # repetido e sem genérico demais"]
}}"""

PEDIDO_PAUTA = """{identidade}

Monte uma pauta de conteúdo com 7 posts para a semana do Instagram do Porthon, variando os temas entre estes pilares:
{pilares}.

Responda SÓ com um JSON, sem mais nada:
{{ "pauta": [ {{ "dia": "Segunda", "tema": "...", "gancho": "título da arte, curto" }}, ... 7 itens ... ] }}"""

PEDIDO_PLANO = """{identidade}

Monte um PLANO de marketing semanal pro Instagram do Porthon: {quantidade} na semana, nos MELHORES dias e horários
(terça, quarta e quinta por volta das 12h ou das 19h-21h; domingo à noite também rende), variando os pilares:
{pilares}. Misture formatos (Reels e Post).

O QUE O CHEFE PEDIU (manda mais que as regras acima — siga à risca dia, horário, quantidade e tema que ele disser):
"{pedido}"

Responda SÓ com um JSON, sem mais nada:
{{ "plano": [ {{ "dia": "Terça", "horario": "19h", "formato": "Reels", "tema": "...", "gancho": "título curto" }}, ... ] }}"""

PEDIDO_EDITAR = """{identidade}

Este é o {nome} atual do Instagram do Porthon, em JSON:
{atual}

O chefe pediu esta mudança: "{instrucao}"

Aplique EXATAMENTE o que ele pediu, e só isso — o resto fica igual, palavra por palavra. Se ele disser uma quantidade
de posts, deixe exatamente essa quantidade (fique com os mais fortes e variados). Se ele mudar dia, horário, formato,
tema, gancho, título, legenda ou CTA, troque só o que ele falou. Se trocar o TEMA de um post e ele não disser o
gancho, escreva um gancho novo que combine com o tema novo. Se ele pedir pra adicionar, crie o item completo. Dias por extenso (Segunda, Terça, Quarta, Quinta,
Sexta, Sábado, Domingo) e horário no jeito "19h" ou "19h30".

Responda SÓ com um JSON, sem mais nada: {{ "{chave}": {formato}, "resumo": "o que mudou, numa frase curta, falando com ele" }}"""

ORDEM_DIAS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


def _ordenar(itens):
    def chave(i):
        d = _sa(i.get("dia", "")).strip()
        return (ORDEM_DIAS.index(d) if d in ORDEM_DIAS else 9, _sa(i.get("horario", "")))
    return sorted(itens, key=chave)


def _gerar_plano(pedido=""):
    n = _qtd(pedido)
    quantidade = (f"EXATAMENTE {n} post" + ("s" if n > 1 else "")) if n else "4 a 5 posts"
    bruto = asyncio.run(cerebro.completar(
        [{"role": "user", "content": PEDIDO_PLANO.format(identidade=IDENTIDADE, pilares="; ".join(PILARES),
                                                         quantidade=quantidade, pedido=pedido or "(nada específico)")}],
        json_mode=True, temperatura=0.6, max_tokens=800, dificil=True))
    d = _json_da_ia(bruto) or {}
    plano = [p for p in (d.get("plano") or []) if isinstance(p, dict)][:14]
    return plano[:n] if n else plano[:6]  # a quantidade que ele falou é lei, mesmo se a IA errar a conta


def _editar_com_ia(nome, chave, atual, instrucao, formato):
    bruto = asyncio.run(cerebro.completar(
        [{"role": "user", "content": PEDIDO_EDITAR.format(
            identidade=IDENTIDADE, nome=nome, atual=json.dumps(atual, ensure_ascii=False, indent=1),
            instrucao=instrucao, chave=chave, formato=formato)}],
        json_mode=True, temperatura=0.2, max_tokens=900, dificil=True))
    d = _json_da_ia(bruto) or {}
    resumo = str(d.get("resumo") or "").strip()
    return d.get(chave), (resumo + ("" if resumo[-1:] in ".!?" else ".")) if resumo else ""


def _editar_lista_na_mao(itens, instrucao):
    """Se a IA falhar: o básico sem IA — quantidade ("deixa só um") e tirar um dia ("tira o de quinta")."""
    itens = list(itens)
    n = _qtd(instrucao)
    if n and len(itens) > n:
        return itens[:n], f"Deixei {n} post" + ("s" if n > 1 else "") + "."
    m = re.search(r"\b(?:tir|remov|exclu|apag)\w*\b.{0,15}?\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)\b",
                  instrucao, re.I)
    if m:
        dia = _sa(m.group(1))
        fica = [i for i in itens if _sa(i.get("dia", "")).strip() != dia]
        if len(fica) < len(itens):
            return fica, f"Tirei o de {m.group(1)}."
    return None, ""


def _json_da_ia(bruto):
    try:
        return json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def _gerar_post(tema):
    if not tema:
        tema = PILARES[int(time.time()) % len(PILARES)]  # rodízio quando ele não diz o tema
    bruto = asyncio.run(cerebro.completar(
        [{"role": "user", "content": PEDIDO_POST.format(identidade=IDENTIDADE, tema=tema)}],
        json_mode=True, temperatura=0.6, max_tokens=500, dificil=True))
    d = _json_da_ia(bruto) or {}
    return {
        "tema": tema,
        "gancho": str(d.get("gancho") or "").strip()[:80],
        "apoio": str(d.get("apoio") or "").strip()[:140],
        "legenda": str(d.get("legenda") or "").strip(),
        "cta": str(d.get("cta") or "").strip()[:120],
        "hashtags": [h.strip().lstrip("#") for h in (d.get("hashtags") or []) if h and h.strip()][:8],
    }


def _gerar_pauta():
    bruto = asyncio.run(cerebro.completar(
        [{"role": "user", "content": PEDIDO_PAUTA.format(identidade=IDENTIDADE, pilares="; ".join(PILARES))}],
        json_mode=True, temperatura=0.7, max_tokens=700, dificil=True))
    d = _json_da_ia(bruto) or {}
    return [p for p in (d.get("pauta") or []) if isinstance(p, dict)][:7]


def _legenda_completa(post):
    tags = " ".join("#" + h for h in post["hashtags"])
    partes = [post["legenda"]]
    if post["cta"]:
        partes.append(post["cta"])
    if tags:
        partes.append(tags)
    return "\n\n".join(p for p in partes if p)


def _salvar(nome, dados, texto):
    PASTA.mkdir(parents=True, exist_ok=True)
    base = PASTA / f"{date.today().isoformat()}-{nome}"
    base.with_suffix(".json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    base.with_suffix(".txt").write_text(texto, encoding="utf-8")
    return base.with_suffix(".txt")


# ---------------------------------------------------------------- Canva (opcional)
def _config(chave, padrao=None):
    try:
        return json.loads((RAIZ / "config.json").read_text(encoding="utf-8")).get(chave, padrao)
    except (OSError, ValueError):
        return padrao


def _canva_pode_criar():
    """True se o Canva está conectado e com permissão de escrita (tem as ferramentas de criar/editar)."""
    try:
        import conectores
        if "canva" not in conectores.nomes_ligados():
            return False
        nomes = [t["name"] for t in conectores._ferramentas_de("canva")]
        return "copy-design" in nomes and "perform-editing-operations" in nomes
    except Exception:
        return False


def _canva_fazer_arte(gancho, apoio, cta):
    """Copia o modelo PORTHON POSTS e preenche os textos de verdade. Devolve (edit_url, thumb_url) ou (None, motivo).

    Precisa do Canva conectado com permissão de ESCRITA (Configurações → Conectores → Canva). Testado 24/10: funciona.
    """
    import json
    import unicodedata
    modelo = _config("canva_modelo_id")
    if not modelo:
        return None, "sem modelo configurado"
    pagina = _config("canva_modelo_pagina", 2)
    dec = json.JSONDecoder()

    def sa(x):
        return "".join(c for c in unicodedata.normalize("NFD", (x or "").lower()) if unicodedata.category(c) != "Mn")

    async def fluxo():
        import conectores

        async def mcp(tool, args):
            return await conectores.chamar(conectores._id("canva", tool), args)

        r = await mcp("copy-design", {"design_id": modelo, "page_numbers": [pagina],
                                      "user_intent": "criar um post novo do Porthon a partir do modelo PORTHON POSTS"})
        if "disabled" in r or '"design"' not in r:
            return None, (r[:100] or "não consegui copiar o modelo")
        novo = dec.raw_decode(r.lstrip())[0]["design"]
        did = novo["id"]
        edit_url = (novo.get("urls") or {}).get("edit_url")
        t = await mcp("start-editing-transaction", {"design_id": did, "user_intent": "preencher os textos do post"})
        d = dec.raw_decode(t.lstrip())[0]
        tx = d["transaction"]["transaction_id"]
        ops = []
        for e in d.get("richtexts", []):
            txt = sa("".join(rg.get("text", "") for rg in e.get("regions", []))).strip()
            eid = e["element_id"]
            if "subtitulo" in txt:
                ops.append({"type": "replace_text", "element_id": eid, "text": apoio})
            elif "tulo" in txt and "subt" not in txt:
                ops.append({"type": "replace_text", "element_id": eid, "text": gancho})
            elif txt == "cta":
                ops.append({"type": "replace_text", "element_id": eid, "text": cta})
        if ops:
            await mcp("perform-editing-operations", {"transaction_id": tx, "operations": ops, "page_index": 1,
                                                     "pages": [], "user_intent": "preencher o post do Porthon"})
            await mcp("commit-editing-transaction", {"transaction_id": tx, "user_intent": "salvar o post"})
        else:
            await mcp("cancel-editing-transaction", {"transaction_id": tx, "user_intent": "nada a editar"})
        g = await mcp("get-design", {"design_id": did})
        thumb = (dec.raw_decode(g.lstrip())[0].get("design", {}).get("thumbnail") or {}).get("url")
        return edit_url, thumb

    try:
        return asyncio.run(fluxo())
    except Exception as e:
        return None, f"erro no Canva ({str(e)[:80]})"


def _abrir_canva(link_pronto=None):
    try:
        import navegadores
        navegadores.abrir(link_pronto or _config("canva_template_url") or "https://www.canva.com/create/instagram-posts/")
        return True
    except Exception:
        return False


def _copiar(texto):
    try:
        import controle_pc
        controle_pc.area_de_transferencia("copiar", texto)
        return True
    except Exception:
        return False


_PREFIXO_LEMBRETE = "Chefe, hoje é dia de postar no Porthon"
_DIAS_IDX = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}


def _agendar_lembretes_do_plano(plano):
    """Cria uma fala programada pra cada post do plano: no dia e horário, o Jarvis lembra com o tema pronto."""
    try:
        import falas_programadas as fp
    except Exception:
        return 0
    # tira os lembretes do plano anterior (pra não acumular)
    for f in fp.todas():
        if (f.get("texto") or "").startswith(_PREFIXO_LEMBRETE):
            fp.apagar(f["id"])

    def hhmm(h):
        m = re.search(r"(\d{1,2})(?:\s*[:h]\s*(\d{2}))?", h or "")  # "19h", "19h30", "19:30"
        return f"{int(m.group(1)):02d}:{m.group(2) or '00'}" if m else "19:00"

    n = 0
    for i in plano:
        dia = _DIAS_IDX.get(_sa(i.get("dia", "")).strip())
        if dia is None:
            continue
        texto = (f"{_PREFIXO_LEMBRETE}: {i.get('tema', '')}. O gancho é: {i.get('gancho', '')}. "
                 "Quer que eu prepare a ideia do post pra você?")
        try:
            fp.salvar({"hora": hhmm(i.get("horario")), "dias": [dia], "texto": texto, "ativa": True})
            n += 1
        except Exception:
            pass
    return n


# ---------------------------------------------------------------- o plano guardado (voz e Configurações → Marketing)
def _limpar_item(i):
    return {k: str(i.get(k) or "").strip()[:160] for k in ("dia", "horario", "formato", "tema", "gancho")}


def plano_atual():
    return (_ler(PLANO_ATUAL) or {}).get("plano") or []


def salvar_plano(plano):
    """Grava o plano como ELE quer (vindo da voz ou da tela) e refaz os lembretes pra bater com ele."""
    plano = _ordenar([_limpar_item(i) for i in plano if isinstance(i, dict) and (i.get("tema") or i.get("gancho"))])
    if not plano:
        apagar_plano()
        return []
    _gravar(PLANO_ATUAL, {"plano": plano, "atualizado": time.time()})
    linhas = [_linha_do_plano(i) for i in plano]
    _salvar("plano-marketing", {"plano": plano}, "PLANO DE MARKETING — PORTHON\n\n" + "\n".join(linhas))
    _agendar_lembretes_do_plano(plano)
    return plano


def apagar_plano():
    """Tira o plano E os lembretes dele (antes o "apaga esse plano" deixava os 5 lembretes tocando)."""
    n = 0
    try:
        import falas_programadas as fp
        for f in fp.todas():
            if (f.get("texto") or "").startswith(_PREFIXO_LEMBRETE):
                fp.apagar(f["id"])
                n += 1
    except Exception:
        pass
    try:
        PLANO_ATUAL.unlink()
    except OSError:
        pass
    return n


def _linha_do_plano(i):
    return f"{i.get('dia','')} {i.get('horario','')} · {i.get('formato') or 'Post'} — {i.get('tema','')}: \"{i.get('gancho','')}\""


COMO_MUDAR = ("Pra mudar é só falar: \"deixa só um post\", \"tira o de quinta\", \"passa o de terça pra 20h\", "
              "\"troca o tema de quarta pra reservas\" — ou editar em Configurações → Marketing.")


def _cartao_do_plano(plano, destaque=None):
    n = len(plano)
    return {"titulo": "Plano de marketing · Porthon", "destaque": destaque or f"{n} post{'s' if n != 1 else ''} na semana",
            "linhas": [_linha_do_plano(i) for i in plano] + ["", "Lembretes marcados — no dia eu te aviso com o tema pronto.",
                                                              COMO_MUDAR]}


def _plural(n):
    return f"{n} post{'s' if n != 1 else ''}"


TIRA = re.compile(r"\b(?:tir|remov|exclu|apag|cancel|corta|elimin|s[oó]\b|apenas|somente|menos|reduz|diminu)", re.I)


def _devolver_sumidos(atual, novo):
    """Ele não pediu pra tirar nada: o post que sumiu na resposta da IA volta (casando por dia+horário ou tema)."""
    novo = [i for i in novo if isinstance(i, dict)]
    tem = {(_sa(i.get("dia", "")), _sa(i.get("horario", ""))) for i in novo} | {_sa(i.get("tema", "")) for i in novo}
    sumiram = [i for i in atual if (_sa(i.get("dia", "")), _sa(i.get("horario", ""))) not in tem
               and _sa(i.get("tema", "")) not in tem]
    return novo + sumiram if len(novo) < len(atual) else novo


def _editar_plano(instrucao):
    atual = plano_atual()
    if not atual:
        return executar({"modo": "plano", "texto": instrucao})
    novo, resumo = None, ""
    try:
        novo, resumo = _editar_com_ia("plano de marketing semanal", "plano", atual, instrucao,
                                      '[ { "dia": "...", "horario": "...", "formato": "...", "tema": "...", "gancho": "..." } ]')
    except Exception:
        pass
    if not isinstance(novo, list) or (not novo and not re.search(r"\b(?:tud|todos)\b", instrucao, re.I)):
        novo, resumo = _editar_lista_na_mao(atual, instrucao)
    if novo is None:
        return ("Não entendi o que mudar no plano, chefe. Fala tipo \"deixa só um post\", \"tira o de quinta\" ou "
                "\"passa o de terça pra 20h\". Ou edita em Configurações → Marketing.", [_cartao_do_plano(atual)])
    n = _qtd(instrucao)
    if n and len(novo) > n:
        novo = novo[:n]  # a quantidade que ele falou é lei
    if not n and not TIRA.search(instrucao):
        novo = _devolver_sumidos(atual, novo)  # a IA às vezes "esquece" um post ao mexer em outro
    plano = salvar_plano(novo)
    _focar("plano")
    if not plano:
        return "Pronto, chefe: tirei todos os posts, então apaguei o plano e os lembretes dele.", []
    fala = (f"Feito, chefe. {resumo + ' ' if resumo else ''}Agora o plano tem {_plural(len(plano))}: "
            + " ".join(f"{i['dia']} às {i['horario']}, {i['tema']}." for i in plano[:3])
            + " Já acertei os lembretes.")
    return fala, [_cartao_do_plano(plano)]


def _editar_pauta(instrucao):
    atual = (_ler(PAUTA_ATUAL) or {}).get("pauta") or []
    novo, resumo = None, ""
    try:
        novo, resumo = _editar_com_ia("pauta da semana", "pauta", atual, instrucao,
                                      '[ { "dia": "...", "tema": "...", "gancho": "..." } ]')
    except Exception:
        pass
    if not isinstance(novo, list) or not novo:
        novo, resumo = _editar_lista_na_mao(atual, instrucao)
    if not novo:
        return "Não entendi o que mudar na pauta, chefe. Fala tipo \"deixa só três\" ou \"tira a de sexta\".", []
    n = _qtd(instrucao)
    pauta = _ordenar([i for i in novo if isinstance(i, dict)])[:n or 14]
    _gravar(PAUTA_ATUAL, {"pauta": pauta})
    _focar("pauta")
    return (f"Feito, chefe. {resumo + ' ' if resumo else ''}A pauta ficou com {_plural(len(pauta))}.",
            [{"titulo": "Pauta da semana · Porthon", "destaque": _plural(len(pauta)),
              "linhas": [f"{i.get('dia','')} — {i.get('gancho','')}" for i in pauta]}])


def _editar_post(instrucao):
    atual = _ler(POST_ATUAL)
    novo, resumo = None, ""
    try:
        novo, resumo = _editar_com_ia("post (ideia pra arte + legenda)", "post", atual, instrucao,
                                      '{ "tema": "...", "gancho": "...", "apoio": "...", "legenda": "...", "cta": "...", '
                                      '"hashtags": ["..."] }')
    except Exception:
        pass
    if not isinstance(novo, dict):
        return "Não consegui mexer no post agora, chefe. Tenta de novo?", []
    post = {**atual, **{k: v for k, v in novo.items() if k in atual}}
    post["hashtags"] = [str(h).strip().lstrip("#") for h in (post.get("hashtags") or []) if str(h).strip()][:10]
    return _mostrar_post(post, f"Feito, chefe. {resumo or 'Mudei o post.'}", abrir_canva=False)


# ---------------------------------------------------------------- executar
def executar(p):
    if p["modo"] == "quando":
        return MELHORES_HORARIOS["fala"], [MELHORES_HORARIOS["cartao"]]
    if p["modo"] == "dicas":
        return DICAS_MARKETING["fala"], [DICAS_MARKETING["cartao"]]
    if p["modo"] == "apagar_plano":
        tinha = bool(plano_atual())
        n = apagar_plano()
        _FOCO.update(tipo=None, quando=0.0)
        if not tinha and not n:
            return "Não tem plano de marketing marcado, chefe.", []
        return f"Apaguei o plano de marketing, chefe" + (f", e os {n} lembretes dele." if n > 1 else
                                                          ", e o lembrete dele." if n else "."), []
    if p["modo"] == "ver_plano":
        plano = plano_atual()
        if not plano:
            return "Não tem plano de marketing agora, chefe. Quer que eu monte um? Pode dizer quantos posts.", []
        _focar("plano")
        return f"O plano tem {_plural(len(plano))}, chefe. Tá aí na tela; é só falar o que mudar.", [_cartao_do_plano(plano)]
    if p["modo"] == "editar":
        return {"plano": _editar_plano, "pauta": _editar_pauta, "post": _editar_post}[p["alvo"]](p.get("texto") or "")
    if p["modo"] == "plano":
        plano = _gerar_plano(p.get("texto") or "")
        if not plano:
            return "Não consegui montar o plano agora, chefe. Tenta de novo?", []
        plano = salvar_plano(plano)  # guarda (pra poder mexer depois) e cria os lembretes nos dias/horários
        _focar("plano")
        fala = (f"Montei o plano de marketing da semana, chefe: {_plural(len(plano))}. "
                + " ".join(f"{i.get('dia','')} às {i.get('horario','')}, {i.get('tema','')}." for i in plano[:3])
                + " Deixei os lembretes marcados. Se quiser mudar alguma coisa, é só falar.")
        return fala, [_cartao_do_plano(plano)]
    if p["modo"] == "pauta":
        pauta = _gerar_pauta()
        if not pauta:
            return "Não consegui montar a pauta agora, chefe. Tenta de novo?", []
        texto = "PAUTA DA SEMANA — PORTHON\n\n" + "\n".join(
            f"{i.get('dia','')}: {i.get('tema','')} — \"{i.get('gancho','')}\"" for i in pauta)
        _salvar("pauta-semana", {"pauta": pauta}, texto)
        _gravar(PAUTA_ATUAL, {"pauta": pauta})
        _focar("pauta")
        fala = "Montei a pauta da semana, chefe. " + " ".join(
            f"{i.get('dia','')}, {i.get('tema','')}." for i in pauta[:3]) + " O resto tá no cartão; dá pra mudar o que quiser."
        cartao = {"titulo": "Pauta da semana · Porthon", "destaque": f"{len(pauta)} posts",
                  "linhas": [f"{i.get('dia','')} — {i.get('gancho','')}" for i in pauta]}
        return fala, [cartao]

    post = _gerar_post(p.get("tema"))
    if not post["gancho"] and not post["legenda"]:
        return "Não consegui escrever o post agora, chefe. Tenta de novo?", []
    return _mostrar_post(post, None, abrir_canva=True)


def _mostrar_post(post, fala, abrir_canva):
    legenda = _legenda_completa(post)
    _salvar(_slug(post["tema"]), post, f"{post['gancho']}\n{post['apoio']}\n\n{legenda}")
    _gravar(POST_ATUAL, post)
    _focar("post")
    copiou = _copiar(legenda)

    # Decisão dele (24/10): o Jarvis NÃO monta a arte no Canva (ficava desconfigurado). Ele dá a IDEIA formatada aqui no
    # HUD, copia a legenda e abre o modelo LIMPO pra ELE montar a arte.
    if abrir_canva:
        _abrir_canva()  # abre o PORTHON POSTS (modelo limpo) pra ele fazer a arte
    modelo = _config("canva_template_nome") or "o Canva"
    linhas = [f"Título: {post['gancho']}"]
    if post["apoio"]:
        linhas.append(f"Subtítulo: {post['apoio']}")
    if post["cta"]:
        linhas.append(f"CTA: {post['cta']}")
    linhas.append("Legenda: " + post["legenda"])
    if post["hashtags"]:
        linhas.append(" ".join("#" + h for h in post["hashtags"]))
    linhas.append("Pra mudar: \"troca o título\", \"deixa a legenda mais curta\", \"muda o CTA pra…\".")
    if fala:
        fala += " A legenda nova já tá copiada." if copiou else ""
    else:
        fala = (f"Prontinho, chefe. Ideia do post sobre {post['tema']}: \"{post['gancho']}\". "
                f"Deixei tudo formatado aí na tela e abri o {modelo} pra você montar a arte"
                + (", e a legenda já tá copiada, é só colar." if copiou else "."))
    cartao = {"titulo": f"Ideia de post · {post['tema']}", "destaque": post["gancho"],
              "linhas": linhas, "copiar": legenda}
    return fala, [cartao]
