"""App and schema "commons": data shared by every domain (sources, practices,
imports).

Follows the COMMONS part of the "BDD" page of the workshop document.

Naming: primary keys are Django's default "id"; reference tables have "code"
and "label"; foreign key columns use Django's default "<field>_id".

Django has no schema option, so db_table uses the quoted form
'commons"."<table>', which Django splits into schema and table name. The
schema itself is created by migration 0001.
"""

from collections.abc import Callable

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import Count, F, Max, Q
from django.utils.module_loading import import_string

from ref_geo.models import LArea

DB_SCHEMA = "commons"


def table(name):
    return f'{DB_SCHEMA}"."{name}'


# The domain apps a file can be imported into.
DOMAINS = [("traffic", "Traffic"), ("biodiversity", "Biodiversity"), ("outdoor", "Outdoor")]

# File format code -> parser class path. Each domain app registers the formats it
# reads when it starts (register_parsers in its AppConfig.ready()): commons does
# not know them. Updated in place, never rebound, so the modules that imported
# it see every parser.
PARSERS: dict[str, str] = {}


def register_parsers(parsers: dict[str, str]) -> None:
    """Add the formats of a domain app: a format has a single parser."""
    taken = {code for code, path in parsers.items() if PARSERS.get(code, path) != path}
    if taken:
        raise ImproperlyConfigured(f"Formats already having a parser: {', '.join(sorted(taken))}")
    PARSERS.update(parsers)


# Functions giving the (id, LayerGroup code, label) of the map layers of a domain app
# (catalog.ts), registered when the app starts (register_layers in its
# AppConfig.ready()): commons does not know them.
LAYER_SOURCES: list[Callable[[], list[tuple[str, str, str]]]] = []


def register_layers(source: Callable[[], list[tuple[str, str, str]]]) -> None:
    LAYER_SOURCES.append(source)


class DataSource(models.Model):
    """Who data comes from. Three notions are kept apart:

    - source: who provided an imported file (OutdoorVision, a park's Geotrek,
      GBIF...), chosen on the import page (DataImport.source);
    - origin: the application that produced the data in the first place, when
      the file says it (Garmin, Openrunner...), stored on the imported objects
      (CountingObject.origin);
    - format: how the file is read (DataImport.format), whatever its source.

    Both sources and origins are DataSource rows; `domains` tells which import
    pages offer a source. Initial values: migrations 0002 and 0005.
    """

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=500)
    domains = ArrayField(
        models.CharField(max_length=20, choices=DOMAINS),
        default=list,
        blank=True,
        help_text="Import pages offering this source; none for a source used only as an origin.",
    )
    absolute_counts = models.BooleanField(
        default=False,
        help_text="Counts every passage (e.g. an eco-counter), not only a sample of users.",
    )
    hide_raw_data = models.BooleanField(
        default=False,
        help_text=(
            "Do not show the raw objects (segments, tracks...) and measures of this source,"
            " as provider or origin, in the interface (license terms). They still count in"
            " the scores and the cell aggregates."
        ),
    )

    class Meta:
        db_table = table("data_sources")

    def __str__(self):
        return self.label


class Practice(models.Model):
    """A practice, in a hierarchy: broad practices (walking, cycling...) have no
    parent, finer ones (hiking, mountain biking...) point to a broader one.

    Shared by traffic (practice of a counting measure) and outdoor (practice of
    an offer), which may point to any level. Initial values: migration 0002.
    """

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = table("practices")
        constraints = [
            models.CheckConstraint(
                condition=~Q(parent=F("id")),
                name="practice_not_its_own_parent",
            ),
        ]

    def __str__(self):
        return self.label


class DataImport(models.Model):
    """One run of an import: a file, in a format, provided by a source (see DataSource).

    The file is imported by the Celery worker (commons.tasks.run_import), which
    records the outcome in `status` and `message`.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    date_import = models.DateTimeField(auto_now_add=True)
    # How the file is read: a key of PARSERS.
    format = models.CharField(max_length=50)
    source = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="imports",
        help_text="Who provided the file.",
    )
    # Uploaded file, stored under MEDIA_ROOT/imports/ (a Docker volume in dev).
    file = models.FileField(upload_to="imports", max_length=500)
    line_numbers = models.IntegerField(default=0)
    error_numbers = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    # Outcome of the import: counts and lines in error, or why the file was refused.
    message = models.TextField(blank=True)

    class Meta:
        db_table = table("data_imports")

    def run_parser(self):
        """Run the parser of this import's format, if available."""
        parser = PARSERS.get(self.format)
        if parser is None:
            return None
        if not self.pk:
            raise ValueError("The DataImport must be saved before it is processed.")
        if not self.file:
            raise ValueError("The DataImport has no file.")

        # Imported by path: the parsers themselves import DataImport.
        return import_string(parser)(self).import_data()

    def __str__(self):
        return f"{self.source} {self.date_import:%Y-%m-%d %H:%M}"


def data_version():
    """Changes when an import ends (done) or is deleted: a cache key for what is
    computed from the imported data. Not when a row is edited in the admin."""
    done = DataImport.objects.filter(status=DataImport.Status.DONE)
    version = done.aggregate(count=Count("id"), last=Max("id"))
    return f"{version['count']}-{version['last']}"


class ExternalLayer(models.Model):
    """A GeoJSON layer of another site (Biodiv'Sports, a national park...), offered
    on the map. The browser loads it when the user checks it, following the
    ``next`` links of a paginated API.
    """

    label = models.CharField(max_length=255)
    url = models.URLField(max_length=2000, help_text="FeatureCollection GeoJSON, en WGS84.")
    description = models.TextField(
        blank=True, help_text="Affichée au survol du nom de la couche (contenu, producteur…)."
    )
    properties = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Attributs affichés au clic, séparés par des virgules ; vide : tous.",
    )
    label_property = models.CharField(
        max_length=100,
        blank=True,
        help_text="Attribute holding the name of each feature, shown as the title of its detail (optional).",
    )
    color = models.CharField(max_length=7, default="#3388ff")
    color_property = models.CharField(
        max_length=100, blank=True, help_text="Attribut dont la valeur choisit la couleur (facultatif)."
    )
    colors = models.JSONField(
        default=dict,
        blank=True,
        help_text='Valeur → couleur, ex. {"IC": "#2e9e5b", "PR": "#c0392b"} ; '
        "les autres valeurs prennent la couleur ci-dessus.",
    )

    class Meta:
        db_table = table("external_layers")

    def __str__(self):
        return self.label


class InstanceSettings(models.Model):
    """Settings of this instance, edited in the admin: a single row (``load``)."""

    # ref_geo is loaded outside of Django and may be reloaded: no database constraint.
    default_area = models.ForeignKey(
        LArea,
        on_delete=models.SET_NULL,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
        help_text="Area that filters the map when it opens (e.g. the national park). "
        "Users can change or remove it.",
    )

    class Meta:
        db_table = table("instance_settings")

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "Instance settings"


class LayerGroup(models.Model):
    """A section of the map's layer list, ranked in the admin. Created by migration 0011."""

    code = models.CharField(max_length=20, unique=True)
    label = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(help_text="Rang de la section, la plus petite en premier.")

    class Meta:
        db_table = table("layer_groups")
        ordering = ["order"]

    def __str__(self):
        return self.label


class LayerOrder(models.Model):
    """Rank of a layer in its section of the map's layer list, edited in the admin.

    The admin lists every layer of the map (``sync``): only their ranks are edited.
    """

    layer = models.CharField(max_length=100, unique=True)
    group = models.ForeignKey(LayerGroup, on_delete=models.CASCADE, related_name="layers")
    label = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(help_text="Rang dans sa section, le plus petit en premier.")

    class Meta:
        db_table = table("layer_orders")
        ordering = ["group__order", "order"]

    def __str__(self):
        return self.label

    @classmethod
    def sync(cls):
        """One row per layer of the map: the new layers last, the removed ones deleted."""
        layers = [layer for source in LAYER_SOURCES for layer in source()] + [
            (f"external/{layer.pk}", "external", layer.label) for layer in ExternalLayer.objects.order_by("label")
        ]
        cls.objects.exclude(layer__in=[layer for layer, _, _ in layers]).delete()
        groups = {group.code: group for group in LayerGroup.objects.all()}
        # Existing layers updated first: one that changed section no longer counts in the old one.
        new = [
            (layer, groups[code], label)
            for layer, code, label in layers
            if not cls.objects.filter(layer=layer).update(label=label, group=groups[code])
        ]
        for layer, group, label in new:
            last = group.layers.aggregate(Max("order"))["order__max"] or 0
            cls.objects.create(layer=layer, label=label, group=group, order=last + 10)
