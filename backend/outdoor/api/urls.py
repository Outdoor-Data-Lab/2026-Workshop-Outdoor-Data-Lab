from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(r'offers/area', views.LAreaCountViewSet, basename='offer_area')
router.register(r'offers', views.OfferViewSet, basename='offer')

urlpatterns = router.urls
