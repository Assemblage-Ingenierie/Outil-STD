"""Diagramme de Givoni (diagramme bioclimatique psychrométrique) avec Plotly."""
import numpy as np
import plotly.graph_objects as go
from config.charte import (
    ROUGE, VIOLET, GRIS, ROUGE_CLAIR, GRIS_CLAIR, BLANC, NOIR, NOIR70,
    COULEURS_VARIANTES, PLOTLY_LAYOUT
)
from core.try_parser import humidite_absolue


def _courbes_saturation() -> tuple[np.ndarray, np.ndarray]:
    """Génère la courbe de saturation RH=100% (T, w)."""
    T = np.linspace(-5, 50, 300)
    w = humidite_absolue(T, 100)
    return T, w


def _courbe_rh(rh: float, t_range=(-5, 50)) -> tuple[np.ndarray, np.ndarray]:
    T = np.linspace(t_range[0], t_range[1], 200)
    w = humidite_absolue(T, rh)
    return T, w


def _zone_confort_polygon(t_min, t_max, w_min, w_max) -> tuple[list, list]:
    T = [t_min, t_max, t_max, t_min, t_min]
    W = [w_min, w_min, w_max, w_max, w_min]
    return T, W


def creer_givoni(
    df_meteo,
    config: dict,
    variantes_extra: list[dict] | None = None,
    titre: str = "Diagramme de Givoni — Conditions extérieures",
    periode: tuple[int, int] | None = None,  # (mois_debut, mois_fin)
    colorby: str = "mois",  # "mois" ou "heure"
) -> go.Figure:
    """
    Crée le diagramme de Givoni.

    Args:
        df_meteo: DataFrame météo (colonnes T_ext, HR_ext, w_ext)
        config: dict avec clés givoni (t_confort_min, t_confort_max, w_confort_min, w_confort_max)
        variantes_extra: liste optionnelle de dicts {'label': str, 'df_meteo': df} pour comparaison
        titre: titre du graphique
        periode: filtre mois (1=jan ... 12=dec), None = année entière
        colorby: comment colorer les points
    """
    fig = go.Figure()

    # -- Courbes iso-humidité relative --
    for rh in [20, 40, 60, 80, 100]:
        T_rh, w_rh = _courbe_rh(rh)
        # Clip au domaine utile
        mask = w_rh <= 30
        fig.add_trace(go.Scatter(
            x=T_rh[mask], y=w_rh[mask],
            mode='lines',
            line=dict(color=GRIS, width=0.8, dash='dot'),
            showlegend=(rh == 20),
            legendgroup='iso_rh',
            name=f'Iso-HR {rh}%' if rh == 20 else f'{rh}%',
            hovertemplate=f'HR={rh}%<br>T=%{{x:.1f}}°C<br>w=%{{y:.2f}} g/kg<extra></extra>',
        ))
        # Label
        t_label = 35
        w_label = float(humidite_absolue(t_label, rh))
        if 0 < w_label < 28:
            fig.add_annotation(
                x=t_label, y=w_label,
                text=f'{rh}%',
                showarrow=False,
                font=dict(size=8, color=NOIR70),
                xanchor='left',
            )

    # -- Zone de confort --
    gc = config.get('givoni', {})
    t_c_min = gc.get('t_confort_min', 18)
    t_c_max = gc.get('t_confort_max', 27)
    w_c_min = gc.get('w_confort_min', 4)
    w_c_max = gc.get('w_confort_max', 12)

    T_zc, W_zc = _zone_confort_polygon(t_c_min, t_c_max, w_c_min, w_c_max)
    fig.add_trace(go.Scatter(
        x=T_zc, y=W_zc,
        fill='toself',
        fillcolor='rgba(46,204,113,0.15)',
        line=dict(color='#2ECC71', width=1.5),
        name='Zone de confort',
        hoverinfo='skip',
    ))

    # -- Points météo horaires --
    df = df_meteo.copy()
    if periode:
        # Filtrage par mois: ajouter colonne mois si absente
        # Le df météo TRY n'a pas de colonne mois, on la génère depuis l'index
        n = len(df)
        mois_arr = np.repeat(range(1, 13), [
            31*24, 28*24, 31*24, 30*24, 31*24, 30*24,
            31*24, 31*24, 30*24, 31*24, 30*24, 31*24
        ])[:n]
        df['mois_'] = mois_arr
        df = df[(df['mois_'] >= periode[0]) & (df['mois_'] <= periode[1])]

    if colorby == "mois":
        # Colorer par mois (12 couleurs)
        n = len(df)
        mois_arr = np.repeat(range(1, 13), [
            31*24, 28*24, 31*24, 30*24, 31*24, 30*24,
            31*24, 31*24, 30*24, 31*24, 30*24, 31*24
        ])[:n]
        df = df.copy()
        df['mois_plot'] = mois_arr[:len(df)]

        noms_mois = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
        couleurs_mois = [
            '#2196F3','#42A5F5','#66BB6A','#26A69A',
            '#FFA726','#FF7043','#E30513','#C62828',
            '#8D6E63','#78909C','#5C6BC0','#26C6DA'
        ]
        for m in range(1, 13):
            mask = df['mois_plot'] == m
            sub = df[mask]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub['T_ext'], y=sub['w_ext'],
                mode='markers',
                marker=dict(size=2, color=couleurs_mois[m-1], opacity=0.5),
                name=noms_mois[m-1],
                legendgroup=f'mois_{m}',
                hovertemplate=f'T=%{{x:.1f}}°C<br>w=%{{y:.2f}} g/kg<extra>{noms_mois[m-1]}</extra>',
            ))
    else:
        fig.add_trace(go.Scatter(
            x=df['T_ext'], y=df['w_ext'],
            mode='markers',
            marker=dict(size=2, color=VIOLET, opacity=0.4),
            name='Données horaires',
            hovertemplate='T=%{x:.1f}°C<br>w=%{y:.2f} g/kg<extra></extra>',
        ))

    # -- Variantes supplémentaires --
    if variantes_extra:
        for i, v in enumerate(variantes_extra):
            df_v = v['df_meteo']
            color = COULEURS_VARIANTES[(i+1) % len(COULEURS_VARIANTES)]
            fig.add_trace(go.Scatter(
                x=df_v['T_ext'], y=df_v['w_ext'],
                mode='markers',
                marker=dict(size=2, color=color, opacity=0.4),
                name=v['label'],
                hovertemplate=f'T=%{{x:.1f}}°C<br>w=%{{y:.2f}} g/kg<extra>{v["label"]}</extra>',
            ))

    # -- Mise en forme --
    layout = dict(PLOTLY_LAYOUT)
    layout.update(
        title=titre,
        xaxis=dict(title='Température sèche (°C)', range=[-5, 45], gridcolor=GRIS),
        yaxis=dict(title='Humidité absolue (g/kg a.s.)', range=[0, 30], gridcolor=GRIS),
        legend=dict(itemsizing='constant'),
        height=550,
    )
    fig.update_layout(**layout)

    return fig
