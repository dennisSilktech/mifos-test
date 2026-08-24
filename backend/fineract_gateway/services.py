from .client import FineractClient


def client_for_tenant(tenant) -> FineractClient:
    from tenants.models import EncryptedCredential  # noqa: avoid circular import at module load

    # Tenant service-account credentials are provisioned alongside the
    # Fineract tenant registration; stored/retrieved the same way as DB
    # credentials (see tenants.models.EncryptedCredential pattern).
    from authentication.models import User

    admin_user = User.objects.filter(tenant_id=tenant.id, role=User.Role.CEO).first()
    from django.conf import settings

    return FineractClient(
        tenant_identifier=tenant.fineract_tenant_identifier,
        username=admin_user.email if admin_user else settings.FINERACT_ADMIN_USERNAME,
        password=settings.FINERACT_ADMIN_PASSWORD,
    )


class ClientService:
    def __init__(self, client: FineractClient):
        self.client = client

    def create_client(self, first_name, last_name, office_id=1):
        return self.client.post(
            "/clients",
            json={
                "firstname": first_name, "lastname": last_name, "officeId": office_id,
                "active": True, "activationDate": None, "locale": "en", "dateFormat": "dd MMMM yyyy",
            },
        )

    def get_client(self, client_id):
        return self.client.get(f"/clients/{client_id}")

    def list_clients(self, office_id=None):
        params = {"officeId": office_id} if office_id else {}
        return self.client.get("/clients", params=params)


class LoanService:
    def __init__(self, client: FineractClient):
        self.client = client

    def apply_loan(self, client_id, product_id, principal, term_months):
        return self.client.post(
            "/loans",
            json={
                "clientId": client_id, "productId": product_id, "principal": principal,
                "loanTermFrequency": term_months, "loanTermFrequencyType": 2,
                "loanType": "individual", "locale": "en", "dateFormat": "dd MMMM yyyy",
            },
        )

    def approve_loan(self, loan_id, approved_amount):
        return self.client.post(
            f"/loans/{loan_id}?command=approve",
            json={"approvedLoanAmount": approved_amount, "locale": "en", "dateFormat": "dd MMMM yyyy"},
        )

    def disburse_loan(self, loan_id, actual_disbursement_date):
        return self.client.post(
            f"/loans/{loan_id}?command=disburse",
            json={"actualDisbursementDate": actual_disbursement_date, "locale": "en", "dateFormat": "dd MMMM yyyy"},
            timeout=20,
        )

    def get_repayment_schedule(self, loan_id):
        return self.client.get(f"/loans/{loan_id}", params={"associations": "repaymentSchedule"})


class SavingsService:
    def __init__(self, client: FineractClient):
        self.client = client

    def open_account(self, client_id, product_id):
        return self.client.post(
            "/savingsaccounts",
            json={"clientId": client_id, "productId": product_id, "locale": "en", "dateFormat": "dd MMMM yyyy"},
        )

    def deposit(self, account_id, amount, transaction_date):
        return self.client.post(
            f"/savingsaccounts/{account_id}/transactions?command=deposit",
            json={"transactionDate": transaction_date, "transactionAmount": amount,
                  "locale": "en", "dateFormat": "dd MMMM yyyy"},
        )

    def withdraw(self, account_id, amount, transaction_date):
        return self.client.post(
            f"/savingsaccounts/{account_id}/transactions?command=withdrawal",
            json={"transactionDate": transaction_date, "transactionAmount": amount,
                  "locale": "en", "dateFormat": "dd MMMM yyyy"},
        )


class MemberService:
    """Thin wrapper over ClientService + shares, for SACCO/Chama membership semantics."""

    def __init__(self, client: FineractClient):
        self.client = client
        self.clients = ClientService(client)

    def enroll_member(self, first_name, last_name, office_id=1):
        return self.clients.create_client(first_name, last_name, office_id)

    def assign_shares(self, client_id, product_id, number_of_shares):
        return self.client.post(
            "/shareaccounts",
            json={"clientId": client_id, "productId": product_id, "requestedShares": number_of_shares,
                  "locale": "en", "dateFormat": "dd MMMM yyyy"},
        )


class JournalService:
    def __init__(self, client: FineractClient):
        self.client = client

    def post_journal_entry(self, office_id, transaction_date, credits, debits):
        return self.client.post(
            "/journalentries",
            json={
                "officeId": office_id, "transactionDate": transaction_date,
                "credits": credits, "debits": debits,
                "locale": "en", "dateFormat": "dd MMMM yyyy",
            },
        )

    def get_trial_balance(self, office_id):
        return self.client.get("/glclosures", params={"officeId": office_id})
