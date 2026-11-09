"""Vue Niveau 3 — Comparaison d'un échantillon de zones (une variante)."""
import streamlit as st
import pandas as pd
import numpy as np

from views.widgets import persist_multiselect, persist_selectbox, show_plotly, degrade


def render_comparaison_zones(variantes: list, seuil_t1: float, seuil_t2: float,
                             config: dict, methode: str = "givoni", dh_on: bool = False):
    """Comparaison d'un échantillon de zones sur une variante sélectionnée."""
    from charts.temperature import (
        graphique_temp_min_moy_max,
        graphique_heures_depassement,
        graphique_apports_par_zone_mensuel,
        graphique_besoins_par_zone,
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
                     .apply(degrade, subset=cols_couleur)
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

    st.divider()
    tab_t, tab_hr, tab_dep, tab_bes, tab_app, tab_en = st.tabs(
        ["🌡️ Températures", "💧 Humidité", "⏱️ Dépassements", "⚡ Besoins", "☀️ Apports",
         "🌿 Confort adaptatif EN 16798"])

    with tab_t:
        # -- Températures min/moy/max en barres --
        st.subheader("Températures min / moyenne / max par zone")
        fig_t = graphique_temp_min_moy_max([var], zones_sel)
        show_plotly(fig_t, width='stretch')

    with tab_hr:
        # -- Humidité relative min/moy/max en barres --
        st.subheader("Humidité relative min / moyenne / max par zone")
        fig_hr = graphique_hr_min_moy_max([var], zones_sel)
        show_plotly(fig_hr, width='stretch')

    with tab_dep:
        # -- Heures de dépassement --
        st.subheader("Heures de dépassement")
        fig_dep = graphique_heures_depassement([var], zones_sel, seuil_t1, seuil_t2)
        show_plotly(fig_dep, width='stretch')

    with tab_bes:
        # -- Besoins annuels --
        st.subheader("Besoins annuels par zone")
        fig_bes = graphique_besoins_par_zone(var, zones_sel)
        if fig_bes is not None:
            show_plotly(fig_bes, width='stretch')

    with tab_app:
        # -- Apports solaires mensuels : une barre par mois par zone --
        st.subheader("Apports solaires mensuels par zone")
        fig_sol = graphique_apports_par_zone_mensuel(var, zones_sel, type_apport="solaires")
        show_plotly(fig_sol, width='stretch')

        # -- Apports internes mensuels : une barre par mois par zone --
        st.subheader("Apports internes mensuels par zone (éclairage + occupants + équipements)")
        fig_int = graphique_apports_par_zone_mensuel(var, zones_sel, type_apport="internes")
        show_plotly(fig_int, width='stretch')

    with tab_en:
        _onglet_en16798(var, zones_sel)


def _onglet_en16798(var, zones_sel):
    """Onglet confort adaptatif : barres du % d'inconfort par zone + tableau."""
    from views.focus_zone import choisir_categorie_en16798
    from charts.adaptatif import creer_barres_en16798

    if not len(var.t_ext_horaire()):
        st.info("Confort adaptatif indisponible : aucune température extérieure "
                "(météo .try ou colonne T extérieure des résultats).")
        return
    c1, c2 = st.columns([1, 3])
    with c1:
        cat = choisir_categorie_en16798()
    rom = ["I", "II", "III"][cat - 1]

    rows = []
    for zone in zones_sel:
        r = var.en16798(zone, cat)          # mémoïsé par (zone, catégorie, période)
        if r is None:
            continue
        syn = var.synthese_zone(zone)
        rows.append({
            'zone': zone,
            'surface': syn.get('surface_m2', np.nan) if syn else np.nan,
            'occupied': r['total_occupied'],
            'evaluated': r['total_occupied_valid'],
            'discomfort_hours': r['discomfort_hours'],
            'discomfort_pct': r['discomfort_pct'],
            'discomfort_warm': r['discomfort_hours_warm'],
            'discomfort_cold': r['discomfort_hours_cold'],
        })
    if not rows:
        st.info("Aucune zone exploitable (température ou occupation manquante).")
        return
    df = pd.DataFrame(rows).sort_values('discomfort_pct', kind='stable', na_position='last')

    show_plotly(creer_barres_en16798(df, cat, var.nom), width='stretch', key="comp_en16798_bar")
    sans = df.loc[df['discomfort_pct'].isna(), 'zone'].tolist()
    st.caption("Bandes de fond = niveaux de performance passive : < 5 % excellente · "
               "5–15 % bonne · 15–25 % modérée (rafraîchissement ou brassage d'air "
               "recommandé) · > 25 % refroidissement actif nécessaire. Heures évaluées = "
               "heures occupées où θrm est dans le domaine d'application (10–30 °C)."
               + (f" Zones sans heure évaluée (non affichées) : {', '.join(sans)}." if sans else ""))

    df_aff = df.rename(columns={
        'zone': 'Zone', 'surface': 'Surface (m²)', 'occupied': 'Heures occupées',
        'evaluated': 'Heures évaluées', 'discomfort_hours': f'Inconfort Cat.{rom} (h)',
        'discomfort_pct': f'Inconfort Cat.{rom} (%)', 'discomfort_warm': 'dont chaud (h)',
        'discomfort_cold': 'dont froid (h)'})
    col_pct = [f'Inconfort Cat.{rom} (%)']
    _dec = ',' if st.session_state.get('cfg_format_fr', True) else '.'
    st.dataframe(
        df_aff.style.format({'Surface (m²)': '{:.0f}', **{c: '{:.1f} %' for c in col_pct}},
                            na_rep='NA', decimal=_dec, thousands=' ')
        .apply(degrade, subset=col_pct),
        width='stretch', hide_index=True,
        height=min(600, 60 + 35 * len(df_aff)),
    )
    st.download_button("⬇️ Exporter CSV", data=df_aff.to_csv(index=False).encode('utf-8-sig'),
                       file_name=f"en16798_zones_{var.nom}.csv",
                       mime="text/csv", key="dl_comp_en16798")
