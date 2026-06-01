@echo off
REM Lanzador del Corrector de Examenes TIPO TEST (version escritorio)
cd /d "%~dp0"
python corrector_test_gui.py
if errorlevel 1 (
  echo.
  echo Si ha fallado, instala las dependencias:
  echo    pip install pillow numpy
  pause
)
