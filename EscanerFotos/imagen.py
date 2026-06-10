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


def filtro_bn_escaner(imagen, intensidad=50):
    """B/N estilo escáner: iguala la luz, binariza con Sauvola, limpia motas y
    ajusta el grosor del texto según `intensidad` (0-100, 50 = neutro).
    Los tamaños de ventana/kernel se escalan con la resolución para que la
    vista previa (reducida a ~1400 px) coincida con el guardado a tamaño real."""
    escala = max(1.0, max(imagen.shape[:2]) / 1400.0)
    base = igualar_iluminacion(imagen)
    gris = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    ventana = int(round(25 * escala)) | 1
    bn = binarizar_sauvola(gris, ventana=ventana, k=0.2)
    bn = cv2.medianBlur(bn, 3 if escala < 1.5 else 5)
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


def filtro_color_mejorado(imagen):
    """Mejora luz y color manteniendo la imagen en color. Ideal para DNI."""
    lab = cv2.cvtColor(imagen, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    mejorada = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    f = mejorada.astype(np.float32)
    avg_b = float(np.mean(f[:, :, 0]))
    avg_g = float(np.mean(f[:, :, 1]))
    avg_r = float(np.mean(f[:, :, 2]))
    avg = (avg_b + avg_g + avg_r) / 3.0
    if avg_b > 1 and avg_g > 1 and avg_r > 1:
        f[:, :, 0] *= avg / avg_b
        f[:, :, 1] *= avg / avg_g
        f[:, :, 2] *= avg / avg_r
    mejorada = np.clip(f, 0, 255).astype(np.uint8)

    mejorada = cv2.bilateralFilter(mejorada, 5, 35, 35)
    return mejorada


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
    if filtro_idx == 0:        # B/N escáner (iguala la luz internamente)
        img = filtro_bn_escaner(base, intensidad_bn)
    elif filtro_idx == 1:      # Color con luz corregida
        img = filtro_color_mejorado(igualar_iluminacion(base))
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
