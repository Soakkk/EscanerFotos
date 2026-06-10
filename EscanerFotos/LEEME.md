# Escáner de Fotos — Navaja suiza para documentos

Aplicación de escritorio para Windows que convierte fotos de documentos
(facturas, contratos, DNI) hechas con el móvil en imágenes tipo escáner:
recortadas, enderezadas y con el texto perfectamente legible.

Sin IA. Solo OpenCV puro. Rápido, ligero, sin dependencias raras.


## Cómo se usa (primera vez)

1. **Doble clic en `instalar.bat`**
   Comprueba que tienes Python y te instala las librerías necesarias.
   Solo hay que hacerlo una vez.

   > Si te dice que Python no está instalado: descárgalo desde
   > https://www.python.org/downloads/ y al instalarlo marca la casilla
   > **"Add Python to PATH"**. Después ejecuta `instalar.bat` de nuevo.

2. **Doble clic en `EscanerFotos.bat`**
   Se abre el programa.


## Cómo se usa (día a día)

Doble clic en `EscanerFotos.bat` y a tirar.

Flujo típico para una factura o contrato:

1. **📂 Abrir imagen** (o arrastra la foto sobre la ventana) → eliges la foto.
2. **🔍 Detectar automáticamente** → la app encuentra el papel y lo endereza.
   - Si la detección no acierta → **✏️ Marcar 4 esquinas a mano** (clic en cada esquina;
     clic derecho o Escape para deshacer).
   - Si el papel ya llena la foto entera → **↺ Usar sin recortar**.
3. **Tipo de salida**:
   - **B/N nítido** → para facturas, contratos y texto: limpio y suave,
     estilo CamScanner. Es el recomendado.
   - **B/N puro tinta** → solo negro y blanco puros; los PDFs ocupan
     poquísimo. Para archivar mucho volumen.
   - **Color con luz corregida** → para DNI, fotos con color importante.
   - **Color original** → si solo quieres recortar sin tocar nada más.
4. **Ajustes finos** (opcional): brillo, contraste, nitidez.
5. **💾 Guardar** como JPG, PNG o PDF.


## Atajos de teclado

| Atajo            | Acción                          |
|------------------|---------------------------------|
| Ctrl+O           | Abrir imagen                    |
| F5               | Detectar automáticamente        |
| Ctrl+Z           | Deshacer último punto (manual)  |
| Escape           | Cancelar modo manual            |
| Ctrl+R           | Resetear ajustes                |
| Ctrl+S           | Guardar como JPG                |
| Ctrl+E           | Guardar como PNG                |
| Ctrl+Shift+S     | Guardar como PDF                |


## Funcionalidades

- Vista lado a lado: foto original vs resultado en tiempo real.
- Arrastrar y soltar imágenes directamente sobre la ventana.
- Detección automática de bordes del papel (4 estrategias en cascada).
- Recorte manual con clic en las 4 esquinas (clic derecho para deshacer).
- Rotar 90° / 180° / 270° por si el móvil guardó la foto torcida.
- 3 modos de salida: B/N escáner, color mejorado, color original.
- Sliders de brillo, contraste y nitidez con previsualización al instante.
- Guardar en JPG (calidad 95%), PNG (sin pérdida) o PDF (200 DPI; los B/N
  se incrustan a 1 bit y ocupan poquísimo).
- **PDF multipágina**: acumula varias páginas y expórtalas en un solo PDF.
- **DNI 2 en 1**: añade las dos caras y pulsa «🪪 Unir 2 en 1 hoja» para
  tenerlas juntas en una sola hoja A4, como al fotocopiar un DNI.
- **Carpeta vigilada**: elige la carpeta donde caen tus fotos de WhatsApp
  y las nuevas entran solas a la cola de trabajo.
- **Prefijo**: escribe el cliente o concepto y los archivos se guardan como
  `Perez_2026-06-10_14-33-12.jpg` en vez de solo la fecha.
- **Procesado por lotes**: procesa una carpeta entera de fotos de golpe.
- Abre fotos de iPhone (HEIC/HEIF).


## ¿Y si quiero un `.exe` de verdad?

Tienes dos opciones:

1. **En tu PC**: ejecuta `crear_exe.bat`. Tarda 3-7 minutos y te genera un
   `.exe` único en la carpeta `dist\` que puedes copiar a otro ordenador.

2. **Automático en GitHub**: cada vez que subas un tag de versión
   (`git tag v2.0 && git push --tags`), GitHub compila el `.exe` solo y lo
   publica en la sección *Releases* del repositorio, listo para descargar.


## Archivos del proyecto

```
EscanerFotos/
├── escaner_fotos.py    ← La interfaz gráfica (la lógica de imagen está en imagen.py)
├── instalar.bat        ← Instalación inicial (una sola vez)
├── EscanerFotos.bat    ← Lanzador diario (doble clic aquí)
├── crear_exe.bat       ← Generar .exe (opcional)
└── LEEME.md            ← Este archivo
```


## Tecnología

- **Python 3.11+**
- **PySide6** — interfaz gráfica (Qt 6)
- **OpenCV 4** — procesado de imagen
- **NumPy** — operaciones numéricas
- **Pillow** — exportar a PDF y PNG

Probado en Windows 10 y 11.


## Notas técnicas para iterar con Claude Code

El archivo `escaner_fotos.py` está dividido en tres bloques bien marcados:

1. **Funciones de procesado** → toda la lógica de imagen. Pura, sin GUI.
   Aquí tocas para mejorar detección, añadir filtros, etc. Incluye
   `procesar_lote()` para el modo por lotes.

2. **LienzoImagen** (clase QLabel personalizada) → widget que muestra
   imágenes, soporta drag&drop y permite clicar para marcar puntos.

3. **VentanaPrincipal** (la GUI) → cableado de botones, sliders, atajos
   de teclado y acciones.

Cosas que se pueden añadir fácil:
- OCR (texto seleccionable en el PDF) con Tesseract.
- Detección de rotación automática (orientar texto siempre derecho).
- Guardar perfiles de ajustes para distintos tipos de documento.
- Captura desde webcam en tiempo real.

## Actualizaciones automáticas

EscanerFotos se **instala** en tu usuario (con accesos directos en Escritorio y Menú
Inicio) y se actualiza solo desde GitHub. La primera vez instalas el `Setup.exe`; a partir
de ahí, al abrir la app, si hay una versión más nueva te **avisa al instante**, y al
aceptar la **descarga con barra de progreso** y se instala sola (sin permisos de
administrador).

Todo vive en un único repositorio (`Soakkk/EscanerFotos`): el código y las Releases con el
instalador. No hace falta ningún token.

### Publicar una versión nueva (desarrollador)
1. Sube el número en `EscanerFotos/version.py` (p. ej. `2.1` -> `2.2`).
2. `git commit -am "v2.2"` y `git tag v2.2` y `git push --tags`.
3. GitHub Actions compila el instalador y publica la Release en este mismo repositorio.
   Los PCs se actualizan solos al abrir.

### Primera instalación
- Descarga el `Setup.exe` de la última Release e instálalo. A partir de ahí, automático.
