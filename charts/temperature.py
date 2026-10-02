"""Graphiques de température et confort thermique."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config.charte import (
    ROUGE,
    COULEURS_VARIANTES,
    get_layout, grille_color, ligne_ext_color, violet_color, finalize_fig, bar_labels,
)
from config.i18n import t, noms_mois


NOMS_MOIS = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']  # FR (cf. noms_mois())
JOURS_CUMULES = [0,31,59,90,120,151,181,212,243,273,304,334,365]


def _cap(s: str) -> str:
    """Majuscule initiale (« solar gains (kWh) » → « Solar gains (kWh) »)."""
    return s[:1].upper() + s[1:]


def graphique_temp_horaire(
    variantes: list,  # list of Variante
    zone: str,
    seuil_t1: float | None = None,
    seuil_t2: float | None = None,
    titre: str | None = None,
) -> go.Figure:
    """Série temporelle de température intérieure — comparaison variantes."""
    fig = go.Figure()

    for i, var in enumerate(variantes):
        s = var.col_temp(zone)
        if s.empty:
            continue
        x = var.horodatage()
        m = var.masque_periode(len(s))
        color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
        fig.add_trace(go.Scatter(
            x=np.asarray(x)[m], y=s.values[m],
            mode='lines',
            name=var.nom,
            line=dict(color=color, width=1),
            hovertemplate='%{x|%d %b %H:%M}<br>T=%{y:.1f}°C<extra>' + var.nom + '</extra>',
        ))

    # Température(s) extérieure(s) : une courbe par fichier météo distinct
    meteos_vus = {}
    for var in variantes:
        if var.df_meteo.empty:
            continue
        nom = var.meteo_affiche() or t("météo")
        if nom in meteos_vus:
            continue
        meteos_vus[nom] = var
    multi = len(meteos_vus) > 1
    # Météo unique : gris-bleu foncé. Plusieurs météos : couleurs distinctes
    # (toujours en pointillé pour marquer « extérieur »).
    teintes_ext = [ligne_ext_color()] if not multi else ["#455A64", "#8E24AA", "#00897B", "#6D4C41"]
    for j, (nom, var) in enumerate(meteos_vus.items()):
        t_ext = var.df_meteo['T_ext'].values
        n = min(len(t_ext), len(var.df_horaire))
        x = var.horodatage()
        m = var.masque_periode(n)
        label = t('T ext — {nom}', nom=nom) if multi else t('T extérieure')
        fig.add_trace(go.Scatter(
            x=np.asarray(x[:n])[m], y=t_ext[:n][m],
            mode='lines',
            name=label,
            line=dict(color=teintes_ext[j % len(teintes_ext)], width=1.3, dash='dot'),
            hovertemplate='%{x|%d %b %H:%M}<br>T_ext=%{y:.1f}°C<extra>' + label + '</extra>',
        ))

    # Seuils
    if seuil_t1:
        fig.add_hline(y=seuil_t1, line_dash='dash', line_color=ROUGE,
                      annotation_text=t('Seuil T1 ({s}°C)', s=seuil_t1),
                      annotation_position='top right')
    if seuil_t2:
        fig.add_hline(y=seuil_t2, line_dash='dash', line_color='#8B0000',
                      annotation_text=t('Seuil T2 ({s}°C)', s=seuil_t2),
                      annotation_position='bottom right')

    layout = get_layout()
    layout.update(
        title=titre or t('Température intérieure — {zone}', zone=zone),
        xaxis=dict(title=t('Date'), gridcolor=grille_color()),
        yaxis=dict(title=t('Température (°C)'), gridcolor=grille_color()),
        height=420,
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)


def graphique_text_vs_text_op(
    variantes,
    zone: str,
    titre: str | None = None,
    par_saison: bool = True,
) -> go.Figure:
    """
    Nuage de points T° opérative intérieure vs T° extérieure.
    - 1 variante : coloration par saison (si par_saison) sinon couleur unique.
    - plusieurs variantes : une couleur par variante (chacune avec sa propre
      météo), avec le fichier météo en étiquette/survol.
    """
    if not isinstance(variantes, (list, tuple)):
        variantes = [variantes]
    variantes = [v for v in variantes if not v.col_temp(zone).empty and not v.df_meteo.empty]
    if not variantes:
        return go.Figure()

    fig = go.Figure()
    all_x, all_y = [], []

    if len(variantes) == 1:
        var = variantes[0]
        n = min(len(var.col_temp(zone)), len(var.df_meteo))
        mp = var.masque_periode(n)
        t_ext = var.df_meteo['T_ext'].values[:n][mp]
        t_int = var.col_temp(zone).values[:n][mp]
        if par_saison:
            saison = var.df_horaire['saison'].values[:n][mp]
            couleurs_saison = {'Refroidissement': '#2196F3', 'Chauffage': ROUGE, '': '#757575'}
            for saison_nom, color in couleurs_saison.items():
                mask = saison == saison_nom
                if not any(mask):
                    continue
                label = t(saison_nom) if saison_nom else t('Hors saison de chauffe')
                fig.add_trace(go.Scatter(
                    x=t_ext[mask], y=t_int[mask], mode='markers',
                    marker=dict(size=3, color=color, opacity=0.4), name=label,
                    hovertemplate='T_ext=%{x:.1f}°C<br>T_int=%{y:.1f}°C<extra>' + label + '</extra>',
                ))
        else:
            fig.add_trace(go.Scatter(
                x=t_ext, y=t_int, mode='markers',
                marker=dict(size=3, color="#1976D2", opacity=0.4),
                name=t('Points horaires'),
                hovertemplate='T_ext=%{x:.1f}°C<br>T_int=%{y:.1f}°C<extra></extra>',
            ))
        all_x, all_y = list(t_ext), list(t_int)
    else:
        for i, var in enumerate(variantes):
            n = min(len(var.col_temp(zone)), len(var.df_meteo))
            mp = var.masque_periode(n)
            t_ext = var.df_meteo['T_ext'].values[:n][mp]
            t_int = var.col_temp(zone).values[:n][mp]
            color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
            meteo = f" · {var.meteo_affiche()}" if var.meteo_affiche() else ""
            fig.add_trace(go.Scatter(
                x=t_ext, y=t_int, mode='markers',
                marker=dict(size=3, color=color, opacity=0.4),
                name=f"{var.nom}{meteo}",
                hovertemplate='T_ext=%{x:.1f}°C<br>T_int=%{y:.1f}°C<extra>' + var.nom + meteo + '</extra>',
            ))
            all_x += list(t_ext)
            all_y += list(t_int)

    # Ligne diagonale (T_int = T_ext)
    if all_x:
        lo = min(min(all_x), min(all_y)) - 2
        hi = max(max(all_x), max(all_y)) + 2
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[lo, hi], mode='lines',
            line=dict(color=violet_color(), width=1.5, dash='dash'),
            name='T_int = T_ext', hoverinfo='skip',
        ))

    layout = get_layout()
    layout.update(
        title=titre or t('T° opérative vs T° extérieure — {zone}', zone=zone),
        xaxis=dict(title=t('T extérieure (°C)'), gridcolor=grille_color()),
        yaxis=dict(title=t('T opérative intérieure (°C)'), gridcolor=grille_color()),
        height=420,
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)


def graphique_meteo_comparaison(variantes) -> go.Figure:
    """
    Comparaison des fichiers météo : température extérieure moyenne mensuelle
    pour chaque météo distincte parmi les variantes. Une courbe par météo.
    """
    fig = go.Figure()
    jours_mois = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    vus = {}
    idx = 0
    for var in variantes:
        if var.df_meteo.empty:
            continue
        nom = var.meteo_affiche() or t("météo")
        if nom in vus:
            continue
        vus[nom] = True
        t_ext = var.df_meteo['T_ext'].values
        n = len(t_ext)
        mois = np.repeat(range(1, 13), [d * 24 for d in jours_mois])[:n]
        df = pd.DataFrame({'mois': mois, 't': t_ext[:len(mois)]})
        moy = df.groupby('mois')['t'].mean()
        color = COULEURS_VARIANTES[idx % len(COULEURS_VARIANTES)]
        idx += 1
        fig.add_trace(go.Scatter(
            x=[noms_mois()[int(m) - 1] for m in moy.index], y=moy.values,
            mode='lines+markers', name=nom, line=dict(color=color, width=2),
        ))

    layout = get_layout()
    layout.update(
        title=t("Comparaison des fichiers météo — T° extérieure moyenne mensuelle"),
        xaxis=dict(title=t('Mois')), yaxis=dict(title=t('T extérieure (°C)'), gridcolor=grille_color()),
        height=380,
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)


def graphique_heures_depassement(
    variantes: list,
    zones: list[str],
    seuil_t1: float,
    seuil_t2: float,
    mode: str = 'zones',  # 'zones' ou 'variantes'
) -> go.Figure:
    """Barres groupées heures de dépassement par zone ou variante."""
    fig = go.Figure()

    if mode == 'zones':
        # Un groupe par zone, deux barres (T1, T2) par variante
        x_labels = zones
        for i, var in enumerate(variantes):
            color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
            h1 = [var.heures_dessus_seuil(z, seuil_t1) for z in zones]
            h2 = [var.heures_dessus_seuil(z, seuil_t2) for z in zones]
            fig.add_trace(go.Bar(
                x=x_labels, y=h1,
                name=f'{var.nom} > {seuil_t1}°C',
                marker=dict(color=color, opacity=0.85),
                **bar_labels(".0f"),
            ))
            fig.add_trace(go.Bar(
                x=x_labels, y=h2,
                name=f'{var.nom} > {seuil_t2}°C',
                marker=dict(color=color, opacity=0.5),
                **bar_labels(".0f"),
            ))
    else:
        for i, var in enumerate(variantes):
            color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
            h1 = [var.heures_dessus_seuil(z, seuil_t1) for z in zones]
            fig.add_trace(go.Bar(x=zones, y=h1, name=var.nom, marker_color=color,
                                 **bar_labels(".0f")))

    layout = get_layout()
    layout.update(
        title=t('Heures de dépassement (seuils {s1}°C / {s2}°C)', s1=seuil_t1, s2=seuil_t2),
        xaxis=dict(title=t('Zone'), tickangle=-30),
        yaxis=dict(title=t('Heures / an')),
        barmode='group',
        height=420,
        uniformtext=dict(minsize=8, mode='hide'),
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)


def graphique_temp_min_moy_max(
    variantes: list,
    zones: list[str],
    titre: str | None = None,
) -> go.Figure:
    """Barres groupées T min / moy / max par zone (comparaison variantes)."""
    fig = go.Figure()
    # Une variante = un groupe de 3 barres (min/moy/max) par zone.
    for i, var in enumerate(variantes):
        color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
        t_min, t_moy, t_max = [], [], []
        for zone in zones:
            st = var.stats_temp(zone)
            t_min.append(round(st['t_min'], 1))
            t_moy.append(round(st['t_moy'], 1))
            t_max.append(round(st['t_max'], 1))
        suffixe = f" — {var.nom}" if len(variantes) > 1 else ""
        fig.add_trace(go.Bar(x=zones, y=t_min, name=f"{t('T min')}{suffixe}",
                             marker=dict(color=color, opacity=0.45), **bar_labels()))
        fig.add_trace(go.Bar(x=zones, y=t_moy, name=f"{t('T moy')}{suffixe}",
                             marker=dict(color=color, opacity=0.7), **bar_labels()))
        fig.add_trace(go.Bar(x=zones, y=t_max, name=f"{t('T max')}{suffixe}",
                             marker=dict(color=color, opacity=1.0), **bar_labels()))

    layout = get_layout()
    layout.update(
        title=titre or t('Températures min / moyenne / max par zone'),
        xaxis=dict(title=t('Zone'), tickangle=-30),
        yaxis=dict(title=t('Température (°C)'), gridcolor=grille_color()),
        barmode='group',
        height=440,
        uniformtext=dict(minsize=8, mode='hide'),
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)


def graphique_apports_solaires(
    variantes: list,
    zone: str,
    titre: str | None = None,
    type_apport: str = "solaires",
) -> go.Figure:
    """Apports mensuels (solaires ou internes) en barres — comparaison variantes."""
    fig = go.Figure()
    libelle = t("internes" if type_apport == "internes" else "solaires")

    for i, var in enumerate(variantes):
        monthly = var.apports_mensuels(zone, type_apport)
        if monthly.empty:
            continue
        color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
        fig.add_trace(go.Bar(
            x=[noms_mois()[int(m)-1] for m in monthly.index],
            y=monthly.values,
            name=var.nom,
            marker=dict(color=color, opacity=0.85),
            **bar_labels(".0f"),
        ))

    layout = get_layout()
    layout.update(
        title=titre or t('Apports {libelle} mensuels — {zone}', libelle=libelle, zone=zone),
        xaxis=dict(title=t('Mois')),
        yaxis=dict(title=_cap(t('Apports {libelle} (kWh)', libelle=libelle))),
        barmode='group',
        height=380,
        uniformtext=dict(minsize=7, mode='hide'),
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)


def heatmap_temp_jour_heure(
    var,                       # Variante
    zone: str,
    occupation_seulement: bool = False,
    zmin: float | None = None,
    zmax: float | None = None,
    titre: str | None = None,
) -> go.Figure | None:
    """
    Carte de chaleur de la température intérieure : jour (x) × heure du jour (y),
    couleur = T °C. Lit d'un coup le cycle journalier ET la dérive saisonnière
    des ~8 760 valeurs horaires de l'année. Une carte par variante.

    - Respecte la période d'analyse active et le filtre heures d'occupation.
    - zmin/zmax : bornes de l'échelle de couleur (fixer les mêmes pour deux
      variantes les rend directement comparables) ; auto si None.
    Retourne None si la zone n'a pas de colonne température.
    """
    s = var.col_temp(zone)
    if s.empty:
        return None
    n = len(s)
    xi = pd.DatetimeIndex(np.asarray(var.horodatage())[:n])
    y = np.asarray(s.values[:n], dtype=float)
    if occupation_seulement:
        occ = var.col_apports_occupants(zone)
        if not occ.empty:
            y = y.copy()
            y[~(occ.values[:n] > 0)] = np.nan
    m = var.masque_periode(n)
    xi, y = xi[m], y[m]
    if len(xi) == 0:
        return None
    d = pd.DataFrame({'date': xi.normalize(), 'hour': xi.hour, 't': y})
    # pivot (et non pivot_table) : chaque couple (jour, heure) est unique sur
    # l'année → pas d'agrégation nécessaire, reshape direct plus rapide.
    piv = d.pivot(index='hour', columns='date', values='t').reindex(range(24))
    fig = go.Figure(go.Heatmap(
        x=piv.columns, y=piv.index, z=piv.values,
        colorscale='RdYlBu_r', zmin=zmin, zmax=zmax,
        colorbar=dict(title='T °C'),
        hovertemplate='%{x|%d %b} · %{y}h<br>T = %{z:.1f}°C<extra></extra>'))
    layout = get_layout()
    layout.update(
        title=titre or t('Température horaire — {zone} · {variante} (jour × heure)',
                         zone=zone, variante=var.nom),
        xaxis=dict(title=t('Date'), type='date'),
        yaxis=dict(title=t('Heure'), dtick=6, range=[-0.5, 23.5]),
        height=360,
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)


def graphique_apports_par_zone_mensuel(
    variante,
    zones: list[str],
    type_apport: str = "solaires",
    titre: str | None = None,
) -> go.Figure:
    """
    Apports mensuels : une barre par mois par zone (échantillon de zones,
    une seule variante). x = mois, une couleur par zone, barres groupées.
    """
    fig = go.Figure()
    libelle = t("internes" if type_apport == "internes" else "solaires")

    for i, zone in enumerate(zones):
        monthly = variante.apports_mensuels(zone, type_apport)
        if monthly.empty:
            continue
        # Réindexer sur 1-12 pour aligner toutes les zones
        monthly = monthly.reindex(range(1, 13), fill_value=0)
        color = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
        fig.add_trace(go.Bar(
            x=noms_mois(),
            y=monthly.values,
            name=zone,
            marker=dict(color=color, opacity=0.9),
            **bar_labels(".0f"),
        ))

    layout = get_layout()
    layout.update(
        title=titre or t('Apports {libelle} mensuels par zone — {variante}',
                         libelle=libelle, variante=variante.nom),
        xaxis=dict(title=t('Mois')),
        yaxis=dict(title=_cap(t('Apports {libelle} (kWh)', libelle=libelle))),
        barmode='group',
        height=440,
        uniformtext=dict(minsize=7, mode='hide'),
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)
