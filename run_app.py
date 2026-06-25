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
import time
import urllib.request
import webbrowser

PORT = 8501
URL = f"http://localhost:{PORT}"


def _ouvrir_navigateur():
    """Ouvre le navigateur SEULEMENT quand le serveur répond.

    Un délai fixe (ancien comportement : sleep 3 s) provoquait
    ERR_CONNECTION_REFUSED sur les postes où Streamlit met plus longtemps à
    démarrer (1er lancement, scan antivirus du bundle ~292 Mo, machine lente).
    On sonde donc l'endpoint santé jusqu'à 120 s avant d'ouvrir l'onglet.
    """
    sante = f"{URL}/_stcore/health"
    for _ in range(240):            # 240 × 0,5 s = 120 s max
        try:
            with urllib.request.urlopen(sante, timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            pass
        time.sleep(0.5)
    webbrowser.open(URL)


threading.Thread(target=_ouvrir_navigateur, daemon=True).start()

from streamlit.web import cli as stcli

sys.argv = [
    "streamlit", "run", app_file,
    "--global.developmentMode=false",
    f"--server.port={PORT}",
    "--server.address=localhost",
    "--server.headless=true",
    "--browser.gatherUsageStats=false",
    "--server.enableXsrfProtection=false",
]

# Garder la console ouverte si Streamlit plante au démarrage, pour que
# l'utilisateur puisse lire/recopier l'erreur (la fenêtre se fermerait sinon).
try:
    code = stcli.main()
except SystemExit as e:
    code = e.code
except Exception:
    import traceback
    traceback.print_exc()
    code = 1
if code:
    try:
        input("\n[Outil STD] Une erreur est survenue ci-dessus. "
              "Appuyez sur Entrée pour fermer cette fenêtre...")
    except EOFError:
        pass
sys.exit(code or 0)
