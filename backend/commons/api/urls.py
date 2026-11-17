from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("data-source", views.DataSourceViewSet, basename="data-source")
router.register("data-import", views.DataImportViewSet, basename="data-import")

urlpatterns = router.urls