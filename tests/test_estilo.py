"""El tema y los recursos (icono, marca de verificación) están completos."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

_app = QApplication.instance() or QApplication([])

import estilo


def test_los_recursos_existen():
    for nombre in ("icono.ico", "icono.png", "check.png"):
        assert os.path.isfile(estilo.ruta_recurso(nombre)), nombre


def test_el_icono_carga():
    icono = QIcon(estilo.ruta_recurso("icono.ico"))
    assert not icono.isNull()
    assert icono.availableSizes(), "el .ico no trae tamaños incrustados"


def test_aplicar_tema_no_falla_y_define_qss():
    estilo.aplicar_tema(_app)
    assert _app.styleSheet() == estilo.QSS
    assert "QPushButton#btnPrimario" in estilo.QSS
    assert "QGroupBox" in estilo.QSS
