# Ordre des couches

L'ordre des couches du panneau de gauche se règle dans l'admin Django (http://localhost:8000/admin/), page **Commons › Layer orders**.

1. Cliquer sur **Add**.
2. **Layer** : l'identifiant de la couche (voir le tableau).
3. **Order** : son rang dans son groupe, le plus petit en premier.
4. **Save**.

Pour changer un rang ensuite, modifier la colonne **Order** directement dans la liste, puis **Save**. Rechargez la carte pour voir le nouvel ordre.

| Groupe | Couche | Identifiant |
|---|---|---|
| Fréquentation | une couche par type de compteur | `traffic/<code du type>`, ex. `traffic/counter`, `traffic/segment` |
| Fréquentation | fréquentation par maille | `traffic/area` |
| Biodiversité | taxons menacés par maille | `biodiversity/area` |
| Outdoor | offres outdoor | `outdoor/offer` |
| Couches externes | une couche par couche externe | `external/<id>`, l'id de la couche dans l'admin (dans l'URL de sa page) |

Le rang vaut à l'intérieur d'un groupe : l'ordre des groupes ne change pas. Les couches sans rang passent après celles qui en ont un, dans leur ordre habituel.
