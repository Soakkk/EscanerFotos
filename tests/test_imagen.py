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
