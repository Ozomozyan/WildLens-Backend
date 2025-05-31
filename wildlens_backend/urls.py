# wildlens_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from dashboard.views import login_view

urlpatterns = [
    path("admin/", admin.site.urls),
    
    path("login/", login_view, name="login_view"),

    # API endpoints
    path("api/", include("api.urls")),

    # Admin dashboard
    path("admin-dashboard/", include("dashboard.urls_admin")),

    # User dashboard
    path("user-dashboard/",  include("dashboard.urls_user")),
]
