from actualizador_core import parse_version
from actualizador_core import es_mas_nueva

def test_parse_version_con_prefijo_v():
    assert parse_version("v2.1.0") == (2, 1, 0)

def test_parse_version_sin_prefijo():
    assert parse_version("2.1") == (2, 1)

def test_parse_version_un_solo_numero():
    assert parse_version("v3") == (3,)

def test_parse_version_vacia():
    assert parse_version("") == ()
    assert parse_version(None) == ()

def test_es_mas_nueva_mayor():
    assert es_mas_nueva("v2.1", "2.0") is True

def test_es_mas_nueva_igual():
    assert es_mas_nueva("v2.0", "2.0") is False

def test_es_mas_nueva_menor():
    assert es_mas_nueva("v2.0", "2.1") is False

def test_es_mas_nueva_distinto_numero_de_componentes():
    assert es_mas_nueva("v2.1.0", "2.1") is False
    assert es_mas_nueva("v2.1.1", "2.1") is True
