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

from streamlit.web import cli as stcli

sys.argv = [
    "streamlit", "run", app_file,
    "--global.developmentMode=false",
    "--server.port=8501",
    "--server.headless=true",
    "--browser.gatherUsageStats=false",
    "--server.enableXsrfProtection=false",
]
sys.exit(stcli.main())
