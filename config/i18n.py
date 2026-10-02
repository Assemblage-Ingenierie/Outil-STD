"""
Langue des GRAPHIQUES (titres, axes, légendes, survols, annotations).

L'interface et les tableaux restent en français ; seuls les textes portés par
les figures Plotly basculent, pour intégrer les graphiques à un rendu
anglophone (écran ET rapport Word, qui réutilise les mêmes fonctions).

Usage : ``t("Température intérieure — {zone}", zone=zone)``. La clé est le texte
français lui-même (lisible dans le code) ; en anglais on cherche sa traduction
dans ``EN``, avec repli sur le français si elle manque (jamais d'erreur).
Le réglage est global au processus, comme le mode sombre (cf. config.charte).
"""
from __future__ import annotations

LANGUES = {"fr": "Français", "en": "English"}
_langue: str = "fr"


def set_langue(code: str) -> None:
    global _langue
    _langue = code if code in LANGUES else "fr"


def langue() -> str:
    return _langue


def est_anglais() -> bool:
    return _langue == "en"


def t(texte: str, **kwargs) -> str:
    """Traduit ``texte`` (gabarit français) puis le formate avec ``kwargs``."""
    gabarit = EN.get(texte, texte) if _langue == "en" else texte
    return gabarit.format(**kwargs) if kwargs else gabarit


def nombre(x: float, fmt: str = ".1f") -> str:
    """Nombre formaté avec le séparateur décimal de la langue des graphiques."""
    s = format(x, fmt)
    return s if _langue == "en" else s.replace(".", ",")


def noms_mois() -> list[str]:
    return [t(m) for m in MOIS_FR]


MOIS_FR = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']


# ======================================================================
# Dictionnaire français → anglais
# ======================================================================
EN: dict[str, str] = {
    # --- Mois (abréviations) ---
    'Fév': 'Feb', 'Avr': 'Apr', 'Mai': 'May', 'Aoû': 'Aug', 'Déc': 'Dec',

    # --- Commun ---
    'Date': 'Date',
    'Mois': 'Month',
    'Heure': 'Hour',
    'Zone': 'Zone',
    'Variante': 'Variant',
    'météo': 'weather',
    'Température (°C)': 'Temperature (°C)',
    'T extérieure': 'Outdoor T',
    'T extérieure (°C)': 'Outdoor temperature (°C)',
    'T ext — {nom}': 'Outdoor T — {nom}',
    'Seuil T1 ({s}°C)': 'Threshold T1 ({s}°C)',
    'Seuil T2 ({s}°C)': 'Threshold T2 ({s}°C)',
    'Chauffage': 'Heating',
    'Besoins annuels par zone (kWh/m²)': 'Annual energy needs by zone (kWh/m²)',
    'Climatisation': 'Cooling',
    'Refroidissement': 'Cooling',
    'Hors saison de chauffe': 'Outside heating season',
    'Saison de refroidissement': 'Cooling season',
    'Saison de chauffe': 'Heating season',
    'Hors période': 'Outside period',
    'Points horaires': 'Hourly values',
    'Conditions intérieures': 'Indoor conditions',

    # --- charts/temperature.py ---
    'Température intérieure — {zone}': 'Indoor temperature — {zone}',
    'T° opérative vs T° extérieure — {zone}': 'Operative vs outdoor temperature — {zone}',
    'T opérative intérieure (°C)': 'Indoor operative temperature (°C)',
    'Comparaison des fichiers météo — T° extérieure moyenne mensuelle':
        'Weather file comparison — monthly mean outdoor temperature',
    'Heures de dépassement (seuils {s1}°C / {s2}°C)':
        'Overheating hours (thresholds {s1}°C / {s2}°C)',
    'Heures / an': 'Hours / year',
    'Températures min / moyenne / max par zone': 'Min / mean / max temperatures by zone',
    'T min': 'T min', 'T moy': 'T mean', 'T max': 'T max',
    'solaires': 'solar', 'internes': 'internal',
    'Apports {libelle} mensuels — {zone}': 'Monthly {libelle} gains — {zone}',
    'Apports {libelle} (kWh)': '{libelle} gains (kWh)',
    'Apports {libelle} mensuels par zone — {variante}':
        'Monthly {libelle} gains by zone — {variante}',
    'Température horaire — {zone} · {variante} (jour × heure)':
        'Hourly temperature — {zone} · {variante} (day × hour)',

    # --- charts/humidite.py ---
    'Confort {a}–{b} %': 'Comfort {a}–{b} %',
    'Min–max journalier': 'Daily min–max',
    'HR moy': 'RH mean', 'HR min': 'RH min', 'HR max': 'RH max',
    'HR ext — {nom}': 'Outdoor RH — {nom}',
    'HR extérieure': 'Outdoor RH',
    ' (moyenne journalière)': ' (daily mean)',
    ' (horaire)': ' (hourly)',
    '1 mois': '1 month', '3 mois': '3 months', 'Année': 'Year',
    'Humidité relative — {zone}{suffixe}': 'Relative humidity — {zone}{suffixe}',
    'HR': 'RH',
    'HR (%)': 'RH (%)',
    'HR %': 'RH %',
    'HR horaire — {zone} · {variante} (jour × heure)':
        'Hourly RH — {zone} · {variante} (day × hour)',
    'Humidité relative min / moyenne / max par zone': 'Min / mean / max relative humidity by zone',

    # --- charts/synthese.py ---
    'Besoins par variante (kWh/m²)': 'Energy needs by variant (kWh/m²)',
    'Températures par variante (°C)': 'Temperatures by variant (°C)',
    'Heures de dépassement par variante': 'Overheating hours by variant',
    'heures (moy. par zone)': 'hours (mean per zone)',
    'Humidité relative par variante (%)': 'Relative humidity by variant (%)',
    "Part d'inconfort par variante (%)": 'Share of discomfort by variant (%)',
    "% des heures d'occupation": '% of occupied hours',
    'Jour · 0 m/s': 'Day · 0 m/s', 'Nuit · 0 m/s': 'Night · 0 m/s',
    'Jour · 1 m/s': 'Day · 1 m/s', 'Nuit · 1 m/s': 'Night · 1 m/s',
    'Inconfort jour / nuit par variante (%)': 'Day / night discomfort by variant (%)',
    '% hors': '% outside',

    # --- charts/givoni.py ---
    'Saturation (HR 100 %)': 'Saturation (RH 100 %)',
    'HR {rh} %': 'RH {rh} %',
    'Diagramme de {nom} — Conditions intérieures': '{nom} chart — Indoor conditions',
    'Diagramme de {nom} — {zone} (toutes variantes)': '{nom} chart — {zone} (all variants)',
    'Diagramme de {nom} — {zone} · {variante}': '{nom} chart — {zone} · {variante}',
    'Diagramme de {nom} — {zone} · {variante} (par période)':
        '{nom} chart — {zone} · {variante} (by period)',
    '{zone} · {variante} — par période': '{zone} · {variante} — by period',
    'Température opérative (°C)': 'Operative temperature (°C)',
    'Humidité absolue (g/kg air sec)': 'Absolute humidity (g/kg dry air)',
    'Confort 0 m/s (repos)': 'Comfort 0 m/s (still air)',
    'Confort {v} m/s': 'Comfort {v} m/s',
    'COCO sans apport de vent': 'COCO without air movement',
    'COCO avec apport de vent': 'COCO with air movement',
    ("Hypothèse : les heures où le local est chauffé alors que T est sous la borne basse "
     "de confort ({t} °C) sont exclues du diagramme et du décompte d'inconfort (chauffer "
     "sous le minimum de confort = choix de consigne, pas inconfort)."):
        ("Assumption: hours when the room is heated while T is below the lower comfort "
         "limit ({t} °C) are excluded from the chart and from the discomfort count "
         "(heating below the comfort minimum is a set-point choice, not discomfort)."),

    # --- charts/adaptatif.py (EN 16798-1) ---
    'Non évaluée (inoccupée ou θrm hors domaine)': 'Not assessed (unoccupied or θrm out of range)',
    'Non évaluées ({n} h)': 'Not assessed ({n} h)',
    'Confortable': 'Comfortable',
    'Confortable ({n} h)': 'Comfortable ({n} h)',
    'Trop chaud': 'Too warm',
    'Trop chaud ({n} h)': 'Too warm ({n} h)',
    'Trop froid': 'Too cold',
    'Trop froid ({n} h)': 'Too cold ({n} h)',
    'Bande Cat. {c}': 'Category {c} band',
    'Limite haute Cat. {c} (θc + {k} K)': 'Category {c} upper limit (θc + {k} K)',
    'Limite basse Cat. {c} (θc − {k} K)': 'Category {c} lower limit (θc − {k} K)',
    'θrm — moyenne glissante de T extérieure (°C)': 'θrm — running mean outdoor temperature (°C)',
    'Température intérieure (°C)': 'Indoor temperature (°C)',
    'heure {i}': 'hour {i}',
    ("Heures évaluées = heures occupées avec θrm entre {a} et {b} °C (limite basse appliquée "
     "pour θrm ≥ {c} °C). Graphique allégé au-delà de {p} points : les heures d'inconfort "
     "sont toutes affichées."):
        ("Assessed hours = occupied hours with θrm between {a} and {b} °C (lower limit applied "
         "for θrm ≥ {c} °C). Chart thinned out beyond {p} points: all discomfort hours "
         "are shown."),
    'Inconfort :': 'Discomfort:',
    "Heures d'inconfort :": 'Discomfort hours:',
    'dont chaud :': 'of which too warm:',
    'dont froid :': 'of which too cold:',
    ' Seuil de référence {s} %': ' Reference threshold {s} %',
    'EN 16798-1 — inconfort adaptatif Cat. {c} (%) — {variante}':
        'EN 16798-1 adaptive comfort — Category {c} discomfort (%) — {variante}',
    'Heures occupées hors bande Cat. {c} (%)': 'Occupied hours outside Category {c} band (%)',
    "{zone} — {variante} — EN 16798-1 Cat. {c} : {pct} d'inconfort":
        '{zone} — {variante} — EN 16798-1 Cat. {c}: {pct} discomfort',
    '{zone} — variantes superposées — EN 16798-1 Cat. {c}':
        '{zone} — overlaid variants — EN 16798-1 Cat. {c}',
}
