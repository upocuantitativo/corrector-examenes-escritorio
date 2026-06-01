@echo off
echo ========================================
echo Sistema de Correccion de Examenes
echo Instalador para Windows
echo ========================================
echo.

REM Verificar Python
echo [1/4] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en el PATH
    echo Por favor, instala Python 3.8 o superior desde python.org
    pause
    exit /b 1
)
echo Python encontrado!
echo.

REM Instalar dependencias
echo [2/4] Instalando dependencias de Python...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)
echo Dependencias instaladas!
echo.

REM Verificar Tesseract
echo [3/4] Verificando Tesseract OCR...
tesseract --version >nul 2>&1
if errorlevel 1 (
    echo ADVERTENCIA: Tesseract no esta instalado o no esta en el PATH
    echo.
    echo Para el Modo 2 (cuadricula con numeros), necesitas instalar Tesseract:
    echo 1. Descarga desde: https://github.com/UB-Mannheim/tesseract/wiki
    echo 2. Instala en C:\Program Files\Tesseract-OCR
    echo 3. Agrega al PATH del sistema
    echo.
    echo Puedes usar el Modo 1 (simbolos) sin Tesseract.
    echo.
) else (
    echo Tesseract encontrado!
)
echo.

REM Crear archivo de configuración inicial
echo [4/4] Configurando aplicacion...
if not exist "exams.db" (
    echo Base de datos se creara al primer uso.
)
echo.

echo ========================================
echo INSTALACION COMPLETADA!
echo ========================================
echo.
echo Para iniciar la aplicacion, ejecuta:
echo     python main_app.py
echo.
echo O simplemente haz doble clic en: run.bat
echo.
pause
