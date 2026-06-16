@echo off
chcp 65001 > nul
echo Démarrage de l'Outil STD...
echo L'application va s'ouvrir dans votre navigateur.
echo Pour arrêter : fermer cette fenêtre ou appuyer sur Ctrl+C
echo.
streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
pause
