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
