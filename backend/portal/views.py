# portal/views.py
from django.contrib.auth.views import LoginView, LogoutView
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse_lazy

from .forms import TenantLoginForm



class TenantLoginView(LoginView):
    template_name = "portal/login.html"
    authentication_form = TenantLoginForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "tenant", None) is None:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        # Update 'home' to include the 'portal:' namespace prefix
        return reverse_lazy("portal:home")

class TenantLogoutView(LogoutView):
    next_page = reverse_lazy("portal:portal-login")

    # Allow GET requests to perform logout
    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

def home(request):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise Http404
    return render(request, "portal/home.html", {"tenant": tenant})