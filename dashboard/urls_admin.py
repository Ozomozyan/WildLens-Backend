from django.urls import path
from .views import (
    admin_dashboard, data_quality_dashboard, run_etl_via_github,
    run_training, admin_stats_api, data_quality_api, logs_api, run_hpsearch, hpsearch_best_config
)

urlpatterns = [
    path("",                     admin_dashboard,        name="admin_dashboard"),
    path("data/",                admin_stats_api,        name="admin_stats_api"), 
    path("data-quality/",      data_quality_dashboard, name="data_quality"),
    path("data-quality-data/", data_quality_api, name="data_quality_api"),
    path("run-etl-github/",      run_etl_via_github,     name="run_etl"),
    path("run-training/",        run_training,           name="run_training"),
    path("run-hpsearch/",        run_hpsearch,         name="run_hpsearch"),
    path("hpsearch-best/",       hpsearch_best_config, name="hpsearch_best"),
    path("server-logs/", logs_api, name="server_logs_api"),
]
