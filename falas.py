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


def todas_fixas():
    """Todas as frases fixas (o servidor gera o áudio delas no startup)."""
    saida = set(CHAMADO + ESPERAS + DEMORANDO + MUSICA + PAINEL + DE_NADA + CANCELADO + PRONTO)
    for lista in TROCAS.values():
        saida.update(lista)
    return sorted(saida)
