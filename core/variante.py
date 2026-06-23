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
    meteo_nom: str = ""          # nom du fichier météo (identifiant)
    meteo_label: str = ""        # libellé convivial (ex. "Climat actuel", "RCP 8.5")
    periode: tuple | None = None  # (mois_debut, mois_fin) ; None = année entière
    # Cache interne des indicateurs bâtiment (clé = (methode, config_hash))
    _cache_ind: dict = field(default_factory=dict, repr=False, compare=False)
    # Index zone (strippée) -> ligne de synthèse, construit une fois à l'init
    _syn_par_zone: dict = field(default_factory=dict, repr=False, compare=False)
    # Cache du masque de période (clé = (periode, n)) ; periode peut être mutée
    # en place entre re-runs (app.py) → la clé l'absorbe.
    _mask_cache: dict = field(default_factory=dict, repr=False, compare=False)

    def a_meteo(self) -> bool:
        return self.df_meteo is not None and not self.df_meteo.empty

    def masque_periode(self, n: int | None = None):
        """
        Masque booléen des heures appartenant à la période d'analyse active
        (self.periode). None = année entière. Gère les périodes à cheval sur
        l'année (ex. (11, 4) = novembre→avril).
        """
        key = (self.periode, n)
        cached = self._mask_cache.get(key)
        if cached is not None:
            return cached
        mois = self.df_horaire['mois'].values
        if n is not None:
            mois = mois[:n]
        if not self.periode:
            mask = np.ones(len(mois), dtype=bool)
        else:
            m1, m2 = self.periode
            if m1 <= m2:
                mask = (mois >= m1) & (mois <= m2)
            else:
                mask = (mois >= m1) | (mois <= m2)   # période à cheval sur l'année
        mask.flags.writeable = False   # masque partagé en lecture seule
        self._mask_cache[key] = mask
        return mask

    def meteo_affiche(self) -> str:
        """Libellé météo à afficher : le label convivial sinon le nom de fichier."""
        return self.meteo_label or self.meteo_nom or ""

    def __post_init__(self):
        if not self.zones and 'zones' in self.df_horaire.attrs:
            self.zones = self.df_horaire.attrs['zones']
        # Index zone -> ligne de synthèse (lookup O(1) au lieu d'un scan str.strip
        # par appel). setdefault → conserve la 1re occurrence (≡ iloc[0] d'avant).
        self._syn_par_zone = {}
        df_s = self.df_synthese
        if df_s is not None and not df_s.empty and 'zone' in df_s.columns:
            for _, row in df_s.iterrows():
                self._syn_par_zone.setdefault(str(row['zone']).strip(), row.to_dict())
        # Pré-calcule l'humidité absolue intérieure pour toutes les zones une
        # seule fois (économise le calcul psychrométrique répété dans chaque vue).
        self._precalculer_w_interieur()

    # ------------------------------------------------------------------
    # Pré-calcul humidité absolue intérieure
    # ------------------------------------------------------------------

    def _precalculer_w_interieur(self):
        """Calcule w_intérieur (g/kg) pour toutes les zones et le stocke dans
        df_horaire sous la clé ``w_interieur|<zone>``. Appelé une seule fois
        à la création de la Variante."""
        cols = self.df_horaire.columns
        for zone in self.zones:
            w_key = f"w_interieur|{zone}"
            if w_key in cols:
                continue   # déjà calculé (ex. variante reconstruite depuis un cache)
            t_key = f"Température (°C)|{zone}"
            hr_key = f"Humidité relative (%)|{zone}"
            if t_key not in cols or hr_key not in cols:
                continue
            t_vals = self.df_horaire[t_key].values
            hr_vals = self.df_horaire[hr_key].values
            w = humidite_absolue(t_vals, hr_vals)
            self.df_horaire[w_key] = w

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
        """Humidité absolue intérieure (g/kg) — pré-calculée à l'init."""
        key = f"w_interieur|{zone}"
        return self.df_horaire.get(key, pd.Series(dtype=float))

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
        n = len(s)
        mask = self.masque_periode(n)
        df = pd.DataFrame({"mois": self.df_horaire["mois"].values[:n], "val": s.values})
        df = df[mask]
        # W horaires → kWh (× 1h, ÷ 1000)
        return df.groupby("mois")["val"].sum() / 1000.0

    # ------------------------------------------------------------------
    # Calculs indicateurs
    # ------------------------------------------------------------------

    def heures_dessus_seuil(self, zone: str, seuil: float) -> int:
        s = self.col_temp(zone)
        if s.empty:
            return 0
        v = s.values
        v = v[self.masque_periode(len(v))]
        return int((v > seuil).sum())

    def stats_temp(self, zone: str) -> dict:
        s = self.col_temp(zone)
        if s.empty:
            return {'t_min': np.nan, 't_moy': np.nan, 't_max': np.nan}
        v = s.values
        v = v[self.masque_periode(len(v))]
        if v.size == 0:
            return {'t_min': np.nan, 't_moy': np.nan, 't_max': np.nan}
        return {
            't_min': float(v.min()),
            't_moy': float(v.mean()),
            't_max': float(v.max()),
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

    def degre_heures(self, zone: str, seuil: float) -> float:
        """
        Degré-heures d'inconfort chaud : somme des écarts (T intérieure − seuil)
        pour les heures d'OCCUPATION où T > seuil (en °C·h). Mesure la SÉVÉRITÉ
        de l'inconfort, pas seulement sa fréquence.
        NaN si le local n'a aucune heure d'occupation.
        """
        t = self.col_temp(zone)
        occ = self.col_apports_occupants(zone)
        if t.empty or occ.empty:
            return np.nan
        n = min(len(t), len(occ))
        occupe = (occ.values[:n] > 0) & self.masque_periode(n)
        if not occupe.any():
            return np.nan
        ecarts = np.maximum(0.0, t.values[:n][occupe] - seuil)
        return float(ecarts.sum())

    def dh_batiment(self, seuil: float, zones: list[str] | None = None) -> float:
        """Degré-heures moyen du bâtiment, pondéré par la surface des zones."""
        zones = zones if zones is not None else self.zones
        num = den = 0.0
        for z in zones:
            dh = self.degre_heures(z, seuil)
            if dh != dh:   # NaN
                continue
            syn = self.synthese_zone(z)
            surf = (syn.get('surface_m2', np.nan) if syn else np.nan)
            w = surf if (surf == surf and surf > 0) else 1.0
            num += dh * w
            den += w
        return (num / den) if den else np.nan

    def heures_occupation(self, zone: str) -> int:
        """
        Nombre d'heures d'occupation, déduit des apports d'occupants (> 0).
        """
        occ = self.col_apports_occupants(zone)
        if occ.empty:
            return 0
        v = occ.values
        return int(((v > 0) & self.masque_periode(len(v))).sum())

    def pct_hors_confort(self, zone: str, config: dict, vitesse: float,
                         methode: str = "givoni") -> float:
        """
        Pourcentage des HEURES D'OCCUPATION où la zone est hors confort
        (modèle Givoni ou COCO, vitesse d'air donnée).

        Les heures de saison de chauffe sous la consigne (T < borne basse de
        confort) sont considérées comme CONFORTABLES (chauffage à une consigne
        plus basse que le minimum Givoni n'est pas de l'inconfort).
        Retourne NaN si le local n'a aucune heure d'occupation.
        """
        n_hors, n_occ = self._compte_hors_occupe(zone, config, vitesse, methode)
        if n_occ == 0:
            return np.nan
        return 100.0 * n_hors / n_occ

    def _compte_hors_occupe(self, zone: str, config: dict, vitesse: float,
                            methode: str = "givoni") -> tuple[int, int]:
        """
        Retourne (heures occupées ET hors confort, heures d'occupation) pour
        une zone. Sert au % par zone et au % agrégé bâtiment.
        """
        t = self.col_temp(zone)
        w = self.col_w_interieur(zone)
        occ = self.col_apports_occupants(zone)
        if t.empty or w.empty or occ.empty:
            return 0, 0
        n = min(len(t), len(w), len(occ))
        occupe = (occ.values[:n] > 0) & self.masque_periode(n)
        n_occ = int(occupe.sum())
        if n_occ == 0:
            return 0, 0
        dedans = confort.dans_zone(t.values[:n], w.values[:n], config, methode, vitesse)
        exempt = confort.masque_chauffe_sous_consigne(
            t.values[:n], self._est_chauffe(zone, n), config, methode)
        hors_et_occupe = (~dedans) & (~exempt) & occupe
        return int(hors_et_occupe.sum()), n_occ

    def _est_chauffe(self, zone: str, n: int):
        """
        Heures où le local est en chauffe : P chauffage > 0 (indicateur direct,
        toujours disponible) ou, à défaut, saison Pléiades = chauffe.
        """
        pch = self.col_p_chaud(zone)
        if not pch.empty:
            return pch.values[:n] > 0
        if 'saison' in self.df_horaire:
            sais = self.df_horaire['saison'].values[:n]
            return np.array(["chauff" in str(s).strip().lower() for s in sais])
        return np.zeros(n, dtype=bool)

    def points_interieurs_givoni(self, zone: str, config: dict, methode: str = "givoni"):
        """
        Conditions intérieures de la zone pour le diagramme de Givoni :
        (T_int, w_int, saison), après retrait des heures de chauffe sous consigne.
        Retourne un dict de numpy arrays {T, w, saison}.
        """
        t = self.col_temp(zone)
        w = self.col_w_interieur(zone)
        if t.empty or w.empty:
            return {'T': np.array([]), 'w': np.array([]), 'saison': np.array([])}
        n = min(len(t), len(w))
        T = t.values[:n]
        W = w.values[:n]
        saison = self.df_horaire['saison'].values[:n] if 'saison' in self.df_horaire else np.array([''] * n)
        exempt = confort.masque_chauffe_sous_consigne(T, self._est_chauffe(zone, n), config, methode)
        garde = (~exempt) & self.masque_periode(n)
        return {'T': T[garde], 'w': W[garde], 'saison': np.asarray(saison)[garde]}

    def synthese_zone(self, zone: str) -> dict | None:
        """Retourne la ligne de synthèse annuelle pour une zone (lookup O(1))."""
        return self._syn_par_zone.get(str(zone).strip())

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

    # ------------------------------------------------------------------
    # Agrégats au niveau BÂTIMENT (pour la synthèse 1 ligne / variante)
    # ------------------------------------------------------------------

    def indicateurs_batiment(self, config: dict, methode: str = "givoni",
                             zones: list[str] | None = None) -> dict:
        """
        Indicateurs agrégés sur l'ensemble du bâtiment (zones données ou toutes) :
          - Surface totale (somme)
          - Besoins chaud / froid : totaux (kWh) et ratios (kWh/m²)
          - T min (mini global), T moy (moyenne pondérée surface), T max (maxi global)
          - % hors confort 0 / 1 m/s : pondéré par heures d'occupation
        Résultat mis en cache par (methode, config_hash, zones) — recalculé
        seulement si la configuration change.
        """
        config = config or {}
        zones = zones if zones is not None else self.zones
        libelle = "COCO" if methode == "coco" else "Givoni"

        # --- cache (C) ---------------------------------------------------
        try:
            config_key = hash(repr(sorted(config.items())))
        except Exception:
            config_key = id(config)
        cache_key = (methode, config_key, tuple(zones), self.periode)
        if cache_key in self._cache_ind:
            return self._cache_ind[cache_key]
        # -----------------------------------------------------------------

        surf_tot = 0.0
        bch_tot = bfr_tot = 0.0
        t_mins, t_maxs = [], []
        somme_tmoy_surf = 0.0
        somme_surf_pour_tmoy = 0.0
        # Confort : accumulateurs pour les deux vitesses en une seule passe (B)
        tot_hors_0 = tot_occ_0 = 0
        tot_hors_1 = tot_occ_1 = 0

        for zone in zones:
            syn = self.synthese_zone(zone)
            stats = self.stats_temp(zone)
            surf = syn.get('surface_m2', np.nan) if syn else np.nan
            if syn:
                surf_tot += (surf if surf == surf else 0.0)
                bch_tot += syn.get('besoins_chaud_kwh', 0.0) or 0.0
                bfr_tot += syn.get('besoins_froid_kwh', 0.0) or 0.0
            if stats['t_min'] == stats['t_min']:
                t_mins.append(stats['t_min'])
            if stats['t_max'] == stats['t_max']:
                t_maxs.append(stats['t_max'])
            if stats['t_moy'] == stats['t_moy'] and surf == surf and surf > 0:
                somme_tmoy_surf += stats['t_moy'] * surf
                somme_surf_pour_tmoy += surf
            # Confort 0 m/s et 1 m/s dans la même itération zone (B)
            h0, o0 = self._compte_hors_occupe(zone, config, 0.0, methode)
            tot_hors_0 += h0; tot_occ_0 += o0
            h1, o1 = self._compte_hors_occupe(zone, config, 1.0, methode)
            tot_hors_1 += h1; tot_occ_1 += o1

        # T moyenne pondérée surface ; repli moyenne simple si pas de surfaces
        if somme_surf_pour_tmoy > 0:
            t_moy = somme_tmoy_surf / somme_surf_pour_tmoy
        else:
            moys = [self.stats_temp(z)['t_moy'] for z in zones]
            moys = [m for m in moys if m == m]
            t_moy = float(np.mean(moys)) if moys else np.nan

        result = {
            'Surface totale (m²)': round(surf_tot, 1) if surf_tot else np.nan,
            'Besoins chaud (kWh)': round(bch_tot, 0),
            'Besoins chaud (kWh/m²)': round(bch_tot / surf_tot, 1) if surf_tot else np.nan,
            'Besoins froid (kWh)': round(bfr_tot, 0),
            'Besoins froid (kWh/m²)': round(bfr_tot / surf_tot, 1) if surf_tot else np.nan,
            'T min (°C)': round(min(t_mins), 1) if t_mins else np.nan,
            'T moy (°C)': round(t_moy, 1) if t_moy == t_moy else np.nan,
            'T max (°C)': round(max(t_maxs), 1) if t_maxs else np.nan,
            f'% hors {libelle} 0 m/s': (100.0 * tot_hors_0 / tot_occ_0) if tot_occ_0 > 0 else np.nan,
            f'% hors {libelle} 1 m/s': (100.0 * tot_hors_1 / tot_occ_1) if tot_occ_1 > 0 else np.nan,
        }
        self._cache_ind[cache_key] = result
        return result


def charger_variante(
    nom: str,
    fichier_resultats: str,
    fichier_synthese: str,
    fichier_meteo: str,
) -> Variante:
    """
    Charge et assemble une variante depuis ses fichiers (météo optionnelle).

    Cache disque L2 (core/cache_disque) devant le parsing : un fichier déjà parsé
    est rechargé depuis un binaire local au lieu d'être re-parsé (gain majeur entre
    sessions). Best-effort : toute erreur de cache retombe sur un parsing normal.
    """
    from core import cache_disque

    bundle = cache_disque.charger(fichier_resultats, fichier_synthese, fichier_meteo)
    if bundle is not None:
        df_h = bundle['df_horaire']
        df_s = bundle['df_synthese']
        df_m = bundle['df_meteo']
        zones = bundle.get('zones', [])
        meteo_nom = bundle.get('meteo_nom', "")
        # Restaurer les attrs (pickle les préserve en principe, mais on les
        # ré-affecte explicitement pour ne dépendre d'aucune version pandas).
        try:
            df_h.attrs['zones'] = zones
            if bundle.get('groupes') is not None:
                df_h.attrs['groupes'] = bundle['groupes']
        except Exception:
            pass
        return Variante(nom=nom, df_horaire=df_h, df_synthese=df_s, df_meteo=df_m,
                        zones=zones, meteo_nom=meteo_nom)

    # --- cache miss : parsing complet ---
    df_h = parse_resultats(fichier_resultats)
    df_s = parse_synthese(fichier_synthese)
    meteo_nom = ""
    if fichier_meteo and Path(fichier_meteo).exists():
        df_m = parse_try(fichier_meteo)
        meteo_nom = Path(fichier_meteo).name
    else:
        df_m = pd.DataFrame(columns=['T_ext', 'HR_ext', 'DNI', 'DHI', 'w_ext'])
    zones = df_h.attrs.get('zones', [])
    cache_disque.ecrire(fichier_resultats, fichier_synthese, fichier_meteo,
                        df_h, df_s, df_m, zones, df_h.attrs.get('groupes'), meteo_nom)
    return Variante(nom=nom, df_horaire=df_h, df_synthese=df_s, df_meteo=df_m,
                    zones=zones, meteo_nom=meteo_nom)
