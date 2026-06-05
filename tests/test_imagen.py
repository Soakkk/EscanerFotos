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
