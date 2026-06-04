# Diseño: Auto-actualización para EscanerFotos (portable)

**Fecha:** 2026-06-05
**Estado:** Aprobado (pendiente de plan de implementación)

## Problema

EscanerFotos se distribuye como un `.exe` portable (PyInstaller `--onefile`), publicado
como Release al subir un tag `v*`. Para actualizar hay que entrar a la web, borrar la
versión vieja y descargar la nueva a mano en cada PC.

Se quiere que la app **se actualice sola** desde GitHub en cuanto se publique una versión
nueva, **manteniendo el modelo portable** (un único `.exe` que se copia, sin instalar).

## Decisiones tomadas

- **Enfoque A (portable):** se mantiene el `.exe` portable (`--onefile`). La propia app se
  encarga de descargar la versión nueva y reemplazarse mediante un ayudante.
- **Repo de releases separado:** `Soakkk/EscanerFotos-releases`.
- **Flujo de actualización:** avisar y elegir — al abrir, si hay versión nueva, diálogo
  *"Reiniciar e instalar" / "Más tarde"*; si elige "Más tarde", el reemplazo se hace al
  cerrar la app.
- **Plataforma objetivo:** Windows (oficina). Desarrollo en Mac; compilación en CI Windows.

## El reto técnico central

En Windows **no se puede sobrescribir un `.exe` mientras se está ejecutando**, pero **sí
se puede renombrar**. El mecanismo de actualización se apoya en eso: descargar el `.exe`
nuevo al lado del actual y, cuando la app cierra, un pequeño ayudante (`.bat`) renombra el
viejo, coloca el nuevo y reabre la app. Es el punto más delicado (es donde notas-asesoria
tuvo el bug de archivos bloqueados), por eso lleva varias defensas (ver §5).

## Arquitectura

Cuatro piezas:

1. **Versión única** (`version.py`): constante `__version__`, importada por la app y el
   updater. Fuente de verdad para comparar con la última release.
2. **Updater** (`actualizador.py`): comprueba GitHub Releases, descarga el `.exe` nuevo,
   muestra el diálogo y lanza el ayudante de reemplazo.
3. **Ayudante de reemplazo** (`.bat` generado en tiempo de ejecución): espera a que la app
   cierre, intercambia el `.exe` y reabre la app.
4. **Instancia única** (`QLockFile`): impide dos copias abiertas que bloqueen el `.exe`.

### 1. Empaquetado

- Se **mantiene PyInstaller `--onefile --windowed`** (como ahora). Salida: `EscanerFotos.exe`.
- No hay instalador ni dependencias nuevas de empaquetado.

### 2. Updater (`actualizador.py`)

- Solo activo en la app empaquetada (no en desarrollo: detectar con
  `getattr(sys, 'frozen', False)`).
- **Al arrancar** (en hilo aparte para no bloquear la UI) y **reintentando cada 3 h**:
  - `GET https://api.github.com/repos/Soakkk/EscanerFotos-releases/releases/latest`.
  - Parsear `tag_name` (`vX.Y.Z` → tupla numérica) y comparar con `__version__`.
  - Si la remota es mayor: localizar el asset `.exe` y **descargarlo a la misma carpeta
    del `.exe` actual** como `EscanerFotos.new.exe`.
    (Misma carpeta = mismo volumen → el reemplazo posterior es un `move` local fiable.)
  - **Verificar la descarga** (tamaño = `Content-Length` / `size` del asset) antes de
    proponer instalar. Si no cuadra, borrar el `.new` y abortar en silencio.
- Al completar y verificar la descarga, diálogo modal:
  - **"Reiniciar e instalar"**: generar el `.bat` ayudante, lanzarlo como proceso
    independiente (`subprocess.Popen` con `DETACHED_PROCESS`/`CREATE_NEW_PROCESS_GROUP`) y
    **cerrar la app** para soltar el `.exe`.
  - **"Más tarde"**: guardar la ruta y ejecutar el ayudante en el cierre de la app
    (`QApplication.aboutToQuit`).
- **Errores silenciosos**: sin conexión, timeout, respuesta inesperada o carpeta no
  escribible → no se muestra nada; la app funciona con normalidad.
- Red: `urllib` (sin añadir dependencias como `requests`).

### 3. Ayudante de reemplazo (`.bat`)

Generado en `%TEMP%` con la ruta del `.exe` incrustada. Pasos:

1. Esperar a que el `.exe` quede libre: bucle que intenta renombrar con reintentos y un
   tope de tiempo (la app ya se está cerrando).
2. `move /Y EscanerFotos.exe EscanerFotos.old.exe`.
3. `move /Y EscanerFotos.new.exe EscanerFotos.exe`.
4. `start "" EscanerFotos.exe`.
5. Borrar `EscanerFotos.old.exe` y autoeliminarse.

Al **arrancar**, la app limpia restos de updates previos: si existe `EscanerFotos.old.exe`,
lo borra.

### 4. Versionado (fuente de verdad)

- `version.py` con `__version__ = "X.Y.Z"`.
- El usuario sube `__version__` a mano antes de taggear. El workflow deriva la versión del
  tag git (`v2.1.0` → `2.1.0`) para nombrar el asset si procede.
- La comparación de versiones soporta distinto número de componentes (ej. `2` vs `2.1.0`).

### 5. Defensas anti-bug (lecciones de notas, aplicadas al portable)

- **Instancia única** (`QLockFile`): nunca dos copias con el `.exe` abierto a la vez.
- **Renombrar en vez de sobrescribir**: el ayudante mueve, no escribe sobre el `.exe` vivo.
- **Reintentos con espera** en el ayudante hasta que el archivo se libere.
- **Verificación de la descarga** (tamaño) antes de tocar el `.exe` actual.
- **Carpeta escribible**: si el `.exe` está en una ruta sin permiso de escritura (p. ej.
  `Archivos de programa`), el updater lo detecta y no intenta nada (mensaje opcional). Se
  documenta usar una carpeta del usuario (Escritorio/Documentos/carpeta propia).
- El repo `EscanerFotos-releases` tendrá un `README` (≥1 archivo) para poder crear tags.

### 6. CI/CD

Se **reutiliza el workflow actual** (`build.yml`, PyInstaller `--onefile`), con dos cambios:

1. Publicar la Release en **`Soakkk/EscanerFotos-releases`** (no en el repo de código),
   con `softprops/action-gh-release` usando `repository: Soakkk/EscanerFotos-releases` y
   un **PAT** (`secrets.RELEASES_TOKEN`), porque el `GITHUB_TOKEN` por defecto solo cubre
   el repo actual.
2. El asset publicado es `EscanerFotos.exe` (el updater busca el asset `.exe` de la release).

## Setup manual (una sola vez)

1. Crear el repo `Soakkk/EscanerFotos-releases` con un `README`.
2. Crear un **Personal Access Token** con permiso sobre `EscanerFotos-releases` y
   guardarlo como secret `RELEASES_TOKEN` en `EscanerFotos`.
3. Colocar `EscanerFotos.exe` en una **carpeta del usuario** (no en `Archivos de programa`).
4. La primera versión se coloca a mano (descargar el primer `.exe`). A partir de ahí,
   automático.

## Flujo de publicación (futuro, para el usuario)

1. Subir `__version__` en `version.py` (ej. `2.0` → `2.1`).
2. `git commit` + `git tag v2.1` + `git push --tags`.
3. El CI compila el `.exe` y publica la Release. Los PCs se actualizan solos al abrir.

## Pruebas

- **Automatizadas (en Mac):** lógica pura del updater — parseo de `tag_name`, comparación
  de versiones (mayor/menor/igual, distinto número de componentes), decisión "¿hay
  actualización?", y **generación del contenido del `.bat`** (verificable como texto). TDD.
- **Manuales (solo Windows):** prueba real de extremo a extremo — publicar un tag de
  prueba y comprobar que un PC con la versión anterior detecta, descarga y se reemplaza,
  reabriéndose ya actualizado.

## Fuera de alcance (YAGNI)

- Instalador (Inno Setup) y accesos directos: descartado al elegir portable.
- Actualizaciones diferenciales/parches (se descarga el `.exe` completo, ~150-200 MB;
  aceptable para 1-pocos equipos).
- Icono propio del `.exe` (mejora opcional; no bloquea el updater).
- Firma del `.exe` con certificado (de pago): Windows SmartScreen seguirá avisando la
  primera vez. Asumido.
- Canales beta / rollback de versiones.

## Riesgos y mitigaciones

- **Reemplazo de un `.exe` en ejecución** (el bug de notas): mitigado con instancia única,
  renombrar en vez de sobrescribir, ayudante con reintentos y verificación de descarga.
- **Carpeta no escribible**: el updater lo detecta y no actúa; documentado usar carpeta de
  usuario.
- **Publicar en otro repo**: requiere PAT (`RELEASES_TOKEN`); documentado en setup manual.
- **SmartScreen**: el `.exe` sin firmar mostrará aviso la primera vez; aceptado.
