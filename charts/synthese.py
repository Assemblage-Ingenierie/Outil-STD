"""Graphiques barres au niveau BÂTIMENT (comparaison des variantes).

Source unique partagée par la vue « Synthèse générale » (écran) et le rapport
Word, pour éviter toute divergence entre l'affichage et l'export.

Chaque fonction prend un DataFrame indicateurs (une ligne par variante, colonnes
= indicateurs bâtiment de `Variante.indicateurs_batiment`) + la liste des noms de
variantes (ordre des barres), et retourne une figure Plotly (ou None si la donnée
requise est absente).
"""
import plotly.graph_objects as go

from config.charte import (
    ROUGE, get_layout, grille_color, finalize_fig, bar_labels,
)
from config.i18n import t

BLEU = "#2196F3"
TEAL = "#00897B"
ORANGE = "#FF9800"
INDIGO = "#3F51B5"


def _layout(titre: str, ytitre: str) -> dict:
    lay = get_layout()
    lay.update(title=titre, xaxis=dict(title=t("Variante"), tickangle=-15),
               yaxis=dict(title=ytitre, gridcolor=grille_color()),
               barmode="group", height=380,
               uniformtext=dict(minsize=8, mode='hide'))
    return lay


def graphique_besoins(df, noms_var) -> go.Figure:
    """Besoins de chauffage / climatisation (kWh/m²)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=noms_var, y=df["Besoins chaud (kWh/m²)"],
                         name=t("Chauffage"), marker_color=ROUGE, **bar_labels()))
    fig.add_trace(go.Bar(x=noms_var, y=df["Besoins froid (kWh/m²)"],
                         name=t("Climatisation"), marker_color=BLEU, **bar_labels()))
    fig.update_layout(**_layout(t("Besoins par variante (kWh/m²)"), "kWh/m²"))
    return finalize_fig(fig)


def graphique_temperatures(df, noms_var) -> go.Figure:
    """Températures min / moyenne / max du bâtiment (°C)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=noms_var, y=df["T min (°C)"], name=t("T min"),
                         marker=dict(color=BLEU, opacity=0.6), **bar_labels()))
    fig.add_trace(go.Bar(x=noms_var, y=df["T moy (°C)"], name=t("T moy"),
                         marker_color="#9E9E9E", **bar_labels()))
    fig.add_trace(go.Bar(x=noms_var, y=df["T max (°C)"], name=t("T max"),
                         marker=dict(color=ROUGE, opacity=0.85), **bar_labels()))
    fig.update_layout(**_layout(t("Températures par variante (°C)"), "°C"))
    return finalize_fig(fig)


def graphique_heures_depassement_batiment(df, noms_var, seuil_t0, seuil_t1, seuil_t2):
    """Heures de dépassement des seuils au niveau BÂTIMENT (H<T0 / H>T1 / H>T2),
    une barre par variante. None si aucune colonne de seuil présente.

    À ne pas confondre avec ``charts.temperature.graphique_heures_depassement``
    (par ZONE, à partir des objets Variante)."""
    cols = [f'H < {seuil_t0:.0f}°C', f'H > {seuil_t1:.0f}°C', f'H > {seuil_t2:.0f}°C']
    couleurs = {cols[0]: BLEU, cols[1]: ORANGE, cols[2]: ROUGE}
    presentes = [c for c in cols if c in df.columns]
    if not presentes:
        return None
    fig = go.Figure()
    for c in presentes:
        fig.add_trace(go.Bar(x=noms_var, y=df[c], name=c,
                             marker_color=couleurs.get(c, "#9E9E9E"), **bar_labels(".0f")))
    fig.update_layout(**_layout(t("Heures de dépassement par variante"), t("heures (moy. par zone)")))
    return finalize_fig(fig)


def graphique_humidite(df, noms_var) -> go.Figure:
    """Humidité relative min / moyenne / max du bâtiment (%)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=noms_var, y=df["HR min (%)"], name=t("HR min"),
                         marker=dict(color=BLEU, opacity=0.45), **bar_labels(".0f")))
    fig.add_trace(go.Bar(x=noms_var, y=df["HR moy (%)"], name=t("HR moy"),
                         marker_color="#9E9E9E", **bar_labels(".0f")))
    fig.add_trace(go.Bar(x=noms_var, y=df["HR max (%)"], name=t("HR max"),
                         marker=dict(color=TEAL, opacity=0.9), **bar_labels(".0f")))
    fig.update_layout(**_layout(t("Humidité relative par variante (%)"), t("HR (%)")))
    # Dégagement au-dessus de 100 % pour ne pas couper l'étiquette « outside » du max
    fig.update_layout(yaxis_range=[0, 112])
    return finalize_fig(fig)


def graphique_part_inconfort(df, noms_var) -> go.Figure:
    """% des heures d'occupation hors confort (0 et 1 m/s)."""
    cols_pct = [c for c in df.columns if c.startswith('% hors')]
    fig = go.Figure()
    if cols_pct:
        specs = [(cols_pct[0], 0.6), (cols_pct[1] if len(cols_pct) > 1 else cols_pct[0], 1.0)]
        for col, op in specs:
            fig.add_trace(go.Bar(x=noms_var, y=df[col], name=col.replace('% hors', t('% hors'), 1),
                                 marker=dict(color=ROUGE, opacity=op), **bar_labels(".1f")))
    fig.update_layout(**_layout(t("Part d'inconfort par variante (%)"), t("% des heures d'occupation")))
    return finalize_fig(fig)


def graphique_inconfort_jour_nuit(df_dn, noms_var) -> go.Figure:
    """Inconfort ventilé jour / nuit (0 et 1 m/s)."""
    fig = go.Figure()
    specs = [
        ('% inconfort jour 0 m/s', 'Jour · 0 m/s', ORANGE, 0.9),
        ('% inconfort nuit 0 m/s', 'Nuit · 0 m/s', INDIGO, 0.9),
        ('% inconfort jour 1 m/s', 'Jour · 1 m/s', ORANGE, 0.45),
        ('% inconfort nuit 1 m/s', 'Nuit · 1 m/s', INDIGO, 0.45),
    ]
    for col, name, color, op in specs:
        if col in df_dn.columns:
            fig.add_trace(go.Bar(x=noms_var, y=df_dn[col], name=t(name),
                                 marker=dict(color=color, opacity=op), **bar_labels(".1f")))
    fig.update_layout(**_layout(t("Inconfort jour / nuit par variante (%)"),
                                t("% des heures d'occupation")))
    return finalize_fig(fig)
