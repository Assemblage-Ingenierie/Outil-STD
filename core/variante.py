"""Modèle de données pour une variante STD Pléiades."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd
import numpy as np
import toml

from core.slk_parser import parse_resultats, parse_synthese
from core.try_parser import parse_try


@dataclass
class Variante:
    """Représente une variante de simulation thermique dynamique."""
    nom: str
    df_horaire: pd.DataFrame     # 8736 lignes × colonnes (type|zone)
    df_synthese: pd.DataFrame    # 1 ligne par zone
    df_meteo: pd.DataFrame       # 8760 lignes météo
    zones: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.zones and 'zones' in self.df_horaire.attrs:
            self.zones = self.df_horaire.attrs['zones']

    # ------------------------------------------------------------------
    # Accesseurs colonnes horaires
    # ------------------------------------------------------------------

    def col_temp(self, zone: str) -> pd.Series:
        """Série horaire de température intérieure pour une zone."""
        key = f"Température (°C)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    def col_p_chaud(self, zone: str) -> pd.Series:
        key = f"P Chauffage (W)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    def col_p_froid(self, zone: str) -> pd.Series:
        key = f"P CLim (W)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    def col_apports_sol(self, zone: str) -> pd.Series:
        key = f"Apports solaires (W)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    def col_hr(self, zone: str) -> pd.Series:
        key = f"Humidité relative (%)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    # ------------------------------------------------------------------
    # Calculs indicateurs
    # ------------------------------------------------------------------

    def heures_dessus_seuil(self, zone: str, seuil: float) -> int:
        s = self.col_temp(zone)
        if s.empty:
            return 0
        return int((s > seuil).sum())

    def stats_temp(self, zone: str) -> dict:
        s = self.col_temp(zone)
        if s.empty:
            return {'t_min': np.nan, 't_moy': np.nan, 't_max': np.nan}
        return {
            't_min': float(s.min()),
            't_moy': float(s.mean()),
            't_max': float(s.max()),
        }

    def synthese_zone(self, zone: str) -> dict | None:
        """Retourne la ligne de synthèse annuelle pour une zone."""
        df = self.df_synthese
        mask = df['zone'].str.strip() == zone.strip()
        if not mask.any():
            return None
        return df[mask].iloc[0].to_dict()

    # ------------------------------------------------------------------
    # Tableau de synthèse bâtiment
    # ------------------------------------------------------------------

    def tableau_synthese_global(self, seuil_t1: float, seuil_t2: float) -> pd.DataFrame:
        """DataFrame de synthèse pour toutes les zones (niveau 1)."""
        rows = []
        for zone in self.zones:
            syn = self.synthese_zone(zone)
            stats = self.stats_temp(zone)
            row = {
                'Zone': zone,
                'Surface (m²)': round(syn['surface_m2'], 1) if syn and not np.isnan(syn.get('surface_m2', np.nan)) else '',
                'Besoins chaud (kWh/m²)': round(syn['besoins_chaud_kwh_m2'], 1) if syn else '',
                'Besoins froid (kWh/m²)': round(syn['besoins_froid_kwh_m2'], 1) if syn else '',
                'T min (°C)': round(stats['t_min'], 1),
                'T moy (°C)': round(stats['t_moy'], 1),
                'T max (°C)': round(stats['t_max'], 1),
                f'H > {seuil_t1}°C': self.heures_dessus_seuil(zone, seuil_t1),
                f'H > {seuil_t2}°C': self.heures_dessus_seuil(zone, seuil_t2),
            }
            rows.append(row)
        return pd.DataFrame(rows)


def charger_variante(
    nom: str,
    fichier_resultats: str,
    fichier_synthese: str,
    fichier_meteo: str,
) -> Variante:
    """Charge et assemble une variante depuis ses trois fichiers."""
    df_h = parse_resultats(fichier_resultats)
    df_s = parse_synthese(fichier_synthese)
    df_m = parse_try(fichier_meteo)
    zones = df_h.attrs.get('zones', [])
    return Variante(nom=nom, df_horaire=df_h, df_synthese=df_s, df_meteo=df_m, zones=zones)
