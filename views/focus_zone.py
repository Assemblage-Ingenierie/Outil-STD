"""Vue Niveau 2 — Focus sur une zone (comparaison variantes)."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from views.widgets import persist_multiselect, persist_selectbox
from config.charte import COULEURS_VARIANTES, GRIS, PLOTLY_LAYOUT


def render_focus_zone(variantes: list, seuil_t1: float, seuil_t2: float,
                      config: dict, methode: str = "givoni"):
    """Affiche l'analyse détaillée d'une zone pour toutes les variantes."""
    from charts.temperature import (
        graphique_temp_horaire,
        graphique_text_vs_text_op,
        graphique_apports_solaires,
        _serie_vers_horodate,
    )
    from charts.givoni import creer_givoni

    if not variantes:
        st.info("Chargez au moins une variante dans le panneau latéral.")
        return

    st.header("Focus zone")

    col1, col2 = st.columns([2, 2])
    with col1:
        all_zones = variantes[0].zones if variantes else []
        zone = persist_selectbox("Zone analysée", all_zones, "sel_focus_zone")
    with col2:
        noms = [v.nom for v in variantes]
        selected_noms = persist_multiselect("Variantes", noms,
                                            "sel_focus_variantes", defaut=noms)

    variantes_sel = [v for v in variantes if v.nom in selected_noms]
    if not variantes_sel or not zone:
        return

    # -- Indicateurs clés --
    st.subheader("Indicateurs clés")
    cols = st.columns(len(variantes_sel))
    for col_ui, var in zip(cols, variantes_sel):
        stats = var.stats_temp(zone)
        with col_ui:
            st.markdown(f"**{var.nom}**")
            st.metric("T min", f"{stats['t_min']:.1f} °C")
            st.metric("T moy", f"{stats['t_moy']:.1f} °C")
            st.metric("T max", f"{stats['t_max']:.1f} °C")
            lib = "COCO" if methode == "coco" else "Givoni"
            st.metric(f"H > {seuil_t1}°C", f"{var.heures_dessus_seuil(zone, seuil_t1)} h")
            st.metric(f"H > {seuil_t2}°C", f"{var.heures_dessus_seuil(zone, seuil_t2)} h")
            st.metric(f"H hors {lib} 0 m/s",
                      f"{var.heures_hors_confort(zone, config, 0.0, methode)} h")
            st.metric(f"H hors {lib} 1 m/s",
                      f"{var.heures_hors_confort(zone, config, 1.0, methode)} h")
            hr_vals = var.col_hr(zone)
            if not hr_vals.empty:
                st.metric("HR moy", f"{hr_vals.mean():.1f} %")

    st.divider()

    # -- Série temporelle température --
    st.subheader("Évolution horaire de la température")
    fig_temp = graphique_temp_horaire(variantes_sel, zone, seuil_t1, seuil_t2)
    st.plotly_chart(fig_temp, use_container_width=True)

    # -- T_op vs T_ext --
    st.subheader("Température opérative vs Température extérieure")
    var_op = persist_selectbox("Variante pour ce graphique",
                               [v.nom for v in variantes_sel], "sel_focus_var_op")
    var_sel = next(v for v in variantes_sel if v.nom == var_op)
    fig_op = graphique_text_vs_text_op(var_sel, zone)
    st.plotly_chart(fig_op, use_container_width=True)

    # -- Diagramme bioclimatique (Givoni / COCO) --
    nom_modele = "COCO" if methode == "coco" else "Givoni"
    st.subheader(f"Diagramme de {nom_modele} — Conditions extérieures")
    var_ref = persist_selectbox("Données météo (variante référence)",
                                [v.nom for v in variantes_sel], "sel_focus_givoni_ref")
    var_ref_obj = next(v for v in variantes_sel if v.nom == var_ref)

    if not var_ref_obj.df_meteo.empty:
        periode_options = {'Année entière': None, 'Été (mai-oct)': (5, 10), 'Hiver (nov-avr)': (11, 4)}
        periode_label = persist_selectbox("Période", list(periode_options.keys()),
                                          "sel_focus_givoni_periode")
        saison = var_ref_obj.df_horaire.get('saison')
        fig_giv = creer_givoni(
            var_ref_obj.df_meteo,
            config=config,
            methode=methode,
            saison=saison,
            periode=periode_options[periode_label],
        )
        st.plotly_chart(fig_giv, use_container_width=True)
    else:
        st.info("Fichier météo non chargé — diagramme non disponible.")

    # -- Apports solaires & internes --
    st.subheader("Apports solaires mensuels")
    fig_sol = graphique_apports_solaires(variantes_sel, zone, type_apport="solaires")
    st.plotly_chart(fig_sol, use_container_width=True)

    st.subheader("Apports internes mensuels (éclairage + occupants + équipements)")
    fig_int = graphique_apports_solaires(variantes_sel, zone, type_apport="internes")
    st.plotly_chart(fig_int, use_container_width=True)

    # -- Humidité relative --
    st.subheader("Humidité relative horaire")
    fig_hr = go.Figure()
    for i, var in enumerate(variantes_sel):
        s_hr = var.col_hr(zone)
        if s_hr.empty:
            continue
        x = _serie_vers_horodate(var.df_horaire)
        fig_hr.add_trace(go.Scatter(
            x=x, y=s_hr.values, mode='lines', name=var.nom,
            line=dict(color=COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)], width=1),
        ))
    layout = dict(PLOTLY_LAYOUT)
    layout.update(
        title=f'Humidité relative — {zone}',
        xaxis=dict(title='Date', gridcolor=GRIS),
        yaxis=dict(title='HR (%)', gridcolor=GRIS, range=[0, 100]),
        height=380,
    )
    fig_hr.update_layout(**layout)
    st.plotly_chart(fig_hr, use_container_width=True)
