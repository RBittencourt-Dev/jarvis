"""Gera o ícone do Jarvis: o mesmo ARC REACTOR do HUD (web/arc-reactor.js), parado, com "JARVIS" no meio.

    python gerar-icone.py   →  web/marca/jarvis.ico, jarvis-192.png, jarvis-512.png

As camadas, raios e cores são as do arc-reactor.js (desenhado para 390px); aqui tudo escala a partir disso.
"""
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).parent
MARCA = RAIZ / "web" / "marca"
FONTE = RAIZ / "web" / "vendor" / "fonts" / "orbitron.woff2"
L = 1024  # desenha grande e reduz: as bordas ficam lisas
ESC = (L / 2 - 14) / 195  # o reator do HUD tem 390px; o HUD externo (r=190) quase encosta na borda
CX = CY = L / 2

PRIM, SEC, ALTO, NUCLEO = "#00E5FF", "#0077FF", "#B8F7FF", "#061A2B"


def rgb(hexa, a=255):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4)) + (int(a),)


def camada():
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def com_brilho(base, img, blur):
    """Equivale ao shadowBlur do canvas: a camada desfocada por baixo + a nítida por cima."""
    if blur:
        base = Image.alpha_composite(base, img.filter(ImageFilter.GaussianBlur(blur * ESC)))
    return Image.alpha_composite(base, img)


def caixa(r):
    r *= ESC
    return (CX - r, CY - r, CX + r, CY + r)


def anel_segmentado(base, r, w, seg, ativos, gap, cor, rot):
    """Arcos grossos: os 'ativos' acesos com brilho, o resto quase apagado (igual anelSegmentado do JS)."""
    passo = 360 / seg
    acesos, apagados = camada(), camada()
    for i in range(seg):
        a0 = i * passo + rot
        d = acesos[1] if i < ativos else apagados[1]
        d.arc(caixa(r + w / 2), a0, a0 + passo - gap, fill=rgb(cor, 230 if i < ativos else 31), width=round(w * ESC))
    base = Image.alpha_composite(base, apagados[0])
    return com_brilho(base, acesos[0], 8)


def radial(r, paradas, alfa=1.0):
    """Gradiente radial (cor no centro → transparente na borda) como o createRadialGradient do JS."""
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    px = img.load()
    rr = r * ESC
    for y in range(int(CY - rr), int(CY + rr) + 1):
        for x in range(int(CX - rr), int(CX + rr) + 1):
            t = math.hypot(x - CX, y - CY) / rr
            if t >= 1:
                continue
            for (ta, ca), (tb, cb) in zip(paradas, paradas[1:]):
                if ta <= t <= tb:
                    k = (t - ta) / (tb - ta)
                    c = [round(ca[j] + (cb[j] - ca[j]) * k) for j in range(4)]
                    px[x, y] = (c[0], c[1], c[2], round(c[3] * alfa))
                    break
    return img


def raio(d, a, r1, r2, cor):
    d.line((CX + math.cos(a) * r1, CY + math.sin(a) * r1, CX + math.cos(a) * r2, CY + math.sin(a) * r2), fill=cor, width=max(2, round(ESC)))


def icone():
    base = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    ImageDraw.Draw(base).ellipse(caixa(194), fill=(2, 10, 18, 255))  # fundo escuro pro ícone ler em qualquer papel de parede

    # 1) HUD externo — círculo fino + 96 notas
    img, d = camada()
    cor = rgb(SEC, 0.45 * 255)
    d.ellipse(caixa(190), outline=cor, width=max(2, round(ESC)))
    for i in range(96):
        raio(d, i / 96 * math.tau, 186 * ESC, 190 * ESC, cor)
    base = Image.alpha_composite(base, img)

    # 2) anel técnico segmentado (48/30)
    base = anel_segmentado(base, 174, 4, 48, 30, 3, "#00BFFF", 15)

    # 3) ticks radiais (120, maior a cada 10)
    img, d = camada()
    for i in range(120):
        r2 = 158 * ESC
        raio(d, i / 120 * math.tau - math.pi / 2, r2 - (12 if i % 10 == 0 else 5) * ESC, r2, rgb(PRIM, 0.8 * 255))
    base = Image.alpha_composite(base, img)

    # 4) e 5) anéis de energia; 6) anel mecânico (12 blocos)
    base = anel_segmentado(base, 140, 12, 16, 11, 4, "#00CFFF", 200)
    base = anel_segmentado(base, 116, 8, 24, 18, 3, SEC, 60)
    base = anel_segmentado(base, 91, 7, 12, 12, 6, PRIM, 0)

    # 7) raios internos (32) + brilho central
    base = Image.alpha_composite(base, radial(72, [(0, rgb(ALTO)), (0.5, rgb("#00BFFF")), (1, rgb("#00BFFF", 0))], 0.9))
    img, d = camada()
    for i in range(32):
        raio(d, i / 32 * math.tau, 0, 72 * ESC, rgb("#00BFFF", 0.35 * 255))
    base = Image.alpha_composite(base, img)

    # 8) núcleo concêntrico (4 anéis) + bloom central
    for i in range(4, 0, -1):
        r = 48 * i / 4
        img, d = camada()
        d.ellipse(caixa(r), fill=rgb(NUCLEO, 0.9 * 255))
        base = Image.alpha_composite(base, img)
        img, d = camada()
        d.ellipse(caixa(r + 1), outline=rgb(PRIM, (0.5 + i / 8) * 255), width=round(2 * ESC))
        base = com_brilho(base, img, 6)
    base = Image.alpha_composite(base, radial(48 * 0.9, [(0, rgb("#00CFFF")), (0.6, rgb(PRIM)), (1, rgb(PRIM, 0))], 0.85))

    # rótulo JARVIS (Orbitron bold, espaçado, cor alta com halo ciano)
    fonte = ImageFont.truetype(str(FONTE), round(22 * ESC))
    try:
        fonte.set_variation_by_axes([700])
    except Exception:
        pass
    esp = 5 * ESC
    larguras = [fonte.getlength(c) for c in "JARVIS"]
    x = CX - (sum(larguras) + esp * 5) / 2
    texto, d = camada()
    for c, w in zip("JARVIS", larguras):
        d.text((x, CY), c, font=fonte, fill=rgb(ALTO), anchor="lm", stroke_width=round(1.2 * ESC), stroke_fill=rgb(ALTO))
        x += w + esp
    halo = Image.new("RGBA", (L, L), rgb(PRIM, 0))
    halo.putalpha(texto.getchannel("A"))
    base = Image.alpha_composite(base, halo.filter(ImageFilter.GaussianBlur(14 * ESC)))
    base = Image.alpha_composite(base, halo.filter(ImageFilter.GaussianBlur(5 * ESC)))
    base = Image.alpha_composite(base, texto)

    # recorta no círculo, para o canto ficar transparente
    mascara = Image.new("L", (L, L), 0)
    ImageDraw.Draw(mascara).ellipse(caixa(194), fill=255)
    base.putalpha(ImageChops.multiply(base.getchannel("A"), mascara))
    return base


if __name__ == "__main__":
    img = icone()
    img.resize((512, 512), Image.LANCZOS).save(MARCA / "jarvis-512.png")
    img.resize((192, 192), Image.LANCZOS).save(MARCA / "jarvis-192.png")
    img.save(MARCA / "jarvis.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ícone gerado em", MARCA)
