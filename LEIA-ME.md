# J.A.R.V.I.S. da 7 SevenCode

Assistente pessoal que roda inteiro no seu PC: cérebro local (Ollama), voz, reconhecimento facial e abertura com duas palmas.

## Como usar
| Arquivo | O que faz |
|---|---|
| `ligar-jarvis.bat` | Liga o Jarvis escondido. Depois disso, **duas palmas** abrem a janela |
| `abrir-jarvis-sem-palmas.bat` | Abre a janela direto |
| `desligar-jarvis.bat` | Desliga tudo |
| `ligar-junto-com-o-windows.bat` | Faz o Jarvis ligar sozinho quando o PC inicia (rode uma vez) |
| `ajustar-palmas.bat` | Mostra o volume do microfone, para acertar a `sensibilidade` no `config.json` |

**Primeira vez que abrir:** ele cadastra o seu rosto (6 posições, siga o que aparece na tela). A partir daí só abre quando reconhecer você. Para refazer o cadastro, apague `rosto.json`. O arquivo guarda só números do rosto, nenhuma foto, e nunca sai do PC.

Na primeira vez o navegador também pede permissão de **câmera e microfone**: clique em Permitir. Ele lembra, porque a janela do Jarvis usa um perfil próprio do Chrome (`.perfil-navegador`).

## O que ele faz
- Conversa por voz em português. Clique no círculo para mutar ou desmutar o microfone.
- Abre programas e sites na hora ("abre o WhatsApp", "abre o Porthon", "abre o painel 7SevenCode").
- Pesquisa no Google, lista pastas e lê arquivos de texto (só Desktop, Documentos e Downloads; nunca `.env` nem arquivos de senha).
- **Pede autorização** (botão vermelho) antes de rodar comando ou criar arquivo.
- Ao abrir, dá um resumo: a hora, onde parou o Porthon (última publicação e arquivos esperando o pacote) e pergunta o que vamos fazer.
- Aprende: diga "guarda aí que…" e ele salva em `conhecimento/memoria.md`.

## Dormir e acordar
- **Dormir:** "boa noite, Jarvis", "hora do intervalo", "pode se desligar", "vai dormir", "até mais". Ele se despede, a janela fecha e ele continua esperando palmas ou o nome.
- **Desligar de vez** (parar de ouvir também): `desligar-jarvis.bat`.

## Mexer no PC por voz
| Diga | Faz | Pede "sim"? |
|---|---|---|
| "desliga o PC" / "reinicia o computador" | desliga/reinicia em 10 s | sim |
| "suspende" | suspende | sim |
| "cancela o desligamento" | cancela | não |
| "bloqueia a tela" | bloqueia o Windows | não |
| "aumenta/abaixa o volume", "silencia" | volume | não |
| "modo escuro" / "modo claro" | tema do Windows | não |
| "abre as configurações de Wi-Fi / Bluetooth / som / tela / energia / atualização…" | abre a tela certa | não |
| qualquer outra coisa ("muda tal configuração") | o modelo monta um comando PowerShell | sim |

Para confirmar, diga **"sim"** (ou "pode", "confirmo"); para cancelar, **"não"**. Se quiser que ele faça tudo sem perguntar, troque `"confirmar_acoes_perigosas": true` para `false` no `config.json` (não recomendo: um erro de reconhecimento de voz desliga o PC no meio do trabalho).

## Programar junto com o Claude Code
- **"Pergunta pro Claude …"** → o Claude lê o projeto em modo só leitura (não muda nada) e a resposta volta falada, com cartão na tela. Pode continuar conversando com o Jarvis enquanto isso.
- **"Pede pro Claude …"** (criar, arrumar, mudar…) → abre o Claude Code numa janela de terminal, no projeto, com o pedido já digitado. Você acompanha e aprova cada passo por lá.
- **Sempre** o Jarvis lê em voz alta o que entendeu e só manda depois do seu "sim" (a transcrição pode errar).
- Projeto: diga "no Porthon", "no painel", "no radar", "no site", "no planner" ou "no Jarvis". Sem dizer, vai para o último usado (começa no Porthon).

## WhatsApp
- "manda um oi pra minha mãe", "manda pro Jesus que a reunião é às 3", "envia uma mensagem" (ele pergunta pra quem e o quê).
- **Sempre confirma** antes de enviar. Envia pelo WhatsApp Desktop.
- Pessoa nova: ele pergunta "como está salvo no WhatsApp, ou qual o número?". Responda "tá salva como Coroa" ou o número; ele grava em `contatos.json` (mãe → Coroa).
- Pelo **número**, envia direto. Pelo **nome salvo**, na 1ª vez deixa a mensagem digitada e pergunta "foi a conversa certa?"; com o seu "sim" envia e passa a confiar.
- Disparo pros leads é com o Radar (ritmo seguro, sem banir o número).

## Radar / CRM por voz
- Quando um lead responde (a extensão do Radar marca no CRM), ele avisa: "Chefe, o lead X respondeu".
- "marca o lead X como interessado / reunião / fechado / perdido porque …" → confirma e grava no CRM, com o evento na linha do tempo (igual ao Radar).
- "sugere uma resposta pro X" → ele escreve uma sugestão e pergunta se manda no WhatsApp.

## Música
- Sem configurar: "pausa", "continua", "próxima", "volta a música" (teclas de mídia) e "toca X" (abre a busca no Spotify).
- Para ele dar o play sozinho (precisa Spotify Premium): 1) developer.spotify.com/dashboard → Create app → Redirect URI `http://127.0.0.1:8765/spotify/retorno` → marque Web API; 2) crie `spotify.json` aqui com `{"client_id": "o Client ID do app"}`; 3) abra `http://127.0.0.1:8765/spotify/conectar` e autorize.

## Pesquisa e Porthon
- "pesquisa X", "procura no YouTube X" → abre na hora.
- Ao abrir, ele conta o andamento do Porthon (pacote de atualização e pendências) lido da memória do Claude. "Qual foi o último commit do Porthon?" → só então fala de commit.
- Ele lê AO VIVO a memória do Claude e os documentos dos projetos (`fontes.py`), relendo a cada 10 min.

## Internet na tela
"quanto tá o dólar", "vai chover?", "o que é X", "quem foi X", "me mostra fotos de X" → resposta num cartão (com foto quando tem). Preço, receita, hotel, "no Google/YouTube/Opera" → abre o navegador.

## Duas telas e janelas
"abre o YouTube na outra tela", "abre o Notion aqui", "passa o Spotify pra outra tela", "fecha/minimiza/maximiza o Chrome".

## Memória
- Ficha de fatos (`conhecimento/fatos-essenciais.md`): responde na hora o que está lá (piloto, condomínio de teste, equipe…).
- O que você conta de si ("meu carro é…", "eu torço pro…") ele anota sozinho em `conhecimento/memoria.md`.
- Ele lê também a memória do Claude, sempre a versão atual.

## Treino
`python treino.py` confere 131 frases do jeito que você fala (gaúcho, inglês misturado, nomes do Windows em inglês). Achou um erro de entendimento? Acrescente a frase lá com o esperado.

## Quando ele entende errado
- **Corrige sozinho** os erros conhecidos dos seus termos: "seven code" → SevenCode, "lides/lids/leeds" → leads, "porton" → Porthon, "pro cloud" → pro Claude, "jarves" → Jarvis. A lista fica em `vocabulario.py` (FIXOS).
- **Pergunta "Você quis dizer…?"** quando uma palavra *soa* como um termo seu mas não é certeza. "Sim" ensina (da próxima vez corrige sem perguntar); "não" ensina a não insistir.
- **Ensine direto:** "quando eu falar *lídia*, é *leads*".
- O Chrome manda até 5 versões do que ouviu; o Jarvis usa a que vira um comando conhecido.
- Na tela, a sua fala aparece **já corrigida**: dá pra ver o que ele entendeu.
- O que ele aprendeu fica em `vocabulario-aprendido.json` (apagar zera).

## O que ele aprende sozinho (e fica mais rápido)
| O quê | Onde fica | Efeito |
|---|---|---|
| Caminho de cada programa que você pede ("zap" → WhatsApp) | `apps-conhecidos.json` | abre em ~1 ms; o índice de apps se atualiza a cada 30 min |
| Endereço de site que o modelo descobriu | `apps-conhecidos.json` | "abre o X" vai direto da próxima vez |
| Respostas a perguntas | `respostas-aprendidas.json` | a mesma pergunta volta na hora ("errado" apaga a última) |
| Áudio das frases | `voz-guardada/` | frase repetida fala na hora; as fixas já vêm prontas |
| Fatos que você mandar guardar ("guarda aí que…") | `conhecimento/memoria.md` | entra no que ele sabe |

Apagar qualquer um desses arquivos zera só aquele aprendizado.

## O que ele sabe
Tudo em `conhecimento/*.md`: `7sevencode.md` (empresa, projetos, como você trabalha) e `porthon.md` (o documento completo do Porthon). Para ensinar mais, basta criar ou editar um `.md` ali e reabrir o Jarvis.

## Ajustes (`config.json`)
- `modelo`: hoje `qwen2.5:3b`. Ele roda no processador (sua placa de vídeo é integrada), então leva uns 3 s para a primeira palavra e 8 a 15 s quando consulta os documentos. `qwen2.5:1.5b` é mais rápido e mais burro.
- `voz`: `pt-BR-AntonioNeural`, com o tom um pouco mais grave. Precisa de internet (é a voz neural da Microsoft, grátis).
- `palmas.sensibilidade`: se abrir sozinho com barulho, aumente; se não abrir com palma, diminua.

## Limites (honestos)
- A voz não é a do Paul Bettany nem a do dublador: clonar a voz de uma pessoa real sem autorização é imitação. A Antonio grave é o mais perto que fica sem isso.
- O reconhecimento facial é uma trava de conveniência, não de segurança: uma foto boa sua pode enganar.
- Com um modelo de 3B ele não navega sozinho dentro do Porthon, do painel ou do WhatsApp: ele abre esses sistemas pra você. Fazer tarefas lá dentro pede um cérebro mais forte (Claude via API).
- O reconhecimento de voz do Chrome manda o áudio da fala pro Google para transcrever.

## Novidades de 20/10
- **Cérebro na nuvem (Groq, grátis):** crie `groq.json` com `{ "chave": "gsk_..." }` (chave em console.groq.com → API Keys). Com ela ele responde em ~1 s, conversa de verdade, busca na internet, lê sites, calcula e cria planilhas (em Documentos\Jarvis). Sem chave ou sem internet, volta sozinho para o Ollama local.
- **Independente:** roda comandos do PC sozinho; só pede "sim" pra apagar, desligar, matar programa e afins.
- **Segundo plano:** com a tela fechada, diga "Jarvis, <pedido>" — ele dá um bip, faz e responde pela caixa de som, sem abrir nada. "Jarvis, abre a tela" (ou duas palmas) abre o HUD. Precisa da chave da Groq (é ela que transcreve).
- **Rosto e resumo do dia** só na primeira abertura depois de ligar o PC. Depois: "Pois não, chefe?". O resumo volta com "me passa os dados de hoje" / "resumo do dia".
- **Automações (botão ⚙, canto esquerdo):** quando eu disser uma frase / num horário / quando o PC ligar → lista de ações, uma por linha, do jeito que você falaria. Botão Testar roda na hora.
- **Sites abrem na tela vertical** (`"tela_dos_sites": "outra"` no config; `"esta"` deixa na principal; "…aqui" no pedido também).
- **Mandar dormir:** "se desliga", "tchau", "standby", "modo espera", "falou", "vai embora"… ("desliga o PC" segue desligando o PC, com confirmação).
- Voz 12% mais rápida (`voz_velocidade` no config).

## Como o Jarvis aprende (e como ensinar)
**Ele se vira sozinho:** pedido sem habilidade pronta → o cérebro raciocina e usa o que tem (PowerShell, internet, ver a tela, digitar, atalhos, planilha). Se a primeira tentativa falhar, tenta outro caminho.

**Ele aprende sozinho:** quando resolve algo com ferramentas e dá certo, grava o caminho em `habilidades-aprendidas.json` ("caminhos"). Num pedido parecido depois, ele recebe "da última vez deu certo assim" e repete direto, mais rápido e sem errar de novo.
- Fez errado? Diga **"errado"** ou **"esquece isso"** logo depois (até 5 min): ele apaga aquele caminho e pergunta como era.

**Você ensina por voz (vale pra sempre):**
- "Aprende que quando eu pedir o relatório, é pra criar planilha com os leads da semana e abrir."
- "Daqui pra frente, quando eu falar 'tô saindo', bloqueia a tela e pausa a música."
- "Não, o certo é abrir no Opera." (correção vira regra)
- "Esquece a habilidade do relatório."
Essas ficam em "ensinadas" e entram em TODA conversa como regra.

**Atalho de voz:** "quando eu falar bora codar, abre o VS Code e toca Development" → vira automação (aparece no botão ⚙).

**Outras memórias:** "lembra que meu carro é X" (fatos sobre você, em `conhecimento/memoria.md`); frases que ele traduziu (`frases-aprendidas.json`); palavras que ele ouve errado (`vocabulario-aprendido.json`); apps e sites (`apps-conhecidos.json`).

## Novidades de 20/10 (noite)
- **Lembretes:** "me lembra às 15h de ligar pro Jesus", "me lembra em 20 minutos de…", "me acorda em meia hora", "amanhã às 9 me lembra da reunião", "quais meus lembretes", "cancela o lembrete do bolo". Na hora: fala + pop-up (com a tela fechada, ele fala pela caixa de som).
- **Pomodoro:** "inicia um pomodoro", "bora focar 50 minutos", "pausa / volta / cancela o pomodoro", "quanto tempo falta". O modo caverna oferece um. Contagem na extensão.
- **Anotações:** "anota: …", "lê minhas anotações", "apaga a última anotação".
- **Notícias:** "notícias do dia", "notícias de tecnologia", "notícias do Grêmio".
- **Sistemas:** "tá tudo no ar?" (confere os sites; a cada 5 min vigia sozinho e avisa se cair), "o deploy do Porthon subiu?" (Vercel). Sites em `sites_monitorados` no config.
- **PC:** "o PC tá lento?" / "o que tá pesando?". CPU e memória ficam no cantinho da extensão.
- **Clima no globo:** "como tá o tempo em Gramado?".
- **Globo:** estilo holograma; "seleciona o Brasil" / "destaca o RS" pinta o território; "limpa a seleção". Lugares, estabelecimentos ("onde fica o Burger King" pergunta qual), "restaurantes aqui perto" (Google Maps). Casa = `casa` no config.
- **Pop-up rápido some sozinho** (mínimo 12 s, com barrinha); fotos, listas e links ficam até você fechar.

## Novidades de 21/10 (a grande evolução)
Backup antes de tudo: `Desktop\Jarvis-backup-2026-10-21` + git local nesta pasta (`git log` mostra cada etapa; nada vai pra internet).

**Corrigido**
- "Para de me escutar depois de muito tempo": o reconhecimento do Chrome morria calado e o ouvido de fundo achava que a tela estava atendendo. Agora a tela se reanima sozinha (vigia a cada 5 s) e, se você chamar "Jarvis" e a tela não reagir em 2,5 s, o segundo plano atende e manda a tela acordar.
- Spotify não tocava: o app do PC aceita "toca essa faixa" mas não toca. Agora toca pelo álbum começando na faixa (e confere se tocou de verdade). Curtidas tocam em modo aleatório.
- "Procura X no globo" respondia "não achei app chamado globo": globo, mapa, painéis e Olho de Deus são dele — `internos.py` entende na hora.
- "depois" virava "deploy" e ele perguntava "Você quis dizer…?".

**Entender e agir**
- Com o cérebro da nuvem, frase sem atalho vai direto pra ele (uma ida ao modelo, não duas). Atalhos instantâneos continuam (treino 462/462).
- Conversa longa não some mais: vira resumo (`memoria_conversa.py`, guardado em `dados/conversa.json`).
- Diário de tudo que ele fez (`registro.py`): "faz aquilo de ontem", "o que eu te pedi hoje". "Desfaz isso" volta arquivo criado/movido/renomeado/editado.
- Tarefa grande: ele mostra o PLANO e cada passo acende na linha do tempo (rodando/ok/erro); tenta até 3 vezes e depois explica.
- Ferramentas por grupos (base sempre; arquivos, tela, programação, aprender e conectores sob demanda): o pedido ficou mais leve que antes.

**Novas habilidades**
- Pesquisa DENTRO dele: "pesquisa X", "me fala sobre X" → painel com resumo, tópicos, fotos livres (Commons/Openverse/NASA) e fontes; a voz lê e o tópico da vez acende. "mostra mais fotos", "aprofunda isso", "lê a fonte 2" (modo leitura), "abre a fonte 2 no navegador", "amplia a segunda foto", "fixa/fecha esse painel". Navegador só se você pedir.
- Seus arquivos: ele procura em Desktop e Documentos (índice local, 1.400+ arquivos, busca em milissegundos). Arquivos de senha ficam fora.
- PC: mover/copiar/renomear/criar pasta (com desfazer), apagar (vai pra lixeira, sempre com o seu sim), área de transferência, print, brilho, listar janelas, clicar num botão PELO NOME.
- Programação: rodar código numa pasta isolada (com o sim quando mexe fora dela), git (leitura direto, commit/push com o sim), editar arquivo com aprovação mostrando antes/depois, código com realce de sintaxe.
- Música por gênero/clima: "toca um funk", "bota um pagode", "algo pra treinar", "gospel" (as suas playlists primeiro).
- Frases com variação e humor (`falas.py`). Passou de 10 s: ele avisa que tá terminando.

**Olho de Deus** ("modo olho de deus" / "mostra os aviões", "os satélites", "os terremotos", "o clima"; "desliga o olho de deus")
Aviões ao vivo voando em volta de você (adsb.lol), satélites e a ISS (CelesTrak + cálculo de órbita aqui), terremotos 24 h (USGS), clima nas capitais, manchetes no letreiro. Tudo grátis.

**Configurações** (botão de controles ao lado do ⚙): Geral, Modelos (benchmark), Voz, Proatividade (nível, não perturbe, horário de silêncio), Memória (ver/editar/apagar), Privacidade (confirmações, cofre de chaves criptografado, log com desfazer), Automações (o mesmo painel do ⚙), Conectores, Instalação (verificar). Exportar/importar dados pra outro PC.
Por voz: "ativa/desliga o não perturbe". Ele também avisa sozinho se o disco encher ou a CPU/memória ficarem no talo, e sugere automações quando você repete um pedido no mesmo horário ("cria a automação sugerida").

**Conectores** (Configurações → Conectores): cliente MCP (programa local ou servidor remoto, com chave ou login OAuth) + GitHub, Google (Agenda/Gmail/Drive), Telegram. Canva e Notion pelo MCP oficial deles. Chaves só no cofre. O que envia/publica/apaga/gasta pede o sim.

**Não feito (de propósito)** — ia deixar ele pior neste PC sem GPU: proibir os atalhos e passar TUDO por um modelo local de 1.7B; trocar o Groq pelos modelos locais; trocar a voz Antonio e o Whisper da Groq por Piper/faster-whisper; clicar por coordenada com modelo de visão. O benchmark mediu 3–4 tokens/s nos modelos locais contra ~2 s de resposta da nuvem: o local segue como reserva (qwen2.5:3b, escolhido pelo benchmark).

## Novidades de 21/10 (2ª rodada)
- **Duas telas**: informação curta aparece na tela principal; pesquisa, notícias e páginas na vertical. "Passa isso pra outra tela", "traz pra cá". "Beleza, pode fechar" fecha o que está na tela (não o Jarvis).
- **Olho de Deus**: "desativa o olho de deus", "volta o globo ao normal" / "tira o zoom", "mostra os aviões sobrevoando o Brasil" (qualquer região; os aviões vão aparecendo conforme o radar varre).
- **Globo de verdade**: roda do mouse dá zoom; "mostra o globo real" / "camadas da terra" = foto de satélite sem nuvens (dá pra chegar até a rua); "mostra as nuvens" = nuvens reais de ontem (NASA); "modo holograma" volta.
- **Clique pra selecionar**: país → estado (no Brasil) → cidade. Depois: "me fala desse país", "procura pizzaria nessa cidade".
- **Notícias**: "notícias de hoje", "notícias de economia", "o que tá rolando sobre o Lula": ele conta uma por uma com a foto da matéria; "abre a notícia 2" abre a página do site dentro dele e ele conta a matéria.
- **Estabelecimentos**: "mostra os Burger King", "restaurantes em Gramado", "farmácias aqui perto", depois "só no centro". Clique num pino: nome, endereço e foto. Foto da loja igual à do Google: Configurações → Privacidade → Cofre → "Chave do Google Places" (precisa de projeto no Google Cloud com faturamento ativo; uso pessoal fica na cota grátis). Sem a chave: foto de satélite da quadra.
- **Canva e Notion em um clique**: Configurações → Conectores → Conectar → autoriza no navegador. Sem Client ID.

- **Música do artista** (21/10): "toca Tempo Perdido da Legião Urbana", "bota Evidências do Chitãozinho e Xororó" — ele separa música e artista e confere no Spotify. "Pagode gospel" / "Pagode Restaura" viraram gênero. "Pórton" falado = Porthon.

## Marketing do Porthon (23/10)
O Jarvis cria as postagens do Porthon no padrão da marca, pela voz da IA que ele já usa (Groq/Gemini). Fale:
- **"cria um post pro Porthon sobre encomendas"** / "faz uma arte sobre a LGPD" / "escreve uma legenda sobre reserva de salão": ele escreve o gancho da arte, a linha de apoio, a legenda pronta e as hashtags; salva em `conteudo/porthon/`, **copia a legenda** pra área de transferência e **abre o Canva** pra você montar a arte e aprovar. Sem tema, ele rodízia os pilares de conteúdo.
- **"monta a pauta da semana do Porthon"**: 7 posts com dia, tema e gancho.
- **"monta um plano de marketing"** (ou "…com 1 post por semana, na quinta"): o plano do tamanho que você pedir, com lembretes nos dias/horários.

**Tudo isso é editável (24/10)** — nada fica fixo no que a IA escolheu. O plano, a pauta e o último post ficam guardados (`conteudo/porthon/*-atual.json`) e você muda falando: "deixa só um post", "tira o de quinta", "passa o de terça pra 20h", "adiciona um post no domingo às 21h sobre reservas", "troca o tema de quarta pra ocorrências", "mostra o plano de marketing", "apaga esse plano" (apaga os lembretes junto). No post: "troca o título", "deixa a legenda mais curta", "muda o CTA pra…". Na mão: **Configurações → Marketing** (dia, horário, formato, tema, gancho, tirar/adicionar; ao salvar os lembretes acompanham). Nas **Falas programadas** agora tem botão **Editar**. Em vendas: depois de uma mensagem, "deixa ela mais curta", "mais formal", "sem emoji" reescreve a mesma.
A identidade (tom, público, regras: nada de número/preço inventado, zero cara de robô) está em `marketing.py` → `IDENTIDADE`/`PILARES` — mexer ali muda o tom de tudo. Nunca posta sozinho no Instagram (publicar automático exige conta Business + app aprovado pela Meta): deixa pronto pra você publicar com um toque.

**Canva automático (opcional):** com o Canva conectado (Configurações → Conectores) e **Canva Pro**, dá pra ele já preencher a arte sozinho. Ligue uma vez no `config.json`: `"canva_autofill_automatico": true`, `"canva_template_post": "<id do brand template>"` e `"canva_campos": {"gancho":"<campo do título>","apoio":"<campo de apoio>"}`. Sem isso, segue o caminho manual (abrir o Canva com a legenda pronta). Opcional também: `"canva_template_url"` pra abrir direto o seu modelo em vez da página de criar.
