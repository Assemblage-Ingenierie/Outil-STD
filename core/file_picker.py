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

    chemin = filedialog.askopenfilename(
        title=titre,
        filetypes=filetypes,
        initialdir=dossier_initial,
    )
    root.destroy()

    return chemin if chemin else None
