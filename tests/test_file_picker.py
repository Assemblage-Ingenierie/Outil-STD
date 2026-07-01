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


class _FauxRoot:
    """Root Tk factice : enregistre les méthodes appelées, sans Tcl."""
    def withdraw(self): pass
    def wm_attributes(self, *a, **k): pass
    def destroy(self): self.detruit = True


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

    import pytest
    with pytest.raises(RuntimeError):
        file_picker.choisir_fichier("Ouvrir")
    assert getattr(faux, "detruit", False)
