"""Verifica la conversión de imágenes del portapapeles (QImage -> OpenCV BGR).
El bug original: una captura (ARGB32) reventaba la conversión en Windows."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage

_app = QApplication.instance() or QApplication([])

import escaner_fotos as ef


def test_qimage_argb32_se_convierte_con_color_correcto():
    v = ef.VentanaPrincipal()
    # Imita una captura de pantalla: formato con transparencia.
    qi = QImage(8, 6, QImage.Format.Format_ARGB32)
    qi.fill(0xFF2266AA)  # ARGB -> R=0x22, G=0x66, B=0xAA
    out = v._qimage_a_cv(qi)
    assert out is not None, "la conversión devolvió None"
    assert out.shape == (6, 8, 3)
    b, g, r = (int(x) for x in out[0, 0])
    assert (r, g, b) == (0x22, 0x66, 0xAA), (r, g, b)


def test_qimage_nulo_devuelve_none():
    v = ef.VentanaPrincipal()
    assert v._qimage_a_cv(QImage()) is None
