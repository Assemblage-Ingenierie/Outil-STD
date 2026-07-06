"""
Tests du parser CSV Pléiades (core.csv_parser) :
- équivalence STRICTE avec le parser SYLK sur des données identiques
  (le DataFrame produit doit être interchangeable en aval) ;
- mapping des colonnes de la synthèse (2 tableaux) ;
- validation (grandeurs requises, fichier de synthèse) ;
- auto-détection par extension dans charger_variante.
"""
import numpy as np
import pandas as pd
import pytest

from core import csv_parser
from core.slk_parser import parse_resultats as slk_parse_resultats, FichierInvalideError
from core.variante import _parse_resultats_auto, _parse_synthese_auto
from tests.test_perf_optims import _resultats_lignes, _ecrire


def _ecrire_csv(tmp_path, texte, nom):
    f = tmp_path / nom
    f.write_text(texte, encoding="utf-8-sig")
    return f


def _csv_resultats(zones, n_rows, t_zone):
    """CSV résultats reproduisant EXACTEMENT le contenu de _resultats_lignes (SYLK)
    pour permettre une comparaison à l'identique."""
    nz = len(zones)
    types = (["mois", "jour", "heure", "Températures"]
             + ["Température (°C)"] * nz
             + ["Humidité relative (%)"] * nz
             + ["Apports occupants (W)"] * nz)
    zrow = ["", "", "", ""] + list(zones) * 3
    lignes = [",".join(types), ",".join(zrow)]
    for r in range(n_rows):
        row = [str((r % 12) + 1), str((r % 28) + 1), str((r % 24) + 1), str(15.0 + r)]
        row += [str(t_zone(i, r)) for i in range(nz)]
        row += [str(50.0 + i) for i in range(nz)]
        row += [str(100.0 * (r % 2)) for i in range(nz)]
        lignes.append(",".join(row))
    return "\n".join(lignes) + "\n"


# ----------------------------------------------------------------------
# Équivalence stricte CSV ↔ SYLK (résultats)
# ----------------------------------------------------------------------
def test_csv_resultats_equivaut_slk(tmp_path):
    zones = ["Séjour", "Chambre", "SdB"]
    t_zone = lambda i, r: 10.0 + i + r
    slk = _ecrire(tmp_path, _resultats_lignes(zones, 30, t_zone), "r.slk")
    csv = _ecrire_csv(tmp_path, _csv_resultats(zones, 30, t_zone), "r.csv")

    df_slk = slk_parse_resultats(slk)
    df_csv = csv_parser.parse_resultats(csv)

    assert df_slk.attrs["zones"] == df_csv.attrs["zones"] == zones
    # Mêmes colonnes et mêmes valeurs (ordre de colonnes indifférent).
    pd.testing.assert_frame_equal(
        df_csv, df_slk, check_like=True, check_dtype=False)


def test_csv_resultats_globales_et_zones(tmp_path):
    zones = ["A", "B"]
    csv = _ecrire_csv(tmp_path, _csv_resultats(zones, 24, lambda i, r: 20.0 + i + r), "r.csv")
    df = csv_parser.parse_resultats(csv)
    assert set(df.attrs["zones"]) == {"A", "B"}
    assert df["Température (°C)|A"].iloc[0] == pytest.approx(20.0)
    assert df["Humidité relative (%)|B"].iloc[0] == pytest.approx(51.0)
    assert df["heure"].tolist() == [(r % 24) + 1 for r in range(24)]
    # saison / theta_rm absents → colonnes présentes mais neutres
    assert (df["saison"] == "").all()
    assert df["theta_rm"].isna().all()


def test_csv_resultats_manque_grandeur_requise(tmp_path):
    # Retirer la grandeur « Apports occupants (W) » → doit lever FichierInvalideError
    nz = 1
    types = ["mois", "jour", "heure", "Températures",
             "Température (°C)", "Humidité relative (%)"]
    zrow = ["", "", "", "", "A", "A"]
    lignes = [",".join(types), ",".join(zrow), "1,1,1,15.0,20.0,50.0"]
    csv = _ecrire_csv(tmp_path, "\n".join(lignes) + "\n", "bad.csv")
    with pytest.raises(FichierInvalideError):
        csv_parser.parse_resultats(csv)


# ----------------------------------------------------------------------
# Synthèse : mapping des deux tableaux
# ----------------------------------------------------------------------
def _csv_synthese(rows):
    """rows = liste de tuples (zone, bch_kwh, bch_m2, bfr_kwh, bfr_m2, pch, pfr,
    tmin, tmoy, tmax, heures_inc, surface, volume)."""
    t1_head = "Zones,Besoins Ch.,Besoins Ch.,Besoins Clim.,Besoins Clim.,Puiss. Chauff.,Puiss. Clim.,T° Min,T° Moyenne,T° Max"
    t1_units = ",kWh,kWh/m²,kWh,kWh/m²,W,W,°C,°C,°C"
    t2_head = "Zones,Apports solaires bruts,Conso Eclairage,Heures > T°Inconfort,Taux d'inconfort,Part de besoins nets,Besoins bruts,Surface,Volume"
    t2_units = ",kWh,kWh,h,%,%,kWh,m²,m³"
    L = [t1_head, t1_units, "", "Total,0,0,0,0,0,0,0,0,0"]
    for (z, bch, bchm, bfr, bfrm, pch, pfr, tmin, tmoy, tmax, hi, surf, vol) in rows:
        L.append(f"{z},{bch},{bchm},{bfr},{bfrm},{pch},{pfr},{tmin},{tmoy},{tmax}")
    L += [t2_head, t2_units, "", "Total,0,0,0,0,0,0,0,0"]
    for (z, bch, bchm, bfr, bfrm, pch, pfr, tmin, tmoy, tmax, hi, surf, vol) in rows:
        # cols: zone, apports, conso, heures_inc(3), taux, part, besoins, surface(7), volume(8)
        L.append(f"{z},0,0,{hi},0,0,0,{surf},{vol}")
    return "\n".join(L) + "\n"


def test_csv_synthese_mapping(tmp_path):
    rows = [
        # zone, bch_kwh, bch_m2, bfr_kwh, bfr_m2, pch, pfr, tmin, tmoy, tmax, heures_inc, surf, vol
        ("A", 100.0, 8.3, 5.0, 0.4, 1200.0, 800.0, 18.5, 24.0, 30.5, 120.0, 12.0, 30.0),
        ("B", 0.0, 0.0, 50.0, 2.0, 0.0, 1500.0, 19.0, 25.0, 33.0, 300.0, 25.0, 62.5),
    ]
    csv = _ecrire_csv(tmp_path, _csv_synthese(rows), "syn.csv")
    df = csv_parser.parse_synthese(csv)
    assert list(df["zone"]) == ["A", "B"]
    a = df[df["zone"] == "A"].iloc[0]
    assert a["besoins_chaud_kwh"] == pytest.approx(100.0)
    assert a["besoins_chaud_kwh_m2"] == pytest.approx(8.3)
    assert a["besoins_froid_kwh"] == pytest.approx(5.0)
    assert a["t_min"] == pytest.approx(18.5)
    assert a["t_max"] == pytest.approx(30.5)
    assert a["surface_m2"] == pytest.approx(12.0)
    assert a["volume_m3"] == pytest.approx(30.0)
    assert a["heures_inconfort"] == pytest.approx(120.0)
    b = df[df["zone"] == "B"].iloc[0]
    assert b["surface_m2"] == pytest.approx(25.0)
    assert b["volume_m3"] == pytest.approx(62.5)


def test_csv_synthese_invalide(tmp_path):
    # Un CSV sans en-tête « Besoins » (ex. résultats) → erreur explicite
    csv = _ecrire_csv(tmp_path, "a,b,c\n1,2,3\n", "pasyn.csv")
    with pytest.raises(FichierInvalideError):
        csv_parser.parse_synthese(csv)


# ----------------------------------------------------------------------
# Auto-détection par extension (charger_variante)
# ----------------------------------------------------------------------
def test_auto_detection_extension(tmp_path):
    zones = ["A"]
    slk = _ecrire(tmp_path, _resultats_lignes(zones, 12, lambda i, r: 20.0 + r), "r.slk")
    csv = _ecrire_csv(tmp_path, _csv_resultats(zones, 12, lambda i, r: 20.0 + r), "r.csv")
    # .csv → parser CSV ; .slk → parser SYLK ; résultats identiques
    df_csv = _parse_resultats_auto(str(csv))
    df_slk = _parse_resultats_auto(str(slk))
    assert df_csv.attrs["zones"] == df_slk.attrs["zones"] == ["A"]
    pd.testing.assert_frame_equal(df_csv, df_slk, check_like=True, check_dtype=False)
