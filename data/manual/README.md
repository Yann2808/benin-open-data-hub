# Fichiers déposés à la main

data.gouv.bj n'autorise pas la collecte automatisée. Pour ajouter un jeu de données :

1. Télécharge le fichier depuis data.gouv.bj (ou une autre source ouverte).
2. Convertis-le en `.csv` s'il est en `.xlsx`, et dépose-le dans ce dossier.
3. Déclare-le dans `config/sources.yml`, section `manual.datasets` :

```yaml
- file: effectifs_ecoles_2024.csv
  table: datagouvbj_effectifs_ecoles     # minuscules, chiffres et _ uniquement
  source_url: https://data.gouv.bj/...  # lien exact de la page source
  producer: Ministère des Enseignements Maternel et Primaire
  downloaded_on: 2026-10-11
```

4. Lance `make run`. Le fichier est chargé dans `raw.<table>` et apparaît dans le catalogue du dashboard avec sa provenance.

Vérifie la licence du jeu de données avant de le republier dans le dépôt Git.
