from django.conf import settings

from .client import FineractAPIError, FineractClient


class FineractAdminClient(FineractClient):
    """
    Talks to Fineract's platform-tenant management endpoints using the
    Fineract super-admin (default tenant) credentials. Used exclusively by
    provisioning.services.TenantRegistrar — never exposed to end users.
    """

    def __init__(self):
        super().__init__(
            tenant_identifier="default",
            username=settings.FINERACT_ADMIN_USERNAME,
            password=settings.FINERACT_ADMIN_PASSWORD,
        )

    def create_tenant(self, identifier: str, name: str, db_host: str, db_name: str):
        return self.post(
            "/tenants",
            json={
                "tenantIdentifier": identifier,
                "name": name,
                "timezoneId": "Africa/Nairobi",
                "dbHostname": db_host,
                "dbName": db_name,
            },
        )

    def delete_tenant(self, identifier: str):
        try:
            self.request("DELETE", f"/tenants/{identifier}")
        except Exception:  # noqa: BLE001 — best-effort compensating action
            pass

    def create_tenant_user(self, tenant_identifier: str, username: str, password: str):
        tenant_client = FineractClient(
            tenant_identifier=tenant_identifier,
            username=settings.FINERACT_ADMIN_USERNAME,
            password=settings.FINERACT_ADMIN_PASSWORD,
        )
        office_id = self._resolve_head_office_id(tenant_client)
        role_id = self._resolve_super_user_role_id(tenant_client)

        return tenant_client.post(
            "/users",
            json={
                "username": username,
                "password": password,
                "repeatPassword": password,
                "officeId": office_id,
                "roles": [role_id],
                "sendPasswordToEmail": False,
            },
        )

    @staticmethod
    def _resolve_head_office_id(tenant_client: FineractClient) -> int:
        """
        A freshly-provisioned Fineract tenant seeds exactly one office
        (Head Office, parentId null) — resolved by lookup rather than
        assumed to be id=1, since that isn't guaranteed across Fineract
        versions/seed data.
        """
        offices = tenant_client.get("/offices")
        head_office = next((o for o in offices if o.get("parentId") is None), None)
        if head_office is None and offices:
            head_office = offices[0]
        if head_office is None:
            raise FineractAPIError(404, "No office found for new tenant; cannot create admin user.")
        return head_office["id"]

    @staticmethod
    def _resolve_super_user_role_id(tenant_client: FineractClient) -> int:
        """Resolves the seeded 'Super user' role by name rather than assuming id=1."""
        roles = tenant_client.get("/roles")
        super_role = next((r for r in roles if r.get("name", "").lower() == "super user"), None)
        if super_role is None and roles:
            super_role = roles[0]
        if super_role is None:
            raise FineractAPIError(404, "No role found for new tenant; cannot create admin user.")
        return super_role["id"]
