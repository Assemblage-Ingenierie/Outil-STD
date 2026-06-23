"""
Tests de non-régression des optimisations de performance (chargement + calcul) :
- parser orienté-colonnes : tolérance aux cellules manquantes (alignement), en-tête
  bornée, sémantique de K inchangée ;
- cache disque L2 : roundtrip préservant valeurs/attrs ;
- synthese_zone : 1re occurrence sur zone dupliquée ;
- masque_periode : invalidation quand periode est mutée en place ;
- confort.zones_modele : mémoïsation correcte par configuration.
"""
import numpy as np
import pandas as pd
import pytest

from core.slk_parser import parse_resultats
from core.variante import Variante
from core import confort, cache_disque


def _cell(row, col, val):
    if isinstance(val, str):
        return f'C;Y{row};X{col};K"{val}"\n'
    return f'C;Y{row};X{col};K{val}\n'


def _resultats_lignes(zones, n_rows, t_zone):
    """
    Construit les lignes d'un SLK résultats 1 grandeur/zone minimal valide
    (Température, HR, Apports occupants), avec une fonction t_zone(i, r) pour la
    température de la zone i à la ligne r — permet des valeurs distinctes par ligne
    pour tester l'alignement.
    Retourne la liste de lignes (modifiable avant écriture).
    """
    nz = len(zones)
    lines = ["ID;PWXL;N;E\n"]
    lines.append(_cell(1, 1, "Mois")); lines.append(_cell(1, 2, "Jour")); lines.append(_cell(1, 3, "Heure"))
    lines.append(_cell(1, 4, "Températures"))
    for i in range(nz):
        lines.append(_cell(1, 5 + i,        "Température (°C)"))
        lines.append(_cell(1, 5 + nz + i,   "Humidité relative (%)"))
        lines.append(_cell(1, 5 + 2*nz + i, "Apports occupants (W)"))
    lines.append(_cell(2, 4, ""))
    for i, z in enumerate(zones):
        lines.append(_cell(2, 5 + i,        z))
        lines.append(_cell(2, 5 + nz + i,   z))
        lines.append(_cell(2, 5 + 2*nz + i, z))
    for r in range(n_rows):
        row = 3 + r
        lines.append(_cell(row, 1, (r % 12) + 1))
        lines.append(_cell(row, 2, (r % 28) + 1))
        lines.append(_cell(row, 3, (r % 24) + 1))
        lines.append(_cell(row, 4, 15.0 + r))
        for i in range(nz):
            lines.append(_cell(row, 5 + i,        t_zone(i, r)))
            lines.append(_cell(row, 5 + nz + i,   50.0 + i))
            lines.append(_cell(row, 5 + 2*nz + i, 100.0 * (r % 2)))
    lines.append("E\n")
    return lines


def _ecrire(tmp_path, lines, nom="r.slk"):
    f = tmp_path / nom
    f.write_text("".join(lines), encoding="latin-1")
    return f


# ---------------------------------------------------------------------------
# Parser : alignement préservé quand une cellule manque (tolérance aux trous)
# ---------------------------------------------------------------------------

def test_parser_cellule_manquante_garde_alignement(tmp_path):
    # Température de la zone = 100 + r → distincte par ligne
    lines = _resultats_lignes(["Z"], n_rows=4, t_zone=lambda i, r: 100.0 + r)
    # Retirer la cellule Température de la 2e ligne de données (row=4 → r=1)
    cible = _cell(4, 5, 101.0)
    lines = [ln for ln in lines if ln != cible]
    f = _ecrire(tmp_path, lines)

    df = parse_resultats(f)
    col = "Température (°C)|Z"
    assert len(df) == 4
    assert df[col].iloc[0] == pytest.approx(100.0)   # r=0
    assert np.isnan(df[col].iloc[1])                 # r=1 : cellule manquante → NaN
    assert df[col].iloc[2] == pytest.approx(102.0)   # r=2 : PAS décalé
    assert df[col].iloc[3] == pytest.approx(103.0)   # r=3


def test_parser_entete_bornee_detecte_zones(tmp_path):
    lines = _resultats_lignes(["Séjour", "Chambre"], n_rows=3, t_zone=lambda i, r: 20.0 + i + r)
    f = _ecrire(tmp_path, lines)
    df = parse_resultats(f)
    assert set(df.attrs["zones"]) == {"Séjour", "Chambre"}
    assert df["Température (°C)|Séjour"].iloc[0] == pytest.approx(20.0)
    assert df["Humidité relative (%)|Chambre"].iloc[0] == pytest.approx(51.0)


def test_parser_K_tronque_au_point_virgule(tmp_path):
    """Sémantique de K inchangée : un libellé avec ';' interne reste tronqué au ';'
    (comportement de la regex historique), donc la zone est nommée sans le suffixe."""
    lines = _resultats_lignes(["Bureau"], n_rows=2, t_zone=lambda i, r: 20.0 + r)
    # Remplacer le nom de zone Y2 par un libellé contenant un ';' interne
    lines = [ln.replace('K"Bureau"', 'K"Bureau;RDC"') for ln in lines]
    f = _ecrire(tmp_path, lines)
    df = parse_resultats(f)
    zones = df.attrs["zones"]
    # La regex coupe au ';' → le nom retenu commence par '"Bureau' (guillemet non fermé)
    assert len(zones) == 1
    assert ";" not in zones[0]


# ---------------------------------------------------------------------------
# Cache disque L2 : roundtrip
# ---------------------------------------------------------------------------

def test_cache_disque_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_disque, "_dossier_cache", lambda: tmp_path)
    res = _ecrire(tmp_path, _resultats_lignes(["Z"], 3, lambda i, r: 20.0 + r), "res.slk")
    df = parse_resultats(res)
    syn = pd.DataFrame([{"zone": "Z", "surface_m2": 10.0}])
    met = pd.DataFrame(columns=["T_ext"])

    assert cache_disque.charger(str(res), "", "") is None  # rien en cache
    cache_disque.ecrire(str(res), "", "", df, syn, met,
                        df.attrs.get("zones"), df.attrs.get("groupes"), "meteo.try")
    bundle = cache_disque.charger(str(res), "", "")
    assert bundle is not None
    assert bundle["meteo_nom"] == "meteo.try"
    assert list(bundle["zones"]) == ["Z"]
    pd.testing.assert_frame_equal(bundle["df_horaire"], df)


def test_cache_disque_invalide_si_mtime_change(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_disque, "_dossier_cache", lambda: tmp_path)
    res = _ecrire(tmp_path, _resultats_lignes(["Z"], 3, lambda i, r: 20.0 + r), "res2.slk")
    df = parse_resultats(res)
    cache_disque.ecrire(str(res), "", "", df, df, pd.DataFrame(),
                        df.attrs.get("zones"), df.attrs.get("groupes"), "")
    assert cache_disque.charger(str(res), "", "") is not None
    # Réécrire le fichier (mtime + taille changent) → cache invalidé
    res.write_text("".join(_resultats_lignes(["Z"], 5, lambda i, r: 20.0 + r)), encoding="latin-1")
    assert cache_disque.charger(str(res), "", "") is None


# ---------------------------------------------------------------------------
# Variante : synthese_zone (1re occurrence) + invalidation masque_periode
# ---------------------------------------------------------------------------

def _variante_minimale(periode=None, df_synthese=None):
    n = 12
    df_h = pd.DataFrame({"mois": list(range(1, n + 1))})
    df_s = df_synthese if df_synthese is not None else pd.DataFrame(columns=["zone"])
    df_m = pd.DataFrame(columns=["T_ext"])
    return Variante(nom="v", df_horaire=df_h, df_synthese=df_s, df_meteo=df_m,
                    zones=[], periode=periode)


def test_synthese_zone_premiere_occurrence():
    df_s = pd.DataFrame([
        {"zone": "A", "surface_m2": 10.0},
        {"zone": "A", "surface_m2": 99.0},   # doublon : doit être ignoré
        {"zone": "B", "surface_m2": 20.0},
    ])
    v = _variante_minimale(df_synthese=df_s)
    assert v.synthese_zone("A")["surface_m2"] == pytest.approx(10.0)  # 1re occurrence
    assert v.synthese_zone("B")["surface_m2"] == pytest.approx(20.0)
    assert v.synthese_zone("Z") is None


def test_masque_periode_invalide_quand_periode_mutee():
    v = _variante_minimale(periode=(6, 8))
    m1 = v.masque_periode()
    assert m1.sum() == 3                       # juin, juillet, août
    v.periode = (1, 2)                         # mutation en place (comme app.py)
    m2 = v.masque_periode()
    assert m2.sum() == 2                       # janvier, février
    assert not np.array_equal(m1, m2)


# ---------------------------------------------------------------------------
# confort.zones_modele : mémoïsation par configuration
# ---------------------------------------------------------------------------

def test_zones_modele_memoise_meme_objet():
    z1 = confort.zones_modele({}, "givoni")
    z2 = confort.zones_modele({}, "givoni")
    assert z1 is z2   # même objet renvoyé (cache)


def test_zones_modele_config_differente_polygone_different():
    base = confort.zones_modele({}, "givoni")
    override = confort.zones_modele({"givoni": {"hr_max_zones": [60, 60, 60, 60]}}, "givoni")
    assert base is not override
    # HR max abaissée → w (humidité absolue) max du 1er polygone plus faible
    assert override[0][3].max() < base[0][3].max()
