"""Vue Niveau 3 — Comparaison d'un échantillon de zones (une variante)."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from config.charte import COULEURS_VARIANTES, GRIS, ROUGE, PLOTLY_LAYOUT


def render_comparaison_zones(variantes: list, seuil_t1: float, seuil_t2: float):
    """Comparaison d'un échantillon de zones sur une variante sélectionnée."""
    from charts.temperature import (
        graphique_boite_temp,
        graphique_heures_depassement,
        graphique_apports_solaires,
    )

    if not variantes:
        st.info("Chargez au moins une variante dans le panneau latéral.")
        return

    st.header("Comparaison de zones")

    col1, col2 = st.columns([1, 2])
    with col1:
        var_nom = st.selectbox("Variante", [v.nom for v in variantes], key="comp_variante")

    var = next(v for v in variantes if v.nom == var_nom)
    all_zones = var.zones

    with col2:
        zones_sel = st.multiselect(
            "Zones à comparer (échantillon)",
            all_zones,
            default=all_zones[:min(6, len(all_zones))],
            key="comp_zones"
        )

    if not zones_sel:
        st.warning("Sélectionnez au moins une zone.")
        return

    # -- Tableau récapitulatif de l'échantillon --
    st.subheader("Récapitulatif de l'échantillon")
    rows = []
    for zone in zones_sel:
        stats = var.stats_temp(zone)
        syn = var.synthese_zone(zone)
        hr = var.col_hr(zone)
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
            'HR moy (%)': round(float(hr.mean()), 1) if not hr.empty else '',
        })

    df_comp = pd.DataFrame(rows)
    st.dataframe(
        df_comp.style.background_gradient(
            subset=[f'H > {seuil_t1}°C', f'H > {seuil_t2}°C'], cmap='YlOrRd'
        ),
        use_container_width=True,
    )

    csv = df_comp.to_csv(index=False).encode('utf-8-sig')
    st.download_button("⬇️ Exporter CSV", data=csv,
                       file_name=f"comparaison_zones_{var.nom}.csv",
                       mime="text/csv")

    st.divider()

    # -- Graphiques --
    st.subheader("Distribution des températures")
    fig_boite = graphique_boite_temp([var], zones_sel)
    st.plotly_chart(fig_boite, use_container_width=True)

    st.subheader("Heures de dépassement")
    fig_dep = graphique_heures_depassement([var], zones_sel, seuil_t1, seuil_t2)
    st.plotly_chart(fig_dep, use_container_width=True)

    st.subheader("Besoins annuels")
    if all(var.synthese_zone(z) is not None for z in zones_sel):
        fig_bes = go.Figure()
        besoins_ch = [var.synthese_zone(z)['besoins_chaud_kwh_m2'] for z in zones_sel]
        besoins_fr = [var.synthese_zone(z)['besoins_froid_kwh_m2'] for z in zones_sel]
        fig_bes.add_trace(go.Bar(x=zones_sel, y=besoins_ch, name='Chauffage',
                                  marker_color='#2196F3'))
        fig_bes.add_trace(go.Bar(x=zones_sel, y=besoins_fr, name='Climatisation',
                                  marker_color=ROUGE))
        layout = dict(PLOTLY_LAYOUT)
        layout.update(
            title='Besoins annuels par zone (kWh/m²)',
            xaxis=dict(tickangle=-30),
            yaxis=dict(title='kWh/m²'),
            barmode='group', height=400,
        )
        fig_bes.update_layout(**layout)
        st.plotly_chart(fig_bes, use_container_width=True)

    st.subheader("Apports solaires mensuels")
    zone_sol = st.selectbox("Zone pour apports solaires", zones_sel, key="comp_sol_zone")
    fig_sol = graphique_apports_solaires([var], zone_sol)
    st.plotly_chart(fig_sol, use_container_width=True)
