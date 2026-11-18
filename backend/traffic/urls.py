from django.urls import path

from .views import ScoreMapView, ScoreSourcesView

app_name = "traffic"

urlpatterns = [
    path("score-map/", ScoreMapView.as_view(), name="score-map"),
    path("sources/", ScoreSourcesView.as_view(), name="score-sources"),
]
