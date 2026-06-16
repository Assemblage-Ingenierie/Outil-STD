"""Vue Niveau 1 — Synthèse générale (bâtiment entier, toutes variantes)."""
import streamlit as st
import pandas as pd

from views.widgets import persist_multiselect


def render_synthese_generale(variantes: list, seuil_t1: float, seuil_t2: float, config: dict):
    """Affiche la synthèse générale pour toutes les variantes sélectionnées."""
    from charts.temperature import graphique_heures_depassement, graphique_temp_min_moy_max

    if not variantes:
        st.info("Chargez au moins une variante dans le panneau latéral.")
        return

    st.header("Synthèse générale — Bâtiment entier")

    noms = [v.nom for v in variantes]
    selected_noms = persist_multiselect("Variantes affichées", noms,
                                        "sel_syn_variantes", defaut=noms)
    variantes_sel = [v for v in variantes if v.nom in selected_noms]

    if not variantes_sel:
        st.warning("Sélectionnez au moins une variante.")
        return

    # -- Tableaux par variante --
    for var in variantes_sel:
        st.subheader(f"Variante : {var.nom}")
        df_table = var.tableau_synthese_global(seuil_t1, seuil_t2, config=config)
        if df_table.empty:
            st.warning("Aucune donnée de synthèse disponible.")
            continue

        cols_couleur = [c for c in df_table.columns
                        if c.startswith('H >') or c.startswith('H hors')]
        st.dataframe(
            df_table.style
                .format({
                    'T min (°C)': '{:.1f}', 'T moy (°C)': '{:.1f}', 'T max (°C)': '{:.1f}',
                })
                .background_gradient(subset=cols_couleur, cmap='YlOrRd'),
            use_container_width=True,
            height=min(600, 60 + 35 * len(df_table)),
        )

        csv = df_table.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            f"⬇️ Exporter CSV — {var.nom}",
            data=csv,
            file_name=f"synthese_{var.nom}.csv",
            mime="text/csv",
            key=f"dl_syn_{var.nom}",
        )

    st.divider()

    # -- Graphique heures de dépassement --
    st.subheader("Heures de dépassement des seuils")
    all_zones = variantes_sel[0].zones
    zones_sel = persist_multiselect(
        "Zones à afficher", all_zones, "sel_syn_zones_graph",
        defaut=all_zones[:min(10, len(all_zones))]
    )
    if zones_sel:
        fig = graphique_heures_depassement(variantes_sel, zones_sel, seuil_t1, seuil_t2)
        st.plotly_chart(fig, use_container_width=True)

        # -- Températures min/moy/max en barres (remplace les boîtes à moustaches) --
        st.subheader("Températures min / moyenne / max")
        fig2 = graphique_temp_min_moy_max(variantes_sel, zones_sel)
        st.plotly_chart(fig2, use_container_width=True)
