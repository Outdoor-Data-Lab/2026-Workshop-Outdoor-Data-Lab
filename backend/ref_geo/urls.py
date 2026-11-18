from rest_framework.routers import SimpleRouter

from . import views

app_name = "ref_geo"

router = SimpleRouter(trailing_slash=False)
router.register("area-types", views.BibAreasTypeViewSet, "area-type")
router.register("linear-types", views.BibLinearsTypeViewSet, "linear-type")
router.register("point-types", views.BibPointsTypeViewSet, "point-type")
router.register("areas", views.LAreaViewSet, "area")
router.register("linears", views.LLinearViewSet, "linear")
router.register("points", views.LPointViewSet, "point")
router.register("municipalities", views.LiMunicipalityViewSet, "municipality")
router.register("grids", views.LiGridViewSet, "grid")
router.register("linear-groups", views.TLinearGroupViewSet, "linear-group")

urlpatterns = router.urls
