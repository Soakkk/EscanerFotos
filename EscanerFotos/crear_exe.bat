@echo off
chcp 65001 > nul
title Generar ejecutable EXE
color 0E
cd /d "%~dp0"

echo.
echo ===============================================
echo    Generar ejecutable .exe
echo ===============================================
echo.
echo Convierte el programa en un unico .exe que
echo puedes usar en cualquier PC con Windows sin
echo instalar Python ni librerias.
echo.
echo Peso estimado del .exe: 150-200 MB
echo Tiempo estimado: 3-7 minutos
echo.
pause

echo.
echo [1/3] Instalando/actualizando PyInstaller...
python -m pip install --upgrade pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] No se pudo instalar PyInstaller.
    echo Comprueba tu conexion a internet.
    pause
    exit /b 1
)

echo.
echo [2/3] Generando el ejecutable...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "EscanerFotos" ^
    --clean ^
    --hidden-import="PIL._tkinter_finder" ^
    --collect-all cv2 ^
    escaner_fotos.py

if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la generacion del ejecutable.
    echo Revisa los mensajes de error anteriores.
    pause
    exit /b 1
)

echo.
echo [3/3] Limpiando archivos temporales...
if exist build rmdir /s /q build
if exist EscanerFotos.spec del /q EscanerFotos.spec

echo.
echo ===============================================
echo    LISTO
echo ===============================================
echo.
echo El ejecutable se ha generado en:
echo    dist\EscanerFotos.exe
echo.
echo Puedes copiar ese fichero a cualquier ordenador
echo con Windows (64 bits) sin instalar nada mas.
echo.
pause
