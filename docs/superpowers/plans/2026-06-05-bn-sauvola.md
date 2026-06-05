# B/N estilo escáner (Sauvola) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el modo Blanco y Negro dé texto nítido estilo escáner (CamScanner/Lens) usando binarización Sauvola, con un deslizador de intensidad.

**Architecture:** Se añade `binarizar_sauvola` (umbral local con OpenCV/NumPy) a `imagen.py` y se reescribe `filtro_bn_escaner` para: igualar luz → Sauvola → limpieza → ajuste de grosor según intensidad. La UI gana un deslizador "Intensidad B/N" que se pasa al pipeline.

**Tech Stack:** Python 3.12, OpenCV, NumPy, PySide6, pytest.

**Entorno de tests:** `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -v`

---

### Task 1: `binarizar_sauvola` (umbral local)

**Files:**
- Modify: `EscanerFotos/imagen.py`
- Modify: `tests/test_imagen.py`

- [ ] **Step 1: Write the failing test (append a tests/test_imagen.py)**

```python
from imagen import binarizar_sauvola

def test_sauvola_solo_da_0_y_255_y_conserva_tamano():
    gris = (np.random.rand(70, 90) * 255).astype(np.uint8)
    out = binarizar_sauvola(gris)
    assert out.shape == gris.shape
    assert out.dtype == np.uint8
    assert set(np.unique(out).tolist()).issubset({0, 255})

def test_sauvola_texto_fino_negro_sobre_fondo_con_sombra():
    # Fondo claro con gradiente de sombra + líneas finas oscuras (texto)
    h, w = 80, 160
    gris = np.tile(np.linspace(150, 255, w).astype(np.uint8), (h, 1)).copy()
    for y in (20, 30, 40, 50, 60):
        gris[y:y + 2, 30:130] = 15
    out = binarizar_sauvola(gris)
    # las líneas de texto quedan negras
    assert out[20:22, 30:130].mean() < 60
    # el fondo entre líneas queda blanco (pese al gradiente de sombra)
    assert out[24:28, 30:130].mean() > 180
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_imagen.py -k sauvola -v`
Expected: FAIL con `ImportError: cannot import name 'binarizar_sauvola'`

- [ ] **Step 3: Write minimal implementation (en imagen.py)**

```python
def binarizar_sauvola(gris, ventana=25, k=0.2, R=128.0):
    """Binarización local de Sauvola (umbral por píxel según media y desviación
    del entorno). Entra gris uint8, sale uint8 con solo 0 (texto) y 255 (fondo)."""
    if ventana % 2 == 0:
        ventana += 1
    g = gris.astype(np.float32)
    media = cv2.boxFilter(g, ddepth=-1, ksize=(ventana, ventana),
                          normalize=True, borderType=cv2.BORDER_REPLICATE)
    media_sq = cv2.boxFilter(g * g, ddepth=-1, ksize=(ventana, ventana),
                             normalize=True, borderType=cv2.BORDER_REPLICATE)
    var = np.clip(media_sq - media * media, 0, None)
    std = np.sqrt(var)
    T = media * (1.0 + k * (std / R - 1.0))
    return np.where(g > T, 255, 0).astype(np.uint8)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_imagen.py -k sauvola -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add EscanerFotos/imagen.py tests/test_imagen.py
git commit -m "feat: binarizar_sauvola (umbral local estilo escaner)"
```

---

### Task 2: `filtro_bn_escaner` con Sauvola + intensidad, y pipeline

**Files:**
- Modify: `EscanerFotos/imagen.py` (`filtro_bn_escaner`, `aplicar_pipeline`)
- Modify: `tests/test_imagen.py`

- [ ] **Step 1: Write the failing test (append)**

```python
import cv2 as _cv2  # ya importado arriba como cv2; alias por claridad

def _prop_negros(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float((g < 128).mean())

def test_filtro_bn_intensidad_controla_grosor():
    img = (np.random.rand(90, 120, 3) * 255).astype(np.uint8)
    baja = filtro_bn_escaner(img, intensidad=10)
    alta = filtro_bn_escaner(img, intensidad=90)
    assert baja.shape == img.shape and baja.dtype == np.uint8
    # más intensidad => texto más marcado => al menos tantos píxeles negros
    assert _prop_negros(alta) >= _prop_negros(baja)
```
(El import `from imagen import filtro_bn_escaner` ya existe arriba en el archivo; si no, añádelo.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_imagen.py -k intensidad -v`
Expected: FAIL (filtro_bn_escaner aún no acepta `intensidad`) — `TypeError` o aserción.

- [ ] **Step 3: Reescribir `filtro_bn_escaner` en imagen.py**

```python
def filtro_bn_escaner(imagen, intensidad=50):
    """B/N estilo escáner: iguala la luz, binariza con Sauvola, limpia motas y
    ajusta el grosor del texto según `intensidad` (0-100, 50 = neutro)."""
    base = igualar_iluminacion(imagen)
    gris = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    bn = binarizar_sauvola(gris, ventana=25, k=0.2)
    bn = cv2.medianBlur(bn, 3)
    # El texto es 0 (negro): erosionar engrosa el negro; dilatar lo adelgaza.
    if intensidad > 55:
        r = min(3, 1 + (intensidad - 55) // 20)
        bn = cv2.erode(bn, np.ones((r, r), np.uint8))
    elif intensidad < 45:
        r = min(3, 1 + (45 - intensidad) // 20)
        bn = cv2.dilate(bn, np.ones((r, r), np.uint8))
    return cv2.cvtColor(bn, cv2.COLOR_GRAY2BGR)
```

- [ ] **Step 4: Actualizar `aplicar_pipeline` en imagen.py**

```python
def aplicar_pipeline(base, filtro_idx, brillo, contraste, nitidez, intensidad_bn=50):
    if filtro_idx == 0:        # B/N escáner (iguala la luz internamente)
        img = filtro_bn_escaner(base, intensidad_bn)
    elif filtro_idx == 1:      # Color con luz corregida
        img = filtro_color_mejorado(igualar_iluminacion(base))
    else:                      # Color original
        img = base.copy()
    if brillo or contraste or nitidez:
        img = aplicar_ajustes(img, brillo, contraste, nitidez)
    return img
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -q`
Expected: PASS (incluido el test antiguo `test_pipeline_tres_modos_conservan_tamano`, que sigue válido con el nuevo parámetro por defecto).

- [ ] **Step 6: Commit**

```bash
git add EscanerFotos/imagen.py tests/test_imagen.py
git commit -m "feat: B/N con Sauvola + intensidad (grosor del texto) en el pipeline"
```

---

### Task 3: Deslizador "Intensidad B/N" en la UI

**Files:**
- Modify: `EscanerFotos/escaner_fotos.py` (`_construir_panel_controles`, `_params`)

- [ ] **Step 1: Añadir el deslizador en el grupo de filtro**

En `_construir_panel_controles`, localiza el grupo "Tipo de salida" (el del `self.combo_filtro`,
con su layout `l3`). Justo después de `l3.addWidget(self.combo_filtro)`, añade:
```python
        self.sld_intensidad_bn, fila_int_bn = self._crear_slider("Intensidad B/N", 0, 100, 50)
        l3.addLayout(fila_int_bn)
```
(`_crear_slider` ya conecta el cambio a `self._programar_actualizacion`, así que re-procesa
solo con debounce.)

- [ ] **Step 2: Pasar la intensidad al pipeline vía `_params`**

Localiza el método `_params` y sustitúyelo por:
```python
    def _params(self):
        """Parámetros actuales de filtro y ajustes finos."""
        return (
            self.combo_filtro.currentIndex(),
            self.sld_brillo.value(),
            self.sld_contraste.value(),
            self.sld_nitidez.value(),
            self.sld_intensidad_bn.value(),
        )
```
(Tanto `actualizar_procesado` como `procesada_full` llaman a `aplicar_pipeline(base, *self._params())`,
así que recogen el nuevo valor automáticamente.)

- [ ] **Step 3: Verify (smoke offscreen)**

```bash
python3 -m py_compile EscanerFotos/escaner_fotos.py
QT_QPA_PLATFORM=offscreen PYTHONPATH=EscanerFotos .venv/bin/python -c "
import numpy as np
import escaner_fotos as ef
from PySide6.QtWidgets import QApplication
app = QApplication([]); v = ef.VentanaPrincipal()
assert hasattr(v, 'sld_intensidad_bn') and len(v._params()) == 5
v.imagen_original = (np.random.rand(80,60,3)*255).astype('uint8'); v._actualizar_preview_base()
v.combo_filtro.setCurrentIndex(0)         # modo B/N
v.sld_intensidad_bn.setValue(80)
v.actualizar_procesado()                  # no debe lanzar
print('intensidad B/N OK; _params =', v._params())
"
PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -q
```
Expected: `intensidad B/N OK ...` + tests verdes.

- [ ] **Step 4: Commit**

```bash
git add EscanerFotos/escaner_fotos.py
git commit -m "feat: deslizador Intensidad B/N conectado al pipeline"
```

---

## Self-review (cobertura del spec)

- §"Pipeline nuevo del B/N" (igualar → Sauvola → limpieza) → Tasks 1 y 2. ✓
- §"binarizar_sauvola" → Task 1. ✓
- §"filtro_bn_escaner(intensidad)" + "aplicar_pipeline(intensidad_bn)" → Task 2. ✓
- §"UI deslizador Intensidad B/N" → Task 3. ✓
- §"Pruebas" (Sauvola texto/fondo; intensidad cambia proporción de negro) → Tasks 1 y 2. ✓

**Nota de afinado respecto al spec:** el control de intensidad se implementa como **grosor
del texto** (erosión/dilatación morfológica del resultado), no variando `k`. Es más
intuitivo y monótono ("más intensidad = texto más marcado") que tocar `k` de Sauvola; el
objetivo del spec ("intensidad alta = texto más marcado") se cumple igual. (El spec se
actualiza con esta nota.)

Sin placeholders. Nombres consistentes (`binarizar_sauvola`, `filtro_bn_escaner`,
`aplicar_pipeline`, `intensidad_bn`, `sld_intensidad_bn`, `_params`).

> Publicación (fuera de las tareas de código): al terminar, subir `version.py` a `2.5`,
> `git tag v2.5`, push → publica el instalador; prueba real del auto-update + del nuevo B/N.
