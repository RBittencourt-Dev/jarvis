"""Filtro "de IA / traje" na voz do Jarvis — SEM clonar pessoa nenhuma.

Pedido dele (23/10/2026): deixar a voz com cara de assistente de IA tipo capacete do Homem de Ferro, como OPÇÃO.
NÃO é clone de voz real (recusado): é um efeito em cima da voz edge-tts (Antonio) que ele já usa — flanger metálico leve,
um respiro de reverb e um realce de presença. Tudo em Python (PyAV + numpy), nada de ffmpeg externo nem modelo de ninguém.

Uso: `processar_mp3(caminho)` reescreve o mp3 com o efeito. O server chama isso depois do edge-tts salvar, quando
CONFIG["voz_filtro"] == "ia". A chave do cache de voz inclui o filtro, então filtrada e normal não se misturam.
"""
import numpy as np


def ler_mp3(caminho):
    import av
    cont = av.open(str(caminho))
    stream = cont.streams.audio[0]
    sr = stream.rate or 24000
    res = av.AudioResampler(format="flt", layout="mono", rate=sr)
    partes = []
    for frame in cont.decode(stream):
        for f in res.resample(frame):
            partes.append(f.to_ndarray().reshape(-1))
    cont.close()
    if not partes:
        return np.zeros(1, np.float32), sr
    return np.concatenate(partes).astype(np.float32), sr


def escrever_mp3(caminho, x, sr):
    import av
    x = np.clip(x, -1.0, 1.0).astype(np.float32)
    cont = av.open(str(caminho), mode="w")
    stream = cont.add_stream("mp3", rate=sr)
    tam = 1152  # o encoder mp3 trabalha em quadros desse tamanho
    for i in range(0, len(x), tam):
        bloco = x[i:i + tam]
        frame = av.AudioFrame.from_ndarray(bloco.reshape(1, -1), format="flt", layout="mono")
        frame.rate = sr
        frame.pts = i
        for p in stream.encode(frame):
            cont.mux(p)
    for p in stream.encode(None):
        cont.mux(p)
    cont.close()


def _flanger(x, sr, prof_ms=2.2, taxa=0.28, mix=0.45):
    """Delay curto modulado por um LFO: dá o brilho 'metálico' de assistente de IA."""
    n = len(x)
    t = np.arange(n)
    atraso = (prof_ms * 0.5e-3 * sr) * (1 + np.sin(2 * np.pi * taxa * t / sr))  # em amostras, 0..prof
    idx = t - atraso
    i0 = np.floor(idx).astype(np.int64)
    frac = idx - i0
    i0 = np.clip(i0, 0, n - 1)
    i1 = np.clip(i0 + 1, 0, n - 1)
    atrasado = x[i0] * (1 - frac) + x[i1] * frac
    return (1 - mix) * x + mix * atrasado


def _reverb(x, sr, mix=0.16):
    """Reverb curto por multi-tap (ecos somados, tudo vetorizado — instantâneo): o 'respiro' de dentro do traje."""
    taps = [(0.029, 0.50), (0.037, 0.40), (0.041, 0.33), (0.053, 0.26), (0.067, 0.20), (0.083, 0.15)]  # (seg, ganho)
    molhado = np.zeros_like(x)
    for seg, g in taps:
        d = int(seg * sr)
        if 0 < d < len(x):
            molhado[d:] += g * x[:-d]
    molhado /= (np.max(np.abs(molhado)) + 1e-6)
    return (1 - mix) * x + mix * molhado


def _presenca(x, k=6):
    """Realce leve de agudos (high-shelf via média móvel, vetorizado) pra voz 'limpa de rádio'."""
    ma = np.convolve(x, np.ones(k, np.float32) / k, mode="same")
    return x + 0.5 * (x - ma)


def filtrar_ia(x, sr):
    y = _presenca(x)
    y = _flanger(y, sr)
    y = _reverb(y, sr)
    pico = np.max(np.abs(y)) + 1e-6
    return (y / pico) * 0.97  # normaliza sem estourar


def processar_mp3(caminho):
    try:
        x, sr = ler_mp3(caminho)
        escrever_mp3(caminho, filtrar_ia(x, sr), sr)
        return True
    except Exception:
        return False  # se algo falhar, fica a voz normal (nunca quebra a fala)
