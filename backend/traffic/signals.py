"""Deleting an import deletes the counting objects it created, unless another
import still gives them measures (CountingObject.data_import)."""

from django.db.models import Exists, OuterRef
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from commons.models import DataImport

from .models import CountingMeasure, CountingObject, TrafficImport


# Sent with the class of the deleted import: DataImport, or the TrafficImport proxy
# from the traffic import page. Not without sender: a receiver for every model
# makes Django load each measure of the import before deleting it.
@receiver(pre_delete, sender=DataImport)
@receiver(pre_delete, sender=TrafficImport)
def delete_objects_left_empty(sender, instance, **kwargs):
    other_measures = CountingMeasure.objects.filter(counting_object=OuterRef("pk")).exclude(data_import=instance)
    CountingObject.objects.filter(data_import=instance).exclude(Exists(other_measures)).delete()
