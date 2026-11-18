# Couches externes

Couches GeoJSON d'autres sites, proposées sur la carte dans le groupe « Couches externes ». Décochées au départ, chaque utilisateur les coche s'il le souhaite. Une couche se télécharge au moment où on la coche.

Dans l'admin Django : **Commons › External layers › Add**.

| Champ | Contenu |
|---|---|
| Label | nom affiché dans la liste des couches |
| Url | FeatureCollection GeoJSON en WGS84 |
| Description | affichée au survol du nom de la couche : contenu, producteur des données |
| Properties | attributs affichés au clic, séparés par des virgules ; vide : tous |
| Color | couleur de la couche |
| Color property, Colors | facultatif : couleur selon la valeur d'un attribut, ex. `STATUT` et `{"IC": "#2e9e5b", "PR": "#c0392b"}` |

L'URL doit être lisible depuis le navigateur (en-tête CORS `Access-Control-Allow-Origin`). Une API paginée est suivie page par page (lien `next`) : bornez le volume dans l'URL, par exemple avec une emprise.

Les URL des couches se transmettent en interne : elles ne figurent pas dans ce dépôt, qui est public.
