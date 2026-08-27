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
        return reverse_lazy("portal:home")


class TenantLogoutView(LogoutView):
    next_page = reverse_lazy("portal:portal-login")

    # Allow GET requests to perform logout (plain <a href> links, not just
    # a POST form). Note: this brings back the CSRF exposure Django 5
    # deliberately removed GET-logout to close — a malicious page or
    # <img src="/logout/"> embedded elsewhere could log a user out without
    # their intent. Low-severity (worst case is an unwanted logout, not
    # data loss or privilege escalation), but worth knowing it's a
    # deliberate trade-off, not an oversight.
    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


def home(request):
    """
    Tenant landing page. Pulls real account/org details from the DB (not
    just the lightweight SimpleNamespace TenantResolverMiddleware attaches
    to request.tenant) so the page can show membership, roles, database,
    and provisioning info rather than a bare placeholder.
    """
    tenant_ref = getattr(request, "tenant", None)
    if tenant_ref is None:
        raise Http404

    from django.conf import settings
    from django.db.models import Count

    from tenants.models import Tenant

    tenant = (
        Tenant.objects.select_related("organization")
        .prefetch_related("domains")
        .get(id=tenant_ref.id)
    )
    organization = tenant.organization

    subscription = None
    try:
        subscription = tenant.subscription
    except Exception:  # noqa: BLE001 — Subscription is an optional OneToOne
        subscription = None

    role_breakdown = None
    member_count = None
    if request.user.is_authenticated:
        role_breakdown = list(
            tenant.users.values("role").annotate(count=Count("id")).order_by("-count")
        )
        member_count = sum(r["count"] for r in role_breakdown)

    domain = tenant.primary_domain

    fineract_console_url = None
    if tenant.fineract_tenant_identifier:
        public_api_base = getattr(settings, "FINERACT_PUBLIC_URL", None)
        web_app_url = getattr(settings, "FINERACT_WEB_APP_URL", None)
        if public_api_base and web_app_url:
            fineract_console_url = (
                f"{web_app_url}/?"
                f"baseApiUrl={public_api_base}/fineract-provider&"
                f"tenantIdentifier={tenant.fineract_tenant_identifier}"
            )

    context = {
        "tenant": tenant,
        "organization": organization,
        "subscription": subscription,
        "domain": domain,
        "member_count": member_count,
        "role_breakdown": role_breakdown,
        "db_engine": "PostgreSQL",
        "fineract_console_url": fineract_console_url,
    }
    return render(request, "portal/home.html", context)