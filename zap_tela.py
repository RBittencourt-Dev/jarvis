"""O WhatsApp Desktop "lido" por acessibilidade (UI Automation): achar contatos, abrir a conversa certa e enviar.

Pedido dele (22/10): "identifica meus contatos, eu escolho qual, e ele aprende". Antes o Jarvis só mandava por
número ou abria o 1º resultado da busca às cegas. Agora:
  procurar("Rihan")            → [{"nome": "Rihan Bittencourt", "tipo": "conversa"}, {"nome": "Rihan Crepes", …}]
  enviar("Rihan Bittencourt", "oi") → busca, clica no resultado com ESSE nome, confere no topo da conversa
                                       que abriu a certa e só então cola o texto e aperta Enter.
O WhatsApp novo é uma página (WebView2): os nomes aparecem pra acessibilidade como DataItem/Text.
Nunca envia se não conseguiu conferir o nome da conversa aberta.
"""
import re
import time
import unicodedata

try:
    import uiautomation as auto
except ImportError:  # PC sem a biblioteca: o whatsapp.py cai no jeito antigo
    auto = None

BUSCA = "Search or start a new chat"
NOMES_DA_BUSCA = ("Pesquisar ou começar uma nova conversa", "Pesquisar ou iniciar uma nova conversa", BUSCA)
SECOES = {"chats": "conversa", "conversas": "conversa", "contacts": "contato", "contatos": "contato",
          "groups in common": "grupo", "grupos em comum": "grupo", "messages": None, "mensagens": None}
NAO_E_NOME = re.compile(r"^\d+\s+(?:unread|mensage|n[aã]o lida)|^(?:pinned|fixad|muted|silenciad)", re.I)


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn").strip()


def disponivel():
    return auto is not None


def _janela():
    if not auto:
        return None
    w = auto.WindowControl(searchDepth=1, Name="WhatsApp")
    if not w.Exists(1):
        w = auto.WindowControl(searchDepth=1, RegexName=r"^(?:\(\d+\)\s*)?WhatsApp$")
    if not w.Exists(1):
        import os
        os.startfile("whatsapp:")
        w = auto.WindowControl(searchDepth=1, Name="WhatsApp")
        if not w.Exists(10):
            return None
        time.sleep(2)
    try:
        w.SetActive()
    except Exception:
        pass
    time.sleep(0.4)
    return w


def _campo_de_busca(w):
    # com texto dentro o campo perde o nome (o nome é o placeholder): o 1º campo "html-input" da página é a busca
    c = w.EditControl(searchDepth=30, Compare=lambda c, _: c.ClassName.startswith("html-input") or c.Name in NOMES_DA_BUSCA)
    return c if c.Exists(4) else None


def _frente(w):
    """Traz o WhatsApp pra frente e CONFERE (o Windows não deixa programa de fundo roubar o foco: o Alt libera).
    Sem isso as teclas iam pra outra janela."""
    import ctypes
    u = ctypes.windll.user32
    h = w.NativeWindowHandle
    for _ in range(3):
        if u.IsIconic(h):
            u.ShowWindow(h, 9)
        u.keybd_event(0x12, 0, 0, 0)
        u.keybd_event(0x12, 0, 2, 0)
        u.SetForegroundWindow(h)
        time.sleep(0.35)
        if u.GetForegroundWindow() == h:
            return True
    return False


def _valor(controle):
    try:
        return (controle.GetValuePattern().Value or "").strip()
    except Exception:
        return None


def _focar(w, controle, confere=None):
    """WhatsApp na frente + clique no campo. (O foco dentro da página não aparece pra acessibilidade: quem confere
    é a leitura do texto do campo depois de colar.)"""
    if not _frente(w):
        return False
    controle.Click(simulateMove=False)
    time.sleep(0.3)
    return True


def _e_busca(c):
    return c.ControlTypeName == "EditControl" and (c.ClassName.startswith("html-input") or c.Name in NOMES_DA_BUSCA)


def _e_caixa(c, nome=None):
    m = CAIXA.match((c.Name or "").strip())
    return bool(m) and (nome is None or (m.group("quem") and _so_letras(m.group("quem")) == _so_letras(nome)))


def _colar_em(w, controle, texto, confere=None, substituir=True):
    """Cola o texto no campo e CONFERE lendo o campo de volta. substituir=False (caixa de mensagem): se já tem
    texto lá (rascunho dele), não mexe."""
    if not substituir and _valor(controle):
        return False
    if not _focar(w, controle):
        return False
    auto.SetClipboardText(texto)
    auto.SendKeys("{Ctrl}a{Ctrl}v" if substituir else "{Ctrl}v", waitTime=0.2)
    time.sleep(0.3)
    lido = _valor(controle)
    return lido is None or _so_letras(texto) in _so_letras(lido)


HORA = re.compile(r"^(?:\d{1,2}:\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|yesterday|today|ontem|hoje|monday|tuesday|wednesday|thursday|"
                  r"friday|saturday|sunday|segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)", re.I)


def _titulo(item):
    """O nome da conversa/contato. A busca parte o nome no pedaço destacado ("Rihan" + " Bittencourt", "Loja Ch" +
    "risan"): junta os textos (e emojis) da MESMA linha do primeiro, parando na hora/data."""
    partes, topo = [], None
    for c, _ in auto.WalkControl(item, maxDepth=8):
        if c.ControlTypeName not in ("TextControl", "ImageControl") or not c.Name or NAO_E_NOME.match(c.Name.strip()):
            continue
        y = c.BoundingRectangle.top
        if topo is None:
            topo = y
        elif abs(y - topo) > 2 or HORA.match(c.Name.strip()):
            break
        partes.append(c.Name)
    return re.sub(r"\s+", " ", "".join(partes)).strip() or (item.Name or "").strip()


def _resultados(w):
    grade = w.DataGridControl(Name="Search results.", searchDepth=30)
    if not grade.Exists(2):
        grade = w.DataGridControl(RegexName=r"(?i)resultado|search result", searchDepth=30)
    if not grade.Exists(1):
        return []
    achados, secao = [], "conversa"
    try:
        filhos = grade.GetChildren()
    except Exception:
        return []
    for item in filhos:
        try:  # a lista se refaz enquanto lê (item some no meio): pula, a próxima volta do _buscar relê
            nome = (item.Name or "").strip()
            if _sa(nome) in SECOES:
                secao = SECOES[_sa(nome)]
                continue
            if secao is None or not nome:
                continue  # resultado de MENSAGEM (texto achado numa conversa): não é contato
            achados.append({"nome": _titulo(item), "tipo": secao, "_item": item})
        except Exception:
            continue
    return achados


def procurar(nome, limite=6):
    """Contatos/conversas do WhatsApp que batem com o nome dito. Ordem: nome igual, começa com, contém."""
    w = _janela()
    if not w:
        return None
    busca = _campo_de_busca(w)
    if not busca:
        return None
    palavras = [p for p in _sa(nome).split() if len(p) > 1]
    vistos, saida = set(), []
    for r in _buscar(w, busca, nome):
        n = _sa(r["nome"])
        if not palavras or not all(p in n for p in palavras) or n in vistos:
            continue  # o WhatsApp mostra parecidos ("Mariana" pra "Rihan"): só fica quem tem as palavras
        vistos.add(n)
        nota = 0 if n == _sa(nome) else 1 if n.startswith(_sa(nome)) else 2
        saida.append({**r, "nota": nota})
    saida.sort(key=lambda r: (r["nota"], r["tipo"] != "conversa"))
    _limpar_busca(w)
    return [{"nome": r["nome"], "tipo": r["tipo"]} for r in saida[:limite]]


def _buscar(w, busca, nome):
    """Digita na busca e espera a lista ATUALIZAR (até 5 s): sem isso vinham os resultados da busca anterior."""
    if not _colar_em(w, busca, nome, _e_busca):
        return []
    primeira = (_sa(nome).split() or [""])[0]
    resultados = []
    for _ in range(12):
        time.sleep(0.45)
        resultados = _resultados(w)
        if any(primeira in _sa(r["nome"]) for r in resultados):
            break
    return resultados


def _limpar_busca(w):
    try:
        busca = _campo_de_busca(w)
        if busca and _focar(w, busca, _e_busca):
            auto.SendKeys("{Ctrl}a{Del}{Esc}", waitTime=0.05)
    except Exception:
        pass


CAIXA = re.compile(r"^(?:type a message|digite uma mensagem|mensagem)(?:\s+(?:to|para|pra)(?:\s+(?:group|o grupo))?\s+(?P<quem>.+))?$", re.I)


def _so_letras(t):
    return re.sub(r"[^a-z0-9]+", "", _sa(t))


def _caixa_de_texto(w):
    c = w.EditControl(searchDepth=34, Compare=lambda c, _: bool(CAIXA.match((c.Name or "").strip())))
    return c if c.Exists(4) else None


def _conversa_aberta(w, nome):
    """A caixa de mensagem diz pra quem é ("Type a message to group 7 SevenCode"): tem que ser o escolhido."""
    caixa = _caixa_de_texto(w)
    if not caixa:
        return False
    m = CAIXA.match(caixa.Name.strip())
    return bool(m and m.group("quem") and _so_letras(m.group("quem")) == _so_letras(nome))


def abrir(nome):
    """Abre a conversa com esse nome exato. Devolve a janela, ou None se não deu pra conferir."""
    w = _janela()
    if not w:
        return None
    busca = _campo_de_busca(w)
    if not busca:
        return None
    certo = [r for r in _buscar(w, busca, nome) if _so_letras(r["nome"]) == _so_letras(nome)]
    if not certo:
        _limpar_busca(w)
        return None
    if not _frente(w):
        return None
    certo[0]["_item"].Click(simulateMove=False)
    time.sleep(1.2)
    return w if _conversa_aberta(w, nome) else None


def enviar(nome, texto, arquivo=None):
    """Manda pro contato/grupo com esse nome. Só aperta Enter depois de conferir a conversa aberta."""
    if not auto:
        return False, "Falta a biblioteca de acessibilidade (uiautomation) neste PC."
    w = abrir(nome)
    if not w:
        return False, f"Não consegui abrir a conversa {nome} com certeza, então não mandei nada."
    caixa = _caixa_de_texto(w)
    if not caixa:
        return False, "Abri a conversa mas não achei a caixa de mensagem. Não mandei."
    guardado = auto.GetClipboardText()  # o que ele tinha copiado volta pro lugar no fim
    confere = lambda c: _e_caixa(c, nome)
    if arquivo:
        import subprocess
        if _valor(caixa) or not _focar(w, caixa):
            return False, "Não consegui pôr o cursor na conversa certa (ou tem rascunho seu lá). Não mandei."
        subprocess.run(["powershell", "-NoProfile", "-STA", "-Command",
                        "Add-Type -AssemblyName System.Windows.Forms; $l=New-Object System.Collections.Specialized.StringCollection; "
                        f"[void]$l.Add('{arquivo}'); [System.Windows.Forms.Clipboard]::SetFileDropList($l)"],
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        auto.SendKeys("{Ctrl}v", waitTime=0.1)
        time.sleep(2.5)  # abre a prévia do anexo; o texto vira legenda
        if texto:
            auto.SetClipboardText(texto)
            auto.SendKeys("{Ctrl}v", waitTime=0.2)
    elif _valor(caixa):
        return False, f"A conversa {nome} já tem um rascunho seu escrito. Não mexi nem mandei."
    elif not _colar_em(w, caixa, texto, substituir=False):
        return False, "Não consegui escrever na conversa certa. Conferi e não mandei."
    time.sleep(0.4)
    if auto.GetForegroundControl().NativeWindowHandle != w.NativeWindowHandle:
        return False, "O WhatsApp saiu da frente antes de enviar. Deixei digitado, sem enviar."
    auto.SendKeys("{Enter}", waitTime=0.2)
    try:
        auto.SetClipboardText(guardado or "")
    except Exception:
        pass
    return True, f"Enviado pro {nome}, chefe."
