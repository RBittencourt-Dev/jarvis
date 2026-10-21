"""Gera o ícone do Jarvis: o 7 da 7 SevenCode brilhando num núcleo escuro com anel ciano.

    python gerar-icone.py   →  web/marca/jarvis.ico, jarvis-192.png, jarvis-512.png
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

MARCA = Path(__file__).parent / "web" / "marca"
CIANO = (57, 208, 255)
L = 1024  # desenha grande e reduz: as bordas ficam lisas


def icone():
    base = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.ellipse((24, 24, L - 24, L - 24), fill=(5, 14, 24, 255))

    # brilho do núcleo: um disco ciano bem desfocado no centro
    brilho = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    ImageDraw.Draw(brilho).ellipse((260, 260, L - 260, L - 260), fill=CIANO + (150,))
    base = Image.alpha_composite(base, brilho.filter(ImageFilter.GaussianBlur(110)))

    # anel externo com brilho
    anel = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    ImageDraw.Draw(anel).ellipse((70, 70, L - 70, L - 70), outline=CIANO + (255,), width=34)
    base = Image.alpha_composite(base, anel.filter(ImageFilter.GaussianBlur(18)))
    base = Image.alpha_composite(base, anel)

    # o 7 de circuito (branco), com um halo ciano em volta
    sete = Image.open(MARCA / "sete.png").convert("RGBA").resize((600, 600), Image.LANCZOS)
    camada = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    camada.alpha_composite(sete, ((L - 600) // 2, (L - 600) // 2 + 10))
    halo = Image.new("RGBA", (L, L), CIANO + (0,))
    halo.putalpha(ImageChops.multiply(camada.getchannel("A"), Image.new("L", (L, L), 255)))
    base = Image.alpha_composite(base, halo.filter(ImageFilter.GaussianBlur(14)))
    base = Image.alpha_composite(base, camada)

    # recorta no círculo, para o canto ficar transparente
    mascara = Image.new("L", (L, L), 0)
    ImageDraw.Draw(mascara).ellipse((24, 24, L - 24, L - 24), fill=255)
    base.putalpha(ImageChops.multiply(base.getchannel("A"), mascara))
    return base


if __name__ == "__main__":
    img = icone()
    img.resize((512, 512), Image.LANCZOS).save(MARCA / "jarvis-512.png")
    img.resize((192, 192), Image.LANCZOS).save(MARCA / "jarvis-192.png")
    img.save(MARCA / "jarvis.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ícone gerado em", MARCA)
