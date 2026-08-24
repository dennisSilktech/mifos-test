from django.urls import path

from .views import add_custom_domain

urlpatterns = [
    path("custom-domains/", add_custom_domain, name="add-custom-domain"),
]
