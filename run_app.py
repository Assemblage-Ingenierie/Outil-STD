"""
Bootstrap PyInstaller pour l'Outil STD.
Lance Streamlit sur l'app.py embarquée dans le bundle.
"""
import sys
import os
from pathlib import Path

if getattr(sys, "frozen", False):
    base = Path(sys._MEIPASS)
    os.chdir(base)
else:
    base = Path(__file__).parent

app_file = str(base / "app.py")

import threading
import webbrowser
import time

def _ouvrir_navigateur():
    time.sleep(3)
    webbrowser.open("http://localhost:8501")

threading.Thread(target=_ouvrir_navigateur, daemon=True).start()

from streamlit.web import cli as stcli

sys.argv = [
    "streamlit", "run", app_file,
    "--global.developmentMode=false",
    "--server.port=8501",
    "--server.address=localhost",
    "--server.headless=true",
    "--browser.gatherUsageStats=false",
    "--server.enableXsrfProtection=false",
]
sys.exit(stcli.main())
