from django.urls import path
from .views import (
    user_dashboard, user_species_summary, user_predictions_map, user_stats_api, species_summary_api
)

urlpatterns = [
    path("",               user_dashboard,        name="user_dashboard"),
    path("species-summary/", user_species_summary, name="user_species_summary"),
    path("species-summary-data/", species_summary_api, name="species_summary_api"),
    path("map/",             user_predictions_map, name="user_map"),
    path("user-stats/",      user_stats_api, name="user_stats_api"),
]
