"""Shared base of the parsers of every domain: one imported file -> rows saved.

A parser reads its file in `read()`, which returns the number of lines read and
the rows to save; `save()` writes them, the way of its domain (traffic: objects
and measures; biodiversity: taxon records). `import_data()` does both in one
transaction, then records on the import the lines read and the lines in error.
"""

from abc import ABC, abstractmethod

import pandas as pd
from django.db import transaction

from .models import DataImport


class ImportParser(ABC):
    NAME = ""  # used in error messages
    CONTENT = ""  # what the file holds (traces, points...), shown in the admin above EXAMPLE
    EXAMPLE = ""  # expected file, shown in the admin when the source is selected

    def __init__(self, data_import: DataImport):
        self.data_import = data_import
        self.source = data_import.source

    @abstractmethod
    def read(self) -> tuple[int, pd.DataFrame]:
        """Read the file: return the number of lines read and the rows to save."""

    @abstractmethod
    def save(self, rows: pd.DataFrame) -> None:
        """Write the rows read; raise ValueError to refuse the file (nothing is kept)."""

    def error_count(self, line_count: int, rows: pd.DataFrame) -> int:
        """Lines read but not saved, by default when each row comes from one line."""
        return line_count - len(rows)

    def import_data(self) -> int:
        """Save the rows read from the file; return their number."""
        line_count, rows = self.read()
        with transaction.atomic():
            self.save(rows)
            self.data_import.line_numbers = line_count
            self.data_import.error_numbers = self.error_count(line_count, rows)
            self.data_import.save(update_fields=["line_numbers", "error_numbers"])
        return len(rows)
