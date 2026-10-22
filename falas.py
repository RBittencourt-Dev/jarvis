"""Frases do Jarvis com variação (e um humorzinho), pra ele não falar sempre igual.

Tudo que sai pelas respostas prontas (responder_ja) passa por variar(): se a frase é uma das "de sempre"
("Pronto, chefe.", "Pausado.", "Tocando X."), troca por outra com o mesmo sentido, sem repetir a última.
As listas daqui também alimentam as esperas da tela, o "Pois não?" e as despedidas, e o servidor deixa o
áudio de todas pronto no startup (saem na hora, sem esperar a voz ser gerada).
Pra adicionar uma variação: é só pôr mais uma frase na lista certa.
"""
import random
import re

# chamar: "Jarvis" sozinho
CHAMADO = [
    "Pois não, chefe?", "Pode falar, chefe.", "Às ordens.", "Tô aqui, chefe.", "Diga, chefe.", "Na escuta.",
    "Opa, chefe. Manda.", "Fala comigo.", "Presente, chefe.", "Sim, senhor?", "Chamou? Tô na escuta.",
    "Pronto pra próxima, chefe.", "Em que posso ser útil hoje, senhor?",
]
# enquanto pensa / busca
ESPERAS = [
    "Deixa eu ver, chefe.", "Um instante.", "Já vejo isso.", "Só um momento, chefe.", "Hum, deixa eu pensar.",
    "Pera aí que eu acho.", "Consultando os meus circuitos.", "Já tô nisso, chefe.", "Um segundinho.",
    "Processando, com toda a elegância possível.", "Rodando isso aqui.", "Vasculhando, chefe.",
    "Deixa comigo.", "Só um tiquinho.", "Calibrando os neurônios de silício.",
]
DEMORANDO = [  # passou de 10 s
    "Tá demorando um pouco, chefe, mas já tô terminando.", "Quase lá, chefe. A internet hoje tá de má vontade.",
    "Ainda trabalhando nisso, chefe. Não desisti, prometo.", "Mais um pouquinho, chefe. Tá vindo.",
    "Segura aí, chefe. Coisa grande demora um pouco mais.",
]
MUSICA = [
    "Boa escolha, chefe.", "Essa é das boas.", "Ótimo pedido.", "Já vai, chefe.", "Gosto musical refinado, chefe.",
    "Solta o som!", "Agora sim, chefe.", "Aumenta que isso aí é bom.", "Pedido anotado, DJ.", "Saindo do forno.",
]
PAINEL = ["Deixa eu olhar o painel.", "Um instante, vou conferir.", "Abrindo os livros, chefe.",
          "Deixa eu espiar os números.", "Conferindo o painel, chefe."]
DE_NADA = ["Às ordens, chefe.", "Sempre, chefe.", "Disponha.", "Tamo junto, chefe.", "É pra isso que eu tô aqui.",
           "Imagina, chefe.", "Por nada. Meu salário é a sua satisfação. E energia elétrica.", "Precisando, só chamar.",
           "Valeu você, chefe."]
CANCELADO = ["Cancelado, chefe.", "Beleza, deixei quieto.", "Tudo bem, não mexi em nada.", "Ok, abortando missão.",
             "Cancelado. Fingimos que nada aconteceu."]
PRONTO = ["Pronto, chefe.", "Feito.", "Prontinho.", "Missão cumprida, chefe.", "Tá feito.", "Resolvido, chefe.",
          "Feito. Fácil demais.", "Pronto. Pode conferir."]

# frase de sempre → variações (inclui a própria). A chave é a frase exata, sem diferença de maiúscula.
TROCAS = {
    "pois não, chefe?": CHAMADO,
    "cancelado, chefe.": CANCELADO,
    "cancelado.": CANCELADO,
    "pronto, chefe.": PRONTO,
    "feito.": PRONTO,
    "pausado.": ["Pausado.", "Pausei.", "Silêncio na pista.", "Música em pausa, chefe.", "Dei uma pausa."],
    "continuando.": ["Continuando.", "Voltando o som.", "E o show continua.", "Play de novo, chefe."],
    "próxima.": ["Próxima.", "Pulando.", "Essa não colou, né? Próxima.", "Passando pra próxima.", "Trocando, chefe."],
    "voltando.": ["Voltando.", "Voltando uma.", "Rebobinando, chefe.", "De volta pra anterior."],
    "do começo.": ["Do começo.", "Do zero, chefe.", "Mais uma vez, desde o início."],
    "virando.": ["Virando.", "Girando a câmera.", "Olhando pra lá, chefe."],
    "beleza, chefe.": ["Beleza, chefe.", "Fechado.", "Combinado, chefe.", "Tranquilo."],
    "limpei o globo, chefe.": ["Limpei o globo, chefe.", "Globo zerado.", "Mapa limpo, chefe."],
    "fechei a visão da rua, chefe.": ["Fechei a visão da rua, chefe.", "Saindo da rua.", "Street View fechado."],
    "boa noite, chefe. descanse. estarei aqui quando precisar.": [
        "Boa noite, chefe. Descanse. Estarei aqui quando precisar.", "Boa noite, chefe. Vou ficar de olho em tudo.",
        "Bons sonhos, chefe. Eu cuido do turno da noite.", "Boa noite. Desligando as luzes metafóricas."],
    "bom intervalo, chefe. é só me chamar.": [
        "Bom intervalo, chefe. É só me chamar.", "Aproveita a pausa, chefe.", "Vai lá, chefe. Eu seguro as pontas.",
        "Intervalo merecido. Tô por aqui."],
    "desligando. até logo, chefe.": ["Desligando. Até logo, chefe.", "Indo pro stand-by. Até já, chefe.",
                                     "Modo econômico ativado. Até logo."],
    "até mais, chefe. fico de ouvido aqui.": [
        "Até mais, chefe. Fico de ouvido aqui.", "Falou, chefe. Tô por perto.", "Até, chefe. É só chamar.",
        "Saindo de cena. Mas continuo escutando, hein.", "Tchau, chefe. Vou fingir que descanso."],
}
# começos de frase com variação ("Tocando X." → "Solta o som: X.")
PADROES = [
    (re.compile(r"^Tocando (.+?)\.$"), ["Tocando {}.", "Solta o som: {}.", "Mandando ver: {}.", "Lá vai: {}.",
                                         "No ar: {}."]),
    (re.compile(r"^Abrindo (.+?)(?:, chefe)?\.$"), ["Abrindo {}.", "Abrindo {}, chefe.", "{} na tela, já já.",
                                                     "Deixa comigo: {}."]),
]
_ultima = {}


def escolher(lista, chave=None):
    """Uma frase da lista, sem repetir a última dita dessa mesma lista."""
    chave = chave or id(lista)
    opcoes = [f for f in lista if f != _ultima.get(chave)] or lista
    f = random.choice(opcoes)
    _ultima[chave] = f
    return f


def variar(texto):
    if not texto or not isinstance(texto, str):
        return texto
    limpo = texto.strip()
    trocas = TROCAS.get(limpo.lower())
    if trocas:
        return escolher(trocas, limpo.lower())
    for regra, modelos in PADROES:
        m = regra.match(limpo)
        if m:
            return escolher(modelos, regra.pattern).format(m.group(1))
    # o "chefe" no fim de toda frase cansa: às vezes vira "senhor" ou some
    if limpo.endswith(", chefe.") and random.random() < 0.35:
        return limpo[:-len(", chefe.")] + random.choice([", senhor.", "."])
    return texto


# Espera que COMBINA com o pedido (22/10: ele pedia "me mostra meu PC" e ouvia "Calibrando os neurônios de silício").
# (regra, frases): a primeira que bater vale. Frases None = papo/cumprimento: fica calado (só o som de pensar).
ESPERAS_POR_ASSUNTO = [
    (r"\b(?:tudo bem|tudo certo|e a[ií]|beleza|bom dia|boa tarde|boa noite|como vai|como (?:tu )?t[aá]s?\b(?! o| a)|"
     r"t[aá] a[ií]|oi|ol[aá]|valeu|obrigad)", None),
    (r"^(?:jarvis[ ,]*)?(?:abre|liga|inicia|entra)\b", ["Abrindo, chefe.", "Já abro.", "Um segundo, abrindo."]),
    (r"^(?:jarvis[ ,]*)?(?:fecha|minimiza|desliga|tira)\b", ["Já fecho, chefe.", "Fechando."]),
    (r"\b(?:pc|computador|processador|cpu|mem[oó]ria|ram|placa de v[ií]deo|gpu|ssd|disco|hd|pe[cç]as|hardware|setup|temperatura)\b",
     ["Lendo o seu hardware, chefe.", "Montando as peças do seu PC.", "Já te mostro o PC por dentro.", "Conferindo as peças."]),
    (r"not[ií]cia|manchete|o que (?:t[aá]|est[aá]) (?:rolando|acontecendo)",
     ["Puxando as notícias, chefe.", "Vendo o que tá rolando.", "Buscando as manchetes."]),
    (r"\b(?:toca|tocar|m[uú]sica|playlist|spotify|ouvir|som)\b", ["Já vai, chefe.", "Escolhendo o som.", "Preparando a música."]),
    (r"whats|\bzap\b|mensagem|manda pr[ao]|fala pr[ao]", ["Preparando a mensagem.", "Já vejo isso no WhatsApp."]),
    (r"\b(?:caixa|leads?|reuni|crm|radar|clientes?|faturamento|cobran)", PAINEL),
    (r"porthon|condom[ií]nio|morador|encomenda|portaria|placa", ["Consultando o Porthon, chefe.", "Deixa eu olhar o Porthon."]),
    (r"\b(?:globo|mapa|onde fica|cidade|pa[ií]s|estado|bairro|rua|avenida|perto)\b|street view|aqui perto",
     ["Localizando no globo, chefe.", "Girando o globo.", "Achando no mapa."]),
    (r"\b(?:tempo|clima|previs[aã]o|chover|chuva|temperatura|frio|calor)\b", ["Olhando a previsão, chefe.", "Vendo o tempo."]),
    (r"cota[cç][aã]o|d[oó]lar|euro|bitcoin", ["Vendo a cotação, chefe."]),
    (r"\b(?:c[oó]digo|script|programa[cç][aã]o|bug|erro|commit|deploy|git)\b", ["Olhando o código, chefe.", "Deixa eu analisar isso."]),
    (r"\b(?:arquivo|pasta|documento|planilha)s?\b", ["Procurando nos seus arquivos.", "Deixa eu achar isso."]),
    (r"\btela\b|print", ["Dando uma olhada na tela.", "Deixa eu ver a tela."]),
    (r"^(?:jarvis[ ,]*)?(?:pesquisa|procura|busca|o que [eé]|quem [eé]|quem foi|me fala (?:sobre|de|do|da)|me explica|explica)",
     ["Pesquisando, chefe.", "Vou atrás disso.", "Buscando isso pra ti."]),
    (r"^(?:jarvis[ ,]*)?(?:me mostra|mostra)\b", ["Já te mostro, chefe.", "Preparando pra te mostrar.", "Um instante, já aparece."]),
    (r"\?\s*$|^(?:jarvis[ ,]*)?(?:o que|como|por ?que|qual|quais|quanto|quantos|quem|quando|onde|ser[aá])\b",
     ["Hum, deixa eu pensar.", "Boa pergunta. Deixa eu pensar.", "Deixa eu ver isso, chefe."]),
]
NEUTRAS = ["Um instante.", "Só um momento, chefe.", "Já vejo isso.", "Deixa comigo.", "Já tô nisso, chefe."]


def espera_para(texto):
    """A frase de espera que combina com o pedido, ou None (papo: melhor ficar quieto do que falar "processando")."""
    t = (texto or "").strip().lower()
    for regra, frases in ESPERAS_POR_ASSUNTO:
        if re.search(regra, t, re.I):
            return escolher(frases, regra) if frases else None
    return escolher(NEUTRAS, "neutras")


def todas_fixas():
    """Todas as frases fixas (o servidor gera o áudio delas no startup)."""
    saida = set(CHAMADO + ESPERAS + DEMORANDO + MUSICA + PAINEL + DE_NADA + CANCELADO + PRONTO + NEUTRAS)
    for _, frases in ESPERAS_POR_ASSUNTO:
        saida.update(frases or ())
    for lista in TROCAS.values():
        saida.update(lista)
    return sorted(saida)
