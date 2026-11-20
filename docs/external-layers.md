# External layers

GeoJSON layers from other websites are available on the map in the **External
layers** group. They are disabled by default, and users can enable them as
needed. A layer is downloaded when it is enabled.

In the Django admin interface, go to **Commons › External layers › Add**.

| Field | Content |
|---|---|
| Label | Name displayed in the layer list |
| Url | GeoJSON FeatureCollection in WGS84 |
| Description | Displayed when hovering over the layer name; describes the content and data provider |
| Properties | Comma-separated attributes displayed when a feature is clicked; leave blank to display all attributes |
| Color | Layer color |
| Color property, Colors | Optional: color features according to an attribute value, e.g. `STATUT` and `{"IC": "#2e9e5b", "PR": "#c0392b"}` |

The URL must be accessible from the browser (CORS
`Access-Control-Allow-Origin` header). Paginated APIs are retrieved one page at
a time by following the `next` link. Limit the amount of data in the URL, for
example by specifying a bounding box.

Layer URLs are shared internally and are not stored in this public repository.

To place a layer in the layer list, see [Layer order](layer-order.md).
