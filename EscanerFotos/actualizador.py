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

from actualizador_core import es_mas_nueva, elegir_asset_exe

API_URL = "https://api.github.com/repos/Soakkk/EscanerFotos-releases/releases/latest"


def esta_empaquetada():
    """True solo cuando corre como .exe de PyInstaller (no en desarrollo)."""
    return getattr(sys, "frozen", False)




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

            destino = os.path.join(tempfile.gettempdir(), "EscanerFotos-Setup.exe")
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


def _lanzar_instalador(ruta_setup):
    """Ejecuta el instalador en silencio. Inno cierra la app, reemplaza y la reabre."""
    subprocess.Popen(
        [ruta_setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        close_fds=True,
    )


def conectar(ventana, version_local):
    """Punto de entrada: arranca la comprobación si procede y cablea el diálogo.
    Llamar una vez tras mostrar la ventana principal."""
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
            # Instalar al cerrar la app (equivalente a autoInstallOnAppQuit).
            from PySide6.QtWidgets import QApplication
            QApplication.instance().aboutToQuit.connect(
                lambda: _lanzar_instalador(ruta_setup)
            )

    hilo = HiloActualizacion(version_local, parent=ventana)
    hilo.encontrada.connect(al_encontrar)
    hilo.start()
    ventana._hilo_actualizacion = hilo  # evita que el GC lo recoja
