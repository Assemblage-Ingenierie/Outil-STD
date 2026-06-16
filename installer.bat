@echo off
setlocal

echo ============================================
echo   Installation de l'Outil STD
echo   Assemblage ingenierie
echo ============================================
echo.

cd /d "%~dp0"

REM Recherche de Python : py launcher, puis python du PATH
set PYCMD=
where py >nul 2>&1
if %errorlevel%==0 set PYCMD=py
if not defined PYCMD (
    where python >nul 2>&1
    if %errorlevel%==0 set PYCMD=python
)

if not defined PYCMD (
    echo ERREUR : Python est introuvable.
    echo Telechargez Python 3.11+ sur https://python.org
    echo IMPORTANT : cochez "Add Python to PATH" lors de l'installation.
    pause
    exit /b 1
)

echo Python detecte : %PYCMD%
echo Installation des dependances...
echo.
%PYCMD% -m pip install -r requirements.txt

if %errorlevel%==0 (
    echo.
    echo ============================================
    echo   Installation terminee avec succes !
    echo   Lancez l'outil avec : lancer.bat
    echo ============================================
) else (
    echo.
    echo ERREUR lors de l'installation des dependances.
)
pause
