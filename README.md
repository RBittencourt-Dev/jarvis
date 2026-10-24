# J.A.R.V.I.S.

Assistente pessoal por voz para Windows: conversa, controla o PC, pesquisa e mostra tudo dentro dele (globo 3D,
Olho de Deus, notícias com foto, painéis), toca música no Spotify e se conecta a apps (MCP, Google, GitHub, Canva…).

O uso do dia a dia está no [LEIA-ME.md](LEIA-ME.md). Este arquivo é só a **instalação em um PC novo**.

## Instalar (Windows 10/11)

1. Baixe o código:
   ```
   git clone https://github.com/RBittencourt-Dev/jarvis.git
   ```
   (sem Git: em "Code → Download ZIP" funciona também, mas aí ele não se atualiza sozinho)
2. Dê **duplo clique em `instalar.bat`**. Ele:
   - instala o Python e o Git se faltarem (pelo winget, só pro seu usuário, sem precisar de administrador);
   - cria o ambiente do Jarvis e instala as bibliotecas;
   - cria o atalho **Jarvis** na área de trabalho e abre o Jarvis.
3. Na primeira vez abre o **assistente de configuração** dentro do Jarvis:
   - seu nome, cidade, o nome deste PC e **o que ele faz aqui** (ex.: "PC do colégio: revisar o 7planner");
   - se este PC usa reconhecimento facial e se liga junto com o Windows;
   - a **chave do Groq** (grátis, em https://console.groq.com/keys): cérebro rápido e ouvido;
   - os downloads (ouvido do "Jarvis", modelo local do Ollama), com barra de progresso. Se a internet cair,
     continuam de onde pararam;
   - o que precisa instalar à mão (Ollama, Chrome, Node) mostra o link oficial e o botão "Já instalei, verificar de novo";
   - a máquina é analisada (RAM, CPU, placa de vídeo) e o modelo local certo é recomendado.

Pronto: é só chamar "Jarvis".

## Atualizar

Configurações → Instalação → **Verificar atualizações** (ou fale: "tem atualização?" / "se atualiza").
Ele baixa do GitHub, avisa "Chefe, tudo pronto, subindo atualização!" e reinicia. **Nada seu é apagado**: memória,
chaves, configurações e o que ele aprendeu ficam fora do código (estão no `.gitignore`).

## Levar seus dados para outro PC

Configurações → Geral → **Exportar meus dados** (um .zip) → no outro PC, **Importar**. Vão a memória, o conhecimento,
as habilidades, contatos e automações. O que é de cada PC (perfil, modelo local, reconhecimento facial) não é trocado.
As chaves **não** vão: o cofre é criptografado pelo Windows e só abre no PC onde foi criado. No PC novo, cole de novo.

## HUD (visual)

O HUD (tela do Jarvis, `web/`) segue a referência `jarvis_hud.json`: tema ciano `#00E5FF` com âmbar/vermelho/verde
para aviso/perigo/ok, fontes **Orbitron** (títulos e números) e **Share Tech Mono** (código/relógio), ambas locais em
`web/vendor/fonts/` (offline), e scanlines finas por cima. O núcleo é um **arc reactor** desenhado em canvas (`web/arc-reactor.js`, fiel ao `jarvis_core` JSON do Rafael): 8 camadas
(HUD externo, anel técnico, ticks radiais, dois anéis de energia, anel mecânico, raios internos e núcleo concêntrico),
com "JARVIS" escrito no meio, partículas, varredura e ignição na abertura. Reage ao áudio pelo `--nivel`. A cor fica
sempre ciano (só o MOVIMENTO muda por estado — pulso ao ouvir, giro acelerado ao pensar); vermelho só em alerta/segurança
(há um interruptor `CORES_DE_ESTADO` pra ligar as cores verde/âmbar/azul do JSON, se um dia quiser). O holograma 3D aparece no palco central. Nos quatro cantos ficam painéis fixos ao
vivo — **SISTEMA** (CPU/RAM/GPU/disco/temp/bateria), **REDE** (download/upload/ping/dispositivos), **VISÃO** (câmera,
ainda stub) e **HOJE** (relógio, clima de Porto Alegre via open-meteo, notícias do G1) — servidos por `hud_paineis.py`
em `/api/hud` e desenhados por `web/hud-paineis.js`. Os cartões transitórios continuam aparecendo no miolo.
Tudo responsivo (PC, monitor em pé, janela pequena/celular). O "modo leve" (Configurações → Geral) desliga os efeitos
pesados. Evoluindo em passos; ver progresso nos commits "HUD:".

## O que fica fora do repositório

`config.json` (cada PC tem o seu, nasce do `config.padrao.json`), `dados/` (cofre, diário, índice, caches),
`conhecimento/*.md`, rosto, logins, tokens, memória e tudo que ele aprende, `.venv/`, `modelos/` e os perfis do navegador.

## Requisitos

- Windows 10 ou 11, microfone, Chrome ou Edge.
- Internet para o cérebro na nuvem (Groq, grátis). Sem internet ele usa o Ollama, se estiver instalado.
- Linux/macOS: não suportado (usa APIs do Windows).
