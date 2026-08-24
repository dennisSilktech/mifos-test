import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class FineractAPIError(Exception):
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Fineract API error {status_code}: {payload}")

    @classmethod
    def from_response(cls, response):
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        return cls(response.status_code, payload)


class FineractTimeoutError(Exception):
    pass


class FineractClient:
    """Per-tenant HTTP client — every call carries the Fineract-Platform-TenantId header."""

    def __init__(self, tenant_identifier: str, username: str, password: str, timeout=10, max_retries=3):
        self.base_url = settings.FINERACT_BASE_URL.rstrip("/")
        self.tenant_identifier = tenant_identifier
        self.auth = (username, password)
        self.timeout = timeout
        self.session = self._build_session(max_retries)

    @staticmethod
    def _build_session(max_retries):
        session = requests.Session()
        retry = Retry(
            total=max_retries, backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.mount("http://", HTTPAdapter(max_retries=retry))
        return session

    def request(self, method, path, timeout=None, **kwargs):
        headers = {"Fineract-Platform-TenantId": self.tenant_identifier, **kwargs.pop("headers", {})}
        try:
            resp = self.session.request(
                method, f"{self.base_url}{path}", auth=self.auth, headers=headers,
                timeout=timeout or self.timeout, verify=settings.FINERACT_VERIFY_SSL, **kwargs,
            )
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except requests.Timeout as exc:
            raise FineractTimeoutError(path) from exc
        except requests.HTTPError as exc:
            raise FineractAPIError.from_response(exc.response) from exc

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)
