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
