from django.db import connection
from django.db.models import ProtectedError
from django.test import TestCase

from .models import DataImport, DataSource


class CommonsTests(TestCase):
    def test_tables_are_in_commons_schema(self):
        with connection.cursor() as cursor:
            cursor.execute("select tablename from pg_tables where schemaname = 'commons'")
            tables = {row[0] for row in cursor.fetchall()}
        self.assertEqual(tables, {"data_sources", "data_imports"})

    def test_source_with_imports_cannot_be_deleted(self):
        source = DataSource.objects.create(code_source="gbif", source="GBIF")
        DataImport.objects.create(source=source, line_numbers=10, error_numbers=1)
        with self.assertRaises(ProtectedError):
            source.delete()
