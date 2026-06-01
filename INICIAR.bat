@echo off
title Sistema de Correccion de Examenes
color 0A
cls

echo ================================================
echo   SISTEMA DE CORRECCION DE EXAMENES
echo   Reconocimiento automatico con camara
echo ================================================
echo.

:: Verificar que Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo.
    echo Descarga Python desde: https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

:: Mostrar version de Python
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo Python detectado: %PYVER%

:: Verificar que las dependencias estan instaladas
echo Verificando dependencias...
python -c "import cv2, numpy, PIL, openpyxl" >nul 2>&1
if errorlevel 1 (
    color 0E
    echo.
    echo AVISO: Faltan dependencias. Instalando ahora...
    echo.
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        color 0C
        echo.
        echo ERROR: No se pudieron instalar las dependencias.
        echo Ejecuta manualmente: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    color 0A
    echo.
    echo Dependencias instaladas correctamente.
)

echo Dependencias OK.
echo.
echo Iniciando aplicacion...
echo.

:: Iniciar la aplicacion
python main_app.py

:: Si hubo error al cerrar
if errorlevel 1 (
    color 0C
    echo.
    echo La aplicacion cerro con un error.
    echo Revisa los mensajes anteriores para mas informacion.
    echo.
    pause
)
