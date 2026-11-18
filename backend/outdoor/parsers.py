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
(format, layers, CRS, columns, no valid line) rejects it: no offer changes and
the import gets error_numbers = 1.

preview() tells what import_data() would do, without writing. An offer is
linked to the last import that wrote it, created or updated (Offer.data_import):
deleting that import deletes the offer.
"""

import uuid

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from django.contrib.gis.geos import GEOSGeometry
from django.db import IntegrityError, transaction
from django.utils import timezone
from pyogrio.errors import DataSourceError

from commons.models import DataImport, Practice

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


def describe_errors(errors: list[tuple[int, str, str]], limit: int = 10) -> str:
    """The first lines in error, as "line 3 (id): reason; ..."."""
    described = "; ".join(
        f"line {number}{f' ({line_id})' if line_id else ''}: {reason}"
        for number, line_id, reason in errors[:limit]
    )
    if len(errors) > limit:
        described += f"; and {len(errors) - limit} more"
    return described


class OfferParser:
    def __init__(self, data_import: DataImport):
        self.data_import = data_import
        self.source = data_import.source
        # Lines in error, filled by check(): (line number, id, reason).
        self.errors: list[tuple[int, str, str]] = []

    def preview(self) -> dict[str, int]:
        """What import_data() would do, without writing anything."""
        lines, offers, listed_ids = self.check()
        known = self.known()
        created = sum(offer["external_id"] not in known for offer in offers)
        return {
            "lines": len(lines),
            "created": created,
            "updated": len(offers) - created,
            "deleted": sum(external_id not in listed_ids for external_id in known),
            "errors": len(self.errors),
        }

    def import_data(self) -> int:
        """Replace the source's offers by those of the file; return their number."""
        try:
            lines, offers, listed_ids = self.check()
            with transaction.atomic():
                self.save(offers, listed_ids)
                self.data_import.line_numbers = len(lines)
                self.data_import.error_numbers = len(self.errors)
                self.data_import.save(update_fields=["line_numbers", "error_numbers"])
        except IntegrityError as exc:
            self._reject()
            raise ValueError("uuid conflict with existing offers.") from exc
        except ValueError:
            self._reject()
            raise
        return len(offers)

    def _reject(self):
        self.data_import.error_numbers = 1
        self.data_import.save(update_fields=["error_numbers"])

    def check(self) -> tuple[gpd.GeoDataFrame, list[dict], set[str]]:
        """The file's lines, the valid offers, and the ids listed (lines in error included)."""
        lines = self.read()
        offers, listed_ids = self.check_lines(lines)
        return lines, offers, listed_ids

    def known(self) -> dict[str, int]:
        """The source's offers: pk by external id."""
        return dict(Offer.objects.filter(source=self.source).values_list("external_id", "pk"))

    def read(self) -> gpd.GeoDataFrame:
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

    def check_lines(self, lines) -> tuple[list[dict], set[str]]:
        """The valid offers, and the ids listed by the file; fills self.errors."""
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

        offers, self.errors = [], []
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
                error = f"unknown practice \"{practice}\""
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
        if not offers:
            raise ValueError(
                f"The file has no valid line ({describe_errors(self.errors, 3)})."
            )
        return offers, set(ids) - {""}

    def save(self, offers: list[dict], listed_ids: set[str]) -> None:
        known = self.known()
        gone = [pk for external_id, pk in known.items() if external_id not in listed_ids]
        for i in range(0, len(gone), BATCH_SIZE):
            Offer.objects.filter(pk__in=gone[i : i + BATCH_SIZE]).delete()

        now = timezone.now()
        Offer.objects.bulk_update(
            [
                Offer(pk=known[offer["external_id"]], data_import=self.data_import, date_update=now, **offer)
                for offer in offers
                if offer["external_id"] in known
            ],
            ["name", "practice", "uuid", "geom", "data_import", "date_update"],
            batch_size=BATCH_SIZE,
        )
        Offer.objects.bulk_create(
            [
                Offer(source=self.source, data_import=self.data_import, **offer)
                for offer in offers
                if offer["external_id"] not in known
            ],
            batch_size=BATCH_SIZE,
        )
