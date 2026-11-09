"""
Tests de non-régression des optimisations issues de l'audit (branche perf) :

- mémoïsation de l'horodatage, des stats T°/HR, du test de confort (dedans/exempt)
  et de l'inconfort jour/nuit — avec invalidation correcte quand la période change ;
- équivalence du point-dans-polygone numpy (remplaçant matplotlib) ;
- dé-pickle restreint (sécurité) : roundtrip projet valide + refus d'une charge
  malveillante.
"""
import os
import pickle
import numpy as np
import pandas as pd
import pytest

from core import confort
from core.variante import Variante
from core.pickle_securise import charger_bytes_securise
from tests.test_nouvelles_fonctions import _variante


# ----------------------------------------------------------------------
# Horodatage mémoïsé
# ----------------------------------------------------------------------
def test_horodatage_memoise(tmp_path):
    v = _variante(tmp_path, ["A"], n_rows=48)
    h1 = v.horodatage()
    h2 = v.horodatage()
    assert h1 is h2                       # même objet (calcul unique)
    assert len(h1) == len(v.df_horaire)


# ----------------------------------------------------------------------
# Cache du test de confort : dans_zone calculé une seule fois par (zone, vitesse)
# ----------------------------------------------------------------------
def test_dedans_cache_un_seul_calcul(tmp_path, monkeypatch):
    v = _variante(tmp_path, ["A"], n_rows=48)
    appels = {"n": 0}
    vrai = confort.dans_zone

    def _compte(*a, **k):
        appels["n"] += 1
        return vrai(*a, **k)

    monkeypatch.setattr(confort, "dans_zone", _compte)

    n = len(v.df_horaire)
    masque_jour = v.masque_jour(n, 7.0, 22.0)
    # Deux décomptes à la même vitesse (jour puis nuit) → un seul point-dans-polygone
    v._compte_hors_occupe("A", {}, 0.0, "givoni", masque_extra=masque_jour)
    v._compte_hors_occupe("A", {}, 0.0, "givoni", masque_extra=~masque_jour)
    assert appels["n"] == 1               # le 2e appel réutilise le cache

    # inconfort_plages_horaires (0 et 1 m/s) : +1 seul appel (la vitesse 0 est déjà
    # en cache ; seule la vitesse 1 est nouvelle).
    v.inconfort_plages_horaires({}, "givoni", 7.0, 22.0)
    assert appels["n"] == 2


def test_inconfort_plages_cache_et_invalidation(tmp_path):
    v = _variante(tmp_path, ["A", "B"], n_rows=48)
    r1 = v.inconfort_plages_horaires({}, "givoni", 7.0, 22.0)
    r2 = v.inconfort_plages_horaires({}, "givoni", 7.0, 22.0)
    assert r1 is r2                       # même objet renvoyé (cache)
    # Changer de plage horaire → recalcul (nouvel objet)
    r3 = v.inconfort_plages_horaires({}, "givoni", 8.0, 20.0)
    assert r3 is not r1


# ----------------------------------------------------------------------
# Stats mémoïsées + invalidation quand la période est mutée en place
# ----------------------------------------------------------------------
def test_stats_temp_memoise_et_invalide_periode(tmp_path):
    v = _variante(tmp_path, ["A"], n_rows=48)      # T = 10 + r sur 48 h
    s_annee = v.stats_temp("A")
    assert v.stats_temp("A") is s_annee            # même objet (cache)
    tmax_annee = s_annee["t_max"]
    v.periode = (1, 1)                             # restreindre à janvier (mutation)
    s_jan = v.stats_temp("A")
    assert s_jan is not s_annee                    # clé (zone, periode) invalidée
    assert s_jan["t_max"] <= tmax_annee


# ----------------------------------------------------------------------
# Point-dans-polygone numpy : points connus + entrée vide
# ----------------------------------------------------------------------
def test_points_dans_polygone_connus():
    T, W = confort.polygone_zone({}, "givoni", 0.0)
    # Point clairement intérieur (23 °C, humidité modérée)
    w_in = confort.humidite_absolue(np.array([23.0]), np.array([50.0]))
    assert confort._points_dans_polygone(np.array([23.0]), w_in, T, W)[0]
    # Point clairement extérieur (40 °C, très humide)
    assert not confort._points_dans_polygone(
        np.array([40.0]), np.array([25.0]), T, W)[0]
    # Entrée vide → tableau booléen vide
    assert confort._points_dans_polygone(
        np.array([]), np.array([]), T, W).shape == (0,)


def test_dans_zone_polygone_absent_renvoie_faux():
    # Vitesse inexistante → polygone vide → tous hors zone
    res = confort.dans_zone(np.array([23.0, 24.0]), np.array([8.0, 9.0]),
                            {}, "givoni", 99.0)
    assert res.dtype == bool and not res.any()


# ----------------------------------------------------------------------
# Dé-pickle restreint
# ----------------------------------------------------------------------
def test_pickle_securise_bloque_charge_malveillante():
    class Evil:
        def __reduce__(self):
            return (os.system, ("echo pwned",))
    with pytest.raises(pickle.UnpicklingError):
        charger_bytes_securise(pickle.dumps(Evil()))


def test_pickle_securise_autorise_objets_simples():
    data = {"a": [1, 2, 3], "b": (4.0, "x"), "c": {1, 2}}
    assert charger_bytes_securise(pickle.dumps(data)) == data


def test_projet_roundtrip_securise(tmp_path):
    from core import projet as projet_io
    v = _variante(tmp_path, ["A", "B"], n_rows=48)
    chemin = tmp_path / "p.stdproj"
    projet_io.sauvegarder_projet(chemin, {
        "nom_projet": "P", "params": {"methode": "givoni"},
        "variantes": [v], "meteo_labels": {}, "selections": {"sel_focus_zone": "A"},
    })
    charge = projet_io.charger_projet(chemin)     # passe par l'Unpickler restreint
    vr = charge["variantes"][0]
    assert vr.zones == ["A", "B"]
    pd.testing.assert_frame_equal(vr.df_horaire, v.df_horaire)
    assert charge["selections"] == {"sel_focus_zone": "A"}


