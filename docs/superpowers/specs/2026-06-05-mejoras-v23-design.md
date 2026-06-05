# Diseño: Mejoras v2.3 de EscanerFotos

**Fecha:** 2026-06-05
**Estado:** Aprobado (pendiente de plan de implementación)

## Objetivo

Tanda de mejoras de usabilidad y calidad sobre EscanerFotos, manteniendo el modelo
instalable + auto-actualización ya montado. Será la versión **2.3**, y su publicación
servirá además como prueba real del auto-update.

## Áreas

### 1. Arreglar solapamiento de controles en ventana grande / pantalla completa

**Problema:** el panel central de controles (grupos: cargar, rotar, recortar, filtro,
ajustes, guardar, PDF) se solapa y no se lee cuando la ventana se agranda o en pantalla
completa.

**Solución:** envolver el panel de controles en un `QScrollArea`
(`setWidgetResizable(True)`), con ancho fijo y scroll vertical cuando el contenido no
quepa. Revisar `setMinimumHeight`/políticas de tamaño de los grupos para que no se aplasten.

### 2. Recorte: mejor detección + esquinas arrastrables

- **Detección automática afinada:** aplicar el igualado de iluminación (área 3) *antes* de
  la detección para que las sombras no rompan los bordes; añadir una estrategia extra y
  ampliar tolerancias en `detectar_documento`.
- **Esquinas arrastrables (clave):** tras detectar (o si el usuario lo pide), `LienzoImagen`
  muestra los 4 vértices como puntos grandes que se pueden **arrastrar con el ratón**. Al
  soltar, se recalcula el enderezado. Esto sustituye/complementa el modo "marcar 4 clics":
  - `mousePressEvent`: si hay 4 puntos y el clic cae cerca de uno (radio ~15 px en
    coordenadas de pantalla), se selecciona ese vértice para arrastrar.
  - `mouseMoveEvent`: mueve el vértice seleccionado (en coordenadas de imagen).
  - `mouseReleaseEvent`: deselecciona y emite la señal para recalcular el enderezado.
  - Se conserva el modo "marcar 4 esquinas a mano" para cuando no hay detección previa.

### 3. Calidad de imagen: igualado de iluminación + afinado de filtros

**Causa principal de "regular":** sombras y luz irregular de las fotos de móvil.

- **Nueva función `igualar_iluminacion(imagen)`** (en color): estima el fondo con un
  desenfoque grande / operación morfológica y normaliza la imagen dividiéndola por ese
  fondo, dejando iluminación uniforme y sin sombras. Se aplica como primer paso del
  pipeline (antes del filtro), opcional según modo.
- **Afinado de los tres modos:**
  - **B/N (facturas/contratos):** sobre la imagen ya igualada, `adaptiveThreshold` con
    parámetros revisados (menos ruido/manchas); opción de leve denoise.
  - **Color general y DNI:** CLAHE + balance de blancos sobre la imagen igualada, con
    nitidez suave; colores naturales, sin quemar.
- Los deslizadores de brillo/contraste/nitidez siguen disponibles para retoque manual.

> La calidad fina se valida visualmente en Windows; el spec fija valores por defecto
> razonables y se ajustan tras la prueba.

### 4. Pegar con Ctrl+V (portapapeles)

- Atajo `Ctrl+V` → leer `QApplication.clipboard()`:
  - Si contiene **imagen** (`mimeData().hasImage()`): convertir `QImage` → array OpenCV
    BGR y cargarla como si se hubiera abierto.
  - Si contiene la **ruta de un archivo** de imagen copiado (`hasUrls()`): cargarlo.
- Se mantienen Abrir archivo, arrastrar y soltar, y procesar carpeta.

### 5. PDF de varias fotos, ordenable con miniaturas

Sustituye la sección "PDF multipágina" actual (añadir/vaciar/exportar sin ver ni ordenar):

- **`QListWidget` en modo icono** (`IconMode`) con `DragDropMode = InternalMove`: cada
  página añadida se ve como **miniatura** y se **reordena arrastrando**.
- **Añadir página actual** (la imagen procesada) → añade un item con su miniatura; la
  imagen PIL a tamaño completo se guarda asociada al item (en su `data`).
- **Quitar seleccionada** (botón o tecla Supr) y **Vaciar**.
- **Exportar PDF**: recorre los items en el orden visual y genera el PDF unido.

### 6. Reorganización interna (para poder testear)

`escaner_fotos.py` ha crecido demasiado. Separar el **procesado de imagen** en un módulo
nuevo `EscanerFotos/imagen.py` (funciones puras de OpenCV/PIL): `detectar_documento`,
`_buscar_cuadrilatero`, `ordenar_puntos`, `corregir_perspectiva`, `igualar_iluminacion`,
`filtro_bn_escaner`, `filtro_color_mejorado`, `aplicar_ajustes`, `aplicar_pipeline`,
`rotar_imagen`, `leer_imagen`, `cv_a_pil`. `escaner_fotos.py` las importa. La UI
(LienzoImagen, VentanaPrincipal) permanece en `escaner_fotos.py`.

## Componentes y archivos

- `EscanerFotos/imagen.py` (nuevo): procesado puro + `igualar_iluminacion`.
- `EscanerFotos/escaner_fotos.py`: scroll en panel, esquinas arrastrables en
  `LienzoImagen`, pegar Ctrl+V, panel PDF con `QListWidget`, imports desde `imagen.py`.
- `tests/test_imagen.py` (nuevo): tests del procesado.

## Pruebas

- **Automatizadas (Mac):** `igualar_iluminacion` (conserva forma/canales, reduce gradiente),
  `detectar_documento` sobre imagen sintética (encuentra el rectángulo), filtros
  (forma/tipo correctos), conversión `QImage`→cv2 del pegado (con Qt offscreen).
- **Manuales (Windows):** arrastrar esquinas, pegar Ctrl+V, miniaturas/reordenar PDF,
  pantalla completa sin solapamientos, y calidad visual de los tres modos.

## Fuera de alcance (YAGNI)

- OCR / reconocimiento de texto.
- Detección de documento con IA/deep learning (se mantiene "sin IA").
- Reordenar por arrastre entre varias ventanas; edición avanzada de PDF (rotar página
  individual dentro del PDF, etc.).

## Riesgos

- **Calidad de imagen** es subjetiva y se afina viéndola: se fijan defaults y se ajusta
  tras la prueba en Windows.
- **Arrastrar esquinas**: cuidar la conversión pantalla↔imagen (ya existe el mapeo
  `factor_escala`/`offset` en `LienzoImagen`).
- **Refactor a `imagen.py`**: cambio mecánico amplio; cubierto por que la app siga
  arrancando (smoke) y los tests del procesado.
