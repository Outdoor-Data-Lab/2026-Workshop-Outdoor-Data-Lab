"""Vector tiles (MVT) of the counting objects, for the map.

The Outdoorvision tracks are too many for GeoJSON (40 million points): the map
asks only the visible tiles, from zoom ``MIN_ZOOM``. Each tile simplifies
``geom_tiles`` (already simplified to 10 m) to a few pixels of its zoom.

Tiles are cached (cache "tiles") until the data changes: the key holds
``data_version()``, which changes when an import ends or is deleted.
"""

from django.conf import settings
from django.core.cache.backends.filebased import FileBasedCache
from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest

from commons.models import data_version
from ref_geo.models import LArea

from ..models import CountingObject, CountingObjectType

# Below, a tile of the Écrins holds every track (2 to 8 MB): the grid cells show them.
MIN_ZOOM = 10
EXTENT = 4096  # tile resolution, in pixels
LAYER = "counting_objects"
WORLD_WIDTH = 40075016.68  # web mercator, in metres


def tolerance_pixels(z):
    """4 px at zoom 10 (a third lighter, invisible at that scale), then 2 px."""
    return 4 if z < 11 else 2

SQL = """
SELECT ST_AsMVT(t, %(layer)s, %(extent)s, 'geom', 'id') FROM (
    SELECT o.id, ty.code AS type_code,
           ST_AsMVTGeom(ST_Simplify(o.geom_tiles, %(tolerance)s), ST_TileEnvelope(%(z)s, %(x)s, %(y)s),
                        %(extent)s, 64, true) AS geom
    FROM {objects} o JOIN {types} ty ON ty.id = o.type_id
    WHERE o.geom_tiles && ST_TileEnvelope(%(z)s, %(x)s, %(y)s) {filters}
) t
"""


# On disk: shared by the gunicorn workers, and kept out of Redis, which also queues
# the imports (a tile of a dense area weighs up to 2 MB). Not in settings.CACHES,
# which other features may redefine.
cache = FileBasedCache(
    settings.TILES_CACHE_DIR, {"TIMEOUT": 24 * 3600, "OPTIONS": {"MAX_ENTRIES": 3000}}
)


def counting_object_tile(request, z, x, y):
    """Optional filters, as on counting-objects: ``type_code``, ``area_id``
    (objects intersecting this ref_geo area)."""
    if z < MIN_ZOOM:
        return HttpResponse(status=204)
    type_code = request.GET.get("type_code")
    area_id = request.GET.get("area_id")
    if area_id is not None and not area_id.isdigit():
        return HttpResponseBadRequest("area_id must be an integer.")
    key = f"{data_version()}:{z}/{x}/{y}:{type_code}:{area_id}"
    tile = cache.get(key)
    if tile is None:
        tile = render_tile(z, x, y, type_code, int(area_id) if area_id is not None else None)
        cache.set(key, tile)
    response = HttpResponse(tile, content_type="application/vnd.mapbox-vector-tile")
    response["Cache-Control"] = "max-age=300"
    return response


def render_tile(z, x, y, type_code, area_id):
    quote = connection.ops.quote_name
    filters = ""
    if type_code is not None:
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
            "tolerance": tolerance_pixels(z) * WORLD_WIDTH / 2**z / EXTENT,
            "type_code": type_code,
            "area_id": area_id,
        })
        return bytes(cursor.fetchone()[0])
