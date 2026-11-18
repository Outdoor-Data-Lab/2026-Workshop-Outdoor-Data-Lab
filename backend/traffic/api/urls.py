from django.urls import path
from rest_framework.routers import SimpleRouter

from . import tiles, views

router = SimpleRouter(trailing_slash=False)
router.register("areas", views.AreasViewSet, basename="areas")
router.register("units", views.UnitViewSet, basename="unit")
router.register("counting-object-types", views.CountingObjectTypeViewSet, basename="counting-object-type")
router.register("counting-objects", views.CountingObjectViewSet, basename="counting-object")
router.register("counting-measures", views.CountingMeasureViewSet, basename="counting-measure")

urlpatterns = [
    path("tiles/<int:z>/<int:x>/<int:y>.pbf", tiles.counting_object_tile, name="counting-object-tile"),
    *router.urls,
]
