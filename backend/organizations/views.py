from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsPlatformSupportOrAbove, IsSuperAdmin
from tenants.models import Tenant

from .models import Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.prefetch_related("tenants").all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsPlatformSupportOrAbove]
    filterset_fields = ["org_type", "country", "kyc_verified"]

    def get_permissions(self):
        if self.action in ("create", "verify_kyc"):
            return [IsSuperAdmin()]
        return super().get_permissions()

    @transaction.atomic
    def perform_create(self, serializer):
        org = serializer.save()
        # A PENDING Tenant record is created immediately so the admin
        # dashboard shows "awaiting provisioning" right away; the actual
        # DB/Fineract provisioning only kicks off once KYC is verified
        # (see verify_kyc below), matching the Section 5 state machine.
        tenant_code = self._suggest_tenant_code(org.trading_name or org.legal_name)
        Tenant.objects.create(
            organization=org,
            tenant_code=tenant_code,
            db_name=f"tenant_{tenant_code}",
            fineract_tenant_identifier=tenant_code,
            status=Tenant.Status.PENDING,
        )

    @staticmethod
    def _suggest_tenant_code(name: str) -> str:
        from django.utils.text import slugify

        base = slugify(name)[:24] or "org"
        code = base
        suffix = 1
        while Tenant.objects.filter(tenant_code=code).exists():
            suffix += 1
            code = f"{base}{suffix}"
        return code

    @action(detail=True, methods=["post"])
    def verify_kyc(self, request, pk=None):
        org = self.get_object()
        org.kyc_verified = True
        org.save(update_fields=["kyc_verified"])

        from provisioning.models import ProvisionJob
        from provisioning.tasks import run_provisioning

        tenant = org.tenants.first()
        if tenant and tenant.status == Tenant.Status.PENDING:
            job = ProvisionJob.objects.create(tenant=tenant)
            run_provisioning.delay(str(job.id))

        return Response(OrganizationSerializer(org).data)
