"""Vue Niveau 2 — Focus sur une zone (comparaison variantes)."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from views.widgets import persist_multiselect, persist_selectbox
from config.charte import COULEURS_VARIANTES, GRILLE, PLOTLY_LAYOUT


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

            def _fmt_pct(v):
                return f"{v:.1f} %" if v == v else "— (non occupé)"

            st.metric(f"H > {seuil_t1}°C", f"{var.heures_dessus_seuil(zone, seuil_t1)} h")
            st.metric(f"H > {seuil_t2}°C", f"{var.heures_dessus_seuil(zone, seuil_t2)} h")
            st.metric(f"% hors {lib} 0 m/s",
                      _fmt_pct(var.pct_hors_confort(zone, config, 0.0, methode)))
            st.metric(f"% hors {lib} 1 m/s",
                      _fmt_pct(var.pct_hors_confort(zone, config, 1.0, methode)))
            st.caption(f"{var.heures_occupation(zone)} h d'occupation/an")
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

    # -- Diagramme bioclimatique (Givoni / COCO) — conditions INTÉRIEURES --
    nom_modele = "COCO" if methode == "coco" else "Givoni"
    st.subheader(f"Diagramme de {nom_modele} — Conditions intérieures de la zone")
    st.caption("Points = conditions intérieures horaires de la zone. Les heures de "
               "saison de chauffe sous la consigne (T < min confort) sont écartées.")

    series = []
    for v in variantes_sel:
        pts = v.points_interieurs_givoni(zone, config, methode)
        if len(pts['T']):
            pts['label'] = v.nom
            series.append(pts)

    if series:
        fig_giv = creer_givoni(series, config=config, methode=methode)
        st.plotly_chart(fig_giv, use_container_width=True)
        if len(series) > 1:
            st.caption("Plusieurs variantes : une couleur par variante. "
                       "Sélectionnez une seule variante pour une coloration par saison.")
    else:
        st.info("Données intérieures indisponibles pour cette zone.")

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
        xaxis=dict(title='Date', gridcolor=GRILLE),
        yaxis=dict(title='HR (%)', gridcolor=GRILLE, range=[0, 100]),
        height=380,
    )
    fig_hr.update_layout(**layout)
    st.plotly_chart(fig_hr, use_container_width=True)
