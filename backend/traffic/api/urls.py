from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("unit", views.UnitViewSet, basename="unit")
router.register(
    "counting-object-type", views.CountingObjectTypeViewSet, basename="counting-object-type"
)
router.register("counting-object", views.CountingObjectViewSet, basename="counting-object")
router.register("counting-measure", views.CountingMeasureViewSet, basename="counting-measure")

urlpatterns = router.urls