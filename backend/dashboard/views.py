from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.text import slugify

from organizations.models import Organization
from provisioning.models import ProvisionJob
from provisioning.services import ProvisioningService
from tenants.models import Tenant

from .forms import CreateOrganizationForm, StaffLoginForm


class StaffLoginView(LoginView):
    template_name = "dashboard/login.html"
    authentication_form = StaffLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("dashboard:tenant-list")


class StaffLogoutView(LogoutView):
    next_page = reverse_lazy("dashboard:login")


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = reverse_lazy("dashboard:login")

    def test_func(self):
        return self.request.user.is_platform_staff or self.request.user.is_superuser


def _unique_tenant_code(base: str) -> str:
    code = slugify(base)[:24] or "org"
    candidate = code
    suffix = 1
    while Tenant.objects.filter(tenant_code=candidate).exists():
        suffix += 1
        candidate = f"{code}{suffix}"
    return candidate


@login_required(login_url="dashboard:login")
def tenant_list(request):
    if not (request.user.is_platform_staff or request.user.is_superuser):
        return redirect("dashboard:login")
    tenants = list(Tenant.objects.select_related("organization").prefetch_related("domains").order_by("-created_at"))
    # attach latest provision job to each tenant to avoid per-row queries in template
    jobs = ProvisionJob.objects.filter(tenant__in=tenants).order_by("-started_at")
    latest = {}
    for j in jobs:
        if j.tenant_id not in latest:
            latest[j.tenant_id] = j
    for t in tenants:
        t.latest_job = latest.get(t.id)
    host = request.get_host()
    current_port = host.split(":")[1] if ":" in host else ""
    return render(request, "dashboard/tenant_list.html", {"tenants": tenants, "current_port": current_port})


@login_required(login_url="dashboard:login")
def create_organization(request):
    if not (request.user.is_platform_staff or request.user.is_superuser):
        return redirect("dashboard:login")

    if request.method == "POST":
        form = CreateOrganizationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            org = Organization.objects.create(
                legal_name=data["legal_name"],
                trading_name=data["legal_name"],
                org_type=data["org_type"],
                registration_number=data["registration_number"],
                contact_email=data["contact_email"],
                contact_phone=data["contact_phone"],
                kyc_verified=True,  # simplified flow — no separate KYC step
            )
            tenant_code = _unique_tenant_code(data["subdomain"] or data["legal_name"])
            tenant = Tenant.objects.create(
                organization=org,
                tenant_code=tenant_code,
                db_name=f"tenant_{tenant_code}",
                fineract_tenant_identifier=tenant_code,
                status=Tenant.Status.PENDING,
            )

            job = ProvisionJob.objects.create(tenant=tenant)
            service = ProvisioningService(job)
            try:
                service.run()
                request.session["just_created_password"] = service.registrar.last_created_password
            except Exception as exc:  # noqa: BLE001
                request.session["just_created_password"] = None
                request.session["provisioning_error"] = str(exc)

            return redirect("dashboard:tenant-detail", tenant_id=tenant.id)
    else:
        form = CreateOrganizationForm()

    return render(request, "dashboard/create_organization.html", {"form": form})


@login_required(login_url="dashboard:login")
def tenant_detail(request, tenant_id):
    if not (request.user.is_platform_staff or request.user.is_superuser):
        return redirect("dashboard:login")

    tenant = get_object_or_404(Tenant.objects.select_related("organization").prefetch_related("domains"), id=tenant_id)
    domain = tenant.primary_domain

    # One-time reveal: pulled from the session and cleared immediately so a
    # page refresh (or someone else opening the same link) never sees it.
    admin_password = request.session.pop("just_created_password", None)
    provisioning_error = request.session.pop("provisioning_error", None)

    admin_user = tenant.users.filter(role="CEO").first()
    latest_job = tenant.provision_jobs.order_by("-started_at").first()

    subdomain_url = None
    if domain:
        host = request.get_host()
        port = host.split(":")[1] if ":" in host else ""
        subdomain_url = f"http://{domain.hostname}{':' + port if port else ''}/"

    return render(request, "dashboard/tenant_detail.html", {
        "tenant": tenant,
        "domain": domain,
        "admin_user": admin_user,
        "admin_password": admin_password,
        "provisioning_error": provisioning_error,
        "latest_job": latest_job,
        "subdomain_url": subdomain_url,
    })


@login_required(login_url="dashboard:login")
def tenant_retry(request, tenant_id):
    if not (request.user.is_platform_staff or request.user.is_superuser):
        return redirect("dashboard:login")

    tenant = get_object_or_404(Tenant, id=tenant_id)
    job = ProvisionJob.objects.create(tenant=tenant)
    service = ProvisioningService(job)
    try:
        service.run()
        request.session["just_created_password"] = service.registrar.last_created_password
    except Exception as exc:  # noqa: BLE001
        request.session["provisioning_error"] = str(exc)
    return redirect("dashboard:tenant-detail", tenant_id=tenant.id)
