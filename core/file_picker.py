"""Sélecteur de fichier natif Windows (renvoie le chemin, pas le contenu)."""
from __future__ import annotations


def choisir_fichier(titre: str = "Sélectionner un fichier",
                    filetypes: list[tuple[str, str]] | None = None,
                    dossier_initial: str | None = None) -> str | None:
    """
    Ouvre la boîte de dialogue Windows de sélection de fichier.
    Retourne le chemin complet du fichier choisi, ou None si annulé.

    Contrairement à st.file_uploader, cette approche transmet uniquement
    le CHEMIN à l'application — le fichier n'est jamais copié ni uploadé,
    donc aucune limite de taille.
    """
    import tkinter as tk
    from tkinter import filedialog

    if filetypes is None:
        filetypes = [("Tous les fichiers", "*.*")]

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)  # boîte de dialogue au premier plan

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
    Ouvre la boîte de dialogue Windows « Enregistrer sous ».
    Retourne le chemin complet choisi, ou None si annulé.
    """
    import tkinter as tk
    from tkinter import filedialog

    if filetypes is None:
        filetypes = [("Tous les fichiers", "*.*")]

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)

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
