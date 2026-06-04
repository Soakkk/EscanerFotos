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
