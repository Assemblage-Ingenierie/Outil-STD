"""Régression #7 — cohérence méthode COCO/Givoni.

À l'ouverture d'un projet COCO, `cfg_methode` était restauré ('coco') mais pas
le libellé du radio → au 1er rendu de Réglages, le radio resté sur « Givoni »
réécrasait `cfg_methode` en 'givoni' (diagramme COCO à l'écran mais Réglages sur
Givoni, puis crash au switch). Le correctif restaure aussi `cfg_methode_label`.

On vérifie l'invariant garanti : si le libellé du radio vaut COCO, alors après
rendu de Réglages `cfg_methode` == 'coco' (et réciproquement).
"""
import os
import pytest

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")


def _run(label):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["cfg_methode_label"] = label
    at.session_state["nav_vue"] = "Réglages"
    at.run()
    return at


def test_label_coco_donne_methode_coco():
    at = _run("COCO (tropical)")
    assert not at.exception
    assert at.session_state["cfg_methode"] == "coco"


def test_label_givoni_donne_methode_givoni():
    at = _run("Givoni")
    assert not at.exception
    assert at.session_state["cfg_methode"] == "givoni"


def test_switch_coco_vers_givoni_sans_crash():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["cfg_methode_label"] = "COCO (tropical)"
    at.session_state["nav_vue"] = "Réglages"
    at.run()
    assert not at.exception
    r = next((x for x in at.radio if "bioclimatique" in (x.label or "").lower()), None)
    assert r is not None and r.value == "COCO (tropical)"
    r.set_value("Givoni").run()
    assert not at.exception
    assert at.session_state["cfg_methode"] == "givoni"
