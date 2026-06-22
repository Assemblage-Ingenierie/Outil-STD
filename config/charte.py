ROUGE = "#E30513"
VIOLET = "#30323E"
GRIS = "#DFE4E8"
ROUGE_CLAIR = "#F9E1E3"
GRIS_CLAIR = "#F2F2F2"
NOIR70 = "#4D4D4D"
BLANC = "#FFFFFF"
NOIR = "#000000"

# Couleurs dédiées aux graphiques (contraste suffisant sur fond blanc)
GRILLE = "#C2C8CE"        # lignes de grille — visibles sans dominer
COURBE_REF = "#7A828B"    # courbes de référence (iso-HR) — gris moyen lisible
LIGNE_EXT = "#37474F"     # courbe T extérieure — gris-bleu foncé, contraste fort

# Palette des variantes : couleurs vives et bien distinctes en tête
# (rouge charte, bleu, violet, orange, vert…) pour un bon contraste visuel
# même à 2-3 variantes. Les teintes ternes (brun, bleu-gris) sont en fin.
COULEURS_VARIANTES = [
    "#E30513",  # rouge (charte)
    "#2196F3",  # bleu
    "#9C27B0",  # violet
    "#FF9800",  # orange
    "#2ECC71",  # vert
    "#00BCD4",  # cyan
    "#FF5722",  # orange foncé
    "#3F51B5",  # indigo
    "#8D6E63",  # brun
    "#607D8B",  # bleu-gris
]

FONT_FAMILY = "Open Sans, sans-serif"

# Couleurs dédiées au mode sombre (graphiques Plotly)
BG_DARK        = "#0F1117"   # fond papier (identique au fond Streamlit dark)
PLOT_BG_DARK   = "#1A1C24"   # fond zone de tracé
TEXTE_DARK     = "#E8ECF0"   # texte principal
ANNOTATION_DARK = "#9AAAB8"  # annotations légères (labels iso-HR…)
GRILLE_DARK    = "#2D3748"   # lignes de grille
COURBE_REF_DARK = "#7A8FA0"  # courbes iso-HR
LIGNE_EXT_DARK  = "#90CAF9"  # courbe T extérieure (bleu clair)

PLOTLY_LAYOUT = dict(
    font=dict(family=FONT_FAMILY, color=NOIR),
    paper_bgcolor=BLANC,
    plot_bgcolor=BLANC,
    title_font=dict(family=FONT_FAMILY, color=VIOLET, size=14),
    legend=dict(bgcolor=BLANC, bordercolor=GRIS, borderwidth=1),
    margin=dict(l=60, r=30, t=60, b=60),
)

PLOTLY_LAYOUT_DARK = dict(
    font=dict(family=FONT_FAMILY, color=TEXTE_DARK),
    paper_bgcolor=BG_DARK,
    plot_bgcolor=PLOT_BG_DARK,
    title_font=dict(family=FONT_FAMILY, color=TEXTE_DARK, size=14),
    legend=dict(bgcolor=PLOT_BG_DARK, bordercolor=GRILLE_DARK, borderwidth=1,
                font=dict(color=TEXTE_DARK)),
    margin=dict(l=60, r=30, t=60, b=60),
)

# ---- Singleton mode sombre (initialisé à chaque re-run Streamlit) ----
_dark_mode: bool = False


def set_dark_mode(dark: bool) -> None:
    global _dark_mode
    _dark_mode = dark


def is_dark() -> bool:
    return _dark_mode


def get_layout() -> dict:
    """Retourne le dict PLOTLY_LAYOUT adapté au mode courant (clair/sombre)."""
    return dict(PLOTLY_LAYOUT_DARK if _dark_mode else PLOTLY_LAYOUT)


def annotation_color() -> str:
    return ANNOTATION_DARK if _dark_mode else NOIR70


def grille_color() -> str:
    return GRILLE_DARK if _dark_mode else GRILLE


def courbe_ref_color() -> str:
    return COURBE_REF_DARK if _dark_mode else COURBE_REF


def ligne_ext_color() -> str:
    return LIGNE_EXT_DARK if _dark_mode else LIGNE_EXT


def violet_color() -> str:
    """VIOLET charte en clair, gris-bleu clair en sombre (diagonales, courbes neutres)."""
    return "#9BAABF" if _dark_mode else VIOLET


def title_color() -> str:
    return TEXTE_DARK if _dark_mode else VIOLET


def finalize_fig(fig):
    """
    Applique le thème courant au titre et à la légende d'une figure Plotly.
    À appeler juste avant de retourner la figure depuis une fonction de graphe.

    Utilise fig.update_layout() (magic-underscore garanti) pour forcer les
    couleurs de titre et de légende, indépendamment de la façon dont les
    fonctions de graphe ont construit leur layout dict.
    """
    if _dark_mode:
        fig.update_layout(
            title_font_color=TEXTE_DARK,
            legend_font_color=TEXTE_DARK,
            legend_bgcolor=PLOT_BG_DARK,
            legend_bordercolor=GRILLE_DARK,
        )
    else:
        fig.update_layout(
            title_font_color=VIOLET,
        )
    return fig
