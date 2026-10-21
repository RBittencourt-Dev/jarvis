"""Qual navegador abre o quê. Padrão: Chrome. "no Opera" / "no Edge" no fim do pedido escolhe outro.

Também sabe o endereço dos sites que ele costuma pedir pelo nome ("abre a Netflix").
"""
import json
import os
import re
import subprocess
import threading
import webbrowser
from pathlib import Path

import telas

# onde abrem os sites que o Jarvis abre sozinho: "outra" = tela vertical (o HUD fica livre na horizontal)
TELA_DOS_SITES = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8")).get("tela_dos_sites", "outra")

LOCAL = Path(os.environ.get("LOCALAPPDATA", ""))
NAVEGADORES = {  # nome falado → executáveis possíveis (o primeiro que existir)
    "chrome": [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
               LOCAL / "Google/Chrome/Application/chrome.exe"],
    "opera": [LOCAL / "Programs/Opera GX/opera.exe", LOCAL / "Programs/Opera/opera.exe"],
    "edge": [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
             Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")],
}
PADRAO = "chrome"

NO_NAVEGADOR = re.compile(r"\s+(?:no|pelo|com o|usando o)\s+(?P<nav>opera(?: gx)?|chrome|google chrome|edge|navegador)\s*[.!?]*$", re.I)

SITES = {  # como ele fala → endereço
    "netflix": "https://www.netflix.com", "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com",
    "email": "https://mail.google.com", "google": "https://www.google.com", "github": "https://github.com",
    "vercel": "https://vercel.com/dashboard", "supabase": "https://supabase.com/dashboard",
    "chatgpt": "https://chatgpt.com", "chat gpt": "https://chatgpt.com", "whatsapp web": "https://web.whatsapp.com",
    "spotify web": "https://open.spotify.com", "mercado livre": "https://www.mercadolivre.com.br",
    "drive": "https://drive.google.com", "google drive": "https://drive.google.com",
    "agenda do google": "https://calendar.google.com", "google agenda": "https://calendar.google.com",
    "twitch": "https://www.twitch.tv", "prime video": "https://www.primevideo.com", "disney": "https://www.disneyplus.com",
    "max": "https://www.max.com", "globoplay": "https://globoplay.globo.com", "linkedin": "https://www.linkedin.com",
    "facebook": "https://www.facebook.com", "tiktok": "https://www.tiktok.com", "x": "https://x.com", "twitter": "https://x.com",
    "porthon": "https://porthon.com.br", "site do porthon": "https://porthon.com.br",
    "figma": "https://www.figma.com", "canva": "https://www.canva.com", "claude": "https://claude.ai",
}


def separar(alvo):
    """"netflix no opera" → ("netflix", "opera"); "youtube" → ("youtube", None)."""
    m = NO_NAVEGADOR.search(alvo)
    if not m:
        return alvo, None
    nav = m.group("nav").lower()
    nav = "opera" if "opera" in nav else "chrome" if "chrome" in nav else "edge" if "edge" in nav else None
    return alvo[:m.start()].strip(), nav


def site_conhecido(alvo):
    nome = re.sub(r"^(?:o|a|site d[oa])\s+", "", alvo.lower().strip())
    return SITES.get(nome)


def executavel(nome):
    achado = next((p for p in NAVEGADORES.get(nome or PADRAO, []) if p.exists()), None)
    if not achado and (nome or PADRAO) == "chrome":  # PC sem Chrome (colégio): o Edge faz o mesmo papel
        achado = next((p for p in NAVEGADORES["edge"] if p.exists()), None)
    return achado


def abrir(url, navegador=None, janela_nova=False, tela="padrao"):
    """Abre no navegador pedido; sem pedido, no Chrome (e, se faltar, no padrão do Windows).

    tela: "esta" (horizontal), "outra" (vertical), None (onde o navegador quiser) ou "padrao" (config tela_dos_sites).
    Com tela, abre janela nova e leva ela pra lá em segundo plano, sem segurar a resposta.
    """
    if tela == "padrao":
        tela = TELA_DOS_SITES or None
    exe = executavel(navegador) or executavel(PADRAO)
    if tela and exe and telas.monitor(tela):
        threading.Thread(target=telas.abrir_em, args=(tela, lambda: subprocess.Popen([str(exe), "--new-window", url])),
                         daemon=True).start()
    elif exe:
        subprocess.Popen([str(exe), *(["--new-window"] if janela_nova else []), url])
    else:
        webbrowser.open(url)
