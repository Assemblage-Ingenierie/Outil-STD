"""Tests du lot d'améliorations UI :
- nom de fichier de snapshot = titre du graphique (plotly_config)
- vitesse d'air dans la légende COCO + annotations sur le diagramme
- séparateur décimal virgule dans le rapport Word (format_fr)
"""
import os
import re
import numpy as np
import pytest
import config.charte as charte
from core import confort
from charts.givoni import creer_givoni
from tests.test_nouvelles_fonctions import _variante

APP = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")


# ----------------------------------------------------------------------
# #3 — nom de fichier du snapshot = titre du graphique
# ----------------------------------------------------------------------
def test_plotly_config_filename_depuis_titre():
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.update_layout(title="Diagramme de Givoni — A_Ch")
    conf = charte.plotly_config(fig)
    assert conf["toImageButtonOptions"]["filename"] == "Diagramme de Givoni — A_Ch"
    assert conf["displaylogo"] is False


def test_plotly_config_sanitize_et_defaut():
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.update_layout(title='T:/mauvais*nom?"<>|')
    nom = charte.plotly_config(fig)["toImageButtonOptions"]["filename"]
    assert not set(nom) & set('\\/:*?"<>|')
    # Sans titre → nom par défaut
    assert charte.plotly_config(go.Figure())["toImageButtonOptions"]["filename"] == "graphique"


# ----------------------------------------------------------------------
# #4 / #5 — vitesse d'air : légende COCO + annotations sur le graphe
# ----------------------------------------------------------------------
def test_coco_labels_contiennent_vitesse():
    labels = [label for _v, label, _T, _W in confort.zones_modele({}, "coco")]
    assert all("m/s" in lab for lab in labels)
    assert any("0 m/s" in lab for lab in labels)
    assert any("1 m/s" in lab for lab in labels)


def test_givoni_annotations_vitesse_sur_graphe():
    pts = {'T': np.array([24.0, 25.0]), 'w': np.array([9.0, 10.0]),
           'saison': np.array(['', '']), 'label': 'Z'}
    fig = creer_givoni([pts], config={}, methode="givoni")
    txts = [a.text for a in fig.layout.annotations if a.text and "m/s" in a.text]
    # 4 zones Givoni → 4 étiquettes de vitesse, dont "0,5 m/s" (virgule FR)
    assert len(txts) == 4
    assert "0,5 m/s" in txts and "0 m/s" in txts


# ----------------------------------------------------------------------
# #8 — séparateur décimal virgule dans le rapport Word
# ----------------------------------------------------------------------
def _cellules(buf):
    from docx import Document
    from io import BytesIO
    doc = Document(BytesIO(buf.getvalue()))
    return [c.text for t in doc.tables for row in t.rows for c in row.cells]


def test_rapport_word_separateur_decimal(tmp_path):
    from export.word_report import generer_rapport
    v = _variante(tmp_path, ["A", "B"], n_rows=48)
    buf_fr = generer_rapport(variantes=[v], config={}, seuil_t1=26.0, seuil_t2=28.0,
                             zones_focus=[], zones_comparaison=[], nom_projet="P",
                             methode="givoni", format_fr=True,
                             inclure_graphiques_synthese=False)
    buf_pt = generer_rapport(variantes=[v], config={}, seuil_t1=26.0, seuil_t2=28.0,
                             zones_focus=[], zones_comparaison=[], nom_projet="P",
                             methode="givoni", format_fr=False,
                             inclure_graphiques_synthese=False)
    cells_fr = _cellules(buf_fr)
    cells_pt = _cellules(buf_pt)
    assert any(re.search(r"\d,\d", c) for c in cells_fr), "virgule attendue en format FR"
    assert not any(re.search(r"\d\.\d", c) for c in cells_fr), "aucun point décimal en format FR"
    assert any(re.search(r"\d\.\d", c) for c in cells_pt), "point attendu si format_fr=False"


# ----------------------------------------------------------------------
# Synthèse générale : onglets thématiques + graphe heures de dépassement
# ----------------------------------------------------------------------
def test_synthese_generale_onglets_et_graphe_heures(tmp_path):
    from streamlit.testing.v1 import AppTest
    v = _variante(tmp_path, ["A", "B"], n_rows=48)
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["variantes"] = [v]
    at.session_state["nav_vue"] = "Synthèse générale"
    at.run()
    assert not at.exception
    # 5 onglets thématiques (Synthèse / Besoins / Températures / Humidité / Confort)
    assert len(at.tabs) == 5
    # 6 graphes : besoins, températures, HEURES DE DÉPASSEMENT (nouveau),
    # humidité, % inconfort, inconfort jour/nuit.
    assert len(at.get("plotly_chart")) == 6


def _kaleido_ok():
    try:
        import plotly.graph_objects as go
        go.Figure().to_image(format="png")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _kaleido_ok(), reason="kaleido/Chrome indisponible")
def test_rapport_word_inclut_graphiques_synthese(tmp_path):
    """Les 6 graphes barres bâtiment sont ajoutés à la synthèse du rapport Word
    quand inclure_graphiques_synthese=True (source charts/synthese partagée)."""
    from export.word_report import generer_rapport
    from docx import Document
    from io import BytesIO

    v = _variante(tmp_path, ["A", "B"], n_rows=48)

    def n_images(buf):
        return len(Document(BytesIO(buf.getvalue())).inline_shapes)

    sans = generer_rapport(variantes=[v], config={}, seuil_t1=26.0, seuil_t2=28.0,
                           zones_focus=[], zones_comparaison=[], nom_projet="P",
                           methode="givoni", inclure_graphiques_synthese=False)
    avec = generer_rapport(variantes=[v], config={}, seuil_t1=26.0, seuil_t2=28.0,
                           zones_focus=[], zones_comparaison=[], nom_projet="P",
                           methode="givoni", inclure_graphiques_synthese=True)
    assert n_images(avec) - n_images(sans) == 6


# ----------------------------------------------------------------------
# Dégradé de couleur des tableaux sans matplotlib (exclu de l'exécutable)
# ----------------------------------------------------------------------
def test_vues_sans_background_gradient():
    """Styler.background_gradient exige matplotlib, absent de l'exécutable :
    les vues doivent utiliser views.widgets.degrade."""
    import glob
    racine = os.path.dirname(os.path.dirname(__file__))
    for f in glob.glob(os.path.join(racine, "views", "*.py")) + [APP]:
        with open(f, encoding="utf-8") as fh:
            assert ".background_gradient(" not in fh.read(), f


def test_degrade_equivalent_background_gradient():
    import pandas as pd
    from views.widgets import degrade
    df = pd.DataFrame({"a": [0.0, 12.5, np.nan, 50.0, 100.0], "b": [5.0] * 5})
    css = df.style.apply(degrade, subset=["a", "b"])._compute().ctx
    assert css[(2, 0)] == []                                   # NaN : pas de style
    assert ("background-color", "#ffffcc") in css[(0, 0)]      # min → jaune clair
    assert ("background-color", "#800026") in css[(4, 0)]      # max → rouge foncé
    assert ("color", "#f1f1f1") in css[(4, 0)]                 # texte clair sur fond sombre
    assert ("background-color", "#ffffcc") in css[(0, 1)]      # colonne constante
    pytest.importorskip("matplotlib")
    ref = df.style.background_gradient(subset=["a"], cmap="YlOrRd")._compute().ctx
    def _rgb(c):
        h = dict(c)["background-color"].lstrip("#")
        return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)])
    for i in (0, 1, 3, 4):
        assert np.abs(_rgb(css[(i, 0)]) - _rgb(ref[(i, 0)])).max() <= 3
        assert dict(css[(i, 0)])["color"] == dict(ref[(i, 0)])["color"]
