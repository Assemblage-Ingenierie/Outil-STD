"""
Confort adaptatif — NF EN 16798-1:2019 (bâtiments sans refroidissement mécanique).

Module AUTONOME (numpy + pandas uniquement, aucune dépendance Streamlit ni au
reste de l'application) : il peut être importé et testé isolément.

Chaîne de calcul
----------------
1. Température extérieure moyenne glissante θrm (« running mean »)
   — EN 16798-1, Annexe B (§ B.2.2, formule B.1) :

       θrm(j) = (1 − α) · θed(j−1) + α · θrm(j−1)       α = 0,8

   θed(j−1) = moyenne des 24 valeurs horaires de T extérieure du jour précédent.
   Série JOURNALIÈRE, répliquée sur les 24 h de chaque jour.

2. Température de confort optimale — EN 16798-1, Annexe B (formule B.2) :

       θc = 0,33 · θrm + 18,8

3. Limites haute / basse par catégorie — EN 16798-1, Annexe B, Tableau B.2 :

       Catégorie   θi,max        θi,min
       I           θc + 2 K      θc − 3 K
       II          θc + 3 K      θc − 4 K     (catégorie par défaut)
       III         θc + 4 K      θc − 5 K

   Domaine d'application (§ B.2.2) : limites hautes pour 10 °C < θrm < 30 °C,
   limites basses pour 15 °C < θrm < 30 °C. Hors domaine, les heures ne sont
   pas évaluées (flaggées via ``trm_in_range`` / ``lower_applicable``).

   Les bandes et domaines sont paramétrables (``bandes``, ``trm_range``,
   ``trm_range_lower``) : une variante symétrique ±2/±3/±4 K sur 10–33 °C
   s'obtient avec ``bandes=BANDES_SYMETRIQUES, trm_range=(10, 33),
   trm_range_lower=None``.

Note : Pléiades exporte sa propre θrm (colonne « Theta rm ») ; la formule
ci-dessus la reproduit à < 0,01 K une fois la période d'initialisation passée.
"""
from __future__ import annotations

import warnings
from typing import Iterable

import numpy as np
import pandas as pd


# ======================================================================
# Constantes EN 16798-1
# ======================================================================

ALPHA = 0.8                 # Annexe B, formule B.1 — constante de pondération
PENTE_CONFORT = 0.33        # Annexe B, formule B.2
ORDONNEE_CONFORT = 18.8     # Annexe B, formule B.2 (°C)

# Annexe B, Tableau B.2 — écarts (K) sous / au-dessus de θc : {cat: (bas, haut)}
BANDES_EN16798 = {1: (3.0, 2.0), 2: (4.0, 3.0), 3: (5.0, 4.0)}
# Variante symétrique (bande ±2/±3/±4 K), conservée pour comparaison.
BANDES_SYMETRIQUES = {1: (2.0, 2.0), 2: (3.0, 3.0), 3: (4.0, 4.0)}

# Annexe B, § B.2.2 — domaines de validité du modèle (°C)
TRM_RANGE = (10.0, 30.0)        # limites hautes (et validité générale)
TRM_RANGE_LOWER = (15.0, 30.0)  # limites basses

CATEGORIES = (1, 2, 3)
CATEGORIE_DEFAUT = 2
NB_JOURS_INIT = 7               # initialisation de θrm (moyenne des 7 premiers jours)


# ======================================================================
# 1. Running mean θrm — Annexe B, formule B.1
# ======================================================================

def moyennes_journalieres(t_ext) -> np.ndarray:
    """θed : moyenne journalière de T extérieure (blocs de 24 h consécutives).
    Un dernier jour incomplet est moyenné sur ses heures disponibles ; les NaN
    sont ignorés."""
    v = np.asarray(t_ext, dtype=float).ravel()
    n_jours = int(np.ceil(len(v) / 24))
    pad = np.full(n_jours * 24, np.nan)
    pad[:len(v)] = v
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # jour entièrement NaN
        return np.nanmean(pad.reshape(n_jours, 24), axis=1)


def running_mean_journaliere(t_ext, alpha: float = ALPHA,
                             init: str = "moyenne_7j") -> np.ndarray:
    """
    θrm journalière — EN 16798-1, Annexe B, formule B.1 :
        θrm(j) = (1 − α)·θed(j−1) + α·θrm(j−1)

    init :
      - ``"moyenne_7j"`` (défaut) : θrm des 7 premiers jours = moyenne
        arithmétique des θed de ces 7 jours, puis récurrence à partir du jour 8.
      - ``"cyclique"`` : année supposée périodique (le 1er janvier succède au
        31 décembre) ; la récurrence est préchauffée sur la fin d'année. Plus
        proche de la θrm exportée par Pléiades sur les premiers jours.
    """
    ted = moyennes_journalieres(t_ext)
    n = len(ted)
    trm = np.empty(n)
    if n == 0:
        return trm
    if init == "cyclique":
        # Point fixe de la récurrence sur une année périodique : on itère la
        # récurrence sur l'année depuis la moyenne annuelle ; α^365 ≈ 0 → une
        # seule passe de préchauffage suffit.
        prec = float(np.nanmean(ted))
        for j in range(n):
            prec = (1 - alpha) * ted[j - 1] + alpha * prec   # j=0 → ted[-1]
        for j in range(n):
            prec = (1 - alpha) * ted[j - 1] + alpha * prec
            trm[j] = prec
        return trm
    if init != "moyenne_7j":
        raise ValueError(f"init inconnu : {init!r} (attendu 'moyenne_7j' ou 'cyclique')")
    k = min(NB_JOURS_INIT, n)
    trm[:k] = np.nanmean(ted[:k])
    for j in range(k, n):
        trm[j] = (1 - alpha) * ted[j - 1] + alpha * trm[j - 1]
    return trm


def running_mean_horaire(t_ext, alpha: float = ALPHA, init: str = "moyenne_7j",
                         index=None) -> pd.Series:
    """θrm répliquée sur les 24 h de chaque jour (même longueur que ``t_ext``)."""
    n = len(t_ext)
    trm_h = np.repeat(running_mean_journaliere(t_ext, alpha, init), 24)[:n]
    if index is None:
        index = t_ext.index if isinstance(t_ext, pd.Series) else pd.RangeIndex(n)
    return pd.Series(trm_h, index=index, name="trm")


# ======================================================================
# 2-3. Température de confort et limites — formule B.2, Tableau B.2
# ======================================================================

def temperature_confort(trm):
    """θc = 0,33·θrm + 18,8 — EN 16798-1, Annexe B, formule B.2."""
    return PENTE_CONFORT * trm + ORDONNEE_CONFORT


def limites_categorie(trm, category: int = CATEGORIE_DEFAUT, bandes: dict | None = None):
    """(θi,min, θi,max) de la catégorie — EN 16798-1, Annexe B, Tableau B.2."""
    bandes = bandes or BANDES_EN16798
    if category not in bandes:
        raise ValueError(f"Catégorie EN 16798 invalide : {category!r} (attendu 1, 2 ou 3)")
    bas, haut = bandes[category]
    tc = temperature_confort(trm)
    return tc - bas, tc + haut


def _dans(trm, plage) -> np.ndarray:
    lo, hi = plage
    with np.errstate(invalid="ignore"):
        return (trm >= lo) & (trm <= hi)


# ======================================================================
# 4. Évaluation d'une zone
# ======================================================================

def compute_en16798_adaptive(
    t_int: pd.Series,
    t_ext: pd.Series,
    occupied: pd.Series,
    category: int = CATEGORIE_DEFAUT,
    alpha: float = ALPHA,
    *,
    bandes: dict | None = None,
    trm_range: tuple = TRM_RANGE,
    trm_range_lower: tuple | None = TRM_RANGE_LOWER,
    init: str = "moyenne_7j",
    trm_hourly: pd.Series | None = None,
) -> dict:
    """
    Confort adaptatif EN 16798-1 d'une zone.

    Args:
        t_int     : température intérieure horaire (°C) — opérative si disponible.
        t_ext     : température extérieure horaire (°C), même pas de temps.
        occupied  : booléen horaire « zone occupée ».
        category  : 1, 2 ou 3 (Tableau B.2).
        alpha     : pondération de la running mean (formule B.1).
        bandes    : {cat: (écart_bas, écart_haut)} en K (défaut Tableau B.2).
        trm_range : domaine de θrm où le modèle est évalué (défaut 10–30 °C).
        trm_range_lower : domaine où la limite BASSE s'applique (défaut 15–30 °C) ;
                    None = même domaine que ``trm_range``.
        init      : initialisation de θrm (cf. ``running_mean_journaliere``).
        trm_hourly : θrm horaire pré-calculée (évite de la recalculer pour chaque
                    zone d'un même bâtiment) ; ``t_ext`` est alors ignorée.

    Les séries sont alignées par POSITION (heure n de l'année) et tronquées à la
    longueur commune — les résultats Pléiades (8736 h) sont plus courts que la
    météo .try (8760 h). θrm est calculée sur toute la série extérieure.

    Heures évaluées = occupées ET θrm dans ``trm_range``. Parmi elles :
      - chaud  : T_int > θi,max
      - froid  : T_int < θi,min, uniquement si θrm dans ``trm_range_lower``
      - confortable sinon.

    Retourne un dict :
        trm_hourly, t_comfort, t_upper, t_lower      (pd.Series float)
        comfortable, warm, cold                      (pd.Series bool, heures évaluées)
        occupied, trm_in_range, lower_applicable     (pd.Series bool)
        discomfort_hours, discomfort_hours_warm, discomfort_hours_cold (int)
        discomfort_pct    (float, % des heures évaluées ; NaN si aucune)
        total_occupied, total_occupied_valid, occupied_out_of_range (int)
        category (int)
    """
    if trm_hourly is None:
        trm_full = running_mean_horaire(t_ext, alpha, init).to_numpy()
    else:
        trm_full = np.asarray(trm_hourly, dtype=float)

    ti_raw = np.asarray(t_int, dtype=float).ravel()
    occ_raw = np.asarray(occupied).ravel()
    n = min(len(ti_raw), len(occ_raw), len(trm_full))
    ti = ti_raw[:n]
    occ = occ_raw[:n].astype(bool) & ~np.isnan(ti)
    trm = trm_full[:n]
    index = t_int.index[:n] if isinstance(t_int, pd.Series) else pd.RangeIndex(n)

    tc = temperature_confort(trm)
    t_lower, t_upper = limites_categorie(trm, category, bandes)

    in_range = _dans(trm, trm_range)
    lower_ok = in_range & _dans(trm, trm_range_lower or trm_range)

    evalue = occ & in_range
    warm = evalue & (ti > t_upper)
    cold = evalue & lower_ok & (ti < t_lower)
    comfortable = evalue & ~warm & ~cold

    n_valid = int(evalue.sum())
    n_warm = int(warm.sum())
    n_cold = int(cold.sum())
    n_disc = n_warm + n_cold

    def _s(a, name):
        return pd.Series(a, index=index, name=name)

    return {
        "category": int(category),
        "trm_hourly": _s(trm, "trm"),
        "t_comfort": _s(tc, "t_comfort"),
        "t_upper": _s(t_upper, "t_upper"),
        "t_lower": _s(t_lower, "t_lower"),
        "comfortable": _s(comfortable, "comfortable"),
        "warm": _s(warm, "warm"),
        "cold": _s(cold, "cold"),
        "occupied": _s(occ, "occupied"),
        "trm_in_range": _s(in_range, "trm_in_range"),
        "lower_applicable": _s(lower_ok, "lower_applicable"),
        "discomfort_hours": n_disc,
        "discomfort_pct": (100.0 * n_disc / n_valid) if n_valid else float("nan"),
        "discomfort_hours_warm": n_warm,
        "discomfort_hours_cold": n_cold,
        "total_occupied": int(occ.sum()),
        "total_occupied_valid": n_valid,
        "occupied_out_of_range": int((occ & ~in_range).sum()),
    }


def compute_toutes_categories(t_int, t_ext, occupied, alpha: float = ALPHA,
                              **kwargs) -> dict[int, dict]:
    """Évaluation pour les catégories I, II et III ({1: res, 2: res, 3: res}).
    θrm n'est calculée qu'une fois."""
    trm = kwargs.pop("trm_hourly", None)
    if trm is None:
        trm = running_mean_horaire(t_ext, alpha, kwargs.get("init", "moyenne_7j"))
    return {c: compute_en16798_adaptive(t_int, t_ext, occupied, c, alpha,
                                        trm_hourly=trm, **kwargs)
            for c in CATEGORIES}


def indicateurs_plats(res_par_cat: dict[int, dict]) -> dict:
    """Aplatit les résultats multi-catégories en indicateurs nommés
    (discomfort_hours_catII, discomfort_pct_catII, …)."""
    romain = {1: "I", 2: "II", 3: "III"}
    out = {}
    for c, r in res_par_cat.items():
        s = romain.get(c, str(c))
        out[f"discomfort_hours_cat{s}"] = r["discomfort_hours"]
        out[f"discomfort_pct_cat{s}"] = r["discomfort_pct"]
        out[f"discomfort_hours_warm_cat{s}"] = r["discomfort_hours_warm"]
        out[f"discomfort_hours_cold_cat{s}"] = r["discomfort_hours_cold"]
    return out


# ======================================================================
# 5. Tableau récapitulatif multi-zones
# ======================================================================

def tableau_multizones(zones: Iterable[dict], t_ext=None,
                       category: int = CATEGORIE_DEFAUT, **kwargs) -> pd.DataFrame:
    """
    Une ligne par zone. Chaque élément de ``zones`` est un dict :
        {'zone': str, 't_int': série, 'occupied': série,
         'surface': float (optionnel), 't_ext': série (optionnel, sinon ``t_ext``)}

    θrm est calculée une seule fois pour la météo commune.
    Colonnes : Zone | Surface (m²) | Heures occupées | Heures évaluées |
               Inconfort Cat.X (h) | Inconfort Cat.X (%) | dont chaud (h) | dont froid (h)
    """
    romain = {1: "I", 2: "II", 3: "III"}[category]
    alpha = kwargs.pop("alpha", ALPHA)
    trm_commun = None
    if t_ext is not None and kwargs.get("trm_hourly") is None:
        trm_commun = running_mean_horaire(t_ext, alpha, kwargs.get("init", "moyenne_7j"))
    rows = []
    for z in zones:
        te = z.get("t_ext")
        kw = dict(kwargs)
        if te is None and trm_commun is not None:
            kw["trm_hourly"] = trm_commun
        r = compute_en16798_adaptive(z["t_int"], te if te is not None else t_ext,
                                     z["occupied"], category, alpha, **kw)
        rows.append({
            "Zone": z["zone"],
            "Surface (m²)": z.get("surface", np.nan),
            "Heures occupées": r["total_occupied"],
            "Heures évaluées": r["total_occupied_valid"],
            f"Inconfort Cat.{romain} (h)": r["discomfort_hours"],
            f"Inconfort Cat.{romain} (%)": r["discomfort_pct"],
            "dont chaud (h)": r["discomfort_hours_warm"],
            "dont froid (h)": r["discomfort_hours_cold"],
        })
    return pd.DataFrame(rows)
