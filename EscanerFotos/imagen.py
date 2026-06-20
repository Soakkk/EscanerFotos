"""Procesado de imagen de EscanerFotos (OpenCV/PIL puro, sin Qt).
Separado para poder probarlo automáticamente."""

import os
import cv2
import numpy as np
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    _HEIF_DISPONIBLE = True
except ImportError:
    _HEIF_DISPONIBLE = False

# Única lista de formatos admitidos (diálogos, drag&drop, lotes, carpeta vigilada).
EXTENSIONES_IMAGEN = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp') + \
    (('.heic', '.heif') if _HEIF_DISPONIBLE else ())


def es_ruta_imagen(ruta):
    """True si la extensión del archivo es un formato de imagen admitido."""
    return ruta.lower().endswith(EXTENSIONES_IMAGEN)


def igualar_iluminacion(imagen):
    """Quita sombras y luz irregular: estima la iluminación de fondo con un
    desenfoque grande y normaliza la imagen dividiéndola por ese fondo.
    Entra y sale BGR del mismo tamaño. El sigma se escala con la resolución
    para que el resultado no dependa del tamaño de la imagen."""
    sigma = 25 * max(1.0, max(imagen.shape[:2]) / 1400.0)
    salida = []
    for canal in cv2.split(imagen):
        fondo = cv2.GaussianBlur(canal, (0, 0), sigmaX=sigma)
        norm = cv2.divide(canal, fondo, scale=255)
        salida.append(norm)
    return cv2.merge(salida)


def buffer_rgb_a_cv(buffer, w, h, bytes_per_line):
    """Convierte un buffer RGB888 (con posible padding por fila) en imagen BGR OpenCV."""
    arr = np.frombuffer(buffer, dtype=np.uint8).reshape(h, bytes_per_line)
    arr = arr[:, : w * 3].reshape(h, w, 3)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def detectar_documento(imagen):
    """
    Detecta los 4 vértices de un documento dentro de la imagen.
    Genera candidatos con varias estrategias (Canny, umbral adaptativo,
    máscara HSV de papel, Otsu) y se queda con el de mejor puntuación
    (tamaño × rectangularidad × fiabilidad de la estrategia), en lugar de
    aceptar el primero que aparezca.
    Devuelve puntos o None si no detecta nada.
    """
    altura_orig, anchura_orig = imagen.shape[:2]

    ratio = 1000.0 / max(altura_orig, anchura_orig)
    if ratio < 1.0:
        img_p = cv2.resize(imagen, None, fx=ratio, fy=ratio)
    else:
        img_p = imagen.copy()
        ratio = 1.0

    gris = cv2.cvtColor(img_p, cv2.COLOR_BGR2GRAY)
    forma = img_p.shape[:2]
    kernel = np.ones((5, 5), np.uint8)
    kernel_g = np.ones((11, 11), np.uint8)
    candidatos = []   # (puntos, peso de la estrategia)

    # Estrategia 1: Canny
    desenfoque = cv2.GaussianBlur(gris, (5, 5), 0)
    bordes = cv2.Canny(desenfoque, 50, 150)
    bordes = cv2.morphologyEx(bordes, cv2.MORPH_CLOSE, kernel)
    candidatos += [(p, 1.0) for p in _cuadrilateros_en(bordes, forma)]

    # Estrategia 2: Umbral adaptativo invertido
    th = cv2.adaptiveThreshold(
        gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 10
    )
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
    candidatos += [(p, 0.95) for p in _cuadrilateros_en(th, forma)]

    # Estrategia 3: Máscara HSV (papel blanco = poca saturación)
    hsv = cv2.cvtColor(img_p, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    mascara = ((s < 60) & (v > 90)).astype(np.uint8) * 255
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kernel_g)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kernel_g)
    candidatos += [(p, 0.9) for p in _cuadrilateros_en(mascara, forma)]
    caja = _caja_mayor_contorno(mascara, forma, area_min=0.15)
    if caja is not None:
        candidatos.append((caja, 0.7))

    # Estrategia 4: Otsu + minAreaRect (último recurso)
    _, th_g = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th_g = cv2.morphologyEx(th_g, cv2.MORPH_CLOSE, kernel_g)
    caja = _caja_mayor_contorno(th_g, forma, area_min=0.2)
    if caja is not None:
        candidatos.append((caja, 0.65))

    mejor, mejor_punt = None, 0.0
    for pts, peso in candidatos:
        punt = _puntuar_candidato(pts, forma) * peso
        if punt > mejor_punt:
            mejor, mejor_punt = pts, punt
    if mejor is None:
        return None
    return mejor / ratio


def _puntuar_candidato(pts, forma):
    """Puntuación 0..1 de un cuadrilátero candidato: fracción de imagen que
    ocupa × rectangularidad (área / área de su rectángulo mínimo). Descarta
    candidatos no convexos, minúsculos o que son el marco entero de la foto."""
    h, w = forma
    contorno = pts.reshape(-1, 1, 2).astype(np.float32)
    if not cv2.isContourConvex(contorno.astype(np.int32)):
        return 0.0
    area = cv2.contourArea(contorno)
    frac = area / (h * w)
    if frac < 0.08 or frac > 0.985:
        return 0.0
    rect = cv2.minAreaRect(contorno)
    area_rect = rect[1][0] * rect[1][1]
    if area_rect <= 0:
        return 0.0
    rectangularidad = min(1.0, area / area_rect)
    return frac * rectangularidad


def _cuadrilateros_en(mascara, forma):
    """Todos los contornos grandes que aproximan bien a un cuadrilátero."""
    h, w = forma
    area_total = h * w
    contornos, _ = cv2.findContours(
        mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    contornos = sorted(contornos, key=cv2.contourArea, reverse=True)[:10]

    resultado = []
    for c in contornos:
        area = cv2.contourArea(c)
        if area < area_total * 0.08:
            continue
        peri = cv2.arcLength(c, True)
        for eps in (0.02, 0.03, 0.04, 0.05):
            aprox = cv2.approxPolyDP(c, eps * peri, True)
            if len(aprox) == 4:
                resultado.append(aprox.reshape(4, 2).astype(np.float32))
                break
    return resultado


def _caja_mayor_contorno(mascara, forma, area_min):
    """Rectángulo mínimo del mayor contorno si ocupa al menos `area_min`."""
    contornos, _ = cv2.findContours(
        mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contornos:
        return None
    c = max(contornos, key=cv2.contourArea)
    if cv2.contourArea(c) <= forma[0] * forma[1] * area_min:
        return None
    rect = cv2.minAreaRect(c)
    return cv2.boxPoints(rect).astype(np.float32)


def ordenar_puntos(puntos):
    """Ordena 4 puntos como [arriba-izq, arriba-der, abajo-der, abajo-izq]."""
    rect = np.zeros((4, 2), dtype=np.float32)
    suma = puntos.sum(axis=1)
    rect[0] = puntos[np.argmin(suma)]
    rect[2] = puntos[np.argmax(suma)]
    diff = np.diff(puntos, axis=1)
    rect[1] = puntos[np.argmin(diff)]
    rect[3] = puntos[np.argmax(diff)]
    return rect


def corregir_perspectiva(imagen, puntos):
    """Endereza el documento aplicando transformación de perspectiva."""
    puntos_ordenados = ordenar_puntos(puntos)
    (tl, tr, br, bl) = puntos_ordenados

    ancho_a = np.linalg.norm(br - bl)
    ancho_b = np.linalg.norm(tr - tl)
    ancho_max = max(int(ancho_a), int(ancho_b))

    alto_a = np.linalg.norm(tr - br)
    alto_b = np.linalg.norm(tl - bl)
    alto_max = max(int(alto_a), int(alto_b))

    if ancho_max < 10 or alto_max < 10:
        return imagen.copy()

    dst = np.array([
        [0, 0],
        [ancho_max - 1, 0],
        [ancho_max - 1, alto_max - 1],
        [0, alto_max - 1]
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(puntos_ordenados, dst)
    return cv2.warpPerspective(
        imagen, M, (ancho_max, alto_max), flags=cv2.INTER_CUBIC
    )


def binarizar_sauvola(gris, ventana=25, k=0.2, R=128.0):
    """Binarización local de Sauvola (umbral por píxel según media y desviación
    del entorno). Entra gris uint8, sale uint8 con solo 0 (texto) y 255 (fondo)."""
    if ventana % 2 == 0:
        ventana += 1
    g = gris.astype(np.float32)
    media = cv2.boxFilter(g, ddepth=-1, ksize=(ventana, ventana),
                          normalize=True, borderType=cv2.BORDER_REPLICATE)
    media_sq = cv2.boxFilter(g * g, ddepth=-1, ksize=(ventana, ventana),
                             normalize=True, borderType=cv2.BORDER_REPLICATE)
    var = np.clip(media_sq - media * media, 0, None)
    std = np.sqrt(var)
    T = media * (1.0 + k * (std / R - 1.0))
    return np.where(g > T, 255, 0).astype(np.uint8)


def _aplanar_fondo(gris):
    """Lleva el fondo del documento a blanco uniforme: estima la iluminación
    con un cierre morfológico a baja resolución (el cierre borra la tinta,
    cosa que un desenfoque no hace: evita halos alrededor del texto) y
    divide la imagen por ese fondo. Independiente de la resolución.
    El fondo se acota por abajo para no amplificar el ruido de las zonas
    muy oscuras (sombras profundas)."""
    h, w = gris.shape[:2]
    factor = max(1, max(h, w) // 700)
    peq = cv2.resize(gris, (max(1, w // factor), max(1, h // factor)),
                     interpolation=cv2.INTER_AREA)
    # Mediana grande: borra el texto (los trazos son minoría en la ventana)
    # y, a diferencia de un cierre morfológico, no se deja arrastrar por
    # píxeles "sal" brillantes del ruido o del JPEG.
    fondo = cv2.medianBlur(peq, 21)
    fondo = cv2.GaussianBlur(fondo, (0, 0), 3)
    fondo = cv2.resize(fondo, (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.divide(gris, np.maximum(fondo, 50), scale=255)


def _quitar_motas(bn, area_min, escala=1.0):
    """Borra las manchas negras pequeñas Y aisladas (ruido). Una mancha
    pequeña pegada a un trazo grande se conserva: así sobreviven los puntos,
    tildes y comas, que siempre están junto al texto. 0 = tinta, 255 = fondo."""
    inv = (bn == 0).astype(np.uint8)
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    areas = stats[:, cv2.CC_STAT_AREA]
    pequenas = areas < area_min
    pequenas[0] = False
    if not pequenas.any():
        return bn
    grandes = ~pequenas
    grandes[0] = False
    cerca = np.isin(etiquetas, np.where(grandes)[0]).astype(np.uint8)
    lado = int(round(15 * escala)) | 1
    cerca = cv2.dilate(cerca, np.ones((lado, lado), np.uint8))
    quitar = np.isin(etiquetas, np.where(pequenas)[0]) & (cerca == 0)
    salida = bn.copy()
    salida[quitar] = 255
    return salida


def _mascara_tinta(plano, escala, k=0.12, contraste_min=40):
    """Máscara de tinta (0 = trazo, 255 = fondo) sobre la imagen aplanada:
    Sauvola + un contraste mínimo frente al blanco global (la imagen ya
    viene con el fondo aplanado a ~255: el ruido de las sombras solo baja
    ~30 niveles y se descarta; la tinta real baja bastante más) + limpieza
    de motas aisladas. La máscara decide QUÉ es texto; el tono lo pone
    cada filtro."""
    ventana = int(round(31 * escala)) | 1
    mascara = binarizar_sauvola(plano, ventana=ventana, k=k)
    mascara[plano > 255 - contraste_min] = 255
    return _quitar_motas(mascara, max(6, int(round(12 * escala * escala))), escala)


def _preparar_bn(imagen):
    """Trabajo común de los dos filtros B/N: aplanar la iluminación, realzar
    los trazos (ayuda a Sauvola a ver el texto débil) y calcular la máscara
    de tinta. Devuelve (escala, realzado, mascara)."""
    escala = max(1.0, max(imagen.shape[:2]) / 1400.0)
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    plano = _aplanar_fondo(gris)
    suave = cv2.GaussianBlur(plano, (0, 0), 1.0 * escala)
    realzado = cv2.addWeighted(plano, 1.6, suave, -0.6, 0)
    mascara = _mascara_tinta(cv2.medianBlur(realzado, 3), escala)
    return escala, realzado, mascara


def filtro_bn_escaner(imagen, intensidad=50):
    """B/N estilo escáner con texto nítido (estilo CamScanner).
    1) Aplana la iluminación y realza los trazos.
    2) Decide qué es tinta con una máscara Sauvola despeckleada
       (el fondo queda blanco PURO, sin motas grises).
    3) Dentro de la tinta estira el contraste según los percentiles de la
       propia tinta (el trazo más oscuro va a negro aunque la foto sea
       floja) y conserva bordes antialiasados: texto nítido, no pixelado.
    `intensidad` (0-100): cuánto se oscurece la tinta (50 = neutro)."""
    escala, realzado, mascara = _preparar_bn(imagen)

    # La zona de tinta se ensancha 1-2 px para conservar el borde suave
    lado = 2 * int(round(escala)) + 1
    zona_tinta = cv2.erode(mascara, np.ones((lado, lado), np.uint8)) == 0

    tinta = realzado[mascara == 0]
    if tinta.size < 50:           # página prácticamente en blanco
        return cv2.cvtColor(np.full(imagen.shape[:2], 255, np.uint8),
                            cv2.COLOR_GRAY2BGR)
    negro = float(np.percentile(tinta, 20))
    blanco = min(max(float(np.percentile(tinta, 92)), negro + 40.0), 240.0)
    norm = np.clip((realzado.astype(np.float32) - negro) / (blanco - negro), 0, 1)
    gamma = 0.65 + 0.013 * float(intensidad)   # 0.65 .. 1.95 (50 -> 1.3)
    rampa = (norm ** gamma) * 255.0

    out = np.where(zona_tinta, rampa, 255.0).astype(np.uint8)
    return cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)


def filtro_bn_puro(imagen, intensidad=50):
    """B/N de 1 bit (solo negro y blanco puros): la misma máscara de tinta
    que el B/N nítido, pero sin medios tonos. Produce PDFs mínimos
    (se incrustan con CCITT G4).
    `intensidad` (0-100) ajusta el grosor del trazo (50 = neutro)."""
    escala, _, bn = _preparar_bn(imagen)
    if intensidad > 55:
        r = min(3, 1 + (intensidad - 55) // 20)
    elif intensidad < 45:
        r = -min(3, 1 + (45 - intensidad) // 20)
    else:
        r = 0
    if r:
        lado = max(1, min(9, int(round(abs(r) * escala))))
        kernel = np.ones((lado, lado), np.uint8)
        bn = cv2.erode(bn, kernel) if r > 0 else cv2.dilate(bn, kernel)
    return cv2.cvtColor(bn, cv2.COLOR_GRAY2BGR)


def balance_blancos_scb(imagen, recorte=0.5, suelo=0, techo=255):
    """Simplest Color Balance (Limare, Lisani, Morel, Petro & Sbert, IPOL
    2011: https://www.ipol.im/pub/art/2011/llmps-scb/). Por cada canal de
    color satura el `recorte` % de píxeles más oscuros y el `recorte` % más
    claros y estira el resto con una transformación afín al rango
    [suelo, techo]. Equilibra el blanco y realza el contraste sin los virajes
    de color del 'gris-mundo' y, al saturar solo los extremos, sin quemar.

    `suelo`/`techo` dejan margen en negros y blancos para no reventar la
    imagen (con 0 y 255 es el algoritmo original). Los percentiles se estiman
    sobre una copia reducida: rápido e independiente de la resolución."""
    h, w = imagen.shape[:2]
    if max(h, w) > 600:
        r = 600.0 / max(h, w)
        muestra = cv2.resize(imagen, None, fx=r, fy=r, interpolation=cv2.INTER_AREA)
    else:
        muestra = imagen
    salida = []
    for c in range(3):
        canal = imagen[:, :, c].astype(np.float32)
        lo, hi = np.percentile(muestra[:, :, c], (recorte, 100.0 - recorte))
        if hi <= lo:
            salida.append(imagen[:, :, c])
            continue
        esc = (canal - lo) * ((techo - suelo) / (hi - lo)) + suelo
        salida.append(np.clip(esc, 0, 255).astype(np.uint8))
    return cv2.merge(salida)


def filtro_color_mejorado(imagen, intensidad=50):
    """Color limpio para DNI y fotos: corrige la dominante de luz e iguala el
    blanco SIN quemar. A diferencia del 'gris-mundo' (que vira los colores) y
    de la igualación de luz por división (que revienta a blanco las zonas
    claras del DNI), aquí se usa:
      1) reducción de ruido conservando bordes (bilateral),
      2) balance de blancos robusto con Simplest Color Balance, dejando
         margen en negros (8) y blancos (248) para no reventar,
      3) realce de contraste local suave (CLAHE sobre la luminancia),
         mezclado con la original para no exagerar.
    `intensidad` (0-100) gradúa el realce; 50 = neutro, 0 = casi sin tocar."""
    t = intensidad / 50.0          # 0..2, 1 = neutro

    base = cv2.bilateralFilter(imagen, 7, 45, 7)

    # Balance de blancos. El techo de blancos se queda SIEMPRE por debajo de
    # 250 (incluso a intensidad máxima): así un reflejo o el flash no revientan
    # a blanco puro, que era el origen del 'quemado'. El brillo apenas baja.
    recorte = 0.3 + 0.4 * min(t, 1.5)        # 0.3 .. 0.9 %
    techo = 238 + int(10 * min(t, 1.0))      # 238 (suave) .. 248 (fuerte)
    base = balance_blancos_scb(base, recorte=recorte, suelo=6, techo=techo)

    # Contraste local suave sobre la luminancia, mezclado con la original.
    lab = cv2.cvtColor(base, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clip = 1.0 + 0.7 * min(t, 1.6)           # 1.0 .. ~2.1
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
    l_eq = clahe.apply(l)
    peso = 0.35 + 0.30 * min(t, 1.5)         # 0.35 .. 0.80
    l = cv2.addWeighted(l_eq, peso, l, 1.0 - peso, 0)
    lab = cv2.merge([l, a, b])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def aplicar_ajustes(imagen, brillo, contraste, nitidez):
    """Aplica brillo (-100..100), contraste (-100..100) y nitidez (0..100)."""
    alfa = 1.0 + (contraste / 100.0)
    beta = float(brillo)
    ajustada = cv2.convertScaleAbs(imagen, alpha=alfa, beta=beta)

    if nitidez > 0:
        intensidad = nitidez / 50.0
        gaus = cv2.GaussianBlur(ajustada, (0, 0), 2)
        ajustada = cv2.addWeighted(
            ajustada, 1.0 + intensidad, gaus, -intensidad, 0
        )
    return ajustada


def rotar_imagen(imagen, grados):
    """Rota la imagen 90, 180 o 270 grados."""
    if grados == 90:
        return cv2.rotate(imagen, cv2.ROTATE_90_CLOCKWISE)
    if grados == 180:
        return cv2.rotate(imagen, cv2.ROTATE_180)
    if grados == 270:
        return cv2.rotate(imagen, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return imagen


def cv_a_pil(imagen_cv):
    """Convierte imagen OpenCV BGR a PIL RGB."""
    rgb = cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    return pil.convert("RGB") if pil.mode != "RGB" else pil


def es_bilevel(imagen_cv):
    """True si la imagen BGR es blanco y negro puro: sin color (los tres
    canales iguales) y con como mucho dos niveles de gris."""
    b, g, r = imagen_cv[:, :, 0], imagen_cv[:, :, 1], imagen_cv[:, :, 2]
    if (b != g).any() or (g != r).any():
        return False
    return len(np.unique(b)) <= 2


def cv_a_pil_pdf(imagen_cv):
    """PIL listo para incrustar en PDF. Si la imagen es B/N puro la convierte
    a modo '1' (1 bit por píxel): Pillow la comprime con CCITT G4 y una
    factura pasa de ~1 MB a decenas de KB."""
    if not es_bilevel(imagen_cv):
        return cv_a_pil(imagen_cv)
    gris = imagen_cv[:, :, 0]
    vals = np.unique(gris)
    umbral = float(vals.mean()) if len(vals) == 2 else 127.0
    bw = ((gris > umbral) * 255).astype(np.uint8)
    return Image.fromarray(bw, mode="L").convert("1", dither=Image.Dither.NONE)


def codificar_pagina(imagen_cv):
    """Comprime una página para retenerla en memoria sin comerse la RAM:
    PNG (sin pérdida, minúsculo) si es B/N puro; JPEG 95 si tiene color.
    Devuelve bytes."""
    if es_bilevel(imagen_cv):
        ok, buf = cv2.imencode(".png", imagen_cv[:, :, 0],
                               [cv2.IMWRITE_PNG_COMPRESSION, 3])
    else:
        ok, buf = cv2.imencode(".jpg", imagen_cv,
                               [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise RuntimeError("No se pudo comprimir la página")
    return buf.tobytes()


def decodificar_pagina(datos):
    """Bytes de codificar_pagina -> imagen OpenCV BGR."""
    arr = np.frombuffer(datos, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def pagina_a_pil_pdf(datos):
    """Bytes de codificar_pagina -> PIL óptimo para PDF."""
    return cv_a_pil_pdf(decodificar_pagina(datos))


# Página A4 a 200 ppp (la resolución con la que se exportan los PDF).
A4_ANCHO_200DPI = 1654
A4_ALTO_200DPI = 2339


def componer_dni(img_arriba, img_abajo,
                 ancho=A4_ANCHO_200DPI, alto=A4_ALTO_200DPI):
    """Compone las dos caras de un DNI (u otro carnet) en una sola hoja A4
    vertical: una imagen centrada en la mitad superior y otra en la inferior,
    como al fotocopiar un DNI. Entran y sale BGR."""
    hoja = np.full((alto, ancho, 3), 255, dtype=np.uint8)
    margen_x = int(ancho * 0.08)
    margen_y = int(alto * 0.06)
    hueco = int(alto * 0.04)
    zona_w = ancho - 2 * margen_x
    zona_h = (alto - 2 * margen_y - hueco) // 2

    for i, img in enumerate((img_arriba, img_abajo)):
        h, w = img.shape[:2]
        r = min(zona_w / w, zona_h / h)
        nw, nh = max(1, int(w * r)), max(1, int(h * r))
        interp = cv2.INTER_AREA if r < 1.0 else cv2.INTER_CUBIC
        red = cv2.resize(img, (nw, nh), interpolation=interp)
        x = margen_x + (zona_w - nw) // 2
        y = margen_y + i * (zona_h + hueco) + (zona_h - nh) // 2
        hoja[y:y + nh, x:x + nw] = red

    return hoja


def leer_imagen(ruta):
    """
    Lee una imagen de disco como array OpenCV BGR, corrigiendo la
    orientación según los metadatos EXIF (las fotos de móvil a menudo
    vienen tumbadas). Soporta rutas con caracteres no ASCII.
    """
    with Image.open(ruta) as pil:
        pil = ImageOps.exif_transpose(pil)
        rgb = np.array(pil.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def aplicar_pipeline(base, filtro_idx, brillo, contraste, nitidez, intensidad_bn=50):
    if filtro_idx == 0:        # B/N nítido (texto suave, estilo CamScanner)
        img = filtro_bn_escaner(base, intensidad_bn)
    elif filtro_idx == 1:      # B/N puro tinta (1 bit, PDFs mínimos)
        img = filtro_bn_puro(base, intensidad_bn)
    elif filtro_idx == 2:      # Color limpio (DNI, fotos)
        img = filtro_color_mejorado(base, intensidad_bn)
    else:                      # Color original
        img = base.copy()
    if brillo or contraste or nitidez:
        img = aplicar_ajustes(img, brillo, contraste, nitidez)
    return img


def procesar_lote(carpeta_entrada, carpeta_salida, filtro_idx, brillo, contraste, nitidez, cb_progreso=None):
    """
    Procesa todas las imágenes de carpeta_entrada con los ajustes actuales
    y las guarda como JPG en carpeta_salida.
    Llama cb_progreso(i, total, nombre) en cada paso si se proporciona.
    Devuelve (n_ok, n_errores, lista_mensajes_error).
    """
    archivos = sorted([
        f for f in os.listdir(carpeta_entrada)
        if es_ruta_imagen(f)
    ])
    os.makedirs(carpeta_salida, exist_ok=True)

    n_ok, errores = 0, []
    for i, nombre in enumerate(archivos):
        if cb_progreso:
            cb_progreso(i, len(archivos), nombre)
        try:
            ruta = os.path.join(carpeta_entrada, nombre)
            img = leer_imagen(ruta)
            if img is None:
                raise ValueError("OpenCV no pudo leer el archivo")

            puntos = detectar_documento(img)
            if puntos is not None:
                img = corregir_perspectiva(img, puntos)

            img = aplicar_pipeline(img, filtro_idx, brillo, contraste, nitidez)

            nombre_salida = os.path.splitext(nombre)[0] + ".jpg"
            ruta_salida = os.path.join(carpeta_salida, nombre_salida)
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not ok:
                raise RuntimeError("cv2.imencode falló")
            buf.tofile(ruta_salida)
            n_ok += 1
        except Exception as e:
            errores.append(f"{nombre}: {e}")

    return n_ok, len(errores), errores
