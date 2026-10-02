"""Diagramme de confort adaptatif EN 16798-1 (θrm en abscisse, T intérieure en
ordonnée) — équivalent adaptatif du diagramme de Givoni."""
import numpy as np
import plotly.graph_objects as go

from config.charte import (
    ROUGE, FONT_FAMILY, get_layout, annotation_color, grille_color, finalize_fig,
)
from core import confort_en16798 as en


COULEUR_CONFORT = "#2ECC71"   # vert — dans la bande
COULEUR_CHAUD = ROUGE         # rouge — au-dessus de la limite haute
COULEUR_FROID = "#2196F3"     # bleu — sous la limite basse
COULEUR_HORS = "#9E9E9E"      # gris — occupé mais θrm hors domaine
COULEUR_BANDE = "#16A085"
ROMAIN = {1: "I", 2: "II", 3: "III"}
# Remplissage des bandes de fond (de la plus large à la plus étroite)
ALPHA_BANDE = {3: 0.06, 2: 0.10, 1: 0.16}

T_MIN_PLOT, T_MAX_PLOT = 10.0, 40.0


def _segment(plage, x_min, x_max):
    lo, hi = plage
    return max(lo, x_min), min(hi, x_max)


def creer_diagramme_adaptatif(
    res: dict,
    t_int,
    titre: str | None = None,
    bandes_fond: bool = True,
    afficher_hors_domaine: bool = True,
) -> go.Figure:
    """
    Nuage θrm / T intérieure des heures OCCUPÉES, coloré confort / chaud / froid,
    avec les limites de la catégorie évaluée (traits pleins) et, en fond, les
    bandes des catégories I, II, III (remplissage transparent).

    Args:
        res   : résultat de ``confort_en16798.compute_en16798_adaptive``.
        t_int : température intérieure horaire (même alignement que ``res``).
        titre : titre de la figure (auto si None).
        bandes_fond : superposer les bandes Cat. I / II / III en transparence.
        afficher_hors_domaine : points occupés dont θrm sort du domaine en gris.
    """
    cat = res["category"]
    trm = res["trm_hourly"].to_numpy()
    n = len(trm)
    ti = np.asarray(t_int, dtype=float)[:n]
    warm = res["warm"].to_numpy()
    cold = res["cold"].to_numpy()
    ok = res["comfortable"].to_numpy()
    hors = res["occupied"].to_numpy() & ~res["trm_in_range"].to_numpy()
    evalue = warm | cold | ok

    x_min = float(np.floor(min(np.nanmin(trm), en.TRM_RANGE[0]) - 1))
    x_max = float(np.ceil(max(np.nanmax(trm), en.TRM_RANGE[1]) + 1))
    xs = np.array([x_min, x_max])

    fig = go.Figure()

    # ------------------------------------------------------------------
    # 1. Bandes de fond Cat. III → I (Tableau B.2), là où les deux limites
    #    s'appliquent (θrm 15–30 °C) ; entre 10 et 15 °C seule la limite haute
    #    de la catégorie évaluée est tracée.
    # ------------------------------------------------------------------
    if bandes_fond:
        lo = max(en.TRM_RANGE[0], en.TRM_RANGE_LOWER[0], x_min)
        hi = min(en.TRM_RANGE[1], en.TRM_RANGE_LOWER[1], x_max)
        xb = np.array([lo, hi, hi, lo, lo])
        tc = en.temperature_confort(xb)
        for c in (3, 2, 1):
            bas, haut = en.BANDES_EN16798[c]
            yb = tc + np.array([haut, haut, -bas, -bas, haut])
            fig.add_trace(go.Scatter(
                x=xb, y=yb, mode="lines", fill="toself",
                fillcolor=f"rgba(22,160,133,{ALPHA_BANDE[c]})",
                line=dict(width=0), name=f"Bande Cat. {ROMAIN[c]}",
                legendgroup="bandes", hoverinfo="skip",
            ))

    # θc (confort optimal) en pointillés
    fig.add_trace(go.Scatter(
        x=xs, y=en.temperature_confort(xs), mode="lines",
        line=dict(color=COULEUR_BANDE, width=1, dash="dot"),
        name="θc = 0,33·θrm + 18,8", hoverinfo="skip",
    ))

    # ------------------------------------------------------------------
    # 2. Points horaires occupés
    # ------------------------------------------------------------------
    hover = "θrm=%{x:.1f}°C<br>T int=%{y:.1f}°C<extra>%{fullData.name}</extra>"
    for m, label, couleur in (
        (ok, "Confortable", COULEUR_CONFORT),
        (warm, "Inconfort chaud", COULEUR_CHAUD),
        (cold, "Inconfort froid", COULEUR_FROID),
    ):
        fig.add_trace(go.Scatter(
            x=trm[m], y=ti[m], mode="markers",
            marker=dict(size=4, color=couleur, opacity=0.55),
            name=f"{label} ({int(m.sum())} h)", hovertemplate=hover,
        ))
    if afficher_hors_domaine and hors.any():
        fig.add_trace(go.Scatter(
            x=trm[hors], y=ti[hors], mode="markers",
            marker=dict(size=4, color=COULEUR_HORS, opacity=0.4),
            name=f"θrm hors domaine ({int(hors.sum())} h, non évaluées)",
            hovertemplate=hover,
        ))

    # ------------------------------------------------------------------
    # 3. Limites de la catégorie évaluée (traits pleins)
    # ------------------------------------------------------------------
    bas, haut = en.BANDES_EN16798[cat]
    xh = np.array(_segment(en.TRM_RANGE, x_min, x_max))
    xb = np.array(_segment(en.TRM_RANGE_LOWER, x_min, x_max))
    fig.add_trace(go.Scatter(
        x=xh, y=en.temperature_confort(xh) + haut, mode="lines",
        line=dict(color=COULEUR_CHAUD, width=2),
        name=f"Limite haute Cat. {ROMAIN[cat]} (θc + {haut:g} K)",
        hovertemplate="θrm=%{x:.1f}°C<br>θi,max=%{y:.1f}°C<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=xb, y=en.temperature_confort(xb) - bas, mode="lines",
        line=dict(color=COULEUR_FROID, width=2),
        name=f"Limite basse Cat. {ROMAIN[cat]} (θc − {bas:g} K)",
        hovertemplate="θrm=%{x:.1f}°C<br>θi,min=%{y:.1f}°C<extra></extra>",
    ))

    # ------------------------------------------------------------------
    # 4. Mise en forme
    # ------------------------------------------------------------------
    pct = res["discomfort_pct"]
    pct_txt = f"{pct:.1f} %".replace(".", ",") if pct == pct else "NA"
    if titre is None:
        titre = "Confort adaptatif EN 16798-1"
    titre = f"{titre} — inconfort Cat. {ROMAIN[cat]} : {pct_txt}"

    y_vals = ti[evalue] if evalue.any() else ti
    y_lo = min(T_MIN_PLOT, float(np.nanmin(y_vals)) - 1) if len(y_vals) else T_MIN_PLOT
    y_hi = max(T_MAX_PLOT, float(np.nanmax(y_vals)) + 1) if len(y_vals) else T_MAX_PLOT

    layout = get_layout()
    layout.update(
        title=titre,
        xaxis=dict(title="θrm — moyenne glissante de T extérieure (°C)",
                   range=[x_min, x_max], gridcolor=grille_color()),
        yaxis=dict(title="Température intérieure (°C)", range=[y_lo, y_hi],
                   gridcolor=grille_color()),
        legend=dict(itemsizing="constant"),
        height=620,
        margin=dict(l=60, r=30, t=60, b=110),
    )
    fig.update_layout(**layout)
    fig.add_annotation(
        xref="paper", yref="paper", x=0.0, y=-0.14, xanchor="left", yanchor="top",
        showarrow=False, align="left",
        font=dict(size=10, color=annotation_color(), family=FONT_FAMILY),
        text=(f"Heures occupées évaluées : {res['total_occupied_valid']} h "
              f"(θrm entre {en.TRM_RANGE[0]:g} et {en.TRM_RANGE[1]:g} °C ; limite basse "
              f"appliquée pour θrm ≥ {en.TRM_RANGE_LOWER[0]:g} °C). "
              f"Hors domaine : {res['occupied_out_of_range']} h non évaluées."),
    )
    return finalize_fig(fig)
