"""Tests des indicateurs et du graphique d'humidité relative (HR)."""
import numpy as np
import pandas as pd
import pytest

from core.slk_parser import parse_resultats
from core.variante import Variante
from tests.test_perf_optims import _resultats_lignes, _ecrire


def _variante_hr(tmp_path, zones, n_rows=24, surfaces=None):
    """Variante minimale parsée depuis un SLK synthétique.
    _resultats_lignes fixe HR = 50 + indice de zone (constante sur les lignes)."""
    f = _ecrire(tmp_path, _resultats_lignes(zones, n_rows, lambda i, r: 20.0 + i + r))
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


def test_stats_hr_constante_par_zone(tmp_path):
    v = _variante_hr(tmp_path, ["A", "B"])
    sa = v.stats_hr("A")
    assert sa["hr_min"] == pytest.approx(50.0)
    assert sa["hr_moy"] == pytest.approx(50.0)
    assert sa["hr_max"] == pytest.approx(50.0)
    assert v.stats_hr("B")["hr_min"] == pytest.approx(51.0)


def test_stats_hr_zone_absente(tmp_path):
    v = _variante_hr(tmp_path, ["A"])
    s = v.stats_hr("ZZZ")
    assert np.isnan(s["hr_min"]) and np.isnan(s["hr_moy"]) and np.isnan(s["hr_max"])


def test_indicateurs_batiment_hr_ponderee_surface(tmp_path):
    # HR A=50 (surf 10), HR B=51 (surf 30) → moy pondérée = 50.75 → arrondi 51
    v = _variante_hr(tmp_path, ["A", "B"], surfaces=[10.0, 30.0])
    ind = v.indicateurs_batiment({}, "givoni")
    assert ind["HR min (%)"] == pytest.approx(50.0)
    assert ind["HR max (%)"] == pytest.approx(51.0)
    assert ind["HR moy (%)"] == pytest.approx(51.0)


def test_graphique_hr_horaire_smoke(tmp_path):
    from charts.humidite import graphique_hr_horaire
    v = _variante_hr(tmp_path, ["A", "B"])
    fig = graphique_hr_horaire([v], "A")
    assert any(tr.name == "v" for tr in fig.data)          # courbe intérieure zone A
    fig2 = graphique_hr_horaire([v], "A", occupation_seulement=True, agregation="horaire")
    assert fig2 is not None                                # filtre occupation : pas de crash


def test_graphique_hr_min_moy_max_smoke(tmp_path):
    from charts.humidite import graphique_hr_min_moy_max
    v = _variante_hr(tmp_path, ["A", "B"])
    fig = graphique_hr_min_moy_max([v], ["A", "B"])
    # 3 barres (min/moy/max) attendues
    noms = {tr.name for tr in fig.data}
    assert {"HR min", "HR moy", "HR max"} <= noms


def test_graphique_hr_axe_date_et_rangeslider(tmp_path):
    """Régression : l'axe X doit être typé 'date' (sinon plotly.js infère un axe
    linéaire à cause du marqueur de légende x=[None] → graphe vide). Le mode
    horaire active en plus le rangeslider de navigation."""
    from charts.humidite import graphique_hr_horaire
    v = _variante_hr(tmp_path, ["A"])
    fig_j = graphique_hr_horaire([v], "A", agregation="journalier")
    assert fig_j.layout.xaxis.type == "date"
    fig_h = graphique_hr_horaire([v], "A", agregation="horaire")
    assert fig_h.layout.xaxis.type == "date"
    assert fig_h.layout.xaxis.rangeslider.visible is True


def test_heatmap_hr_jour_heure_smoke(tmp_path):
    import plotly.graph_objects as go
    from charts.humidite import heatmap_hr_jour_heure
    v = _variante_hr(tmp_path, ["A", "B"])
    fig = heatmap_hr_jour_heure(v, "A")
    assert fig is not None
    assert any(isinstance(tr, go.Heatmap) for tr in fig.data)
    assert heatmap_hr_jour_heure(v, "ZZZ") is None      # zone absente → None
