"""
Zones de confort de Givoni étendues par la vitesse d'air (modèle de Szokolay).

Logique partagée entre :
  - le tracé du diagramme de Givoni (charts/givoni.py)
  - le décompte des heures hors confort (core/variante.py)

Modèle de Szokolay : le mouvement d'air relève la limite haute de température
admissible de la zone de confort de :
    ΔT = 6·v − 1.6·v²      (v : vitesse d'air en m/s)

Vitesses retenues : 0 / 0.5 / 1.0 / 1.5 m/s → 4 zones de confort emboîtées.
La limite basse de température et les bornes d'humidité absolue ne bougent pas.
"""
from __future__ import annotations
import numpy as np


# Vitesses d'air des 4 zones de confort (m/s)
VITESSES_AIR = [0.0, 0.5, 1.0, 1.5]

# Couleurs des contours de zones (du plus restreint au plus large)
COULEURS_ZONES = ["#2ECC71", "#27AE60", "#16A085", "#0E6655"]


def delta_t_szokolay(v: float) -> float:
    """Élévation de température admissible (K) pour une vitesse d'air v (m/s)."""
    return 6.0 * v - 1.6 * v * v


def bornes_zone(config: dict, v: float) -> dict:
    """
    Retourne les bornes de la zone de confort pour la vitesse d'air v.
    Clés : t_min, t_max, w_min, w_max.
    """
    gc = config.get("givoni", {})
    t_min = float(gc.get("t_confort_min", 18.0))
    t_max = float(gc.get("t_confort_max", 27.0))
    w_min = float(gc.get("w_confort_min", 4.0))
    w_max = float(gc.get("w_confort_max", 12.0))
    return {
        "t_min": t_min,
        "t_max": t_max + delta_t_szokolay(v),
        "w_min": w_min,
        "w_max": w_max,
    }


def polygone_zone(config: dict, v: float) -> tuple[list[float], list[float]]:
    """Polygone fermé (T, w) de la zone de confort pour la vitesse v."""
    b = bornes_zone(config, v)
    T = [b["t_min"], b["t_max"], b["t_max"], b["t_min"], b["t_min"]]
    W = [b["w_min"], b["w_min"], b["w_max"], b["w_max"], b["w_min"]]
    return T, W


def dans_zone(T, w, config: dict, v: float):
    """
    Test vectorisé : le(s) point(s) (T, w) est/sont dans la zone de confort v ?
    Accepte des scalaires ou des np.ndarray. Retourne bool / np.ndarray[bool].
    """
    b = bornes_zone(config, v)
    T = np.asarray(T, dtype=float)
    w = np.asarray(w, dtype=float)
    return (
        (T >= b["t_min"]) & (T <= b["t_max"]) &
        (w >= b["w_min"]) & (w <= b["w_max"])
    )


def label_zone(v: float) -> str:
    """Libellé court d'une zone, ex. 'Confort 1.0 m/s'."""
    if v == 0:
        return "Confort 0 m/s (repos)"
    return f"Confort {v:.1f} m/s"
