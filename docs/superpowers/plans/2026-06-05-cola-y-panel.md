# Cola de trabajo + panel compacto (v2.4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Procesar tandas de fotos en cola (cargar muchas, trabajarlas una a una con un botón "Añadir al PDF y siguiente") y compactar el panel central con secciones plegables.

**Architecture:** La lógica pura de la cola vive en `cola.py` (testeable sin Qt). La UI en `escaner_fotos.py` gana estado de cola, carga múltiple por arrastre/abrir, un helper de grupos plegables y un botón de flujo, manteniendo el panel de PDF con miniaturas.

**Tech Stack:** Python 3.12, PySide6 (Qt6), OpenCV, Pillow, pytest.

**Entorno de tests:** `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -v`

---

### Task 1: Lógica pura de la cola (`cola.py`)

**Files:**
- Create: `EscanerFotos/cola.py`
- Create: `tests/test_cola.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cola.py
from cola import siguiente_de_cola, texto_cola

def test_siguiente_saca_el_primero():
    assert siguiente_de_cola(["a", "b", "c"]) == ("a", ["b", "c"])

def test_siguiente_de_cola_vacia():
    assert siguiente_de_cola([]) == (None, [])

def test_texto_sin_cola():
    assert texto_cola(1, 1) == ""
    assert texto_cola(0, 0) == ""

def test_texto_en_mitad_de_la_tanda():
    assert texto_cola(1, 5) == "📥 Foto 1 de 5"
    assert texto_cola(3, 5) == "📥 Foto 3 de 5"

def test_texto_ultima_de_la_tanda():
    assert texto_cola(5, 5) == "✓ Última de la tanda"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_cola.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'cola'`

- [ ] **Step 3: Write minimal implementation**

```python
# EscanerFotos/cola.py
"""Lógica pura de la cola de fotos (sin Qt)."""


def siguiente_de_cola(cola):
    """Saca el primer elemento: devuelve (siguiente, resto).
    Con la cola vacía devuelve (None, [])."""
    if not cola:
        return None, []
    return cola[0], list(cola[1:])


def texto_cola(pos, total):
    """Texto del indicador de cola. pos=foto actual (1-based), total=tamaño de la tanda."""
    if total <= 1:
        return ""
    if pos < total:
        return f"📥 Foto {pos} de {total}"
    return "✓ Última de la tanda"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_cola.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add EscanerFotos/cola.py tests/test_cola.py
git commit -m "feat: lógica pura de la cola de fotos"
```

---

### Task 2: Integrar la cola y el panel compacto en la app

Cambios en `escaner_fotos.py`. Es un cambio amplio pero acoplado (panel + flujo de cola van
juntos). Aplica los pasos en orden. LEE el archivo primero para ubicar los puntos.

**Files:**
- Modify: `EscanerFotos/escaner_fotos.py`

- [ ] **Step 1: Imports y estado**

En el import de `cola` (nuevo) al lado de los otros imports locales:
```python
from cola import siguiente_de_cola, texto_cola
```
Asegura que `QWidget` está importado de `PySide6.QtWidgets` (ya lo está). En
`VentanaPrincipal.__init__`, junto a los demás atributos de estado, añade:
```python
        self.cola = []
        self.cola_total = 0
        self.cola_pos = 0
```

- [ ] **Step 2: Helper de grupo plegable**

Añade este método a `VentanaPrincipal`:
```python
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
```

- [ ] **Step 3: Lienzo — arrastrar varias imágenes**

En `LienzoImagen`, junto a las señales existentes, añade:
```python
    imagenes_soltadas = Signal(list)   # varias rutas soltadas a la vez
```
Y sustituye el método `dropEvent` de `LienzoImagen` por:
```python
    def dropEvent(self, event):
        exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp')
        rutas = [u.toLocalFile() for u in event.mimeData().urls()
                 if u.isLocalFile() and u.toLocalFile().lower().endswith(exts)]
        if rutas:
            self.imagenes_soltadas.emit(rutas)
```

- [ ] **Step 4: Ventana — recoger rutas de imagen y carga múltiple**

Añade a `VentanaPrincipal` un helper y sustituye su `dropEvent`:
```python
    def _rutas_imagen_de(self, mime):
        exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp')
        return [u.toLocalFile() for u in mime.urls()
                if u.isLocalFile() and u.toLocalFile().lower().endswith(exts)] \
            if mime.hasUrls() else []

    def dropEvent(self, event):
        rutas = self._rutas_imagen_de(event.mimeData())
        if rutas:
            self._iniciar_cola(rutas)
```

- [ ] **Step 5: Métodos de la cola**

Añade a `VentanaPrincipal`:
```python
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
            QMessageBox.information(
                self, "Cola terminada",
                f"Has terminado la tanda.\n{n} página{'s' if n != 1 else ''} en el PDF.")
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
```

- [ ] **Step 6: Abrir varias imágenes**

Sustituye el cuerpo de `abrir_imagen` por:
```python
    def abrir_imagen(self):
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Abrir imágenes", self._ruta_origen,
            "Imágenes (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp);;"
            "Todos los archivos (*.*)")
        if rutas:
            self._iniciar_cola(rutas)
```

- [ ] **Step 7: Panel — indicador de cola, botón de flujo y plegables**

En `_construir_panel_controles`:

(a) Reduce el espaciado: cambia `panel.setSpacing(8)` por `panel.setSpacing(6)`.

(b) Conecta el lienzo a la carga múltiple. En `_crear_interfaz`, donde se conecta
`self.lienzo_original.imagen_soltada.connect(self._cargar_archivo)`, añade debajo:
```python
        self.lienzo_original.imagenes_soltadas.connect(self._iniciar_cola)
```

(c) Tras el grupo "Cargar foto" (`panel.addWidget(g1)`), inserta el indicador de cola:
```python
        self.lbl_cola = QLabel("")
        self.lbl_cola.setStyleSheet(
            "background:#243; color:#9f9; padding:5px; border-radius:4px; font-weight:bold;")
        self.lbl_cola.setVisible(False)
        panel.addWidget(self.lbl_cola)
```

(d) Convierte el grupo **Rotar** en plegable. Localiza el grupo de rotar (el `QGroupBox`
"🔄 Rotar (si hace falta)" con los tres botones) y cámbialo para que su contenido vaya en
un `QWidget` y se envuelva con `_grupo_plegable`. Es decir, donde antes hacía
`g_rot = QGroupBox(...)` con su `QHBoxLayout` de botones, déjalo así:
```python
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
```

(e) Convierte el grupo **Ajustes finos** en plegable. Donde construye los sliders
(`self.sld_brillo, fila1 = ...`, etc. dentro del grupo "Ajustes finos"), mete las tres
filas y el botón de reset en un `QWidget` y envuélvelo:
```python
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
```

(f) Justo **antes** del grupo "Guardar resultado", inserta el botón de flujo:
```python
        self.btn_terminar = QPushButton("✓  Añadir al PDF y siguiente  →")
        self.btn_terminar.setMinimumHeight(46)
        self.btn_terminar.setStyleSheet(
            "QPushButton { background-color:#1565c0; color:white; font-size:14px;"
            " font-weight:bold; border-radius:5px; }"
            "QPushButton:hover { background-color:#1976d2; }")
        self.btn_terminar.clicked.connect(self.terminar_y_siguiente)
        panel.addWidget(self.btn_terminar)
```

- [ ] **Step 8: Verify (smoke offscreen)**

```bash
python3 -m py_compile EscanerFotos/escaner_fotos.py
QT_QPA_PLATFORM=offscreen PYTHONPATH=EscanerFotos .venv/bin/python -c "
import numpy as np, tempfile, os, cv2
import escaner_fotos as ef
from PySide6.QtWidgets import QApplication
app = QApplication([]); v = ef.VentanaPrincipal()
# Crea 3 imágenes temporales y simula una tanda en cola
d = tempfile.mkdtemp(); rutas = []
for i in range(3):
    p = os.path.join(d, f'f{i}.png'); cv2.imwrite(p, (np.random.rand(40,30,3)*255).astype('uint8')); rutas.append(p)
v._iniciar_cola(rutas)
assert v.cola_total == 3 and len(v.cola) == 2 and v.cola_pos == 1, (v.cola_total, len(v.cola), v.cola_pos)
assert v.lbl_cola.isVisible() and 'Foto 1 de 3' in v.lbl_cola.text()
v.terminar_y_siguiente()  # añade al PDF y carga la 2
assert v.lista_pdf.count() == 1 and v.cola_pos == 2 and len(v.cola) == 1
v.terminar_y_siguiente()  # 3ª (última)
v.terminar_y_siguiente()  # vacía -> cola terminada
assert v.cola_total == 0 and v.lista_pdf.count() == 3
print('cola + panel OK')
"
PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -q
```
Expected: `cola + panel OK` + tests verdes.

- [ ] **Step 9: Commit**

```bash
git add EscanerFotos/escaner_fotos.py
git commit -m "feat: cola de fotos (añadir al PDF y siguiente) y panel compacto plegable"
```

---

## Self-review (cobertura del spec)

- §1 cola (estado, drop/abrir múltiples, iniciar/avanzar/terminar, indicador) → Tasks 1 y 2
  (pasos 1, 3-6) + botón (paso 7f). ✓
- §2 panel compacto (helper plegable, Rotar y Ajustes plegables, indicador, botón,
  spacing) → Task 2 (pasos 2, 7). ✓
- §3 sin cambios (PDF miniaturas, guardado rápido, pegar, esquinas) → no se tocan. ✓
- §pruebas → Task 1 (TDD `cola.py`) + smoke de cola en Task 2 paso 8. ✓

Sin placeholders. Nombres consistentes (`siguiente_de_cola`, `texto_cola`, `_iniciar_cola`,
`_cargar_siguiente_de_cola`, `terminar_y_siguiente`, `_actualizar_indicador_cola`,
`_grupo_plegable`, `lbl_cola`, `btn_terminar`, `imagenes_soltadas`, `anadir_pagina_pdf`,
`lista_pdf`).

> Publicación (fuera de las tareas de código): al terminar, subir `version.py` a `2.4`,
> `git tag v2.4`, push → publica el instalador; la app se actualiza sola (sigue probando
> el auto-update).
