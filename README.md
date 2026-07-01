# Outil STD

Outil métier d'analyse des sorties de **simulation thermique dynamique (STD) Pléiades**, pour l'équipe environnement d'Assemblage ingénierie. Application Streamlit, 100 % hors-ligne, packagée en exécutable Windows.

## Fonctionnalités

- **Trois niveaux d'analyse** : synthèse générale (niveau bâtiment, 1 ligne par variante), focus zone, comparaison de zones.
- **Diagrammes bioclimatiques** Givoni et COCO (adaptation tropicale), conditions intérieures par zone.
- **Confort** exprimé en % des heures d'occupation hors confort (vitesses d'air 0 et 1 m/s).
- **Humidité relative** : synthèse, cartes jour × heure, courbes horaires.
- **Périodes d'analyse** et **périodes de focus** configurables, seuils T0/T1/T2, inconfort jour/nuit, degré-heures.
- **Météo** par défaut du projet, surchargeable par variante (fichiers Météonorm `.try`).
- **Export Word** selon la charte Assemblage (couverture, synthèse, focus, comparaison).
- **Projet autoportant** `.stdproj` (variantes parsées + paramètres + sélections).

## Formats d'entrée (3 fichiers par variante)

- Résultats `.slk` — données horaires par zone (8736 h × colonnes).
- Synthèse `.slk` — besoins, températures, surfaces, volumes.
- Météo `.try` (Météonorm) — fichier à largeur fixe.

## Lancer en développement

```bat
lancer.bat
```

Détecte automatiquement `py` ou `python` et démarre Streamlit sur le port 8501.

## Construire l'exécutable

```bat
build.bat
```

Enchaîne l'installation des dépendances puis PyInstaller (`outil_std.spec`, `--onedir`, ~3 min).
Sortie : **`dist/Outil STD/Outil STD.exe`**.

> **Distribution** : envoyer le **dossier complet** `dist/Outil STD/` zippé, à extraire entièrement.
> L'exe seul ne fonctionne pas (il a besoin de `_internal/`).

## Tests

```bat
py -m pytest tests/ -v
```

## Dépannage

- **Fenêtre blanche / démarrage impossible chez un utilisateur** : le terminal est masqué, consulter les logs
  `%LOCALAPPDATA%\OutilSTD\outil_std.log` (lanceur) et `outil_std_server.log` (serveur).
- **`ERR_CONNECTION_REFUSED` au lancement** : port 8501 occupé par un process fantôme, ou proxy d'entreprise
  interceptant les adresses locales → ajouter `localhost;127.0.0.1` aux exceptions proxy Windows.
- **Export du rapport Word en erreur** : renseigner le champ **« Nom du projet »** dans l'onglet *Réglages*
  avant de générer le rapport.
- **Premier chargement d'un gros fichier lent (minutes)** : normal (parsing `.slk`). Les chargements suivants
  du même fichier sont mis en cache disque. Enregistrer le projet `.stdproj` après le setup pour des réouvertures rapides.
