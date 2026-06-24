"""Graphiques d'humidité relative (HR)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.charte import (
    COULEURS_VARIANTES,
    get_layout, grille_color, ligne_ext_color, finalize_fig, bar_labels,
)
from charts.temperature import _serie_vers_horodate

# Bande de confort hygrométrique usuelle (plage saine recommandée intérieur)
HR_CONFORT_MIN = 40.0
HR_CONFORT_MAX = 70.0
VERT_CONFORT = "#2ECC71"


def _rgba(hex_color: str, alpha: float) -> str:
    """Convertit '#RRGGBB' en chaîne rgba() pour les remplissages translucides."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


def _xy_zone(var, valeurs, n, zone, occupation_seulement):
    """Index temporel + valeurs sur la période, NaN sur les heures inoccupées
    si demandé. Retourne (pd.DatetimeIndex, np.ndarray)."""
    m = var.masque_periode(n)
    x = _serie_vers_horodate(var.df_horaire)[:n][m]
    y = np.asarray(valeurs[:n], dtype=float)[m]
    if occupation_seulement:
        occ = var.col_apports_occupants(zone)
        if not occ.empty:
            y = y.copy()
            y[~((occ.values[:n] > 0)[m])] = np.nan
    return pd.DatetimeIndex(x), y


def graphique_hr_horaire(
    variantes: list,            # list of Variante
    zone: str,
    hr_min: float = HR_CONFORT_MIN,
    hr_max: float = HR_CONFORT_MAX,
    occupation_seulement: bool = False,
    agregation: str = "journalier",   # "journalier" (lisible) ou "horaire" (détaillé)
    titre: str | None = None,
) -> go.Figure:
    """
    Évolution de l'humidité relative intérieure — comparaison variantes.

    - "journalier" (défaut) : moyenne journalière par variante ; enveloppe min–max
      journalière ajoutée quand une seule variante est tracée (sinon trop chargé).
    - "horaire" : série horaire brute (8 760 pts), trait fin.
    - HR extérieure superposée en pointillés (une par fichier météo distinct).
    - Bande de confort [hr_min, hr_max] % en fond ; libellé dans la légende.
    - occupation_seulement : exclut les heures inoccupées (apports occupants nuls).
    """
    fig = go.Figure()
    journalier = (agregation == "journalier")

    # Bande de confort hygrométrique : rectangle de fond + entrée de légende
    # lisible (pas d'annotation dans le graphe, qui se superposait aux courbes).
    fig.add_hrect(y0=hr_min, y1=hr_max, fillcolor=VERT_CONFORT, opacity=0.12,
                  line_width=0, layer="below")
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers',
        marker=dict(size=11, color=VERT_CONFORT, opacity=0.45, symbol='square'),
        name=f'Confort {hr_min:.0f}–{hr_max:.0f} %', hoverinfo='skip',
    ))

    interieures = [v for v in variantes if not v.col_hr(zone).empty]
    solo = len(interieures) == 1

    # -- HR intérieure : une courbe par variante --
    for i, var in enumerate(variantes):
        s = var.col_hr(zone)
        if s.empty:
            continue
        x, y = _xy_zone(var, s.values, len(s), zone, occupation_seulement)
        color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
        ts = pd.Series(y, index=x)

        if journalier:
            jm = ts.resample('D').mean()
            if solo:
                jmin = ts.resample('D').min()
                jmax = ts.resample('D').max()
                fig.add_trace(go.Scatter(
                    x=jmax.index, y=jmax.values, mode='lines',
                    line=dict(width=0), hoverinfo='skip', showlegend=False))
                fig.add_trace(go.Scatter(
                    x=jmin.index, y=jmin.values, mode='lines', line=dict(width=0),
                    fill='tonexty', fillcolor=_rgba(color, 0.15), hoverinfo='skip',
                    name='Min–max journalier', showlegend=True))
            fig.add_trace(go.Scatter(
                x=jm.index, y=jm.values, mode='lines', name=var.nom,
                line=dict(color=color, width=1.6), connectgaps=False,
                hovertemplate='%{x|%d %b}<br>HR moy=%{y:.0f}%<extra>' + var.nom + '</extra>'))
        else:
            fig.add_trace(go.Scatter(
                x=ts.index, y=ts.values, mode='lines', name=var.nom, opacity=0.85,
                line=dict(color=color, width=0.8), connectgaps=False,
                hovertemplate='%{x|%d %b %H:%M}<br>HR=%{y:.0f}%<extra>' + var.nom + '</extra>'))

    # -- HR extérieure : une courbe pointillée par fichier météo distinct --
    meteos_vus = {}
    for var in variantes:
        if var.df_meteo.empty or 'HR_ext' not in var.df_meteo.columns:
            continue
        nom = var.meteo_affiche() or "météo"
        meteos_vus.setdefault(nom, var)
    multi = len(meteos_vus) > 1
    teintes_ext = [ligne_ext_color()] if not multi else ["#455A64", "#8E24AA", "#00897B", "#6D4C41"]
    for j, (nom, var) in enumerate(meteos_vus.items()):
        hr_ext = var.df_meteo['HR_ext'].values
        n = min(len(hr_ext), len(var.df_horaire))
        x, y = _xy_zone(var, hr_ext, n, zone, occupation_seulement)
        ts = pd.Series(y, index=x)
        yy = ts.resample('D').mean() if journalier else ts
        label = f'HR ext — {nom}' if multi else 'HR extérieure'
        fig.add_trace(go.Scatter(
            x=yy.index, y=yy.values, mode='lines', name=label, connectgaps=False,
            line=dict(color=teintes_ext[j % len(teintes_ext)], width=1.2, dash='dot'),
            hovertemplate='%{x|%d %b}<br>HR_ext=%{y:.0f}%<extra>' + label + '</extra>'))

    suffixe = " (moyenne journalière)" if journalier else " (horaire)"
    layout = get_layout()
    layout.update(
        title=titre or f'Humidité relative — {zone}{suffixe}',
        xaxis=dict(title='Date', gridcolor=grille_color()),
        yaxis=dict(title='HR (%)', gridcolor=grille_color(), range=[0, 100]),
        height=400,
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)


def graphique_hr_min_moy_max(
    variantes: list,
    zones: list[str],
    titre: str | None = None,
) -> go.Figure:
    """Barres groupées HR min / moy / max par zone (comparaison variantes)."""
    fig = go.Figure()
    # Une variante = un groupe de 3 barres (min/moy/max) par zone.
    for i, var in enumerate(variantes):
        color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
        hr_min, hr_moy, hr_max = [], [], []
        for zone in zones:
            s = var.stats_hr(zone)
            hr_min.append(round(s['hr_min'], 0))
            hr_moy.append(round(s['hr_moy'], 0))
            hr_max.append(round(s['hr_max'], 0))
        suffixe = f" — {var.nom}" if len(variantes) > 1 else ""
        fig.add_trace(go.Bar(x=zones, y=hr_min, name=f"HR min{suffixe}",
                             marker=dict(color=color, opacity=0.45), **bar_labels(".0f")))
        fig.add_trace(go.Bar(x=zones, y=hr_moy, name=f"HR moy{suffixe}",
                             marker=dict(color=color, opacity=0.7), **bar_labels(".0f")))
        fig.add_trace(go.Bar(x=zones, y=hr_max, name=f"HR max{suffixe}",
                             marker=dict(color=color, opacity=1.0), **bar_labels(".0f")))

    layout = get_layout()
    layout.update(
        title=titre or 'Humidité relative min / moyenne / max par zone',
        xaxis=dict(title='Zone', tickangle=-30),
        yaxis=dict(title='HR (%)', gridcolor=grille_color(), range=[0, 112]),
        barmode='group',
        height=440,
        uniformtext=dict(minsize=8, mode='hide'),
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)
