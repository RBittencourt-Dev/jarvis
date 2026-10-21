"""Comandos do Windows que o Jarvis entende direto, sem passar pelo modelo.

Cada comando diz se é perigoso (desligar, reiniciar…): esses esperam o "sim" do Rafael,
a menos que ele desligue isso no config ("confirmar_acoes_perigosas": false).
"""
import re
import subprocess

AJUSTES_DO_WINDOWS = {
    r"wi-?fi|internet|rede": ("ms-settings:network-wifi", "as configurações de Wi-Fi"),
    r"bluetooth": ("ms-settings:bluetooth", "o Bluetooth"),
    r"som|[aá]udio|alto-?falante|microfone": ("ms-settings:sound", "as configurações de som"),
    r"tela|monitor|brilho|resolu[cç][aã]o": ("ms-settings:display", "as configurações de tela"),
    r"atualiza[cç]": ("ms-settings:windowsupdate", "o Windows Update"),
    r"energia|bateria|suspens": ("ms-settings:powersleep", "as configurações de energia"),
    r"papel de parede|fundo de tela|personaliza": ("ms-settings:personalization-background", "a personalização"),
    r"aplicativos|programas instalados": ("ms-settings:appsfeatures", "os aplicativos instalados"),
    r"impressora": ("ms-settings:printers", "as impressoras"),
    r"notifica": ("ms-settings:notifications", "as notificações"),
}


def powershell(comando):
    subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", comando],
                     creationflags=subprocess.CREATE_NO_WINDOW)


def teclas_de_volume(tecla, vezes):
    # 175 = aumentar, 174 = diminuir, 173 = mudo (cada toque muda 2%)
    powershell(f"$w = New-Object -ComObject WScript.Shell; 1..{vezes} | ForEach-Object {{ $w.SendKeys([char]{tecla}) }}")


def tema(claro):
    v = 1 if claro else 0
    chave = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    powershell(f"Set-ItemProperty '{chave}' AppsUseLightTheme {v}; Set-ItemProperty '{chave}' SystemUsesLightTheme {v}")


# (regra, perigoso, ação, o que ele fala)
COMANDOS = [
    (r"\bcancela\w* (o )?(desligamento|reinicio|rein[ií]cio)", False,
     lambda: subprocess.run(["shutdown", "/a"]), "Desligamento cancelado, chefe."),
    (r"\b(deslig\w*|apag\w*)\b.*\b(pc|computador|m[aá]quina|tudo)\b", True,
     lambda: subprocess.run(["shutdown", "/s", "/t", "10"]), "Desligando o computador em 10 segundos. Até logo, chefe."),
    (r"\breinici\w*\b.*\b(pc|computador|m[aá]quina)\b|\breinici\w* o windows", True,
     lambda: subprocess.run(["shutdown", "/r", "/t", "10"]), "Reiniciando o computador em 10 segundos."),
    (r"\b(suspend\w*|hibern\w*)\b", True,
     lambda: powershell("Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"),
     "Suspendendo o computador."),
    (r"\bbloque\w*\b.*\b(pc|computador|tela|m[aá]quina)\b", False,
     lambda: subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"]), "Computador bloqueado."),
    (r"\b(aument\w*|sobe|subir|mais alto)\b.*\b(volume|som|m[uú]sica)\b|\bvolume\b.*\b(mais alto|aument)", False,
     lambda: teclas_de_volume(175, 10), "Volume aumentado."),
    (r"\b(diminu\w*|baix\w*|abaix\w*|mais baixo)\b.*\b(volume|som|m[uú]sica)\b|\bvolume\b.*\b(mais baixo|diminu)", False,
     lambda: teclas_de_volume(174, 10), "Volume diminuído."),
    (r"\b(silenci\w*|mut\w*|tira o som)\b(?!.*\b(microfone|mic)\b)", False,  # microfone é com o microfone.py
     lambda: teclas_de_volume(173, 1), "Pronto, chefe."),
    (r"\bmodo escuro\b|\btema escuro\b", False, lambda: tema(False), "Modo escuro ativado."),
    (r"\bmodo claro\b|\btema claro\b", False, lambda: tema(True), "Modo claro ativado."),
]


def entender(texto):
    """Devolve (perigoso, ação, fala) se o texto for um comando do Windows; senão None."""
    t = texto.lower()
    for regra, perigoso, acao, fala in COMANDOS:
        if re.search(regra, t):
            return perigoso, acao, fala
    if re.search(r"\b(abr\w*|mostr\w*|configur\w*|ajust\w*)\b", t) and re.search(r"configura|ajuste", t):
        for regra, (uri, nome) in AJUSTES_DO_WINDOWS.items():
            if re.search(regra, t):
                return False, (lambda u=uri: subprocess.Popen(["explorer.exe", u])), f"Abrindo {nome}."
        return False, (lambda: subprocess.Popen(["explorer.exe", "ms-settings:"])), "Abrindo as configurações do Windows."
    return None


DESPEDIDAS = [
    (r"\bboa noite\b", "Boa noite, chefe. Descanse. Estarei aqui quando precisar."),
    (r"\bintervalo\b|\bpausa\b", "Bom intervalo, chefe. É só me chamar."),
    (r"\b(pode (se )?deslig\w*|se deslig(a|ue|ar)\b|^deslig(a|ue|ar)( (o )?jarvis| isso| a[ií])?$|encerr\w*|"
     r"stand ?by|modo (de )?espera|em espera|desativ\w*|hiberna (o )?jarvis)\b", "Desligando. Até logo, chefe."),
    (r"\b(dorm\w*|descans\w*|at[ée] (mais|logo|amanh[aã]|depois|j[aá])|tchau\w*|xau|falou|fui|vaza|some|"
     r"pode (ir|sair|fechar)|vai embora|sai da tela|fecha a janela|fecha (o )?jarvis)\b",
     "Até mais, chefe. Fico de ouvido aqui."),
]


def despedida(texto):
    """Pedido para o Jarvis dormir (fechar a janela e voltar a esperar palmas ou o nome)."""
    t = texto.lower()
    if re.search(r"\b(pc|computador|m[aá]quina)\b", t) or len(t.split()) > 7:
        return None  # "desliga o computador" é outra coisa; frase longa é conversa, não despedida
    for regra, fala in DESPEDIDAS:
        m = re.search(regra, t)
        if m:
            sobra = re.sub(r"\b(jarvis|chefe|tch[eê]|bah|ent[aã]o|por hoje|a[ií]|pode|vou|meu|guri|valeu|obrigad[oa])\b|[,.!?]",
                           " ", t[:m.start()] + t[m.end():]).split()
            return fala if len(sobra) <= 2 else None
    return None


def fechar_janela():
    """Fecha a janela do Jarvis (Chrome com o perfil próprio dele); o resto do Chrome não é tocado."""
    powershell("Start-Sleep -Milliseconds 400; Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' OR Name='msedge.exe'\" | "
               "Where-Object { $_.CommandLine -like '*perfil-navegador*' -or $_.CommandLine -like '*perfil-extensao*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
