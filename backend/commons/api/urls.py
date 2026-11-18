from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("data-sources", views.DataSourceViewSet, basename="data-source")
router.register("data-imports", views.DataImportViewSet, basename="data-import")
router.register("practices", views.PracticeViewSet, basename="practice")

urlpatterns = router.urls
