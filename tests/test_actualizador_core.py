from actualizador_core import parse_version
from actualizador_core import es_mas_nueva
from actualizador_core import elegir_asset_exe
from actualizador_core import construir_bat

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

def test_construir_bat_contiene_piezas_clave():
    exe = r"C:\Users\u\Desktop\EscanerFotos.exe"
    nuevo = r"C:\Users\u\Desktop\EscanerFotos.exe.new"
    bat = construir_bat(exe, nuevo, pid=4321)
    assert "PID eq 4321" in bat
    assert '"EscanerFotos.exe" "EscanerFotos.exe.old"' in bat
    assert '"EscanerFotos.exe.new" "EscanerFotos.exe"' in bat
    assert 'start "" "EscanerFotos.exe"' in bat
    assert r'cd /d "C:\Users\u\Desktop"' in bat
    assert 'del "%~f0"' in bat
