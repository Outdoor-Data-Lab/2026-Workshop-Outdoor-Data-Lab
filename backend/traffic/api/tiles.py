"""Vector tiles (MVT) of the counting objects, for the map.

The Outdoorvision tracks are too many for GeoJSON (40 million points): the map
asks only the visible tiles, from zoom ``MIN_ZOOM``. Each tile simplifies
``geom_tiles`` (already simplified to 10 m) to about two pixels of its zoom.
"""

from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest

from ref_geo.models import LArea

from ..models import CountingObject, CountingObjectType

# Below, a tile of the Écrins holds every track (8 MB): the grid cells show them.
MIN_ZOOM = 11
EXTENT = 4096  # tile resolution, in pixels
LAYER = "counting_objects"
WORLD_WIDTH = 40075016.68  # web mercator, in metres

SQL = """
SELECT ST_AsMVT(t, %(layer)s, %(extent)s, 'geom', 'id') FROM (
    SELECT o.id, ty.code AS type_code,
           ST_AsMVTGeom(ST_Simplify(o.geom_tiles, %(tolerance)s), ST_TileEnvelope(%(z)s, %(x)s, %(y)s),
                        %(extent)s, 64, true) AS geom
    FROM {objects} o JOIN {types} ty ON ty.id = o.type_id
    WHERE o.geom_tiles && ST_TileEnvelope(%(z)s, %(x)s, %(y)s) {filters}
) t
"""


def counting_object_tile(request, z, x, y):
    """Optional filters, as on counting-objects: ``type_code``, ``area_id``
    (objects intersecting this ref_geo area)."""
    if z < MIN_ZOOM:
        return HttpResponse(status=204)
    area_id = request.GET.get("area_id")
    if area_id is not None and not area_id.isdigit():
        return HttpResponseBadRequest("area_id must be an integer.")
    quote = connection.ops.quote_name
    filters = ""
    if "type_code" in request.GET:
        filters += " AND ty.code = %(type_code)s"
    if area_id is not None:
        # Only when asked: ref_geo may not be loaded yet. On geom_tiles, not geom:
        # the same objects, without reading the full tracks (20 s per tile, cold).
        filters += (
            " AND ST_Intersects(o.geom_tiles, (SELECT ST_Transform(geom_4326, 3857)"
            f" FROM {quote(LArea._meta.db_table)} WHERE id_area = %(area_id)s))"
        )
    sql = SQL.format(
        objects=quote(CountingObject._meta.db_table),
        types=quote(CountingObjectType._meta.db_table),
        filters=filters,
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            "layer": LAYER, "extent": EXTENT, "z": z, "x": x, "y": y,
            "tolerance": 2 * WORLD_WIDTH / 2**z / EXTENT,
            "type_code": request.GET.get("type_code"),
            "area_id": int(area_id) if area_id is not None else None,
        })
        tile = bytes(cursor.fetchone()[0])
    response = HttpResponse(tile, content_type="application/vnd.mapbox-vector-tile")
    response["Cache-Control"] = "max-age=300"
    return response
