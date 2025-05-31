from django.urls import path
from .views import (
    admin_dashboard, data_quality_dashboard, run_etl_via_github,
    run_training
)

urlpatterns = [
    path("",                     admin_dashboard,        name="admin_dashboard"),
    path("data-quality/",        data_quality_dashboard, name="data_quality"),
    path("run-etl-github/",      run_etl_via_github,     name="run_etl"),
    path("run-training/",        run_training,           name="run_training"),
]
