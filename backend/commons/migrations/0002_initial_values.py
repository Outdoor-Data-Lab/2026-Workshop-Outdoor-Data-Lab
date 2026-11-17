"""Initial values of the data sources and practices reference tables."""

from django.db import migrations

# The same list holds providers (the application that supplies data to us)
# and origins (the application that produced it). More can be added in the admin.
DATA_SOURCES = [
    # Providers
    ("outdoorvision", "OutdoorVision"),
    ("ecocompteur", "Eco-Compteur"),
    ("strava", "Strava"),
    ("geotrek", "Geotrek"),
    ("gbif", "GBIF"),
    ("inpn", "INPN"),
    ("geonature", "GeoNature"),
    ("inaturalist", "iNaturalist"),
    # Origin applications, behind a provider such as OutdoorVision
    ("garmin", "Garmin"),
    ("komoot", "Komoot"),
    ("visorando", "Visorando"),
]

# Broad practices, without parent.
BROAD_PRACTICES = [
    ("walking", "Marcher"),
    ("running", "Courir"),
    ("cycling", "Pédaler"),
    ("flying", "Voler"),
    ("boating", "Naviguer"),
    ("climbing", "Grimper"),
    ("skiing", "Skier"),
    ("riding", "Chevaucher"),
]

# Finer practices: (code, label, parent code).
FINER_PRACTICES = [
    ("hiking", "Randonnée pédestre", "walking"),
    ("horse_riding", "Equestre", "riding"),
    ("trail_running", "Trail", "running"),
    ("mountain_biking", "VTT", "cycling"),
    ("road_cycling", "Cyclo", "cycling"),
    ("gravel", "Gravel", "cycling"),
    ("alpine_skiing", "Ski alpin", "skiing"),
    ("ski_touring", "Ski de rando", "skiing"),
    ("kayaking", "Kayak", "boating"),
    ("canyoning", "Canyoning", "boating"),
    ("rock_climbing", "Escalade", "climbing"),
    ("via_ferrata", "Via ferrata", "climbing"),
    ("mountaineering", "Alpinisme", "climbing"),
    ("paragliding", "Parapente", "flying"),
    ("snowshoeing", "Raquette", "walking"),
]


def add_values(apps, schema_editor):
    DataSource = apps.get_model("commons", "DataSource")
    Practice = apps.get_model("commons", "Practice")
    for code, label in DATA_SOURCES:
        DataSource.objects.update_or_create(code=code, defaults={"label": label})
    broad = {}
    for code, label in BROAD_PRACTICES:
        broad[code], _ = Practice.objects.update_or_create(
            code=code, defaults={"label": label, "parent": None}
        )
    for code, label, parent in FINER_PRACTICES:
        Practice.objects.update_or_create(
            code=code, defaults={"label": label, "parent": broad[parent]}
        )


def remove_values(apps, schema_editor):
    Practice = apps.get_model("commons", "Practice")
    # Children first: a parent with children is protected.
    Practice.objects.filter(code__in=[code for code, _, _ in FINER_PRACTICES]).delete()
    Practice.objects.filter(code__in=[code for code, _ in BROAD_PRACTICES]).delete()
    apps.get_model("commons", "DataSource").objects.filter(
        code__in=[code for code, _ in DATA_SOURCES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("commons", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_values, remove_values),
    ]
