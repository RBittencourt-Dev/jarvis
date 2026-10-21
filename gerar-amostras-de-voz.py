"""Gera amostras de voz para o Rafael escolher (pasta amostras-de-voz, abre a página com os players)."""
import asyncio
import io
import os
import wave
from pathlib import Path

import av
import edge_tts
import numpy as np

RAIZ = Path(__file__).parent
PASTA = RAIZ / "amostras-de-voz"
TEXTO = ("Boa tarde, chefe! Tá tudo rodando por aqui. O caixa tá em cento e setenta e cinco reais, "
         "e dois leads te responderam hoje. Quer que eu já abra o Radar pra ti?")
TAXA = 24000

AMOSTRAS = [  # (arquivo, título, voz, tom, ritmo, filtro) — sem mexer no tom: tom alterado soa robótico
    ("1-william-natural", "William natural (mais rápido, tom original)", "en-AU-WilliamMultilingualNeural", "+0Hz", "+15%", False),
    ("2-william-filtro", "William natural + filtro de IA", "en-AU-WilliamMultilingualNeural", "+0Hz", "+15%", True),
    ("3-antonio-natural", "Antonio natural (mais rápido, tom original)", "pt-BR-AntonioNeural", "+0Hz", "+18%", False),
    ("4-antonio-levemente-grave", "Antonio levemente grave", "pt-BR-AntonioNeural", "-3Hz", "+18%", False),
    ("5-brian-conversa", "Brian (voz feita pra conversa, sotaque americano)", "en-US-BrianMultilingualNeural", "+0Hz", "+12%", False),
    ("6-florian", "Florian (sotaque europeu, ar de mordomo)", "de-DE-FlorianMultilingualNeural", "+0Hz", "+12%", False),
    ("7-remy", "Remy (sotaque francês, elegante)", "fr-FR-RemyMultilingualNeural", "+0Hz", "+12%", False),
]


async def falar(voz, tom, ritmo):
    audio = b""
    async for parte in edge_tts.Communicate(TEXTO, voz, rate=ritmo, pitch=tom).stream():
        if parte["type"] == "audio":
            audio += parte["data"]
    return audio


def decodificar(mp3):
    blocos = []
    with av.open(io.BytesIO(mp3)) as f:
        conv = av.AudioResampler(format="s16", layout="mono", rate=TAXA)
        for quadro in f.decode(audio=0):
            for r in conv.resample(quadro):
                blocos.append(r.to_ndarray().ravel())
    return np.concatenate(blocos).astype(np.float32) / 32768


def filtro_de_ia(x):
    """Leve "voz de computador": cópias atrasadas (metálico), sala pequena e um tremor de anel bem sutil."""
    def atraso(sinal, ms, ganho):
        n = int(TAXA * ms / 1000)
        return np.concatenate([np.zeros(n, np.float32), sinal])[:len(sinal)] * ganho
    y = x + atraso(x, 11, 0.45) + atraso(x, 19, 0.3)              # brilho metálico (pente)
    sala = sum(atraso(y, ms, g) for ms, g in [(47, .22), (73, .16), (101, .11), (139, .07)])
    t = np.arange(len(y)) / TAXA
    y = y + sala
    y = y * (0.88 + 0.12 * np.sin(2 * np.pi * 38 * t))              # anel sutil
    return y / max(1e-6, np.abs(y).max()) * 0.9


def salvar_wav(caminho, x):
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


async def main():
    PASTA.mkdir(exist_ok=True)
    itens = []
    for arquivo, titulo, voz, tom, ritmo, filtro in AMOSTRAS:
        x = decodificar(await falar(voz, tom, ritmo))
        if filtro:
            x = filtro_de_ia(x)
        salvar_wav(PASTA / f"{arquivo}.wav", x)
        itens.append(f'<li><strong>{titulo}</strong><audio controls preload="auto" src="{arquivo}.wav"></audio></li>')
    (PASTA / "ouvir.html").write_text(f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Vozes do Jarvis</title>
<style>body{{background:#03080f;color:#cfeeff;font:16px Segoe UI,sans-serif;max-width:640px;margin:40px auto;padding:0 16px}}
h1{{color:#39d0ff;font-weight:400;letter-spacing:.2em;font-size:18px}}li{{list-style:none;margin:0 0 18px;padding:12px;border:1px solid #39d0ff33}}
strong{{display:block;margin-bottom:8px}}audio{{width:100%}}p{{color:#6c8aa0}}</style>
<h1>VOZES DO JARVIS</h1><p>Mesmo texto em todas. Me diga o número da que você gostou.</p><ul>{''.join(itens)}</ul></html>""",
                                      encoding="utf-8")
    print(PASTA / "ouvir.html")


asyncio.run(main())
if os.name == "nt":
    os.startfile(PASTA / "ouvir.html")
