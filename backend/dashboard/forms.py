from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class StaffLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not (user.is_platform_staff or user.is_superuser):
            raise ValidationError("This account does not have platform admin access.", code="not_staff")


class CreateOrganizationForm(forms.Form):
    legal_name = forms.CharField(max_length=255, label="Organization name")
    org_type = forms.ChoiceField(choices=[
        ("SACCO", "SACCO"), ("CHAMA", "Chama"),
        ("MFI", "Microfinance Institution"), ("LENDER", "Lending Organization"),
    ])
    registration_number = forms.CharField(max_length=100, label="Registration number")
    contact_email = forms.EmailField(label="Client admin email")
    contact_phone = forms.CharField(max_length=20, label="Client phone number")
    subdomain = forms.SlugField(
        max_length=32, required=False,
        help_text="Leave blank to auto-generate from the organization name.",
    )
