"""O Rafael fala em português, mas o Windows dele está em inglês: "explorador de arquivos" é File Explorer.

candidatos() devolve os nomes a tentar (o dito e as traduções); EMBUTIDOS cobre os programas do
Windows que nem sempre têm atalho no Iniciar; PASTAS abre as pastas do usuário pelo nome.
"""
from pathlib import Path

CASA = Path.home()

# português (como ele fala) → nomes em inglês (como o Windows mostra)
TRADUCOES = {
    "explorador de arquivos": ["file explorer"], "explorador de arquivo": ["file explorer"], "explorador": ["file explorer"], "arquivos": ["file explorer"],
    "gerenciador de arquivos": ["file explorer"], "meus arquivos": ["file explorer"], "windows explorer": ["file explorer"],
    "calculadora": ["calculator"], "bloco de notas": ["notepad"], "bloco de nota": ["notepad"],
    "configuracoes": ["settings"], "configuracao": ["settings"], "ajustes": ["settings"],
    "gerenciador de tarefas": ["task manager"], "gerenciador": ["task manager"],
    "painel de controle": ["control panel"], "prompt de comando": ["command prompt"], "prompt": ["command prompt"],
    "terminal": ["terminal", "windows terminal", "powershell"], "powershell": ["windows powershell", "powershell"],
    "ferramenta de captura": ["snipping tool"], "captura de tela": ["snipping tool"], "recorte": ["snipping tool"],
    "print": ["snipping tool"], "camera": ["camera"], "relogio": ["clock"], "alarme": ["clock"],
    "despertador": ["clock"], "cronometro": ["clock"], "fotos": ["photos"], "galeria": ["photos"],
    "loja": ["microsoft store"], "loja da microsoft": ["microsoft store"], "gravador de voz": ["sound recorder"],
    "gravador de som": ["sound recorder"], "gravador": ["sound recorder"], "mapas": ["maps"], "email": ["outlook", "mail"],
    "e-mail": ["outlook", "mail"], "correio": ["outlook", "mail"], "calendario": ["calendar", "outlook"],
    "agenda": ["calendar", "outlook"], "navegador": ["google chrome", "microsoft edge"],
    "chrome": ["google chrome"], "edge": ["microsoft edge"], "word": ["word"], "excel": ["excel"],
    "powerpoint": ["powerpoint"], "teams": ["microsoft teams", "teams"], "musica": ["spotify", "media player"],
    "player": ["media player"], "reprodutor de midia": ["media player"], "video": ["media player"],
    "editor de video": ["capcut", "clipchamp"], "photoshop": ["adobe photoshop"], "visual studio": ["visual studio code"],
    "codigo": ["visual studio code"], "editor de codigo": ["visual studio code"], "anydesk": ["anydesk"],
    "acesso remoto": ["anydesk"], "lixeira": ["recycle bin"], "lixo": ["recycle bin"],
    "teclado virtual": ["on-screen keyboard"], "lupa": ["magnifier"], "dicas": ["tips"], "ajuda": ["get help"],
    "seguranca do windows": ["windows security"], "antivirus": ["windows security"], "xbox": ["xbox"],
    "jogos": ["steam", "xbox"], "opera": ["opera gx browser", "opera gx"],
}

# programas do Windows que funcionam mesmo sem atalho no Iniciar: nome → comando
EMBUTIDOS = {
    "file explorer": ["explorer.exe"], "calculator": ["calc.exe"], "notepad": ["notepad.exe"],
    "task manager": ["taskmgr.exe"], "control panel": ["control.exe"], "command prompt": ["cmd.exe", "/k"],
    "settings": ["explorer.exe", "ms-settings:"], "snipping tool": ["explorer.exe", "ms-screenclip:"],
    "paint": ["mspaint.exe"], "recycle bin": ["explorer.exe", "shell:RecycleBinFolder"],
    "on-screen keyboard": ["osk.exe"], "magnifier": ["magnify.exe"], "windows powershell": ["powershell.exe"],
    "windows security": ["explorer.exe", "windowsdefender:"], "camera": ["explorer.exe", "microsoft.windows.camera:"],
    "clock": ["explorer.exe", "ms-clock:"], "microsoft store": ["explorer.exe", "ms-windows-store:"],
}

PASTAS = {
    "downloads": CASA / "Downloads", "download": CASA / "Downloads", "baixados": CASA / "Downloads",
    "documentos": CASA / "Documents", "documents": CASA / "Documents", "meus documentos": CASA / "Documents",
    "area de trabalho": CASA / "Desktop", "desktop": CASA / "Desktop", "imagens": CASA / "Pictures",
    "fotos do pc": CASA / "Pictures", "pictures": CASA / "Pictures", "videos": CASA / "Videos", "musicas": CASA / "Music",
    "porthon": CASA / "Desktop" / "Porthon-System", "pasta do porthon": CASA / "Desktop" / "Porthon-System",
    "jarvis": CASA / "Desktop" / "Jarvis", "pasta do jarvis": CASA / "Desktop" / "Jarvis",
    "7 sevencode": CASA / "Desktop" / "7 SevenCode", "sevencode": CASA / "Desktop" / "7 SevenCode",
    "radar": CASA / "Desktop" / "7code-radar-leads", "clientes": CASA / "Desktop" / "Clientes",
}


def candidatos(alvo):
    """Nomes a tentar, na ordem: o que ele disse e as traduções para o inglês."""
    nomes = [alvo]
    for pt, en in TRADUCOES.items():
        if alvo == pt or alvo == f"o {pt}" or alvo == f"a {pt}":
            nomes += en
    return list(dict.fromkeys(nomes))


def pasta(alvo):
    """"pasta downloads", "pasta do jarvis", "downloads" → caminho, se existir."""
    nome = alvo.removeprefix("pasta ").removeprefix("de ").removeprefix("do ").removeprefix("da ").strip()
    caminho = PASTAS.get(nome) or PASTAS.get(alvo)
    return caminho if caminho and caminho.exists() else None
