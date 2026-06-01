@echo off
REM Deja este archivo en la carpeta de un proyecto y haz doble clic.
REM Levanta un contenedor pace-<carpeta> con Claude Code autenticado y el proyecto montado.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.claude\pacing\docker\pace-up.ps1" -ProjectDir "%~dp0."
echo.
pause
