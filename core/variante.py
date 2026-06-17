"""Modèle de données pour une variante STD Pléiades."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd
import numpy as np
import toml

from core.slk_parser import parse_resultats, parse_synthese
from core.try_parser import parse_try, humidite_absolue
from core import confort


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

    def col_apports_eclairage(self, zone: str) -> pd.Series:
        key = f"Apports éclairage (W)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    def col_apports_occupants(self, zone: str) -> pd.Series:
        key = f"Apports occupants (W)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    def col_apports_dissipee(self, zone: str) -> pd.Series:
        key = f"Apports puissance dissipée (W)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    def col_apports_internes(self, zone: str) -> pd.Series:
        """Apports internes = éclairage + occupants + puissance dissipée (équipements)."""
        parts = [
            self.col_apports_eclairage(zone),
            self.col_apports_occupants(zone),
            self.col_apports_dissipee(zone),
        ]
        parts = [p for p in parts if not p.empty]
        if not parts:
            return pd.Series(dtype=float)
        total = parts[0].copy()
        for p in parts[1:]:
            total = total.add(p, fill_value=0)
        return total

    def col_hr(self, zone: str) -> pd.Series:
        key = f"Humidité relative (%)|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

    def col_w_interieur(self, zone: str) -> pd.Series:
        """Humidité absolue intérieure (g/kg) calculée depuis T et HR de la zone."""
        t = self.col_temp(zone)
        hr = self.col_hr(zone)
        if t.empty or hr.empty:
            return pd.Series(dtype=float)
        w = humidite_absolue(t.values, hr.values)
        return pd.Series(w, index=t.index)

    def apports_mensuels(self, zone: str, type_apport: str = "solaires") -> pd.Series:
        """
        Somme mensuelle des apports (kWh) pour une zone.
        type_apport : 'solaires' ou 'internes'.
        Retourne une Series indexée par numéro de mois (1-12).
        """
        if type_apport == "internes":
            s = self.col_apports_internes(zone)
        else:
            s = self.col_apports_sol(zone)
        if s.empty:
            return pd.Series(dtype=float)
        df = pd.DataFrame({"mois": self.df_horaire["mois"].values[:len(s)], "val": s.values})
        # W horaires → kWh (× 1h, ÷ 1000)
        return df.groupby("mois")["val"].sum() / 1000.0

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

    def heures_hors_confort(self, zone: str, config: dict, vitesse: float,
                            methode: str = "givoni") -> int:
        """
        Nombre d'heures où le point (T intérieure, w intérieure) de la zone
        sort de la zone de confort (modèle Givoni ou COCO) pour la vitesse donnée.
        """
        t = self.col_temp(zone)
        w = self.col_w_interieur(zone)
        if t.empty or w.empty:
            return 0
        n = min(len(t), len(w))
        dedans = confort.dans_zone(t.values[:n], w.values[:n], config, methode, vitesse)
        return int((~dedans).sum())

    def heures_occupation(self, zone: str) -> int:
        """
        Nombre d'heures d'occupation, déduit des apports d'occupants (> 0).
        """
        occ = self.col_apports_occupants(zone)
        if occ.empty:
            return 0
        return int((occ.values > 0).sum())

    def pct_hors_confort(self, zone: str, config: dict, vitesse: float,
                         methode: str = "givoni") -> float:
        """
        Pourcentage des HEURES D'OCCUPATION où la zone est hors confort
        (modèle Givoni ou COCO, vitesse d'air donnée).
        Retourne NaN si le local n'a aucune heure d'occupation.
        """
        t = self.col_temp(zone)
        w = self.col_w_interieur(zone)
        occ = self.col_apports_occupants(zone)
        if t.empty or w.empty or occ.empty:
            return np.nan
        n = min(len(t), len(w), len(occ))
        occupe = occ.values[:n] > 0
        n_occ = int(occupe.sum())
        if n_occ == 0:
            return np.nan
        dedans = confort.dans_zone(t.values[:n], w.values[:n], config, methode, vitesse)
        hors_et_occupe = (~dedans) & occupe
        return 100.0 * int(hors_et_occupe.sum()) / n_occ

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

    def tableau_synthese_global(self, seuil_t1: float, seuil_t2: float,
                                config: dict | None = None,
                                zones: list[str] | None = None,
                                methode: str = "givoni") -> pd.DataFrame:
        """DataFrame de synthèse pour les zones demandées (niveau 1)."""
        config = config or {}
        zones = zones if zones is not None else self.zones
        libelle = "COCO" if methode == "coco" else "Givoni"
        rows = []
        for zone in zones:
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
                f'% hors {libelle} 0 m/s': self.pct_hors_confort(zone, config, 0.0, methode),
                f'% hors {libelle} 1 m/s': self.pct_hors_confort(zone, config, 1.0, methode),
            }
            rows.append(row)
        return pd.DataFrame(rows)


def charger_variante(
    nom: str,
    fichier_resultats: str,
    fichier_synthese: str,
    fichier_meteo: str,
) -> Variante:
    """Charge et assemble une variante depuis ses fichiers (météo optionnelle)."""
    df_h = parse_resultats(fichier_resultats)
    df_s = parse_synthese(fichier_synthese)
    if fichier_meteo and Path(fichier_meteo).exists():
        df_m = parse_try(fichier_meteo)
    else:
        df_m = pd.DataFrame(columns=['T_ext', 'HR_ext', 'DNI', 'DHI', 'w_ext'])
    zones = df_h.attrs.get('zones', [])
    return Variante(nom=nom, df_horaire=df_h, df_synthese=df_s, df_meteo=df_m, zones=zones)
