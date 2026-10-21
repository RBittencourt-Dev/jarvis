"""Olhos e mãos do Jarvis no PC (o Rafael liberou em 20/10: "pode enxergar o que eu enxergo, poder total").

Olhos: tira print das telas SÓ quando ele pede ("o que tem na minha tela?", "lê isso") e manda pro modelo
de visão da Groq. Nada fica gravado em disco e nada é capturado sem pedido.
Mãos: digita texto e aperta atalhos na janela que ele está usando (nunca na do próprio Jarvis).
"""
import base64
import ctypes
import ctypes.wintypes as w
import io
import re
import time

import cerebro
import telas

u = ctypes.windll.user32

VER_TELA = re.compile(
    r"\b(?:o que (?:tem|t[aá]|est[aá]|aparece|[eé] isso|[eé] isso aqui) (?:na|aqui na|nessa) (?:minha |outra |essa )?tela|"
    r"(?:olha|v[eê]|analisa|confere|l[eê]) (?:a |minha |essa |na )?(?:minha )?tela|o que (?:voc[eê]|tu) (?:t[aá]|est[aá]) vendo|"
    r"o que (?:eu )?(?:t[oô]|estou) vendo|l[eê] (?:isso|o que t[aá] (?:escrito|na tela))(?: pra mim)?|"
    r"o que (?:t[aá]|est[aá]) escrito (?:aqui|a[ií]|na tela)|(?:me )?explica (?:isso|o que t[aá]) na tela|"
    r"esse erro (?:aqui|a[ií]|na tela)|o que (?:diz|significa) (?:esse|essa|isso) (?:erro|mensagem|aviso))", re.I)


def qual_tela(texto):
    t = texto.lower()
    if re.search(r"outra tela|tela vertical|tela do lado|segunda tela", t):
        return "outra"
    if re.search(r"tela principal|essa tela|nessa tela|tela da frente", t):
        return "esta"
    return "todas"


def prints(tela="todas", largura_max=1600):
    """JPEGs (base64) das telas pedidas, reduzidos pra caber rápido no modelo."""
    from PIL import ImageGrab
    monitores = telas.monitores()
    if tela in ("esta", "outra"):
        m = telas.monitor(tela)
        monitores = [m] if m else monitores
    saida = []
    for m in monitores:
        x, y, larg, alt = m["area"]
        img = ImageGrab.grab(bbox=(x, y, x + larg, y + alt), all_screens=True).convert("RGB")
        if img.width > largura_max:
            img = img.resize((largura_max, int(img.height * largura_max / img.width)))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        saida.append(base64.b64encode(buf.getvalue()).decode())
    return saida


def ver_tela(pergunta: str = "O que tem na tela?", tela: str = "todas"):
    """Olha a tela e responde a pergunta sobre o que está nela."""
    if not cerebro.nuvem():
        return "Pra eu enxergar a tela preciso da chave da Groq (groq.json), chefe."
    imagens = prints(tela)
    return cerebro.ver(imagens, pergunta) or "Não consegui enxergar agora, chefe."


# ------------------------------------------------------------------ mãos

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", w.DWORD), ("u", _U)]


def _tecla(vk=0, scan=0, flags=0):
    i = _INPUT(type=1)
    i.ki = _KEYBDINPUT(vk, scan, flags, 0, 0)
    u.SendInput(1, ctypes.byref(i), ctypes.sizeof(_INPUT))


def focar_janela_dele():
    """Põe na frente a janela que ele usava antes do Jarvis (a de cima que não é o Jarvis)."""
    frente = u.GetForegroundWindow()
    if frente and not telas._titulo(frente).startswith("J.A.R.V.I.S."):
        return frente
    for hwnd in telas._janelas_em_ordem():
        titulo = telas._titulo(hwnd)
        if titulo.startswith("J.A.R.V.I.S.") or titulo in ("Program Manager", "Windows Input Experience"):
            continue
        telas._para_frente(hwnd)
        return hwnd
    return None


def digitar(texto: str):
    """Escreve o texto na janela que ele está usando, letra por letra (acentos inclusos)."""
    alvo = focar_janela_dele()
    if not alvo:
        return "Não achei uma janela pra escrever, chefe."
    for ch in texto:
        if ch == "\n":
            _tecla(0x0D); _tecla(0x0D, flags=2)
            continue
        dados = ch.encode("utf-16-le")  # emoji vira 2 unidades; o Windows junta
        for i in range(0, len(dados), 2):
            codigo = int.from_bytes(dados[i:i + 2], "little")
            _tecla(scan=codigo, flags=4)       # KEYEVENTF_UNICODE
            _tecla(scan=codigo, flags=4 | 2)   # solta
        time.sleep(0.004)
    return f"Escrevi em {telas._titulo(alvo)[:40]}."


TECLAS = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "windows": 0x5B, "enter": 0x0D,
          "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "espaco": 0x20, "space": 0x20, "backspace": 0x08, "apagar": 0x08,
          "delete": 0x2E, "del": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
          "cima": 0x26, "up": 0x26, "baixo": 0x28, "down": 0x28, "esquerda": 0x25, "left": 0x25, "direita": 0x27,
          "right": 0x27, "printscreen": 0x2C, **{f"f{n}": 0x6F + n for n in range(1, 13)}}


def apertar_teclas(atalho: str):
    """Atalho de teclado na janela dele: "ctrl+s", "alt+tab", "enter", "ctrl+shift+t", "win+d"."""
    partes = [p.strip().lower() for p in re.split(r"\s*\+\s*", atalho) if p.strip()]
    codigos = []
    for p in partes:
        if p in TECLAS:
            codigos.append(TECLAS[p])
        elif len(p) == 1 and p.isalnum():
            codigos.append(ord(p.upper()))
        else:
            return f"Não conheço a tecla {p}."
    if not codigos:
        return "Qual tecla, chefe?"
    if 0x5B not in codigos:  # Win+algo é do Windows, não de uma janela
        focar_janela_dele()
    for c in codigos:
        _tecla(c)
    for c in reversed(codigos):
        _tecla(c, flags=2)
    return f"Apertei {atalho}."
