from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.StaffLoginView.as_view(), name="login"),
    path("logout/", views.StaffLogoutView.as_view(), name="logout"),
    path("", views.tenant_list, name="tenant-list"),
    path("create/", views.create_organization, name="create-organization"),
    path("tenants/<uuid:tenant_id>/", views.tenant_detail, name="tenant-detail"),
    path("tenants/<uuid:tenant_id>/retry/", views.tenant_retry, name="tenant-retry"),
]
