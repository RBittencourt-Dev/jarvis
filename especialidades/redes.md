# Redes — conceitos que o técnico precisa dominar

Rede é um monte de aparelhos conversando por um endereço. O essencial:
- **IP**: o endereço do aparelho na rede (ex.: 192.168.0.15). Privado (dentro da escola) começa com 192.168.x.x, 10.x.x.x
  ou 172.16–31.x.x. Público é o que a operadora dá pro link (vale pra internet inteira).
- **Máscara / prefixo** (ex.: 255.255.255.0 = /24): diz quais IPs estão "na mesma rede". /24 = os 254 endereços .1 a .254.
- **Gateway**: a porta de saída pra internet — quase sempre o roteador (ex.: 192.168.0.1). `ipconfig` mostra o seu.
- **DNS**: traduz nome (google.com) em IP. Bons públicos: 8.8.8.8 e 8.8.4.4 (Google), 1.1.1.1 (Cloudflare).
- **DHCP**: o roteador entregando IP automático pros aparelhos. IP começando com **169.254.x.x = não pegou DHCP** (cabo/switch/roteador).
- **MAC**: o "número de série" da placa de rede (ex.: A4-BB-6D-...). Fixo por aparelho; os 3 primeiros pares dizem o fabricante (OUI).
- **Porta**: o "ramal" de um serviço no IP (80 = site HTTP, 443 = HTTPS, 554 = câmera RTSP, 445 = compartilhamento, 3389 = RDP).
- **TCP x UDP**: TCP garante entrega (site, arquivo); UDP é rápido e sem garantia (vídeo ao vivo, voz).
- **LAN / WAN / VLAN**: LAN é a rede local (escola); WAN é a internet/link; VLAN separa redes no mesmo switch (ex.: VLAN
  administrativa x VLAN de alunos), sem precisar de cabo/switch separado.

# Como a rede de uma escola costuma ser montada

Internet da operadora → **modem/ONT** → **roteador/firewall** (faz DHCP, NAT, Wi-Fi ou manda pros APs) → **switch(es)** no
rack → cabos até salas, secretaria, laboratório, câmeras, impressoras e **pontos de acesso Wi-Fi (APs)**. Boas práticas:
rack organizado e identificado, nobreak no rack/servidor/roteador, rede administrativa separada da de alunos/visitantes (VLAN),
IP fixo pro que é "servidor" (impressora, câmera, NVR, servidor de arquivos) fora da faixa do DHCP.

# Descobrir o que tem na rede (mapear)

- `ipconfig /all` → seu IP, máscara, gateway, DNS, MAC. É o ponto de partida.
- `arp -a` → tabela de quem o PC já "viu" na rede (IP ↔ MAC). Encha ela primeiro pingando a faixa.
- Varredura (ping sweep) da faixa /24: pingar .1 até .254 e ver quem responde; depois `arp -a` dá o MAC de cada um.
  No PowerShell: `1..254 | ForEach-Object { Start-Job { ping -n 1 -w 200 192.168.0.$using:_ } } | Wait-Job | Receive-Job`
  (ou mais simples, deixe o Jarvis fazer: "acha os aparelhos da rede").
- `Get-NetNeighbor -AddressFamily IPv4` → cache de vizinhos (IP, MAC, estado) — jeito moderno do `arp -a`.
- Nome do aparelho: `nslookup <ip>` (DNS reverso) ou `nbtstat -A <ip>` (nome NetBIOS/Windows).
- Ferramentas prontas e grátis: **Advanced IP Scanner** (Windows, acha IP/nome/MAC/fabricante/compartilhamentos),
  **Angry IP Scanner**, **Fing** (celular), e **nmap** (o mais completo: `nmap -sn 192.168.0.0/24` lista quem está vivo;
  `nmap -p 80,443,554,8000,37777 192.168.0.0/24` acha portas de câmera/serviço). Use só na rede que você administra.
- Identificar pelo fabricante (MAC): câmeras costumam ser Intelbras, Hikvision, Dahua; roteadores TP-Link, Mikrotik,
  Ubiquiti; celulares Apple/Samsung. O fabricante no MAC é uma boa pista do que é cada IP.

# Entrar / acessar o roteador e os equipamentos

- **Roteador/firewall**: abra o navegador no IP do gateway (`ipconfig` → "Gateway Padrão", ex.: 192.168.0.1 ou 192.168.1.1).
  Login padrão vem na etiqueta embaixo do aparelho (comum: admin/admin, admin/senha do Wi-Fi). **Troque a senha padrão** —
  é a falha nº 1. Lá você vê/edita: Wi-Fi, DHCP, reservas de IP por MAC, redirecionamento de portas, firmware, horário.
- **Switch gerenciável** (Mikrotik/Ubiquiti/TP-Link gerenciável): acessa por navegador no IP dele, ou por app (UniFi) /
  Winbox (Mikrotik). É onde se configuram VLANs e portas.
- **Access Points (APs)**: em rede gerenciada (UniFi/Omada/Aruba) o controlador cuida de todos juntos (um SSID, roaming).
- **Achar o IP de um aparelho "perdido"** (impressora/câmera/NVR que trocou de IP): varra a rede (acima), ou veja no
  próprio aparelho (impressora imprime página de config; câmera/NVR mostra no menu na TV), ou procure pelo MAC/fabricante.
- **Sempre**: depois de achar, fixe o IP (reserva por MAC no roteador) pra ele não "sumir" de novo.

# Wi-Fi

- Bandas: **2.4 GHz** alcança mais longe e atravessa parede, mas é lento e cheio de interferência; **5 GHz** é rápido e
  limpo, mas alcance menor. Em escola, 5 GHz pras salas com AP próximo.
- Canais: no 2.4 GHz use **1, 6 ou 11** (não sobrepõem). Canais lotados = Wi-Fi caindo; um analisador (app WiFiAnalyzer) mostra.
- Segurança: **WPA2** ou **WPA3**, senha forte. Desligue **WPS** (é inseguro). Separe **rede de visitantes** da administrativa.
- Muitos alunos num AP só = lentidão: precisa de mais APs (gerenciados, com roaming) distribuídos, não um roteador doméstico.
- Esqueceu/mudou a senha do Wi-Fi: muda no roteador (seção Wireless) e reconecta os aparelhos; a senha salva num PC aparece
  em `netsh wlan show profile name="SSID" key=clear` (linha "Conteúdo da Chave").

# Câmeras, DVR e NVR

- **Câmera IP**: tem IP próprio na rede. Acessa pelo navegador no IP dela (usuário/senha da câmera) ou pelo app do
  fabricante. Portas comuns: **80/443** (interface web), **554** (RTSP, o fluxo de vídeo), **8000/8899/37777/34567**
  (apps/protocolos de DVR — Hikvision 8000, Dahua 37777, genéricas 34567).
- **DVR** (câmeras analógicas por cabo coaxial) e **NVR** (câmeras IP pela rede): o gravador junta tudo; acessa pela TV
  conectada nele, pelo navegador no IP do gravador, ou por app (iDMSS/gDMSS da Dahua/Intelbras, Hik-Connect da Hikvision).
- **RTSP** (ver o vídeo em VLC/sistema): `rtsp://usuario:senha@IP:554/caminho` — o caminho muda por marca (Intelbras:
  `/cam/realmonitor?channel=1&subtype=0`; Hikvision: `/Streaming/Channels/101`; Dahua parecido com Intelbras).
- **Achar as câmeras na rede**: varra a faixa e procure IPs com porta **554** aberta, ou MAC de Intelbras/Hikvision/Dahua,
  ou use o app do fabricante que descobre sozinho (Intelbras IP Utility, SADP da Hikvision, ConfigTool da Dahua).
- **Segurança (crítico)**: **troque a senha padrão** de toda câmera/DVR (admin/admin e 12345 são alvo fácil); NÃO exponha a
  câmera direto na internet com porta aberta — use o app oficial (P2P/nuvem) ou VPN; mantenha o firmware atualizado.
- **Esqueceu a senha (recuperar, é legítimo quando o aparelho é seu)**: NÃO existe ver a imagem sem login — autenticação é
  obrigatória por design, mesmo na mesma rede; "burlar" não é o caminho. O certo é recuperar:
  - **DVR/NVR Intelbras (MHDX/NVD)**: na tela de login do próprio gravador (monitor+mouse nele) tem **"Esqueci a senha"** →
    responde as **perguntas de segurança**, ou ele gera um **QR code/código**; abre o app **Intelbras ISIC/Defense** (ou manda
    pro suporte Intelbras com a nota/prova de posse) e recebe uma **senha temporária do dia** pra entrar e redefinir.
  - **Câmera IP Intelbras avulsa**: **Intelbras IP Utility** acha a câmera e oferece **reset de senha** por código/data; ou o
    **botão de reset físico** (segurar ~10-15 s) volta ao padrão de fábrica (cria senha nova no 1º acesso).
  - Se havia **e-mail cadastrado** no aparelho, o reset sai por e-mail. Padrão de usuário costuma ser **admin**.
  - Hikvision usa o **SADP** (código de reset por data/serial); Dahua o **ConfigTool** — mesma lógica da Intelbras.

# Compartilhamento de arquivos (pastas de rede)

- Protocolo **SMB**. Acessa uma pasta compartilhada por `\\nome-ou-IP-do-PC\pasta` no Explorer ou `net use`.
- Ver compartilhamentos de um PC: `net view \\IP` (ou `net view` lista os computadores). As pastas que ESTE PC compartilha:
  `Get-SmbShare`.
- Mapear como unidade: `net use Z: \\servidor\pasta /persistent:yes` (pede usuário/senha se tiver permissão).
- **Permissão** manda: "Compartilhamento" (quem vê pela rede) + "Segurança/NTFS" (quem pode ler/gravar). A mais restritiva vence.
- Compartilhar impressora: melhor por **IP fixo** (porta TCP/IP) do que presa num PC que precisa ficar ligado.

# Acesso remoto

- **AnyDesk / TeamViewer**: controle de tela fácil; a versão grátis é pra uso pessoal (a comercial derruba a sessão).
- **RDP** (Área de Trabalho Remota, porta 3389): nativo do Windows Pro; dentro da rede é ótimo. **Nunca** abra o 3389
  direto na internet (alvo de ataque) — use **VPN** pra entrar na rede primeiro.
- **VPN**: cria um "túnel" seguro de fora pra dentro da rede da escola (no próprio firewall/roteador, ou WireGuard/OpenVPN).
  É o jeito certo de acessar câmeras, servidor e PCs de casa.
- **Redirecionamento de porta (port forwarding)** no roteador expõe um serviço interno à internet: poderoso e **arriscado** —
  prefira VPN ou o app em nuvem do fabricante.

# Diagnóstico de rede (passo a passo)

1. `ipconfig /all` — tem IP válido? (169.254 = sem DHCP; 0.0.0.0 = sem link).
2. `ping 127.0.0.1` — a placa de rede responde (pilha TCP/IP ok)?
3. `ping <gateway>` (ex.: 192.168.0.1) — chega no roteador? Não → cabo/Wi-Fi/switch/porta.
4. `ping 8.8.8.8` — tem internet (saída)? Não, mas o gateway responde → link da operadora/roteador.
5. `ping google.com` — se o 8.8.8.8 responde e o nome não, é **DNS**: troque pra 8.8.8.8 / 1.1.1.1.
6. `tracert google.com` mostra onde a rota para; `pathping` mede perda por salto; `nslookup nome` testa o DNS.
- Reset da pilha quando nada resolve: `ipconfig /release` → `/renew` → `ipconfig /flushdns` → `netsh winsock reset` →
  `netsh int ip reset` → reiniciar.
- **Conflito de IP** ("outro dispositivo está usando este endereço"): dois aparelhos com o mesmo IP fixo — dê IPs fixos
  fora da faixa do DHCP ou reserve por MAC.
- Cabo: padrão T568B, Cat5e/Cat6, máximo 100 m; testador mostra par rompido. Luz piscando no conector = link ativo.

# Segurança de rede (sempre defensivo)

- Trocar TODA senha padrão (roteador, switch, AP, câmera, DVR, impressora com web).
- Segmentar: VLAN/SSID separados pra administrativo, alunos e visitantes; o aluno não enxerga o servidor nem as câmeras.
- Firewall ligado, firmware atualizado, WPS desligado, acesso de administração do roteador só pela rede interna (não pela WAN).
- Filtro de conteúdo (DNS tipo OpenDNS/Cloudflare for Families, ou no firewall) pra escola.
- Senha forte WPA2/WPA3; monitorar quem conecta; desativar portas de switch que não se usam.
- Backup 3-2-1 do servidor/arquivos; nobreak nos equipamentos críticos.

# Limite ético (importante)

Tudo aqui é pra administrar e proteger a **rede que o Rafael cuida** (a escola), com autorização — achar aparelhos,
acessar o roteador/câmeras da escola, resolver problema, fechar brecha. **Nunca** usar isso pra invadir, acessar ou
bisbilhotar rede, câmera, Wi-Fi ou aparelho de terceiros sem permissão — além de errado, é crime (invasão de dispositivo,
Lei 12.737 e Marco Civil). Na dúvida, é defensivo: proteger o que é dele, não atacar o que é dos outros.
