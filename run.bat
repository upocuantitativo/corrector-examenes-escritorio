@echo off
echo Iniciando Sistema de Correccion de Examenes...
python main_app.py
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo iniciar la aplicacion
    echo Verifica que Python este instalado y las dependencias instaladas
    echo Ejecuta install.bat primero si no lo has hecho
    pause
)
