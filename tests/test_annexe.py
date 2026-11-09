"""Tests de l'export annexe (export/annexe.py) : Word + Excel + ZIP PNG."""
import re
import zipfile
from io import BytesIO

import pandas as pd
import pytest
from docx import Document

from export.annexe import generer_annexe, estimer_figures, _nom_fichier
from tests.test_nouvelles_fonctions import _variante


def _kaleido_ok():
    try:
        import plotly.graph_objects as go
        go.Figure().to_image(format="png")
        return True
    except Exception:
        return False


def _doc(res):
    return Document(BytesIO(res.docx.getvalue()))


def _cellules(res):
    return [c.text for t in _doc(res).tables for row in t.rows for c in row.cells]


def _legendes(res):
    return [p.text for p in _doc(res).paragraphs if p.style.name == "Caption"]


def _titres(res, niveau):
    return [p.text for p in _doc(res).paragraphs if p.style.name == f"Heading {niveau}"]


def _annexe(tmp_path, zones=("A", "B", "C"), **kw):
    v = _variante(tmp_path, list(zones), n_rows=48)
    kw.setdefault("inclure_graphiques", False)
    return generer_annexe([v], {}, nom_projet="P", **kw)


def test_tableaux_toutes_zones_fiches_zones_choisies(tmp_path):
    res = _annexe(tmp_path, zones_detail=["B"])
    cells = _cellules(res)
    # Le tableau « Indicateurs par zone » couvre TOUTES les zones…
    assert {"A", "B", "C"} <= set(cells)
    # … mais seules les zones détaillées ont une fiche (titre de niveau 2).
    assert "B" in _titres(res, 2) and "A" not in _titres(res, 2)
    assert "5. Fiches zone" in _titres(res, 1)
    assert res.n_figures == 0 and res.zip_png is None


def test_sans_zone_detaillee_pas_de_fiche(tmp_path):
    res = _annexe(tmp_path, zones_detail=[])
    assert "5. Fiches zone" not in _titres(res, 1)
    assert "3. Indicateurs par zone (toutes zones)" in _titres(res, 1)


def test_tableaux_numerotes_et_excel_coherent(tmp_path):
    res = _annexe(tmp_path, zones_detail=["A"])
    leg = [x for x in _legendes(res) if x.startswith("Tableau")]
    assert len(leg) == res.n_tableaux
    assert [int(re.match(r"Tableau (\d+)", x).group(1)) for x in leg] == \
        list(range(1, res.n_tableaux + 1))
    xl = pd.ExcelFile(res.xlsx)
    assert xl.sheet_names[:2] == ["Sommaire", "Zones"]
    sommaire = pd.read_excel(xl, "Sommaire")
    assert len(sommaire) == res.n_tableaux + 1      # + la feuille Zones consolidée
    # Chaque onglet référencé existe
    assert set(sommaire["Onglet"]) <= set(xl.sheet_names)
    # Feuille Zones : format long, valeurs numériques brutes
    zl = pd.read_excel(xl, "Zones")
    assert list(zl.columns[:2]) == ["Variante", "Zone"]
    assert sorted(zl["Zone"]) == ["A", "B", "C"]
    assert pd.api.types.is_numeric_dtype(zl["T max (°C)"])


def test_separateur_decimal(tmp_path):
    fr = _cellules(_annexe(tmp_path, format_fr=True))
    en = _cellules(_annexe(tmp_path, format_fr=False))
    assert any(re.fullmatch(r"-?\d+,\d", c) for c in fr)
    assert not any(re.fullmatch(r"-?\d+\.\d", c) for c in fr)
    assert any(re.fullmatch(r"-?\d+\.\d", c) for c in en)


def test_recap_et_descriptif(tmp_path):
    df_recap = pd.DataFrame({"v": [True, False]}, index=["Brise-soleil", "Surventilation"])
    df_detail = pd.DataFrame({"Amélioration": ["Brise-soleil"],
                              "Descriptif": ["Protection sud"]})
    cells = _cellules(_annexe(tmp_path, df_recap=df_recap, df_detail=df_detail))
    # L'index (non nommé) du récap est conservé, les cases cochées rendues en ✕
    assert "Brise-soleil" in cells and "Surventilation" in cells
    assert "✕" in cells
    assert "Protection sud" in cells


@pytest.mark.parametrize("nom", ["", "Mon Projet"])
def test_nom_projet_vide(tmp_path, nom):
    v = _variante(tmp_path, ["A"], n_rows=24)
    res = generer_annexe([v], {}, nom_projet=nom, inclure_graphiques=False)
    assert res.docx.getvalue() and res.xlsx.getvalue()


def test_estimer_figures():
    assert estimer_figures(3, 2, graphiques=False) == 0
    assert estimer_figures(2, 0) < estimer_figures(2, 1) < estimer_figures(2, 2)


def test_nom_fichier_png():
    assert _nom_fichier("T<br>moy / max : <b>zone</b>?") == "T moy max zone"


@pytest.mark.skipif(not _kaleido_ok(), reason="kaleido/Chrome indisponible")
def test_figures_word_zip_et_progression(tmp_path):
    etapes = []
    res = _annexe(tmp_path, zones=("A", "B"), zones_detail=["A"], inclure_graphiques=True,
                  progression=lambda f, msg: etapes.append(f))
    assert not res.erreurs
    assert res.n_figures > 10
    assert len(_doc(res).inline_shapes) == res.n_figures + 1          # + logo de couverture
    assert len([x for x in _legendes(res) if x.startswith("Figure")]) == res.n_figures
    noms = zipfile.ZipFile(res.zip_png).namelist()
    assert len(noms) == res.n_figures
    assert noms[0].startswith("F001 - ") and all(n.endswith(".png") for n in noms)
    assert pd.read_excel(res.xlsx, "Figures").shape[0] == res.n_figures
    assert etapes == sorted(etapes) and etapes[-1] == 1.0


def test_ecran_reglages_export_annexe(tmp_path):
    """Onglet Réglages : génération de l'annexe (tableaux seuls) puis trois boutons
    de téléchargement, qui survivent au rerun."""
    import os
    from streamlit.testing.v1 import AppTest
    app = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.py")
    v = _variante(tmp_path, ["A", "B"], n_rows=48)
    at = AppTest.from_file(app, default_timeout=120)
    at.session_state["variantes"] = [v]
    at.session_state["nav_vue"] = "Réglages"
    at.session_state["cfg_annexe_graphiques"] = False
    at.run()
    assert not at.exception
    bouton = next(b for b in at.button if b.key == "btn_annexe")
    bouton.click().run()
    assert not at.exception
    assert at.session_state["_annexe"].n_tableaux > 5
    assert any("Annexe générée" in s.value for s in at.success)
    at.run()                                     # rerun (ex. après un téléchargement)
    assert any("Annexe générée" in s.value for s in at.success)
