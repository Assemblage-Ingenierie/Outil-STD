"""Vue Niveau 1 — Synthèse générale : un tableau, une ligne par variante (bâtiment)."""
import streamlit as st
import pandas as pd

from views.widgets import persist_multiselect, show_plotly, degrade


def render_synthese_generale(variantes: list, seuil_t1: float, seuil_t2: float,
                             config: dict, methode: str = "givoni", dh_on: bool = False):
    """Tableau de synthèse au niveau bâtiment : une ligne par variante."""
    if not variantes:
        st.info("Chargez au moins une variante dans le panneau latéral.")
        return

    st.header("Synthèse générale — Bâtiment entier")

    noms = [v.nom for v in variantes]
    selected_noms = persist_multiselect("Variantes affichées", noms,
                                        "sel_syn_variantes", defaut=noms, auto_new=True,
                                        placeholder="Rechercher / sélectionner des variantes…")
    variantes_sel = [v for v in variantes if v.nom in selected_noms]
    if not variantes_sel:
        st.warning("Sélectionnez au moins une variante.")
        return

    seuil_t0 = st.session_state.get('cfg_seuil_t0', 18.0)
    dh_col = f"DH > {seuil_t1:.0f}°C (°C·h)"
    cols_heures = [f'H < {seuil_t0:.0f}°C', f'H > {seuil_t1:.0f}°C', f'H > {seuil_t2:.0f}°C']
    _dec = ',' if st.session_state.get('cfg_format_fr', True) else '.'

    # ==================================================================
    # Données
    # ==================================================================
    rows = []
    for var in variantes_sel:
        ind = var.indicateurs_batiment(config, methode, seuil_t0=seuil_t0,
                                       seuil_t1=seuil_t1, seuil_t2=seuil_t2)
        if dh_on:
            ind[dh_col] = var.dh_batiment(seuil_t1)
        rows.append({'Variante': var.nom, **ind})
    df = pd.DataFrame(rows).set_index('Variante')
    cols_pct = [c for c in df.columns if c.startswith('% hors')]

    jour_debut = st.session_state.get('cfg_jour_debut', 7.0)
    jour_fin = st.session_state.get('cfg_jour_fin', 22.0)
    rows_dn = []
    for var in variantes_sel:
        dn = var.inconfort_plages_horaires(config, methode, jour_debut, jour_fin)
        rows_dn.append({'Variante': var.nom, **dn})
    df_dn = pd.DataFrame(rows_dn).set_index('Variante')
    cols_dn = list(df_dn.columns)

    def _style_na(col):
        return ['background-color:#FFFFFF; color:#9E9E9E; font-style:italic'
                if v != v else '' for v in col]

    # Graphiques barres bâtiment : source unique partagée avec le rapport Word.
    from charts import synthese as gsyn
    noms_var = list(df.index)

    # ==================================================================
    # Onglets thématiques (comme la vue Focus zone)
    # ==================================================================
    tab_syn, tab_bes, tab_temp, tab_hum, tab_conf = st.tabs(
        ["📋 Synthèse", "⚡ Besoins", "🌡️ Températures", "💧 Humidité", "🔆 Confort"])

    # ----------------------------- Synthèse ----------------------------
    with tab_syn:
        fmt = {
            'Surface totale (m²)': '{:.0f}',
            'Besoins chaud (kWh)': '{:.0f}', 'Besoins froid (kWh)': '{:.0f}',
            'Besoins chaud (kWh/m²)': '{:.1f}', 'Besoins froid (kWh/m²)': '{:.1f}',
            'T min (°C)': '{:.1f}', 'T moy (°C)': '{:.1f}', 'T max (°C)': '{:.1f}',
            'HR min (%)': '{:.0f}', 'HR moy (%)': '{:.0f}', 'HR max (%)': '{:.0f}',
            **{c: '{:.0f}' for c in cols_heures if c in df.columns},
            **{c: '{:.1f} %' for c in cols_pct},
        }
        if dh_on:
            fmt[dh_col] = '{:.0f}'
        st.dataframe(
            df.style.format(fmt, na_rep='NA', decimal=_dec, thousands=' ', precision=1)
                  .apply(degrade, subset=cols_pct)
                  .apply(_style_na, subset=cols_pct),
            width='stretch',
        )
        st.caption("Indicateurs au niveau bâtiment. T moy / HR moy = moyennes pondérées par la "
                   "surface ; T et HR min/max = extrêmes toutes zones. "
                   f"« H < {seuil_t0:.0f}°C / H > {seuil_t1:.0f}°C / H > {seuil_t2:.0f}°C » = "
                   "heures moyennes par zone, pondérées par la surface utile. "
                   "« % hors » = heures d'occupation hors zone de confort (pondéré par les "
                   "heures d'occupation de chaque zone). « NA » : aucune zone occupée.")

        csv = df.to_csv().encode('utf-8-sig')
        st.download_button("⬇️ Exporter la synthèse (CSV)", data=csv,
                           file_name="synthese_generale.csv", mime="text/csv",
                           key="dl_syn_global")

    # ----------------------------- Besoins -----------------------------
    with tab_bes:
        st.subheader("Besoins de chauffage et de climatisation")
        show_plotly(gsyn.graphique_besoins(df, noms_var), width='stretch')

    # --------------------------- Températures --------------------------
    with tab_temp:
        st.subheader("Températures du bâtiment")
        show_plotly(gsyn.graphique_temperatures(df, noms_var), width='stretch')

        # Heures de dépassement des seuils de température (H<T0 / H>T1 / H>T2)
        st.subheader("Heures de dépassement des seuils de température")
        fig_h = gsyn.graphique_heures_depassement_batiment(df, noms_var, seuil_t0, seuil_t1, seuil_t2)
        if fig_h is not None:
            show_plotly(fig_h, width='stretch')
            st.caption("Heures moyennes par zone, pondérées par la surface utile : sous "
                       f"{seuil_t0:.0f}°C (froid), au-dessus de {seuil_t1:.0f}°C et {seuil_t2:.0f}°C "
                       "(surchauffe). Seuils réglables dans l'onglet Réglages.")
        else:
            st.info("Aucun seuil de dépassement disponible.")

    # ---------------------------- Humidité -----------------------------
    with tab_hum:
        st.subheader("Humidité relative du bâtiment")
        show_plotly(gsyn.graphique_humidite(df, noms_var), width='stretch')

    # ----------------------------- Confort -----------------------------
    with tab_conf:
        st.subheader("Inconfort par plage horaire (jour / nuit)")
        st.dataframe(
            df_dn.style.format({c: '{:.1f} %' for c in cols_dn},
                               na_rep='NA', decimal=_dec, thousands=' ', precision=1)
                  .apply(degrade, subset=cols_dn)
                  .apply(_style_na, subset=cols_dn),
            width='stretch',
        )
        st.caption(f"Part d'heures d'occupation hors confort {('COCO' if methode=='coco' else 'Givoni')}, "
                   f"ventilée jour ([{jour_debut:.0f} h, {jour_fin:.0f} h[) / nuit. "
                   "Agrégat bâtiment pondéré par la surface utile. "
                   "Plages réglables dans l'onglet Réglages.")

        st.divider()

        st.subheader("Part d'inconfort (heures d'occupation)")
        show_plotly(gsyn.graphique_part_inconfort(df, noms_var), width='stretch')

        st.subheader("Inconfort jour / nuit")
        show_plotly(gsyn.graphique_inconfort_jour_nuit(df_dn, noms_var), width='stretch')
