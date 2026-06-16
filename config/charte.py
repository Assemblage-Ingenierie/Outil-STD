ROUGE = "#E30513"
VIOLET = "#30323E"
GRIS = "#DFE4E8"
ROUGE_CLAIR = "#F9E1E3"
GRIS_CLAIR = "#F2F2F2"
NOIR70 = "#4D4D4D"
BLANC = "#FFFFFF"
NOIR = "#000000"

COULEURS_VARIANTES = [
    "#E30513",
    "#30323E",
    "#2196F3",
    "#FF9800",
    "#4CAF50",
    "#9C27B0",
    "#00BCD4",
    "#FF5722",
    "#795548",
    "#607D8B",
]

FONT_FAMILY = "Open Sans, sans-serif"

PLOTLY_LAYOUT = dict(
    font=dict(family=FONT_FAMILY, color=NOIR),
    paper_bgcolor=BLANC,
    plot_bgcolor=GRIS_CLAIR,
    title_font=dict(family=FONT_FAMILY, color=VIOLET, size=14),
    legend=dict(bgcolor=BLANC, bordercolor=GRIS, borderwidth=1),
    margin=dict(l=60, r=30, t=60, b=60),
)
