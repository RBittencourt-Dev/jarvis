"""Abrir coisas no monitor certo: "abre o YouTube na outra tela" vai para o monitor vertical.

O Rafael tem dois monitores: o horizontal (principal, onde o Jarvis fica) e o vertical.
"nessa tela / aqui / principal" = o do Jarvis; "outra / segunda / vertical / do lado" = o outro.
Funciona assim: guarda as janelas que já existem, abre, acha a janela nova e a move para lá, maximizada.
"""
import ctypes
import ctypes.wintypes as w
import re
import time

u = ctypes.windll.user32

NA_TELA = re.compile(
    r"\s+(?:na|no|pra|para a|para o|pro)\s+(?:minha\s+|meu\s+)?"
    r"(?P<qual>outra|segunda|2ª|tela vertical|monitor vertical|outro|tela do lado|tela de cima|vertical|"
    r"essa|nessa|esta|nesta|primeira|principal|tela principal|tela horizontal|horizontal)"
    r"(?:\s+(?:tela|monitor))?\s*$", re.I)
AQUI = re.compile(r"\s+(?:aqui|aqui mesmo|nessa tela|nesta tela|nesse monitor|neste monitor)\s*$", re.I)
QUAL = (r"(?P<qual>outra|segunda|2ª|tela vertical|monitor vertical|outro|tela do lado|tela de cima|vertical|"
        r"essa|esta|primeira|principal|tela principal|tela horizontal|horizontal)")
# "passa o spotify pra outra tela", "joga o chrome nessa tela", "move o whatsapp pro monitor vertical"
MOVER = re.compile(r"^(?:passa|joga|move|leva|manda|bota|coloca|muda)\s+(?:o\s+|a\s+)?(?P<app>.+?)\s+"
                   r"(?:(?:pra|para|na|no|pro)\s+(?:a\s+|o\s+)?(?:minha\s+|meu\s+)?" + QUAL + r"|(?P<aqui>nessa|nesta|neste|nesse))"
                   r"(?:\s+(?:tela|monitor))?\s*[.!]*$", re.I)


def pedido_de_mover(texto):
    """"passa o spotify pra outra tela" → ("spotify", "outra"); None se não for."""
    m = MOVER.match(texto.strip())
    if not m:
        return None
    qual = (m.group("qual") or "esta").lower()
    destino = "esta" if m.group("aqui") or re.match(r"essa|esta|primeira|principal|tela principal|tela horizontal|horizontal", qual) else "outra"
    return m.group("app").strip(), destino


def _programa_da_janela(hwnd):
    pid = w.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(520)
    tamanho = w.DWORD(520)
    k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(tamanho))
    k.CloseHandle(h)
    return buf.value.rsplit("\\", 1)[-1].lower()


def _titulo(hwnd):
    n = u.GetWindowTextLengthW(hwnd)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, b, n + 1)
    return b.value


PROGRAMAS = {"explorador": "explorer.exe", "arquivos": "explorer.exe", "file explorer": "explorer.exe",
             "vs code": "code.exe", "visual studio code": "code.exe", "chrome": "chrome.exe", "navegador": "chrome.exe",
             "opera": "opera.exe", "edge": "msedge.exe", "zap": "whatsapp", "whatsapp": "whatsapp", "spotify": "spotify.exe",
             "notion": "notion.exe", "steam": "steam", "capcut": "capcut", "calculadora": "calculator", "photoshop": "photoshop"}


CONTROLE = re.compile(r"^(?P<acao>fecha|fechar|feche|minimiza|minimizar|minimize|maximiza|maximizar|maximize|restaura|restaurar)"
                      r"\s+(?:o\s+|a\s+)?(?P<app>.+?)[.!]*$", re.I)
ACOES = {"fech": ("fechar", "Fechei"), "minimiz": ("minimizar", "Minimizei"), "maximiz": ("maximizar", "Maximizei"),
         "restaur": ("restaurar", "Restaurei")}


def pedido_de_janela(texto):
    """"fecha o spotify" → ("fechar", "spotify"); o Jarvis em si fica de fora ("fecha a janela" é ele dormir)."""
    m = CONTROLE.match(texto.strip())
    if not m or re.search(r"\bjarvis\b|^(?:a\s+)?janela$|^tudo$", m.group("app"), re.I):
        return None
    acao = next(v for k, v in ACOES.items() if m.group("acao").lower().startswith(k))
    return acao[0], m.group("app").strip()


def _achar_janelas(nome):
    alvo = nome.lower()
    programa = PROGRAMAS.get(alvo, alvo.replace(" ", ""))
    return [h for h in _janelas() if not _titulo(h).startswith("J.A.R.V.I.S.")
            and (programa in _programa_da_janela(h) or alvo in _titulo(h).lower())]


def controlar_janela(acao, nome):
    """Fechar manda o pedido normal de fechar (o programa ainda pergunta se tiver algo sem salvar)."""
    janelas = _achar_janelas(nome)
    if not janelas:
        return f"Não achei {nome} aberto, chefe."
    for h in janelas:
        if acao == "fechar":
            u.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
        else:
            u.ShowWindow(h, {"minimizar": 6, "maximizar": 3, "restaurar": 9}[acao])
    feito = next(v[1] for v in ACOES.values() if v[0] == acao)
    return f"{feito} {nome}, chefe."


# ------------------------------------------------------------- janelas que o Jarvis abriu ("popups")

ABERTAS = []  # hwnds, a mais nova no fim (só nesta sessão do servidor)

POPUP = re.compile(
    r"^(?P<acao>fecha|fechar|feche|minimiza|minimizar|minimize|esconde|tira|maximiza|maximizar|restaura|restaurar|"
    r"traz de volta|traga de volta|mostra de novo|reabre)\s+(?:o\s+|a\s+|os\s+|as\s+|esse\s+|essa\s+|esses\s+|essas\s+)?"
    # "a janela" sozinha é o próprio Jarvis (ir dormir); só "janelas" ou "a janela que você abriu" é popup
    r"(?P<qual>tod[oa]s\s+(?:[oa]s\s+)?(?:pop ?-?ups|janelas|cart[oõ]es|abas)|pop ?-?ups?|janelas(?: que (?:voc[eê]|tu) abriu| do lado| da outra tela| abertas)?|"
    r"janela (?:que (?:voc[eê]|tu) abriu|do lado|da outra tela|aberta)|"
    r"isso|isso a[ií]|tudo que (?:voc[eê]|tu) abriu|tudo|todas?|todos|[uú]ltim[ao]|sites?|pesquisas?|p[aá]ginas?)"
    r"(?:\s+(?:da|na) (?:outra )?tela)?(?:\s+(?:pra mim|a[ií]|por favor))?[.!]*$", re.I)


def lembrar_aberta(hwnd):
    if hwnd in ABERTAS:
        ABERTAS.remove(hwnd)
    ABERTAS.append(hwnd)


def pedido_de_popup(texto):
    """"minimiza os popups" → ("minimizar", "todas"); "fecha isso" → ("fechar", "ultima"); None se não for."""
    m = POPUP.match(texto.strip())
    if not m:
        return None
    a = m.group("acao").lower()
    acao = ("fechar" if a.startswith("fech") else "minimizar" if a.startswith(("minimiz", "escond", "tira"))
            else "maximizar" if a.startswith("maximiz") else "restaurar")
    q = m.group("qual").lower()
    todas = bool(re.match(r"(pop ?-?ups|janelas|sites|pesquisas|p[aá]ginas)(\s|$)|tudo|tod[oa]s", q))
    return acao, "todas" if todas else "ultima"


# ------------------------------------------------------------- abas do navegador ("fecha a aba do youtube no opera")

NAVEGADORES_EXE = {"chrome": "chrome.exe", "opera": "opera.exe", "edge": "msedge.exe", "firefox": "firefox.exe"}
ABA = re.compile(
    r"^(?:fecha|fechar|feche)\s+(?:a\s+|as\s+|essa\s+|esta\s+|essas\s+|todas\s+(?:as\s+)?)?(?P<qual>abas|guias|aba|guia)"
    r"(?:\s+(?:aberta|abertas|atual))?"
    r"(?:\s+(?:do|da|de|dos|das|com o|com a)\s+(?P<alvo>.+?))?"
    r"(?:\s+(?:no|na|do|da)\s+(?P<nav>google chrome|chrome|opera(?: gx)?|edge|firefox|navegador))?[.!]*$", re.I)


def pedido_de_aba(texto):
    """"fecha a aba do youtube no opera" → ("youtube", "opera", False); "fecha as abas do youtube" → (…, True)."""
    m = ABA.match(texto.strip())
    if not m:
        return None
    alvo = (m.group("alvo") or "").strip().lower() or None
    nav = (m.group("nav") or "").lower()
    if alvo in NAVEGADORES_EXE or (alvo or "").startswith(("opera", "google chrome")):  # "fecha a aba do chrome"
        nav, alvo = alvo, None
    nav = next((k for k in NAVEGADORES_EXE if k in nav), None)
    todas = m.group("qual").lower() in ("abas", "guias") or texto.lower().lstrip().startswith(("fecha todas", "fechar todas"))
    return alvo, nav, todas


def _para_frente(hwnd):
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)
    u.keybd_event(0x12, 0, 0, 0)  # Alt: o Windows deixa trocar o foco
    u.keybd_event(0x12, 0, 2, 0)
    u.SetForegroundWindow(hwnd)
    time.sleep(0.2)


def _atalho(*teclas):
    for t in teclas:
        u.keybd_event(t, 0, 0, 0)
    for t in reversed(teclas):
        u.keybd_event(t, 0, 2, 0)
    time.sleep(0.18)  # dá tempo do título da janela trocar pra aba nova


def _janelas_de_navegador(nav):
    exes = [NAVEGADORES_EXE[nav]] if nav else list(NAVEGADORES_EXE.values())
    return [h for h in _janelas_em_ordem() if not _titulo(h).startswith("J.A.R.V.I.S.") and _programa_da_janela(h) in exes]


def _varrer_abas(hwnd, alvo, todas):
    """Passa por todas as abas da janela (Ctrl+Tab) e fecha as que têm `alvo` no título. Devolve quantas fechou.

    Só a aba da frente aparece no título da janela, por isso precisa passar uma por uma."""
    _para_frente(hwnd)
    fechadas, vistos, voltas = 0, [], 0
    while voltas < 60 and u.IsWindow(hwnd):
        voltas += 1
        titulo = _titulo(hwnd)
        if alvo in titulo.lower():
            _atalho(0x11, 0x57)  # Ctrl+W: fecha e a próxima aba vem pra frente
            fechadas += 1
            if not todas:
                break
            continue
        if titulo in vistos[:1] and len(vistos) > 1:
            break  # deu a volta completa
        vistos.append(titulo)
        _atalho(0x11, 0x09)  # Ctrl+Tab: próxima aba
        if _titulo(hwnd) == titulo and len(vistos) > 1 and vistos.count(titulo) > 2:
            break  # uma aba só: o título não muda
    return fechadas


def fechar_aba(alvo, nav, todas=False):
    """Fecha aba(s) do site pedido em qualquer janela do navegador (a do próprio Jarvis nunca entra).
    Sem site ("fecha a aba"): fecha a aba da frente do navegador de cima."""
    janelas = _janelas_de_navegador(nav)
    if not alvo:
        if not janelas:
            janelas = [h for h in reversed(ABERTAS) if u.IsWindow(h) and not _titulo(h).startswith("J.A.R.V.I.S.")]
        if not janelas:
            return f"Não achei aba aberta{' no ' + nav.title() if nav else ''}, chefe."
        titulo = _titulo(janelas[0])
        _para_frente(janelas[0])
        _atalho(0x11, 0x57)
        return f"Fechei a aba {re.split(r'\s[-–—|]\s', titulo)[0][:50]}, chefe."
    # primeiro as janelas que já estão mostrando o site; depois as outras (o site pode estar numa aba de trás)
    janelas.sort(key=lambda h: alvo not in _titulo(h).lower())
    total = 0
    for hwnd in janelas:
        total += _varrer_abas(hwnd, alvo, todas)
        if total and not todas:
            break
    if not total:
        return f"Procurei em todas as abas{' do ' + nav.title() if nav else ''} e não achei nenhuma do {alvo}, chefe."
    return f"Fechei {'a aba' if total == 1 else f'{total} abas'} do {alvo}, chefe."


MOVER_ABA = re.compile(
    r"^(?:passa|joga|move|leva|manda|bota|coloca)\s+(?:essa\s+|esta\s+|a\s+)?(?:aba|guia)(?:\s+(?:aberta|atual))?"
    r"(?:\s+(?:do|da|de)\s+(?P<alvo>.+?))?(?:\s+(?:no|do)\s+(?P<nav>chrome|opera(?: gx)?|edge|firefox))?"
    r"\s+(?:pra|para|na|pro)\s+(?:a\s+)?(?:tela\s+|monitor\s+)?(?P<qual>outra|segunda|vertical|principal|primeira|essa|esta)"
    r"(?:\s+(?:tela|monitor))?[.!]*$",
    re.I)


def pedido_de_mover_aba(texto):
    """"passa a aba do youtube pra outra tela" → ("youtube", None, "outra")."""
    m = MOVER_ABA.match(texto.strip())
    if not m:
        return None
    alvo = (m.group("alvo") or "").strip().lower() or None
    nav = next((k for k in NAVEGADORES_EXE if k in (m.group("nav") or "").lower()), None)
    if alvo in NAVEGADORES_EXE:
        nav, alvo = alvo, None
    destino = "outra" if m.group("qual").lower() in ("outra", "segunda", "vertical") else "esta"
    return alvo, nav, destino


def _area_de_transferencia():
    import subprocess
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], capture_output=True, text=True,
                       timeout=10, creationflags=subprocess.CREATE_NO_WINDOW, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def mover_aba(alvo, nav, destino):
    """Copia o endereço da aba (Ctrl+L, Ctrl+C), fecha ela (Ctrl+W) e reabre numa janela no monitor pedido."""
    import navegadores
    exes = [NAVEGADORES_EXE[nav]] if nav else list(NAVEGADORES_EXE.values())
    candidatas = [h for h in _janelas_em_ordem() if not _titulo(h).startswith("J.A.R.V.I.S.")
                  and _programa_da_janela(h) in exes and (not alvo or alvo in _titulo(h).lower())]
    if not candidatas:
        return f"Não achei a aba{' do ' + alvo if alvo else ''} aberta, chefe."
    hwnd = candidatas[0]
    exe = _programa_da_janela(hwnd)
    _para_frente(hwnd)

    def atalho(*teclas):
        for t in teclas:
            u.keybd_event(t, 0, 0, 0)
        for t in reversed(teclas):
            u.keybd_event(t, 0, 2, 0)
        time.sleep(0.15)
    atalho(0x11, 0x4C)  # Ctrl+L: barra de endereço
    atalho(0x11, 0x43)  # Ctrl+C
    url = _area_de_transferencia()
    atalho(0x1B)        # Esc
    if not re.match(r"^(https?://|[\w-]+\.[\w.-]+)", url):
        return "Não consegui pegar o endereço dessa aba, chefe."
    atalho(0x11, 0x57)  # Ctrl+W: fecha a aba de onde ela estava
    nome_nav = next((k for k, v in NAVEGADORES_EXE.items() if v == exe), None)
    navegadores.abrir(url, nome_nav, tela=destino)
    return f"Passei a aba pra {'outra tela' if destino == 'outra' else 'tela principal'}, chefe."


def _janelas_em_ordem():
    """Janelas visíveis de cima pra baixo (ordem de empilhamento)."""
    ordem = []

    def cada(hwnd, _):
        if u.IsWindowVisible(hwnd) and u.GetWindowTextLengthW(hwnd) and not u.GetWindow(hwnd, 4):
            ordem.append(hwnd)
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(cada), 0)
    return ordem


def controlar_popups(acao, quais):
    vivas = [h for h in ABERTAS if u.IsWindow(h) and not _titulo(h).startswith("J.A.R.V.I.S.")]
    ABERTAS[:] = vivas
    if not vivas:
        return "Não tem nenhuma janela que eu abri, chefe."
    alvo = vivas if quais == "todas" else vivas[-1:]
    for h in alvo:
        if acao == "fechar":
            u.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE: igual clicar no X (o programa pergunta se tem algo sem salvar)
            ABERTAS.remove(h)
        else:
            u.ShowWindow(h, {"minimizar": 6, "maximizar": 3, "restaurar": 9}[acao])
    feito = {"fechar": "Fechei", "minimizar": "Minimizei", "maximizar": "Maximizei", "restaurar": "Trouxe de volta"}[acao]
    quanto = f"as {len(alvo)} janelas" if len(alvo) > 1 else "a janela"
    return f"{feito} {quanto}, chefe."


def mover_app(nome, destino):
    """Acha a janela aberta (pelo programa ou pelo título) e leva para o monitor pedido."""
    mon = monitor(destino)
    if not mon:
        return "Só achei um monitor ligado, chefe."
    alvo = nome.lower()
    programa = PROGRAMAS.get(alvo, alvo.replace(" ", ""))
    for hwnd in _janelas():
        if programa in _programa_da_janela(hwnd) or alvo in _titulo(hwnd).lower():
            _mover(hwnd, mon)
            u.SetForegroundWindow(hwnd)
            return f"Pronto, passei {nome} pra {'essa tela' if destino == 'esta' else 'a outra tela'}."
    return f"Não achei {nome} aberto, chefe."


def separar(alvo):
    """"youtube na outra tela" → ("youtube", "outra"); "notion aqui" → ("notion", "esta"); sem tela → (alvo, None)."""
    m = NA_TELA.search(alvo)
    if m:
        qual = m.group("qual").lower()
        destino = "esta" if re.match(r"essa|nessa|esta|nesta|primeira|principal|tela principal|tela horizontal|horizontal", qual) else "outra"
        return alvo[:m.start()].strip(), destino
    m = AQUI.search(alvo)
    if m:
        return alvo[:m.start()].strip(), "esta"
    return alvo, None


class _Info(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("rcMonitor", w.RECT), ("rcWork", w.RECT), ("dwFlags", w.DWORD)]


def monitores():
    """[{area: (x, y, largura, altura), principal: bool, deitado: bool}]"""
    lista = []

    def cada(hmon, _hdc, _rect, _dado):
        info = _Info()
        info.cbSize = ctypes.sizeof(_Info)
        u.GetMonitorInfoW(hmon, ctypes.byref(info))
        r = info.rcWork
        lista.append({"area": (r.left, r.top, r.right - r.left, r.bottom - r.top), "principal": bool(info.dwFlags & 1),
                      "deitado": (r.right - r.left) > (r.bottom - r.top)})
        return True

    tipo = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(w.RECT), ctypes.c_void_p)
    u.EnumDisplayMonitors(None, None, tipo(cada), 0)
    return lista


def monitor(destino):
    """"esta" = o horizontal principal (onde o Jarvis abre); "outra" = qualquer outro."""
    todos = monitores()
    principal = next((m for m in todos if m["deitado"] and m["principal"]), None) or next((m for m in todos if m["deitado"]), todos[0])
    if destino == "esta":
        return principal
    outros = [m for m in todos if m is not principal]
    return outros[0] if outros else None


def _janelas():
    achadas = set()

    def cada(hwnd, _):
        if u.IsWindowVisible(hwnd) and u.GetWindowTextLengthW(hwnd) and not u.GetWindow(hwnd, 4):  # 4 = GW_OWNER
            achadas.add(hwnd)
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(cada), 0)
    return achadas


def _mover(hwnd, mon):
    x, y, larg, alt = mon["area"]
    u.ShowWindow(hwnd, 9)  # SW_RESTORE: janela maximizada não muda de monitor
    u.SetWindowPos(hwnd, 0, x + 40, y + 40, max(600, larg - 80), max(400, alt - 80), 0x0004)  # SWP_NOZORDER
    u.ShowWindow(hwnd, 3)  # SW_MAXIMIZE, já no monitor novo


def abrir_em(destino, abrir):
    """Roda `abrir()` e leva a janela que aparecer para o monitor pedido. Devolve o que `abrir()` devolveu."""
    mon = monitor(destino) if destino else None
    if not mon:
        return abrir()
    antes = _janelas()
    frente_antes = u.GetForegroundWindow()
    resultado = abrir()
    for _ in range(40):  # até 10 s: programa pesado demora a mostrar a janela
        time.sleep(0.25)
        novas = _janelas() - antes
        if novas:
            nova = next(iter(novas))
            _mover(nova, mon)
            lembrar_aberta(nova)
            return resultado
    frente = u.GetForegroundWindow()
    if frente and frente != frente_antes:  # app que já estava aberto e só veio pra frente
        _mover(frente, mon)
        lembrar_aberta(frente)
    return resultado
