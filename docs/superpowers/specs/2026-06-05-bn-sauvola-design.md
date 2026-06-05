# Diseño: B/N "resaltado" estilo escáner (Sauvola) — v2.5

**Fecha:** 2026-06-05
**Estado:** Aprobado (pendiente de plan de implementación)

## Objetivo

Llevar el modo Blanco y Negro al nivel de las apps de escaneo (CamScanner/Google Lens):
texto negro nítido sobre fondo blanco limpio, sin las manchas grises ni las sombras que
deja el umbral adaptativo actual. Foco exclusivo en el **modo B/N de texto**.

## Decisiones tomadas

- **Algoritmo:** binarización **Sauvola** (umbral local según media y desviación del
  entorno), implementada con **OpenCV/NumPy** (sin nuevas dependencias). Es la técnica que
  usan por debajo las apps de escaneo para documentos de texto; equivalente a comerciales
  en facturas/contratos. La IA queda descartada por ahora (no mejora este caso y añade
  cientos de MB); se reconsideraría solo si el resultado real no convence.
- **Control de intensidad:** deslizador "Intensidad B/N" para ajustar al gusto/foto.
- El modo **Color** no se toca en esta versión.

## Pipeline nuevo del modo B/N

1. **Igualado de iluminación / quita-sombras** (paso ya existente `igualar_iluminacion`,
   se reutiliza): deja el fondo blanco uniforme.
2. **Binarización Sauvola** sobre el gris:
   - Media local `m` y desviación local `s` con ventana deslizante (vía `cv2.boxFilter`
     sobre la imagen y su cuadrado → media y varianza locales).
   - Umbral por píxel: `T = m * (1 + k * (s / R - 1))` con `R = 128`.
   - `binary = (gris > T) ? 255 : 0`.
3. **Limpieza fina**: `cv2.medianBlur(binary, 3)` para quitar motas/puntos sueltos.

## Componentes (en `EscanerFotos/imagen.py`)

- `binarizar_sauvola(gris, ventana=25, k=0.2, R=128.0) -> np.ndarray`
  Binarización pura (entra gris uint8, sale uint8 0/255). Usa `boxFilter` para media y
  media de cuadrados; varianza recortada a ≥0 antes de la raíz.
- `filtro_bn_escaner(imagen, intensidad=50)` (se reescribe):
  `igualar_iluminacion` → gris → `binarizar_sauvola` (k=0.2 fijo) → `medianBlur(3)` →
  ajuste de **grosor del texto** según `intensidad` (erosión/dilatación morfológica del
  resultado) → BGR. **Intensidad alta = texto más marcado** (>55 erosiona el negro para
  engrosarlo; <45 lo dilata para adelgazarlo; 50 = neutro). Enfoque morfológico elegido por
  ser monótono e intuitivo frente a variar `k`.
- `aplicar_pipeline(base, filtro_idx, brillo, contraste, nitidez, intensidad_bn=50)`:
  pasa `intensidad_bn` a `filtro_bn_escaner` cuando `filtro_idx == 0`.

## UI (en `EscanerFotos/escaner_fotos.py`)

- Deslizador **"Intensidad B/N"** (0–100, por defecto 50) en el panel. Solo afecta al modo
  B/N; al cambiar, re-procesa (mismo mecanismo de debounce que los otros sliders).
- `actualizar_procesado` / `procesada_full` pasan `self.sld_intensidad_bn.value()` como
  `intensidad_bn` al pipeline.

## Pruebas

- **Automatizadas (Mac):**
  - `binarizar_sauvola`: imagen sintética con texto oscuro sobre fondo claro **con
    gradiente de sombra** → las zonas de texto quedan 0 (negro) y el fondo 255 (blanco);
    salida uint8 con solo valores {0,255}; conserva tamaño.
  - `filtro_bn_escaner(img, intensidad)`: salida BGR del mismo tamaño, uint8; `intensidad`
    distinta cambia la proporción de píxeles negros (más intensidad → más negro).
- **Manuales (Windows):** comparar con facturas reales frente al B/N anterior.

## Fuera de alcance (YAGNI)

- Modo color "mágico" (otra iteración).
- IA / deep learning (solo si Sauvola no convence en pruebas reales).
- Binarización Niblack u otras (Sauvola es suficiente).

## Riesgos

- **Parámetros (ventana/k):** la calidad depende de ellos; el deslizador de intensidad y
  buenos defaults lo cubren, y se afina con fotos reales.
- **Rendimiento:** `boxFilter` es rápido incluso a resolución completa; la vista previa ya
  trabaja a ≤1400 px.
