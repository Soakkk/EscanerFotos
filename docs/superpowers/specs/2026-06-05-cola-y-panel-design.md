# Diseño: Cola de trabajo + panel compacto (v2.4)

**Fecha:** 2026-06-05
**Estado:** Aprobado (pendiente de plan de implementación)

## Objetivo

Acelerar el procesado de tandas de fotos (típico de WhatsApp): cargar muchas de golpe,
trabajarlas una a una y montar un PDF, con un panel central más compacto. Será la v2.4.

## Decisiones tomadas

- **Cola de fotos:** se cargan varias a la vez; se trabaja la actual y un único botón
  **"✓ Añadir al PDF y siguiente"** añade la foto al PDF y carga la siguiente.
- **Sin "saltar":** todas las que se procesan van al PDF (no hay descarte en la cola).
- **Panel compacto:** "Rotar" y "Ajustes finos" pasan a **secciones plegables** (cerradas
  por defecto); el resto se reordena para que quepa con poco scroll.
- Se **mantiene** el panel de PDF con miniaturas reordenables (v2.3) y todo lo demás
  (guardado rápido, pegar Ctrl+V, esquinas arrastrables, procesar carpeta).

## Áreas

### 1. Cola de fotos

**Estado nuevo en `VentanaPrincipal`:**
- `self.cola = []` — lista de rutas pendientes (las que esperan su turno).
- `self.cola_total = 0` — total de la tanda actual (para el contador "X de N").
- `self.cola_pos = 0` — índice de la foto actual dentro de la tanda (1-based para mostrar).

**Entrada de varias fotos:**
- **Arrastrar varias:** `dropEvent` (de la ventana y del lienzo) recoge **todas** las URLs
  de imagen válidas, no solo la primera. La primera se carga; el resto van a `self.cola`.
- **Abrir varias:** `abrir_imagen` usa `QFileDialog.getOpenFileNames` (plural). Igual:
  primera se carga, resto a la cola.
- Si solo hay una, comportamiento idéntico al actual (cola vacía).

**Avance:**
- `_iniciar_cola(rutas)`: fija `cola_total = len(rutas)`, `cola_pos = 1`, carga la primera
  con `_cargar_archivo`, guarda el resto en `self.cola`, actualiza el indicador.
- `_cargar_siguiente_de_cola()`: si `self.cola` no está vacía, saca la primera, incrementa
  `cola_pos`, la carga y actualiza el indicador; si está vacía, marca cola terminada.
- `terminar_y_siguiente()` (botón principal): llama a `anadir_pagina_pdf()` (añade la foto
  procesada actual al PDF); luego `_cargar_siguiente_de_cola()`. Si la cola queda vacía,
  muestra aviso **"Cola terminada — N páginas en el PDF"** (N = `lista_pdf.count()`).

**Indicador:**
- `lbl_cola` (un `QLabel` en el panel): muestra **"📥 Foto X de N en cola"** cuando
  `cola_pos < cola_total` o hay elementos en cola; cuando se vacía, **"Cola terminada"** o
  se oculta si nunca hubo cola. Método `_actualizar_indicador_cola()`.

**Botón principal:**
- `btn_terminar` = "✓  Añadir al PDF y siguiente" (destacado, alto). `clicked` →
  `terminar_y_siguiente`. Atajo de teclado (p. ej. `Ctrl+Intro`) opcional.
- Sin cola: el botón sigue funcionando como "añadir la actual al PDF" (no hay siguiente).

### 2. Panel central compacto con plegables

- Crear un helper `_grupo_plegable(titulo, contenido_widget, abierto=False)` que devuelve
  un `QGroupBox` *checkable*: el contenido vive en un `QWidget` interno cuya visibilidad se
  liga a `toggled`; arranca plegado (oculto) si `abierto=False`. (Qt no oculta los hijos al
  desmarcar por defecto, por eso el widget interno + `toggled.connect(interno.setVisible)`.)
- **Rotar** y **Ajustes finos** se construyen con `_grupo_plegable(...)`, cerrados.
- Reordenar el panel: Cargar → indicador Cola → Recortar → Tipo de salida → [Rotar plegable]
  → [Ajustes finos plegable] → **Añadir al PDF y siguiente** → Guardar → PDF (miniaturas).
- Reducir separaciones (`setSpacing`) y altura de botones secundarios para compactar.
- Se conserva el `QScrollArea` (v2.3) como red de seguridad para pantallas pequeñas.

### 3. Sin cambios

Panel PDF con miniaturas reordenables, guardado rápido, pegar Ctrl+V, esquinas
arrastrables, procesar carpeta, auto-actualización.

## Componentes y archivos

- `EscanerFotos/escaner_fotos.py`: estado y métodos de cola, `dropEvent`/`abrir_imagen`
  múltiples, `_grupo_plegable`, reorganización de `_construir_panel_controles`, botón
  `btn_terminar`, `lbl_cola`.
- `EscanerFotos/cola.py` (nuevo): lógica pura de la cola (sin Qt) para poder testearla:
  `siguiente_de_cola(cola)` y el cálculo del texto del indicador `texto_cola(pos, total)`.
- `tests/test_cola.py` (nuevo): tests de la lógica pura de cola.

## Pruebas

- **Automatizadas (Mac):** lógica pura de `cola.py` (sacar siguiente, texto del contador en
  los casos: con cola, última, sin cola). Smoke: la app arranca, `_iniciar_cola` con 3 rutas
  deja 2 en cola y `terminar_y_siguiente` avanza.
- **Manuales (Windows):** arrastrar una tanda, recorrerla con el botón, plegables, que el
  panel no obligue a hacer scroll.

## Fuera de alcance (YAGNI)

- Descartar/saltar fotos de la cola.
- Reordenar la cola de entrada (solo el PDF se reordena).
- Procesado por lotes automático nuevo (el existente "Procesar carpeta" se mantiene).

## Riesgos

- **Drop múltiple:** asegurar que se filtran solo extensiones de imagen y se conserva el
  orden de selección.
- **Plegables:** la altura del panel cambia al plegar/desplegar; el `QScrollArea` lo
  absorbe sin problema.
