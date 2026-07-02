"""
Bootstrap PyInstaller pour l'Outil STD.

Deux modes dans le MÊME exécutable :
  • LANCEUR (défaut) : ouvre l'appli dans une FENÊTRE NATIVE (pywebview) plutôt
    que dans le navigateur système. Le serveur Streamlit tourne dans un
    sous-processus (le même exe relancé avec OUTIL_STD_RUN_SERVER=1), car
    Streamlit (handlers de signaux) et pywebview (boucle GUI) exigent tous deux
    le thread principal — on les sépare donc en deux processus.
  • SERVEUR (OUTIL_STD_RUN_SERVER=1) : lance Streamlit headless sur le thread
    principal. C'est ce mode qui sert réellement les pages.

Repli sûr : si pywebview est indisponible/échoue (ou OUTIL_STD_NO_WEBVIEW=1),
on retombe sur le comportement éprouvé = serveur Streamlit en intra-processus
+ ouverture du navigateur. Le navigateur reste donc toujours un filet de
sécurité, sans régression par rapport à l'ancienne version.
"""
import sys
import os
import time
import threading
import urllib.request
from pathlib import Path

# Dossier de logs (utile car le terminal est masqué : console=False dans le spec).
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "OutilSTD"


def _journaliser_si_sans_console():
    """Sans console (exe windowed), sys.stdout/stderr valent None en frozen :
    tout print()/logging planterait. On redirige vers un fichier log afin (a)
    d'éviter ces crashs, (b) de garder un diagnostic même sans terminal."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        f = open(LOG_DIR / "outil_std.log", "a", encoding="utf-8", buffering=1)
    except Exception:
        f = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = f
    if sys.stderr is None:
        sys.stderr = f


_journaliser_si_sans_console()

# Adresse loopback EXPLICITE en IPv4 (127.0.0.1) plutôt que « localhost » :
# sur certains postes Windows/entreprise, « localhost » se résout en IPv6 (::1)
# alors que le serveur écoute en IPv4 → ERR_CONNECTION_REFUSED. On neutralise
# aussi un éventuel proxy d'entreprise pour les adresses locales.
HOST = "127.0.0.1"
PORT = 8501
URL = f"http://{HOST}:{PORT}"
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

SERVER_FLAG = "OUTIL_STD_RUN_SERVER"   # =1 → mode serveur
NO_WEBVIEW_FLAG = "OUTIL_STD_NO_WEBVIEW"  # =1 → forcer le navigateur

if getattr(sys, "frozen", False):
    base = Path(sys._MEIPASS)
    os.chdir(base)
else:
    base = Path(__file__).parent

app_file = str(base / "app.py")


def _argv_serveur():
    return [
        "streamlit", "run", app_file,
        "--global.developmentMode=false",
        f"--server.port={PORT}",
        f"--server.address={HOST}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.enableXsrfProtection=false",
        "--client.toolbarMode=minimal",   # masque le bouton « Deploy » + menu dev
    ]


def _lancer_serveur():
    """Mode serveur : Streamlit headless sur le thread principal (ne revient pas)."""
    from streamlit.web import cli as stcli
    sys.argv = _argv_serveur()
    sys.exit(stcli.main())


def _attendre_sante(timeout_s: int = 120) -> bool:
    """Sonde l'endpoint santé jusqu'à ce que le serveur réponde (ou timeout)."""
    sante = f"{URL}/_stcore/health"
    for _ in range(timeout_s * 2):     # pas de 0,5 s
        try:
            with urllib.request.urlopen(sante, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _serveur_inproc_et_navigateur():
    """Chemin HISTORIQUE éprouvé : serveur Streamlit en intra-processus (thread
    principal) + ouverture du navigateur quand la santé répond. Sert de repli."""
    import webbrowser

    def _ouvrir():
        if _attendre_sante():
            webbrowser.open(URL)

    threading.Thread(target=_ouvrir, daemon=True).start()
    try:
        code = _lancer_serveur_retour()
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
        except Exception:
            pass
    sys.exit(code or 0)


def _lancer_serveur_retour():
    """Comme _lancer_serveur mais renvoie le code (au lieu de sys.exit) pour la
    gestion d'erreur du chemin historique."""
    from streamlit.web import cli as stcli
    sys.argv = _argv_serveur()
    return stcli.main()


# ======================================================================
# MODE SERVEUR (sous-processus lancé par le lanceur)
# ======================================================================
if os.environ.get(SERVER_FLAG) == "1":
    _lancer_serveur()
    sys.exit(0)


# ======================================================================
# MODE LANCEUR
# ======================================================================
def _lancer_fenetre_native() -> bool:
    """Tente d'ouvrir l'appli dans une fenêtre native (serveur en sous-processus).
    Renvoie True si la fenêtre native a été utilisée, False s'il faut retomber
    sur le chemin historique (navigateur + serveur intra-processus)."""
    if os.environ.get(NO_WEBVIEW_FLAG) == "1":
        return False
    try:
        import webview  # noqa: F401
    except Exception as e:
        print(f"[Outil STD] pywebview indisponible ({e}) — bascule navigateur.")
        return False

    import subprocess
    env = dict(os.environ)
    env[SERVER_FLAG] = "1"
    cmd = [sys.executable] if getattr(sys, "frozen", False) \
        else [sys.executable, os.path.abspath(__file__)]
    # Sorties du serveur → fichier log (le terminal est masqué) ; pas de fenêtre
    # console pour le processus enfant sous Windows.
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        srv_out = open(LOG_DIR / "outil_std_server.log", "a", encoding="utf-8", buffering=1)
    except Exception:
        srv_out = subprocess.DEVNULL
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        serveur = subprocess.Popen(cmd, env=env, stdout=srv_out, stderr=srv_out,
                                   creationflags=creationflags)
    except Exception as e:
        print(f"[Outil STD] Échec du lancement du serveur ({e}) — bascule navigateur.")
        return False

    try:
        if not _attendre_sante():
            print("[Outil STD] Le serveur n'a pas démarré à temps — bascule navigateur.")
            serveur.terminate()
            return False
        try:
            import webview
            # Sans ceci, pywebview ANNULE silencieusement tout téléchargement
            # (ALLOW_DOWNLOADS=False par défaut) : le bouton 📷 de Plotly et le
            # téléchargement du rapport Word ne produisent rien dans la fenêtre
            # native. Activé → WebView2 ouvre une boîte « Enregistrer sous ».
            webview.settings['ALLOW_DOWNLOADS'] = True
            webview.create_window("Outil STD — Assemblage ingénierie", URL,
                                  width=1400, height=900)
            webview.start()        # bloque jusqu'à fermeture de la fenêtre
        except Exception as e:
            # Fenêtre native KO malgré pywebview importé : ouvrir le navigateur
            # et garder le serveur vivant tant que l'utilisateur s'en sert.
            print(f"[Outil STD] Fenêtre native indisponible ({e}) — ouverture navigateur.")
            import webbrowser
            webbrowser.open(URL)
            serveur.wait()
        return True
    finally:
        try:
            serveur.terminate()
        except Exception:
            pass


if not _lancer_fenetre_native():
    # Repli : comportement historique (serveur intra-processus + navigateur)
    _serveur_inproc_et_navigateur()
sys.exit(0)
