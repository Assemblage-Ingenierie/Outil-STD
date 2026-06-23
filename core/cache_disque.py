"""
Cache disque persistant (L2) pour les variantes parsées.

Le parsing d'un fichier résultats .slk 164 zones coûte plusieurs secondes (lecture
regex cellule par cellule + construction du DataFrame). Le cache RAM de Streamlit
(`st.cache_data`) ne survit pas au redémarrage de l'application : chaque session
re-parse les mêmes fichiers. Ce module ajoute un 2e niveau PERSISTANT sur disque :
le 1er parsing écrit un fichier binaire (pickle+gzip, comme `core/projet.py`) dans
un dossier local ; les chargements suivants relisent ce binaire en quelques ms.

Choix techniques (validés) :
- Format pickle+gzip stdlib : zéro dépendance ajoutée (pas de pyarrow/parquet, qui
  ne sont pas bundlés et ne préservent PAS `df.attrs`). pickle préserve nativement
  attrs + dtypes + noms de colonnes.
- Clé d'invalidation = chemin absolu + mtime_ns + TAILLE de chacun des 3 fichiers,
  + FORMAT_VERSION. La taille capte les modifications à mtime préservé (copie).
- Dossier %LOCALAPPDATA%/OutilSTD/cache : local au poste (PAS le drive partagé),
  inscriptible (PAS sous sys._MEIPASS read-only de PyInstaller), persistant.
- Best-effort : toute erreur (corruption, version, I/O) retombe silencieusement sur
  un parsing normal. Le cache n'est JAMAIS bloquant.
"""
from __future__ import annotations
import gzip
import hashlib
import os
import pickle
import tempfile
from pathlib import Path

# À incrémenter dès que le format du DataFrame produit par le parser change
# (sinon un cache écrit par une version antérieure serait relu tel quel).
FORMAT_VERSION = 1

# Nombre max de fichiers conservés dans le cache (purge LRU des plus anciens).
MAX_FICHIERS = 60


def _dossier_cache() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        d = Path(base) / "OutilSTD" / "cache"
    else:
        try:
            d = Path.home() / ".outilstd_cache"
        except Exception:
            d = Path(tempfile.gettempdir()) / "outilstd_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _empreinte(path: str) -> str:
    """Empreinte d'un fichier : chemin absolu + mtime_ns + taille (ou '-' si absent)."""
    if not path:
        return "-"
    try:
        ap = os.path.abspath(path)          # pas de resolve() : évite la résolution réseau
        st = os.stat(ap)
        return f"{ap}|{st.st_mtime_ns}|{st.st_size}"
    except OSError:
        return f"{path}|0|0"


def _cle(res: str, syn: str, met: str) -> Path:
    sig = "||".join(_empreinte(p) for p in (res, syn, met)) + f"||v{FORMAT_VERSION}"
    h = hashlib.sha1(sig.encode("utf-8", errors="replace")).hexdigest()
    return _dossier_cache() / f"{h}.pkl.gz"


def charger(res: str, syn: str, met: str) -> dict | None:
    """
    Retourne le bundle parsé si un cache valide existe, sinon None.
    Bundle = {format_version, df_horaire, df_synthese, df_meteo, zones, groupes, meteo_nom}.
    """
    try:
        chemin = _cle(res, syn, met)
    except Exception:
        return None
    if not chemin.exists():
        return None
    try:
        with gzip.open(chemin, "rb") as f:
            bundle = pickle.load(f)
    except Exception:
        return None  # cache corrompu → reparse
    if not isinstance(bundle, dict) or bundle.get("format_version") != FORMAT_VERSION:
        return None
    return bundle


def ecrire(res: str, syn: str, met: str, df_horaire, df_synthese, df_meteo,
           zones, groupes, meteo_nom: str) -> None:
    """Écrit le bundle dans le cache (best-effort, jamais bloquant). Écriture atomique."""
    bundle = {
        "format_version": FORMAT_VERSION,
        "df_horaire": df_horaire,
        "df_synthese": df_synthese,
        "df_meteo": df_meteo,
        "zones": list(zones) if zones is not None else [],
        "groupes": groupes,
        "meteo_nom": meteo_nom,
    }
    try:
        chemin = _cle(res, syn, met)
        tmp = chemin.with_suffix(".tmp")
        with gzip.open(tmp, "wb", compresslevel=3) as f:
            pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, chemin)
        _purge_lru()
    except Exception:
        pass  # échec d'écriture non bloquant


def _purge_lru() -> None:
    """Supprime les fichiers de cache les plus anciens au-delà de MAX_FICHIERS."""
    try:
        d = _dossier_cache()
        fichiers = sorted(d.glob("*.pkl.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in fichiers[MAX_FICHIERS:]:
            try:
                p.unlink()
            except OSError:
                pass
    except Exception:
        pass


def vider() -> int:
    """Vide entièrement le cache. Retourne le nombre de fichiers supprimés."""
    n = 0
    try:
        for p in _dossier_cache().glob("*.pkl.gz"):
            try:
                p.unlink()
                n += 1
            except OSError:
                pass
    except Exception:
        pass
    return n
