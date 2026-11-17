from unittest.mock import patch

from django.db import connection
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase

from .models import DataImport, DataSource, PracticeCategory


class CommonsTests(TestCase):
    def test_tables_are_in_commons_schema(self):
        with connection.cursor() as cursor:
            cursor.execute("select tablename from pg_tables where schemaname = 'commons'")
            tables = {row[0] for row in cursor.fetchall()}
        self.assertEqual(tables, {"data_sources", "data_imports", "practice_categories"})

    def test_initial_practice_categories(self):
        self.assertEqual(
            set(PracticeCategory.objects.values_list("code", flat=True)),
            {"hiking", "running", "cycling", "flying", "boating", "climbing", "skiing", "riding"},
        )

    def test_source_with_imports_cannot_be_deleted(self):
        source = DataSource.objects.create(code="gbif", label="GBIF")
        DataImport.objects.create(source=source, file="gbif.csv", line_numbers=10, error_numbers=1)
        with self.assertRaises(ProtectedError):
            source.delete()


class DataImportParserTests(SimpleTestCase):
    def make_import(self, source_code="outdoorvision"):
        data_import = DataImport(
            source=DataSource(code_source=source_code, source=source_code),
            file="imports/outdoorvision.gpkg",
        )
        data_import.pk = 1
        return data_import

    @patch("traffic.parsers.outdoorvision.OutdoorVisionParser")
    def test_run_outdoorvision_parser(self, parser_class):
        data_import = self.make_import()
        parser_class.return_value.import_data.return_value = 2

        result = data_import.run_parser()

        parser_class.assert_called_once_with(data_import)
        parser_class.return_value.import_data.assert_called_once_with()
        self.assertEqual(result, 2)

    def test_source_without_parser_is_ignored(self):
        self.assertIsNone(self.make_import("gbif").run_parser())
