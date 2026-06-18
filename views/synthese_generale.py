"""Vue Niveau 1 — Synthèse générale : un tableau, une ligne par variante (bâtiment)."""
import streamlit as st
import pandas as pd
import numpy as np

from views.widgets import persist_multiselect


def render_synthese_generale(variantes: list, seuil_t1: float, seuil_t2: float,
                             config: dict, methode: str = "givoni"):
    """Tableau de synthèse au niveau bâtiment : une ligne par variante."""
    if not variantes:
        st.info("Chargez au moins une variante dans le panneau latéral.")
        return

    st.header("Synthèse générale — Bâtiment entier")

    noms = [v.nom for v in variantes]
    selected_noms = persist_multiselect("Variantes affichées", noms,
                                        "sel_syn_variantes", defaut=noms,
                                        placeholder="Rechercher / sélectionner des variantes…")
    variantes_sel = [v for v in variantes if v.nom in selected_noms]
    if not variantes_sel:
        st.warning("Sélectionnez au moins une variante.")
        return

    # -- Tableau : une ligne par variante --
    rows = []
    for var in variantes_sel:
        ind = var.indicateurs_batiment(config, methode)
        rows.append({'Variante': var.nom, **ind})
    df = pd.DataFrame(rows).set_index('Variante')

    cols_pct = [c for c in df.columns if c.startswith('% hors')]
    fmt = {
        'Surface totale (m²)': '{:.0f}',
        'Besoins chaud (kWh)': '{:.0f}', 'Besoins froid (kWh)': '{:.0f}',
        'Besoins chaud (kWh/m²)': '{:.1f}', 'Besoins froid (kWh/m²)': '{:.1f}',
        'T min (°C)': '{:.1f}', 'T moy (°C)': '{:.1f}', 'T max (°C)': '{:.1f}',
        **{c: '{:.1f} %' for c in cols_pct},
    }

    def _style_na(col):
        return ['background-color:#FFFFFF; color:#9E9E9E; font-style:italic'
                if v != v else '' for v in col]

    st.dataframe(
        df.style.format(fmt, na_rep='NA')
              .background_gradient(subset=cols_pct, cmap='YlOrRd')
              .apply(_style_na, subset=cols_pct),
        use_container_width=True,
    )
    st.caption("Indicateurs au niveau bâtiment. T moy = moyenne pondérée par la surface ; "
               "T min/max = extrêmes toutes zones. « % hors » = heures d'occupation hors "
               "zone de confort (pondéré par les heures d'occupation de chaque zone). "
               "« NA » : aucune zone occupée.")

    csv = df.to_csv().encode('utf-8-sig')
    st.download_button("⬇️ Exporter la synthèse (CSV)", data=csv,
                       file_name="synthese_generale.csv", mime="text/csv",
                       key="dl_syn_global")
