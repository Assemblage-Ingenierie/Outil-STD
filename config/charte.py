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

PLOTLY_LAYOUT = dict(
    font=dict(family=FONT_FAMILY, color=NOIR),
    paper_bgcolor=BLANC,
    plot_bgcolor=BLANC,
    title_font=dict(family=FONT_FAMILY, color=VIOLET, size=14),
    legend=dict(bgcolor=BLANC, bordercolor=GRIS, borderwidth=1),
    margin=dict(l=60, r=30, t=60, b=60),
)
