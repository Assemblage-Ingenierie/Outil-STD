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

    with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
        for line in f:
            parts = line.split()
            if len(parts) < 7:
                continue
            try:
                t_ext = int(parts[1]) / 10.0   # °C
                dni   = float(parts[2])          # W/m²
                dhi   = float(parts[3])          # W/m²
                hr_raw = float(parts[6])
                # Météonorm TRY: quand HR=100%, le champ fusionne avec le suivant
                # (ex: "1100" = infrared=1 + HR=100). On plafonne à 100%.
                hr = min(hr_raw, 100.0)
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
