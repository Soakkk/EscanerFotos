@echo off
chcp 65001 > nul
title Instalador - Escaner de Fotos
color 0B

echo.
echo ===============================================
echo    Escaner de Fotos - Instalacion
echo ===============================================
echo.

REM Comprobar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado en este equipo.
    echo.
    echo Sigue estos pasos:
    echo   1. Ve a https://www.python.org/downloads/
    echo   2. Descarga la ultima version (Python 3.11 o superior)
    echo   3. Al instalar, MARCA la casilla "Add Python to PATH"
    echo   4. Vuelve a ejecutar este instalador
    echo.
    pause
    exit /b 1
)

echo [OK] Python detectado:
python --version
echo.

echo Actualizando pip...
python -m pip install --upgrade pip --quiet
echo.

echo Instalando librerias (puede tardar 1-3 minutos)...
echo   - PySide6    (interfaz grafica Qt 6)
echo   - OpenCV     (procesado de imagen)
echo   - NumPy      (calculo numerico)
echo   - Pillow     (guardar PDF y PNG)
echo.

python -m pip install --upgrade PySide6 opencv-python numpy Pillow
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la instalacion de librerias.
    echo Revisa tu conexion a internet y vuelve a intentarlo.
    pause
    exit /b 1
)

echo.
echo ===============================================
echo    Instalacion completada correctamente
echo ===============================================
echo.
echo Ya puedes hacer doble clic en "EscanerFotos.bat"
echo para abrir el programa.
echo.
pause
