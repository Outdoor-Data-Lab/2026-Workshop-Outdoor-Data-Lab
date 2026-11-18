"""Import a GeoPackage of offers (trails, climbing sites, take-offs...) into outdoor.

One parser for every source: the offers go to the source chosen for the import.
The file has a single layer, a defined CRS, and the columns:
- id: the offer's id in its source (external_id), required;
- name: required;
- practice: a commons.Practice code, any level of the hierarchy;
- uuid: optional, never generated;
- the geometry: any type (point, line, polygon, multi or collection); Z is
  dropped and an invalid geometry is repaired.
Other columns are ignored.

A line in error is skipped, counted in error_numbers and described in
OfferParser.errors. The file is the reference for its source: offers it no
longer lists are deleted, the others are replaced by their line, uuid included.
An offer whose line is in error is kept unchanged. A problem with the whole file
(format, layers, CRS, columns, no valid line) refuses it (ValueError, see
commons.parsers.ImportParser).

An offer is linked to the last import that wrote it, created or updated
(Offer.data_import): deleting that import deletes the offer.
"""

import uuid
from itertools import batched

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from django.contrib.gis.geos import GEOSGeometry
from django.db import IntegrityError
from django.utils import timezone
from pyogrio.errors import DataSourceError

from commons.models import Practice
from commons.parsers import ImportParser, describe_errors

from .models import Offer

REQUIRED_COLUMNS = {"id", "name", "practice"}
MAX_LENGTH = 255  # of id and name
BATCH_SIZE = 5000


def text(value) -> str:
    """Cell -> stripped string, "" when missing (a NULL is read as NaN)."""
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():  # integer column with NULLs
        value = int(value)
    return str(value).strip()


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def geometry(geom):
    """2D valid geometry, or None when missing or empty."""
    if geom is None or geom.is_empty:
        return None
    geom = shapely.force_2d(geom)
    if not geom.is_valid:
        was_collection = geom.geom_type == "GeometryCollection"
        dimension = shapely.get_dimensions(geom)
        geom = shapely.make_valid(geom)
        if geom.geom_type == "GeometryCollection" and not was_collection:
            # Repairing a simple geometry may add lower-dimension parts: keep its dimension.
            parts = shapely.get_parts(geom)
            geom = shapely.union_all(parts[shapely.get_dimensions(parts) == dimension])
    return None if geom.is_empty else geom


class OfferParser(ImportParser):
    LABEL = "Offers (GPKG)"
    NAME = "Offers"
    CONTENT = (
        "Holds offers (trails, climbing sites, take-offs...). The file is the reference for "
        "its source: the offers it no longer lists are deleted."
    )
    EXAMPLE = (
        "GeoPackage (.gpkg) with a single layer and a coordinate reference system. "
        "Columns: id (the offer's id in its source), name, practice (a practice code, "
        "e.g. hiking), uuid (optional). Geometry: points, lines, polygons or collections. "
        "Other columns are ignored."
    )

    def read(self) -> tuple[int, pd.DataFrame]:
        """The valid offers of the file; sets self.errors and self.listed_ids."""
        lines = self._read_layer()
        return len(lines), pd.DataFrame(self._check_lines(lines))

    def plan(self, rows: pd.DataFrame) -> dict[str, int]:
        known = self._known()
        created = int((~rows["external_id"].isin(list(known))).sum())
        return {
            "Offers created": created,
            "Offers updated": len(rows) - created,
            "Offers deleted, missing from the file": sum(
                external_id not in self.listed_ids for external_id in known
            ),
        }

    def save(self, rows: pd.DataFrame) -> None:
        try:
            self._save(rows.to_dict("records"))
        except IntegrityError as exc:
            raise ValueError("uuid conflict with existing offers.") from exc

    def _known(self) -> dict[str, int]:
        """The source's offers: pk by external id."""
        return dict(Offer.objects.filter(source=self.source).values_list("external_id", "pk"))

    def _read_layer(self) -> gpd.GeoDataFrame:
        """The single layer of the file, in WGS84."""
        path = self.data_import.file.path
        try:
            layers = pyogrio.list_layers(path)
            driver = pyogrio.read_info(path)["driver"]
        except DataSourceError as exc:
            raise ValueError("The file is not a readable GeoPackage.") from exc
        if driver != "GPKG":
            raise ValueError("Only GeoPackage files (.gpkg) are accepted.")
        if len(layers) != 1:
            raise ValueError(f"The GeoPackage must have a single layer, it has {len(layers)}.")

        lines = gpd.read_file(path)
        missing = REQUIRED_COLUMNS.difference(lines.columns)
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}.")
        if lines.crs is None:
            raise ValueError("The file defines no coordinate reference system.")
        return lines.to_crs(4326)

    def _check_lines(self, lines) -> list[dict]:
        """The valid offers; sets self.errors and self.listed_ids (lines in error included)."""
        ids = lines["id"].map(text)
        uuids = lines["uuid"].map(text) if "uuid" in lines else pd.Series("", index=lines.index)
        # An id or uuid given twice puts all its lines in error.
        id_doubles = ids.duplicated(keep=False) & (ids != "")
        uuid_doubles = uuids.duplicated(keep=False) & (uuids != "")
        practices = Practice.objects.in_bulk(field_name="code")
        # uuids are unique across sources.
        taken = set(
            Offer.objects.exclude(source=self.source)
            .filter(uuid__in={u for u in map(parse_uuid, uuids) if u})
            .values_list("uuid", flat=True)
        )

        offers = []
        lines_data = zip(
            ids,
            lines["name"].map(text),
            lines["practice"].map(text),
            lines.geometry.map(geometry),
            uuids,
            id_doubles,
            uuid_doubles,
        )
        for number, (line_id, name, practice, geom, line_uuid, id_double, uuid_double) in enumerate(
            lines_data, start=1
        ):
            valid_uuid = parse_uuid(line_uuid) if line_uuid else None
            if not line_id:
                error = "missing id"
            elif id_double:
                error = "id given twice in the file"
            elif not name:
                error = "missing name"
            elif max(len(line_id), len(name)) > MAX_LENGTH:
                error = f"id or name longer than {MAX_LENGTH} characters"
            elif not practice:
                error = "missing practice"
            elif practice.lower() not in practices:
                error = f'unknown practice "{practice}"'
            elif geom is None:
                error = "missing or empty geometry"
            elif line_uuid and valid_uuid is None:
                error = "invalid uuid"
            elif uuid_double:
                error = "uuid given twice in the file"
            elif valid_uuid in taken:
                error = "uuid already used by an offer of another source"
            else:
                offers.append(
                    {
                        "external_id": line_id,
                        "name": name,
                        "practice": practices[practice.lower()],
                        "uuid": valid_uuid,
                        "geom": GEOSGeometry(memoryview(geom.wkb), srid=4326),
                    }
                )
                continue
            self.errors.append((number, line_id, error))
        self.listed_ids = set(ids) - {""}
        if not offers:
            raise ValueError(f"The file has no valid line ({describe_errors(self.errors, 3)}).")
        return offers

    def _save(self, offers: list[dict]) -> None:
        known = self._known()
        gone = [pk for external_id, pk in known.items() if external_id not in self.listed_ids]
        for i in range(0, len(gone), BATCH_SIZE):
            Offer.objects.filter(pk__in=gone[i : i + BATCH_SIZE]).delete()

        now = timezone.now()
        updated = (
            Offer(pk=known[offer["external_id"]], data_import=self.data_import, date_update=now, **offer)
            for offer in offers
            if offer["external_id"] in known
        )
        created = (
            Offer(source=self.source, data_import=self.data_import, **offer)
            for offer in offers
            if offer["external_id"] not in known
        )
        # One call per batch, so the model instances are not all built at once.
        for batch in batched(updated, BATCH_SIZE):
            Offer.objects.bulk_update(
                batch, ["name", "practice", "uuid", "geom", "data_import", "date_update"]
            )
        for batch in batched(created, BATCH_SIZE):
            Offer.objects.bulk_create(batch)
