from django.urls import path
from .views import admin_dashboard, data_quality_dashboard, login_view, run_etl_via_github

urlpatterns = [
    path('', admin_dashboard, name='admin_dashboard'),
    path('login/', login_view, name='login_view'),
    path('data-quality/', data_quality_dashboard, name='data_quality_dashboard'),
    path('run-etl-github/', run_etl_via_github, name='run_etl_github'),
]
