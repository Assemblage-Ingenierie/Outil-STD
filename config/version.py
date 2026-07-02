"""Version de l'Outil STD.

Point unique de vérité pour le numéro de version et la date de dernière mise
à jour. À incrémenter À CHAQUE build destiné aux utilisateurs (cf. build.bat) :
  - VERSION : versionnage sémantique MAJEUR.MINEUR.CORRECTIF
      * CORRECTIF (x.y.Z) : corrections de bugs, sans changement de comportement.
      * MINEUR   (x.Y.0)  : nouvelles fonctionnalités rétro-compatibles.
      * MAJEUR   (X.0.0)  : changements de rupture / refonte.
  - DATE_MAJ : date de la release au format AAAA-MM-JJ.

Affiché dans l'onglet Réglages (pied de page).
"""
from __future__ import annotations

VERSION = "1.0.0"
DATE_MAJ = "2026-07-02"


def version_affichee() -> str:
    """Libellé prêt à afficher, ex. « V.1.0.0 »."""
    return f"V.{VERSION}"
