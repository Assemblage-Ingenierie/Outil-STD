@echo off
setlocal

echo ============================================
echo   Outil STD - Assemblage ingenierie
echo ============================================
echo.
echo Demarrage en cours...
echo L'application va s'ouvrir dans votre navigateur.
echo Pour arreter : fermez cette fenetre.
echo.

cd /d "%~dp0"

REM Recherche de Python : py launcher, puis python du PATH
where py >nul 2>&1
if %errorlevel%==0 (
    py -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
    goto :end
)

where python >nul 2>&1
if %errorlevel%==0 (
    python -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
    goto :end
)

echo.
echo ERREUR : Python est introuvable.
echo Lancez d'abord installer.bat ou installez Python depuis https://python.org
echo (cochez "Add Python to PATH" lors de l'installation).

:end
echo.
pause
