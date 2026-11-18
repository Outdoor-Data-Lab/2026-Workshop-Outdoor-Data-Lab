from celery import shared_task
from django.utils.module_loading import import_string

from .models import PARSERS, DataImport
from .parsers import describe_errors


@shared_task
def run_import(import_id):
    """Import the file of a pending import, then record its outcome.

    A refused file imports nothing: the import is kept as failed, with the
    reason, and the file is deleted.
    """
    data_import = DataImport.objects.select_related("source").get(pk=import_id)
    parser = import_string(PARSERS[data_import.format])(data_import)
    try:
        count = parser.import_data()
    except ValueError as error:
        fail(data_import, f"File refused, nothing imported: {error}")
        return
    except Exception:
        fail(data_import, "Unexpected error, nothing imported: see the worker logs.")
        raise
    data_import.status = DataImport.Status.DONE
    data_import.message = f"{count} item(s) imported, {data_import.error_numbers} line(s) in error"
    if parser.errors:
        data_import.message += f": {describe_errors(parser.errors)}"
    data_import.message += "."
    data_import.save(update_fields=["status", "message"])


def fail(data_import, message):
    data_import.file.delete(save=False)
    data_import.status = DataImport.Status.FAILED
    data_import.message = message
    data_import.save(update_fields=["file", "status", "message"])
