from rest_framework.routers import DefaultRouter

from . import views

app_name = "biodiversity"

router = DefaultRouter()
router.register(
    "synthetic_data",
    views.BiodivSyntheticDataAreaViewSet,
    basename="biodiv-synthetic-data",
)
router.register(
    "list_taxa",
    views.BiodivListTaxaAreaViewSet,
    basename="biodiv-list-taxa",
)

urlpatterns = router.urls
