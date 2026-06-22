"""Vue Niveau 1 — Synthèse générale : un tableau, une ligne par variante (bâtiment)."""
import streamlit as st
import pandas as pd
import numpy as np

from views.widgets import persist_multiselect


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

    dh_col = f"DH > {seuil_t1:.0f}°C (°C·h)"
    # -- Tableau : une ligne par variante --
    rows = []
    for var in variantes_sel:
        ind = var.indicateurs_batiment(config, methode)
        if dh_on:
            ind[dh_col] = var.dh_batiment(seuil_t1)
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
    if dh_on:
        fmt[dh_col] = '{:.0f}'

    def _style_na(col):
        return ['background-color:#FFFFFF; color:#9E9E9E; font-style:italic'
                if v != v else '' for v in col]

    _dec = ',' if st.session_state.get('cfg_format_fr', True) else '.'
    st.dataframe(
        df.style.format(fmt, na_rep='NA', decimal=_dec, thousands=' ', precision=1)
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

    st.divider()

    # -- Graphiques au niveau BÂTIMENT : comparaison des variantes --
    import plotly.graph_objects as go
    from config.charte import ROUGE, get_layout, grille_color, finalize_fig, bar_labels

    BLEU = "#2196F3"
    noms_var = list(df.index)

    def _layout(titre, ytitre):
        lay = get_layout()
        lay.update(title=titre, xaxis=dict(title="Variante", tickangle=-15),
                   yaxis=dict(title=ytitre, gridcolor=grille_color()),
                   barmode="group", height=380,
                   uniformtext=dict(minsize=8, mode='hide'))
        return lay

    # Besoins chaud / froid (kWh/m²)
    st.subheader("Besoins de chauffage et de climatisation")
    fig_b = go.Figure()
    fig_b.add_trace(go.Bar(x=noms_var, y=df["Besoins chaud (kWh/m²)"],
                           name="Chauffage", marker_color=ROUGE, **bar_labels()))
    fig_b.add_trace(go.Bar(x=noms_var, y=df["Besoins froid (kWh/m²)"],
                           name="Climatisation", marker_color=BLEU, **bar_labels()))
    fig_b.update_layout(**_layout("Besoins par variante (kWh/m²)", "kWh/m²"))
    st.plotly_chart(finalize_fig(fig_b), use_container_width=True)

    # Températures min / moy / max
    st.subheader("Températures du bâtiment")
    fig_t = go.Figure()
    fig_t.add_trace(go.Bar(x=noms_var, y=df["T min (°C)"], name="T min",
                           marker=dict(color=BLEU, opacity=0.6), **bar_labels()))
    fig_t.add_trace(go.Bar(x=noms_var, y=df["T moy (°C)"], name="T moy",
                           marker_color="#9E9E9E", **bar_labels()))
    fig_t.add_trace(go.Bar(x=noms_var, y=df["T max (°C)"], name="T max",
                           marker=dict(color=ROUGE, opacity=0.85), **bar_labels()))
    fig_t.update_layout(**_layout("Températures par variante (°C)", "°C"))
    st.plotly_chart(finalize_fig(fig_t), use_container_width=True)

    # % hors confort 0 / 1 m/s
    st.subheader("Part d'inconfort (heures d'occupation)")
    fig_c = go.Figure()
    for col, op in [(cols_pct[0], 0.6), (cols_pct[1] if len(cols_pct) > 1 else cols_pct[0], 1.0)]:
        fig_c.add_trace(go.Bar(x=noms_var, y=df[col], name=col, marker_color=ROUGE,
                               opacity=op, **bar_labels(".1f")))
    fig_c.update_layout(**_layout("Part d'inconfort par variante (%)", "% des heures d'occupation"))
    st.plotly_chart(finalize_fig(fig_c), use_container_width=True)
