"""Régression : le sélecteur de fichier doit lier la boîte de dialogue à un
root Tk créé sur le thread courant (parent=root), et NON au _default_root
global de tkinter — sinon, dans un thread ScriptRunner Streamlit, on obtient
« RuntimeError: main thread is not in main loop ».

On ne crée AUCUN Tk réel (Tcl est instable en headless et la boîte bloque) :
on simule `tk.Tk` et on intercepte l'appel `filedialog` pour vérifier que le
kwarg `parent` reçoit bien notre root.
"""
import tkinter as tk
import tkinter.filedialog as fd

from core import file_picker


import pytest


class _FauxRoot:
    """Root Tk factice : enregistre les méthodes appelées, sans Tcl."""
    def __init__(self): self.geo = None; self.masque = False
    def withdraw(self): self.masque = True
    def wm_attributes(self, *a, **k): pass
    def overrideredirect(self, *a): pass
    def geometry(self, g): self.geo = g
    def update_idletasks(self): pass
    def deiconify(self): pass
    def update(self): pass
    def destroy(self): self.detruit = True


@pytest.fixture(autouse=True)
def _sans_fenetre_app(monkeypatch):
    """Par défaut, aucune fenêtre d'app détectée (tests indépendants du bureau)."""
    monkeypatch.setattr(file_picker, "_ancrage_dialogue", lambda: None)


def test_choisir_fichier_passe_parent_root(monkeypatch):
    faux = _FauxRoot()
    capté = {}
    monkeypatch.setattr(tk, "Tk", lambda: faux)
    monkeypatch.setattr(fd, "askopenfilename",
                        lambda **k: capté.update(k) or "C:/x/projet.stdproj")

    res = file_picker.choisir_fichier("Ouvrir", [("Projet", ".stdproj")])

    assert res == "C:/x/projet.stdproj"
    # parent DOIT être notre root (thread courant), pas le _default_root global
    assert capté.get("parent") is faux
    assert getattr(faux, "detruit", False), "le root doit être détruit (finally)"


def test_enregistrer_fichier_passe_parent_root(monkeypatch):
    faux = _FauxRoot()
    capté = {}
    monkeypatch.setattr(tk, "Tk", lambda: faux)
    monkeypatch.setattr(fd, "asksaveasfilename",
                        lambda **k: capté.update(k) or "C:/x/projet.stdproj")

    res = file_picker.enregistrer_fichier("Enregistrer", [("Projet", ".stdproj")],
                                          extension_defaut=".stdproj")

    assert res == "C:/x/projet.stdproj"
    assert capté.get("parent") is faux


def test_annulation_retourne_none(monkeypatch):
    monkeypatch.setattr(tk, "Tk", lambda: _FauxRoot())
    monkeypatch.setattr(fd, "askopenfilename", lambda **k: "")
    assert file_picker.choisir_fichier("Ouvrir") is None


def test_root_detruit_meme_si_dialogue_leve(monkeypatch):
    """Le root doit être détruit (try/finally) même si la boîte lève."""
    faux = _FauxRoot()
    monkeypatch.setattr(tk, "Tk", lambda: faux)

    def boom(**k):
        raise RuntimeError("main thread is not in main loop")
    monkeypatch.setattr(fd, "askopenfilename", boom)

    with pytest.raises(RuntimeError):
        file_picker.choisir_fichier("Ouvrir")
    assert getattr(faux, "detruit", False)


def test_dialogue_ancre_sur_la_fenetre_app(monkeypatch):
    """La boîte s'ouvre sur l'écran de l'app : root invisible placé dans sa fenêtre
    (et non masqué en (0, 0), c.-à-d. sur l'écran principal)."""
    faux = _FauxRoot()
    monkeypatch.setattr(tk, "Tk", lambda: faux)
    monkeypatch.setattr(file_picker, "_ancrage_dialogue", lambda: (2628, 449))
    monkeypatch.setattr(fd, "askopenfilename", lambda **k: "C:/x/r.csv")
    assert file_picker.choisir_fichier("Ouvrir") == "C:/x/r.csv"
    assert faux.geo == "1x1+2628+449" and not faux.masque


def test_sans_fenetre_app_root_masque(monkeypatch):
    faux = _FauxRoot()
    monkeypatch.setattr(tk, "Tk", lambda: faux)
    monkeypatch.setattr(fd, "asksaveasfilename", lambda **k: "")
    assert file_picker.enregistrer_fichier("Enregistrer") is None
    assert faux.masque and faux.geo is None
