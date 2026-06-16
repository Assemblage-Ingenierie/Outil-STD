"""Vue Niveau 1 — Synthèse générale (bâtiment entier, toutes variantes)."""
import streamlit as st
import pandas as pd
from config.charte import ROUGE, VIOLET, GRIS_CLAIR


def render_synthese_generale(variantes: list, seuil_t1: float, seuil_t2: float):
    """Affiche la synthèse générale pour toutes les variantes sélectionnées."""
    from charts.temperature import graphique_heures_depassement, graphique_boite_temp

    if not variantes:
        st.info("Chargez au moins une variante dans le panneau latéral.")
        return

    st.header("Synthèse générale — Bâtiment entier")

    # Sélection des variantes à afficher
    noms = [v.nom for v in variantes]
    selected_noms = st.multiselect("Variantes affichées", noms, default=noms, key="syn_variantes")
    variantes_sel = [v for v in variantes if v.nom in selected_noms]

    if not variantes_sel:
        st.warning("Sélectionnez au moins une variante.")
        return

    # -- Tableaux par variante --
    for var in variantes_sel:
        st.subheader(f"Variante : {var.nom}")
        df_table = var.tableau_synthese_global(seuil_t1, seuil_t2)
        if df_table.empty:
            st.warning("Aucune donnée de synthèse disponible.")
            continue

        # Mise en forme avec style
        st.dataframe(
            df_table.style
                .format({
                    'Surface (m²)': lambda x: f"{x:.0f}" if isinstance(x, float) else x,
                    'Besoins chaud (kWh/m²)': lambda x: f"{x:.1f}" if isinstance(x, float) else x,
                    'Besoins froid (kWh/m²)': lambda x: f"{x:.1f}" if isinstance(x, float) else x,
                    'T min (°C)': '{:.1f}',
                    'T moy (°C)': '{:.1f}',
                    'T max (°C)': '{:.1f}',
                })
                .background_gradient(
                    subset=[f'H > {seuil_t1}°C', f'H > {seuil_t2}°C'],
                    cmap='YlOrRd'
                ),
            use_container_width=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"📋 Copier tableau {var.nom}", key=f"copy_{var.nom}"):
                st.write("Tableau copié (utilisez Ctrl+A, Ctrl+C dans le tableau ci-dessus)")
        with col2:
            csv = df_table.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                f"⬇️ Exporter CSV {var.nom}",
                data=csv,
                file_name=f"synthese_{var.nom}.csv",
                mime="text/csv",
                key=f"dl_{var.nom}",
            )

    st.divider()

    # -- Graphique heures de dépassement --
    st.subheader("Heures de dépassement des seuils")
    if variantes_sel:
        all_zones = variantes_sel[0].zones
        zones_sel = st.multiselect(
            "Zones à afficher",
            all_zones,
            default=all_zones[:min(10, len(all_zones))],
            key="syn_zones_graph"
        )
        if zones_sel:
            fig = graphique_heures_depassement(variantes_sel, zones_sel, seuil_t1, seuil_t2)
            st.plotly_chart(fig, use_container_width=True)

    # -- Boîtes à moustaches --
    st.subheader("Distribution des températures")
    zones_boite = st.multiselect(
        "Zones à comparer",
        all_zones if variantes_sel else [],
        default=(all_zones[:min(5, len(all_zones))] if variantes_sel else []),
        key="syn_zones_boite"
    )
    if zones_boite and variantes_sel:
        fig2 = graphique_boite_temp(variantes_sel, zones_boite)
        st.plotly_chart(fig2, use_container_width=True)
