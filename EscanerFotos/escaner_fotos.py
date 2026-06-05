"""
Escáner de Fotos — Navaja suiza para digitalizar documentos
============================================================
Aplicación de escritorio para convertir fotos de documentos
(facturas, contratos, DNI) hechas con el móvil en imágenes
tipo escáner: enderezadas, recortadas y con el texto legible.

Sin IA. Basado en OpenCV.

v2.0 — Novedades:
  • Arrastra y suelta imágenes directamente sobre la ventana
  • Clic derecho / Escape para deshacer puntos en modo manual
  • Atajos de teclado: Ctrl+O, Ctrl+S, Ctrl+Shift+S, Ctrl+E, F5
  • Barra de estado con dimensiones de imagen en tiempo real
  • Exportar como PNG (sin pérdida de calidad)
  • PDF multipágina: acumula varias páginas y expórtalas juntas
  • Procesado por lotes de carpetas completas
"""

import sys
import os
from datetime import datetime
import cv2
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QFileDialog, QSlider, QComboBox,
    QMessageBox, QGroupBox, QSizePolicy, QProgressDialog, QScrollArea,
    QListWidget, QListWidgetItem
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QMouseEvent,
    QKeySequence, QShortcut, QIcon
)
from PySide6.QtCore import Qt, Signal, QSettings, QTimer, QSize
from PySide6.QtCore import QLockFile, QStandardPaths
from version import __version__
import actualizador
from imagen import (
    detectar_documento, corregir_perspectiva, ordenar_puntos,
    filtro_bn_escaner, filtro_color_mejorado, aplicar_ajustes,
    rotar_imagen, aplicar_pipeline, leer_imagen, cv_a_pil, procesar_lote,
    buffer_rgb_a_cv,
)
from cola import siguiente_de_cola, texto_cola


# =============================================================
# =================   COMPONENTES DE INTERFAZ   ===============
# =============================================================

class LienzoImagen(QLabel):
    """
    Visualizador de imágenes con soporte para:
    - Mostrar imagen OpenCV (BGR) escalada al tamaño del widget.
    - Arrastrar y soltar archivos de imagen.
    - Selección manual de 4 puntos (clic izquierdo).
    - Deshacer último punto (clic derecho).
    - Cancelar modo selección (método público).
    """
    puntos_listos = Signal(list)
    imagen_soltada = Signal(str)   # ruta del archivo soltado
    puntos_editados = Signal(list)   # 4 puntos tras arrastrar una esquina
    imagenes_soltadas = Signal(list)   # varias rutas soltadas a la vez

    def __init__(self):
        super().__init__()
        self.setMinimumSize(450, 500)
        self.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #444; border-radius: 4px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)

        self.imagen_cv = None
        self.modo_seleccion = False
        self.puntos = []
        self.modo_editar = False
        self._idx_arrastrado = None
        self.factor_escala = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self._w_pix = 0
        self._h_pix = 0

    # --- Drag & drop ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                ext = os.path.splitext(urls[0].toLocalFile())[1].lower()
                if ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp')
        rutas = [u.toLocalFile() for u in event.mimeData().urls()
                 if u.isLocalFile() and u.toLocalFile().lower().endswith(exts)]
        if rutas:
            self.imagenes_soltadas.emit(rutas)

    # --- Visualización ---

    def mostrar_imagen(self, imagen_cv):
        self.imagen_cv = imagen_cv
        self.actualizar_visualizacion()

    def limpiar_puntos(self):
        self.puntos = []
        self.actualizar_visualizacion()

    def mostrar_esquinas(self, puntos):
        """Muestra 4 vértices (coords de imagen) que se pueden arrastrar."""
        self.puntos = [list(p) for p in puntos]
        self.modo_editar = True
        self.modo_seleccion = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.actualizar_visualizacion()

    def _esquina_cercana(self, x_pix, y_pix):
        """Índice del vértice cuya posición en pantalla está a <=18 px del clic, o None."""
        mejor, mejor_d = None, 18.0
        for i, p in enumerate(self.puntos):
            px = p[0] * self.factor_escala + self.offset_x
            py = p[1] * self.factor_escala + self.offset_y
            d = ((px - x_pix) ** 2 + (py - y_pix) ** 2) ** 0.5
            if d <= mejor_d:
                mejor, mejor_d = i, d
        return mejor

    def actualizar_visualizacion(self):
        if self.imagen_cv is None:
            self.clear()
            self.setText(
                "<span style='color:#555; font-size:14px'>"
                "Arrastra una imagen aquí<br>o usa Ctrl+O para abrirla"
                "</span>"
            )
            return

        img_rgb = cv2.cvtColor(self.imagen_cv, cv2.COLOR_BGR2RGB)
        h, w = img_rgb.shape[:2]
        qimg = QImage(
            img_rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888
        ).copy()
        pixmap = QPixmap.fromImage(qimg)

        pixmap_esc = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._w_pix = pixmap_esc.width()
        self._h_pix = pixmap_esc.height()
        self.factor_escala = self._w_pix / w if w > 0 else 1.0
        self.offset_x = (self.width() - self._w_pix) / 2
        self.offset_y = (self.height() - self._h_pix) / 2

        if self.puntos:
            painter = QPainter(pixmap_esc)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if len(self.puntos) >= 2:
                pen_linea = QPen(QColor(50, 200, 80), 2)
                painter.setPen(pen_linea)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                n = len(self.puntos)
                for i in range(n - 1):
                    x1 = self.puntos[i][0] * self.factor_escala
                    y1 = self.puntos[i][1] * self.factor_escala
                    x2 = self.puntos[i + 1][0] * self.factor_escala
                    y2 = self.puntos[i + 1][1] * self.factor_escala
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                if n == 4:
                    x1 = self.puntos[3][0] * self.factor_escala
                    y1 = self.puntos[3][1] * self.factor_escala
                    x2 = self.puntos[0][0] * self.factor_escala
                    y2 = self.puntos[0][1] * self.factor_escala
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            pen_punto = QPen(QColor(255, 60, 60), 2)
            painter.setPen(pen_punto)
            painter.setBrush(QColor(255, 60, 60))
            for idx, p in enumerate(self.puntos):
                x = p[0] * self.factor_escala
                y = p[1] * self.factor_escala
                painter.drawEllipse(int(x - 7), int(y - 7), 14, 14)
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.drawText(int(x - 4), int(y + 5), str(idx + 1))
                painter.setPen(pen_punto)

            painter.end()

        # Indicador de modo selección
        if self.modo_seleccion:
            painter2 = QPainter(pixmap_esc)
            painter2.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter2.fillRect(0, 0, pixmap_esc.width(), 28, QColor(0, 0, 0, 160))
            painter2.setPen(QColor(255, 220, 50))
            restantes = 4 - len(self.puntos)
            painter2.drawText(
                8, 19,
                f"Clic en esquina {len(self.puntos) + 1}/4  "
                f"({restantes} restante{'s' if restantes != 1 else ''})  "
                f"— Clic derecho o Ctrl+Z para deshacer  — Escape para cancelar"
            )
            painter2.end()

        self.setPixmap(pixmap_esc)

    def resizeEvent(self, event):
        self.actualizar_visualizacion()
        super().resizeEvent(event)

    # --- Selección manual ---

    def iniciar_seleccion_manual(self):
        self.modo_seleccion = True
        self.puntos = []
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.actualizar_visualizacion()

    def deshacer_ultimo_punto(self):
        if self.puntos and self.modo_seleccion:
            self.puntos.pop()
            self.actualizar_visualizacion()

    def cancelar_seleccion(self):
        if self.modo_seleccion:
            self.modo_seleccion = False
            self.puntos = []
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.actualizar_visualizacion()

    def mousePressEvent(self, event: QMouseEvent):
        if self.modo_editar and len(self.puntos) == 4 and self.imagen_cv is not None:
            idx = self._esquina_cercana(event.position().x(), event.position().y())
            if idx is not None:
                self._idx_arrastrado = idx
                return

        if not self.modo_seleccion or self.imagen_cv is None:
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.deshacer_ultimo_punto()
            return

        cx = event.position().x() - self.offset_x
        cy = event.position().y() - self.offset_y

        if cx < 0 or cy < 0 or cx > self._w_pix or cy > self._h_pix:
            return

        x_orig = cx / self.factor_escala
        y_orig = cy / self.factor_escala
        self.puntos.append([x_orig, y_orig])
        self.actualizar_visualizacion()

        if len(self.puntos) == 4:
            self.modo_seleccion = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.puntos_listos.emit(list(self.puntos))

    def mouseMoveEvent(self, event):
        if self._idx_arrastrado is None:
            return
        cx = (event.position().x() - self.offset_x) / self.factor_escala
        cy = (event.position().y() - self.offset_y) / self.factor_escala
        h, w = self.imagen_cv.shape[:2]
        cx = max(0, min(w - 1, cx))
        cy = max(0, min(h - 1, cy))
        self.puntos[self._idx_arrastrado] = [cx, cy]
        self.actualizar_visualizacion()

    def mouseReleaseEvent(self, event):
        if self._idx_arrastrado is not None:
            self._idx_arrastrado = None
            self.puntos_editados.emit([list(p) for p in self.puntos])


# =============================================================
# ===================   VENTANA PRINCIPAL   ===================
# =============================================================

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Escáner de Fotos v{__version__} — Documentos limpios desde el móvil")
        self.resize(1500, 900)
        self.setAcceptDrops(True)

        self.imagen_original = None
        self.imagen_enderezada = None
        self._preview_base = None    # versión reducida para vista previa fluida
        self._ruta_origen = ""       # carpeta del último archivo abierto

        self.cola = []
        self.cola_total = 0
        self.cola_pos = 0

        # Preferencias persistentes entre sesiones
        self.settings = QSettings("EscanerFotos", "EscanerFotos")
        self.carpeta_salida = self.settings.value("carpeta_salida", "", str)

        # Debounce de los sliders para que la vista previa no dé tirones
        self._timer_preview = QTimer(self)
        self._timer_preview.setSingleShot(True)
        self._timer_preview.setInterval(60)
        self._timer_preview.timeout.connect(self.actualizar_procesado)

        self._crear_interfaz()
        self._crear_atajos()
        self._restaurar_preferencias()
        self._actualizar_barra_estado()

    def _restaurar_preferencias(self):
        """Aplica las preferencias guardadas a la interfaz ya construida."""
        idx = self.settings.value("filtro_idx", 0, int)
        if 0 <= idx < self.combo_filtro.count():
            self.combo_filtro.blockSignals(True)
            self.combo_filtro.setCurrentIndex(idx)
            self.combo_filtro.blockSignals(False)
        self._actualizar_label_carpeta()

    # ----------------------------------------------------------
    # Atajos de teclado
    # ----------------------------------------------------------

    def _crear_atajos(self):
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.abrir_imagen)
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.guardado_rapido)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self.guardado_rapido)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self.guardado_rapido)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=lambda: self.guardar("jpg"))
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=lambda: self.guardar("pdf"))
        QShortcut(QKeySequence("Ctrl+E"), self, activated=lambda: self.guardar("png"))
        QShortcut(QKeySequence("F5"), self, activated=self.detectar_auto)
        QShortcut(QKeySequence("Escape"), self, activated=self.lienzo_original.cancelar_seleccion)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.lienzo_original.deshacer_ultimo_punto)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.reset_ajustes)
        QShortcut(QKeySequence("Ctrl+V"), self, activated=self.pegar_imagen)

    # ----------------------------------------------------------
    # Barra de estado
    # ----------------------------------------------------------

    def _actualizar_barra_estado(self):
        if self.imagen_original is None:
            self.statusBar().showMessage(
                "Arrastra una imagen aquí, usa Ctrl+O para abrir  |  "
                "Ctrl+S: JPG  Ctrl+Shift+S: PDF  Ctrl+E: PNG  F5: Detectar"
            )
            return
        h, w = self.imagen_original.shape[:2]
        partes = [f"Original: {w}×{h} px"]
        base = self._base_full()
        if base is not None:
            hp, wp = base.shape[:2]
            partes.append(f"Resultado: {wp}×{hp} px")
        if hasattr(self, "lista_pdf") and self.lista_pdf.count():
            partes.append(f"PDF: {self.lista_pdf.count()} pág.")
        partes.append("Enter: Guardado rápido  |  Ctrl+S: JPG  Ctrl+Shift+S: PDF")
        self.statusBar().showMessage("   |   ".join(partes))

    # ----------------------------------------------------------
    # Drag & drop sobre la ventana principal
    # ----------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                ext = os.path.splitext(urls[0].toLocalFile())[1].lower()
                if ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _rutas_imagen_de(self, mime):
        exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp')
        return [u.toLocalFile() for u in mime.urls()
                if u.isLocalFile() and u.toLocalFile().lower().endswith(exts)] \
            if mime.hasUrls() else []

    def dropEvent(self, event):
        rutas = self._rutas_imagen_de(event.mimeData())
        if rutas:
            self._iniciar_cola(rutas)

    # ----------------------------------------------------------
    # Construcción de la interfaz
    # ----------------------------------------------------------

    def _grupo_plegable(self, titulo, contenido, abierto=False):
        """QGroupBox 'checkable' cuyo contenido se oculta al desmarcar (plegar)."""
        g = QGroupBox(titulo)
        g.setCheckable(True)
        g.setChecked(abierto)
        lay = QVBoxLayout(g)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.addWidget(contenido)
        contenido.setVisible(abierto)
        g.toggled.connect(contenido.setVisible)
        return g

    def _iniciar_cola(self, rutas):
        rutas = list(rutas)
        if not rutas:
            return
        self.cola_total = len(rutas)
        self.cola_pos = 1
        self.cola = rutas[1:]
        self._cargar_archivo(rutas[0])
        self._actualizar_indicador_cola()

    def _cargar_siguiente_de_cola(self):
        siguiente, resto = siguiente_de_cola(self.cola)
        self.cola = resto
        if siguiente is None:
            n = self.lista_pdf.count()
            self.cola_total = 0
            self.cola_pos = 0
            self._actualizar_indicador_cola()
            msg = f"Has terminado la tanda.\n{n} página{'s' if n != 1 else ''} en el PDF."
            QTimer.singleShot(0, lambda: QMessageBox.information(self, "Cola terminada", msg))
            return
        self.cola_pos += 1
        self._cargar_archivo(siguiente)
        self._actualizar_indicador_cola()

    def terminar_y_siguiente(self):
        if self.procesada_full() is None:
            QMessageBox.warning(self, "Atención", "Procesa una imagen primero.")
            return
        self.anadir_pagina_pdf()
        if self.cola_total:
            self._cargar_siguiente_de_cola()

    def _actualizar_indicador_cola(self):
        self.lbl_cola.setText(texto_cola(self.cola_pos, self.cola_total))
        self.lbl_cola.setVisible(bool(self.lbl_cola.text()))

    def _crear_interfaz(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Columna izquierda: original
        col_izq = QVBoxLayout()
        lbl_orig = QLabel("<b>📷 Foto original</b>")
        lbl_orig.setStyleSheet("font-size: 14px; padding: 4px;")
        col_izq.addWidget(lbl_orig)
        self.lienzo_original = LienzoImagen()
        self.lienzo_original.puntos_listos.connect(self._al_recibir_puntos_manuales)
        self.lienzo_original.puntos_editados.connect(self._al_recibir_puntos_manuales)
        self.lienzo_original.imagen_soltada.connect(self._cargar_archivo)
        self.lienzo_original.imagenes_soltadas.connect(self._iniciar_cola)
        col_izq.addWidget(self.lienzo_original)
        w_izq = QWidget()
        w_izq.setLayout(col_izq)

        # Columna central: controles (con scroll para que no se solapen en pantalla completa)
        w_ctrl = self._construir_panel_controles()
        scroll_ctrl = QScrollArea()
        scroll_ctrl.setWidgetResizable(True)
        scroll_ctrl.setWidget(w_ctrl)
        scroll_ctrl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_ctrl.setMinimumWidth(330)
        scroll_ctrl.setMaximumWidth(370)
        scroll_ctrl.setFrameShape(QScrollArea.Shape.NoFrame)

        # Columna derecha: resultado
        col_der = QVBoxLayout()
        lbl_res = QLabel("<b>✨ Resultado</b>")
        lbl_res.setStyleSheet("font-size: 14px; padding: 4px;")
        col_der.addWidget(lbl_res)
        self.lienzo_resultado = LienzoImagen()
        col_der.addWidget(self.lienzo_resultado)
        w_der = QWidget()
        w_der.setLayout(col_der)

        layout.addWidget(w_izq, 4)
        layout.addWidget(scroll_ctrl, 0)
        layout.addWidget(w_der, 4)

    def _construir_panel_controles(self):
        panel = QVBoxLayout()
        panel.setSpacing(6)

        # === 1. Cargar ===
        g1 = QGroupBox("1️⃣  Cargar foto")
        l1 = QVBoxLayout(g1)
        btn_abrir = QPushButton("📂  Abrir imagen…  (Ctrl+O)")
        btn_abrir.setMinimumHeight(38)
        btn_abrir.clicked.connect(self.abrir_imagen)
        l1.addWidget(btn_abrir)
        btn_lote = QPushButton("📁  Procesar carpeta por lotes…")
        btn_lote.clicked.connect(self.procesar_carpeta)
        l1.addWidget(btn_lote)
        panel.addWidget(g1)

        self.lbl_cola = QLabel("")
        self.lbl_cola.setStyleSheet(
            "background:#243; color:#9f9; padding:5px; border-radius:4px; font-weight:bold;")
        self.lbl_cola.setVisible(False)
        panel.addWidget(self.lbl_cola)

        # === 2. Rotar ===
        cont_rot = QWidget()
        l_rot = QHBoxLayout(cont_rot)
        l_rot.setContentsMargins(0, 0, 0, 0)
        btn_rot_izq = QPushButton("⟲ 90° izq")
        btn_rot_der = QPushButton("⟳ 90° der")
        btn_rot_180 = QPushButton("⤢ 180°")
        btn_rot_izq.clicked.connect(lambda: self.rotar_original(270))
        btn_rot_der.clicked.connect(lambda: self.rotar_original(90))
        btn_rot_180.clicked.connect(lambda: self.rotar_original(180))
        l_rot.addWidget(btn_rot_izq); l_rot.addWidget(btn_rot_der); l_rot.addWidget(btn_rot_180)
        panel.addWidget(self._grupo_plegable("🔄  Rotar", cont_rot, abierto=False))

        # === 3. Recortar y enderezar ===
        g2 = QGroupBox("2️⃣  Recortar y enderezar")
        l2 = QVBoxLayout(g2)
        btn_auto = QPushButton("🔍  Detectar automáticamente  (F5)")
        btn_auto.setMinimumHeight(38)
        btn_auto.clicked.connect(self.detectar_auto)
        l2.addWidget(btn_auto)
        btn_man = QPushButton("✏️  Marcar 4 esquinas a mano")
        btn_man.setMinimumHeight(38)
        btn_man.clicked.connect(self.iniciar_manual)
        l2.addWidget(btn_man)
        btn_sin_recortar = QPushButton("↺  Usar sin recortar")
        btn_sin_recortar.clicked.connect(self.usar_sin_recortar)
        l2.addWidget(btn_sin_recortar)
        self.lbl_estado_recorte = QLabel("<i style='color:#888'>Sin recortar</i>")
        l2.addWidget(self.lbl_estado_recorte)
        panel.addWidget(g2)

        # === 4. Filtro ===
        g3 = QGroupBox("3️⃣  Tipo de salida")
        l3 = QVBoxLayout(g3)
        self.combo_filtro = QComboBox()
        self.combo_filtro.addItems([
            "⚪ Blanco y negro (escáner)  — facturas, contratos",
            "🎨 Color con luz corregida  — DNI, fotos",
            "📷 Color original",
        ])
        self.combo_filtro.setMinimumHeight(34)
        self.combo_filtro.currentIndexChanged.connect(self._al_cambiar_filtro)
        l3.addWidget(self.combo_filtro)
        self.sld_intensidad_bn, fila_int_bn = self._crear_slider("Intensidad B/N", 0, 100, 50)
        l3.addLayout(fila_int_bn)
        panel.addWidget(g3)

        # === 5. Ajustes finos ===
        cont_aj = QWidget()
        l4 = QVBoxLayout(cont_aj)
        l4.setContentsMargins(0, 0, 0, 0)
        self.sld_brillo,    fila1 = self._crear_slider("Brillo",    -100, 100, 0)
        self.sld_contraste, fila2 = self._crear_slider("Contraste", -100, 100, 0)
        self.sld_nitidez,   fila3 = self._crear_slider("Nitidez",      0, 100, 0)
        l4.addLayout(fila1); l4.addLayout(fila2); l4.addLayout(fila3)
        btn_reset = QPushButton("↺  Resetear ajustes  (Ctrl+R)")
        btn_reset.clicked.connect(self.reset_ajustes)
        l4.addWidget(btn_reset)
        panel.addWidget(self._grupo_plegable("🎚️  Ajustes finos", cont_aj, abierto=False))

        self.btn_terminar = QPushButton("✓  Añadir al PDF y siguiente  →")
        self.btn_terminar.setMinimumHeight(46)
        self.btn_terminar.setStyleSheet(
            "QPushButton { background-color:#1565c0; color:white; font-size:14px;"
            " font-weight:bold; border-radius:5px; }"
            "QPushButton:hover { background-color:#1976d2; }")
        self.btn_terminar.clicked.connect(self.terminar_y_siguiente)
        panel.addWidget(self.btn_terminar)

        # === 6. Guardar ===
        g5 = QGroupBox("5️⃣  Guardar resultado")
        l5 = QVBoxLayout(g5)

        # Guardado rápido: destino fijo + nombre por fecha-hora, sin diálogos
        btn_rapido = QPushButton("⚡  Guardado rápido  (Enter)")
        btn_rapido.setMinimumHeight(44)
        btn_rapido.setStyleSheet(
            "QPushButton { background-color: #2e7d32; color: white;"
            " font-size: 14px; font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #388e3c; }"
        )
        btn_rapido.clicked.connect(self.guardado_rapido)
        l5.addWidget(btn_rapido)

        fila_carpeta = QHBoxLayout()
        self.lbl_carpeta_salida = QLabel()
        self.lbl_carpeta_salida.setStyleSheet("color:#888; font-size:11px;")
        self.lbl_carpeta_salida.setWordWrap(True)
        fila_carpeta.addWidget(self.lbl_carpeta_salida, 1)
        btn_cambiar_carpeta = QPushButton("📁 Cambiar")
        btn_cambiar_carpeta.setMaximumWidth(90)
        btn_cambiar_carpeta.clicked.connect(self.elegir_carpeta_salida)
        fila_carpeta.addWidget(btn_cambiar_carpeta)
        l5.addLayout(fila_carpeta)

        btn_jpg = QPushButton("💾  Guardar como… JPG  (Ctrl+S)")
        btn_jpg.setMinimumHeight(36)
        btn_jpg.clicked.connect(lambda: self.guardar("jpg"))
        l5.addWidget(btn_jpg)
        btn_png = QPushButton("🖼️  Guardar como PNG  (Ctrl+E)")
        btn_png.setMinimumHeight(36)
        btn_png.clicked.connect(lambda: self.guardar("png"))
        l5.addWidget(btn_png)
        btn_pdf = QPushButton("📄  Guardar como PDF  (Ctrl+Shift+S)")
        btn_pdf.setMinimumHeight(36)
        btn_pdf.clicked.connect(lambda: self.guardar("pdf"))
        l5.addWidget(btn_pdf)
        panel.addWidget(g5)

        # === PDF de varias fotos (miniaturas reordenables) ===
        g6 = QGroupBox("📑  PDF de varias fotos (arrastra para ordenar)")
        l6 = QVBoxLayout(g6)
        self.lista_pdf = QListWidget()
        self.lista_pdf.setViewMode(QListWidget.ViewMode.IconMode)
        self.lista_pdf.setIconSize(QSize(80, 104))
        self.lista_pdf.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.lista_pdf.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.lista_pdf.setMinimumHeight(130)
        l6.addWidget(self.lista_pdf)
        fila_pdf = QHBoxLayout()
        btn_add_pdf = QPushButton("➕ Añadir")
        btn_add_pdf.clicked.connect(self.anadir_pagina_pdf)
        btn_quitar_pdf = QPushButton("🗑️ Quitar")
        btn_quitar_pdf.clicked.connect(self.quitar_pagina_pdf)
        btn_vaciar_pdf = QPushButton("Vaciar")
        btn_vaciar_pdf.clicked.connect(self.vaciar_paginas_pdf)
        fila_pdf.addWidget(btn_add_pdf)
        fila_pdf.addWidget(btn_quitar_pdf)
        fila_pdf.addWidget(btn_vaciar_pdf)
        l6.addLayout(fila_pdf)
        btn_exp_pdf = QPushButton("📄  Exportar PDF")
        btn_exp_pdf.setMinimumHeight(36)
        btn_exp_pdf.clicked.connect(self.exportar_pdf_multipagina)
        l6.addWidget(btn_exp_pdf)
        panel.addWidget(g6)

        panel.addStretch()

        w = QWidget()
        w.setLayout(panel)
        w.setMinimumWidth(300)
        return w

    def _crear_slider(self, nombre, mn, mx, val):
        fila = QHBoxLayout()
        lbl = QLabel(f"{nombre}:")
        lbl.setMinimumWidth(75)
        sld = QSlider(Qt.Orientation.Horizontal)
        sld.setRange(mn, mx)
        sld.setValue(val)
        lbl_val = QLabel(str(val))
        lbl_val.setMinimumWidth(35)
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        sld.valueChanged.connect(lambda v: lbl_val.setText(str(v)))
        sld.valueChanged.connect(self._programar_actualizacion)
        fila.addWidget(lbl)
        fila.addWidget(sld)
        fila.addWidget(lbl_val)
        return sld, fila

    # ----------------------------------------------------------
    # Acciones
    # ----------------------------------------------------------

    def abrir_imagen(self):
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Abrir imágenes", self._ruta_origen,
            "Imágenes (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp);;"
            "Todos los archivos (*.*)")
        if rutas:
            self._iniciar_cola(rutas)

    def _cargar_archivo(self, ruta):
        try:
            img = leer_imagen(ruta)
            if img is None:
                raise ValueError("OpenCV no pudo leer el archivo.")
            self._cargar_cv(img, os.path.dirname(ruta))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la imagen:\n{e}")

    def _cargar_cv(self, img, ruta_origen=""):
        self.imagen_original = img
        self.imagen_enderezada = None
        self._ruta_origen = ruta_origen or self._ruta_origen
        self.lienzo_original.limpiar_puntos()
        self.lienzo_original.mostrar_imagen(img)
        self.lbl_estado_recorte.setText("<i style='color:#888'>Sin recortar</i>")
        self._resetear_sliders()
        self._actualizar_preview_base()
        self.detectar_auto(silencioso=True)
        self.actualizar_procesado()
        self._actualizar_barra_estado()

    def _qimage_a_cv(self, qimg):
        if qimg.isNull():
            return None
        qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
        b = bytes(qimg.constBits())
        return buffer_rgb_a_cv(b, qimg.width(), qimg.height(), qimg.bytesPerLine())

    def pegar_imagen(self):
        cb = QApplication.clipboard()
        md = cb.mimeData()
        if md.hasImage():
            img = self._qimage_a_cv(cb.image())
            if img is not None and img.size:
                self._cargar_cv(img)
                self.statusBar().showMessage("Imagen pegada del portapapeles", 4000)
                return
        if md.hasUrls():
            exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp')
            for url in md.urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(exts):
                    self._cargar_archivo(url.toLocalFile())
                    return
        self.statusBar().showMessage("El portapapeles no contiene una imagen", 4000)

    def rotar_original(self, grados):
        if self.imagen_original is None:
            return
        self.imagen_original = rotar_imagen(self.imagen_original, grados)
        self.imagen_enderezada = None
        self.lienzo_original.limpiar_puntos()
        self.lienzo_original.mostrar_imagen(self.imagen_original)
        self.lbl_estado_recorte.setText("<i style='color:#888'>Sin recortar</i>")
        self._actualizar_preview_base()
        self.actualizar_procesado()
        self._actualizar_barra_estado()

    def detectar_auto(self, silencioso=False):
        if self.imagen_original is None:
            if not silencioso:
                QMessageBox.warning(self, "Atención", "Primero abre una imagen.")
            return
        puntos = detectar_documento(self.imagen_original)
        if puntos is None:
            if not silencioso:
                QMessageBox.information(
                    self, "Sin detección",
                    "No se ha podido detectar el documento automáticamente.\n\n"
                    "Opciones:\n"
                    "  • Marca las 4 esquinas a mano.\n"
                    "  • Usa «Sin recortar» si el papel ya ocupa toda la foto."
                )
            return
        self.lienzo_original.mostrar_esquinas(puntos.tolist())
        self.imagen_enderezada = corregir_perspectiva(self.imagen_original, puntos)
        self.lbl_estado_recorte.setText(
            "<span style='color:#3a3'>Recorte automático ✓</span>"
        )
        self._actualizar_preview_base()
        self.actualizar_procesado()

    def iniciar_manual(self):
        if self.imagen_original is None:
            QMessageBox.warning(self, "Atención", "Primero abre una imagen.")
            return
        self.lienzo_original.iniciar_seleccion_manual()
        self.lbl_estado_recorte.setText(
            "<i>Haz clic en las 4 esquinas del documento…</i>"
        )

    def _al_recibir_puntos_manuales(self, puntos):
        puntos_np = np.array(puntos, dtype=np.float32)
        self.imagen_enderezada = corregir_perspectiva(
            self.imagen_original, puntos_np
        )
        self.lbl_estado_recorte.setText(
            "<span style='color:#3a3'>Recorte manual ✓</span>"
        )
        self._actualizar_preview_base()
        self.actualizar_procesado()

    def usar_sin_recortar(self):
        if self.imagen_original is None:
            return
        self.imagen_enderezada = None
        self.lienzo_original.limpiar_puntos()
        self.lbl_estado_recorte.setText(
            "<span style='color:#888'><i>Sin recortar</i></span>"
        )
        self._actualizar_preview_base()
        self.actualizar_procesado()

    # --- Procesado: vista previa (rápida) vs. resolución completa ---

    def _base_full(self):
        """Imagen base a resolución completa (enderezada si la hay)."""
        if self.imagen_enderezada is not None:
            return self.imagen_enderezada
        return self.imagen_original

    def _params(self):
        """Parámetros actuales de filtro y ajustes finos."""
        return (
            self.combo_filtro.currentIndex(),
            self.sld_brillo.value(),
            self.sld_contraste.value(),
            self.sld_nitidez.value(),
            self.sld_intensidad_bn.value(),
        )

    def _actualizar_preview_base(self):
        """Reduce la base a máx. 1400 px para que la vista previa vuele."""
        base = self._base_full()
        if base is None:
            self._preview_base = None
            return
        h, w = base.shape[:2]
        m = max(h, w)
        if m > 1400:
            r = 1400.0 / m
            self._preview_base = cv2.resize(
                base, None, fx=r, fy=r, interpolation=cv2.INTER_AREA
            )
        else:
            self._preview_base = base

    def _programar_actualizacion(self):
        """Reinicia el temporizador de debounce de los sliders."""
        self._timer_preview.start()

    def procesada_full(self):
        """Procesa la base a resolución completa con los parámetros actuales."""
        base = self._base_full()
        if base is None:
            return None
        return aplicar_pipeline(base, *self._params())

    def actualizar_procesado(self):
        """Refresca solo la vista previa (sobre la imagen reducida)."""
        if self._preview_base is None:
            self.lienzo_resultado.mostrar_imagen(None)
            return
        img = aplicar_pipeline(self._preview_base, *self._params())
        self.lienzo_resultado.mostrar_imagen(img)
        self._actualizar_barra_estado()

    def _resetear_sliders(self):
        for sld in (self.sld_brillo, self.sld_contraste, self.sld_nitidez):
            sld.blockSignals(True)
            sld.setValue(0)
            sld.blockSignals(False)

    def reset_ajustes(self):
        self._resetear_sliders()
        self.actualizar_procesado()

    def _al_cambiar_filtro(self, idx):
        self.settings.setValue("filtro_idx", idx)
        self.actualizar_procesado()

    # ----------------------------------------------------------
    # Guardado rápido (carpeta fija + nombre por fecha-hora)
    # ----------------------------------------------------------

    def _actualizar_label_carpeta(self):
        if self.carpeta_salida:
            self.lbl_carpeta_salida.setText(
                f"Carpeta: <b>{self.carpeta_salida}</b>"
            )
        else:
            self.lbl_carpeta_salida.setText(
                "<i>Sin carpeta fija — se preguntará la primera vez</i>"
            )

    def elegir_carpeta_salida(self):
        inicio = self.carpeta_salida or self._ruta_origen
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elige la carpeta donde guardar los escaneos", inicio
        )
        if carpeta:
            self.carpeta_salida = carpeta
            self.settings.setValue("carpeta_salida", carpeta)
            self._actualizar_label_carpeta()
        return bool(self.carpeta_salida)

    def _nombre_por_fecha(self, carpeta, ext=".jpg"):
        """Genera 'AAAA-MM-DD_HH-MM-SS.jpg', evitando pisar archivos."""
        base = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ruta = os.path.join(carpeta, base + ext)
        n = 2
        while os.path.exists(ruta):
            ruta = os.path.join(carpeta, f"{base}_{n}{ext}")
            n += 1
        return ruta

    def guardado_rapido(self):
        img = self.procesada_full()
        if img is None:
            QMessageBox.warning(self, "Atención", "No hay nada que guardar todavía.")
            return

        # Asegura una carpeta de destino válida (la pide solo la 1ª vez)
        if not self.carpeta_salida or not os.path.isdir(self.carpeta_salida):
            if not self.elegir_carpeta_salida():
                return

        ruta = self._nombre_por_fecha(self.carpeta_salida, ".jpg")
        try:
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not ok:
                raise RuntimeError("Error codificando JPEG")
            buf.tofile(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")
            return

        # Aviso no bloqueante en la barra de estado (no frena el flujo)
        self.statusBar().showMessage(
            f"✅ Guardado: {os.path.basename(ruta)}  →  {self.carpeta_salida}", 6000
        )

    def guardar(self, formato):
        img = self.procesada_full()
        if img is None:
            QMessageBox.warning(self, "Atención", "No hay nada que guardar todavía.")
            return

        formatos = {
            "jpg": ("JPEG (*.jpg)", ".jpg", "documento.jpg"),
            "png": ("PNG sin pérdida (*.png)", ".png", "documento.png"),
            "pdf": ("PDF (*.pdf)", ".pdf", "documento.pdf"),
        }
        filtro, ext, nombre_def = formatos[formato]
        carpeta_def = self.carpeta_salida or self._ruta_origen
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", os.path.join(carpeta_def, nombre_def), filtro
        )
        if not ruta:
            return
        if not ruta.lower().endswith(ext):
            ruta += ext

        try:
            if formato == "jpg":
                ok, buf = cv2.imencode(
                    ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95]
                )
                if not ok:
                    raise RuntimeError("Error codificando JPEG")
                buf.tofile(ruta)
            elif formato == "png":
                ok, buf = cv2.imencode(
                    ".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 3]
                )
                if not ok:
                    raise RuntimeError("Error codificando PNG")
                buf.tofile(ruta)
            else:
                cv_a_pil(img).save(ruta, "PDF", resolution=200.0)

            QMessageBox.information(
                self, "Guardado",
                f"Archivo guardado correctamente:\n{ruta}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e}")

    # ----------------------------------------------------------
    # PDF multipágina
    # ----------------------------------------------------------

    def anadir_pagina_pdf(self):
        img = self.procesada_full()
        if img is None:
            QMessageBox.warning(self, "Atención", "Procesa una imagen primero.")
            return
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        icono = QIcon(QPixmap.fromImage(qimg).scaled(
            80, 104, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        item = QListWidgetItem(icono, "")
        item.setData(Qt.ItemDataRole.UserRole, cv_a_pil(img))
        self.lista_pdf.addItem(item)
        self.lista_pdf.setCurrentItem(item)
        self._actualizar_barra_estado()

    def quitar_pagina_pdf(self):
        fila = self.lista_pdf.currentRow()
        if fila >= 0:
            self.lista_pdf.takeItem(fila)
        self._actualizar_barra_estado()

    def vaciar_paginas_pdf(self):
        self.lista_pdf.clear()
        self._actualizar_barra_estado()

    def exportar_pdf_multipagina(self):
        paginas = [
            self.lista_pdf.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.lista_pdf.count())
        ]
        if not paginas:
            QMessageBox.warning(self, "Atención",
                "No hay páginas. Añade con «➕ Añadir».")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar PDF",
            os.path.join(self._ruta_origen, "documento.pdf"), "PDF (*.pdf)")
        if not ruta:
            return
        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"
        try:
            paginas[0].save(ruta, "PDF", resolution=200.0,
                            save_all=True, append_images=paginas[1:])
            QMessageBox.information(self, "Exportado",
                f"PDF de {len(paginas)} páginas guardado en:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar el PDF:\n{e}")

    # ----------------------------------------------------------
    # Procesado por lotes
    # ----------------------------------------------------------

    def procesar_carpeta(self):
        carpeta_ent = QFileDialog.getExistingDirectory(
            self, "Selecciona la carpeta con las fotos a procesar",
            self.carpeta_salida or self._ruta_origen
        )
        if not carpeta_ent:
            return

        # Sugerir carpeta de salida automáticamente
        nombre_salida = os.path.basename(carpeta_ent.rstrip("/\\")) + "_escaneado"
        carpeta_sal_def = os.path.join(os.path.dirname(carpeta_ent), nombre_salida)
        carpeta_sal = QFileDialog.getExistingDirectory(
            self,
            f"Carpeta de salida (vacío = se creará «{nombre_salida}»)",
            carpeta_sal_def
        )
        if not carpeta_sal:
            carpeta_sal = carpeta_sal_def

        # Contar imágenes
        extensiones = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        archivos = [
            f for f in os.listdir(carpeta_ent)
            if os.path.splitext(f)[1].lower() in extensiones
        ]
        if not archivos:
            QMessageBox.information(
                self, "Sin imágenes",
                "No se encontraron imágenes en la carpeta seleccionada."
            )
            return

        # Diálogo de progreso
        progreso = QProgressDialog(
            "Procesando imágenes…", "Cancelar", 0, len(archivos), self
        )
        progreso.setWindowTitle("Procesado por lotes")
        progreso.setWindowModality(Qt.WindowModality.WindowModal)
        progreso.setMinimumDuration(0)

        cancelado = [False]

        def cb(i, total, nombre):
            if progreso.wasCanceled():
                cancelado[0] = True
                return
            progreso.setValue(i)
            progreso.setLabelText(f"Procesando ({i + 1}/{total}):\n{nombre}")
            QApplication.processEvents()

        filtro_idx = self.combo_filtro.currentIndex()
        b = self.sld_brillo.value()
        c = self.sld_contraste.value()
        n_sld = self.sld_nitidez.value()

        try:
            n_ok, n_err, errores = procesar_lote(
                carpeta_ent, carpeta_sal, filtro_idx, b, c, n_sld, cb
            )
        except Exception as e:
            progreso.close()
            QMessageBox.critical(self, "Error", f"Error durante el procesado:\n{e}")
            return

        progreso.setValue(len(archivos))
        progreso.close()

        if cancelado[0]:
            msg = f"Procesado cancelado.\n{n_ok} imágenes procesadas."
        else:
            msg = (
                f"Procesado completado.\n\n"
                f"✅ {n_ok} imagen{'es' if n_ok != 1 else ''} procesada{'s' if n_ok != 1 else ''}\n"
            )
            if n_err:
                msg += f"❌ {n_err} error{'es' if n_err != 1 else ''}:\n" + "\n".join(errores[:5])
                if len(errores) > 5:
                    msg += f"\n… y {len(errores) - 5} más."
            msg += f"\n\nGuardadas en:\n{carpeta_sal}"

        QMessageBox.information(self, "Lotes finalizado", msg)


# =============================================================
# ==========================   MAIN   =========================
# =============================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Instancia única: evita dos copias abiertas que bloqueen el .exe al actualizar.
    ruta_lock = os.path.join(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation),
        "EscanerFotos.lock",
    )
    lock = QLockFile(ruta_lock)
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(
            None, "Ya está abierto",
            "EscanerFotos ya se está ejecutando."
        )
        return

    ventana = VentanaPrincipal()
    ventana.show()

    # Comprobar actualizaciones poco después de abrir (no bloquea el arranque).
    QTimer.singleShot(1500, lambda: actualizador.conectar(ventana, __version__))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
