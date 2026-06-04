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

1. **📂 Abrir imagen** → eliges la foto que te ha mandado el cliente.
2. **🔍 Detectar automáticamente** → la app encuentra el papel y lo endereza.
   - Si la detección no acierta → **✏️ Marcar 4 esquinas a mano** (clic en cada esquina).
   - Si el papel ya llena la foto entera → **↺ Usar sin recortar**.
3. **Tipo de salida**:
   - **B/N escáner** → para facturas, contratos, documentos con mucho texto.
   - **Color con luz corregida** → para DNI, fotos con color importante.
   - **Color original** → si solo quieres recortar sin tocar nada más.
4. **Ajustes finos** (opcional): brillo, contraste, nitidez si hace falta.
5. **💾 Guardar como JPG** o **📄 Guardar como PDF**.


## Funcionalidades

- Vista lado a lado: foto original vs resultado en tiempo real.
- Detección automática de bordes del papel (4 estrategias en cascada).
- Recorte manual con clic en las 4 esquinas si el automático falla.
- Rotar 90° / 180° / 270° por si el móvil guardó la foto torcida.
- 3 modos de salida: B/N escáner, color mejorado, color original.
- Sliders de brillo, contraste y nitidez con previsualización al instante.
- Guardar en JPG (calidad 92%) o PDF (200 DPI).


## ¿Y si quiero un `.exe` de verdad?

Ejecuta `crear_exe.bat`. Tarda 2-5 minutos y te genera un `.exe` único
en la carpeta `dist\` que puedes copiar a otro ordenador sin necesidad
de instalar nada más.


## Archivos del proyecto

```
EscanerFotos/
├── escaner_fotos.py    ← El programa (~700 líneas, todo Python + OpenCV)
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
- **Pillow** — exportar a PDF

Probado en Windows 10 y 11.


## Notas técnicas para iterar con Claude Code

El archivo `escaner_fotos.py` está dividido en tres bloques bien marcados:

1. **Funciones de procesado** (líneas 1-200 aprox) → toda la lógica de
   imagen. Pura, sin GUI. Aquí es donde tocas si quieres mejorar
   detección, añadir filtros nuevos, etc.

2. **LienzoImagen** (clase QLabel personalizada) → el widget que muestra
   imágenes y permite hacer clic para marcar puntos.

3. **VentanaPrincipal** (la GUI) → cableado de botones, sliders y
   acciones. Aquí tocas si quieres añadir nuevos botones o cambiar el
   layout.

Cosas que se pueden añadir fácil:
- Procesamiento por lotes (procesar una carpeta entera de golpe).
- Combinar varias páginas en un único PDF.
- Detección de rotación automática (orientar texto siempre derecho).
- Guardar perfiles de ajustes para distintos tipos de documento.
- OCR (pasar a texto seleccionable en el PDF) con Tesseract.
