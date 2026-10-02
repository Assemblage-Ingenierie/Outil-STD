"""Langue des graphiques (config/i18n.py) : traductions complètes et figures
sans texte français en mode anglais."""
import ast
import glob
import os
import re

import numpy as np
import pandas as pd
import pytest

from config import i18n

RACINE = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture
def anglais():
    i18n.set_langue("en")
    yield
    i18n.set_langue("fr")


def test_t_repli_et_formatage(anglais):
    assert i18n.t("Température intérieure — {zone}", zone="Z") == "Indoor temperature — Z"
    assert i18n.t("Texte sans traduction") == "Texte sans traduction"     # repli FR
    assert i18n.nombre(0.5) == "0.5"
    assert i18n.noms_mois()[1] == "Feb"
    i18n.set_langue("fr")
    assert i18n.t("Température intérieure — {zone}", zone="Z") == "Température intérieure — Z"
    assert i18n.nombre(0.5) == "0,5"
    assert i18n.noms_mois()[1] == "Fév"
    i18n.set_langue("xx")                                                   # code inconnu → FR
    assert i18n.langue() == "fr"


def _appels_t(fichier):
    """Littéraux passés en 1er argument de t(...) (concaténations implicites incluses)."""
    with open(fichier, encoding="utf-8") as f:
        arbre = ast.parse(f.read())
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "t"
                and n.args and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)):
            yield n.args[0].value


def test_tous_les_appels_t_sont_traduits():
    fichiers = (glob.glob(os.path.join(RACINE, "charts", "*.py"))
                + glob.glob(os.path.join(RACINE, "views", "*.py"))
                + [os.path.join(RACINE, "export", "word_report.py")])
    manquants = {(os.path.basename(f), s) for f in fichiers for s in _appels_t(f)
                 if s not in i18n.EN}
    assert not manquants, sorted(manquants)


def test_gabarits_en_memes_champs():
    """Chaque traduction garde exactement les mêmes champs {…} que le français."""
    champs = re.compile(r"(?<!\{)\{(\w*)\}(?!\})")
    for fr, en in i18n.EN.items():
        assert set(champs.findall(fr)) == set(champs.findall(en)), fr


# ----------------------------------------------------------------------
# Rendu : aucune chaîne française dans les figures en anglais
# ----------------------------------------------------------------------
_FRANCAIS = re.compile(r"[éèêàùûôîç]|\b(de|des|du|la|le|les|par|et|sous|hors|dont|Heures?|"
                       r"Confort|Diagramme|Apports|Besoins|Variante|Mois|Seuil)\b")


def _textes(fig):
    """Tous les textes affichés par une figure (layout + traces)."""
    d = fig.to_plotly_json()
    out = []
    lay = d.get("layout", {})

    def _titre(x):
        if isinstance(x, dict):
            return x.get("text")
        return x
    out.append(_titre(lay.get("title")))
    for k, v in lay.items():
        if k.startswith(("xaxis", "yaxis")) and isinstance(v, dict):
            out.append(_titre(v.get("title")))
            for b in (v.get("rangeselector") or {}).get("buttons", []):
                out.append(b.get("label"))
    out += [a.get("text") for a in lay.get("annotations", [])]
    for tr in d.get("data", []):
        out.append(tr.get("name"))
        ht = tr.get("hovertemplate")
        if isinstance(ht, str):
            out.append(re.sub(r"<extra>.*?</extra>", "", ht))
        cb = (tr.get("colorbar") or {}).get("title")
        out.append(_titre(cb))
        xs = list(tr["x"]) if tr.get("type") == "bar" and tr.get("x") is not None else []
        if xs and isinstance(xs[0], str):
            out += xs                 # mois en abscisse
    return [s for s in out if isinstance(s, str) and s]


def _assert_anglais(fig):
    fr = [s for s in _textes(fig) if _FRANCAIS.search(s)]
    assert not fr, fr


@pytest.fixture
def variantes():
    """Deux variantes synthétiques complètes (8 760 h, météo, saisons, apports)."""
    from core.variante import Variante
    h = pd.date_range("2023-01-01", periods=8760, freq="h")
    rng = np.random.default_rng(0)
    t_ext = 15 + 10 * np.sin(np.arange(8760) / 8760 * 2 * np.pi) + rng.normal(0, 2, 8760)
    out = []
    for k in range(2):
        df = pd.DataFrame({"mois": h.month, "jour": h.day, "heure": h.hour + 1,
                           "T_ext": t_ext,
                           "saison": np.where(h.month.isin([6, 7, 8]), "Refroidissement",
                                              np.where(h.month.isin([12, 1, 2]), "Chauffage", ""))})
        for z in ("Z1", "Z2"):
            df[f"Température (°C)|{z}"] = 22 + 0.4 * (t_ext - 15) + k
            df[f"Humidité relative (%)|{z}"] = 55 + 10 * np.cos(np.arange(8760) / 24)
            df[f"Apports occupants (W)|{z}"] = np.where((h.hour >= 8) & (h.hour < 20), 100.0, 0.0)
            df[f"Apports solaires (W)|{z}"] = 200.0
            df[f"P Chauffage (W)|{z}"] = np.where(h.month.isin([12, 1, 2]), 500.0, 0.0)
        df.attrs["zones"] = ["Z1", "Z2"]
        syn = pd.DataFrame([{"zone": z, "surface_m2": 20.0, "besoins_chaud_kwh": 1.0,
                             "besoins_froid_kwh": 1.0, "besoins_chaud_kwh_m2": 1.0,
                             "besoins_froid_kwh_m2": 1.0} for z in ("Z1", "Z2")])
        met = pd.DataFrame({"T_ext": t_ext, "HR_ext": 60.0})
        out.append(Variante(nom=f"V{k + 1}", df_horaire=df, df_synthese=syn, df_meteo=met,
                            zones=["Z1", "Z2"], meteo_nom=f"meteo{k}.try"))
    return out


def test_figures_temperature_humidite_en_anglais(anglais, variantes):
    from charts import temperature as ct, humidite as ch
    vs, z = variantes, "Z1"
    figs = [
        ct.graphique_temp_horaire(vs, z, 26, 28),
        ct.graphique_text_vs_text_op(vs[:1], z, par_saison=True),
        ct.graphique_text_vs_text_op(vs[:1], z, par_saison=False),
        ct.graphique_meteo_comparaison(vs),
        ct.graphique_heures_depassement(vs, ["Z1", "Z2"], 26, 28),
        ct.graphique_temp_min_moy_max(vs, ["Z1", "Z2"]),
        ct.graphique_apports_solaires(vs, z, type_apport="solaires"),
        ct.graphique_apports_solaires(vs, z, type_apport="internes"),
        ct.heatmap_temp_jour_heure(vs[0], z),
        ct.graphique_apports_par_zone_mensuel(vs[0], ["Z1", "Z2"]),
        ch.graphique_hr_horaire(vs[:1], z, agregation="journalier"),
        ch.graphique_hr_horaire(vs, z, agregation="horaire"),
        ch.heatmap_hr_jour_heure(vs[0], z),
        ch.graphique_hr_min_moy_max(vs, ["Z1", "Z2"]),
    ]
    for f in figs:
        _assert_anglais(f)
    assert figs[0].layout.title.text == "Indoor temperature — Z1"
    assert list(figs[6].data[0].x[:2]) == ["Jan", "Feb"]


def test_figures_givoni_coco_en_anglais(anglais, variantes):
    from charts.givoni import creer_givoni
    v = variantes[0]
    for methode in ("givoni", "coco"):
        pts = v.points_interieurs_givoni("Z1", {}, methode)
        pts["label"] = v.nom
        fig = creer_givoni([pts], {}, methode=methode, note_chauffe=True)
        _assert_anglais(fig)
        noms = [tr.name for tr in fig.data]
        assert any("Comfort" in n or "COCO" in n for n in noms)
    per = v.points_interieurs_par_periode("Z1", {}, [{"nom": "Summer", "m1": 6, "m2": 8}], "givoni")
    per["label"] = v.nom
    _assert_anglais(creer_givoni([per], {}, par_periode=True))


def test_figures_synthese_en_anglais(anglais):
    from charts import synthese as cs
    noms = ["V1", "V2"]
    df = pd.DataFrame({"Besoins chaud (kWh/m²)": [1, 2], "Besoins froid (kWh/m²)": [3, 4],
                       "T min (°C)": [18, 19], "T moy (°C)": [22, 23], "T max (°C)": [28, 29],
                       "H < 18°C": [1, 2], "H > 26°C": [3, 4], "H > 28°C": [5, 6],
                       "HR min (%)": [30, 31], "HR moy (%)": [50, 51], "HR max (%)": [80, 81],
                       "% hors Givoni 0 m/s": [10, 20], "% hors Givoni 1 m/s": [5, 10]})
    dn = pd.DataFrame({c: [1.0, 2.0] for c in ("% inconfort jour 0 m/s", "% inconfort nuit 0 m/s",
                                                  "% inconfort jour 1 m/s", "% inconfort nuit 1 m/s")})
    for f in (cs.graphique_besoins(df, noms), cs.graphique_temperatures(df, noms),
              cs.graphique_heures_depassement_batiment(df, noms, 18, 26, 28),
              cs.graphique_humidite(df, noms), cs.graphique_part_inconfort(df, noms),
              cs.graphique_inconfort_jour_nuit(dn, noms)):
        _assert_anglais(f)


def test_figures_en16798_en_anglais(anglais, variantes):
    from charts.adaptatif import creer_scatter_adaptatif, creer_barres_en16798
    series = [{"label": v.nom, "res": v.en16798("Z1"), "t_int": v.col_temp("Z1"),
               "horodatage": v.horodatage()} for v in variantes]
    for s in (series[:1], series):
        fig = creer_scatter_adaptatif(s, "t", bandes_123=True)
        _assert_anglais(fig)
    noms = [tr.name for tr in creer_scatter_adaptatif(series[:1], "t").data]
    assert any(n.startswith("Comfortable (") for n in noms)
    df = pd.DataFrame({"zone": ["Z1", "Z2"], "discomfort_pct": [3.0, 30.0],
                       "discomfort_hours": [1, 2], "discomfort_warm": [1, 1],
                       "discomfort_cold": [0, 1]})
    fig = creer_barres_en16798(df, 2, "V1")
    _assert_anglais(fig)
    assert fig.layout.title.text.startswith("EN 16798-1 adaptive comfort — Category II")


def test_francais_par_defaut_inchange(variantes):
    """Sans réglage, les figures restent en français (non-régression)."""
    from charts import temperature as ct
    assert i18n.langue() == "fr"
    fig = ct.graphique_temp_horaire(variantes, "Z1")
    assert fig.layout.title.text == "Température intérieure — Z1"
    assert fig.layout.xaxis.title.text == "Date"
