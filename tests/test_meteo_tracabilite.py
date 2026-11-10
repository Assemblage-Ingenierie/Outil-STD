"""Traçabilité du fichier météo associé à chaque variante (app + annexe + projet)."""
import dataclasses
from io import BytesIO

import pandas as pd
from docx import Document

from core.variante import _chemin_meteo
from tests.test_nouvelles_fonctions import _variante


def _avec_meteo(tmp_path, nom="v", fichier="Pietersburg-hour.try", label="",
                origine="projet", chemin="C:/meteo/Pietersburg-hour.try"):
    v = _variante(tmp_path, ["A", "B"], n_rows=48)
    v = dataclasses.replace(v, nom=nom, meteo_nom=fichier, meteo_chemin=chemin,
                            meteo_origine=origine)
    v.meteo_label = label
    return v


def test_trace_libelle_et_fichier(tmp_path):
    v = _avec_meteo(tmp_path, label="RCP 8.5 2050")
    # Le libellé ne masque plus le fichier
    assert v.meteo_trace() == "RCP 8.5 2050 (Pietersburg-hour.try)"
    v.meteo_label = ""
    assert v.meteo_trace() == "Pietersburg-hour.try"


def test_infos_meteo_origine_et_chemin(tmp_path):
    info = _avec_meteo(tmp_path, origine="specifique").infos_meteo()
    assert info["Origine météo"] == "Spécifique à la variante"
    assert info["Chemin du fichier météo"] == "C:/meteo/Pietersburg-hour.try"
    assert _avec_meteo(tmp_path, origine="projet").meteo_origine_affiche() == \
        "Météo par défaut du projet"
    # Projet ancien : origine inconnue
    assert _avec_meteo(tmp_path, origine="").meteo_origine_affiche() == "Non renseignée"


def test_sans_meteo(tmp_path):
    v = _variante(tmp_path, ["A"], n_rows=24)
    assert v.meteo_trace() == "Aucune"
    info = v.infos_meteo()
    assert info["Fichier météo"] == "Aucun" and info["Origine météo"] == "Aucune"
    assert info["T extérieure utilisée"] in ("Indisponible", "Résultats Pléiades (colonne T ext.)")


def test_chemin_meteo_absolu(tmp_path):
    f = tmp_path / "m.try"
    f.write_text("x")
    assert _chemin_meteo(str(f), "m.try") == str(f.resolve())
    assert _chemin_meteo("", "") == ""


def test_charger_variante_rapide_enregistre_origine(tmp_path, monkeypatch):
    from views import reglages
    base = _avec_meteo(tmp_path, origine="")
    monkeypatch.setattr(reglages, "_charger_cache", lambda *a: base)
    assert reglages.charger_variante_rapide("X", "r", "s", "m", "specifique").meteo_origine \
        == "specifique"
    sans = dataclasses.replace(base, meteo_nom="")
    monkeypatch.setattr(reglages, "_charger_cache", lambda *a: sans)
    assert reglages.charger_variante_rapide("X", "r", "s", "", "projet").meteo_origine == ""


def test_projet_conserve_tracabilite(tmp_path):
    from core import projet as projet_io
    v = _avec_meteo(tmp_path, origine="specifique")
    chemin = projet_io.sauvegarder_projet(tmp_path / "p.stdproj", {"variantes": [v]})
    vr = projet_io.charger_projet(chemin)["variantes"][0]
    assert (vr.meteo_nom, vr.meteo_chemin, vr.meteo_origine) == \
        ("Pietersburg-hour.try", "C:/meteo/Pietersburg-hour.try", "specifique")


def test_annexe_trace_meteo(tmp_path):
    from export.annexe import generer_annexe
    v1 = _avec_meteo(tmp_path, nom="V1", label="Actuel")
    v2 = _avec_meteo(tmp_path, nom="V2", fichier="RCP85.try", chemin="D:/m/RCP85.try",
                     origine="specifique")
    v3 = dataclasses.replace(_variante(tmp_path, ["A"], n_rows=48), nom="V3")
    res = generer_annexe([v1, v2, v3], {}, zones_detail=["A"], inclure_graphiques=False)
    doc = Document(BytesIO(res.docx.getvalue()))
    cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
    assert "Pietersburg-hour.try" in cells and "RCP85.try" in cells
    assert "Spécifique à la variante" in cells and "Météo par défaut du projet" in cells
    assert "D:/m/RCP85.try" in cells                     # tableau « Fichiers météo utilisés »
    assert "Actuel (Pietersburg-hour.try)" in cells      # fiche zone : libellé + fichier
    assert any("Sans fichier météo .try : V3" in p.text for p in doc.paragraphs)
    zl = pd.read_excel(res.xlsx, "Zones")
    assert set(zl["Fichier météo"].fillna("")) == {"Pietersburg-hour.try", "RCP85.try", ""}
