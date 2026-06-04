# Escáner de Fotos

Aplicación de escritorio para Windows que convierte fotos de documentos hechas con el móvil en imágenes tipo escáner: recortadas, enderezadas y con el texto perfectamente legible.

**Sin IA. Solo OpenCV puro.** Rápido, ligero, sin dependencias raras.

---

## Captura de pantalla

> Vista lado a lado: foto original del móvil (izquierda) → documento escaneado limpio (derecha).

---

## Características

| Función | Descripción |
|---|---|
| 🔍 Detección automática | 4 estrategias en cascada (Canny, umbral adaptativo, HSV, Otsu) |
| ✏️ Selección manual | Clic en las 4 esquinas; clic derecho / Escape para deshacer |
| 🔄 Rotar | 90° / 180° / 270° por si el móvil guardó la foto torcida |
| ⚪ B/N escáner | Umbral adaptativo. Ideal para facturas y contratos |
| 🎨 Color mejorado | CLAHE + balance de blancos gray-world + filtro bilateral |
| 📷 Color original | Solo recorte, sin retocar color |
| 🎚️ Ajustes finos | Brillo, contraste y nitidez con sliders en tiempo real |
| 💾 JPG | Calidad 92% |
| 🖼️ PNG | Sin pérdida de calidad |
| 📄 PDF | Página única o multipágina (varias páginas juntas) |
| 📁 Lotes | Procesa una carpeta entera de golpe |
| ↕️ Drag & drop | Arrastra la imagen directamente sobre la ventana |

---

## Instalación rápida (primera vez)

1. **Asegúrate de tener Python 3.11 o superior:**
   Descárgalo desde [python.org](https://www.python.org/downloads/) y al instalar marca **"Add Python to PATH"**.

2. **Doble clic en `instalar.bat`**
   Instala automáticamente PySide6, OpenCV, NumPy y Pillow. Solo hay que hacerlo una vez.

3. **Doble clic en `EscanerFotos.bat`**
   Se abre el programa.

---

## Uso diario

Doble clic en `EscanerFotos.bat`.

### Flujo típico para una factura o contrato

1. **📂 Abrir imagen** (o arrastra la foto sobre la ventana) → `Ctrl+O`
2. **🔍 Detectar automáticamente** → `F5`
   - Si falla → **✏️ Marcar 4 esquinas a mano** (clic en cada esquina, clic derecho para deshacer)
   - Si el papel ya llena toda la foto → **↺ Usar sin recortar**
3. **Tipo de salida:** B/N escáner para documentos, Color mejorado para DNI
4. **Ajustes** (opcionales): brillo, contraste, nitidez
5. **Guardar:** JPG (`Ctrl+S`), PNG (`Ctrl+E`) o PDF (`Ctrl+Shift+S`)

### PDF con varias páginas

1. Procesa cada página y pulsa **➕ Añadir página actual** para ir añadiéndolas a la cola.
2. Cuando tengas todas, pulsa **📄 Exportar PDF multipágina**.

### Procesar carpeta entera

Pulsa **📁 Procesar carpeta por lotes…**, elige la carpeta de entrada y la de salida. Aplica automáticamente los ajustes actuales a todas las imágenes.

---

## Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+O` | Abrir imagen |
| `F5` | Detectar automáticamente |
| `Ctrl+Z` | Deshacer último punto (modo manual) |
| `Escape` | Cancelar modo manual |
| `Ctrl+R` | Resetear ajustes de brillo/contraste/nitidez |
| `Ctrl+S` | Guardar como JPG |
| `Ctrl+E` | Guardar como PNG |
| `Ctrl+Shift+S` | Guardar como PDF |

---

## Generar un .exe para distribuir

Ejecuta `crear_exe.bat`. Tarda 3-7 minutos y genera `dist\EscanerFotos.exe`, un ejecutable único (~150-200 MB) que funciona en cualquier Windows sin instalar nada.

---

## Tecnología

- **Python 3.11+**
- **PySide6** — interfaz gráfica (Qt 6)
- **OpenCV 4** — procesado de imagen
- **NumPy** — operaciones numéricas
- **Pillow** — exportar a PDF y PNG

Probado en Windows 10 y 11.

---

## Estructura del proyecto

```
EscanerFotos/
├── escaner_fotos.py    ← Programa principal (~850 líneas, Python + OpenCV)
├── instalar.bat        ← Instalación inicial (una sola vez)
├── EscanerFotos.bat    ← Lanzador diario
├── crear_exe.bat       ← Generar .exe para distribuir
└── LEEME.md            ← Instrucciones en español (offline)
```

---

## Contribuir / seguir desarrollando

El código está dividido en tres bloques claros:

1. **Funciones de procesado** (`detectar_documento`, `filtro_*`, etc.) — lógica pura, sin GUI.
2. **`LienzoImagen`** — widget QLabel con drag&drop y selección de puntos.
3. **`VentanaPrincipal`** — interfaz gráfica, botones y acciones.

Ideas para futuras mejoras:
- OCR con Tesseract (texto seleccionable en el PDF)
- Detección automática de orientación del texto
- Guardar perfiles de ajustes por tipo de documento
- Soporte para cámara en tiempo real (OpenCV + webcam)

---

## Licencia

Uso personal. Generado con asistencia de [Claude](https://claude.ai).
