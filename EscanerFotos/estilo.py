"""Tema visual de EscanerFotos: paleta, hoja de estilos Qt (QSS) y recursos.

Criterios: superficies neutras oscuras, un único color de acento (azul) para
las acciones primarias y la selección, verde solo para el guardado rápido,
y los mismos estados (normal/hover/pulsado/foco/deshabilitado) en todos los
controles. El tema sirve a la tarea; no decora.
"""

import os
import sys

from PySide6.QtGui import QPalette, QColor

# ---- Paleta -------------------------------------------------------------

FONDO = "#1e2227"            # ventana
PANEL = "#262b31"            # grupos y paneles
CONTROL = "#2e343b"          # botones, inputs
CONTROL_HOVER = "#363d45"
CONTROL_PULSADO = "#2a3037"
BORDE = "#3a4149"
LIENZO = "#15181c"           # visores de imagen
TEXTO = "#e8eaed"
TEXTO_SUAVE = "#a5aeb7"
TEXTO_DESACTIVADO = "#6c757e"

ACENTO = "#3c83f6"           # acción primaria / selección / foco
ACENTO_HOVER = "#5b97f7"
ACENTO_PULSADO = "#2f6bd0"
EXITO = "#2f9e5b"            # guardado rápido
EXITO_HOVER = "#3bb46c"
EXITO_PULSADO = "#27854c"

# Colores para texto enriquecido (setText con HTML) coherentes con el tema
HTML_SUAVE = TEXTO_SUAVE
HTML_OK = "#5fc88a"


def ruta_recurso(nombre):
    """Ruta a un archivo de `recursos/`: junto a este .py en desarrollo,
    dentro del paquete de PyInstaller (_MEIPASS) en el ejecutable."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "recursos", nombre)


def _url(nombre):
    """url() de QSS (siempre con barras /, también en Windows)."""
    return ruta_recurso(nombre).replace("\\", "/")


QSS = f"""
QWidget {{
    color: {TEXTO};
    font-family: "Segoe UI", "Helvetica Neue", "Noto Sans", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog, QMessageBox, QProgressDialog, QFileDialog {{
    background: {FONDO};
}}

/* ---- Grupos ---- */
QGroupBox {{
    background: {PANEL};
    border: 1px solid {BORDE};
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px 10px 8px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {TEXTO_SUAVE};
    background: {FONDO};
}}
/* Grupo plegable cerrado: solo el título, sin caja vacía debajo */
QGroupBox[plegado="true"] {{
    padding: 0px 10px;
    background: transparent;
    border-color: {PANEL};
}}

/* ---- Botones ---- */
QPushButton {{
    background: {CONTROL};
    border: 1px solid {BORDE};
    border-radius: 6px;
    padding: 7px 12px;
}}
QPushButton:hover {{ background: {CONTROL_HOVER}; border-color: #485058; }}
QPushButton:pressed {{ background: {CONTROL_PULSADO}; }}
QPushButton:focus {{ border-color: {ACENTO}; }}
QPushButton:disabled {{ color: {TEXTO_DESACTIVADO}; background: {PANEL}; }}

QPushButton#btnPrimario {{
    background: {ACENTO};
    border: none;
    color: white;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#btnPrimario:hover {{ background: {ACENTO_HOVER}; }}
QPushButton#btnPrimario:pressed {{ background: {ACENTO_PULSADO}; }}

QPushButton#btnExito {{
    background: {EXITO};
    border: none;
    color: white;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#btnExito:hover {{ background: {EXITO_HOVER}; }}
QPushButton#btnExito:pressed {{ background: {EXITO_PULSADO}; }}

/* ---- Entradas ---- */
QComboBox, QLineEdit {{
    background: {CONTROL};
    border: 1px solid {BORDE};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACENTO};
}}
QComboBox:hover, QLineEdit:hover {{ border-color: #485058; }}
QComboBox:focus, QLineEdit:focus {{ border-color: {ACENTO}; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDE};
    selection-background-color: {ACENTO};
    outline: none;
}}

/* ---- Casillas (también las de los grupos plegables) ---- */
QCheckBox {{ spacing: 7px; background: transparent; }}
QCheckBox::indicator, QGroupBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid #4a525b;
    background: {CONTROL};
}}
QCheckBox::indicator:hover, QGroupBox::indicator:hover {{
    border-color: {ACENTO};
}}
QCheckBox::indicator:checked, QGroupBox::indicator:checked {{
    background: {ACENTO};
    border-color: {ACENTO};
    image: url("{_url('check.png')}");
}}

/* ---- Deslizadores ---- */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDE};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {ACENTO}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {TEXTO};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: white; }}

/* ---- Lista de páginas del PDF ---- */
QListWidget {{
    background: {LIENZO};
    border: 1px solid {BORDE};
    border-radius: 6px;
    padding: 4px;
}}
QListWidget::item {{ border-radius: 6px; }}
QListWidget::item:selected {{ background: {ACENTO}; }}

/* ---- Barras de scroll ---- */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: #3f4750;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #4d5660; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: #3f4750;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: #4d5660; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- Barra de progreso ---- */
QProgressBar {{
    background: {CONTROL};
    border: 1px solid {BORDE};
    border-radius: 6px;
    text-align: center;
    color: {TEXTO};
}}
QProgressBar::chunk {{ background: {ACENTO}; border-radius: 5px; }}

/* ---- Barra de estado y tooltips ---- */
QStatusBar {{ background: #181c20; color: {TEXTO_SUAVE}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{
    background: {PANEL};
    color: {TEXTO};
    border: 1px solid {BORDE};
    padding: 4px 6px;
}}

/* ---- Elementos con nombre ---- */
QLabel {{ background: transparent; }}
QLabel#lienzo {{
    background: {LIENZO};
    border: 1px solid {BORDE};
    border-radius: 8px;
}}
QLabel#tituloLienzo {{
    color: {TEXTO_SUAVE};
    font-size: 14px;
    font-weight: 600;
    padding: 2px 0;
}}
QLabel#infoSuave {{ color: {TEXTO_SUAVE}; font-size: 11px; }}
QLabel#indicadorCola {{
    background: #1d3a2a;
    color: #7fe0a7;
    padding: 6px 8px;
    border-radius: 6px;
    font-weight: 600;
}}
"""


def aplicar_tema(app):
    """Aplica estilo Fusion, paleta oscura y la hoja de estilos a la app.
    La paleta cubre lo que el QSS no alcanza (menús nativos, diálogos)."""
    app.setStyle("Fusion")
    p = app.palette()
    rol = QPalette.ColorRole
    p.setColor(rol.Window, QColor(FONDO))
    p.setColor(rol.WindowText, QColor(TEXTO))
    p.setColor(rol.Base, QColor(CONTROL))
    p.setColor(rol.AlternateBase, QColor(PANEL))
    p.setColor(rol.Text, QColor(TEXTO))
    p.setColor(rol.Button, QColor(CONTROL))
    p.setColor(rol.ButtonText, QColor(TEXTO))
    p.setColor(rol.ToolTipBase, QColor(PANEL))
    p.setColor(rol.ToolTipText, QColor(TEXTO))
    p.setColor(rol.Highlight, QColor(ACENTO))
    p.setColor(rol.HighlightedText, QColor("#ffffff"))
    p.setColor(rol.PlaceholderText, QColor(TEXTO_SUAVE))
    p.setColor(rol.Link, QColor(ACENTO))
    grupo = QPalette.ColorGroup.Disabled
    p.setColor(grupo, rol.Text, QColor(TEXTO_DESACTIVADO))
    p.setColor(grupo, rol.ButtonText, QColor(TEXTO_DESACTIVADO))
    p.setColor(grupo, rol.WindowText, QColor(TEXTO_DESACTIVADO))
    app.setPalette(p)
    app.setStyleSheet(QSS)
