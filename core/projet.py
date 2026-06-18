"""
Enregistrement / chargement d'un projet STD (fichier autoportant .stdproj).

Un projet embarque les données déjà parsées de chaque variante (df horaire,
synthèse, météo) + les paramètres et la description des variantes. Il sert de
mémoire des simulations : réouverture sans les fichiers .slk/.try d'origine.

Format : pickle compressé gzip. Pour la robustesse, on ne sérialise PAS les
objets Variante mais des structures simples (dicts + DataFrames), reconstruites
à l'ouverture.
"""
from __future__ import annotations
import gzip
import pickle
from pathlib import Path

import pandas as pd

from core.variante import Variante

FORMAT_VERSION = 1
EXTENSION = ".stdproj"


def sauvegarder_projet(chemin: str | Path, etat: dict) -> Path:
    """
    Enregistre un projet.

    etat attendu :
      - nom_projet (str)
      - params (dict) : seuil_t1, seuil_t2, methode, config…
      - variantes (list[Variante])
      - descriptions (pd.DataFrame | None) : tableau comparatif des variantes
      - selections (dict | None) : clés de sélection persistantes
    """
    chemin = Path(chemin)
    if chemin.suffix != EXTENSION:
        chemin = chemin.with_suffix(EXTENSION)

    variantes_ser = []
    for v in etat.get("variantes", []):
        variantes_ser.append({
            "nom": v.nom,
            "zones": list(v.zones),
            "meteo_nom": getattr(v, "meteo_nom", ""),
            "df_horaire": v.df_horaire,
            "df_synthese": v.df_synthese,
            "df_meteo": v.df_meteo,
        })

    bundle = {
        "format_version": FORMAT_VERSION,
        "nom_projet": etat.get("nom_projet", ""),
        "params": etat.get("params", {}),
        "variantes": variantes_ser,
        "ameliorations": etat.get("ameliorations"),
        "recap_vals": etat.get("recap_vals"),
        "descriptions": etat.get("descriptions"),  # rétro-compat anciens projets
        "selections": etat.get("selections", {}),
    }

    with gzip.open(chemin, "wb") as f:
        pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)

    return chemin


def charger_projet(chemin: str | Path) -> dict:
    """
    Charge un projet et reconstruit les objets Variante.
    Retourne un dict : nom_projet, params, variantes (list[Variante]),
    descriptions, selections.
    """
    chemin = Path(chemin)
    with gzip.open(chemin, "rb") as f:
        bundle = pickle.load(f)

    variantes = []
    for vs in bundle.get("variantes", []):
        df_h = vs["df_horaire"]
        # Restaurer l'attribut 'zones' sur le DataFrame (utilisé par Variante)
        try:
            df_h.attrs["zones"] = vs.get("zones", [])
        except Exception:
            pass
        variantes.append(Variante(
            nom=vs["nom"],
            df_horaire=df_h,
            df_synthese=vs["df_synthese"],
            df_meteo=vs["df_meteo"],
            zones=vs.get("zones", []),
            meteo_nom=vs.get("meteo_nom", ""),
        ))

    return {
        "format_version": bundle.get("format_version"),
        "nom_projet": bundle.get("nom_projet", ""),
        "params": bundle.get("params", {}),
        "variantes": variantes,
        "ameliorations": bundle.get("ameliorations"),
        "recap_vals": bundle.get("recap_vals"),
        "descriptions": bundle.get("descriptions"),
        "selections": bundle.get("selections", {}),
    }
