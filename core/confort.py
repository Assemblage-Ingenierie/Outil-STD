"""
Zones de confort thermique — deux modèles au choix :

  • GIVONI : diagramme bioclimatique classique. 4 zones selon la vitesse d'air.
    Chaque zone est délimitée par des courbes d'iso-humidité relative (et non
    des rectangles) : bornes basse/haute = courbes HR_min / HR_max, bornes
    gauche/droite = verticales de température. Paramètres issus de l'outil
    interne (T_min=20, HR_min=20%) — ajustables via la configuration projet.

  • COCO  : « Confort Optimisé pour réduire la Climatisation en Outre-mer ».
    Adaptation de Givoni au climat tropical humide (Martinique, Réunion,
    Mayotte, Guadeloupe). 2 zones (sans vent / avec apport de vent) définies
    par des polygones explicites dans le plan (température opérative, humidité
    absolue). Source : rapport COCO v2 (sept. 2023), figure 11.

Le module fournit, pour chaque modèle :
  - les polygones (T, w) des zones (pour le tracé)
  - un test d'appartenance vectorisé (pour le décompte d'heures hors confort)
"""
from __future__ import annotations
import numpy as np

from core.try_parser import humidite_absolue


# ======================================================================
# Paramètres des modèles
# ======================================================================

# --- GIVONI : zones par vitesse d'air (T_min/HR_min communs) ---
GIVONI_T_MIN = 20.0
GIVONI_HR_MIN = 20.0
GIVONI_ZONES = [
    # (vitesse m/s, T_max °C, HR_max %)
    (0.0, 27.0, 80.0),
    (0.5, 30.0, 85.0),
    (1.0, 32.0, 90.0),
    (1.5, 33.0, 95.0),
]

# --- COCO : polygones explicites (T °C, w g/kg air sec) ---
#   Sommets relevés sur la figure 11 du rapport COCO (sens horaire).
COCO_ZONES = [
    # (vitesse m/s, libellé, liste de sommets (T, w))
    (0.0, "COCO sans apport de vent", [(20, 3), (20, 12), (27, 18), (28, 5)]),
    (1.0, "COCO avec apport de vent", [(20, 3), (20, 13), (28, 21), (31, 21), (32, 6)]),
]

# Vitesses utilisées pour le décompte d'heures hors confort
VITESSES_DECOMPTE = [0.0, 1.0]

# Couleurs des contours de zones (du plus restreint au plus large)
COULEURS_ZONES = ["#2ECC71", "#27AE60", "#16A085", "#0E6655"]


# ======================================================================
# Construction des polygones
# ======================================================================

def _givoni_params(config: dict):
    """Récupère les paramètres Givoni en tenant compte des surcharges projet."""
    gc = config.get("givoni", {})
    t_min = float(gc.get("t_confort_min", GIVONI_T_MIN))
    hr_min = float(gc.get("hr_confort_min", GIVONI_HR_MIN))
    return t_min, hr_min


def _polygone_givoni(t_min, t_max, hr_min, hr_max, n=40):
    """
    Polygone d'une zone Givoni suivant les courbes d'iso-HR.
      - bord bas  : courbe HR_min, de t_min à t_max
      - bord droit: verticale à t_max
      - bord haut : courbe HR_max, de t_max à t_min
      - bord gauche: verticale à t_min (fermeture)
    """
    T_bas = np.linspace(t_min, t_max, n)
    w_bas = humidite_absolue(T_bas, hr_min)
    T_haut = np.linspace(t_max, t_min, n)
    w_haut = humidite_absolue(T_haut, hr_max)
    T = np.concatenate([T_bas, T_haut, [t_min]])
    W = np.concatenate([w_bas, w_haut, [w_bas[0]]])
    return T, W


def zones_modele(config: dict, methode: str):
    """
    Retourne la liste des zones du modèle choisi :
      [(vitesse, libellé, T_array, w_array), ...]
    triées de la plus restreinte à la plus large.
    """
    methode = (methode or "givoni").lower()
    out = []
    if methode == "coco":
        for v, label, sommets in COCO_ZONES:
            T = np.array([p[0] for p in sommets] + [sommets[0][0]], dtype=float)
            W = np.array([p[1] for p in sommets] + [sommets[0][1]], dtype=float)
            out.append((v, label, T, W))
    else:  # givoni
        t_min, hr_min = _givoni_params(config)
        for v, t_max, hr_max in GIVONI_ZONES:
            T, W = _polygone_givoni(t_min, t_max, hr_min, hr_max)
            label = label_zone(v)
            out.append((v, label, T, W))
    return out


def polygone_zone(config: dict, methode: str, vitesse: float):
    """Polygone (T, w) de la zone correspondant à la vitesse donnée."""
    for v, _label, T, W in zones_modele(config, methode):
        if abs(v - vitesse) < 1e-6:
            return T, W
    return np.array([]), np.array([])


# ======================================================================
# Test d'appartenance (point dans polygone)
# ======================================================================

def _points_dans_polygone(T_pts, w_pts, T_poly, w_poly):
    """Test vectorisé point-dans-polygone (matplotlib.path)."""
    from matplotlib.path import Path
    poly = Path(np.column_stack([T_poly, w_poly]))
    pts = np.column_stack([np.asarray(T_pts, float), np.asarray(w_pts, float)])
    return poly.contains_points(pts)


def dans_zone(T, w, config: dict, methode: str, vitesse: float):
    """Le(s) point(s) (T, w) est/sont dans la zone de confort (modèle, vitesse) ?"""
    T_poly, w_poly = polygone_zone(config, methode, vitesse)
    if T_poly.size == 0:
        return np.zeros(np.asarray(T).shape, dtype=bool)
    return _points_dans_polygone(T, w, T_poly, w_poly)


def label_zone(v: float) -> str:
    """Libellé court d'une zone Givoni."""
    if v == 0:
        return "Confort 0 m/s (repos)"
    return f"Confort {v:.1f} m/s"


def vitesses_modele(methode: str) -> list[float]:
    """Liste des vitesses disponibles pour le modèle."""
    if (methode or "givoni").lower() == "coco":
        return [v for v, _, _ in COCO_ZONES]
    return [v for v, _, _ in GIVONI_ZONES]
