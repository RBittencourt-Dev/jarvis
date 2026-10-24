"""O que o Jarvis REALMENTE sabe fazer — fonte única da verdade.

Pedido dele (23/10/2026): "tudo que você for dando de habilidade pro Jarvis, deixe ele sabendo exatamente o que ele
realmente consegue fazer, e quando eu perguntar o que ele sabe, abre um popup com tudo listado".

Este arquivo é a lista CANÔNICA. Ao ganhar uma habilidade nova, acrescente aqui (e só aqui). Daqui saem:
  - cartao()      → o popup que aparece quando ele pergunta "o que você sabe fazer".
  - fala()        → a frase curta que o Jarvis diz junto com o popup.
  - para_prompt() → um resumo enxuto injetado no prompt do sistema, pra o Jarvis NÃO prometer o que não faz.

Regra de ouro: só entra aqui o que foi construído e testado. Nada de capacidade "quase pronta".
"""

# (grupo, [(o que faz, um jeito de pedir)]). Mantém curto: é pra caber no popup e ser lido em voz.
GRUPOS = [
    ("Porthon — Marketing", [
        ("Dar a ideia do post pronta e formatada (título, legenda, hashtags) e abrir o modelo pra você fazer a arte", "cria um post pro Porthon sobre encomendas"),
        ("Montar um plano de marketing da semana com os horários e marcar os lembretes (do tamanho que você pedir)", "monta um plano de marketing com 1 post por semana"),
        ("Mudar o plano do seu jeito: quantidade, dia, horário, tema, tirar/adicionar post (lembretes acompanham; também em Configurações → Marketing)", "deixa só um post / passa o de terça pra 20h"),
        ("Mostrar ou apagar o plano de marketing (e os lembretes dele)", "apaga esse plano"),
        ("Mexer no post já gerado: título, legenda, CTA, hashtags", "deixa a legenda mais curta"),
        ("Montar a pauta de conteúdo da semana", "monta a pauta da semana do Porthon"),
        ("Dizer os melhores dias/horários e a estratégia pra postar", "qual o melhor dia pra postar"),
    ]),
    ("Porthon — Vendas", [
        ("Escrever mensagem de prospecção pra síndico/administradora", "escreve uma mensagem de prospecção pra administradora"),
        ("Dar as perguntas certas pra qualificar um lead", "qualifica esse lead"),
        ("Responder objeção (tá caro, já tenho sistema, vou pensar)", "o cara falou que tá caro, o que respondo"),
        ("Listar argumentos de venda e ideias de prospecção", "me dá argumentos pra vender o Porthon"),
        ("Ajustar o texto que acabou de escrever (mais curto, mais formal, sem emoji…)", "deixa ela mais curta"),
    ]),
    ("SevenCode — painel, leads e reuniões", [
        ("Contar o caixa, os leads e o andamento do Porthon", "como tão os leads hoje"),
        ("Marcar reunião e mexer no CRM do Radar", "marca uma reunião com o fulano amanhã às 3"),
        ("Falar de um lead específico e das reuniões da semana", "me fala do lead João"),
    ]),
    ("Conversa e assistente", [
        ("Conversar de verdade, com opinião, lembrando do que você contou", "o que você acha de..."),
        ("Guardar fatos seus e aprender atalhos que você ensina", "aprende que quando eu falar X você faz Y"),
        ("Avisar você quando o Claude termina uma tarefa", "(automático)"),
    ]),
    ("Abertura (quando liga)", [
        ("Abrir com a sua autenticação por rosto e se reconhecer (estado, cérebro, conectores)", "(ao ligar o PC)"),
        ("Falar a data e a hora e o resumo do dia", "me dá o resumo do dia"),
        ("Dar as principais notícias de tecnologia e IA", "notícias de tecnologia"),
    ]),
    ("WhatsApp e música", [
        ("Mandar mensagem no WhatsApp (você aprova o envio)", "manda um zap pro Rihan"),
        ("Tocar, pausar e trocar música no Spotify", "toca Tempo Perdido da Legião Urbana"),
    ]),
    ("Pesquisa, notícias e imagens", [
        ("Pesquisar na web e te mostrar o resumo dentro de mim", "pesquisa o que é a LGPD"),
        ("Ler uma página e te contar o conteúdo", "lê esse site pra mim"),
        ("Trazer as notícias do dia por tema", "notícias de tecnologia"),
        ("Gerar uma imagem por IA de graça (e salvar pra você)", "cria uma imagem de um gato astronauta"),
    ]),
    ("Globo e Olho de Deus", [
        ("Achar país, cidade, rua e estabelecimentos no globo", "mostra os Burger King em Porto Alegre"),
        ("Aviões ao vivo, satélites, terremotos, clima e foto de satélite", "mostra os aviões sobre o Brasil"),
        ("Camadas da Terra e nuvens reais no globo", "mostra as camadas da Terra"),
    ]),
    ("Computador (Windows)", [
        ("Abrir programas e sites, volume, bloquear, modo escuro", "abre o explorador de arquivos"),
        ("Desligar/reiniciar/suspender (pede seu “sim” falado)", "desliga o PC"),
        ("Ver o que está na sua tela e digitar/apertar teclas por você", "vê o que tá na tela"),
        ("Criar planilha e fazer qualquer conta", "quanto é 15% de 2340"),
    ]),
    ("Produtividade", [
        ("Lembretes, timer, pomodoro e anotações", "me lembra de ligar pro cliente às 5"),
    ]),
    ("Programação e Claude Code", [
        ("Ler, rodar e testar código; editar arquivo seu (você aprova)", "roda esse script e vê o que dá"),
        ("Passar um pedido pro Claude (pergunta em modo leitura ou faz na janela)", "pergunta pro Claude como tá o Porthon"),
        ("Se o Claude pago falhar (cota/fora do ar), o Claude grátis (FreeLLMAPI) responde a pergunta", "(automático)"),
    ]),
    ("Especialistas que ele aciona", [
        ("Chamar um expert: programação, segurança, copy, dados, finanças, design gráfico, jurídico, contábil", "chama o especialista em segurança"),
        ("Responder com a cabeça daquela área; tarefa pesada ele manda pro Claude", "como especialista em programação, me explica recursão"),
        ("Programação e segurança: resposta rápida na hora + análise do Claude lendo o projeto", "modo segurança, o login do Porthon tá protegido?"),
        ("Suporte técnico de T.I (PC, rede, Wi-Fi, impressora, projetor, Chromebook): passo a passo do diagnóstico", "a impressora não imprime"),
        ("Educação Adventista e Igreja Adventista: crenças, Escola Sabatina, Desbravadores, filosofia da escola", "modo adventista, o que é a Semana de Oração"),
        ("Marketing de escola: matrícula, rematrícula, Instagram e posts com autorização de imagem", "chama o especialista em marketing, ideias pra matrícula"),
    ]),
    ("Agenda (7planner)", [
        ("Ler as suas agendas do 7planner", "o que tem na minha agenda hoje"),
        ("Falar a agenda do dia sozinho às 7h e avisar 10 min antes de cada agendamento do Marketing e da T.I", "(automático)"),
    ]),
    ("Corpo humano 3D (voz + janelinha)", [
        ("Mostrar o corpo e os sistemas: esqueleto, músculos, nervoso, crânio, coração, cérebro", "mostra o esqueleto"),
        ("Mostrar um órgão ou parte sozinho e separar peça por peça, explicando", "me explica o coração"),
        ("Mostrar o corpo com modelo 3D real, estilo raio-x translúcido", "mostra o corpo em raio-x"),
        ("Janelinha na tela pra clicar e filtrar as partes e trocar de sistema", "(clica no menu ☰ do holograma)"),
    ]),
    ("Apresentações 3D", [
        ("Explicar qualquer assunto com holograma 3D (camadas da Terra, peças do PC...)", "me mostra as camadas da Terra em 3D"),
    ]),
    ("Professor particular (colégio)", [
        ("Dar uma aula de ensino médio sobre qualquer matéria", "me dá uma aula sobre fotossíntese"),
        ("Passar exercício pra você treinar (com a resposta explicada)", "me passa um exercício de matemática"),
        ("Ajudar com o dever, a prova e tirar dúvida da escola", "me ajuda com o dever de química"),
    ]),
]


def cartao():
    """O popup com tudo que ele sabe fazer, agrupado."""
    linhas = []
    total = 0
    for grupo, itens in GRUPOS:
        linhas.append(f"— {grupo} —")
        for faz, _exemplo in itens:
            linhas.append(f"• {faz}")
            total += 1
    return {"titulo": "O que eu sei fazer", "destaque": f"{total} habilidades", "linhas": linhas}


def fala():
    return ("Bastante coisa, chefe. Cuido do marketing e das vendas do Porthon, controlo o PC, pesquiso, "
            "mostro o globo e o Olho de Deus, toco música, mando WhatsApp e ainda falo com o Claude. "
            "Botei a lista completa aí na tela.")


def falar_tudo():
    """Lê a lista em voz alta, grupo por grupo (quando ele pede 'me lê/fala as habilidades')."""
    partes = []
    for grupo, itens in GRUPOS:
        coisas = "; ".join(faz for faz, _ in itens)
        partes.append(f"Em {grupo.lower()}: {coisas}.")
    return "Então, chefe, tudo que eu sei fazer. " + " ".join(partes) + " E tá tudo listado aí na tela também."


def para_prompt():
    """Resumo pro prompt do sistema: o Jarvis sabe o que faz e, fora disso, é honesto que ainda não faz."""
    partes = []
    for grupo, itens in GRUPOS:
        partes.append(f"{grupo}: " + "; ".join(faz for faz, _ in itens) + ".")
    corpo = "\n".join(partes)
    return ("O QUE VOCÊ REALMENTE FAZ (só isto; se pedirem algo fora daqui, diga com honestidade que ainda não faz "
            "isso, sem inventar que consegue):\n" + corpo)
