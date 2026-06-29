"""Vue Niveau 2 — Focus sur une zone (comparaison variantes)."""
import streamlit as st
import pandas as pd
import numpy as np

from views.widgets import persist_multiselect, persist_selectbox


@st.fragment
def _section_humidite(variantes_sel, zone, config):
    """Section humidité relative, isolée dans un fragment : la case « heures
    d'occupation » ne déclenche qu'un rerun LOCAL (les ~15 autres figures de la
    page ne sont pas reconstruites, et l'onglet actif n'est pas réinitialisé).

    Tous les graphiques HR restent affichés (pas de sélecteur) → tous imprimables.
    """
    from charts.humidite import graphique_hr_horaire, heatmap_hr_jour_heure

    seuils = config.get('seuils', {}) if isinstance(config, dict) else {}
    hr_min = float(seuils.get('hr_confort_min', 40.0))
    hr_max = float(seuils.get('hr_confort_max', 70.0))

    # Garde-fou : sans colonne HR pour cette zone, le graphe sortirait vide (axe
    # numérique -1..6 au lieu de dates). Message explicite plutôt que graphe muet.
    if not any(not v.col_hr(zone).empty for v in variantes_sel):
        st.info("Humidité relative indisponible pour cette zone : aucune colonne "
                "« Humidité relative (%) » dans les résultats des variantes sélectionnées.")
        return
    st.caption(f"HR intérieure par variante, HR extérieure (météo) en pointillés, "
               f"bande de confort {hr_min:.0f}–{hr_max:.0f} % en fond "
               "(modifiable dans l'onglet Réglages).")
    hr_occ_only = st.checkbox("Heures d'occupation seulement", value=False, key="hr_occ_only",
                              help="Exclut les heures inoccupées (apports occupants nuls). "
                                   "S'applique à tous les graphiques d'humidité ci-dessous.")

    st.markdown("**Moyenne journalière**")
    fig_hr_j = graphique_hr_horaire(variantes_sel, zone, hr_min=hr_min, hr_max=hr_max,
                                    occupation_seulement=hr_occ_only, agregation="journalier")
    st.plotly_chart(fig_hr_j, width='stretch', key="hr_journalier")

    st.markdown("**Horaire (zoomable)**")
    fig_hr_h = graphique_hr_horaire(variantes_sel, zone, hr_min=hr_min, hr_max=hr_max,
                                    occupation_seulement=hr_occ_only, agregation="horaire")
    st.plotly_chart(fig_hr_h, width='stretch', key="hr_horaire")

    st.markdown("**Carte jour × heure**")
    st.caption("Couleur = HR % (échelle fixe 20–100, variantes comparables). "
               "Une carte par variante sélectionnée.")
    for i, var in enumerate(variantes_sel):
        fig_hm = heatmap_hr_jour_heure(var, zone, occupation_seulement=hr_occ_only)
        if fig_hm is not None:
            st.plotly_chart(fig_hm, width='stretch', key=f"hr_hm_{i}")


def render_focus_zone(variantes: list, seuil_t1: float, seuil_t2: float,
                      config: dict, methode: str = "givoni", dh_on: bool = False):
    """Affiche l'analyse détaillée d'une zone pour toutes les variantes."""
    from charts.temperature import (
        graphique_temp_horaire,
        graphique_text_vs_text_op,
        graphique_apports_solaires,
        graphique_meteo_comparaison,
        heatmap_temp_jour_heure,
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
                                            "sel_focus_variantes", defaut=noms, auto_new=True,
                                            placeholder="Rechercher / sélectionner des variantes…")

    variantes_sel = [v for v in variantes if v.nom in selected_noms]
    if not variantes_sel or not zone:
        return

    lib = "COCO" if methode == "coco" else "Givoni"
    nom_modele = "COCO" if methode == "coco" else "Givoni"
    par_saison = not st.session_state.get('cfg_saison_off', False)
    # Note d'hypothèse chauffe-sous-consigne sur le Givoni : seulement si au moins
    # une variante affichée est chauffée (saison de chauffe ou P chauffage > 0).
    note_chauffe = any(v.a_chauffage() for v in variantes_sel)

    # -- Tableau comparatif : une ligne par variante (pour la zone choisie) --
    st.subheader(f"Comparatif des variantes — {zone}")
    rows = []
    for var in variantes_sel:
        stats = var.stats_temp(zone)
        syn = var.synthese_zone(zone)
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
            **({f'DH > {seuil_t1:.0f}°C (°C·h)': var.degre_heures(zone, seuil_t1)} if dh_on else {}),
            'Occupation (h/an)': var.heures_occupation(zone),
            'Météo': var.meteo_affiche() or '—',
        })
    df_cmp = pd.DataFrame(rows).set_index('Variante')
    cols_pct = [c for c in df_cmp.columns if c.startswith('% hors')]

    def _style_na(col):
        return ['background-color:#FFFFFF; color:#9E9E9E; font-style:italic'
                if v != v else '' for v in col]

    fmt_focus = {
        'T min (°C)': '{:.1f}', 'T moy (°C)': '{:.1f}', 'T max (°C)': '{:.1f}',
        **{c: '{:.1f} %' for c in cols_pct},
    }
    for c in df_cmp.columns:
        if c.startswith('DH'):
            fmt_focus[c] = '{:.0f}'
    _dec = ',' if st.session_state.get('cfg_format_fr', True) else '.'
    st.dataframe(
        df_cmp.style.format(fmt_focus, na_rep='NA', decimal=_dec, thousands=' ', precision=1)
        .background_gradient(subset=cols_pct, cmap='YlOrRd')
        .apply(_style_na, subset=cols_pct),
        width='stretch',
    )
    csv = df_cmp.to_csv().encode('utf-8-sig')
    st.download_button("⬇️ Exporter le comparatif (CSV)", data=csv,
                       file_name=f"focus_{zone}.csv", mime="text/csv", key="dl_focus")

    # Détection de météos différentes parmi les variantes sélectionnées
    meteos = {v.meteo_affiche() for v in variantes_sel if v.a_meteo()}
    meteos_differentes = len(meteos) > 1
    if meteos_differentes:
        st.info("ℹ️ Les variantes comparées utilisent des **fichiers météo différents** : "
                + ", ".join(sorted(meteos)) + ". Les graphiques bâtiment/météo intègrent cette différence.")

    # Onglets : réduit le scroll et regroupe par thème. Le rapport Word reste
    # exhaustif (il génère ses figures indépendamment de l'affichage écran).
    tab_t, tab_conf, tab_hum, tab_app = st.tabs(
        ["🌡️ Température", "🔆 Confort bioclimatique", "💧 Humidité", "☀️ Apports"])

    # ===================== Onglet Température =====================
    with tab_t:
        st.subheader("Évolution horaire de la température")
        fig_temp = graphique_temp_horaire(variantes_sel, zone, seuil_t1, seuil_t2)
        st.plotly_chart(fig_temp, width='stretch')

        st.subheader("Carte de température (jour × heure)")
        st.caption("Couleur = température intérieure (°C). Échelle commune aux variantes "
                   "sélectionnées pour les rendre comparables. Une carte par variante.")
        _stats = [var.stats_temp(zone) for var in variantes_sel]
        _tmins = [s['t_min'] for s in _stats if s['t_min'] == s['t_min']]
        _tmaxs = [s['t_max'] for s in _stats if s['t_max'] == s['t_max']]
        _zmin = min(_tmins) if _tmins else None
        _zmax = max(_tmaxs) if _tmaxs else None
        for i, var in enumerate(variantes_sel):
            fig_thm = heatmap_temp_jour_heure(var, zone, zmin=_zmin, zmax=_zmax)
            if fig_thm is not None:
                st.plotly_chart(fig_thm, width='stretch', key=f"temp_hm_{i}")

        st.subheader("Température opérative vs Température extérieure")
        fig_op = graphique_text_vs_text_op(variantes_sel, zone, par_saison=par_saison)
        st.plotly_chart(fig_op, width='stretch')
        if len(variantes_sel) == 1 and par_saison:
            st.caption("Coloration par saison. Sélectionnez plusieurs variantes pour les comparer.")

        if meteos_differentes:
            st.subheader("Comparaison des fichiers météo")
            st.plotly_chart(graphique_meteo_comparaison(variantes_sel), width='stretch')

    # ===================== Onglet Confort bioclimatique =====================
    with tab_conf:
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
                                       titre=f"Diagramme de {nom_modele} — {zone} (toutes variantes)",
                                       par_saison=par_saison, note_chauffe=note_chauffe)
                st.plotly_chart(fig_all, width='stretch', key="giv_all")

            # 2) Un diagramme par variante (coloration par saison si activée)
            st.markdown("**Par variante**" if len(series) > 1 else "")
            for s in series:
                fig_one = creer_givoni([s], config=config, methode=methode,
                                       titre=f"Diagramme de {nom_modele} — {zone} · {s['label']}",
                                       par_saison=par_saison, note_chauffe=note_chauffe)
                st.plotly_chart(fig_one, width='stretch', key=f"giv_{s['label']}")

        # Périodes de focus (module optionnel) : Givoni par période + récap
        if st.session_state.get('cfg_periodes_on'):
            periodes = st.session_state.get('cfg_periodes') or []
            if periodes:
                st.divider()
                st.subheader(f"Diagramme de {nom_modele} par périodes de focus")
                st.caption("Points colorés selon la période de focus définie en Réglages "
                           "(alternative à la saison Pléiades).")
                for v in variantes_sel:
                    pts = v.points_interieurs_par_periode(zone, config, periodes, methode)
                    if not len(pts['T']):
                        continue
                    pts['label'] = v.nom
                    fig_per = creer_givoni([pts], config=config, methode=methode,
                                           titre=f"Diagramme de {nom_modele} — {zone} · "
                                                 f"{v.nom} (par période)",
                                           par_periode=True, note_chauffe=note_chauffe)
                    st.plotly_chart(fig_per, width='stretch', key=f"giv_per_{v.nom}")

                st.markdown("**Récapitulatif par période** (vitesses d'air 0 et 1 m/s)")
                rows_per = []
                for v in variantes_sel:
                    r0 = {r['periode']: r for r in v.inconfort_periodes(zone, config, periodes, methode, 0.0)}
                    r1 = {r['periode']: r for r in v.inconfort_periodes(zone, config, periodes, methode, 1.0)}
                    for p in periodes:
                        nom = p.get('nom', '')
                        a = r0.get(nom, {})
                        b = r1.get(nom, {})
                        rows_per.append({
                            'Variante': v.nom,
                            'Période': nom,
                            "Heures d'occupation": a.get('heures_occ', 0),
                            "Inconfort 0 m/s (h)": a.get('heures_inconfort', 0),
                            '% inconfort 0 m/s': a.get('pct', np.nan),
                            "Inconfort 1 m/s (h)": b.get('heures_inconfort', 0),
                            '% inconfort 1 m/s': b.get('pct', np.nan),
                        })
                if rows_per:
                    df_per = pd.DataFrame(rows_per).set_index(['Variante', 'Période'])
                    _decp = ',' if st.session_state.get('cfg_format_fr', True) else '.'
                    st.dataframe(
                        df_per.style.format({"Heures d'occupation": '{:.0f}',
                                             "Inconfort 0 m/s (h)": '{:.0f}',
                                             '% inconfort 0 m/s': '{:.1f} %',
                                             "Inconfort 1 m/s (h)": '{:.0f}',
                                             '% inconfort 1 m/s': '{:.1f} %'},
                                            na_rep='NA', decimal=_decp, thousands=' '),
                        width='stretch',
                    )

    # ===================== Onglet Humidité (fragment) =====================
    with tab_hum:
        _section_humidite(variantes_sel, zone, config)

    # ===================== Onglet Apports =====================
    with tab_app:
        st.subheader("Apports solaires mensuels")
        fig_sol = graphique_apports_solaires(variantes_sel, zone, type_apport="solaires")
        st.plotly_chart(fig_sol, width='stretch')

        st.subheader("Apports internes mensuels (éclairage + occupants + équipements)")
        fig_int = graphique_apports_solaires(variantes_sel, zone, type_apport="internes")
        st.plotly_chart(fig_int, width='stretch')
