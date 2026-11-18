"""Find TaxRef reference names (cd_ref) from scientific names.

TaxRef is loaded by TaxHub in the taxonomie.taxref table of the same database
(see the taxhub service of docker-compose-dev.yaml); it is not a Django model.
"""

from collections import defaultdict
from collections.abc import Hashable

from django.db import connection

TAXREF_TABLE = "taxonomie.taxref"


def find_cd_refs(
    taxa: dict[Hashable, tuple[str, list[str]]],
) -> dict[Hashable, int | None]:
    """Return the cd_ref of each taxon, or None when it is not found or ambiguous.

    `taxa` maps any key to (kingdom, candidate names by priority). Each
    candidate is compared to the TaxRef full name (with authorship), then to
    the name without authorship, within the same kingdom. The first candidate
    that matches decides: one cd_ref is kept, several (homonyms) give None.

    Example (cd_ref values are illustrative), with GBIF taxonKey as keys:

        find_cd_refs({
            "3Z5VY": ("Animalia", ["Melanargia galathea Linnaeus, 1758", "Melanargia galathea"]),
            "6T7B5": ("Plantae", ["Origanum vulgare L.", "Origanum vulgare"]),
            "XXXXX": ("Animalia", ["Mystery mystery"]),
        })
        -> {"3Z5VY": 53865, "6T7B5": 105404, "XXXXX": None}
    """
    kingdoms = {kingdom for kingdom, _ in taxa.values()}
    names = {name for _, candidates in taxa.values() for name in candidates}
    with connection.cursor() as cursor:
        cursor.execute("select to_regclass(%s)", [TAXREF_TABLE])
        if cursor.fetchone()[0] is None:
            raise ValueError(
                "TaxRef is not loaded (no taxonomie.taxref table): start the taxhub service."
            )
        cursor.execute(
            f"""
            select regne, nom_complet, lb_nom, cd_ref from {TAXREF_TABLE}
            where regne = any(%s) and (nom_complet = any(%s) or lb_nom = any(%s))
            """,
            [list(kingdoms), list(names), list(names)],
        )
        matches = cursor.fetchall()

    by_full_name, by_name = defaultdict(set), defaultdict(set)
    for kingdom, full_name, name, cd_ref in matches:
        by_full_name[kingdom, full_name].add(cd_ref)
        by_name[kingdom, name].add(cd_ref)

    def cd_ref(kingdom, candidates):
        for name in candidates:
            # Full name (with authorship) first, then name without authorship.
            found = by_full_name.get((kingdom, name)) or by_name.get((kingdom, name))
            if found:
                # Several cd_ref for the same name: homonyms, can't choose.
                return next(iter(found)) if len(found) == 1 else None
        return None

    return {
        key: cd_ref(kingdom, candidates) for key, (kingdom, candidates) in taxa.items()
    }
