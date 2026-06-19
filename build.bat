@echo off
setlocal

echo ============================================
echo   Outil STD - Build PyInstaller
echo   Assemblage ingenierie
echo ============================================
echo.

cd /d "%~dp0"

REM --- Verifier Python ---
where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=py
    goto :check_pyinstaller
)
where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON=python
    goto :check_pyinstaller
)
echo ERREUR : Python introuvable. Lancez installer.bat d'abord.
pause
exit /b 1

:check_pyinstaller
echo [1/4] Verification des dependances de build...
%PYTHON% -m pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERREUR : Impossible d'installer PyInstaller.
    pause
    exit /b 1
)

echo [2/4] Installation des dependances de l'application...
%PYTHON% -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERREUR : Impossible d'installer les dependances.
    pause
    exit /b 1
)

echo [3/4] Nettoyage des anciens builds...
if exist "dist\OuiSTD" rmdir /s /q "dist\OuiSTD"
if exist "build\OuiSTD"  rmdir /s /q "build\OuiSTD"

echo [4/4] Build PyInstaller (--onedir)...
%PYTHON% -m PyInstaller outil_std.spec --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo ERREUR : Le build a echoue. Voir les messages ci-dessus.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build termine avec succes !
echo   Executable : dist\OuiSTD\OuiSTD.exe
echo.
echo   NOTE : A la premiere utilisation de l'export Word,
echo   kaleido telecharge automatiquement Chrome (~150 Mo).
echo   Besoin d'une connexion internet pour ce premier lancement.
echo ============================================
echo.
pause
