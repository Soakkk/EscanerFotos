"""Procesado de imagen de EscanerFotos (OpenCV/PIL puro, sin Qt).
Separado para poder probarlo automáticamente."""

import os
import cv2
import numpy as np
from PIL import Image, ImageOps


def igualar_iluminacion(imagen):
    """Quita sombras y luz irregular: estima la iluminación de fondo con un
    desenfoque grande y normaliza la imagen dividiéndola por ese fondo.
    Entra y sale BGR del mismo tamaño."""
    salida = []
    for canal in cv2.split(imagen):
        fondo = cv2.GaussianBlur(canal, (0, 0), sigmaX=25)
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
    Aplica varias estrategias en cascada:
      1) Canny + búsqueda de cuadrilátero con varios epsilons
      2) Umbral adaptativo + búsqueda de cuadrilátero
      3) Máscara HSV (papel = baja saturación + alto brillo) + minAreaRect
      4) Umbral global Otsu + minAreaRect
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

    # Estrategia 1: Canny
    desenfoque = cv2.GaussianBlur(gris, (5, 5), 0)
    bordes = cv2.Canny(desenfoque, 50, 150)
    bordes = cv2.morphologyEx(bordes, cv2.MORPH_CLOSE, kernel)
    pts = _buscar_cuadrilatero(bordes, forma)
    if pts is not None:
        return pts / ratio

    # Estrategia 2: Umbral adaptativo invertido
    th = cv2.adaptiveThreshold(
        gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 10
    )
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
    pts = _buscar_cuadrilatero(th, forma)
    if pts is not None:
        return pts / ratio

    # Estrategia 3: Máscara HSV (papel blanco = poca saturación)
    hsv = cv2.cvtColor(img_p, cv2.COLOR_BGR2HSV)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    mascara = ((s < 60) & (v > 90)).astype(np.uint8) * 255
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kernel_g)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kernel_g)
    pts = _buscar_cuadrilatero(mascara, forma)
    if pts is not None:
        return pts / ratio
    contornos, _ = cv2.findContours(
        mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if contornos:
        c = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(c) > forma[0] * forma[1] * 0.15:
            rect = cv2.minAreaRect(c)
            box = cv2.boxPoints(rect)
            return box.astype(np.float32) / ratio

    # Estrategia 4: Otsu + minAreaRect (último recurso)
    _, th_g = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th_g = cv2.morphologyEx(th_g, cv2.MORPH_CLOSE, kernel_g)
    contornos, _ = cv2.findContours(
        th_g, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if contornos:
        c = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(c) > forma[0] * forma[1] * 0.2:
            rect = cv2.minAreaRect(c)
            box = cv2.boxPoints(rect)
            return box.astype(np.float32) / ratio

    return None


def _buscar_cuadrilatero(mascara, forma):
    """Busca el mayor contorno cuadrilátero probando varios epsilons."""
    h, w = forma
    area_total = h * w
    contornos, _ = cv2.findContours(
        mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    contornos = sorted(contornos, key=cv2.contourArea, reverse=True)[:10]

    for c in contornos:
        area = cv2.contourArea(c)
        if area < area_total * 0.08:
            continue
        peri = cv2.arcLength(c, True)
        for eps in (0.02, 0.03, 0.04, 0.05):
            aprox = cv2.approxPolyDP(c, eps * peri, True)
            if len(aprox) == 4:
                return aprox.reshape(4, 2).astype(np.float32)

    return None


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


def filtro_bn_escaner(imagen):
    """Convierte a B/N tipo escáner. Pensado para usarse tras igualar_iluminacion."""
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = cv2.GaussianBlur(gris, (3, 3), 0)
    bn = cv2.adaptiveThreshold(
        gris, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 15
    )
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


def aplicar_pipeline(base, filtro_idx, brillo, contraste, nitidez):
    if filtro_idx == 0:        # B/N escáner
        img = filtro_bn_escaner(igualar_iluminacion(base))
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
    extensiones = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    archivos = sorted([
        f for f in os.listdir(carpeta_entrada)
        if os.path.splitext(f)[1].lower() in extensiones
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
