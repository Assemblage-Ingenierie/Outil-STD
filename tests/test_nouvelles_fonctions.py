"""Tests des fonctionnalités ajoutées :
- seuil T0 / heures sous seuil
- heures de dépassement pondérées surface au niveau bâtiment
- inconfort par plage horaire jour / nuit
- périodes de focus (points + récap)
- carte de température jour × heure
- coloration Givoni par période
"""
import numpy as np
import pandas as pd
import pytest

from core.slk_parser import parse_resultats
from core.variante import Variante
from tests.test_perf_optims import _resultats_lignes, _ecrire


def _variante(tmp_path, zones, n_rows=24, surfaces=None, t_zone=None):
    """Variante synthétique. Par défaut T zone i, ligne r = 10 + i + r."""
    if t_zone is None:
        t_zone = lambda i, r: 10.0 + i + r
    f = _ecrire(tmp_path, _resultats_lignes(zones, n_rows, t_zone))
    df = parse_resultats(f)
    rows = []
    for i, z in enumerate(zones):
        surf = surfaces[i] if surfaces else 10.0
        rows.append({"zone": z, "surface_m2": surf,
                     "besoins_chaud_kwh": 0.0, "besoins_froid_kwh": 0.0,
                     "besoins_chaud_kwh_m2": 0.0, "besoins_froid_kwh_m2": 0.0})
    syn = pd.DataFrame(rows)
    return Variante(nom="v", df_horaire=df, df_synthese=syn,
                    df_meteo=pd.DataFrame(columns=["T_ext", "HR_ext"]),
                    zones=list(zones))


# ----------------------------------------------------------------------
# Seuil T0 / heures sous seuil
# ----------------------------------------------------------------------
def test_heures_sous_seuil(tmp_path):
    # Zone A : T = 10..33 → sous 18 = r 0..7 = 8 heures
    v = _variante(tmp_path, ["A"], n_rows=24)
    assert v.heures_sous_seuil("A", 18.0) == 8
    assert v.heures_sous_seuil("A", 10.0) == 0      # rien strictement sous le min
    assert v.heures_sous_seuil("ZZZ", 18.0) == 0    # zone absente


# ----------------------------------------------------------------------
# Heures de dépassement pondérées surface (niveau bâtiment)
# ----------------------------------------------------------------------
def test_indicateurs_batiment_heures_ponderees_surface(tmp_path):
    # A (surf 10) : T 10..33 ; B (surf 30) : T 11..34
    v = _variante(tmp_path, ["A", "B"], n_rows=24, surfaces=[10.0, 30.0])
    ind = v.indicateurs_batiment({}, "givoni", seuil_t0=18.0, seuil_t1=26.0, seuil_t2=30.0)
    # H < 18 : A=8, B=7 → (8*10+7*30)/40 = 7.25 → 7
    assert ind["H < 18°C"] == pytest.approx(7.0)
    # H > 26 : A=7, B=8 → (7*10+8*30)/40 = 7.75 → 8
    assert ind["H > 26°C"] == pytest.approx(8.0)
    # H > 30 : A=3, B=4 → 3.75 → 4
    assert ind["H > 30°C"] == pytest.approx(4.0)


def test_indicateurs_batiment_sans_seuils_inchange(tmp_path):
    # Sans seuils fournis, aucune colonne d'heures n'est ajoutée (compat. ascendante)
    v = _variante(tmp_path, ["A"])
    ind = v.indicateurs_batiment({}, "givoni")
    assert not any(k.startswith(("H < ", "H > ")) for k in ind)


# ----------------------------------------------------------------------
# Masques jour / nuit et mois
# ----------------------------------------------------------------------
def test_masque_jour(tmp_path):
    v = _variante(tmp_path, ["A"], n_rows=24)
    mj = v.masque_jour(24, 7.0, 22.0)
    # heure du jour = r (0..23) ; jour = [7, 22) → 15 heures
    assert mj.sum() == 15
    # plage à cheval sur minuit : [22, 7) → 9 heures
    mc = v.masque_jour(24, 22.0, 7.0)
    assert mc.sum() == 9


def test_masque_mois_periode_cheval_annee(tmp_path):
    v = _variante(tmp_path, ["A"], n_rows=24)
    # mois = (r % 12) + 1 sur 24 lignes → chaque mois apparaît 2 fois
    m_ete = v.masque_mois_periode(24, 5, 10)      # mai..oct = 6 mois × 2 = 12
    assert m_ete.sum() == 12
    m_hiv = v.masque_mois_periode(24, 11, 4)      # nov..avr (cheval) = 6 mois × 2 = 12
    assert m_hiv.sum() == 12


# ----------------------------------------------------------------------
# Inconfort par plage horaire jour / nuit
# ----------------------------------------------------------------------
def test_inconfort_plages_horaires_structure(tmp_path):
    v = _variante(tmp_path, ["A", "B"], surfaces=[10.0, 30.0])
    dn = v.inconfort_plages_horaires({}, "givoni", 7.0, 22.0)
    attendu = {'% inconfort jour 0 m/s', '% inconfort nuit 0 m/s',
               '% inconfort jour 1 m/s', '% inconfort nuit 1 m/s'}
    assert set(dn.keys()) == attendu
    for v_ in dn.values():
        assert np.isnan(v_) or (0.0 <= v_ <= 100.0)


# ----------------------------------------------------------------------
# Périodes de focus
# ----------------------------------------------------------------------
def test_inconfort_periodes(tmp_path):
    v = _variante(tmp_path, ["A"], n_rows=24)
    periodes = [{'nom': 'P1', 'm1': 1, 'm2': 6}, {'nom': 'P2', 'm1': 7, 'm2': 12}]
    rows = v.inconfort_periodes("A", {}, periodes, "givoni")
    assert [r['periode'] for r in rows] == ['P1', 'P2']
    for r in rows:
        assert r['heures_occ'] >= 0
        assert np.isnan(r['pct']) or (0.0 <= r['pct'] <= 100.0)


def test_points_interieurs_par_periode(tmp_path):
    v = _variante(tmp_path, ["A"], n_rows=24)
    periodes = [{'nom': 'P1', 'm1': 1, 'm2': 6}, {'nom': 'P2', 'm1': 7, 'm2': 12}]
    pts = v.points_interieurs_par_periode("A", {}, periodes, "givoni")
    assert len(pts['T']) == len(pts['w']) == len(pts['periode'])
    # toutes les étiquettes appartiennent aux périodes définies (pas de '' ici :
    # les 12 mois sont couverts par P1 ∪ P2)
    assert set(np.unique(pts['periode'])) <= {'P1', 'P2'}


# ----------------------------------------------------------------------
# Graphiques
# ----------------------------------------------------------------------
def test_heatmap_temp_jour_heure_smoke(tmp_path):
    import plotly.graph_objects as go
    from charts.temperature import heatmap_temp_jour_heure
    v = _variante(tmp_path, ["A", "B"])
    fig = heatmap_temp_jour_heure(v, "A", zmin=10.0, zmax=35.0)
    assert fig is not None
    assert any(isinstance(tr, go.Heatmap) for tr in fig.data)
    assert heatmap_temp_jour_heure(v, "ZZZ") is None       # zone absente → None


def test_a_chauffage_et_note_givoni(tmp_path):
    from charts.givoni import creer_givoni
    v = _variante(tmp_path, ["A"], n_rows=24)
    pts = v.points_interieurs_givoni("A", {}, "givoni")
    pts['label'] = "A"

    # Fixture synthétique : ni saison de chauffe ni P chauffage → note absente
    assert v.a_chauffage() is False
    fig_sans = creer_givoni([pts], config={}, methode="givoni",
                            note_chauffe=v.a_chauffage())
    assert not any("Hypothèse" in (a.text or "") for a in fig_sans.layout.annotations)

    # Saison de chauffe injectée → détectée
    v.df_horaire['saison'] = ['Chauffage'] * len(v.df_horaire)
    assert v.a_chauffage() is True
    fig_avec = creer_givoni([pts], config={}, methode="givoni",
                            note_chauffe=v.a_chauffage())
    assert any("Hypothèse" in (a.text or "") for a in fig_avec.layout.annotations)


def test_a_chauffage_via_puissance_chauffage(tmp_path):
    # Saison vide mais P chauffage > 0 → chauffage détecté (cas export Pléiades réel)
    v = _variante(tmp_path, ["A"], n_rows=24)
    assert v.a_chauffage() is False
    v.df_horaire["P Chauffage (W)|A"] = [500.0] * len(v.df_horaire)
    assert v.a_chauffage() is True


def test_creer_givoni_par_periode_smoke(tmp_path):
    from charts.givoni import creer_givoni
    v = _variante(tmp_path, ["A"], n_rows=24)
    periodes = [{'nom': 'P1', 'm1': 1, 'm2': 6}, {'nom': 'P2', 'm1': 7, 'm2': 12}]
    pts = v.points_interieurs_par_periode("A", {}, periodes, "givoni")
    pts['label'] = "A"
    fig = creer_givoni([pts], config={}, methode="givoni", par_periode=True)
    noms = {tr.name for tr in fig.data}
    # les deux périodes apparaissent comme traces de points distinctes
    assert {'P1', 'P2'} <= noms


# ----------------------------------------------------------------------
# Export Word : robustesse au nom de projet vide (régression)
# ----------------------------------------------------------------------
def test_rapport_word_nom_projet_vide(tmp_path):
    """Un nom de projet vide ne doit pas planter la génération du rapport.
    Auparavant : add_paragraph('') ne créait aucun run → runs[0] levait
    « list index out of range »."""
    from export.word_report import generer_rapport
    v = _variante(tmp_path, ["A"], n_rows=24)
    for nom in ("", "Mon Projet"):
        buf = generer_rapport(variantes=[v], config={}, seuil_t1=26.0, seuil_t2=28.0,
                              zones_focus=[], zones_comparaison=[], nom_projet=nom,
                              methode="givoni")
        assert buf.getvalue()   # buffer non vide
