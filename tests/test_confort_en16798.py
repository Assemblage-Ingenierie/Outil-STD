"""Tests du confort adaptatif EN 16798-1 (core/confort_en16798.py)."""
import numpy as np
import pandas as pd
import pytest

from core import confort_en16798 as en


def _t_ext_journalier(moyennes):
    """Série horaire dont la moyenne journalière vaut `moyennes[j]` (profil ±3 K)."""
    profil = 3 * np.sin(np.linspace(0, 2 * np.pi, 24, endpoint=False))
    return pd.Series(np.concatenate([m + profil for m in moyennes]))


# ----------------------------------------------------------------------
# Running mean θrm (Annexe B, formule B.1)
# ----------------------------------------------------------------------
def test_moyennes_journalieres_jour_incomplet():
    t = np.r_[np.full(24, 10.0), np.full(12, 20.0)]
    np.testing.assert_allclose(en.moyennes_journalieres(t), [10.0, 20.0])


def test_running_mean_init_7j_puis_recurrence():
    ted = [10, 12, 14, 16, 18, 20, 22, 30, 30, 30]
    trm = en.running_mean_journaliere(_t_ext_journalier(ted))
    init = np.mean(ted[:7])                          # 16
    np.testing.assert_allclose(trm[:7], init)
    assert trm[7] == pytest.approx(0.2 * ted[6] + 0.8 * init)
    assert trm[8] == pytest.approx(0.2 * ted[7] + 0.8 * trm[7])


def test_running_mean_constante_et_alpha():
    trm = en.running_mean_journaliere(_t_ext_journalier([20.0] * 30))
    np.testing.assert_allclose(trm, 20.0)
    # α = 0 → θrm(j) = θed(j−1)
    ted = np.arange(10.0, 40.0)
    trm0 = en.running_mean_journaliere(_t_ext_journalier(ted), alpha=0.0)
    np.testing.assert_allclose(trm0[7:], ted[6:-1])


def test_running_mean_cyclique_point_fixe():
    ted = 15 + 8 * np.sin(np.linspace(0, 2 * np.pi, 365, endpoint=False))
    trm = en.running_mean_journaliere(_t_ext_journalier(ted), init="cyclique")
    # Périodicité : θrm(0) = 0,2·θed(364) + 0,8·θrm(364)
    assert trm[0] == pytest.approx(0.2 * ted[-1] + 0.8 * trm[-1])
    with pytest.raises(ValueError):
        en.running_mean_journaliere(_t_ext_journalier(ted), init="xx")


def test_running_mean_horaire_repliquee_et_tronquee():
    t = _t_ext_journalier([20.0] * 3).iloc[:60]
    trm = en.running_mean_horaire(t)
    assert len(trm) == 60
    assert trm.index.equals(t.index)


# ----------------------------------------------------------------------
# Température de confort et bandes (formule B.2, Tableau B.2)
# ----------------------------------------------------------------------
def test_temperature_confort_et_limites():
    assert en.temperature_confort(20.0) == pytest.approx(25.4)
    for cat, (bas, haut) in {1: (3, 2), 2: (4, 3), 3: (5, 4)}.items():
        lo, hi = en.limites_categorie(20.0, cat)
        assert lo == pytest.approx(25.4 - bas)
        assert hi == pytest.approx(25.4 + haut)
    lo, hi = en.limites_categorie(20.0, 2, en.BANDES_SYMETRIQUES)
    assert (lo, hi) == pytest.approx((22.4, 28.4))
    with pytest.raises(ValueError):
        en.limites_categorie(20.0, 4)


# ----------------------------------------------------------------------
# Décompte (fonction principale)
# ----------------------------------------------------------------------
def _cas_simple(t_int_val, trm_val=20.0, n_jours=10, occ=True):
    t_ext = _t_ext_journalier([trm_val] * n_jours)        # θrm ≡ trm_val
    n = len(t_ext)
    t_int = pd.Series(np.full(n, t_int_val, dtype=float))
    occupied = pd.Series(np.full(n, occ))
    return t_int, t_ext, occupied


def test_compute_confortable():
    # θrm = 20 → Cat II : [21,4 ; 28,4]
    r = en.compute_en16798_adaptive(*_cas_simple(25.0))
    assert r["discomfort_hours"] == 0
    assert r["discomfort_pct"] == 0.0
    assert r["total_occupied_valid"] == 240
    assert r["comfortable"].all()
    assert r["t_upper"].iloc[0] == pytest.approx(28.4)
    assert r["t_lower"].iloc[0] == pytest.approx(21.4)


def test_compute_chaud_froid_et_categorie():
    r = en.compute_en16798_adaptive(*_cas_simple(29.0))
    assert r["discomfort_hours_warm"] == 240 and r["discomfort_hours_cold"] == 0
    assert r["discomfort_pct"] == pytest.approx(100.0)
    # 29 °C est dans la bande Cat III (≤ 29,4)
    assert en.compute_en16798_adaptive(*_cas_simple(29.0), category=3)["discomfort_hours"] == 0
    r = en.compute_en16798_adaptive(*_cas_simple(21.0))
    assert r["discomfort_hours_cold"] == 240 and r["discomfort_hours_warm"] == 0


def test_compute_heures_non_occupees_ignorees():
    t_int, t_ext, occ = _cas_simple(35.0)
    occ[:] = False
    occ.iloc[:10] = True
    r = en.compute_en16798_adaptive(t_int, t_ext, occ)
    assert r["total_occupied_valid"] == 10
    assert r["discomfort_hours"] == 10
    assert not r["warm"].iloc[10:].any()


def test_compute_domaine_application():
    # θrm = 35 : hors domaine (> 30) → rien n'est évalué
    r = en.compute_en16798_adaptive(*_cas_simple(40.0, trm_val=35.0))
    assert r["total_occupied_valid"] == 0
    assert r["occupied_out_of_range"] == 240
    assert np.isnan(r["discomfort_pct"])
    assert not r["trm_in_range"].any()
    # θrm = 12 : limite haute évaluée, mais pas la limite basse (< 15 °C)
    r = en.compute_en16798_adaptive(*_cas_simple(10.0, trm_val=12.0))
    assert r["total_occupied_valid"] == 240
    assert r["discomfort_hours_cold"] == 0
    assert not r["lower_applicable"].any()
    # Variante symétrique 10–33 °C : le froid est compté dès 10 °C
    r = en.compute_en16798_adaptive(*_cas_simple(10.0, trm_val=12.0),
                                    bandes=en.BANDES_SYMETRIQUES,
                                    trm_range=(10, 33), trm_range_lower=None)
    assert r["discomfort_hours_cold"] == 240


def test_compute_longueurs_differentes_et_nan():
    # Résultats Pléiades 8736 h vs météo 8760 h → troncature à la longueur commune
    t_ext = _t_ext_journalier([20.0] * 365)
    t_int = pd.Series(np.full(8736, 25.0))
    t_int.iloc[0] = np.nan                    # T manquante → heure non comptée
    occ = pd.Series(np.ones(8736, dtype=bool))
    r = en.compute_en16798_adaptive(t_int, t_ext, occ)
    assert len(r["trm_hourly"]) == 8736
    assert r["total_occupied_valid"] == 8735


def test_toutes_categories_et_indicateurs_plats():
    res = en.compute_toutes_categories(*_cas_simple(28.9))
    assert [res[c]["discomfort_hours"] for c in (1, 2, 3)] == [240, 240, 0]
    plats = en.indicateurs_plats(res)
    assert plats["discomfort_hours_catII"] == 240
    assert plats["discomfort_pct_catIII"] == 0.0
    assert "discomfort_hours_warm_catI" in plats


def test_tableau_multizones():
    t_int, t_ext, occ = _cas_simple(25.0)
    zones = [
        {"zone": "Bureau", "t_int": t_int, "occupied": occ, "surface": 20.0},
        {"zone": "Salle", "t_int": t_int + 5, "occupied": occ},
        {"zone": "Vide", "t_int": t_int, "occupied": ~occ},
    ]
    df = en.tableau_multizones(zones, t_ext, category=2)
    assert list(df["Zone"]) == ["Bureau", "Salle", "Vide"]
    assert list(df.columns) == ["Zone", "Surface (m²)", "Heures occupées", "Heures évaluées",
                                "Inconfort Cat.II (h)", "Inconfort Cat.II (%)",
                                "dont chaud (h)", "dont froid (h)"]
    assert df.loc[1, "dont chaud (h)"] == 240
    assert np.isnan(df.loc[1, "Surface (m²)"])
    assert np.isnan(df.loc[2, "Inconfort Cat.II (%)"])
