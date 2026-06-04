# Auto-actualización (portable) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que EscanerFotos (un `.exe` portable) detecte versiones nuevas en GitHub Releases, las descargue y se reemplace a sí mismo, avisando al usuario.

**Architecture:** Lógica pura aislada en `actualizador_core.py` (versiones, selección de asset, generación del `.bat` de reemplazo), testeable sin Qt. Una capa Qt (`actualizador.py`) hace la comprobación en un hilo, descarga el `.exe` nuevo al lado del actual y, tras confirmación del usuario, lanza un `.bat` que espera a que el proceso muera, intercambia el `.exe` y reabre la app. `escaner_fotos.py` integra instancia única, limpieza de restos y el disparo de la comprobación.

**Tech Stack:** Python 3.12, PySide6 (Qt6), urllib (stdlib), PyInstaller `--onefile`, GitHub Actions, pytest (solo dev).

**Repos:** código en `Soakkk/EscanerFotos`; releases en `Soakkk/EscanerFotos-releases`.

---

## Preparación del entorno de tests (una vez)

Las funciones de `actualizador_core.py` solo usan la stdlib, así que se prueban con un
venv mínimo (sin cv2/PySide6).

```bash
cd <repo>
python3 -m venv .venv
.venv/bin/pip install pytest
echo ".venv/" >> .gitignore
```

Los tests se ejecutan siempre con la carpeta `EscanerFotos` en el path:

```bash
PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -v
```

---

### Task 1: Versión única (`version.py`)

**Files:**
- Create: `EscanerFotos/version.py`
- Test: `tests/test_version.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_version.py
import re
from version import __version__

def test_version_es_str_con_formato_numerico():
    assert isinstance(__version__, str)
    assert re.match(r"^\d+(\.\d+)*$", __version__), f"formato inesperado: {__version__}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_version.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'version'`

- [ ] **Step 3: Create the module**

```python
# EscanerFotos/version.py
"""Única fuente de verdad de la versión de la app.
Súbela aquí antes de crear el tag git (p. ej. 2.0 -> 2.1) y luego:
    git commit -am "v2.1" && git tag v2.1 && git push --tags
"""

__version__ = "2.0"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_version.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add EscanerFotos/version.py tests/test_version.py .gitignore
git commit -m "feat: version.py como fuente única de versión"
```

---

### Task 2: `parse_version` (lógica pura)

**Files:**
- Create: `EscanerFotos/actualizador_core.py`
- Test: `tests/test_actualizador_core.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_actualizador_core.py
from actualizador_core import parse_version

def test_parse_version_con_prefijo_v():
    assert parse_version("v2.1.0") == (2, 1, 0)

def test_parse_version_sin_prefijo():
    assert parse_version("2.1") == (2, 1)

def test_parse_version_un_solo_numero():
    assert parse_version("v3") == (3,)

def test_parse_version_vacia():
    assert parse_version("") == ()
    assert parse_version(None) == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_actualizador_core.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'actualizador_core'`

- [ ] **Step 3: Write minimal implementation**

```python
# EscanerFotos/actualizador_core.py
"""Lógica pura del actualizador. Sin dependencias de Qt ni de red:
se puede importar y probar en cualquier máquina con solo la stdlib."""

import os
import re


def parse_version(texto):
    """'v2.1.0' o '2.1' -> (2, 1, 0). Ignora la 'v' y cualquier sufijo no numérico."""
    nums = re.findall(r"\d+", texto or "")
    return tuple(int(n) for n in nums)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_actualizador_core.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add EscanerFotos/actualizador_core.py tests/test_actualizador_core.py
git commit -m "feat: parse_version en actualizador_core"
```

---

### Task 3: `es_mas_nueva` (comparación de versiones)

**Files:**
- Modify: `EscanerFotos/actualizador_core.py`
- Test: `tests/test_actualizador_core.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/test_actualizador_core.py  (añadir)
from actualizador_core import es_mas_nueva

def test_es_mas_nueva_mayor():
    assert es_mas_nueva("v2.1", "2.0") is True

def test_es_mas_nueva_igual():
    assert es_mas_nueva("v2.0", "2.0") is False

def test_es_mas_nueva_menor():
    assert es_mas_nueva("v2.0", "2.1") is False

def test_es_mas_nueva_distinto_numero_de_componentes():
    assert es_mas_nueva("v2.1.0", "2.1") is False   # iguales con padding
    assert es_mas_nueva("v2.1.1", "2.1") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_actualizador_core.py -k es_mas_nueva -v`
Expected: FAIL con `ImportError: cannot import name 'es_mas_nueva'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# EscanerFotos/actualizador_core.py  (añadir)
def es_mas_nueva(remota, local):
    """True si la versión remota es estrictamente mayor que la local."""
    a = parse_version(remota)
    b = parse_version(local)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return a > b
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_actualizador_core.py -k es_mas_nueva -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add EscanerFotos/actualizador_core.py tests/test_actualizador_core.py
git commit -m "feat: es_mas_nueva (comparación con padding)"
```

---

### Task 4: `elegir_asset_exe` (selección del instalable)

**Files:**
- Modify: `EscanerFotos/actualizador_core.py`
- Test: `tests/test_actualizador_core.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/test_actualizador_core.py  (añadir)
from actualizador_core import elegir_asset_exe

def _release(*nombres):
    return {"assets": [{"name": n, "browser_download_url": "http://x/" + n,
                        "size": 10} for n in nombres]}

def test_elegir_asset_exe_encuentra_el_exe():
    a = elegir_asset_exe(_release("notas.txt", "EscanerFotos.exe"))
    assert a is not None and a["name"] == "EscanerFotos.exe"

def test_elegir_asset_exe_sin_exe_devuelve_none():
    assert elegir_asset_exe(_release("LEEME.txt")) is None

def test_elegir_asset_exe_release_vacia():
    assert elegir_asset_exe({}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_actualizador_core.py -k asset -v`
Expected: FAIL con `ImportError: cannot import name 'elegir_asset_exe'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# EscanerFotos/actualizador_core.py  (añadir)
def elegir_asset_exe(release):
    """Devuelve el primer asset cuyo nombre acabe en .exe, o None."""
    for asset in (release or {}).get("assets", []):
        if str(asset.get("name", "")).lower().endswith(".exe"):
            return asset
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_actualizador_core.py -k asset -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add EscanerFotos/actualizador_core.py tests/test_actualizador_core.py
git commit -m "feat: elegir_asset_exe"
```

---

### Task 5: `construir_bat` (ayudante de reemplazo)

**Files:**
- Modify: `EscanerFotos/actualizador_core.py`
- Test: `tests/test_actualizador_core.py`

El `.bat` espera a que el PID de la app muera (con `tasklist`), luego renombra el `.exe`
actual a `.old`, mueve el descargado a su sitio, reabre la app, borra el `.old` y se
autoelimina. Todas las rutas se incrustan entre comillas.

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/test_actualizador_core.py  (añadir)
from actualizador_core import construir_bat

def test_construir_bat_contiene_piezas_clave():
    exe = r"C:\Users\u\Desktop\EscanerFotos.exe"
    nuevo = r"C:\Users\u\Desktop\EscanerFotos.exe.new"
    bat = construir_bat(exe, nuevo, pid=4321)
    # espera a que muera el PID de la app
    assert "PID eq 4321" in bat
    # renombra el viejo, coloca el nuevo y reabre
    assert '"EscanerFotos.exe" "EscanerFotos.exe.old"' in bat
    assert '"EscanerFotos.exe.new" "EscanerFotos.exe"' in bat
    assert 'start "" "EscanerFotos.exe"' in bat
    # trabaja en la carpeta del exe y se autoelimina
    assert r'cd /d "C:\Users\u\Desktop"' in bat
    assert 'del "%~f0"' in bat
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_actualizador_core.py -k construir_bat -v`
Expected: FAIL con `ImportError: cannot import name 'construir_bat'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# EscanerFotos/actualizador_core.py  (añadir)
def construir_bat(ruta_exe, ruta_nueva, pid):
    """
    Genera el contenido del .bat que intercambia el .exe portable:
      1) espera a que el proceso `pid` (la app) termine,
      2) renombra el .exe actual a .old, mueve el descargado a su sitio,
      3) reabre la app, borra el .old y se autoelimina.
    Las rutas se manejan por nombre dentro de la carpeta del .exe.
    """
    carpeta = os.path.dirname(ruta_exe)
    nombre = os.path.basename(ruta_exe)
    viejo = nombre + ".old"
    nueva = os.path.basename(ruta_nueva)
    return (
        "@echo off\r\n"
        "chcp 65001 > nul\r\n"
        ":waitpid\r\n"
        f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  ping -n 2 127.0.0.1 >nul\r\n"
        "  goto waitpid\r\n"
        ")\r\n"
        f'cd /d "{carpeta}"\r\n'
        f'move /Y "{nombre}" "{viejo}" >nul 2>&1\r\n'
        f'move /Y "{nueva}" "{nombre}" >nul\r\n'
        f'del "{viejo}" >nul 2>&1\r\n'
        f'start "" "{nombre}"\r\n'
        'del "%~f0" >nul 2>&1\r\n'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/test_actualizador_core.py -k construir_bat -v`
Expected: PASS

- [ ] **Step 5: Run the FULL core suite**

Run: `PYTHONPATH=EscanerFotos .venv/bin/python -m pytest tests/ -v`
Expected: PASS (todos: version + core)

- [ ] **Step 6: Commit**

```bash
git add EscanerFotos/actualizador_core.py tests/test_actualizador_core.py
git commit -m "feat: construir_bat (ayudante de reemplazo del exe)"
```

---

### Task 6: Capa Qt del actualizador (`actualizador.py`)

No es testeable automáticamente en Mac (usa Qt, red y `subprocess` de Windows). La
verificación es: (a) compila, (b) importa en un venv con PySide6, (c) prueba manual real
en Windows. La lógica delicada ya está cubierta por los tests del core.

**Files:**
- Create: `EscanerFotos/actualizador.py`

- [ ] **Step 1: Create the module**

```python
# EscanerFotos/actualizador.py
"""Capa Qt del actualizador: comprueba GitHub Releases en un hilo, descarga el
.exe nuevo junto al actual y, tras confirmación, lanza el .bat de reemplazo."""

import os
import sys
import json
import tempfile
import subprocess
from urllib.request import urlopen, Request

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox

from actualizador_core import es_mas_nueva, elegir_asset_exe, construir_bat

API_URL = "https://api.github.com/repos/Soakkk/EscanerFotos-releases/releases/latest"


def esta_empaquetada():
    """True solo cuando corre como .exe de PyInstaller (no en desarrollo)."""
    return getattr(sys, "frozen", False)


def ruta_exe():
    """Ruta absoluta del .exe en ejecución."""
    return sys.executable


def carpeta_escribible():
    """True si se puede escribir junto al .exe (necesario para autoactualizar)."""
    try:
        prueba = ruta_exe() + ".wtest"
        with open(prueba, "w") as f:
            f.write("x")
        os.remove(prueba)
        return True
    except Exception:
        return False


def limpiar_restos():
    """Borra archivos sobrantes de una actualización previa (.old / .new)."""
    for sufijo in (".old", ".new"):
        try:
            p = ruta_exe() + sufijo
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


class HiloActualizacion(QThread):
    """Comprueba y descarga en segundo plano. Emite (version, ruta_new) si hay update."""
    encontrada = Signal(str, str)

    def __init__(self, version_local, parent=None):
        super().__init__(parent)
        self.version_local = version_local

    def run(self):
        try:
            req = Request(API_URL, headers={"User-Agent": "EscanerFotos"})
            with urlopen(req, timeout=15) as r:
                release = json.loads(r.read().decode("utf-8"))

            tag = release.get("tag_name", "")
            if not es_mas_nueva(tag, self.version_local):
                return

            asset = elegir_asset_exe(release)
            if not asset:
                return

            destino = ruta_exe() + ".new"
            if not self._descargar(asset["browser_download_url"],
                                   destino, asset.get("size")):
                return

            self.encontrada.emit(tag, destino)
        except Exception:
            pass  # sin internet / error -> silencio

    def _descargar(self, url, destino, tam_esperado):
        try:
            req = Request(url, headers={"User-Agent": "EscanerFotos"})
            with urlopen(req, timeout=60) as r, open(destino, "wb") as f:
                while True:
                    trozo = r.read(1024 * 256)
                    if not trozo:
                        break
                    f.write(trozo)
            if tam_esperado and os.path.getsize(destino) != tam_esperado:
                os.remove(destino)
                return False
            return True
        except Exception:
            try:
                os.remove(destino)
            except Exception:
                pass
            return False


def _lanzar_ayudante(ruta_new):
    """Escribe el .bat y lo lanza como proceso independiente."""
    contenido = construir_bat(ruta_exe(), ruta_new, os.getpid())
    bat = os.path.join(tempfile.gettempdir(), "escaner_update.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(contenido)
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(
        ["cmd", "/c", bat],
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def conectar(ventana, version_local):
    """Punto de entrada: arranca la comprobación si procede y cablea el diálogo.
    Llamar una vez tras mostrar la ventana principal."""
    if not esta_empaquetada() or not carpeta_escribible():
        return

    def al_encontrar(version, ruta_new):
        resp = QMessageBox.question(
            ventana, "Actualización disponible",
            f"Hay una versión nueva de EscanerFotos ({version}).\n\n"
            "¿Reiniciar e instalarla ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if resp == QMessageBox.StandardButton.Yes:
            _lanzar_ayudante(ruta_new)
            ventana.close()
        else:
            # Instalar al cerrar la app (equivalente a autoInstallOnAppQuit).
            from PySide6.QtWidgets import QApplication
            QApplication.instance().aboutToQuit.connect(
                lambda: _lanzar_ayudante(ruta_new)
            )

    hilo = HiloActualizacion(version_local, parent=ventana)
    hilo.encontrada.connect(al_encontrar)
    hilo.start()
    ventana._hilo_actualizacion = hilo  # evita que el GC lo recoja
```

- [ ] **Step 2: Verify it compiles**

Run: `python3 -m py_compile EscanerFotos/actualizador.py`
Expected: sin salida (OK)

- [ ] **Step 3: Verify it imports (venv con PySide6)**

```bash
.venv/bin/pip install PySide6
QT_QPA_PLATFORM=offscreen PYTHONPATH=EscanerFotos .venv/bin/python -c "import actualizador; print('import OK', actualizador.API_URL)"
```
Expected: `import OK https://api.github.com/repos/Soakkk/EscanerFotos-releases/releases/latest`

- [ ] **Step 4: Commit**

```bash
git add EscanerFotos/actualizador.py
git commit -m "feat: capa Qt del actualizador (comprobación, descarga, diálogo)"
```

---

### Task 7: Integrar en la app (`escaner_fotos.py`)

Añade: import de versión, instancia única, limpieza de restos, versión en el título y el
disparo de la comprobación tras mostrar la ventana.

**Files:**
- Modify: `EscanerFotos/escaner_fotos.py` (imports, `__init__` del título, `main()`)

- [ ] **Step 1: Add imports near the top**

Tras `from PySide6.QtCore import Qt, Signal, QSettings, QTimer` añadir:

```python
from PySide6.QtCore import QLockFile, QStandardPaths
from version import __version__
import actualizador
```

- [ ] **Step 2: Show version in the window title**

En `VentanaPrincipal.__init__`, sustituir:

```python
        self.setWindowTitle("Escáner de Fotos v2 — Documentos limpios desde el móvil")
```

por:

```python
        self.setWindowTitle(f"Escáner de Fotos v{__version__} — Documentos limpios desde el móvil")
```

- [ ] **Step 3: Update `main()` with single-instance + updater wiring**

Sustituir la función `main()` completa por:

```python
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Instancia única: evita dos copias abiertas que bloqueen el .exe al actualizar.
    ruta_lock = os.path.join(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation),
        "EscanerFotos.lock",
    )
    lock = QLockFile(ruta_lock)
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(
            None, "Ya está abierto",
            "EscanerFotos ya se está ejecutando."
        )
        return

    actualizador.limpiar_restos()

    ventana = VentanaPrincipal()
    ventana.show()

    # Comprobar actualizaciones poco después de abrir (no bloquea el arranque).
    QTimer.singleShot(1500, lambda: actualizador.conectar(ventana, __version__))

    sys.exit(app.exec())
```

- [ ] **Step 4: Verify it compiles**

Run: `python3 -m py_compile EscanerFotos/escaner_fotos.py`
Expected: sin salida (OK)

- [ ] **Step 5: Smoke test offscreen (venv completo)**

```bash
.venv/bin/pip install opencv-python-headless numpy Pillow PySide6
QT_QPA_PLATFORM=offscreen PYTHONPATH=EscanerFotos .venv/bin/python -c "
import escaner_fotos as ef
from PySide6.QtWidgets import QApplication
app = QApplication([])
v = ef.VentanaPrincipal()
assert 'v2.0' in v.windowTitle()
print('arranque OK:', v.windowTitle())
"
```
Expected: `arranque OK: Escáner de Fotos v2.0 — ...`

- [ ] **Step 6: Commit**

```bash
git add EscanerFotos/escaner_fotos.py
git commit -m "feat: instancia única + disparo del actualizador + versión en título"
```

---

### Task 8: Publicar releases en el repo separado (CI)

Cambia el workflow para que la Release con el `.exe` se publique en
`Soakkk/EscanerFotos-releases` usando un PAT.

**Files:**
- Modify: `.github/workflows/build.yml` (último step)

- [ ] **Step 1: Replace the release step**

Sustituir el step `Publicar Release con el .exe (solo en tags)` por:

```yaml
      - name: Publicar Release en el repo de releases (solo en tags)
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          repository: Soakkk/EscanerFotos-releases
          token: ${{ secrets.RELEASES_TOKEN }}
          files: dist/EscanerFotos.exe
          generate_release_notes: true
```

- [ ] **Step 2: Validate YAML syntax**

```bash
.venv/bin/pip install pyyaml
.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/build.yml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: publicar releases en EscanerFotos-releases con PAT"
```

---

### Task 9: Documentar updates y setup (`LEEME.md`)

**Files:**
- Modify: `EscanerFotos/LEEME.md`

- [ ] **Step 1: Append the update section**

Añadir al final de `EscanerFotos/LEEME.md`:

```markdown

## Actualizaciones automáticas

EscanerFotos se actualiza solo desde GitHub. Al abrir la app, si hay una versión más
nueva, te avisa con **"Reiniciar e instalar / Más tarde"** y se reemplaza sola.

**Importante:** guarda `EscanerFotos.exe` en una carpeta tuya (Escritorio, Documentos o
una carpeta propia). Si está en `Archivos de programa`, Windows no le deja actualizarse
sin permisos de administrador.

### Publicar una versión nueva (desarrollador)
1. Sube el número en `EscanerFotos/version.py` (p. ej. `2.0` -> `2.1`).
2. `git commit -am "v2.1"` y `git tag v2.1` y `git push --tags`.
3. GitHub Actions compila el `.exe` y publica la Release en `EscanerFotos-releases`.
   Los PCs se actualizan solos al abrir.

### Configuración inicial (una sola vez)
- Repo `Soakkk/EscanerFotos-releases` creado con un `README`.
- Secret `RELEASES_TOKEN` (Personal Access Token con permiso de escritura sobre
  `EscanerFotos-releases`) configurado en `Soakkk/EscanerFotos`.
- La primera versión se coloca a mano (descargar el primer `.exe` de la Release).
```

- [ ] **Step 2: Commit**

```bash
git add EscanerFotos/LEEME.md
git commit -m "docs: explicar actualizaciones automáticas y setup"
```

---

## Verificación final (manual, en Windows)

No se puede automatizar desde Mac. Tras desplegar:

1. Crear `Soakkk/EscanerFotos-releases` con README y el secret `RELEASES_TOKEN`.
2. Subir `version.py` a `2.0`, `git tag v2.0`, `push --tags`. Comprobar que la Release
   aparece en `EscanerFotos-releases` con `EscanerFotos.exe`.
3. Descargar ese `.exe` a una carpeta del usuario en un PC Windows y abrirlo.
4. Subir `version.py` a `2.1`, taggear `v2.1`, push.
5. Reabrir el `.exe` viejo (2.0): debe avisar de la 2.1, descargar, y al aceptar
   reemplazarse y reabrirse mostrando `v2.1` en el título.
6. Comprobar que no quedan `EscanerFotos.exe.old` ni `.new` en la carpeta.

---

## Self-review (cobertura del spec)

- §"Empaquetado" (mantener onefile) → sin cambios de build (Task 8 conserva PyInstaller `--onefile`). ✓
- §"Updater" (comprobar, descargar, verificar tamaño, diálogo, instalar al cerrar) → Tasks 6. ✓
- §"Ayudante de reemplazo" (.bat, espera PID, renombrar/mover/relanzar/autoborrado) → Tasks 5 (lógica+tests) y 6 (lanzamiento). ✓
- §"Versionado" (version.py, comparación con padding) → Tasks 1, 3. ✓
- §"Defensas" (instancia única, renombrar no sobrescribir, reintentos, verificación descarga, carpeta escribible, limpieza restos) → Tasks 5, 6, 7. ✓
- §"CI/CD" (publicar en repo separado con PAT) → Task 8. ✓
- §"Setup manual" y §"Flujo de publicación" → Task 9 (documentado). ✓
- §"Pruebas" (lógica pura con TDD; manual en Windows) → Tasks 2-5 (auto) + Verificación final. ✓

Sin placeholders. Nombres consistentes entre tareas (`parse_version`, `es_mas_nueva`,
`elegir_asset_exe`, `construir_bat`, `conectar`, `limpiar_restos`, `ruta_exe`).
