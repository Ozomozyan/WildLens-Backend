from django.urls import path
from .views import (
    user_dashboard, user_species_summary, user_predictions_map
)

urlpatterns = [
    path("",               user_dashboard,        name="user_dashboard"),
    path("species-summary/", user_species_summary, name="user_species_summary"),
    path("map/",             user_predictions_map, name="user_map"),
]
