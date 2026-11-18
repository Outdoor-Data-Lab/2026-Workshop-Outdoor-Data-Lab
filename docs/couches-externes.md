# Couches externes

Couches GeoJSON d'autres sites, proposées sur la carte dans le groupe « Couches externes ». Décochées au départ, chaque utilisateur les coche s'il le souhaite. Une couche se télécharge au moment où on la coche.

1. Vérifier que l'URL est lisible depuis le navigateur (en-tête CORS) :
   ```sh
   curl -sI -H 'Origin: http://localhost' <url> | grep -i access-control-allow-origin
   ```
2. Dans l'admin Django : **Commons › External layers › Add**, remplir les champs ci-dessous.
3. Recharger la carte : la couche apparaît dans « Couches externes ».

| Champ | Contenu |
|---|---|
| Label | nom affiché dans la liste des couches |
| Url | FeatureCollection GeoJSON en WGS84 |
| Description | affichée au survol du nom de la couche : contenu, producteur des données |
| Properties | attributs affichés au clic, séparés par des virgules ; vide : tous |
| Color | couleur de la couche |
| Color property, Colors | facultatif : couleur selon la valeur d'un attribut, ex. `STATUT` et `{"IC": "#2e9e5b", "PR": "#c0392b"}` |

Une API paginée est suivie page par page (lien `next`) : bornez le volume dans l'URL, par exemple avec une emprise.

Exemples :

| Couche | URL |
|---|---|
| Zones sensibles (Biodiv'Sports) | `https://biodiv-sports.fr/api/v2/sensitivearea/?language=fr&format=geojson&period=any&in_bbox=5.9,44.6,6.6,45.2` |
| Habitats du PNE (Delphine), 52 Mo | `https://data.ecrins-parcnational.fr/files/Habitats_Delphine_PNE.geojson` |
| Zones humides du PNE | `https://data.ecrins-parcnational.fr/files/Zones_humides_PNE.geojson` |
| Alpages du PNE | `https://data.ecrins-parcnational.fr/files/alpages-pne.geojson` |
| Signalements Suricate du PNE, 2023-2025 | `https://data.ecrins-parcnational.fr/files/Suricate-PNE-2023-2025.geojson` |
