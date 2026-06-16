@echo off
chcp 65001 > nul
echo ============================================
echo   Installation de l'Outil STD
echo   Assemblage ingénierie
echo ============================================
echo.

:: Vérifier Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR : Python n'est pas installé ou pas dans le PATH.
    echo Téléchargez Python 3.11+ sur https://python.org
    pause
    exit /b 1
)

echo Installation des dépendances...
pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   Installation terminée avec succès !
    echo   Lancez l'outil avec : lancer.bat
    echo ============================================
) else (
    echo.
    echo ERREUR lors de l'installation des dépendances.
)
pause
