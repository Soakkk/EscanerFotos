import numpy as np
import cv2
from imagen import igualar_iluminacion

def test_igualar_iluminacion_conserva_forma_y_tipo():
    img = (np.random.rand(80, 100, 3) * 255).astype(np.uint8)
    out = igualar_iluminacion(img)
    assert out.shape == img.shape
    assert out.dtype == np.uint8

def test_igualar_iluminacion_uniformiza_un_gradiente():
    h, w = 100, 200
    grad = np.tile(np.linspace(120, 255, w).astype(np.uint8), (h, 1))
    img = cv2.cvtColor(grad, cv2.COLOR_GRAY2BGR)
    out = igualar_iluminacion(img)
    g_in = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std()
    g_out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).std()
    assert g_out < g_in


from imagen import buffer_rgb_a_cv

def test_buffer_rgb_a_cv_respeta_padding_y_orden_bgr():
    w, h = 2, 2
    bpl = w * 3 + 2
    fila0 = bytes([255, 0, 0,  0, 255, 0]) + bytes([0, 0])
    fila1 = bytes([0, 0, 255,  9, 9, 9]) + bytes([0, 0])
    buf = fila0 + fila1
    out = buffer_rgb_a_cv(buf, w, h, bpl)
    assert out.shape == (2, 2, 3)
    assert tuple(int(x) for x in out[0, 0]) == (0, 0, 255)
    assert tuple(int(x) for x in out[0, 1]) == (0, 255, 0)


from imagen import aplicar_pipeline

def test_pipeline_tres_modos_conservan_tamano():
    img = (np.random.rand(120, 90, 3) * 255).astype(np.uint8)
    for modo in (0, 1, 2):
        out = aplicar_pipeline(img, modo, 0, 0, 0)
        assert out.shape == img.shape, f"modo {modo}"
        assert out.dtype == np.uint8


from imagen import binarizar_sauvola, filtro_bn_escaner

def test_sauvola_solo_da_0_y_255_y_conserva_tamano():
    gris = (np.random.rand(70, 90) * 255).astype(np.uint8)
    out = binarizar_sauvola(gris)
    assert out.shape == gris.shape
    assert out.dtype == np.uint8
    assert set(np.unique(out).tolist()).issubset({0, 255})

def test_sauvola_texto_fino_negro_sobre_fondo_con_sombra():
    h, w = 80, 160
    gris = np.tile(np.linspace(150, 255, w).astype(np.uint8), (h, 1)).copy()
    for y in (20, 30, 40, 50, 60):
        gris[y:y + 2, 30:130] = 15
    out = binarizar_sauvola(gris)
    assert out[20:22, 30:130].mean() < 60
    assert out[24:28, 30:130].mean() > 180


def _prop_negros(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float((g < 128).mean())

def test_filtro_bn_intensidad_controla_grosor():
    img = (np.random.rand(90, 120, 3) * 255).astype(np.uint8)
    baja = filtro_bn_escaner(img, intensidad=10)
    alta = filtro_bn_escaner(img, intensidad=90)
    assert baja.shape == img.shape and baja.dtype == np.uint8
    assert _prop_negros(alta) >= _prop_negros(baja)


def _documento_sintetico(w=2800, h=2100, lineas=True):
    """Foto sintética: 'papel' blanco con texto sobre fondo oscuro."""
    img = np.full((h, w, 3), 60, dtype=np.uint8)
    esquinas = np.array([[w * 0.2, h * 0.15], [w * 0.85, h * 0.2],
                         [w * 0.8, h * 0.9], [w * 0.15, h * 0.85]],
                        dtype=np.int32)
    cv2.fillPoly(img, [esquinas], (235, 235, 235))
    if lineas:
        for y in range(int(h * 0.3), int(h * 0.7), int(h * 0.06)):
            cv2.line(img, (int(w * 0.3), y), (int(w * 0.7), y), (30, 30, 30), 4)
    return img, esquinas.astype(np.float32)


def test_filtro_bn_consistente_entre_resoluciones():
    """La vista previa (reducida) y el guardado (tamaño real) deben dar
    una proporción de negro parecida gracias al escalado de parámetros."""
    grande, _ = _documento_sintetico(2800, 2100)
    r = 1400.0 / 2800.0
    pequena = cv2.resize(grande, None, fx=r, fy=r, interpolation=cv2.INTER_AREA)
    p_grande = _prop_negros(filtro_bn_escaner(grande))
    p_pequena = _prop_negros(filtro_bn_escaner(pequena))
    assert abs(p_grande - p_pequena) < 0.03, (p_grande, p_pequena)


from imagen import detectar_documento, ordenar_puntos

def test_detectar_documento_cuadrilatero_sintetico():
    img, esperadas = _documento_sintetico()
    pts = detectar_documento(img)
    assert pts is not None
    detectadas = ordenar_puntos(np.array(pts, dtype=np.float32))
    esperadas = ordenar_puntos(esperadas)
    diagonal = (img.shape[0] ** 2 + img.shape[1] ** 2) ** 0.5
    for d, e in zip(detectadas, esperadas):
        assert np.linalg.norm(d - e) < diagonal * 0.02, (d, e)

def test_detectar_documento_imagen_plana_devuelve_none():
    img = np.full((600, 800, 3), 128, dtype=np.uint8)
    assert detectar_documento(img) is None


from imagen import es_bilevel, cv_a_pil_pdf

def test_es_bilevel():
    bn = np.zeros((40, 60, 3), dtype=np.uint8)
    bn[10:20, 10:30] = 255
    assert es_bilevel(bn)
    color = bn.copy()
    color[0, 0] = (10, 20, 30)
    assert not es_bilevel(color)
    grises = cv2.cvtColor((np.random.rand(40, 60) * 255).astype(np.uint8),
                          cv2.COLOR_GRAY2BGR)
    assert not es_bilevel(grises)

def test_cv_a_pil_pdf_modo_1_para_bn_y_rgb_para_color():
    img = (np.random.rand(90, 120, 3) * 255).astype(np.uint8)
    bn = filtro_bn_escaner(img)
    assert cv_a_pil_pdf(bn).mode == "1"
    assert cv_a_pil_pdf(img).mode == "RGB"

def test_cv_a_pil_pdf_conserva_el_contenido():
    bn = np.zeros((40, 60, 3), dtype=np.uint8)
    bn[10:20, 10:30] = 255
    pil = cv_a_pil_pdf(bn)
    arr = np.array(pil.convert("L"))
    assert arr[15, 15] == 255 and arr[0, 0] == 0


from imagen import codificar_pagina, decodificar_pagina

def test_codificar_pagina_bn_es_pequena_y_sin_perdida():
    img = (np.random.rand(300, 400, 3) * 255).astype(np.uint8)
    bn = filtro_bn_escaner(img)
    datos = codificar_pagina(bn)
    assert len(datos) < bn.nbytes / 10
    assert np.array_equal(decodificar_pagina(datos), bn)

def test_codificar_pagina_color_recupera_aproximado():
    img = np.full((50, 80, 3), (200, 120, 40), dtype=np.uint8)
    out = decodificar_pagina(codificar_pagina(img))
    assert out.shape == img.shape
    assert np.abs(out.astype(int) - img.astype(int)).mean() < 3


from imagen import componer_dni, A4_ANCHO_200DPI, A4_ALTO_200DPI

def test_componer_dni_dos_caras_en_una_hoja():
    cara_a = np.full((300, 480, 3), (50, 60, 200), dtype=np.uint8)
    cara_b = np.full((300, 480, 3), (200, 60, 50), dtype=np.uint8)
    hoja = componer_dni(cara_a, cara_b)
    assert hoja.shape == (A4_ALTO_200DPI, A4_ANCHO_200DPI, 3)
    mitad = A4_ALTO_200DPI // 2
    arriba = hoja[:mitad]
    abajo = hoja[mitad:]
    # Cada mitad contiene el color de su cara y no el de la contraria
    assert np.all(arriba == (50, 60, 200), axis=2).any()
    assert not np.all(arriba == (200, 60, 50), axis=2).any()
    assert np.all(abajo == (200, 60, 50), axis=2).any()
    assert not np.all(abajo == (50, 60, 200), axis=2).any()

def test_componer_dni_no_deforma_la_proporcion():
    cara = np.zeros((300, 480, 3), dtype=np.uint8)   # negro puro, ratio 1.6
    hoja = componer_dni(cara, cara)
    ys, xs = np.where(hoja[:, :, 0] < 10)
    mitad = ys < A4_ALTO_200DPI // 2
    alto = ys[mitad].max() - ys[mitad].min() + 1
    ancho = xs[mitad].max() - xs[mitad].min() + 1
    assert abs((ancho / alto) - 1.6) < 0.05
