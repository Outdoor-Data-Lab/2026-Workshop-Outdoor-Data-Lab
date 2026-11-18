# Importer des données

Dans l'admin Django (http://localhost:8000/admin/) : ouvrir la page d'import, cliquer sur **Add**, choisir la source et le fichier, puis **Save**. Le texte sous « Source » décrit le fichier attendu.

| Données | Page | Source | Fichier |
|---|---|---|---|
| Traces Outdoorvision | Traffic › Traffic imports | OutdoorVision | GPKG de traces brutes |
| Strava Metro | Traffic › Traffic imports | Strava | zip annuel ou journalier, tel que livré |
| Compteurs | Traffic › Traffic imports | Eco-Compteur | CSV produit par `compteurs_to_csv.py` |
| Observateurs iNaturalist | Traffic › Traffic imports | iNaturalist | export iNaturalist ou téléchargement GBIF (zip) |
| Observations SINP | Biodiversité › Observation imports | SINP | CSV de la synthèse GeoNature |
| Occurrences GBIF | Biodiversité › Observation imports | GBIF | CSV GBIF dézippé (TaxRef chargé) |
| Offres | Outdoor › Offer imports | source des offres | GeoPackage, puis **Apply the import** |

Historique de tous les imports : Commons › Data imports.

Ne pas importer de données SINP sensibles : la sensibilité n'est pas encore gérée.
