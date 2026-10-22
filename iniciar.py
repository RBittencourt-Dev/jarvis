"""Liga o Jarvis inteiro quando o Windows entra (chamado pelo registro "Executar" do usuário, sem janela nenhuma).

Sobe o servidor e o ouvido de fundo, espera o servidor responder e — se "abrir_tela_ao_ligar" estiver ligado
(padrão) — já abre a tela do Jarvis (com o rosto na primeira vez do dia, se o PC usar reconhecimento facial).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

RAIZ = Path(__file__).parent
SEM_JANELA = 0x08000000 | 0x00000008  # sem console, separado deste processo


def main():
    sys.path.insert(0, str(RAIZ))
    import primeiro_uso  # noqa: F401  (config.json deste PC)
    config = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    pythonw = RAIZ / ".venv" / "Scripts" / "pythonw.exe"
    url = f"http://127.0.0.1:{config.get('porta', 8765)}/api/status"
    try:
        httpx.get(url, timeout=1.5)
        ja_no_ar = True
    except Exception:
        ja_no_ar = False
    if not ja_no_ar:
        subprocess.Popen([str(pythonw), str(RAIZ / "server.py")], cwd=RAIZ, creationflags=SEM_JANELA)
        subprocess.Popen([str(pythonw), str(RAIZ / "palmas.py")], cwd=RAIZ, creationflags=SEM_JANELA)
    for _ in range(120):  # até 60 s (PC acabando de ligar pode estar lento)
        try:
            httpx.get(url, timeout=1.5)
            break
        except Exception:
            time.sleep(0.5)
    if config.get("abrir_tela_ao_ligar", True):
        import palmas
        palmas.abrir_jarvis()


if __name__ == "__main__":
    main()
