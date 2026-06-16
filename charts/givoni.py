"""Diagramme bioclimatique (Givoni ou COCO) avec Plotly."""
import numpy as np
import plotly.graph_objects as go

from config.charte import (
    ROUGE, VIOLET, GRIS, GRIS_CLAIR, BLANC, NOIR, NOIR70,
    GRILLE, COURBE_REF, PLOTLY_LAYOUT
)
from core.try_parser import humidite_absolue
from core import confort


COULEUR_CHAUFFE = "#2196F3"        # bleu — saison de chauffe
COULEUR_REFROIDISSEMENT = ROUGE    # rouge — saison de refroidissement
COULEUR_INTERSAISON = "#757575"    # gris foncé — hors saison marquée

W_MAX_PLOT = 30.0
T_MIN_PLOT = -5.0
T_MAX_PLOT = 45.0


def _courbe_rh(rh: float) -> tuple[np.ndarray, np.ndarray]:
    """Courbe iso-humidité relative (T, w) jusqu'au plafond d'affichage."""
    T = np.linspace(T_MIN_PLOT, T_MAX_PLOT, 250)
    w = humidite_absolue(T, rh)
    mask = w <= W_MAX_PLOT
    return T[mask], w[mask]


def _classer_saison(saison_arr: np.ndarray) -> np.ndarray:
    out = np.full(len(saison_arr), "inter", dtype=object)
    for i, s in enumerate(saison_arr):
        s = str(s).strip().lower()
        if "refroid" in s:
            out[i] = "refroidissement"
        elif "chauff" in s:
            out[i] = "chauffe"
    return out


def creer_givoni(
    df_meteo,
    config: dict,
    methode: str = "givoni",
    saison=None,
    titre: str | None = None,
    periode: tuple[int, int] | None = None,
) -> go.Figure:
    """
    Crée le diagramme bioclimatique (Givoni ou COCO) des conditions extérieures.

    Args:
        df_meteo : DataFrame météo (colonnes T_ext, w_ext)
        config   : configuration projet (bornes Givoni)
        methode  : 'givoni' (4 zones par vitesse d'air) ou 'coco' (2 zones tropicales)
        saison   : Series/array de saison Pléiades, aligné par position avec df_meteo
        titre    : titre (auto si None)
        periode  : filtre (mois_debut, mois_fin), None = année entière
    """
    methode = (methode or "givoni").lower()
    if titre is None:
        nom = "COCO" if methode == "coco" else "Givoni"
        titre = f"Diagramme de {nom} — Conditions extérieures"

    fig = go.Figure()

    # ------------------------------------------------------------------
    # 1. Courbe de saturation (HR 100 %) + courbes iso-HR
    # ------------------------------------------------------------------
    T_sat, w_sat = _courbe_rh(100)
    fig.add_trace(go.Scatter(
        x=T_sat, y=w_sat, mode="lines",
        line=dict(color=VIOLET, width=2),
        name="Saturation (HR 100 %)",
        hovertemplate="Saturation<br>T=%{x:.1f}°C<br>w=%{y:.2f} g/kg<extra></extra>",
    ))
    for rh in [20, 40, 60, 80]:
        T_rh, w_rh = _courbe_rh(rh)
        fig.add_trace(go.Scatter(
            x=T_rh, y=w_rh, mode="lines",
            line=dict(color=COURBE_REF, width=1.1, dash="dot"),
            name=f"HR {rh} %", legendgroup="iso_rh", showlegend=False,
            hovertemplate=f"HR {rh}%<br>T=%{{x:.1f}}°C<br>w=%{{y:.2f}} g/kg<extra></extra>",
        ))
        if len(T_rh):
            fig.add_annotation(
                x=T_rh[-1], y=w_rh[-1], text=f"{rh}%", showarrow=False,
                font=dict(size=9, color=NOIR70), xanchor="left", yanchor="bottom",
            )

    # ------------------------------------------------------------------
    # 2. Zones de confort (polygones) — de la plus large à la plus restreinte
    # ------------------------------------------------------------------
    zones = confort.zones_modele(config, methode)
    couleurs = confort.COULEURS_ZONES
    for idx, (v, label, T_z, W_z) in enumerate(reversed(zones)):
        couleur = couleurs[(len(zones) - 1 - idx) % len(couleurs)]
        fig.add_trace(go.Scatter(
            x=T_z, y=W_z, mode="lines", fill="toself",
            fillcolor="rgba(46,204,113,0.08)",
            line=dict(color=couleur, width=1.8),
            name=label, hoverinfo="skip",
        ))

    # ------------------------------------------------------------------
    # 3. Points météo horaires colorés par saison
    # ------------------------------------------------------------------
    df = df_meteo.copy().reset_index(drop=True)
    n = len(df)
    if n:
        jours_mois = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        mois_arr = np.repeat(range(1, 13), [d * 24 for d in jours_mois])[:n]
        df["_mois"] = mois_arr
        if saison is not None:
            sais = np.asarray(saison)[:n]
            if len(sais) < n:
                sais = np.concatenate([sais, np.full(n - len(sais), "")])
            df["_saison"] = _classer_saison(sais)
        else:
            df["_saison"] = "inter"
        if periode:
            df = df[(df["_mois"] >= periode[0]) & (df["_mois"] <= periode[1])]

        cats = [
            ("refroidissement", "Saison de refroidissement", COULEUR_REFROIDISSEMENT),
            ("chauffe", "Saison de chauffe", COULEUR_CHAUFFE),
            ("inter", "Inter-saison", COULEUR_INTERSAISON),
        ]
        for key, label, couleur in cats:
            sub = df[df["_saison"] == key]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub["T_ext"], y=sub["w_ext"], mode="markers",
                marker=dict(size=3, color=couleur, opacity=0.45),
                name=label,
                hovertemplate="T=%{x:.1f}°C<br>w=%{y:.2f} g/kg<extra>" + label + "</extra>",
            ))

    # ------------------------------------------------------------------
    # 4. Mise en forme
    # ------------------------------------------------------------------
    layout = dict(PLOTLY_LAYOUT)
    layout.update(
        title=titre,
        xaxis=dict(title="Température opérative (°C)", range=[T_MIN_PLOT, T_MAX_PLOT], gridcolor=GRILLE),
        yaxis=dict(title="Humidité absolue (g/kg air sec)", range=[0, W_MAX_PLOT], gridcolor=GRILLE),
        legend=dict(itemsizing="constant"),
        height=600,
    )
    fig.update_layout(**layout)
    return fig
