from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import (
    PredictView, PredictionViewSet,
    prediction_locations, species_info
)

router = SimpleRouter(trailing_slash=False)
router.register(r"predictions", PredictionViewSet, basename="predictions")

urlpatterns = [
    path("predict/",              PredictView.as_view(), name="predict"),
    path("prediction-locations/", prediction_locations,  name="prediction_locations"),
    path("species-info/",         species_info,          name="species_info"),
] + router.urls
