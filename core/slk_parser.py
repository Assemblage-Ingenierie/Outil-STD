"""Parser pour les fichiers .slk exportés par Pléiades."""
import re
from pathlib import Path
import numpy as np
import pandas as pd


# Groupes de colonnes utiles dans le fichier résultats
GROUPES_UTILES = {
    "T_ext": None,      # colonne unique détectée automatiquement
    "theta_rm": None,
    "saison": None,
    "temperature": "Température (°C)",
    "p_chauffage": "P Chauffage (W)",
    "p_clim": "P CLim (W)",
    "apports_solaires": "Apports solaires (W)",
    "apports_solaires_nets": "Apports solaires Nets (W)",
    "humidite_relative": "Humidité relative (%)",
    "ppd": "PPD",
    "pmv": "PMV",
}


def _parse_value(raw: str):
    """Convertit une valeur brute SLK en Python (str ou float)."""
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    try:
        return float(raw)
    except ValueError:
        return raw


def _lire_cellules(filepath: Path, lignes_cibles: set | None = None) -> dict:
    """
    Lit le fichier SLK et retourne un dict {(row, col): valeur}.
    Si lignes_cibles est fourni, ne charge que ces numéros de ligne Y.
    """
    cellules = {}
    pattern = re.compile(r'C;Y(\d+);X(\d+);K([^;\n]+)')

    with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
        for line in f:
            if not line.startswith('C;'):
                continue
            m = pattern.search(line)
            if not m:
                continue
            row, col = int(m.group(1)), int(m.group(2))
            if lignes_cibles is not None and row not in lignes_cibles:
                continue
            cellules[(row, col)] = _parse_value(m.group(3))

    return cellules


def _detecter_type(filepath: Path) -> str:
    """Détecte si le fichier est 'resultats' (>500 cols) ou 'synthese'."""
    max_col = 0
    with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
        for line in f:
            if not line.startswith('C;Y1;'):
                if line.startswith('C;') and 'Y1' not in line:
                    continue
                continue
            m = re.search(r'X(\d+)', line)
            if m:
                max_col = max(max_col, int(m.group(1)))
    return 'resultats' if max_col > 500 else 'synthese'


def parse_resultats(filepath: str | Path) -> pd.DataFrame:
    """
    Parse un fichier résultats Pléiades (.slk horaire).
    Retourne un DataFrame avec index temporel et colonnes multi-niveaux:
      (type_grandeur, nom_zone)
    Plus les colonnes globales: mois, jour, heure, T_ext, theta_rm, saison
    """
    filepath = Path(filepath)

    # 1. Lire les en-têtes (Y1 et Y2)
    headers = _lire_cellules(filepath, lignes_cibles={1, 2})

    # Séparer types (Y1) et noms de zones (Y2)
    types_col = {col: val for (row, col), val in headers.items() if row == 1}
    zones_col = {col: val for (row, col), val in headers.items() if row == 2}

    # 2. Identifier les colonnes globales
    # Col 1=mois, 2=jour, 3=heure, 4=T_ext, 5=theta_rm, 6=saison
    cols_globales = {1, 2, 3, 4, 5, 6}

    # 3. Construire le mapping type → liste de (col, zone)
    groupes: dict[str, list[tuple[int, str]]] = {}
    for col, type_name in types_col.items():
        if col in cols_globales:
            continue
        if type_name not in groupes:
            groupes[type_name] = []
        zone = zones_col.get(col, f"Zone_{col}")
        groupes[type_name].append((col, zone))

    # Extraire la liste des zones depuis le premier groupe trouvé
    zones = []
    for type_name in ["Température (°C)", "P Chauffage (W)"]:
        if type_name in groupes:
            zones = [z for _, z in sorted(groupes[type_name])]
            break

    # 4. Identifier les colonnes à charger (globales + groupes utiles)
    noms_utiles = set(GROUPES_UTILES.values()) - {None}
    cols_a_charger: set[int] = set(cols_globales)
    for type_name, items in groupes.items():
        if type_name in noms_utiles:
            cols_a_charger.update(c for c, _ in items)

    # 5. Lire toutes les données
    print(f"  Lecture de {filepath.name}...")
    toutes_cellules = _lire_cellules(filepath)

    # 6. Déterminer le nombre de lignes de données
    max_row = max(r for (r, c) in toutes_cellules.keys())
    n_rows = max_row - 2  # lignes 3 à max_row

    # 7. Construire le DataFrame
    # Colonnes globales
    data = {
        'mois':    [toutes_cellules.get((r+3, 1), np.nan) for r in range(n_rows)],
        'jour':    [toutes_cellules.get((r+3, 2), np.nan) for r in range(n_rows)],
        'heure':   [toutes_cellules.get((r+3, 3), np.nan) for r in range(n_rows)],
        'T_ext':   [toutes_cellules.get((r+3, 4), np.nan) for r in range(n_rows)],
        'theta_rm':[toutes_cellules.get((r+3, 5), np.nan) for r in range(n_rows)],
        'saison':  [toutes_cellules.get((r+3, 6), '') for r in range(n_rows)],
    }

    # Colonnes par groupe/zone
    for type_name, items in groupes.items():
        if type_name not in noms_utiles:
            continue
        for col, zone in sorted(items):
            key = f"{type_name}|{zone}"
            data[key] = [toutes_cellules.get((r+3, col), np.nan) for r in range(n_rows)]

    df = pd.DataFrame(data)
    df['mois'] = df['mois'].astype(int, errors='ignore')
    df['jour'] = df['jour'].astype(int, errors='ignore')
    df['heure'] = df['heure'].astype(int, errors='ignore')

    df.attrs['zones'] = zones
    df.attrs['groupes'] = {k: v for k, v in groupes.items() if k in noms_utiles}

    return df


def parse_synthese(filepath: str | Path) -> pd.DataFrame:
    """
    Parse un fichier synthèse Pléiades (.slk annuel).

    Le fichier contient deux tableaux :
      - Tableau 1 (Y4→) : Besoins Ch/Clim, Puissance, T° min/moy/max
      - Tableau 2 (Y68→) : Apports solaires, Conso éclairage, Heures inconfort, Surface, Volume

    Retourne un DataFrame fusionné avec une ligne par zone.
    """
    filepath = Path(filepath)
    cellules = _lire_cellules(filepath)

    def _f(val, default=0.0):
        if val is None:
            return float(default)
        try:
            return float(val)
        except (ValueError, TypeError):
            return float(default)

    # Détecter les lignes "Zones" (en-têtes de tableaux) pour délimiter les blocs
    # Y1 = premier en-tête, Yn = deuxième en-tête du second tableau
    header_rows = sorted(
        r for (r, c), v in cellules.items()
        if c == 1 and str(v).strip() == 'Zones'
    )
    # Plages de données : entre chaque paire d'en-têtes
    # Tableau 1 : rows header_rows[0]+3 .. header_rows[1]-1 (si 2 en-têtes)
    # Tableau 2 : rows header_rows[1]+3 .. fin

    r_start1 = (header_rows[0] if header_rows else 1) + 3  # +3 : skip header, units, blank
    r_end1   = (header_rows[1] - 1) if len(header_rows) > 1 else max(r for (r,c) in cellules)
    r_start2 = (header_rows[1] + 3) if len(header_rows) > 1 else None

    # Parsing tableau 1
    table1: dict[str, dict] = {}
    for r in range(r_start1, r_end1 + 1):
        zone = cellules.get((r, 1))
        if zone is None or str(zone).strip() in ('', 'Total'):
            continue
        zone = str(zone).strip()
        table1[zone] = {
            'zone': zone,
            'besoins_chaud_kwh':    _f(cellules.get((r, 2))),
            'besoins_chaud_kwh_m2': _f(cellules.get((r, 3))),
            'besoins_froid_kwh':    _f(cellules.get((r, 4))),
            'besoins_froid_kwh_m2': _f(cellules.get((r, 5))),
            'puiss_chaud_w':        _f(cellules.get((r, 6))),
            'puiss_froid_w':        _f(cellules.get((r, 7))),
            't_min': _f(cellules.get((r, 8)),  default=np.nan),
            't_moy': _f(cellules.get((r, 9)),  default=np.nan),
            't_max': _f(cellules.get((r, 10)), default=np.nan),
            'surface_m2': np.nan,
            'volume_m3':  np.nan,
            'heures_inconfort': np.nan,
        }

    # Parsing tableau 2 (Surface en col 8, Volume en col 9, Heures inconfort en col 4)
    if r_start2:
        max_row = max(r for (r, c) in cellules)
        for r in range(r_start2, max_row + 1):
            zone = cellules.get((r, 1))
            if zone is None or str(zone).strip() in ('', 'Total'):
                continue
            zone = str(zone).strip()
            if zone in table1:
                table1[zone]['surface_m2']       = _f(cellules.get((r, 8)), default=np.nan)
                table1[zone]['volume_m3']         = _f(cellules.get((r, 9)), default=np.nan)
                table1[zone]['heures_inconfort']  = _f(cellules.get((r, 4)), default=np.nan)

    return pd.DataFrame(list(table1.values()))


def parse_slk_auto(filepath: str | Path) -> tuple[str, pd.DataFrame]:
    """
    Détecte automatiquement le type et parse.
    Retourne (type, dataframe) où type = 'resultats' ou 'synthese'.
    """
    filepath = Path(filepath)
    type_fichier = _detecter_type(filepath)
    if type_fichier == 'resultats':
        return 'resultats', parse_resultats(filepath)
    else:
        return 'synthese', parse_synthese(filepath)
