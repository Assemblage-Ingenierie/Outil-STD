"""Vue Niveau 3 — Comparaison d'un échantillon de zones (une variante)."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from config.charte import ROUGE, get_layout, finalize_fig, bar_labels
from views.widgets import persist_multiselect, persist_selectbox, show_plotly


def render_comparaison_zones(variantes: list, seuil_t1: float, seuil_t2: float,
                             config: dict, methode: str = "givoni", dh_on: bool = False):
    """Comparaison d'un échantillon de zones sur une variante sélectionnée."""
    from charts.temperature import (
        graphique_temp_min_moy_max,
        graphique_heures_depassement,
        graphique_apports_par_zone_mensuel,
    )
    from charts.humidite import graphique_hr_min_moy_max

    if not variantes:
        st.info("Chargez au moins une variante dans le panneau latéral.")
        return

    st.header("Comparaison de zones")

    col1, col2 = st.columns([1, 2])
    with col1:
        var_nom = persist_selectbox("Variante", [v.nom for v in variantes],
                                    "sel_comp_variante")
    var = next(v for v in variantes if v.nom == var_nom)
    all_zones = var.zones

    with col2:
        zones_sel = persist_multiselect(
            "Zones à comparer (échantillon)", all_zones, "sel_comp_zones",
            defaut=all_zones[:min(6, len(all_zones))]
        )

    if not zones_sel:
        st.warning("Sélectionnez au moins une zone.")
        return

    # -- Tableau récapitulatif de l'échantillon --
    st.subheader("Récapitulatif de l'échantillon")
    lib = "COCO" if methode == "coco" else "Givoni"
    rows = []
    for zone in zones_sel:
        stats = var.stats_temp(zone)
        syn = var.synthese_zone(zone)
        rows.append({
            'Zone': zone,
            'Surface (m²)': round(syn['surface_m2'], 0) if syn and not np.isnan(syn.get('surface_m2', float('nan'))) else '',
            'Besoins ch. (kWh/m²)': round(syn['besoins_chaud_kwh_m2'], 1) if syn else '',
            'Besoins fr. (kWh/m²)': round(syn['besoins_froid_kwh_m2'], 1) if syn else '',
            'T min (°C)': round(stats['t_min'], 1),
            'T moy (°C)': round(stats['t_moy'], 1),
            'T max (°C)': round(stats['t_max'], 1),
            f'H > {seuil_t1}°C': var.heures_dessus_seuil(zone, seuil_t1),
            f'H > {seuil_t2}°C': var.heures_dessus_seuil(zone, seuil_t2),
            f'% hors {lib} 0 m/s': var.pct_hors_confort(zone, config, 0.0, methode),
            f'% hors {lib} 1 m/s': var.pct_hors_confort(zone, config, 1.0, methode),
            **({f'DH > {seuil_t1:.0f}°C (°C·h)': var.degre_heures(zone, seuil_t1)} if dh_on else {}),
        })

    df_comp = pd.DataFrame(rows)
    cols_pct_list = [c for c in df_comp.columns if c.startswith('% hors')]
    cols_couleur = [c for c in df_comp.columns if c.startswith('H >')] + cols_pct_list
    cols_pct = {c: '{:.1f} %' for c in cols_pct_list}
    for c in df_comp.columns:
        if c.startswith('DH'):
            cols_pct[c] = '{:.0f}'

    def _style_na(col):
        return ['background-color:#FFFFFF; color:#9E9E9E; font-style:italic'
                if v != v else '' for v in col]

    _dec = ',' if st.session_state.get('cfg_format_fr', True) else '.'
    st.dataframe(
        df_comp.style.format(cols_pct, na_rep='NA', decimal=_dec, thousands=' ', precision=1)
                     .background_gradient(subset=cols_couleur, cmap='YlOrRd')
                     .apply(_style_na, subset=cols_pct_list),
        width='stretch',
        height=min(600, 60 + 35 * len(df_comp)),
    )
    st.caption("« % hors » = part des heures d'occupation hors zone de confort. "
               "« NA » : local non occupé.")

    csv = df_comp.to_csv(index=False).encode('utf-8-sig')
    st.download_button("⬇️ Exporter CSV", data=csv,
                       file_name=f"comparaison_zones_{var.nom}.csv",
                       mime="text/csv", key="dl_comp")

    # -- Confort adaptatif EN 16798-1 --
    st.subheader("Confort adaptatif EN 16798-1")
    from views.focus_zone import choisir_categorie_en16798
    from core import confort_en16798
    cat = choisir_categorie_en16798()
    t_ext = var.t_ext_horaire()
    if not len(t_ext):
        st.info("Confort adaptatif indisponible : aucune température extérieure "
                "(météo .try ou colonne T extérieure des résultats).")
    else:
        zones_en = []
        for zone in zones_sel:
            t = var.col_temp(zone)
            occ = var.col_apports_occupants(zone)
            if t.empty or occ.empty:
                continue
            n = min(len(t), len(occ))
            syn = var.synthese_zone(zone)
            zones_en.append({
                'zone': zone, 't_int': t.iloc[:n],
                'occupied': (occ.values[:n] > 0) & var.masque_periode(n),
                'surface': syn.get('surface_m2', np.nan) if syn else np.nan,
            })
        df_en = confort_en16798.tableau_multizones(zones_en, t_ext, cat)
        if df_en.empty:
            st.info("Aucune zone exploitable (température ou occupation manquante).")
        else:
            col_pct = [c for c in df_en.columns if c.endswith('(%)')]
            st.dataframe(
                df_en.style.format({'Surface (m²)': '{:.0f}', **{c: '{:.1f} %' for c in col_pct}},
                                   na_rep='NA', decimal=_dec, thousands=' ')
                .background_gradient(subset=col_pct, cmap='YlOrRd'),
                width='stretch', hide_index=True,
                height=min(600, 60 + 35 * len(df_en)),
            )
            st.caption("Heures évaluées = heures occupées où θrm est dans le domaine "
                       "d'application (10–30 °C). « NA » : aucune heure évaluée.")
            st.download_button("⬇️ Exporter CSV", data=df_en.to_csv(index=False).encode('utf-8-sig'),
                               file_name=f"en16798_zones_{var.nom}.csv",
                               mime="text/csv", key="dl_comp_en16798")

    st.divider()

    # -- Températures min/moy/max en barres --
    st.subheader("Températures min / moyenne / max par zone")
    fig_t = graphique_temp_min_moy_max([var], zones_sel)
    show_plotly(fig_t, width='stretch')

    # -- Humidité relative min/moy/max en barres --
    st.subheader("Humidité relative min / moyenne / max par zone")
    fig_hr = graphique_hr_min_moy_max([var], zones_sel)
    show_plotly(fig_hr, width='stretch')

    # -- Heures de dépassement --
    st.subheader("Heures de dépassement")
    fig_dep = graphique_heures_depassement([var], zones_sel, seuil_t1, seuil_t2)
    show_plotly(fig_dep, width='stretch')

    # -- Besoins annuels --
    st.subheader("Besoins annuels par zone")
    if all(var.synthese_zone(z) is not None for z in zones_sel):
        fig_bes = go.Figure()
        besoins_ch = [var.synthese_zone(z)['besoins_chaud_kwh_m2'] for z in zones_sel]
        besoins_fr = [var.synthese_zone(z)['besoins_froid_kwh_m2'] for z in zones_sel]
        fig_bes.add_trace(go.Bar(x=zones_sel, y=besoins_ch, name='Chauffage',
                                 marker_color=ROUGE, **bar_labels()))
        fig_bes.add_trace(go.Bar(x=zones_sel, y=besoins_fr, name='Climatisation',
                                 marker_color='#2196F3', **bar_labels()))
        layout = get_layout()
        layout.update(title='Besoins annuels par zone (kWh/m²)', xaxis=dict(tickangle=-30),
                      yaxis=dict(title='kWh/m²'), barmode='group', height=400,
                      uniformtext=dict(minsize=8, mode='hide'))
        fig_bes.update_layout(**layout)
        show_plotly(finalize_fig(fig_bes), width='stretch')

    # -- Apports solaires mensuels : une barre par mois par zone --
    st.subheader("Apports solaires mensuels par zone")
    fig_sol = graphique_apports_par_zone_mensuel(var, zones_sel, type_apport="solaires")
    show_plotly(fig_sol, width='stretch')

    # -- Apports internes mensuels : une barre par mois par zone --
    st.subheader("Apports internes mensuels par zone (éclairage + occupants + équipements)")
    fig_int = graphique_apports_par_zone_mensuel(var, zones_sel, type_apport="internes")
    show_plotly(fig_int, width='stretch')
