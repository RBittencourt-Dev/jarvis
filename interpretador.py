"""Entende o pedido do jeito que ele falar e traduz para um comando que o Jarvis sabe executar.

"bota aquela do Legião pra tocar" → "toca Legião Urbana"; "como tá a grana da empresa" → "quanto tem no caixa".
Usa o modelo local só para essa tradução (resposta em JSON, curta). Quem executa continuam sendo os
caminhos certeiros (spotify.py, whatsapp.py, painel.py…). O que ele confirma fica gravado em
frases-aprendidas.json: da próxima vez, a mesma frase vai direto, sem modelo.
"""
import json
import re
import unicodedata
from pathlib import Path

import httpx

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "frases-aprendidas.json"

COMANDOS = """\
MÚSICA (sempre no Spotify, que está conectado): "toca <música, artista ou playlist>", "pausa a música", "continua a música",
  "próxima música", "música anterior", "que música é essa"
PROGRAMAS E SITES: "abre <programa ou site>", "abre <programa> na outra tela", "fecha <programa>", "minimiza <programa>",
  "maximiza <programa>", "passa <programa> pra outra tela", "fecha os popups", "minimiza os popups", "fecha isso",
  "traz de volta as janelas", "fecha a aba do <site> no <navegador>", "fecha a aba"
INTERNET: "pesquisa <assunto inteiro>", "pesquisa <assunto> no opera", "pesquisa <assunto> no chrome", "pesquisa no youtube <assunto>", "me mostra fotos de <coisa>", "quanto tá o dólar",
  "vai chover hoje"
WHATSAPP: "manda pro <pessoa>: <mensagem>", "envia uma mensagem"
SEVENCODE (painel e Radar): "quanto tem no caixa", "quantos leads novos", "tenho reunião hoje", "reuniões da semana",
  "agenda uma reunião com <lead> <dia> às <hora>", "marca o lead <nome> como <interessado|reunião|fechado|perdido>",
  "me fala do lead <nome>", "sugere uma resposta pro <lead>", "quais leads estão interessados"
PORTHON (só se ele falar do Porthon, de morador ou de placa): "procura o morador <nome>", "procura a placa <placa>",
  "procura o carro <modelo> no porthon", "o que falta no porthon", "qual foi o último commit do porthon", "quantas encomendas pendentes"
COMPUTADOR: "aumenta o volume", "abaixa o volume", "bloqueia a tela", "desliga o computador", "ativa o modo escuro"
CLAUDE (programação): "pergunta pro claude <pergunta>", "pede pro claude <tarefa>"
OUTROS: "que horas são", "boa noite jarvis"
"""

EXEMPLOS = [
    ("bota aquela do legião pra tocar", "toca Legião Urbana", 0.9),
    ("quero escutar um engenheiros", "toca Engenheiros do Hawaii", 0.9),
    ("dá um play em tempo perdido", "toca Tempo Perdido", 0.95),
    ("consegue colocar uma música pra mim no spotify", "toca uma playlist", 0.6),
    ("joga um som aí", "toca uma playlist", 0.6),
    ("abre aquele app de música", "abre o spotify", 0.85),
    ("como tá a grana da empresa", "quanto tem no caixa", 0.9),
    ("avisa o jesus que já tô saindo", "manda pro Jesus: já tô saindo", 0.9),
    ("tira essa janela do spotify daqui", "passa o spotify pra outra tela", 0.7),
    ("tem alguém novo no radar", "quantos leads novos", 0.85),
    ("que que tem pra fazer no porthon", "o que falta no porthon", 0.9),
    ("como andam as coisas do porthon", "o que falta no porthon", 0.8),
    ("qual foi a última coisa que subiu no porthon", "qual foi o último commit do porthon", 0.85),
    ("e aí jarvis tudo certo contigo", "conversa", 0.95),
    ("joga aí no opera a bmw x1 pra mim", "pesquisa bmw x1 no opera", 0.9),
    ("quero ver uns preço de x1 da bmw", "pesquisa preço bmw x1", 0.85),
    ("acha pra mim quem mora no porthon com nome silva", "procura o morador silva", 0.85),
    ("o que tu acha da landing do porthon", "conversa", 0.9),
]


def _prompt(texto):
    exemplos = "\n".join(f'"{f}" → {{"comando": "{c}", "confianca": {n}}}' for f, c, n in EXEMPLOS)
    return (
        "Você traduz o que o Rafael falou (português gaúcho, transcrito por voz, às vezes errado) para UM comando "
        "da lista abaixo, preenchendo os <campos> com o que ele disse. Se for só conversa, pergunta de opinião ou "
        "algo fora da lista, responda \"conversa\".\n\n" + COMANDOS +
        "\nExemplos:\n" + exemplos +
        f'\n\nAgora: "{texto}"\nResponda SÓ o JSON: {{"comando": "...", "confianca": 0.0 a 1.0}}')


async def interpretar(texto):
    """(comando, confiança) ou ("conversa", 1.0). Nunca levanta erro: na dúvida, é conversa."""
    import cerebro
    try:
        resposta = await cerebro.completar([{"role": "user", "content": _prompt(texto)}], json_mode=True,
                                           temperatura=0, max_tokens=80)
        j = json.loads(resposta[resposta.index("{"):resposta.rindex("}") + 1])
        comando = str(j.get("comando", "conversa")).strip().strip('"')
        return comando or "conversa", float(j.get("confianca", 0.5))
    except Exception:
        return "conversa", 1.0


# ------------------------------------------------------------- aprendizado: frase dele → comando

def _chave(texto):
    t = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"\w+", t))


def _aprendidas():
    if ARQUIVO.exists():
        try:
            return json.loads(ARQUIVO.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def ja_aprendida(texto):
    return _aprendidas().get(_chave(texto))


MUSICA_OU_FECHAR = re.compile(r"^(?:toca|pausa|continua|pr[oó]xima|m[uú]sica anterior|fecha|minimiza)\b", re.I)
PEDIU_MUSICA_OU_FECHAR = re.compile(r"m[uú]sica|spotify|playlist|toca|toque|tocar|coloca|bota|p[oõ]e|som\b|ouvir|"
                                    r"pausa|para|pr[oó]xima|passa|fecha|fechar|minimiza|tira", re.I)


def plausivel(texto, comando):
    """Música e fechar janela só se ele falou disso: letra de música e conversa da TV não viram comando."""
    if MUSICA_OU_FECHAR.match(comando or "") and not PEDIU_MUSICA_OU_FECHAR.search(texto):
        return False
    return len(_chave(texto).split()) >= 2  # palavra solta ("fecha", "fechar") é ambígua demais


def aprender(texto, comando):
    if len(_chave(texto).split()) < 3 or (MUSICA_OU_FECHAR.match(comando or "") and not PEDIU_MUSICA_OU_FECHAR.search(texto)):
        return  # frase curta ou sem pedido claro: não vira atalho permanente
    frases = _aprendidas()
    frases[_chave(texto)] = comando
    ARQUIVO.write_text(json.dumps(frases, ensure_ascii=False, indent=1), encoding="utf-8")


def esquecer(texto):
    frases = _aprendidas()
    if frases.pop(_chave(texto), None):
        ARQUIVO.write_text(json.dumps(frases, ensure_ascii=False, indent=1), encoding="utf-8")
