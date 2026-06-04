"""Lógica pura del actualizador. Sin dependencias de Qt ni de red:
se puede importar y probar en cualquier máquina con solo la stdlib."""

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
