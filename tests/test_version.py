import re
from version import __version__

def test_version_es_str_con_formato_numerico():
    assert isinstance(__version__, str)
    assert re.match(r"^\d+(\.\d+)*$", __version__), f"formato inesperado: {__version__}"
