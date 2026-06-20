"""Flujo completo de la ventana (sin pantalla, QT_QPA_PLATFORM=offscreen):
cargar una foto, detectar, añadir páginas, unir DNI 2-en-1 y exportar PDF."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import cv2
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

_app = QApplication.instance() or QApplication([])

import escaner_fotos as ef


def _foto_documento():
    """Foto sintética: papel claro con líneas de texto sobre fondo oscuro."""
    img = np.full((1050, 1400, 3), 60, dtype=np.uint8)
    cv2.rectangle(img, (280, 160), (1150, 900), (235, 235, 235), -1)
    for y in range(300, 700, 60):
        cv2.line(img, (400, y), (1000, y), (30, 30, 30), 3)
    return img


def test_flujo_dni_dos_caras_en_una_pagina(tmp_path):
    v = ef.VentanaPrincipal()
    v._cargar_cv(_foto_documento())
    img = v.procesada_full()
    assert img is not None

    v.anadir_pagina_pdf(img)
    v.anadir_pagina_pdf(img)
    assert v.lista_pdf.count() == 2

    v.combinar_dni()
    assert v.lista_pdf.count() == 1

    datos = v.lista_pdf.item(0).data(Qt.ItemDataRole.UserRole)
    pil = ef.pagina_a_pil_pdf(datos)
    assert pil.size == (ef.componer_dni.__defaults__[0],
                        ef.componer_dni.__defaults__[1])
    ruta = tmp_path / "dni.pdf"
    pil.save(str(ruta), "PDF", resolution=200.0)
    assert ruta.stat().st_size > 0


def test_prefijo_en_nombre_de_archivo(tmp_path):
    v = ef.VentanaPrincipal()
    original = v.txt_prefijo.text()
    try:
        v.txt_prefijo.setText('Pérez: factura *marzo*')
        ruta = v._nombre_por_fecha(str(tmp_path), ".jpg")
        nombre = os.path.basename(ruta)
        assert nombre.startswith("Pérez factura marzo_")
        assert nombre.endswith(".jpg")
    finally:
        v.txt_prefijo.setText(original)


def test_encolar_no_pisa_la_imagen_cargada(tmp_path):
    v = ef.VentanaPrincipal()
    v._cargar_cv(_foto_documento())
    antes = v.imagen_original
    rutas = []
    for i in range(2):
        ruta = str(tmp_path / f"nueva_{i}.png")
        cv2.imwrite(ruta, _foto_documento())
        rutas.append(ruta)
    v._encolar(rutas)
    assert v.imagen_original is antes        # sigue la misma imagen en pantalla
    assert len(v.cola) == 2                  # y las nuevas esperan en la cola
    assert v.cola_total == 3


def test_quitar_imagen_vacia_la_foto_y_conserva_el_pdf():
    v = ef.VentanaPrincipal()
    v._cargar_cv(_foto_documento())
    assert v.imagen_original is not None
    assert v.btn_quitar.isEnabled()
    # Una página ya añadida al PDF NO debe perderse al quitar la foto.
    v.anadir_pagina_pdf(v.procesada_full())
    assert v.lista_pdf.count() == 1

    v.quitar_imagen()
    assert v.imagen_original is None          # la foto se vació
    assert v.procesada_full() is None         # no hay nada que procesar
    assert v.lista_pdf.count() == 1           # el PDF se conserva
    assert not v.btn_quitar.isEnabled()       # botón deshabilitado sin foto

    # Tras quitar, se puede cargar otra con normalidad (no queda 'bloqueada').
    v._cargar_cv(_foto_documento())
    assert v.imagen_original is not None
    assert v.btn_quitar.isEnabled()


def test_intensidad_visible_en_modos_bn_y_color():
    # isHidden() refleja el setVisible directamente (la ventana no se llega a
    # mostrar en el test offscreen, por eso no se usa isVisible()).
    v = ef.VentanaPrincipal()
    for idx in (0, 1, 2):                      # B/N nítido, B/N puro, Color limpio
        v.combo_filtro.setCurrentIndex(idx)
        assert not v.cont_intensidad.isHidden()
    v.combo_filtro.setCurrentIndex(3)          # Color original: sin intensidad
    assert v.cont_intensidad.isHidden()
