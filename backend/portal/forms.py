# portal/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class TenantLoginForm(AuthenticationForm):
    """
    Login form for a tenant's own users (CEO, Branch Manager, Loan Officer,
    Cashier, Member) on their subdomain — e.g. fl001.banking.silktechagency.com.
    Deliberately does NOT check is_platform_staff (that's StaffLoginForm's
    job, for the separate /dashboard/login/ admin console).
    """

    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        request_tenant = getattr(self.request, "tenant", None)
        if request_tenant is None or str(user.tenant_id) != str(request_tenant.id):
            raise ValidationError("This account is not associated with this organization.", code="wrong_tenant")