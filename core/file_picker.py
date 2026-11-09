"""Sélecteur de fichier natif Windows (renvoie le chemin, pas le contenu)."""
from __future__ import annotations

# Titre de la fenêtre de l'app (pywebview et onglet navigateur, cf. app.py / run_app.py)
TITRE_APP = "Assemblage STD"
# Taille usuelle de la boîte de dialogue Windows (px) : sert à la centrer sur l'app,
# Windows plaçant son coin haut-gauche sur la fenêtre propriétaire.
TAILLE_DIALOGUE = (960, 540)


def _ancrage_dialogue() -> tuple[int, int] | None:
    """Position (x, y) en pixels écran où ancrer la boîte de dialogue pour
    qu'elle apparaisse centrée sur la fenêtre de l'application.

    La boîte de dialogue est ouverte juste après un clic dans l'app : la fenêtre
    au premier plan est donc celle de l'app (fenêtre native pywebview ou
    navigateur). Si ce n'est pas le cas (titre différent), on cherche la fenêtre
    native par son titre. None hors Windows ou si rien n'est trouvé.
    """
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
    except Exception:
        return None

    def _titre(hwnd) -> str:
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value

    hwnd = user32.GetForegroundWindow()
    if not hwnd or TITRE_APP not in _titre(hwnd):
        trouve = []
        PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _cb(h, _l):
            if user32.IsWindowVisible(h) and TITRE_APP in _titre(h):
                trouve.append(h)
                return False
            return True
        user32.EnumWindows(PROC(_cb), 0)
        hwnd = trouve[0] if trouve else hwnd
    if not hwnd or user32.IsIconic(hwnd):
        return None
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)) or r.right <= r.left:
        return None
    x = (r.left + r.right - TAILLE_DIALOGUE[0]) // 2
    y = (r.top + r.bottom - TAILLE_DIALOGUE[1]) // 2
    return max(r.left, x), max(r.top, y)      # jamais hors de la fenêtre de l'app


def _creer_root():
    """Root Tk propriétaire de la boîte de dialogue.

    Windows ouvre la boîte de dialogue sur l'écran (et près de la position) de sa
    fenêtre propriétaire. Un root simplement masqué (withdraw) reste en (0, 0),
    donc sur l'écran PRINCIPAL. On place plutôt un root invisible de 1 px dans
    la fenêtre de l'app (de sorte que la boîte y soit centrée) : la boîte s'ouvre en superposition de l'app,
    sur l'écran où elle se trouve.
    """
    import tkinter as tk

    root = tk.Tk()
    root.wm_attributes('-topmost', 1)   # boîte de dialogue au premier plan
    ancre = _ancrage_dialogue()
    if ancre is None:
        root.withdraw()
        return root
    try:
        root.overrideredirect(True)          # pas de barre de titre ni d'entrée de barre des tâches
        root.wm_attributes('-alpha', 0.0)    # totalement transparent
        root.geometry(f"1x1+{ancre[0]}+{ancre[1]}")
        root.update_idletasks()
        root.deiconify()
        root.update()
    except Exception:
        root.withdraw()
    return root


def choisir_fichier(titre: str = "Sélectionner un fichier",
                    filetypes: list[tuple[str, str]] | None = None,
                    dossier_initial: str | None = None) -> str | None:
    """
    Ouvre la boîte de dialogue Windows de sélection de fichier, en superposition
    de la fenêtre de l'app. Retourne le chemin complet du fichier choisi, ou None
    si annulé.

    Contrairement à st.file_uploader, cette approche transmet uniquement
    le CHEMIN à l'application — le fichier n'est jamais copié ni uploadé,
    donc aucune limite de taille.
    """
    from tkinter import filedialog

    if filetypes is None:
        filetypes = [("Tous les fichiers", "*.*")]

    root = _creer_root()

    # parent=root est ESSENTIEL : Streamlit exécute chaque rerun dans un thread
    # différent. Sans parent, tkinter retombe sur son _default_root global qui
    # peut pointer sur un Tk créé dans un autre thread -> « main thread is not in
    # main loop ». En liant la boîte à notre root (créé sur CE thread), l'appel
    # Tcl s'exécute sur le thread créateur et l'erreur disparaît.
    try:
        chemin = filedialog.askopenfilename(
            parent=root,
            title=titre,
            filetypes=filetypes,
            initialdir=dossier_initial,
        )
    finally:
        root.destroy()

    return chemin if chemin else None


def enregistrer_fichier(titre: str = "Enregistrer sous",
                        filetypes: list[tuple[str, str]] | None = None,
                        extension_defaut: str = "",
                        nom_defaut: str = "") -> str | None:
    """
    Ouvre la boîte de dialogue Windows « Enregistrer sous », en superposition de
    la fenêtre de l'app. Retourne le chemin complet choisi, ou None si annulé.
    """
    from tkinter import filedialog

    if filetypes is None:
        filetypes = [("Tous les fichiers", "*.*")]

    root = _creer_root()

    # parent=root : voir la note dans choisir_fichier (évite le _default_root
    # global partagé entre threads ScriptRunner -> « main thread is not in main loop »).
    try:
        chemin = filedialog.asksaveasfilename(
            parent=root,
            title=titre,
            filetypes=filetypes,
            defaultextension=extension_defaut,
            initialfile=nom_defaut,
        )
    finally:
        root.destroy()

    return chemin if chemin else None
