"""
Parser pour les fichiers .CSV exportés par Pléiades (alternative au .slk / SYLK).

Le CSV Pléiades est bien plus compact que le SYLK (une ligne par pas de temps, au
lieu d'une ligne par cellule) : le fichier résultats est ~5× plus petit et se lit
en quelques secondes via ``pandas.read_csv`` (C), là où le SYLK impose un balayage
regex de ~17 M lignes (~100 s sur un gros projet). Voir core.slk_parser pour la
version SYLK ; ce module produit des DataFrames STRICTEMENT au même format
(mêmes colonnes ``type|zone``, mêmes globales, mêmes ``df.attrs``) afin d'être
interchangeable en aval.

Format observé (export Pléiades) :
  - séparateur « , », décimale « . », encodage UTF-8 avec BOM ;
  - RÉSULTATS : ligne 1 = type de grandeur, ligne 2 = zone (ou unité pour les
    globales), puis les données ; colonnes globales mois/jour/heure/Températures/
    Theta rm/Saison, puis une colonne par (grandeur, zone) ;
  - SYNTHÈSE : deux tableaux successifs, chacun introduit par une ligne « Zones »
    (entête) suivie d'une ligne d'unités puis des lignes de zones ; positions de
    colonnes identiques au SYLK.
"""
from __future__ import annotations
import csv as _csv
from pathlib import Path

import numpy as np
import pandas as pd

from core.slk_parser import (
    GROUPES_UTILES, GROUPES_REQUIS, GLOBALES_NOMS, FichierInvalideError,
)

# Le CSV Pléiades peut contenir des lignes très larges (colonnes de consommation).
_csv.field_size_limit(10 * 1024 * 1024)

ENCODAGE = "utf-8-sig"   # -sig : retire le BOM éventuel en tête de fichier


def _f(val, default=0.0):
    """Convertit une valeur texte en float (notation scientifique tolérée),
    sinon `default`. Vide/None → default."""
    if val is None:
        return float(default)
    s = str(val).strip()
    if not s:
        return float(default)
    try:
        return float(s)
    except ValueError:
        return float(default)


def parse_resultats(filepath: str | Path) -> pd.DataFrame:
    """
    Parse un fichier RÉSULTATS Pléiades au format CSV. Retourne un DataFrame au
    même format que ``core.slk_parser.parse_resultats`` :
      colonnes mois, jour, heure, T_ext, theta_rm, saison + une colonne
      ``{grandeur}|{zone}`` par grandeur utile, et df.attrs['zones'/'groupes'].
    """
    filepath = Path(filepath)

    # 1. En-têtes : ligne 1 = types de grandeur, ligne 2 = zones (ou unités).
    with open(filepath, "r", encoding=ENCODAGE, newline="") as f:
        reader = _csv.reader(f)
        try:
            types_row = next(reader)
            zones_row = next(reader)
        except StopIteration:
            raise FichierInvalideError(
                "Fichier CSV vide ou sans en-tête (types + zones attendus sur 2 lignes).")

    types = [t.strip() for t in types_row]
    zones_h = [z.strip() for z in zones_row]

    # 2. Colonnes globales : mois/jour/heure (fixes) + globales repérées par nom.
    cols_globales = {0, 1, 2}                 # mois, jour, heure
    col_par_global: dict[str, int] = {}
    for i, nom in enumerate(types):
        if i in (0, 1, 2):
            continue
        if nom in GLOBALES_NOMS:
            cle = GLOBALES_NOMS[nom]
            if cle not in col_par_global:     # 1re occurrence seulement
                col_par_global[cle] = i
                cols_globales.add(i)

    # 3. Mapping grandeur → [(col, zone)] (hors globales).
    groupes: dict[str, list[tuple[int, str]]] = {}
    for i, nom in enumerate(types):
        if i in cols_globales or not nom:
            continue
        zone = zones_h[i] if i < len(zones_h) and zones_h[i] else f"Zone_{i}"
        groupes.setdefault(nom, []).append((i, zone))

    # Liste des zones : depuis le 1er groupe trouvé (température puis chauffage).
    zones: list[str] = []
    for nom in ["Température (°C)", "P Chauffage (W)"]:
        if nom in groupes:
            zones = [z for _, z in sorted(groupes[nom])]
            break

    # 4. Colonnes à charger = globales + grandeurs utiles.
    noms_utiles = set(GROUPES_UTILES.values()) - {None}
    cols_a_charger = set(cols_globales)
    for nom, items in groupes.items():
        if nom in noms_utiles:
            cols_a_charger.update(c for c, _ in items)
    cols_a_charger = sorted(cols_a_charger)

    # 5. Lecture des données (C parser vectorisé) : seules les colonnes utiles.
    #    skipinitialspace : les valeurs sont préfixées d'une espace (« , 1.9E+1 »).
    print(f"  Lecture de {filepath.name} (CSV)...")
    brut = pd.read_csv(
        filepath, sep=",", header=None, skiprows=2, usecols=cols_a_charger,
        encoding=ENCODAGE, skipinitialspace=True, na_values=[""],
        dtype=str, keep_default_na=False, low_memory=False,
    )
    # read_csv renvoie les colonnes dans l'ordre du fichier (indices croissants).
    brut.columns = list(cols_a_charger)

    # 6. Construire le DataFrame de sortie au format attendu.
    n_rows = len(brut)

    def _num_col(idx):
        if idx is None or idx not in brut.columns:
            return np.full(n_rows, np.nan)
        return pd.to_numeric(brut[idx], errors="coerce").to_numpy()

    data = {
        "mois":     _num_col(0),
        "jour":     _num_col(1),
        "heure":    _num_col(2),
        "T_ext":    _num_col(col_par_global.get("T_ext")),
        "theta_rm": _num_col(col_par_global.get("theta_rm")),
    }
    c_sais = col_par_global.get("saison")
    if c_sais is not None and c_sais in brut.columns:
        data["saison"] = brut[c_sais].fillna("").astype(str).to_numpy()
    else:
        data["saison"] = np.array([""] * n_rows, dtype=object)

    # Colonnes par grandeur/zone (numériques).
    for nom, items in groupes.items():
        if nom not in noms_utiles:
            continue
        for col, zone in sorted(items):
            data[f"{nom}|{zone}"] = _num_col(col)

    df = pd.DataFrame(data)
    for _c in ("mois", "jour", "heure"):
        try:
            df[_c] = df[_c].astype(int)
        except (ValueError, TypeError):
            pass

    df.attrs["zones"] = zones
    df.attrs["groupes"] = {k: v for k, v in groupes.items() if k in noms_utiles}

    # 7. Validation (mêmes règles que le parser SYLK).
    presents = set(groupes.keys())
    manquants = [g for g in GROUPES_REQUIS if g not in presents]
    if manquants:
        raise FichierInvalideError(
            "Fichier de résultats incomplet : grandeur(s) manquante(s) — "
            + ", ".join(manquants) + ".\n"
            "Exportez le fichier de RÉSULTATS HORAIRES complet depuis Pléiades "
            "(toutes les grandeurs : températures, humidité, apports…), "
            "et non un export partiel ni le fichier de synthèse."
        )
    if not zones:
        raise FichierInvalideError(
            "Aucune zone détectée dans ce fichier de résultats. "
            "Vérifiez qu'il s'agit bien d'un export de résultats horaires Pléiades."
        )
    return df


def parse_synthese(filepath: str | Path) -> pd.DataFrame:
    """
    Parse un fichier SYNTHÈSE Pléiades au format CSV. Deux tableaux successifs,
    chacun introduit par une ligne « Zones ». Retourne un DataFrame une ligne par
    zone, au même format que ``core.slk_parser.parse_synthese``.
    """
    filepath = Path(filepath)

    # On ne conserve que les ~12 premières colonnes de chaque ligne (les seules
    # utiles) → lecture mémoire-sûre même si les lignes sont larges/paddées.
    lignes: list[list[str]] = []
    zones_headers: list[int] = []
    with open(filepath, "r", encoding=ENCODAGE, newline="") as f:
        for i, row in enumerate(_csv.reader(f)):
            if row and row[0].strip() == "Zones":
                zones_headers.append(i)
            lignes.append(row[:12])

    a_besoins = (any("Besoin" in c for r in lignes[:3] for c in r)
                 or any("Besoin" in c for h in zones_headers for c in lignes[h]))

    # Délimitation des deux tableaux (mêmes offsets que le SYLK : entête, unités,
    # ligne vide, puis données).
    h0 = zones_headers[0] if zones_headers else 0
    r_start1 = h0 + 3
    r_end1 = (zones_headers[1] - 1) if len(zones_headers) > 1 else len(lignes) - 1
    r_start2 = (zones_headers[1] + 3) if len(zones_headers) > 1 else None

    def _cell(row, idx):
        return row[idx] if idx < len(row) else None

    # Tableau 1 : besoins, puissances, T° min/moy/max.
    table1: dict[str, dict] = {}
    for r in range(r_start1, min(r_end1 + 1, len(lignes))):
        row = lignes[r]
        if not row:
            continue
        zone = str(row[0]).strip()
        if zone in ("", "Total"):
            continue
        table1[zone] = {
            "zone": zone,
            "besoins_chaud_kwh":    _f(_cell(row, 1)),
            "besoins_chaud_kwh_m2": _f(_cell(row, 2)),
            "besoins_froid_kwh":    _f(_cell(row, 3)),
            "besoins_froid_kwh_m2": _f(_cell(row, 4)),
            "puiss_chaud_w":        _f(_cell(row, 5)),
            "puiss_froid_w":        _f(_cell(row, 6)),
            "t_min": _f(_cell(row, 7), default=np.nan),
            "t_moy": _f(_cell(row, 8), default=np.nan),
            "t_max": _f(_cell(row, 9), default=np.nan),
            "surface_m2": np.nan,
            "volume_m3":  np.nan,
            "heures_inconfort": np.nan,
        }

    # Tableau 2 : Heures inconfort (col 3), Surface (col 7), Volume (col 8).
    if r_start2 is not None:
        for r in range(r_start2, len(lignes)):
            row = lignes[r]
            if not row:
                continue
            zone = str(row[0]).strip()
            if zone in ("", "Total"):
                continue
            if zone in table1:
                table1[zone]["heures_inconfort"] = _f(_cell(row, 3), default=np.nan)
                table1[zone]["surface_m2"]        = _f(_cell(row, 7), default=np.nan)
                table1[zone]["volume_m3"]         = _f(_cell(row, 8), default=np.nan)

    df = pd.DataFrame(list(table1.values()))
    if df.empty or not a_besoins:
        raise FichierInvalideError(
            "Fichier de synthèse non reconnu : en-têtes « Besoins » absents ou aucune zone. "
            "Sélectionnez le fichier de SYNTHÈSE Pléiades (et non les résultats horaires)."
        )
    return df
