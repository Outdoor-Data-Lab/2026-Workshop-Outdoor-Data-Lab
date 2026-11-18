"""Shared base of the parsers of every domain: one imported file -> rows saved.

A parser reads its file in `read()`, which returns the number of lines read and
the rows to save; `save()` writes them, the way of its domain (traffic: objects
and measures; biodiversity: taxon records; outdoor: offers). `import_data()` does
both in one transaction, then records on the import the lines read and the lines
in error. `preview()` reads the file and tells what `import_data()` would do,
without writing: `plan()` counts the changes, by kind.

A ValueError from `read()`, `plan()` or `save()` refuses the whole file.
"""

from abc import ABC, abstractmethod

import pandas as pd
from django.db import transaction

from .models import DataImport


def describe_errors(errors: list[tuple[int, str, str]], limit: int = 10) -> str:
    """The first lines in error, as "line 3 (id): reason; ..."."""
    described = "; ".join(
        f"line {number}{f' ({line_id})' if line_id else ''}: {reason}"
        for number, line_id, reason in errors[:limit]
    )
    if len(errors) > limit:
        described += f"; and {len(errors) - limit} more"
    return described


class ImportParser(ABC):
    LABEL = ""  # name of the format, offered on the import page
    NAME = ""  # used in error messages
    CONTENT = ""  # what the file holds (traces, points...), shown in the admin above EXAMPLE
    EXAMPLE = ""  # expected file, shown in the admin when the format is selected

    def __init__(self, data_import: DataImport):
        self.data_import = data_import
        self.source = data_import.source
        # Lines in error with their reason, when the parser knows them:
        # (line number, id, reason), filled by read().
        self.errors: list[tuple[int, str, str]] = []

    @abstractmethod
    def read(self) -> tuple[int, pd.DataFrame]:
        """Read the file: return the number of lines read and the rows to save."""

    @abstractmethod
    def save(self, rows: pd.DataFrame) -> None:
        """Write the rows read; raise ValueError to refuse the file (nothing is kept)."""

    def plan(self, rows: pd.DataFrame) -> dict[str, int]:
        """What save(rows) would change, by kind (label -> count), without writing."""
        return {}

    def error_count(self, line_count: int, rows: pd.DataFrame) -> int:
        """Lines read but not saved, by default when each row comes from one line."""
        return line_count - len(rows)

    def preview(self) -> dict:
        """What import_data() would do: lines read, rows to save, changes, lines in error."""
        line_count, rows = self.read()
        return {
            "lines": line_count,
            "rows": len(rows),
            "changes": self.plan(rows),
            "errors": self.error_count(line_count, rows),
        }

    def import_data(self) -> int:
        """Save the rows read from the file; return their number."""
        line_count, rows = self.read()
        with transaction.atomic():
            self.save(rows)
            self.data_import.line_numbers = line_count
            self.data_import.error_numbers = self.error_count(line_count, rows)
            self.data_import.save(update_fields=["line_numbers", "error_numbers"])
        return len(rows)
