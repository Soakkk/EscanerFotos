"""Genera el icono de EscanerFotos (icono.ico + icono.png) con Pillow.

Diseño: documento blanco sobre fondo azul con la barra de luz verde de un
escáner cruzándolo. Plano y con pocas formas para que siga siendo legible
a 16×16 px. Ejecutar desde esta carpeta:  python generar_icono.py
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = 1024                       # se dibuja grande y se reescala

AZUL_ARRIBA = (56, 124, 248)
AZUL_ABAJO = (24, 80, 192)
PAPEL = (250, 251, 253, 255)
PLIEGUE = (210, 219, 231, 255)
LINEA = (146, 158, 174, 255)
VERDE_LUZ = (62, 224, 166)


def _fondo_degradado():
    """Cuadrado redondeado con degradado vertical azul."""
    arriba = np.array(AZUL_ARRIBA, dtype=np.float64)
    abajo = np.array(AZUL_ABAJO, dtype=np.float64)
    t = np.linspace(0.0, 1.0, S)[:, None, None]
    franja = arriba * (1 - t) + abajo * t
    rgb = np.broadcast_to(franja, (S, S, 3)).astype(np.uint8)
    fondo = Image.fromarray(rgb, "RGB").convert("RGBA")

    mascara = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        (0, 0, S - 1, S - 1), radius=int(S * 0.225), fill=255)
    fondo.putalpha(mascara)
    return fondo


def _documento():
    """Hoja blanca con esquina plegada y líneas de texto, algo girada."""
    dw, dh = 520, 680
    pliegue = 130
    doc = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
    d = ImageDraw.Draw(doc)
    # Silueta de la hoja con la esquina superior derecha recortada
    d.rounded_rectangle((0, 0, dw - 1, dh - 1), radius=44, fill=PAPEL)
    d.polygon([(dw - pliegue - 6, -2), (dw, -2), (dw, pliegue + 6)],
              fill=(0, 0, 0, 0))
    d.polygon([(dw - pliegue, 0), (dw, pliegue), (dw - pliegue, pliegue)],
              fill=PLIEGUE)
    # Líneas de texto
    x0, x1 = 92, dw - 110
    for i, (ancho, alto) in enumerate(
            [(0.62, 34), (1.0, 26), (1.0, 26), (0.78, 26)]):
        y = 150 + i * 92
        color = (96, 110, 130, 255) if i == 0 else LINEA
        d.rounded_rectangle(
            (x0, y, x0 + (x1 - x0) * ancho, y + alto),
            radius=alto // 2, fill=color)
    return doc.rotate(5, expand=True, resample=Image.Resampling.BICUBIC)


def _con_sombra(capa, desplaza=18, radio=22, alpha=90):
    sombra = Image.new("RGBA", capa.size, (0, 0, 0, 0))
    sombra.paste(Image.new("RGBA", capa.size, (10, 20, 40, alpha)),
                 mask=capa.getchannel("A"))
    sombra = sombra.filter(ImageFilter.GaussianBlur(radio))
    lienzo = Image.new("RGBA",
                       (capa.width + desplaza * 2, capa.height + desplaza * 2),
                       (0, 0, 0, 0))
    lienzo.alpha_composite(sombra, (desplaza, desplaza * 2))
    lienzo.alpha_composite(capa, (desplaza, desplaza))
    return lienzo


def _barra_escaner(img):
    """Barra de luz verde cruzando el icono, con halo hacia abajo."""
    capa = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    y = int(S * 0.585)
    margen = int(S * 0.075)
    # Halo: bandas consecutivas que se desvanecen bajo la barra
    alto_banda = 34
    for i, a in enumerate((84, 56, 32, 14)):
        d.rectangle((margen, y + i * alto_banda,
                     S - margen, y + (i + 1) * alto_banda),
                    fill=VERDE_LUZ + (a,))
    # Barra principal
    d.rounded_rectangle((margen, y - 16, S - margen, y + 16),
                        radius=16, fill=VERDE_LUZ + (255,))
    # Brillo superior fino
    d.rounded_rectangle((margen + 8, y - 16, S - margen - 8, y - 8),
                        radius=4, fill=(214, 255, 236, 160))
    img.alpha_composite(capa)


def _marca_verificacion():
    """check.png: marca blanca para las casillas marcadas (vía QSS)."""
    t = 64
    img = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(14, 34), (27, 47), (50, 18)], fill=(255, 255, 255, 255),
           width=9, joint="curve")
    img.resize((16, 16), Image.Resampling.LANCZOS).save("check.png")


def generar():
    img = _fondo_degradado()
    doc = _con_sombra(_documento())
    img.alpha_composite(doc, ((S - doc.width) // 2, (S - doc.height) // 2 - 10))
    _barra_escaner(img)

    img.resize((256, 256), Image.Resampling.LANCZOS).save("icono.png")
    img.save("icono.ico", sizes=[(256, 256), (128, 128), (64, 64),
                                 (48, 48), (32, 32), (24, 24), (16, 16)])
    _marca_verificacion()
    print("Generados icono.png, icono.ico y check.png")


if __name__ == "__main__":
    generar()
