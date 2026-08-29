from django.contrib.auth.views import LoginView, LogoutView
from django.http import Http404
from django.shortcuts import redirect, render
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
        return reverse_lazy("portal:home")


class TenantLogoutView(LogoutView):
    next_page = reverse_lazy("portal:portal-login")

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


def home(request):
    """
    Tenant landing page. Pulls real account/org details from the DB.
    """
    tenant_ref = getattr(request, "tenant", None)
    if tenant_ref is None:
        raise Http404

    host = request.get_host().split(":")[0].lower()
    return redirect(f"http://{host}:4200/#/login")