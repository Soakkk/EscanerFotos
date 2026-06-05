# Auto-actualización (instalador) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** EscanerFotos como `.exe` instalable (Inno Setup, por usuario) que detecta versiones nuevas en GitHub Releases, descarga el instalador y se reemplaza con un clic.

**Architecture:** Lógica pura en `actualizador_core.py` (versiones, selección de asset). Capa Qt en `actualizador.py` comprueba y descarga el `Setup.exe`, y tras confirmación lo ejecuta en silencio (el instalador cierra la app, reemplaza y reabre). `instalador.iss` define el instalador perUser; el workflow compila `--onedir` + Inno y publica en el repo de releases.

**Tech Stack:** Python 3.12, PySide6, urllib, PyInstaller `--onedir`, Inno Setup, GitHub Actions, pytest (dev).

**Repos:** código en `Soakkk/EscanerFotos`; releases en `Soakkk/EscanerFotos-releases`.

---

## Entorno de tests

```bash
PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -v
```

---

## YA IMPLEMENTADO (se reutiliza del trabajo previo)

- [x] **`version.py`** — `__version__ = "2.0"` (fuente única). + test de formato.
- [x] **`actualizador_core.py`** — `parse_version`, `es_mas_nueva`, `elegir_asset_exe` con tests.
- [x] **Instancia única** en `main()` (`QLockFile`) y versión en el título.
- [x] **Capa Qt base** (`HiloActualizacion`, descarga con verificación de tamaño, diálogo).

Estas piezas no cambian salvo lo indicado en las tareas de pivote siguientes.

---

### Task A: Quitar `construir_bat` del core (ya no hay swap)

**Files:**
- Modify: `EscanerFotos/actualizador_core.py` (eliminar `construir_bat` y `import ntpath`)
- Modify: `tests/test_actualizador_core.py` (eliminar test de `construir_bat`)

- [ ] **Step 1: Borrar el test de construir_bat**

Eliminar de `tests/test_actualizador_core.py` la línea `from actualizador_core import construir_bat`
y la función `test_construir_bat_contiene_piezas_clave` completa.

- [ ] **Step 2: Borrar la función y el import**

En `actualizador_core.py`, eliminar `import ntpath` y la función `construir_bat` completa.
El módulo queda con `import re` y las tres funciones `parse_version`, `es_mas_nueva`,
`elegir_asset_exe`.

- [ ] **Step 3: Run tests**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -v`
Expected: PASS (sin el test de construir_bat).

- [ ] **Step 4: Commit**

```bash
git add EscanerFotos/actualizador_core.py tests/test_actualizador_core.py
git commit -m "refactor: quitar construir_bat (el instalador hace el reemplazo)"
```

---

### Task B: `actualizador.py` lanza el instalador

Sustituye el swap por la ejecución del `Setup.exe`. Cambios concretos en `actualizador.py`:

**Files:**
- Modify: `EscanerFotos/actualizador.py`

- [ ] **Step 1:** En el import del core, quitar `construir_bat`:
`from actualizador_core import es_mas_nueva, elegir_asset_exe`

- [ ] **Step 2:** Eliminar las funciones `carpeta_escribible` y `limpiar_restos`.

- [ ] **Step 3:** En `HiloActualizacion.run`, cambiar el destino de descarga a `%TEMP%`:

```python
            destino = os.path.join(tempfile.gettempdir(), "EscanerFotos-Setup.exe")
            if not self._descargar(asset["browser_download_url"],
                                   destino, asset.get("size")):
                return
            self.encontrada.emit(tag, destino)
```

- [ ] **Step 4:** Reemplazar `_lanzar_ayudante` por `_lanzar_instalador`:

```python
def _lanzar_instalador(ruta_setup):
    """Ejecuta el instalador en silencio. Inno cierra la app, reemplaza y la reabre."""
    subprocess.Popen(
        [ruta_setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        close_fds=True,
    )
```

- [ ] **Step 5:** En `conectar`, simplificar la condición y usar el instalador:

```python
def conectar(ventana, version_local):
    if not esta_empaquetada():
        return

    def al_encontrar(version, ruta_setup):
        resp = QMessageBox.question(
            ventana, "Actualización disponible",
            f"Hay una versión nueva de EscanerFotos ({version}).\n\n"
            "¿Reiniciar e instalarla ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if resp == QMessageBox.StandardButton.Yes:
            _lanzar_instalador(ruta_setup)
            ventana.close()
        else:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().aboutToQuit.connect(
                lambda: _lanzar_instalador(ruta_setup)
            )

    hilo = HiloActualizacion(version_local, parent=ventana)
    hilo.encontrada.connect(al_encontrar)
    hilo.start()
    ventana._hilo_actualizacion = hilo
```

- [ ] **Step 6:** En `escaner_fotos.py` `main()`, eliminar la línea
`actualizador.limpiar_restos()`.

- [ ] **Step 7: Verify**

```bash
python3 -m py_compile EscanerFotos/actualizador.py EscanerFotos/escaner_fotos.py
QT_QPA_PLATFORM=offscreen PYTHONPATH=EscanerFotos .venv/bin/python -c "import actualizador; print('OK')"
PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add EscanerFotos/actualizador.py EscanerFotos/escaner_fotos.py
git commit -m "feat: el updater ejecuta el instalador silencioso (modo instalable)"
```

---

### Task C: `instalador.iss` (Inno Setup)

**Files:**
- Create: `instalador.iss` (raíz del repo)

- [ ] **Step 1: Create the Inno Setup script**

```iss
; Instalador de EscanerFotos (por usuario, sin admin).
; Versión por línea de comandos:  iscc /DMyAppVersion=2.1 instalador.iss
#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif
#define MyAppName "EscanerFotos"
#define MyAppExe "EscanerFotos.exe"

[Setup]
AppId={{8F3A1C2E-5B4D-4E9A-9C7F-2D1E6A8B3F40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\EscanerFotos
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=yes
OutputDir=Output
OutputBaseFilename=EscanerFotos-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "dist\EscanerFotos\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\EscanerFotos"; Filename: "{app}\{#MyAppExe}"
Name: "{userprograms}\EscanerFotos"; Filename: "{app}\{#MyAppExe}"

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Abrir EscanerFotos"; Flags: nowait postinstall
```

- [ ] **Step 2: Commit**

```bash
git add instalador.iss
git commit -m "feat: instalador Inno Setup (por usuario, accesos directos)"
```

---

### Task D: Workflow `--onedir` + Inno + publicar Setup

**Files:**
- Modify: `.github/workflows/build.yml`

- [ ] **Step 1:** Reemplazar el step de compilación (`Compilar ejecutable`, que usa
`--onefile`) por compilación en carpeta:

```yaml
      - name: Compilar (carpeta) con PyInstaller
        run: |
          pyinstaller --onedir --windowed --name "EscanerFotos" --clean `
            --collect-all cv2 `
            EscanerFotos/escaner_fotos.py
```

- [ ] **Step 2:** Sustituir el step de "Subir como artefacto" para que apunte a la carpeta:

```yaml
      - name: Subir carpeta como artefacto (siempre)
        uses: actions/upload-artifact@v4
        with:
          name: EscanerFotos-windows
          path: dist/EscanerFotos
```

- [ ] **Step 3:** Reemplazar el step de Release por construir el instalador y publicarlo:

```yaml
      - name: Construir instalador con Inno Setup (solo en tags)
        if: startsWith(github.ref, 'refs/tags/')
        shell: pwsh
        run: |
          choco install innosetup -y --no-progress
          $v = "${{ github.ref_name }}" -replace '^v',''
          & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=$v instalador.iss

      - name: Publicar Release en EscanerFotos-releases (solo en tags)
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          repository: Soakkk/EscanerFotos-releases
          token: ${{ secrets.RELEASES_TOKEN }}
          files: Output/EscanerFotos-Setup-*.exe
          generate_release_notes: true
```

- [ ] **Step 4: Validate YAML**

```bash
.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/build.yml')); print('YAML OK')"
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: compilar instalador (onedir + Inno) y publicar en releases"
```

---

### Task E: Documentación (`LEEME.md`)

- [ ] Actualizar la sección "Actualizaciones automáticas" de `EscanerFotos/LEEME.md` para
reflejar que ahora es **instalable** (se instala en tu usuario, accesos directos) y que la
primera vez se descarga e instala el `Setup.exe`; después se actualiza solo. Commit
`docs: actualizar a modelo instalable`.

---

## Verificación final (manual, Windows)

1. Secret `RELEASES_TOKEN` configurado.
2. `version.py` a `2.0`, `git tag v2.0`, push → Release con `EscanerFotos-Setup-2.0.exe`.
3. Instalar en un PC. Comprobar accesos directos y que abre.
4. `version.py` a `2.1`, tag `v2.1`, push.
5. Abrir la 2.0: avisa, descarga el Setup, al aceptar se instala y reabre como 2.1.
