"""Lógica pura del actualizador. Sin dependencias de Qt ni de red:
se puede importar y probar en cualquier máquina con solo la stdlib."""

import ntpath
import os
import re


def parse_version(texto):
    """'v2.1.0' o '2.1' -> (2, 1, 0). Ignora la 'v' y cualquier sufijo no numérico."""
    nums = re.findall(r"\d+", texto or "")
    return tuple(int(n) for n in nums)


def es_mas_nueva(remota, local):
    """True si la versión remota es estrictamente mayor que la local."""
    a = parse_version(remota)
    b = parse_version(local)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return a > b


def elegir_asset_exe(release):
    """Devuelve el primer asset cuyo nombre acabe en .exe, o None."""
    for asset in (release or {}).get("assets", []):
        if str(asset.get("name", "")).lower().endswith(".exe"):
            return asset
    return None


def construir_bat(ruta_exe, ruta_nueva, pid):
    """
    Genera el contenido del .bat que intercambia el .exe portable:
      1) espera a que el proceso `pid` (la app) termine,
      2) renombra el .exe actual a .old, mueve el descargado a su sitio,
      3) reabre la app, borra el .old y se autoelimina.
    Las rutas se manejan por nombre dentro de la carpeta del .exe.
    """
    carpeta = ntpath.dirname(ruta_exe)
    nombre = ntpath.basename(ruta_exe)
    viejo = nombre + ".old"
    nueva = ntpath.basename(ruta_nueva)
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
