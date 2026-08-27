from django.urls import path
from . import views

app_name = "portal"

urlpatterns = [
    # Named 'home' to resolve the get_success_url() reverse lookup
    path("", views.home, name="home"),
    path("login/", views.TenantLoginView.as_view(), name="portal-login"),
    path("logout/", views.TenantLogoutView.as_view(), name="portal-logout"),
]