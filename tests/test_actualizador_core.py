from actualizador_core import parse_version
from actualizador_core import es_mas_nueva
from actualizador_core import elegir_asset_exe

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


from actualizador_core import elegir_asset_sha256, parsear_sha256

def test_elegir_asset_sha256_encuentra_el_hash():
    a = elegir_asset_sha256(
        _release("EscanerFotos.exe", "EscanerFotos-Setup-2.7.exe.sha256"))
    assert a is not None and a["name"].endswith(".sha256")

def test_elegir_asset_sha256_sin_hash_devuelve_none():
    assert elegir_asset_sha256(_release("EscanerFotos.exe")) is None

def test_parsear_sha256_formato_estandar():
    h = "ab" * 32
    assert parsear_sha256(f"{h}  EscanerFotos-Setup-2.7.exe\n") == h

def test_parsear_sha256_mayusculas_y_solo_hash():
    h = "AB" * 32
    assert parsear_sha256(h) == "ab" * 32

def test_parsear_sha256_invalido():
    assert parsear_sha256("no hay hash aqui") is None
    assert parsear_sha256("") is None
    assert parsear_sha256(None) is None
    assert parsear_sha256("abc123") is None

