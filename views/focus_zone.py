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
        graphique_meteo_comparaison,
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
                                            "sel_focus_variantes", defaut=noms,
                                            placeholder="Rechercher / sélectionner des variantes…")

    variantes_sel = [v for v in variantes if v.nom in selected_noms]
    if not variantes_sel or not zone:
        return

    lib = "COCO" if methode == "coco" else "Givoni"

    # -- Tableau comparatif : une ligne par variante (pour la zone choisie) --
    st.subheader(f"Comparatif des variantes — {zone}")
    rows = []
    for var in variantes_sel:
        stats = var.stats_temp(zone)
        syn = var.synthese_zone(zone)
        hr = var.col_hr(zone)
        rows.append({
            'Variante': var.nom,
            'Surface (m²)': round(syn['surface_m2'], 0) if syn and not np.isnan(syn.get('surface_m2', float('nan'))) else np.nan,
            'Besoins ch. (kWh/m²)': round(syn['besoins_chaud_kwh_m2'], 1) if syn else np.nan,
            'Besoins fr. (kWh/m²)': round(syn['besoins_froid_kwh_m2'], 1) if syn else np.nan,
            'T min (°C)': round(stats['t_min'], 1),
            'T moy (°C)': round(stats['t_moy'], 1),
            'T max (°C)': round(stats['t_max'], 1),
            f'H > {seuil_t1}°C': var.heures_dessus_seuil(zone, seuil_t1),
            f'H > {seuil_t2}°C': var.heures_dessus_seuil(zone, seuil_t2),
            f'% hors {lib} 0 m/s': var.pct_hors_confort(zone, config, 0.0, methode),
            f'% hors {lib} 1 m/s': var.pct_hors_confort(zone, config, 1.0, methode),
            'HR moy (%)': round(float(hr.mean()), 1) if not hr.empty else np.nan,
            'Occupation (h/an)': var.heures_occupation(zone),
            'Météo': var.meteo_nom or '—',
        })
    df_cmp = pd.DataFrame(rows).set_index('Variante')
    cols_pct = [c for c in df_cmp.columns if c.startswith('% hors')]

    def _style_na(col):
        return ['background-color:#FFFFFF; color:#9E9E9E; font-style:italic'
                if v != v else '' for v in col]

    st.dataframe(
        df_cmp.style.format({
            'T min (°C)': '{:.1f}', 'T moy (°C)': '{:.1f}', 'T max (°C)': '{:.1f}',
            'HR moy (%)': '{:.1f}',
            **{c: '{:.1f} %' for c in cols_pct},
        }, na_rep='NA')
        .background_gradient(subset=cols_pct, cmap='YlOrRd')
        .apply(_style_na, subset=cols_pct),
        use_container_width=True,
    )
    csv = df_cmp.to_csv().encode('utf-8-sig')
    st.download_button("⬇️ Exporter le comparatif (CSV)", data=csv,
                       file_name=f"focus_{zone}.csv", mime="text/csv", key="dl_focus")

    # Détection de météos différentes parmi les variantes sélectionnées
    meteos = {v.meteo_nom for v in variantes_sel if v.a_meteo()}
    meteos_differentes = len(meteos) > 1
    if meteos_differentes:
        st.info("ℹ️ Les variantes comparées utilisent des **fichiers météo différents** : "
                + ", ".join(sorted(meteos)) + ". Les graphiques bâtiment/météo intègrent cette différence.")

    st.divider()

    # -- Série temporelle température --
    st.subheader("Évolution horaire de la température")
    fig_temp = graphique_temp_horaire(variantes_sel, zone, seuil_t1, seuil_t2)
    st.plotly_chart(fig_temp, use_container_width=True)

    # -- T_op vs T_ext (toutes les variantes sélectionnées, chacune sa météo) --
    st.subheader("Température opérative vs Température extérieure")
    fig_op = graphique_text_vs_text_op(variantes_sel, zone)
    st.plotly_chart(fig_op, use_container_width=True)
    if len(variantes_sel) == 1:
        st.caption("Coloration par saison. Sélectionnez plusieurs variantes pour les comparer.")

    # -- Comparaison des fichiers météo (si différents) --
    if meteos_differentes:
        st.subheader("Comparaison des fichiers météo")
        st.plotly_chart(graphique_meteo_comparaison(variantes_sel), use_container_width=True)

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

    if not series:
        st.info("Diagramme indisponible pour cette zone.")
    else:
        # 1) Diagramme global : toutes les variantes superposées (une couleur/variante)
        if len(series) > 1:
            st.markdown("**Toutes les variantes superposées**")
            fig_all = creer_givoni(series, config=config, methode=methode,
                                   titre=f"Diagramme de {nom_modele} — {zone} (toutes variantes)")
            st.plotly_chart(fig_all, use_container_width=True, key="giv_all")

        # 2) Un diagramme par variante (coloration par saison)
        st.markdown("**Par variante**" if len(series) > 1 else "")
        for s in series:
            fig_one = creer_givoni([s], config=config, methode=methode,
                                   titre=f"Diagramme de {nom_modele} — {zone} · {s['label']}")
            st.plotly_chart(fig_one, use_container_width=True, key=f"giv_{s['label']}")

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
