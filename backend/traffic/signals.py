"""Deleting an import deletes the counting objects it created, unless another
import still gives them measures (CountingObject.data_import)."""

from django.db.models import Exists, OuterRef
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from commons.models import DataImport

from .models import CountingMeasure, CountingObject


@receiver(pre_delete)
def delete_objects_left_empty(sender, instance, **kwargs):
    # Sent with the class of the deleted import: DataImport or one of its proxies.
    if not isinstance(instance, DataImport):
        return
    other_measures = CountingMeasure.objects.filter(counting_object=OuterRef("pk")).exclude(data_import=instance)
    CountingObject.objects.filter(data_import=instance).exclude(Exists(other_measures)).delete()
