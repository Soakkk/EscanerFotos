@echo off
chcp 65001 > nul
cd /d "%~dp0"

REM Comprobar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python no esta instalado.
    echo Ejecuta primero "instalar.bat".
    echo.
    pause
    exit /b 1
)

REM Lanzar sin ventana de consola
pythonw escaner_fotos.py
if errorlevel 1 (
    echo.
    echo [ERROR] El programa no arranco correctamente.
    echo Relanzando con consola para ver el error...
    echo.
    python escaner_fotos.py
    echo.
    echo Si ves un error de modulo no encontrado,
    echo ejecuta "instalar.bat" para reinstalar las librerias.
    echo.
    pause
)
