"""Graphiques du confort adaptatif EN 16798-1 :
  - nuage θrm / T intérieure (focus zone), une ou plusieurs variantes ;
  - barres horizontales du % d'inconfort par zone (comparaison de zones)."""
import numpy as np
import plotly.graph_objects as go

from config.charte import (
    ROUGE, FONT_FAMILY,
    get_layout, annotation_color, grille_color, violet_color, finalize_fig,
)
from core import confort_en16798 as en
from config.i18n import t, nombre


COULEUR_CONFORT = "#2ECC71"   # vert — dans la bande
COULEUR_CHAUD = ROUGE         # rouge — au-dessus de la limite haute
COULEUR_FROID = "#2196F3"     # bleu — sous la limite basse
COULEUR_GRIS = "#B0B7BE"      # gris clair — non occupé / θrm hors domaine
COULEUR_BANDE = "#16A085"
ROMAIN = {1: "I", 2: "II", 3: "III"}
# Remplissage des bandes (de la plus large à la plus étroite)
ALPHA_BANDE = {3: 0.06, 2: 0.10, 1: 0.16}
# Variantes superposées : forme + couleur par variante. Palette dédiée, sans le
# rouge / bleu / vert réservés aux statuts et aux limites (lecture non ambiguë).
SYMBOLES = ["circle", "diamond", "triangle-up", "square", "cross", "star"]
# 1re couleur = violet charte, éclairci en thème sombre (cf. _couleur_variante).
COULEURS_SUPERPOSITION = [None, "#9C27B0", "#FF9800", "#00BCD4", "#8D6E63", "#E91E63"]

# Paliers de couleur du bar chart (% d'inconfort) : (borne haute, couleur)
PALIERS_BARRES = [(5.0, "#2ECC71"), (15.0, "#F4D03F"), (25.0, "#F39C12"), (np.inf, ROUGE)]

T_MIN_PLOT, T_MAX_PLOT = 10.0, 40.0
MAX_POINTS_DEFAUT = 6000      # points « de fond » par variante au-delà desquels on sous-échantillonne


def _couleur_variante(k: int) -> str:
    c = COULEURS_SUPERPOSITION[k % len(COULEURS_SUPERPOSITION)]
    return c or violet_color()


def _pct_txt(p) -> str:
    return f"{nombre(p, '.1f')} %" if p == p else "NA"


def _sous_echantillon(masque: np.ndarray, budget: int) -> np.ndarray:
    """Garde 1 point sur N parmi ``masque`` pour ne pas dépasser ``budget``."""
    idx = np.flatnonzero(masque)
    if budget <= 0 or len(idx) <= budget:
        return masque
    pas = int(np.ceil(len(idx) / budget))
    out = np.zeros_like(masque)
    out[idx[::pas]] = True
    return out


def _libelles_dates(horodatage, n: int) -> np.ndarray:
    """Date/heure lisible pour le survol (repli « heure n » sans index datetime)."""
    try:
        return np.asarray(horodatage[:n].strftime("%d/%m %Hh"))
    except (AttributeError, TypeError):
        return np.array([t("heure {i}", i=i + 1) for i in range(n)])


# ======================================================================
# 1. Nuage θrm / T intérieure (focus zone)
# ======================================================================

def creer_scatter_adaptatif(
    series: list[dict],
    titre: str,
    bandes_123: bool = False,
    afficher_gris: bool = True,
    max_points: int = MAX_POINTS_DEFAUT,
) -> go.Figure:
    """
    Nuage des heures (θrm, T intérieure) avec les limites EN 16798-1.

    Args:
        series : liste de dicts {'label', 'res', 't_int', 'horodatage'} où ``res``
                 est le résultat de ``compute_en16798_adaptive`` (même catégorie
                 pour toutes les séries), ``t_int`` la T intérieure horaire et
                 ``horodatage`` l'index datetime (survol), optionnel.
                 - 1 série : points colorés confortable / trop chaud / trop froid.
                 - plusieurs séries : une couleur ET une forme par variante.
        titre  : titre complet de la figure.
        bandes_123 : superposer les bandes Cat. I / II / III en transparence.
        afficher_gris : heures non évaluées (non occupées ou θrm hors domaine)
                 en gris clair, en arrière-plan (une seule série uniquement).
        max_points : au-delà, les points confortables et gris sont sous-échantillonnés
                 (1 sur N) ; les heures d'inconfort sont toujours toutes affichées.
    """
    series = [s for s in series if s.get("res") is not None]
    fig = go.Figure()
    if not series:
        return finalize_fig(fig)
    cat = series[0]["res"]["category"]
    bas_c, haut_c = en.BANDES_EN16798[cat]

    trm_all = np.concatenate([s["res"]["trm_hourly"].to_numpy() for s in series])
    x_min = float(np.floor(min(np.nanmin(trm_all), en.TRM_RANGE[0]) - 1))
    x_max = float(np.ceil(max(np.nanmax(trm_all), en.TRM_RANGE[1]) + 1))

    # ------------------------------------------------------------------
    # Bandes Cat. III → I (option), là où les deux limites s'appliquent
    # ------------------------------------------------------------------
    if bandes_123:
        lo = max(en.TRM_RANGE[0], en.TRM_RANGE_LOWER[0])
        hi = min(en.TRM_RANGE[1], en.TRM_RANGE_LOWER[1])
        xb = np.array([lo, hi, hi, lo, lo])
        tc = en.temperature_confort(xb)
        for c in (3, 2, 1):
            bas, haut = en.BANDES_EN16798[c]
            fig.add_trace(go.Scatter(
                x=xb, y=tc + np.array([haut, haut, -bas, -bas, haut]),
                mode="lines", fill="toself",
                fillcolor=f"rgba(22,160,133,{ALPHA_BANDE[c]})", line=dict(width=0),
                name=t("Bande Cat. {c}", c=ROMAIN[c]), legendgroup="bandes", hoverinfo="skip",
            ))

    # ------------------------------------------------------------------
    # Points
    # ------------------------------------------------------------------
    hover = ("%{customdata[0]}<br>T int = %{y:.1f} °C<br>θrm = %{x:.1f} °C"
             "<br>%{customdata[1]}<extra>%{customdata[2]}</extra>")

    def _points(trm, ti, m, dates, statut, label_var, nom, **marker):
        if not m.any():
            return
        cd = np.column_stack([dates[m], np.full(m.sum(), statut), np.full(m.sum(), label_var)])
        fig.add_trace(go.Scattergl(
            x=trm[m], y=ti[m], mode="markers", marker=marker, name=nom,
            customdata=cd, hovertemplate=hover,
        ))

    ymins, ymaxs = [], []
    for k, s in enumerate(series):
        r = s["res"]
        trm = r["trm_hourly"].to_numpy()
        n = len(trm)
        ti = np.asarray(s["t_int"], dtype=float)[:n]
        dates = _libelles_dates(s.get("horodatage"), n)
        ok, warm, cold = (r[c].to_numpy() for c in ("comfortable", "warm", "cold"))
        gris = ~(ok | warm | cold) & ~np.isnan(ti)
        ymins.append(np.nanmin(ti)), ymaxs.append(np.nanmax(ti))
        lab = s.get("label", "")

        if len(series) == 1:
            if afficher_gris:
                _points(trm, ti, _sous_echantillon(gris, max_points), dates,
                        t("Non évaluée (inoccupée ou θrm hors domaine)"), lab,
                        t("Non évaluées ({n} h)", n=int(gris.sum())),
                        size=3, color=COULEUR_GRIS, opacity=0.25)
            _points(trm, ti, _sous_echantillon(ok, max_points), dates, t("Confortable"), lab,
                    t("Confortable ({n} h)", n=int(ok.sum())),
                    size=4, color=COULEUR_CONFORT, opacity=0.55)
            _points(trm, ti, warm, dates, t("Trop chaud"), lab, t("Trop chaud ({n} h)", n=int(warm.sum())),
                    size=4, color=COULEUR_CHAUD, opacity=0.7)
            _points(trm, ti, cold, dates, t("Trop froid"), lab, t("Trop froid ({n} h)", n=int(cold.sum())),
                    size=4, color=COULEUR_FROID, opacity=0.7)
        else:
            # Superposition : heures évaluées seulement, couleur + forme par variante.
            # Budget par variante réduit pour garder un graphique fluide.
            evalue = _sous_echantillon(ok, max_points // len(series)) | warm | cold
            statut = np.where(warm, t("Trop chaud"), np.where(cold, t("Trop froid"), t("Confortable")))
            m = evalue
            cd = np.column_stack([dates[m], statut[m], np.full(m.sum(), lab)])
            fig.add_trace(go.Scattergl(
                x=trm[m], y=ti[m], mode="markers",
                marker=dict(size=5, color=_couleur_variante(k),
                            symbol=SYMBOLES[k % len(SYMBOLES)], opacity=0.55),
                name=f"{lab} — {_pct_txt(r['discomfort_pct'])}",
                customdata=cd, hovertemplate=hover,
            ))

    # ------------------------------------------------------------------
    # Limites de la catégorie (traits pleins) + θc (pointillés fins)
    # ------------------------------------------------------------------
    xh = np.array(en.TRM_RANGE, dtype=float)
    xl = np.array(en.TRM_RANGE_LOWER, dtype=float)
    fig.add_trace(go.Scatter(
        x=xh, y=en.temperature_confort(xh), mode="lines",
        line=dict(color=COULEUR_BANDE, width=1, dash="dot"),
        name=f"θc = {nombre(0.33, '.2f')}·θrm + {nombre(18.8, '.1f')}", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=xh, y=en.temperature_confort(xh) + haut_c, mode="lines",
        line=dict(color=COULEUR_CHAUD, width=2),
        name=t("Limite haute Cat. {c} (θc + {k} K)", c=ROMAIN[cat], k=f"{haut_c:g}"),
        hovertemplate="θrm = %{x:.1f} °C<br>θi,max = %{y:.1f} °C<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=xl, y=en.temperature_confort(xl) - bas_c, mode="lines",
        line=dict(color=COULEUR_FROID, width=2),
        name=t("Limite basse Cat. {c} (θc − {k} K)", c=ROMAIN[cat], k=f"{bas_c:g}"),
        hovertemplate="θrm = %{x:.1f} °C<br>θi,min = %{y:.1f} °C<extra></extra>",
    ))

    y_lo = min(T_MIN_PLOT, float(np.nanmin(ymins)) - 1)
    y_hi = max(T_MAX_PLOT, float(np.nanmax(ymaxs)) + 1)
    layout = get_layout()
    layout.update(
        title=titre,
        xaxis=dict(title=t("θrm — moyenne glissante de T extérieure (°C)"),
                   range=[x_min, x_max], gridcolor=grille_color()),
        yaxis=dict(title=t("Température intérieure (°C)"), range=[y_lo, y_hi],
                   gridcolor=grille_color()),
        legend=dict(itemsizing="constant"),
        hovermode="closest",
        height=620,
        margin=dict(l=60, r=30, t=60, b=110),
    )
    fig.update_layout(**layout)
    fig.add_annotation(
        xref="paper", yref="paper", x=0.0, y=-0.14, xanchor="left", yanchor="top",
        showarrow=False, align="left",
        font=dict(size=10, color=annotation_color(), family=FONT_FAMILY),
        text=t("Heures évaluées = heures occupées avec θrm entre {a} et {b} °C (limite basse "
               "appliquée pour θrm ≥ {c} °C). Graphique allégé au-delà de {p} points : les "
               "heures d'inconfort sont toutes affichées.",
               a=f"{en.TRM_RANGE[0]:g}", b=f"{en.TRM_RANGE[1]:g}",
               c=f"{en.TRM_RANGE_LOWER[0]:g}", p=max_points),
    )
    return finalize_fig(fig)


# ======================================================================
# 2. Barres horizontales par zone (comparaison de zones)
# ======================================================================

def couleur_palier(pct: float) -> str:
    """Couleur du palier d'inconfort : vert < 5 %, jaune 5–15 %, orange 15–25 %, rouge > 25 %."""
    for borne, couleur in PALIERS_BARRES:
        if pct < borne:
            return couleur
    return PALIERS_BARRES[-1][1]


def creer_barres_en16798(df, category: int, variante: str,
                         seuil_ref: float | None = 20.0) -> go.Figure:
    """
    % d'inconfort par zone en barres horizontales, de la zone la moins
    inconfortable (en haut) à la plus inconfortable (en bas).

    ``df`` : colonnes zone, discomfort_pct, discomfort_hours, discomfort_warm,
    discomfort_cold (les zones sans heure évaluée — % NaN — sont écartées).
    ``seuil_ref`` : ligne verticale de référence (%), None pour la masquer.
    """
    rom = ROMAIN[category]
    d = df[df["discomfort_pct"].notna()].sort_values("discomfort_pct", kind="stable")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=d["discomfort_pct"], y=d["zone"], orientation="h",
        marker_color=[couleur_palier(p) for p in d["discomfort_pct"]],
        text=[_pct_txt(p) for p in d["discomfort_pct"]], textposition="outside",
        cliponaxis=False,
        customdata=np.column_stack([d["discomfort_hours"], d["discomfort_warm"],
                                    d["discomfort_cold"]]) if len(d) else None,
        hovertemplate=("<b>%{y}</b><br>" + t("Inconfort :") + " %{x:.1f} %"
                       + "<br>" + t("Heures d'inconfort :") + " %{customdata[0]} h"
                       + "<br>" + t("dont chaud :") + " %{customdata[1]} h"
                       + "<br>" + t("dont froid :") + " %{customdata[2]} h<extra></extra>"),
        showlegend=False,
    ))
    x_max = max([seuil_ref or 0.0] + list(d["discomfort_pct"])) if len(d) else 100.0
    if seuil_ref is not None:
        fig.add_vline(x=seuil_ref, line=dict(color=annotation_color(), width=1.5, dash="dash"))
        fig.add_annotation(
            x=seuil_ref, y=1.0, yref="paper", yanchor="bottom", xanchor="left",
            text=t(" Seuil de référence {s} %", s=f"{seuil_ref:g}"), showarrow=False,
            font=dict(size=10, color=annotation_color(), family=FONT_FAMILY),
        )
    layout = get_layout()
    layout.update(
        title=t("EN 16798-1 — inconfort adaptatif Cat. {c} (%) — {variante}", c=rom, variante=variante),
        xaxis=dict(title=t("Heures occupées hors bande Cat. {c} (%)", c=rom),
                   range=[0, x_max * 1.15 + 1], gridcolor=grille_color(), ticksuffix=" %"),
        yaxis=dict(autorange="reversed", automargin=True),   # plus faible en haut
        height=max(320, 140 + 26 * len(d)),
        margin=dict(l=20, r=40, t=70, b=50),
        bargap=0.25,
    )
    fig.update_layout(**layout)
    return finalize_fig(fig)
