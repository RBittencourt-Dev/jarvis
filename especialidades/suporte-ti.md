# Suporte técnico de T.I — como pensar

Primeiro ISOLAR o problema: é só um PC ou vários? Só um usuário ou todos? Começou depois de quê (atualização, troca de cabo,
queda de energia)? Reproduz sempre ou às vezes? Anotar a mensagem de erro exata (foto da tela). Do mais simples pro mais
complexo: cabo, energia e reinício resolvem boa parte. Mexer numa coisa por vez e testar. Antes de formatar ou apagar,
fazer backup. Registrar o que foi feito (chamado) pra próxima vez.

# PC não liga ou desliga sozinho

- Não liga nada: tomada, filtro de linha, botão da fonte atrás (I/O), cabo de força. Notebook: carregador e LED de carga;
  segurar o botão 30 s sem bateria/carregador pra descarregar.
- Liga mas sem imagem: cabo de vídeo (HDMI/DisplayPort/VGA) na placa de vídeo dedicada e não na placa-mãe; monitor na
  entrada certa (Input/Source); reencaixar memória RAM (limpar contato com borracha); bipes da placa-mãe indicam o defeito.
- Desliga sozinho: superaquecimento (poeira no cooler, pasta térmica velha), fonte fraca ou com defeito.
- Fica reiniciando / tela azul (BSOD): anotar o código (ex.: MEMORY_MANAGEMENT = memória; INACCESSIBLE_BOOT_DEVICE =
  disco/modo SATA; DRIVER_IRQL = driver). Testar memória com "Diagnóstico de Memória do Windows" (mdsched). Disco:
  `chkdsk C: /f` e ver a saúde com CrystalDiskInfo. Entrar no Modo de Segurança (Shift + Reiniciar → Solução de problemas
  → Opções avançadas → Configurações de inicialização) e remover o driver/atualização que causou.

# PC lento

- Gerenciador de Tarefas (Ctrl+Shift+Esc): ver CPU, memória e disco em 100%; fechar o que pesa.
- Programas que iniciam com o Windows: Gerenciador de Tarefas → Aplicativos de inicialização → desabilitar o desnecessário.
- Disco cheio: Configurações → Sistema → Armazenamento → Limpeza; `cleanmgr`; apagar %temp%.
- HD mecânico é o maior gargalo: trocar por SSD resolve muito. Pouca RAM (4 GB) com Windows 11 e Chrome fica lento: 8 GB+.
- Vírus/adware: Windows Security → verificação completa; Malwarebytes. Extensões estranhas no navegador.
- Reparar o Windows: `sfc /scannow` e depois `DISM /Online /Cleanup-Image /RestoreHealth` (prompt como administrador).
- Último recurso: Configurações → Sistema → Recuperação → Restaurar o PC (mantendo arquivos).

# Windows: atalhos e ferramentas úteis

- Win+R abre o Executar: `devmgmt.msc` (drivers), `services.msc` (serviços), `appwiz.cpl` (desinstalar), `ncpa.cpl`
  (adaptadores de rede), `control printers` (impressoras), `eventvwr` (logs de erro), `msconfig`, `diskmgmt.msc`.
- Driver com ponto de exclamação no Gerenciador de Dispositivos: atualizar pelo site do fabricante (Dell, Lenovo, HP,
  Positivo, Intel, Realtek) em vez do genérico.
- Windows Update travado: parar `wuauserv` e `bits`, apagar C:\Windows\SoftwareDistribution, iniciar de novo.
- Usuário esqueceu a senha local: outra conta admin → Gerenciamento do computador → Usuários. Conta Microsoft: redefinir
  pelo site account.live.com.
- Ativação: `slmgr /xpr` mostra o status.

# Rede e internet

- Sem internet em um PC só: cabo (luz do conector piscando), Wi-Fi certo, "esquecer a rede" e reconectar.
  `ipconfig /all` → IP começando com 169.254 = não pegou IP do DHCP (problema no cabo, switch ou roteador).
  Comandos: `ipconfig /release`, `ipconfig /renew`, `ipconfig /flushdns`, `netsh winsock reset`, `netsh int ip reset`
  e reiniciar. Configurações → Rede → Redefinição de rede (último recurso, reinstala adaptadores).
- Testes em ordem: `ping 127.0.0.1` (placa), `ping <gateway>` (roteador, ex. 192.168.0.1), `ping 8.8.8.8` (internet),
  `ping google.com` (DNS). Se o 8.8.8.8 responde e o google.com não, é DNS: usar 8.8.8.8 / 1.1.1.1.
  `tracert google.com` mostra onde para. `nslookup` testa o DNS.
- Sem internet em vários/todos: roteador/modem (reiniciar, ver luzes), link da operadora, switch central, cabo do
  rack, DHCP esgotado (muitos aparelhos, aumentar o pool ou diminuir o lease).
- Conflito de IP ("outro dispositivo está usando este endereço"): impressoras, câmeras e servidores com IP FIXO fora da
  faixa do DHCP ou reservado por MAC no roteador.
- Wi-Fi fraco/caindo: distância e paredes, interferência no 2.4 GHz (usar 5 GHz), canais sobrepostos, muitos clientes
  num ponto de acesso; em escola usar APs gerenciados (UniFi, Omada, Aruba) com roaming e rede de visitantes separada.
- Segurança de rede de escola: rede administrativa separada da rede de alunos/visitantes (VLAN), senha forte WPA2/WPA3,
  filtro de conteúdo (DNS como OpenDNS/Cloudflare Family ou firewall), atualizar o firmware do roteador.
- Cabo de rede: padrão T568B, categoria 5e/6, máximo 100 m. Testador de cabo mostra par rompido.

# Impressoras

- Não imprime: está ligada, com papel, sem erro no visor, online (não "Usar impressora offline")? Cabo/Wi-Fi.
- Fila travada (o mais comum): no prompt como admin: `net stop spooler`, apagar tudo de
  C:\Windows\System32\spool\PRINTERS, `net start spooler`. Ou services.msc → Spooler de impressão → Reiniciar.
- Impressora de rede "offline": ela trocou de IP. Imprimir a página de configuração (segurar o botão ou menu) e ver o IP;
  fixar o IP (reserva no roteador) e adicionar a porta TCP/IP com esse IP no PC. Testar com `ping <ip da impressora>`.
- Driver: baixar o completo do fabricante (HP, Epson, Brother, Canon, Samsung, Ricoh, Kyocera); remover os antigos em
  Gerenciamento de Impressão (printmanagement.msc).
- Papel atolado: desligar, abrir as tampas e puxar o papel no sentido da saída, sem rasgar; ver se sobrou pedaço.
- Impressão falhada/riscada: limpeza de cabeça (jato de tinta, Epson EcoTank), trocar/agitar o toner (laser), cilindro
  (drum) gasto dá risco repetido.
- Epson com "almofadas cheias": precisa do reset das almofadas (Adjustment Program/serviço autorizado) e trocar as almofadas.
- Scanner pra e-mail/pasta parou: senha do e-mail mudou ou a pasta compartilhada mudou de permissão.
- Compartilhar a impressora: melhor pela rede (IP) do que compartilhada por um PC que precisa ficar ligado.

# Projetor, som e sala de aula

- Projetor sem imagem: entrada certa (HDMI1/HDMI2/VGA), Win+P → Duplicar/Estender, cabo e adaptador; resolução 1280x800
  ou 1920x1080. Imagem amarelada/escura: lâmpada no fim.
- Sem som: dispositivo de saída certo (ícone do som), volume do app, cabo P2/HDMI levando o som, mixer de volume.
- Microfone não funciona: Configurações → Privacidade → Microfone permitido pros apps; dispositivo de entrada certo.

# Chromebooks e Google Workspace for Education

- Chromebook lento ou travando: fechar abas, reiniciar, atualizar (Configurações → Sobre o ChromeOS).
- Powerwash (volta ao padrão, apaga dados locais): Ctrl+Alt+Shift+R. Em Chromebook da escola (gerenciado) ele
  reinscreve sozinho no domínio.
- Recuperação (sistema corrompido): Esc + Atualizar (↻) + Power, e o pendrive de recuperação feito pelo app
  "Utilitário de recuperação do Chromebook".
- Não carrega: carregador USB-C certo, deixar 30 min carregando; reset de hardware: Atualizar + Power.
- Gerenciamento: Google Admin (admin.google.com) → Dispositivos → Chrome: políticas, apps forçados, bloquear sites,
  desativar/reativar aparelho perdido, ver último usuário.
- Contas de alunos/professores: Admin → Usuários: redefinir senha, unidade organizacional (OU) por turma.
- Carrinho de Chromebooks: numerar cada um e controlar retirada/devolução (agenda de Chromebooks no 7planner).

# Office, e-mail e contas

- Office pedindo ativação: entrar com a conta da escola (Microsoft 365 Education) em Arquivo → Conta.
- Outlook não sincroniza: reiniciar, reparar o perfil (Painel de Controle → Email), modo de cache.
- Senha: nunca pedir a senha do usuário por chat; redefinir pelo admin. Ativar verificação em 2 etapas.
- Golpe/phishing: e-mail pedindo senha, boleto ou "sua conta será bloqueada" — não clicar, avisar o T.I, trocar a senha
  se clicou.

# Manutenção preventiva e boas práticas

- Backup 3-2-1: 3 cópias, 2 mídias, 1 fora (nuvem: Google Drive/OneDrive da escola).
- Atualizações do Windows e antivírus em dia; contas de alunos sem privilégio de administrador.
- Limpeza física a cada 6-12 meses (ar comprimido), nobreak nos equipamentos críticos (servidor, rack, roteador).
- Inventário: patrimônio, modelo, sala, IP, data de compra.
- Chamados: registrar quem pediu, problema, solução e tempo — mostra o volume de trabalho do T.I.
