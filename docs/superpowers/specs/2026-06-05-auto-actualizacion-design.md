# Diseño: Auto-actualización para EscanerFotos (instalador)

**Fecha:** 2026-06-05
**Estado:** Aprobado (reemplaza la variante portable)

## Problema

EscanerFotos se distribuye como un `.exe` portable. Actualizar obliga a entrar a la web,
borrar la versión vieja y descargar la nueva en cada PC. Se quiere que la app **se
actualice sola** desde GitHub en cuanto se publique una versión nueva, con un modelo de
**`.exe` instalable** (accesos directos, reemplazo limpio gestionado por el instalador).

## Decisiones tomadas

- **Modelo instalador:** PyInstaller `--onedir` empaquetado con **Inno Setup**, que genera
  `EscanerFotos-Setup-X.Y.Z.exe`. (Reemplazo más robusto que el swap de un portable;
  patrón ya probado en notas-asesoria.)
- **Instalación por usuario, sin admin** (`PrivilegesRequired=lowest`, en `%LocalAppData%`),
  con accesos directos en Escritorio y Menú Inicio.
- **Repo de releases separado:** `Soakkk/EscanerFotos-releases` (ya creado).
- **Flujo de actualización:** avisar y elegir — al abrir, si hay versión nueva, diálogo
  *"Reiniciar e instalar" / "Más tarde"*; "Más tarde" instala al cerrar la app.
- **Plataforma objetivo:** Windows. Desarrollo en Mac; compilación en CI Windows.

## Arquitectura

Cuatro piezas:

1. **Versión única** (`version.py`): `__version__`, importada por la app y el updater.
2. **Lógica pura** (`actualizador_core.py`): `parse_version`, `es_mas_nueva`,
   `elegir_asset_exe`. Testeable sin Qt/red.
3. **Capa Qt** (`actualizador.py`): comprueba GitHub Releases en un hilo, descarga el
   `Setup.exe`, muestra el diálogo y lanza el instalador.
4. **Instalador** (`instalador.iss` + workflow): empaqueta y publica el `Setup.exe`.
5. **Instancia única** (`QLockFile`, en `escaner_fotos.py`): evita dos copias abiertas.

### 1. Empaquetado

- **PyInstaller `--onedir`** (`--windowed`, `--name EscanerFotos`, `--collect-all cv2`):
  genera la carpeta `dist/EscanerFotos/`.
- **Inno Setup** (`instalador.iss`):
  - **`AppId` fijo** (GUID estable): cada instalación reemplaza la anterior, no duplica.
  - `PrivilegesRequired=lowest` + `DefaultDirName={localappdata}\Programs\EscanerFotos`:
    instalación por usuario, sin UAC ni al instalar ni al actualizar.
  - `CloseApplications=yes` + `RestartApplications=yes`: cierra la app antes de reemplazar
    y la reabre. Sección `[Run]` sin `skipifsilent` para reabrir también en update silencioso.
  - Accesos directos en Escritorio (`{autodesktop}`) y Menú Inicio (`{userprograms}`).
  - Versión inyectada por línea de comandos: `iscc /DMyAppVersion=X.Y.Z instalador.iss`.
  - Salida: `Output/EscanerFotos-Setup-X.Y.Z.exe`.

### 2. Updater (`actualizador.py`)

- Solo activo en la app empaquetada (`getattr(sys, 'frozen', False)`).
- **Al arrancar** (en hilo aparte):
  - `GET https://api.github.com/repos/Soakkk/EscanerFotos-releases/releases/latest`.
  - Comparar `tag_name` con `__version__` (`es_mas_nueva`).
  - Si hay nueva: `elegir_asset_exe` (el `Setup.exe`) y **descargarlo a `%TEMP%`**.
  - **Verificar tamaño** (= `size` del asset) antes de proponer; si no cuadra, borrar y abortar.
- Diálogo modal *"Reiniciar e instalar" / "Más tarde"*:
  - **Reiniciar e instalar:** lanzar el `Setup.exe` con `/VERYSILENT /SUPPRESSMSGBOXES
    /NORESTART` y **cerrar la app**. El instalador cierra restos, reemplaza y reabre (vía
    `[Run]` + `RestartApplications`).
  - **Más tarde:** lanzar el instalador en el cierre de la app (`aboutToQuit`).
- **Errores silenciosos**: sin conexión / error → la app funciona con normalidad.
- Red: `urllib` (sin dependencias nuevas).

### 3. Instancia única

- `QLockFile` en `TempLocation`. Si ya hay instancia, salir. Evita que una segunda copia
  bloquee archivos durante la instalación.

### 4. Versionado

- `version.py` con `__version__`. Se sube a mano antes de taggear. El CI deriva la versión
  del tag (`v2.1` → `2.1`) y se la pasa a Inno con `/DMyAppVersion`.
- Comparación de versiones soporta distinto número de componentes.

### 5. CI/CD

Workflow en `Soakkk/EscanerFotos`, trigger `push` de tags `v*`:

1. Checkout, `setup-python` 3.12, `pip install` deps + pyinstaller.
2. PyInstaller `--onedir`.
3. Instalar Inno Setup (`choco install innosetup -y`).
4. `iscc /DMyAppVersion=<version> instalador.iss` → `Output/EscanerFotos-Setup-<v>.exe`.
5. Publicar la Release en **`Soakkk/EscanerFotos-releases`** con
   `softprops/action-gh-release` (`repository:` + `token: secrets.RELEASES_TOKEN`).

## Setup manual (una sola vez)

1. Repo `Soakkk/EscanerFotos-releases` con README. **(Hecho.)**
2. Secret `RELEASES_TOKEN` (PAT con escritura sobre `EscanerFotos-releases`) en `EscanerFotos`.
3. Instalar a mano la primera versión (descargar el primer `Setup.exe`). Después, automático.

## Flujo de publicación (futuro)

1. Subir `__version__` en `version.py` (ej. `2.0` → `2.1`).
2. `git commit` + `git tag v2.1` + `git push --tags`.
3. El CI compila el instalador y publica la Release. Los PCs se actualizan solos al abrir.

## Pruebas

- **Automatizadas (Mac):** lógica pura — `parse_version`, `es_mas_nueva`, `elegir_asset_exe`.
- **Manuales (Windows):** compilación del instalador (CI) y prueba real end-to-end (publicar
  un tag de prueba y ver que un PC con versión anterior se actualiza al abrir).

## Fuera de alcance (YAGNI)

- Modelo portable con swap del `.exe` (descartado en favor del instalador).
- Reintento periódico cada N horas (se comprueba solo al arrancar; la app es de
  abrir-procesar-cerrar).
- Actualizaciones diferenciales (se descarga el instalador completo).
- Icono propio del `.exe` (mejora opcional).
- Firma del instalador con certificado (de pago): SmartScreen avisará la primera vez.

## Riesgos y mitigaciones

- **Archivos bloqueados al instalar** (el bug de notas): mitigado con instancia única,
  `CloseApplications` + `RestartApplications` y cierre de la app antes de instalar.
- **Publicar en otro repo**: requiere PAT (`RELEASES_TOKEN`); documentado en setup.
- **SmartScreen**: instalador sin firmar; aviso la primera vez. Asumido.
