"""Parser pour les fichiers météo .TRY (Météonorm) utilisés par Pléiades."""
from pathlib import Path
import pandas as pd
import numpy as np


def parse_try(filepath: str | Path) -> pd.DataFrame:
    """
    Parse un fichier météo .TRY Météonorm.
    Retourne un DataFrame de 8760 lignes avec les colonnes:
      T_ext, HR_ext, DNI, DHI, w_ext (humidité absolue g/kg)
    """
    filepath = Path(filepath)
    rows = []

    # Le fichier TRY Météonorm est à LARGEUR FIXE. Un découpage par espaces
    # échoue quand une valeur à 3 chiffres (ex. HR=100, ou un rayonnement)
    # colle à la colonne voisine sans séparateur, ce qui décale les champs
    # et fait lire l'HR au mauvais endroit (humidité nulle parasite).
    # On extrait donc T et HR par tranches de caractères fixes :
    #   T   : colonnes [4:7]   (°C × 10)
    #   DNI : colonnes [7:11]
    #   DHI : colonnes [11:15]
    #   HR  : colonnes [23:26] (%)
    SL_T   = slice(4, 7)
    SL_DNI = slice(7, 11)
    SL_DHI = slice(11, 15)
    SL_HR  = slice(23, 26)

    def _num(s, default=0.0):
        s = s.strip()
        try:
            return float(s) if s else default
        except ValueError:
            return default

    with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
        for line in f:
            if len(line) < 26 or not line[:3].strip():
                continue
            try:
                t_ext = _num(line[SL_T]) / 10.0          # °C
                dni   = _num(line[SL_DNI])
                dhi   = _num(line[SL_DHI])
                hr    = min(_num(line[SL_HR]), 100.0)    # % (sécurité 0-100)
                hr    = max(hr, 0.0)
                # Filtre les lignes d'en-tête éventuelles (T aberrante)
                if not (-60.0 <= t_ext <= 70.0):
                    continue
                rows.append({'T_ext': t_ext, 'HR_ext': hr, 'DNI': dni, 'DHI': dhi})
            except (ValueError, IndexError):
                continue

    df = pd.DataFrame(rows)

    # Calculer humidité absolue w (g/kg air sec) depuis T et HR
    df['w_ext'] = _calc_humidite_absolue(df['T_ext'], df['HR_ext'])

    # Ajouter index temporel (heure de l'année 1-8760)
    df.index = range(1, len(df) + 1)
    df.index.name = 'heure_annee'

    return df


def _calc_humidite_absolue(T: pd.Series, HR: pd.Series) -> pd.Series:
    """
    Calcule l'humidité absolue w en g/kg air sec.
    Formule psychrométrique (pression atmosphérique standard 101325 Pa).
    """
    P_atm = 101325.0  # Pa
    # Pression de vapeur saturante (formule de Magnus)
    psat = 610.78 * np.exp(17.27 * T / (T + 237.3))
    # Pression partielle de vapeur
    pv = (HR / 100.0) * psat
    # Humidité absolue
    w = 0.622 * pv / (P_atm - pv) * 1000  # g/kg
    return w.clip(lower=0)


def humidite_absolue(T_degC: float | np.ndarray, HR_pct: float | np.ndarray) -> float | np.ndarray:
    """Utilitaire: calcule w (g/kg) depuis T (°C) et HR (%)."""
    P_atm = 101325.0
    psat = 610.78 * np.exp(17.27 * T_degC / (T_degC + 237.3))
    pv = (HR_pct / 100.0) * psat
    return 0.622 * pv / (P_atm - pv) * 1000
