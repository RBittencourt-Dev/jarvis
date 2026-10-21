"""Pedidos sobre o PRÓPRIO Jarvis: o globo, o mapa, os painéis, o Olho de Deus. Respondem na hora, sem modelo.

Bug que isso resolve: "procura X no globo" / "abre o globo" iam pra pesquisa ou pro "abrir programa" e ele
respondia "não achei nenhum app chamado globo". Globo, mapa, planeta, painel, Olho de Deus são DELE.
entender(texto) → (tipo, valor) ou None. O servidor executa; o treino.py confere pela rota_de.
"""
import re
import unicodedata


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


J = r"^(?:jarvis[ ,]*)?"
FIM = r"(?:\s+(?:a[ií]|pra mim|por favor|chefe|jarvis))*[.!?]*$"
GLOBO = r"(?:globo|mapa|planeta|mundo\s+(?:holografico|3d))"
DONO = r"(?:o\s+|a\s+|teu\s+|tua\s+|seu\s+|sua\s+|nosso\s+|nossa\s+|o\s+teu\s+|o\s+seu\s+|o\s+nosso\s+)?"

ABRE_GLOBO = re.compile(J + r"(?:abre|abrir|mostra|mostrar|liga|ativa|quero\s+ver|me\s+mostra|vai\s+pro|volta\s+pro|traz)\s+"
                        + DONO + GLOBO + FIM)
NO_GLOBO = re.compile(r"\s*\b(?:n[oa]|pelo|pela|em|dentro\s+d[oa])\s+" + DONO + GLOBO + r"\b\s*")
VERBOS_DE_LUGAR = re.compile(
    r"^(?:me\s+)?(?:procura|procurar|acha|achar|encontra|localiza|localizar|busca|buscar|pesquisa|pesquisar|mostra|mostrar|"
    r"marca|marcar|aponta|coloca|joga|bota|p[oõ]e|vai\s+(?:at[eé]|pra|para)|leva\s+(?:at[eé]|pra)|onde\s+fica|cad[eê])"
    r"(?:\s+(?:pra\s+mim|a[ií]))?\s+(?:o\s+|a\s+|os\s+|as\s+|um\s+|uma\s+)?")

# 21/10: "desativar olho de Deus" (verbo com -r) não batia e o cérebro FINGIA que tinha desligado
OLHO_LIGAR = re.compile(J + r"(?:(?:liga|ligar|ativa|ativar|abre|abrir|aciona|acionar|entra\s+n[oa]|entrar\s+n[oa]|mostra|mostrar|"
                        r"modo|volta\s+(?:com\s+)?o)\s+)?(?:o\s+|a\s+)?(?:modo\s+)?olho\s+de\s+deus(?:\s+(?:ligado|on|ativado))?" + FIM)
OLHO_DESLIGAR = re.compile(
    J + r"(?:(?:desliga|desligar|desativa|desativar|fecha|fechar|sai|sair|tira|tirar|encerra|encerrar|para|parar|apaga|apagar|"
    r"cancela|cancelar|chega\s+de|some\s+com|esconde|esconder)\s+(?:d[oa]\s+|o\s+|a\s+)?(?:modo\s+)?olho\s+de\s+deus|"
    r"(?:o\s+)?(?:modo\s+)?olho\s+de\s+deus\s+(?:desligado|off|desativado))" + FIM)
# "volta o globo ao normal", "tira o zoom", "reseta o globo"
GLOBO_NORMAL = re.compile(
    J + r"(?:(?:volta|voltar|deixa|bota|coloca|p[oõ]e)\s+(?:o\s+|a\s+)?(?:globo|mapa|planeta|tela|c[aâ]mera)\s+(?:a[oa]\s+|pr[oa]\s+|para\s+o\s+|no\s+)?normal|"
    r"(?:o\s+)?(?:globo|mapa|planeta)\s+(?:a[oa]\s+|no\s+)?normal|"
    r"(?:tira|tirar|remove|desfaz|desfazer)\s+(?:o\s+)?zoom|zoom\s+out|afasta(?:r)?\s+(?:o\s+globo|a\s+c[aâ]mera|o\s+zoom)?|"
    r"(?:reseta|resetar|reinicia|reiniciar|zera|zerar)\s+o\s+(?:globo|mapa)|limpa\s+tudo\s+do\s+(?:globo|mapa)|volta\s+a\s+girar|"
    r"volta(?:r)?\s+(?:o\s+|a\s+)?(?:globo|mapa|planeta)(?:\s+inteiro)?)" + FIM)
CAMADA = re.compile(
    J + r"(?:e\s+)?(?P<acao>mostra|mostrar|me\s+mostra|liga|ativa|bota|coloca|p[oõ]e|quero\s+ver|tira|esconde|desliga|apaga|remove|some\s+com|"
    r"oculta|ocultar|esconder|tirar|desligar|apagar|remover|sumir\s+com|"
    r"adiciona|acrescenta|mostra\s+tamb[eé]m|me\s+mostra\s+tamb[eé]m|bota\s+tamb[eé]m)\s+(?:tamb[eé]m\s+|junto\s+)?"
    r"(?:o\s+|a\s+|os\s+|as\s+)?(?:camada\s+d[oea]s?\s+)?"
    r"(?P<camada>avi[oõ]es|aviao|voos?|tr[aá]fego\s+a[eé]reo|sat[eé]lites?|esta[cç][aã]o\s+espacial|iss|terremotos?|sismos?|"
    r"tremores?|clima|tempo\s+no\s+mundo|temperaturas?|not[ií]cias\s+no\s+(?:globo|letreiro))"
    r"(?:\s+(?:ao\s+vivo|em\s+tempo\s+real|agora|perto|aqui\s+perto|no\s+globo|no\s+mapa|do\s+mundo|voando|que\s+est[aã]o|"
    r"que\s+t[aã]o|no\s+olho\s+de\s+deus))*"
    # "aviões sobrevoando o Brasil", "voos sobre a Europa", "terremotos no Japão"
    r"(?:\s+(?:sobrevoando|voando\s+(?:sobre|em\s+cima\s+d[oa]|n[oa]|por)|sobre|em\s+cima\s+d[oa]|por\s+cima\s+d[oa]|no\s+c[eé]u\s+d[eoa]|"
    r"n[oa]s?|em|perto\s+d[eoa]|d[oa]s?|pel[oa])\s+(?:o\s+|a\s+|os\s+|as\s+)?(?P<onde>.+?))?"
    r"(?:\s+(?:no\s+globo|no\s+mapa|no\s+olho\s+de\s+deus|ao\s+vivo|agora|em\s+tempo\s+real))*" + FIM)
LIMPAR_CAMADAS = re.compile(J + r"(?:limpa|tira|desliga|apaga)\s+(?:todas\s+)?(?:as\s+)?camadas" + FIM)
MAPA_CAMADA = {"avi": "avioes", "voo": "avioes", "traf": "avioes", "sat": "satelites", "esta": "satelites", "iss": "satelites",
               "terr": "terremotos", "sism": "terremotos", "trem": "terremotos", "clim": "clima", "temp": "clima", "noti": "noticias"}

MAIS_FOTOS = re.compile(J + r"(?:me\s+)?(?:mostra|manda|traz|bota|quero\s+ver)\s+mais\s+(?:fotos|imagens|figuras)" + FIM)
APROFUNDAR = re.compile(J + r"(?:aprofunda|aprofundar|detalha|detalhar|explica\s+melhor|me\s+conta\s+mais|fala\s+mais|"
                        r"quero\s+saber\s+mais|mais\s+detalhes)(?:\s+(?:isso|sobre\s+isso|disso|esse\s+assunto|a[ií]))?" + FIM)
ORDINAIS = {"primeira": 1, "primeiro": 1, "1": 1, "um": 1, "uma": 1, "segunda": 2, "segundo": 2, "2": 2, "dois": 2, "duas": 2,
            "terceira": 3, "terceiro": 3, "3": 3, "tres": 3, "quarta": 4, "quarto": 4, "4": 4, "quatro": 4, "quinta": 5,
            "quinto": 5, "5": 5, "cinco": 5, "sexta": 6, "6": 6, "seis": 6, "ultima": -1, "ultimo": -1}
N = r"(?P<n>primeir[ao]|segund[ao]|terceir[ao]|quart[ao]|quint[ao]|sexta|ultim[ao]|\d|um|uma|dois|duas|tres|quatro|cinco|seis)"
FONTE = re.compile(J + r"(?P<verbo>abre|abrir|l[eê]|ler|mostra|mostrar|me\s+mostra)\s+(?:a\s+|o\s+)?"
                   r"(?:fonte|link|site|artigo|mat[eé]ria)\s+(?:n[uú]mero\s+)?" + N +
                   r"(?P<nav>\s+no\s+(?:navegador|chrome|opera|edge|google))?" + FIM)
FONTE2 = re.compile(J + r"(?P<verbo>abre|abrir|l[eê]|ler|mostra)\s+(?:a\s+|o\s+)?" + N + r"\s+(?:fonte|link|site|mat[eé]ria)"
                    r"(?P<nav>\s+no\s+(?:navegador|chrome|opera|edge|google))?" + FIM)
AMPLIAR = re.compile(J + r"(?:amplia|ampliar|aumenta|abre|mostra|me\s+mostra|zoom\s+n[ao])\s+(?:a\s+|o\s+)?"
                     r"(?:" + N + r"\s+(?:foto|imagem|figura)|(?:foto|imagem|figura)\s+(?:n[uú]mero\s+)?" + N.replace("?P<n>", "?P<n2>") + r")"
                     r"(?:\s+(?:grande|maior|em\s+tela\s+cheia))?" + FIM)
FECHAR_PAINEL = re.compile(J + r"(?:fecha|fechar|tira|some\s+com)\s+(?:esse|este|o|a|essa)\s+"
                           r"(?:painel|pesquisa|leitura|foto|imagem|plano|resultado)" + FIM)
FECHAR_TUDO = re.compile(J + r"(?:fecha|limpa|tira)\s+(?:todos\s+os\s+pain[eé]is|tudo\s+da\s+tela|a\s+tela\s+toda)" + FIM)
FIXAR = re.compile(J + r"(?:fixa|fixar|prende|segura|deixa)\s+(?:esse|este|o)\s+painel(?:\s+(?:a[ií]|na\s+tela|fixo))?" + FIM)
# notícias contadas com foto e página da fonte (noticias_painel.py)
NOTICIAS = re.compile(
    J + r"(?:(?:me\s+)?(?:mostra|mostrar|conta|contar|fala|falar|l[eê]|ler|traz|trazer|bota|quais\s+s[aã]o|quero\s+(?:ver|saber)|"
    r"tem|me\s+atualiza\s+(?:com|n)as)\s+)?(?:as\s+|umas?\s+|algumas\s+)?(?:[uú]ltimas\s+|principais\s+)?"
    r"(?:not[ií]cias?|manchetes?)(?:\s+(?:de\s+hoje|do\s+dia|de\s+agora|mais\s+recentes|principais|quentes|importantes))?"
    r"(?:\s+(?:de|do|da|dos|das|sobre|em)\s+(?P<tema>.+?))?"
    r"(?:\s+(?:na\s+tela|aqui|pra\s+mim|na\s+outra\s+tela|de\s+hoje|do\s+dia|com\s+fotos?))*" + FIM)
RODANDO = re.compile(J + r"o\s+que\s+(?:t[aá]|est[aá])\s+(?:rolando|acontecendo)(?:\s+(?:hoje|no\s+mundo|no\s+brasil|de\s+novo))?"
                     r"(?:\s+sobre\s+(?:o\s+|a\s+)?(?P<tema>.+?))?" + FIM)
ABRIR_NOTICIA = re.compile(
    J + r"(?:abre|abrir|mostra|mostrar|me\s+mostra|l[eê]|ler|quero\s+ver)\s+(?:a\s+|essa\s+|esta\s+)?"
    r"(?:(?:not[ií]cia|mat[eé]ria|reportagem)(?:\s+(?:n[uú]mero\s+)?" + N + r")?|" + N.replace("?P<n>", "?P<n2>") +
    r"\s+(?:not[ií]cia|mat[eé]ria)|p[aá]gina(?:\s+d[oa]\s+(?:site|not[ií]cia|mat[eé]ria|g1|bbc|ag[eê]ncia\s+brasil|fonte))?|"
    r"site\s+d[aoe]\s+(?:not[ií]cia|mat[eé]ria|g1|bbc|fonte))"
    r"(?P<nav>\s+no\s+(?:navegador|chrome|opera|edge))?(?:\s+(?:inteira|a[ií]|aqui|dentro|na\s+tela))*" + FIM)
# mover o que está na tela entre as duas telas
MOVER = re.compile(
    J + r"(?:passa|passar|joga|jogar|manda|mandar|leva|levar|move|mover|coloca|colocar|bota|botar|p[oõ]e|transfere|traz|trazer|mostra)\s+"
    r"(?:isso|isto|esse|essa|este|esta|ele|ela|o\s+painel|a\s+pesquisa|as\s+not[ií]cias|a\s+not[ií]cia|a\s+foto|o\s+cart[aã]o|o\s+pop\s*-?\s*up|"
    r"esse\s+(?:painel|cart[aã]o|pop\s*-?\s*up|resultado)|essa\s+(?:pesquisa|foto|not[ií]cia|leitura|p[aá]gina)|tudo)?\s*"
    r"(?:(?P<la>pra|para|na|pro)\s+(?:a\s+|o\s+)?(?:outra\s+tela|tela\s+de\s+cima|tela\s+vertical|tela\s+em\s+p[eé]|segunda\s+tela|extens[aã]o|tela\s+da\s+direita|outro\s+monitor)|"
    r"(?P<ca>pra\s+c[aá]|aqui|pra\s+(?:a\s+)?tela\s+principal|na\s+tela\s+principal|pra\s+essa\s+tela|pra\s+frente|pro\s+meio|pro\s+centro))" + FIM)
# "beleza, pode fechar", "fecha isso": fecha o que ele acabou de mostrar (o servidor confere se tem algo na tela)
FECHAR_MOSTRADO = re.compile(
    J + r"(?:(?:beleza|blz|ok|t[aá]\s+bom|valeu|show|perfeito|j[aá]\s+vi|entendi)[ ,]+)?(?:pode\s+)?"
    r"(?:fechar|fecha|tirar|tira|sumir\s+com|some\s+com|esconder|esconde)(?:\s+(?:isso|isto|ele|ela|a[ií]|tudo|as\s+not[ií]cias|a\s+p[aá]gina))?" + FIM)
# estabelecimentos: "mostra os Burger King em Porto Alegre", "restaurantes aqui perto", "onde tem farmácia"
POIS = re.compile(
    J + r"(?:me\s+)?(?P<verbo>mostra|mostrar|acha|achar|procura|procurar|busca|buscar|marca|marcar|localiza|localizar|aponta|"
    r"lista|listar|quais(?:\s+s[aã]o)?|onde\s+(?:tem|t[eê]m)|tem)\s+"
    r"(?P<qtd>(?:tod[oa]s\s+)?(?:os|as|uns|umas)\s+|algum[a]?\s+|um[a]?\s+|o\s+|a\s+)?(?P<termo>.+?)"
    r"(?:\s+(?P<perto>aqui\s+perto|perto\s+de\s+mim|por\s+aqui|aqui\s+em\s+volta|perto\s+de\s+casa)|"
    r"\s+(?:que\s+(?:tem|t[eê]m|ficam?|est[aã]o)\s+)?(?:em|no|na|nos|nas|perto\s+d[eoa]|em\s+volta\s+d[eoa])\s+(?P<onde>.+?))?"
    r"(?:\s+(?:no\s+globo|no\s+mapa|pra\s+mim|a[ií]))*" + FIM)
NAO_E_POI = re.compile(r"^(?:rua|avenida|av|estrada|rodovia|br|pra[cç]a|cidade|pa[ií]s|estado|bairro|mapa|globo|planeta|tela|"
                       r"aba|abas|janela|janelas|pop|arquivo|arquivos|pasta|m[uú]sica|playlist|lead|leads|reuni|not[ií]cia|foto|"
                       r"imagem|fontes?|avi[oõ]|voo|sat[eé]lite|terremoto|clima|tempo|previs|cota[cç]|d[oó]lar|morador|placa|"
                       r"carro|porthon|caixa|painel|resultado|rota|street|caminho|fotos|v[ií]deo)", re.I)
FILTRO = re.compile(
    J + r"(?:(?:s[oó]|somente|apenas|agora|filtra|filtrar|e|mas|mostra\s+s[oó])\s+)*(?:(?:os|as)\s+)?(?:que\s+(?:ficam?|est[aã]o)\s+)?"
    r"(?:(?P<perto>aqui\s+perto|perto\s+de\s+mim|por\s+aqui|perto\s+de\s+casa)|(?:em|no|na|nos|nas|perto\s+d[eoa])\s+(?P<onde>.+?))" + FIM)
NAO_E_LUGAR = re.compile(r"^(?:chrome|opera|edge|navegador|youtube|spotify|whatsapp|zap|outra\s+tela|tela|extens|globo|mapa|"
                         r"segundo\s+plano|modo|vs\s*code|porthon|painel|radar)", re.I)

# "mostra o globo real", "via satélite", "camadas da terra" ↔ "modo holograma"
SATELITE = re.compile(J + r"(?:(?:me\s+)?(?:mostra|mostrar|liga|ativa|bota|coloca|p[oõ]e|quero\s+ver|abre|deixa|muda\s+pr[oa]|troca\s+pr[oa]|vai\s+pr[oa])\s+)?"
                      r"(?:o\s+|a\s+|as\s+|em\s+)?(?:modo\s+)?(?:globo\s+(?:real|de\s+verdade|via\s+sat[eé]lite|com\s+(?:foto|imagem)\s+de\s+sat[eé]lite)|"
                      r"terra\s+(?:real|de\s+verdade)|camadas?\s+da\s+terra|(?:foto|imagem|vis[aã]o|vista)\s+(?:real\s+)?(?:de|do|via)\s+sat[eé]lite|"
                      r"sat[eé]lite\s+(?:real|ao\s+vivo|em\s+tempo\s+real)|mapa\s+(?:real|de\s+sat[eé]lite)|modo\s+sat[eé]lite|via\s+sat[eé]lite|"
                      # "segunda visão da terra", "outra visão", "a terra com aquelas camadas" (a foto real por cima)
                      r"(?:segunda|outra|nova)\s+vis[aã]o(?:\s+d[ao]\s+(?:terra|globo|planeta|mundo))?|vis[aã]o\s+real(?:\s+d[ao]\s+(?:terra|globo))?|"
                      r"(?:terra|globo|planeta)\s+com\s+(?:as\s+|aquelas\s+|essas\s+)?camadas)"
                      r"(?:\s+(?:no\s+globo|ao\s+vivo|em\s+tempo\s+real|agora))*" + FIM)
NUVENS = re.compile(J + r"(?P<tira>tira|tirar|sem|esconde|remove|apaga)?\s*(?:(?:mostra|mostrar|bota|coloca|liga|com|p[oõ]e)\s+)?(?:as\s+)?nuvens"
                    r"(?:\s+(?:de\s+hoje|de\s+verdade|reais|do\s+sat[eé]lite|no\s+globo))*" + FIM)
HOLOGRAMA = re.compile(J + r"(?:(?:volta|voltar|muda|troca|bota|liga|ativa|mostra)\s+(?:pr[oa]\s+|o\s+|a\s+|ao\s+)?)?(?:modo\s+)?"
                       r"(?:holograma|hologr[aá]fico|globo\s+hologr[aá]fico|globo\s+azul)" + FIM)

ATUALIZAR = re.compile(J + r"(?:(?:se|te)\s+atualiza|atualiza(?:r)?\s+(?:o\s+jarvis|voc[eê]|a\s+si\s+mesmo|tu|o\s+sistema\s+do\s+jarvis)|"
                       r"(?:baixa|baixar|instala|instalar|aplica|aplicar)\s+a(?:s)?\s+atualiza[cç](?:[aã]o|[oõ]es))" + FIM)
VER_ATUALIZACAO = re.compile(J + r"(?:(?:tem|t[eê]m|h[aá]|existe)\s+(?:alguma\s+)?atualiza[cç](?:[aã]o|[oõ]es)(?:\s+(?:nova|pra\s+(?:ti|voc[eê])|do\s+jarvis))?|"
                             r"(?:verifica|ver|confere|procura)\s+(?:se\s+tem\s+)?(?:as\s+)?atualiza[cç](?:[aã]o|[oõ]es)|"
                             r"(?:voc[eê]|tu)\s+(?:t[aá]|est[aá])\s+atualizado)" + FIM)

AVIAO_INFO = re.compile(
    J + r"(?:(?:qual|que)\s+(?:[eé]\s+)?(?:o\s+)?avi[aã]o\s+(?:[eé]\s+)?(?:esse|aquele|este|t[aá]\s+(?:passando|sobrevoando|voando)|"
    r"est[aá]\s+(?:passando|sobrevoando|voando)|passa|que\s+t[aá]\s+(?:passando|sobrevoando))|"
    r"(?:me\s+)?(?:fala|diz|conta)\s+(?:mais\s+)?(?:desse|daquele|sobre\s+esse)\s+avi[aã]o|"
    r"(?:de\s+)?onde\s+(?:vem|veio)\s+(?:esse|aquele)\s+avi[aã]o|pra\s+onde\s+vai\s+(?:esse|aquele)\s+avi[aã]o)"
    r"(?:\s+(?:aqui|em\s+cima(?:\s+de\s+mim|\s+da\s+minha\s+casa)?|agora|perto|sobre\s+(?:a\s+|o\s+)?(?P<onde>.+?)))?" + FIM)
ESPECIFICAR_AVIOES = re.compile(
    J + r"(?:especifica|especificar|detalha|detalhar|identifica|identificar|lista|listar|me\s+(?:fala|diz|conta)\s+(?:d?os|quais\s+s[aã]o\s+os)|"
    r"quais\s+(?:s[aã]o\s+)?(?:os\s+)?avi[oõ]es(?:\s+(?:que\s+)?(?:est[aã]o|t[aã]o)\s+(?:no\s+ar|voando|passando|sobrevoando)))"
    r"(?:\s+(?:os|esses|aqueles))?(?:\s+avi[oõ]es)?(?:\s+(?:da\s+tela|no\s+globo|aqui|em\s+cima|perto|sobre\s+(?:a\s+|o\s+)?(?P<onde>.+?)))?" + FIM)

RUIDO_INICIAL = re.compile(r"^(?:jarvis[ ,]*)?(?:ent[aã]o|a[ií]|agora|e|ah|bom|n[aã]o)[ ,]+(?=(?:me\s+)?(?:mostra|liga|ativa|desativa|desliga|conta|abre|passa|traz))")

DESFAZER = re.compile(J + r"(?:desfaz|desfazer|desfa[cç]a|volta\s+atr[aá]s|reverte|cancela)\s*(?:isso|o\s+que\s+(?:voc[eê]|tu)\s+fez|"
                      r"a\s+[uú]ltima(?:\s+coisa|\s+a[cç][aã]o)?|essa\s+(?:mudan[cç]a|a[cç][aã]o))?" + FIM)


def _n(m):
    v = m.groupdict().get("n") or m.groupdict().get("n2")
    return ORDINAIS.get(_sa(v or ""), 1)


def entender(texto):
    t = _sa(texto).strip()
    t = RUIDO_INICIAL.sub("", t)  # "então me mostra…" ("não me mostra" é o Chrome ouvindo "então")
    if not t:
        return None
    if GLOBO_NORMAL.match(t):
        return ("globo_normal", None)
    if ATUALIZAR.match(t):
        return ("atualizacao", "atualizar")
    if VER_ATUALIZACAO.match(t):
        return ("atualizacao", "verificar")
    if SATELITE.match(t):
        return ("modo_globo", "satelite")
    if HOLOGRAMA.match(t):
        return ("modo_globo", "holograma")
    m = NUVENS.match(t)
    if m:
        return ("modo_globo", "satelite" if m.group("tira") else "nuvens")
    if OLHO_DESLIGAR.match(t):
        return ("olho", "desligar")
    if OLHO_LIGAR.match(t):
        return ("olho", "ligar")
    if LIMPAR_CAMADAS.match(t):
        return ("olho", "desligar")
    m = AVIAO_INFO.match(t)
    if m:
        return ("aviao_info", (m.group("onde") or "").strip())
    m = ESPECIFICAR_AVIOES.match(t)
    if m and re.search(r"avi[oõ]es|quais", t):
        return ("avioes_lista", (m.group("onde") or "").strip())
    m = CAMADA.match(t) or (CAMADA.match("mostra tambem " + t[2:]) if re.match(r"e\s+(?:os|as|o|a)\s", t) else None)
    if m:
        camada = next(v for k, v in MAPA_CAMADA.items() if _sa(m.group("camada")).startswith(k))
        tira = re.match(r"tira|esconde|desliga|apaga|remove|some|oculta|sumir", m.group("acao"))
        onde = (m.group("onde") or "").strip()
        if re.sub(r"^(?:a|o)\s+", "", onde) in ("aqui", "aqui perto", "perto", "mundo", "globo", "mapa", "ceu", "tela", "orbita",
                                                   "orbita da terra", "orbita terrestre", "espaco", "planeta", "terra"):
            onde = ""
        if onde:  # devolve com os acentos de como ele falou
            i = _sa(texto).find(onde)
            onde = texto[i:i + len(onde)] if i >= 0 else onde
        somar = bool(re.search(r"\b(?:tamb[eé]m|junto|junt[ao]s?|mais\s+(?:os|as)|adiciona|acrescenta|al[eé]m\s+d)", t)) or t.startswith("e ")
        return ("camada", (camada, not tira, onde, somar))
    m = ABRIR_NOTICIA.match(t)
    if m:
        n = m.groupdict().get("n") or m.groupdict().get("n2")
        return ("abrir_noticia", (ORDINAIS.get(n, 1) if n else None, bool(m.group("nav"))))
    m = NOTICIAS.match(t) or RODANDO.match(t)
    if m:
        tema = re.sub(r"^(?:o|a|os|as)\s+", "", (m.group("tema") or "").strip())
        if tema in ("hoje", "agora", "do dia"):
            tema = ""
        i = _sa(texto).find(tema) if tema else -1
        return ("noticias", texto[i:i + len(tema)] if i >= 0 else tema)
    m = MOVER.match(t)
    if m:
        return ("mover", "aqui" if m.group("ca") else "outra")
    sem_verbo = False
    m = POIS.match(t)
    if not m:
        m, sem_verbo = POIS.match("mostra " + t), True  # "restaurantes em Gramado", sem verbo
    if m:
        termo = (m.group("termo") or "").strip(" ,.")
        onde = "perto de mim" if m.group("perto") else (m.group("onde") or "").strip(" ,.")
        import pois as _pois
        plural = bool(re.match(r"(?:tod[oa]s\s+)?(?:os|as|uns|umas)\s", m.group("qtd") or ""))
        cat = _pois.categoria(termo)
        if sem_verbo:
            varios = bool(cat)  # sem verbo só vale categoria ("farmácias", "restaurantes em Gramado")
        elif m.group("verbo") == "tem":
            varios = bool(cat)  # "tem farmácia aqui perto" sim; "tem ocorrência aberta no X" não
        elif m.group("verbo").startswith(("quais", "lista")):
            varios = bool(cat) or bool(onde)
        else:
            varios = plural or bool(cat) or m.group("verbo").startswith("onde") or bool(onde)
        if re.match(r"(?:abre|abrir|pesquisa|pesquisar|joga|toca|fecha|passa|manda)\b", termo):
            varios = False  # "abre o notion na segunda tela", "pesquisa X no google": não é estabelecimento
        if termo and varios and not NAO_E_POI.match(termo) and len(termo.split()) <= 5 and not NAO_E_LUGAR.match(onde or "x"):
            def original(x):
                i = _sa(texto).find(x)
                return texto[i:i + len(x)] if (x and i >= 0) else x
            return ("pois", (original(termo), original(onde) if onde != "perto de mim" else onde))
    m = FILTRO.match(t)
    if m:
        onde = "perto de mim" if m.group("perto") else (m.group("onde") or "").strip(" ,.")
        if onde and not NAO_E_LUGAR.match(onde) and len(onde.split()) <= 5:
            i = _sa(texto).find(onde)
            return ("filtro", texto[i:i + len(onde)] if i >= 0 and onde != "perto de mim" else onde)
    if FECHAR_MOSTRADO.match(t):
        return ("fechar_mostrado", None)
    if ABRE_GLOBO.match(t):
        return ("abrir_globo", None)
    if MAIS_FOTOS.match(t):
        return ("mais_fotos", None)
    if APROFUNDAR.match(t):
        return ("aprofundar", None)
    m = FONTE.match(t) or FONTE2.match(t)
    if m:
        return ("fonte", (_n(m), bool(m.group("nav"))))
    m = AMPLIAR.match(t)
    if m:
        return ("ampliar", _n(m))
    if FECHAR_TUDO.match(t):
        return ("fechar_painel", "todos")
    if FECHAR_PAINEL.match(t):
        return ("fechar_painel", "ultimo")
    if FIXAR.match(t):
        return ("fixar", None)
    if DESFAZER.match(t):
        return ("desfazer", None)
    # "procura a rua X no globo", "no mapa mostra Gramado", "joga Paris no nosso globo"
    if NO_GLOBO.search(t):
        resto = NO_GLOBO.sub(" ", t).strip(" ,.!?")
        resto = re.sub(r"^(?:jarvis[ ,]*)", "", resto)
        resto = VERBOS_DE_LUGAR.sub("", resto).strip(" ,.!?")
        resto = re.sub(r"^(?:pra\s+mim|a[ií])\s+", "", resto)
        if re.match(r"(?:seleciona|selecionar|destaca|destacar|isola|recorta)\b", resto):
            return None  # "seleciona o RS no mapa": é a silhueta, quem cuida é o lugares.SELECIONAR
        if resto and len(resto.split()) <= 10:
            # devolve com a grafia original (acentos), cortando pelo tamanho do resto sem acento
            original = texto.strip()
            i = _sa(original).find(resto)
            return ("lugar", original[i:i + len(resto)] if i >= 0 else resto)
    return None
