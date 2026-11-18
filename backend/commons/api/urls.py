from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("data-sources", views.DataSourceViewSet, basename="data-source")
router.register("data-imports", views.DataImportViewSet, basename="data-import")
router.register("practices", views.PracticeViewSet, basename="practice")
router.register("external-layers", views.ExternalLayerViewSet, basename="external-layer")

urlpatterns = [
    path("instance-settings", views.InstanceSettingsView.as_view(), name="instance-settings"),
    *router.urls,
]
