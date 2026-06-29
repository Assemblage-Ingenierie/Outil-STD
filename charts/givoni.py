"""Diagramme bioclimatique (Givoni ou COCO) avec Plotly."""
import numpy as np
import plotly.graph_objects as go

from config.charte import (
    ROUGE, VIOLET, GRIS, GRIS_CLAIR, BLANC, NOIR, FONT_FAMILY,
    COULEURS_VARIANTES,
    get_layout, annotation_color, grille_color, courbe_ref_color, is_dark, finalize_fig,
)
from core.try_parser import humidite_absolue
from core import confort


COULEUR_CHAUFFE = ROUGE            # rouge — saison de chauffe (chaud)
COULEUR_REFROIDISSEMENT = "#2196F3"  # bleu — saison de refroidissement (froid)
COULEUR_INTERSAISON = "#757575"    # gris foncé — hors saison de chauffe
COULEUR_POINTS_UNIQUE = "#1976D2"  # couleur unique (sans distinction de saison)

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
    series,
    config: dict,
    methode: str = "givoni",
    titre: str | None = None,
    par_saison: bool = True,
    par_periode: bool = False,
    note_chauffe: bool = True,
) -> go.Figure:
    """
    Crée le diagramme bioclimatique (Givoni ou COCO) des conditions INTÉRIEURES.

    Args:
        series      : liste de dicts {'label', 'T', 'w', 'saison'/'periode'(optionnel)}.
                      - 1 seule série : points colorés par saison (si par_saison)
                        ou par période de focus (si par_periode)
                      - plusieurs séries : une couleur par série (comparaison variantes)
        config      : configuration projet (bornes Givoni)
        methode     : 'givoni' (4 zones par vitesse d'air) ou 'coco' (2 zones tropicales)
        titre       : titre (auto si None)
        par_saison  : colorer les points selon la saison (sinon couleur unique)
        par_periode : colorer les points selon la période de focus (prioritaire
                      sur par_saison ; utilise le champ 'periode' de la série)
        note_chauffe : afficher la note d'hypothèse chauffe-sous-consigne (à ne
                      passer à True que si le fichier comporte une saison de chauffe)
    """
    methode = (methode or "givoni").lower()
    if isinstance(series, dict):
        series = [series]
    if titre is None:
        nom = "COCO" if methode == "coco" else "Givoni"
        titre = f"Diagramme de {nom} — Conditions intérieures"

    fig = go.Figure()

    # ------------------------------------------------------------------
    # 1. Courbe de saturation (HR 100 %) + courbes iso-HR
    # ------------------------------------------------------------------
    T_sat, w_sat = _courbe_rh(100)
    sat_color = VIOLET if not is_dark() else "#9C8FBF"
    fig.add_trace(go.Scatter(
        x=T_sat, y=w_sat, mode="lines",
        line=dict(color=sat_color, width=2),
        name="Saturation (HR 100 %)",
        hovertemplate="Saturation<br>T=%{x:.1f}°C<br>w=%{y:.2f} g/kg<extra></extra>",
    ))
    for rh in [20, 40, 60, 80]:
        T_rh, w_rh = _courbe_rh(rh)
        fig.add_trace(go.Scatter(
            x=T_rh, y=w_rh, mode="lines",
            line=dict(color=courbe_ref_color(), width=1.1, dash="dot"),
            name=f"HR {rh} %", legendgroup="iso_rh", showlegend=False,
            hovertemplate=f"HR {rh}%<br>T=%{{x:.1f}}°C<br>w=%{{y:.2f}} g/kg<extra></extra>",
        ))
        if len(T_rh):
            fig.add_annotation(
                x=T_rh[-1], y=w_rh[-1], text=f"{rh}%", showarrow=False,
                font=dict(size=9, color=annotation_color()), xanchor="left", yanchor="bottom",
            )

    # ------------------------------------------------------------------
    # 2. Zones de confort (polygones) — de la plus large à la plus restreinte
    # ------------------------------------------------------------------
    # Zones discrètes (arrière-plan) : remplissage quasi transparent, contour fin.
    zones = confort.zones_modele(config, methode)
    couleurs = confort.COULEURS_ZONES
    for idx, (v, label, T_z, W_z) in enumerate(reversed(zones)):
        couleur = couleurs[(len(zones) - 1 - idx) % len(couleurs)]
        fig.add_trace(go.Scatter(
            x=T_z, y=W_z, mode="lines", fill="toself",
            fillcolor="rgba(46,204,113,0.04)",
            line=dict(color=couleur, width=1.0),
            name=label, hoverinfo="skip", opacity=0.7,
        ))

    # ------------------------------------------------------------------
    # 3. Points horaires intérieurs
    # ------------------------------------------------------------------
    series = [s for s in (series or []) if s is not None and len(s.get('T', [])) > 0]

    if len(series) == 1:
        s = series[0]
        T = np.asarray(s['T'], float)
        w = np.asarray(s['w'], float)
        if par_periode:
            # Coloration par période de focus (été / hiver / … définies en Réglages)
            per = np.asarray(s.get('periode', np.array([''] * len(T))), dtype=object)
            noms = list(dict.fromkeys(per))  # uniques, ordre d'apparition
            for k, nom in enumerate(noms):
                m = per == nom
                if not m.any():
                    continue
                label = str(nom) if str(nom) else "Hors période"
                couleur = (COULEUR_INTERSAISON if not str(nom)
                           else COULEURS_VARIANTES[k % len(COULEURS_VARIANTES)])
                fig.add_trace(go.Scatter(
                    x=T[m], y=w[m], mode="markers",
                    marker=dict(size=4, color=couleur, opacity=0.6),
                    name=label,
                    hovertemplate="T=%{x:.1f}°C<br>w=%{y:.2f} g/kg<extra>" + label + "</extra>",
                ))
        elif par_saison:
            # Coloration par saison
            sais = _classer_saison(np.asarray(s.get('saison', np.array([''] * len(T)))))
            cats = [
                ("refroidissement", "Saison de refroidissement", COULEUR_REFROIDISSEMENT),
                ("chauffe", "Saison de chauffe", COULEUR_CHAUFFE),
                ("inter", "Hors saison de chauffe", COULEUR_INTERSAISON),
            ]
            for key, label, couleur in cats:
                m = sais == key
                if not m.any():
                    continue
                fig.add_trace(go.Scatter(
                    x=T[m], y=w[m], mode="markers",
                    marker=dict(size=4, color=couleur, opacity=0.6),
                    name=label,
                    hovertemplate="T=%{x:.1f}°C<br>w=%{y:.2f} g/kg<extra>" + label + "</extra>",
                ))
        else:
            # Couleur unique (sans distinction de saison)
            fig.add_trace(go.Scatter(
                x=T, y=w, mode="markers",
                marker=dict(size=4, color=COULEUR_POINTS_UNIQUE, opacity=0.55),
                name="Conditions intérieures",
                hovertemplate="T=%{x:.1f}°C<br>w=%{y:.2f} g/kg<extra></extra>",
            ))
    else:
        # Une couleur par série (comparaison de variantes)
        for i, s in enumerate(series):
            couleur = COULEURS_VARIANTES[i % len(COULEURS_VARIANTES)]
            fig.add_trace(go.Scatter(
                x=np.asarray(s['T'], float), y=np.asarray(s['w'], float),
                mode="markers",
                marker=dict(size=4, color=couleur, opacity=0.55),
                name=s.get('label', f'Série {i+1}'),
                hovertemplate="T=%{x:.1f}°C<br>w=%{y:.2f} g/kg<extra>" + s.get('label', '') + "</extra>",
            ))

    # ------------------------------------------------------------------
    # 4. Mise en forme
    # ------------------------------------------------------------------
    layout = get_layout()
    layout.update(
        title=titre,
        xaxis=dict(title="Température opérative (°C)", range=[T_MIN_PLOT, T_MAX_PLOT], gridcolor=grille_color()),
        yaxis=dict(title="Humidité absolue (g/kg air sec)", range=[0, W_MAX_PLOT], gridcolor=grille_color()),
        legend=dict(itemsizing="constant"),
        height=620,
        margin=dict(l=60, r=30, t=60, b=120),
    )
    fig.update_layout(**layout)

    # Hypothèse embarquée DANS la figure (donc rappelée aussi à l'export Word) :
    # les heures de chauffe sous la consigne sont écartées des points ET du décompte.
    # Affichée uniquement si le fichier comporte une saison de chauffe (note_chauffe).
    if note_chauffe:
        t_min = confort.t_min_modele(config, methode)
        fig.add_annotation(
            xref="paper", yref="paper", x=0.0, y=-0.155, xanchor="left", yanchor="top",
            showarrow=False, align="left",
            font=dict(size=10, color=annotation_color(), family=FONT_FAMILY),
            text=(f"Hypothèse : les heures où le local est chauffé alors que T est sous la "
                  f"borne basse de confort ({t_min:.0f} °C) sont exclues du diagramme et du "
                  f"décompte d'inconfort (chauffer sous le minimum de confort = choix de "
                  f"consigne, pas inconfort)."),
        )
    return finalize_fig(fig)
