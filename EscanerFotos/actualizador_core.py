"""Lógica pura del actualizador. Sin dependencias de Qt ni de red:
se puede importar y probar en cualquier máquina con solo la stdlib."""

import os
import re


def parse_version(texto):
    """'v2.1.0' o '2.1' -> (2, 1, 0). Ignora la 'v' y cualquier sufijo no numérico."""
    nums = re.findall(r"\d+", texto or "")
    return tuple(int(n) for n in nums)
