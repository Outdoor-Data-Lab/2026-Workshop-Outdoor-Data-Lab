from rest_framework.routers import DefaultRouter

from . import views

app_name = "biodiversity"

router = DefaultRouter()
router.register(
    "taxon-status-areas",
    views.TaxonStatusAreaViewSet,
    basename="taxon-status-area",
)

urlpatterns = router.urls
